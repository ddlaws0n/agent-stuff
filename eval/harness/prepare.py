#!/usr/bin/env python3
"""Create independent, ignored workspaces for the containerized eval pilot."""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS_BASE = REPO / "eval/results"
WORKSPACES_BASE = Path(tempfile.gettempdir())
DEFAULT_MODEL = "openrouter/z-ai/glm-5.3-flash"
MODELS = (DEFAULT_MODEL, "openrouter/openai/gpt-6-luna")
CASES = [("create-agentsmd", 1), ("create-github-actions", 1), ("manage-github-projects", 1)]


def run_name(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
        raise argparse.ArgumentTypeError("run name must be lowercase letters, digits, or hyphens")
    return value


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def node_fixture(root):
    put(root, "package.json", json.dumps({"name": "sample-node-app", "version": "1.0.0", "private": True, "type": "module", "scripts": {"test": "node --test", "lint": "node --check src/index.js", "build": "node --check src/index.js"}}, indent=2) + "\n")
    put(root, "package-lock.json", json.dumps({"name": "sample-node-app", "version": "1.0.0", "lockfileVersion": 3, "requires": True, "packages": {"": {"name": "sample-node-app", "version": "1.0.0"}}}, indent=2) + "\n")
    put(root, "src/index.js", "export function double(n) { return n * 2; }\n")
    put(root, "test/index.test.js", "import { test } from 'node:test';\nimport { strict as assert } from 'node:assert';\nimport { double } from '../src/index.js';\ntest('double', () => assert.equal(double(2), 4));\n")
    put(root, "README.md", "# Sample Node app\n\nUse `npm ci` to install the exact lockfile. Run `npm test` for unit tests, `npm run lint` for syntax checks, and `npm run build` for the build check. Node 22+ is required. This is a disposable evaluation fixture; do not deploy it.\n")


def board_fixture(root):
    put(root, "README.md", "# Synthetic homelab board\n\nThe `gh` command in this evaluation workspace is a read-only, local fixture. All project issues are invented; never access a real GitHub account. Use only local commands and do not mutate external state.\n")
    put(root, "bin/gh", (Path(__file__).resolve().parent / "mock-gh.py").read_text(encoding="utf-8"))
    (root / "bin/gh").chmod(0o755)
    (root / "gh-config").mkdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", type=run_name, required=True, help="unique result/workspace name (never overwrites)")
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    options = parser.parse_args(argv)
    results = RESULTS_BASE / options.run_name
    workspaces = WORKSPACES_BASE / f"pi-skill-{options.run_name}"
    if results.exists() or workspaces.exists():
        raise SystemExit(f"Refusing to overwrite existing results/workspaces: {results}, {workspaces}")
    model = f"{options.model}:high"
    cells = []
    for skill, case_id in CASES:
        case = next(x for x in json.loads((REPO / f"skills/{skill}/evals/evals.json").read_text())["evals"] if x["id"] == case_id)
        if not case.get("assertions"):
            raise SystemExit(f"Pilot case {skill}/{case_id} needs explicit assertions before execution")
        for cell in ("with_skill", "without_skill"):
            key = f"{skill}-{cell}"
            root = results / skill / f"eval-{case_id}" / cell
            workspace = workspaces / skill / f"eval-{case_id}" / cell
            workspace.mkdir(parents=True)
            (root / "outputs").mkdir(parents=True)
            subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(workspace)], check=True)
            if skill == "manage-github-projects":
                board_fixture(workspace)
                subprocess.run(["git", "-C", str(workspace), "remote", "add", "origin", "https://github.com/fixture-synthetic-skill-eval/homelab.git"], check=True)
            else:
                node_fixture(workspace)
                if skill == "create-github-actions":
                    put(workspace, ".github/workflows/existing.yml", "name: Existing check\non: push\npermissions:\n  contents: read\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm test\n")
            if cell == "with_skill":
                dest = workspace / ".agents/skills" / skill
                dest.parent.mkdir(parents=True)
                shutil.copytree(REPO / "skills" / skill, dest)
            task = f"{case['prompt']}\n\nUse only this disposable fixture workspace. Do not access the network or a real GitHub account. Do not edit .agents/ or .pi/ configuration. For the project-board case, use the local mock gh only. Report what you changed or observed and which checks you actually ran."
            metadata = {"eval_id": case_id, "eval_name": case.get("name", skill), "prompt": task, "expected_output": case["expected_output"], "assertions": case.get("assertions", [])}
            put(root, "eval_metadata.json", json.dumps(metadata, indent=2) + "\n")
            cells.append({"key": key, "skill": skill, "condition": cell, "cwd": str(workspace), "root": str(root), "task": task, "model": model})
    manifest = {"run_name": options.run_name, "model": model, "cells": cells}
    put(results, "manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(cells)} independent cells under {results} with {model}")


if __name__ == "__main__":
    main()
