#!/usr/bin/env python3
"""Grade the three pilot cases against files, commands, and synthetic board truth."""
import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def tool_calls(root):
    result = []
    for line in (root / "transcript.jsonl").read_text().splitlines():
        entry = json.loads(line)
        if entry.get("type") in ("message", "message_end") and entry.get("message", {}).get("role") == "assistant":
            result.extend((block["name"], block.get("arguments", {})) for block in entry["message"].get("content", []) if block.get("type") == "toolCall")
    return result


def agents_grades(cell, root, final, calls):
    guide = (root / "outputs/AGENTS.md").read_text()
    evidence = json.loads((Path(cell["cwd"]) / "package.json").read_text())
    scripts = evidence["scripts"]
    command_set = {"npm ci", "npm test", "npm run lint", "npm run build"}
    mentioned = set(re.findall(r"npm (?:ci|test|run (?:lint|build))", guide))
    actual_bash = "\n".join(a.get("command", "") for n, a in calls if n == "bash")
    return [
        (not re.search(r"TODO|TBD|\[replace|<your-|INSERT HERE", guide, re.I), "AGENTS.md contains no placeholder marker; content reviewed in full."),
        (mentioned == command_set and all(k in scripts for k in ("test", "lint", "build")), f"AGENTS.md names {sorted(mentioned)}; package.json declares scripts {sorted(scripts)} and package-lock.json exists."),
        (all(x in guide for x in ("package-lock.json", "src/", "test/", "node:test")), "AGENTS.md references the actual lockfile, source/test paths and Node test runner."),
        (all(x in actual_bash for x in ("npm test", "npm run lint", "npm run build")) and "npm test" in final and "npm run lint" in final and "npm run build" in final, "Transcript executes npm test/lint/build and final response names those executed checks; npm ci is presented only as a setup command."),
    ]


def actions_grades(cell, root, final, calls):
    workflows = root / "outputs/.github/workflows"
    paths = sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])
    candidates = [(path, path.read_text()) for path in paths]
    if not candidates:
        return [(False, "No workflow output was collected.")] * 5
    # The task may create a new CI file or update the existing fixture.
    path, yaml = next(((path, text) for path, text in candidates if re.search(r"^\s*pull_request\s*:\s*$", text, re.M)), candidates[0])
    pr = bool(re.search(r"^\s*pull_request\s*:\s*$", yaml, re.M)) and "pull_request_target:" not in yaml
    permissions = bool(re.search(r"(?m)^\s*contents:\s*read\s*$", yaml)) and "write-all" not in yaml
    timeout = bool(re.search(r"(?m)^\s*timeout-minutes:\s*\d+", yaml))
    uses = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*(\S+)", yaml)
    return [
        (pr, f"{path.name}: pull_request trigger present={pr}; pull_request_target is absent."),
        (permissions, "Workflow declares permissions.contents: read and no broad write grant."),
        (timeout and "run: npm ci" in yaml, f"timeout-minutes present={timeout}; npm ci step present={'run: npm ci' in yaml}."),
        (bool(uses) and all("@" in action for action in uses), f"Action references: {uses}."),
        ("npm test" in final or "validate-workflows.py" in final, "Final response names npm test or the bundled validation command and reports a local check."),
    ]


def board_grades(cell, root, final, calls):
    bash = "\n".join(a.get("command", "") for n, a in calls if n == "bash")
    has_mock = "bin/gh" in bash or 'PATH="$PWD/bin:$PATH"' in bash or (Path(cell["cwd"]) / "gh-calls.jsonl").exists()
    normalized = re.sub(r"\s+", " ", re.sub(r"[*_`|():]", " ", final)).lower()
    stale = re.split(r"stalest open issues", final, flags=re.I)[-1]
    log_path = Path(cell["cwd"]) / "gh-calls.jsonl"
    attempted_mutation = log_path.exists() and any(json.loads(line).get("operation") == "mutation" for line in log_path.read_text().splitlines() if line.strip())
    unsafe = re.search(r"\b(?:gh|./bin/gh)\s+(?:issue\s+(?:edit|create|close)|project\s+(?:item-edit|delete)|api\s+--method\s+POST)\b|\bcurl\s+https?://", bash)
    return [
        ("5 open" in normalized and "1 closed" in normalized and bool(re.search(r"\b6 (?:items )?total\b", normalized)) and "#418" in final, "Final report says 5 open, 1 closed, 6 total and cites fixture issue #418."),
        (all(x in normalized for x in ("todo 3", "in progress 1")) and bool(re.search(r"(?:unset|no status set) 1\b", normalized)), "Final report includes OPEN Status Todo 3, In Progress 1, unset 1."),
        (bool(re.search(r"priority 2(?:/5|\s)", normalized)) and bool(re.search(r"size 2(?:/5|\s)", normalized)), "Final report gives 2 missing Priority and 2 missing Size among open issues."),
        ("#418" in stale and "#420" in stale and stale.index("#418") < stale.index("#420"), "Stalest list orders #418 before #420, matching fixture updatedAt timestamps."),
        (has_mock and not unsafe and not attempted_mutation, f"Local mock used={has_mock}; prohibited command matched={bool(unsafe)}; mock logged mutation attempt={attempted_mutation}."),
    ]


def main(run_name="pilot-1"):
    manifest = json.loads((REPO / "eval/results" / run_name / "manifest.json").read_text())
    for cell in manifest["cells"]:
        root = Path(cell["root"])
        meta = json.loads((root / "eval_metadata.json").read_text())
        final = (root / "outputs/final.md").read_text()
        calls = tool_calls(root)
        status = json.loads((root / "status.json").read_text())
        grades = {"create-agentsmd": agents_grades, "create-github-actions": actions_grades, "manage-github-projects": board_grades}[cell["skill"]](cell, root, final, calls)
        assert len(grades) == len(meta["assertions"]), cell["key"]
        expectations = [{"text": text, "passed": bool(passed), "evidence": evidence} for text, (passed, evidence) in zip(meta["assertions"], grades)]
        passed = sum(item["passed"] for item in expectations)
        result = {"expectations": expectations, "summary": {"passed": passed, "failed": len(expectations) - passed, "total": len(expectations), "pass_rate": passed / len(expectations)}, "execution_metrics": {"total_tool_calls": status["toolCount"], "total_steps": status["turnCount"], "output_chars": len(final), "transcript_chars": (root / "transcript.jsonl").stat().st_size}, "timing": {"executor_duration_seconds": (status["endedAt"] - status["startedAt"]) / 1000}, "eval_feedback": {"suggestions": [], "overall": "One pilot case per skill; shared passes do not establish a skill advantage."}}
        (root / "grading.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"{cell['key']}: {passed}/{len(expectations)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="pilot-1")
    options = parser.parse_args()
    main(options.run_name)
