"""Exercise copied skill entry points outside the checkout with Docker networking disabled."""

import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path


def run(script: Path, *arguments: str) -> str:
    return subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout


def python_entry_points(skills: Path) -> list[Path]:
    # Mirrors isPythonEntryPoint in scripts/validate-skills.ts.
    guard = re.compile(r"""^if\s+__name__\s*==\s*["']__main__["']\s*:""", re.M)
    return [script for script in sorted(skills.glob("*/scripts/**/*.py")) if guard.search(script.read_text())]


def main() -> None:
    if {name for _, name in socket.if_nameindex()} != {"lo"}:
        raise RuntimeError("Installed smoke tests require a network-isolated container")
    skills = Path("/skills")
    scripts = python_entry_points(skills)
    if not scripts:
        raise RuntimeError("No installed Python entry points found")
    for script in scripts:
        if script.stat().st_mode & 0o111:
            raise AssertionError(f"Installed entry point still has executable bits: {script}")
        if not run(script, "--help").strip():
            raise AssertionError(f"No help output: {script}")

    probe = skills / "analyze-har-workflows/scripts/har_probe.py"
    fixture = Path("capture.har")
    fixture.write_text(json.dumps({"log": {"entries": [{
        "request": {"method": "POST", "url": "https://example.test/profile?token=fixture-secret",
                    "postData": {"mimeType": "application/json", "text": '{"name":"Fixture Person"}'}},
        "response": {"status": 200, "content": {"mimeType": "application/json", "text": '{"ok":true}'}},
    }]}}))
    run(probe, "summarize", str(fixture), "--out", "har-output", "--top", "1")
    summary = json.loads(Path("har-output/summary.json").read_text())
    if summary["total_entries"] != 1:
        raise AssertionError("Installed HAR helper did not analyze the fixture")
    run(probe, "extract", str(fixture), "--indices", "0", "--out", "selected.json")
    selected = Path("selected.json").read_text()
    if json.loads(selected)["entries_found"] != 1 or any(
        value in selected for value in ("fixture-secret", "Fixture Person")
    ):
        raise AssertionError("Installed HAR extraction failed its privacy contract")

    workflow = Path("fixture.yml")
    workflow.write_text("""name: Smoke
on: push
permissions:
  contents: read
concurrency: smoke
jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 1
    steps:
      - run: echo smoke
""")
    result = json.loads(run(
        skills / "create-github-actions/scripts/validate-workflows.py",
        str(workflow), "--require-sha", "--strict", "--format", "json",
    ))
    if result["errors"] or result["warnings"]:
        raise AssertionError("Installed workflow validator rejected the valid fixture")
    shell_scripts = sorted(skills.glob("*/scripts/*.sh"))
    for script in shell_scripts:
        if script.stat().st_mode & 0o111:
            raise AssertionError(f"Installed shell entry point still has executable bits: {script}")
        subprocess.run(["bash", "-n", str(script)], check=True, timeout=30)

    project = Path("git-fixture")
    project.mkdir()
    for arguments in (["init", "-q"], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                                         "commit", "--allow-empty", "-qm", "Initial fixture"]):
        subprocess.run(["git", "-C", str(project), *arguments], check=True, timeout=30)
    scan = subprocess.run(["bash", str(skills / "analyze-git-history/scripts/git-risk-scan.sh"),
                           "--path", str(project)], check=True, capture_output=True, text=True, timeout=30)
    if "git" not in scan.stdout.lower():
        raise AssertionError("Installed history scanner did not report on its fixture")

    project = Path("varlock-fixture")
    binary = project / "node_modules/.bin/varlock"
    binary.parent.mkdir(parents=True)
    (project / ".env.schema").write_text("# Synthetic schema; no credentials\n")
    binary.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> calls.txt\n")
    binary.chmod(0o755)
    subprocess.run(["bash", str(skills / "manage-secrets-varlock/scripts/varlock-project-check.sh"),
                    str(project)], check=True, capture_output=True, text=True, timeout=30,
                   env={"PATH": os.defpath})
    if (project / "calls.txt").read_text().splitlines() != [
        "--version", "load --agent --format json-full", "audit", "scan",
    ]:
        raise AssertionError("Installed Varlock check did not call its local fixture as documented")
    print(f"Installed smoke tests passed for {len(scripts)} Python and {len(shell_scripts)} shell entry points; executable bits removed; network disabled.")


if __name__ == "__main__":
    main()
