#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0.2,<7",
# ]
#
# [tool.ty.rules]
# # Dependencies above are installed by `uv run`, not in the repo environment.
# unresolved-import = "ignore"
# ///

"""Static validator for GitHub Actions workflow YAML.

Usage examples:
  uv run scripts/validate-workflows.py .github/workflows
  uv run scripts/validate-workflows.py .github/workflows/ci.yml --format json
  uv run scripts/validate-workflows.py .github/workflows --strict

Exit codes:
  0 no errors
  1 validation errors found
  2 invalid arguments or unreadable files
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
FLOATING_REFS = {"main", "master", "develop", "trunk", "latest", "HEAD"}
UNTRUSTED_EVENT_EXPR = re.compile(
    r"\$\{\{\s*(?:"
    r"github\.event\.pull_request\.(?:title|body|head\.ref|head\.label|head\.repo\.full_name|base\.ref)|"
    r"github\.event\.(?:issue|comment|discussion|discussion_comment|release)\.(?:title|body|name)|"
    r"github\.event\.inputs\.[A-Za-z0-9_-]+|"
    r"inputs\.[A-Za-z0-9_-]+"
    r")\s*\}\}"
)
EXPRESSION_RE = re.compile(r"\$\{\{.*?\}\}")


class GhaLoader(yaml.SafeLoader):
    """YAML loader that does not coerce GitHub's `on` key to boolean."""


for first_letter, mappings in list(GhaLoader.yaml_implicit_resolvers.items()):
    GhaLoader.yaml_implicit_resolvers[first_letter] = [
        (tag, regexp) for tag, regexp in mappings if tag != "tag:yaml.org,2002:bool"
    ]


@dataclass(frozen=True)
class Finding:
    file: str
    severity: str
    code: str
    message: str
    location: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    files_checked: int
    errors: int
    warnings: int
    findings: list[Finding]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=GhaLoader)
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Workflow must parse to a YAML mapping/object")
    return data


def workflow_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.yml") if p.is_file()))
            files.extend(sorted(p for p in path.rglob("*.yaml") if p.is_file()))
        elif path.is_file():
            files.append(path)
        else:
            raise ValueError(f"Path not found: {path}")
    deduped: list[Path] = []
    seen: set[Path] = set()
    for file in files:
        resolved = file.resolve()
        if resolved not in seen:
            deduped.append(file)
            seen.add(resolved)
    return deduped


def add(findings: list[Finding], path: Path, severity: str, code: str, message: str, location: str | None = None) -> None:
    findings.append(Finding(str(path), severity, code, message, location))


def normalize_events(on_value: Any) -> set[str]:
    if isinstance(on_value, str):
        return {on_value}
    if isinstance(on_value, list):
        return {str(item) for item in on_value}
    if isinstance(on_value, dict):
        return {str(key) for key in on_value.keys()}
    return set()


def permission_map(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, str):
        return {"__all__": value}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {}


def iter_steps(jobs: dict[str, Any]) -> Iterable[tuple[str, int, dict[str, Any]]]:
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for idx, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                yield str(job_id), idx, step


def split_uses_ref(uses: str) -> tuple[str, str | None]:
    if uses.startswith("./") or uses.startswith("docker://"):
        return uses, None
    if "@" not in uses:
        return uses, None
    left, ref = uses.rsplit("@", 1)
    return left, ref


def validate_external_uses(
    findings: list[Finding], path: Path, uses: str, location: str, require_sha: bool
) -> str:
    action, ref = split_uses_ref(uses)
    if uses.startswith("./"):
        return action
    if uses.startswith("docker://"):
        if "@sha256:" not in uses:
            add(findings, path, "warning", "docker-image-unpinned", "Pin Docker container actions/images by digest when possible.", location)
        return action
    if ref is None:
        add(findings, path, "error", "uses-unpinned", f"External action or reusable workflow `{uses}` must include an explicit @version or @SHA.", location)
    elif ref in FLOATING_REFS:
        add(findings, path, "error", "uses-floating-ref", f"Avoid floating ref `{ref}` for `{action}`; use a tag or full commit SHA.", location)
    elif len(ref) < 40 and re.fullmatch(r"[0-9a-f]+", ref):
        add(findings, path, "warning", "uses-short-sha", f"Use full 40-character commit SHA instead of short SHA `{ref}`.", location)
    elif not FULL_SHA.match(ref) and not re.match(r"^v?\d+(\.\d+\.\d+)?([-.+][A-Za-z0-9_.-]+)?$", ref):
        add(findings, path, "warning", "uses-nonstandard-ref", f"Ref `{ref}` is explicit but not a semver-like tag or full SHA; verify it is intentional.", location)
    if require_sha and ref is not None and not FULL_SHA.match(ref):
        add(findings, path, "error", "uses-not-full-sha", f"`{uses}` must use a full 40-character commit SHA under --require-sha.", location)
    return action


def validate_file(path: Path, require_sha: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    try:
        data = load_yaml(path)
    except ValueError as exc:
        add(findings, path, "error", "yaml-invalid", str(exc))
        return findings

    if "name" not in data:
        add(findings, path, "warning", "missing-name", "Workflow has no top-level name.")

    if "on" not in data:
        add(findings, path, "error", "missing-on", "Workflow has no top-level `on` trigger.")
        events: set[str] = set()
    else:
        events = normalize_events(data.get("on"))

    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        add(findings, path, "error", "missing-jobs", "Workflow has no jobs mapping.")
        return findings

    top_permissions_present = "permissions" in data and data.get("permissions") is not None
    top_permissions = permission_map(data.get("permissions"))
    all_jobs_bound_permissions = all(
        isinstance(job, dict) and "permissions" in job and job.get("permissions") is not None
        for job in jobs.values()
    )
    if not top_permissions_present and not all_jobs_bound_permissions:
        add(findings, path, "warning", "permissions-missing", "Set explicit top-level permissions or permissions on every job; default token permissions are easy to overgrant.")
    elif top_permissions.get("__all__") == "write-all":
        add(findings, path, "error", "permissions-write-all", "Avoid top-level `permissions: write-all`; grant only required job-level scopes.")
    elif any(value == "write" for key, value in top_permissions.items() if key != "contents"):
        add(findings, path, "warning", "permissions-top-write", "Top-level write permissions apply to every job; prefer job-level write scopes.")

    if "pull_request_target" in events:
        add(findings, path, "warning", "pull-request-target", "`pull_request_target` is privileged. Do not check out or execute untrusted PR code in this workflow.")

    if "workflow_run" in events:
        add(findings, path, "warning", "workflow-run-boundary", "`workflow_run` can cross trust boundaries. Validate upstream conclusion, branch, and artifact provenance before privileged actions.")

    if "concurrency" not in data and ({"pull_request", "push", "workflow_dispatch"} & events):
        add(findings, path, "warning", "concurrency-missing", "Consider adding concurrency to cancel stale CI or serialize deployments.")

    for job_id, job in jobs.items():
        location = f"jobs.{job_id}"
        if not isinstance(job, dict):
            add(findings, path, "error", "job-invalid", "Job must be a mapping/object.", location)
            continue

        if "uses" not in job and "runs-on" not in job:
            add(findings, path, "error", "runs-on-missing", "Normal jobs require `runs-on`; reusable workflow jobs require `uses`.", location)

        job_uses = job.get("uses")
        if isinstance(job_uses, str):
            validate_external_uses(findings, path, job_uses, location, require_sha)

        if "timeout-minutes" not in job and "uses" not in job:
            add(findings, path, "warning", "timeout-missing", "Add `timeout-minutes` to jobs that can hang.", location)

        job_permissions = permission_map(job.get("permissions"))
        if job_permissions.get("__all__") == "write-all":
            add(findings, path, "error", "job-permissions-write-all", "Avoid `permissions: write-all`; grant only required scopes.", location)
        if job_permissions.get("id-token") == "write" and "environment" not in job:
            add(findings, path, "warning", "oidc-without-environment", "OIDC job has `id-token: write` but no `environment`; confirm this is not a production deploy needing approvals.", location)

        if job.get("environment") and "workflow_dispatch" not in events and "push" not in events and "workflow_run" not in events:
            add(findings, path, "warning", "environment-unusual-trigger", "Environment-gated job is not triggered by workflow_dispatch, push, or workflow_run; confirm this cannot run for untrusted PRs.", location)

    for job_id, idx, step in iter_steps(jobs):
        location = f"jobs.{job_id}.steps[{idx}]"
        uses = step.get("uses")
        if isinstance(uses, str):
            action = validate_external_uses(findings, path, uses, location, require_sha)

            if action == "actions/cache":
                with_block = step.get("with", {})
                key = with_block.get("key") if isinstance(with_block, dict) else None
                if not isinstance(key, str) or "hashFiles(" not in key:
                    add(findings, path, "warning", "cache-key-no-lockfile", "Cache key should usually include hashFiles(...) for lockfiles.", location)

        run = step.get("run")
        if isinstance(run, str):
            if UNTRUSTED_EVENT_EXPR.search(run):
                add(findings, path, "error", "unsafe-event-expression-in-run", "Do not interpolate untrusted event text or dispatch inputs directly in shell. Pass via env and quote shell variables.", location)
            elif EXPRESSION_RE.search(run) and ("github.event" in run or "inputs." in run):
                add(findings, path, "warning", "github-event-expression-in-run", "Review event or input interpolation inside shell; attacker- or operator-controlled text can cause injection.", location)

    if "pull_request_target" in events:
        for job_id, idx, step in iter_steps(jobs):
            location = f"jobs.{job_id}.steps[{idx}]"
            uses = step.get("uses")
            run = step.get("run")
            if uses == "actions/checkout" or (isinstance(uses, str) and uses.startswith("actions/checkout@")):
                add(findings, path, "error", "prt-checkout", "`pull_request_target` workflow uses checkout. Ensure it never checks out PR head code; prefer pull_request for CI.", location)
            if isinstance(run, str):
                add(findings, path, "warning", "prt-run-step", "`pull_request_target` workflow has run steps. Confirm they cannot execute PR-controlled code or data unsafely.", location)

    return findings


def print_text(result: ValidationResult) -> None:
    print(f"Files checked: {result.files_checked}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    if not result.findings:
        print("No findings.")
        return
    print("")
    for finding in result.findings:
        loc = f" ({finding.location})" if finding.location else ""
        print(f"[{finding.severity.upper()}] {finding.file}{loc} {finding.code}: {finding.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Static validator for GitHub Actions workflow YAML.")
    parser.add_argument("paths", nargs="+", help="Workflow file(s) or directories to validate.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format. Default: text.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present, not just errors.")
    parser.add_argument("--require-sha", action="store_true", help="Require full 40-character commit SHAs for external actions and reusable workflows.")
    args = parser.parse_args()

    try:
        files = workflow_files(args.paths)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not files:
        print("Error: no .yml or .yaml workflow files found", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for file in files:
        findings.extend(validate_file(file, require_sha=args.require_sha))

    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    result = ValidationResult(files_checked=len(files), errors=errors, warnings=warnings, findings=findings)

    if args.format == "json":
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        print_text(result)

    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
