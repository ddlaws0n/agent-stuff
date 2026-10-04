#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27,<1",
#   "packaging>=24,<26",
# ]
#
# [tool.ty.rules]
# # Dependencies above are installed by `uv run`, not in the repo environment.
# unresolved-import = "ignore"
# ///

"""Fetch release/tag context for a GitHub Action repository.

Usage examples:
  uv run scripts/fetch-action-release.py actions/checkout --format text
  uv run scripts/fetch-action-release.py actions/setup-node --format json --max-release-notes 1200
  uv run scripts/fetch-action-release.py github/codeql-action --prefer sha

Exit codes:
  0 success
  2 invalid arguments
  3 GitHub API/auth/rate-limit error
  4 no usable tags found
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any, Literal

import httpx
from packaging.version import InvalidVersion, Version

SEMVER_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
MAJOR_TAG = re.compile(r"^v\d+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Tag:
    name: str
    sha: str


@dataclass(frozen=True)
class Selection:
    repository: str
    selected_tag: str
    commit_sha: str
    recommended_ref: str
    major_tag: str | None
    major_tag_exists: bool
    release_url: str | None
    release_name: str | None
    prerelease: bool
    notes: str
    warnings: list[str]


class ToolError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def parse_action_slug(value: str) -> tuple[str, str]:
    raw = value.strip()
    raw = raw.removeprefix("https://github.com/").strip("/")
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    parts = raw.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ToolError(
            "Expected OWNER/REPO, https://github.com/OWNER/REPO, or OWNER/REPO/path@ref.",
            exit_code=2,
        )
    return parts[0], parts[1]


def make_client() -> httpx.Client:
    headers = {
        "User-Agent": "create-github-actions-skill/2.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, timeout=30, follow_redirects=True)


def get_json(c: httpx.Client, url: str) -> Any:
    try:
        response = c.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:500]
        raise ToolError(f"GitHub API request failed with HTTP {status}: {detail}") from exc
    except httpx.RequestError as exc:
        raise ToolError(f"GitHub API request failed: {exc}") from exc


def list_tags(c: httpx.Client, owner: str, repo: str, pages: int) -> list[Tag]:
    tags: list[Tag] = []
    for page in range(1, pages + 1):
        data = get_json(c, f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100&page={page}")
        if not data:
            break
        tags.extend(Tag(item["name"], item["commit"]["sha"]) for item in data)
    return tags


def semver_key(tag: Tag) -> Version | None:
    if not SEMVER_TAG.match(tag.name):
        return None
    try:
        return Version(tag.name.lstrip("v"))
    except InvalidVersion:
        return None


def latest_semver(tags: list[Tag], include_prerelease: bool) -> Tag | None:
    candidates: list[tuple[Version, Tag]] = []
    for tag in tags:
        version = semver_key(tag)
        if version is None:
            continue
        if version.is_prerelease and not include_prerelease:
            continue
        candidates.append((version, tag))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def latest_release(c: httpx.Client, owner: str, repo: str) -> dict[str, Any] | None:
    response = c.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolError(f"GitHub releases/latest failed with HTTP {response.status_code}: {response.text[:500]}") from exc
    return response.json()


def release_for_tag(c: httpx.Client, owner: str, repo: str, tag: str) -> dict[str, Any] | None:
    response = c.get(f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}")
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolError(f"GitHub releases/tags failed with HTTP {response.status_code}: {response.text[:500]}") from exc
    return response.json()


def select_tag(
    c: httpx.Client,
    owner: str,
    repo: str,
    tags: list[Tag],
    include_prerelease: bool,
) -> tuple[Tag, dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    release = latest_release(c, owner, repo)
    chosen: Tag | None = None
    if release and not release.get("prerelease"):
        release_tag = release.get("tag_name")
        chosen = next((tag for tag in tags if tag.name == release_tag), None)
        if chosen is None:
            warnings.append(f"Latest release tag {release_tag!r} was not found in fetched tags; falling back to latest semver tag.")

    if chosen is None:
        chosen = latest_semver(tags, include_prerelease=include_prerelease)
        if chosen is not None:
            release = release_for_tag(c, owner, repo, chosen.name)
            warnings.append("No usable latest release object found; selected latest semver tag from repository tags.")

    if chosen is None and tags:
        chosen = tags[0]
        release = release_for_tag(c, owner, repo, chosen.name)
        warnings.append("No semver tags found; selected the first tag returned by GitHub. Inspect manually before use.")

    if chosen is None:
        raise ToolError(f"No usable tags found for {owner}/{repo}", exit_code=4)

    return chosen, release, warnings


def build_selection(args: argparse.Namespace) -> Selection:
    owner, repo = parse_action_slug(args.action)
    with make_client() as c:
        tags = list_tags(c, owner, repo, pages=args.pages)
        if not tags:
            raise ToolError(f"No tags found for {owner}/{repo}", exit_code=4)
        chosen, release, warnings = select_tag(c, owner, repo, tags, args.include_prerelease)

    version = semver_key(chosen)
    major = f"v{version.major}" if version else None
    major_exists = bool(major and any(tag.name == major for tag in tags))

    if args.prefer == "sha":
        recommended_ref = chosen.sha
    elif args.prefer == "major":
        recommended_ref = major if major_exists else chosen.name
        if major and not major_exists:
            warnings.append(f"Major tag {major} not found; using exact tag {chosen.name} instead.")
    else:
        recommended_ref = chosen.name

    notes = ""
    release_url = None
    release_name = None
    prerelease = False
    if release:
        release_url = release.get("html_url")
        release_name = release.get("name")
        prerelease = bool(release.get("prerelease"))
        notes = (release.get("body") or "").strip()[: args.max_release_notes]
    else:
        warnings.append("No release object found for selected tag; inspect changelog before relying on new inputs/defaults.")

    if SHA_RE.match(recommended_ref):
        warnings.append("Recommended ref is a full SHA. Add a YAML comment with the human-readable tag for maintainability.")

    return Selection(
        repository=f"{owner}/{repo}",
        selected_tag=chosen.name,
        commit_sha=chosen.sha,
        recommended_ref=recommended_ref,
        major_tag=major,
        major_tag_exists=major_exists,
        release_url=release_url,
        release_name=release_name,
        prerelease=prerelease,
        notes=notes,
        warnings=warnings,
    )


def print_text(selection: Selection) -> None:
    print(f"Repository: {selection.repository}")
    print(f"Selected tag: {selection.selected_tag}")
    print(f"Commit SHA: {selection.commit_sha}")
    print(f"Recommended ref: {selection.recommended_ref}")
    if selection.major_tag:
        status = "exists" if selection.major_tag_exists else "not found"
        print(f"Major tag: {selection.major_tag} ({status})")
    print(f"Release URL: {selection.release_url or 'N/A'}")
    if selection.release_name:
        print(f"Release name: {selection.release_name}")
    if selection.warnings:
        print("\nWarnings:", file=sys.stderr)
        for warning in selection.warnings:
            print(f"- {warning}", file=sys.stderr)
    if selection.notes:
        print("\nRelease notes:\n")
        print(selection.notes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch release/tag context for a GitHub Action repository.")
    parser.add_argument("action", help="OWNER/REPO, https://github.com/OWNER/REPO, or OWNER/REPO/path@ref")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format. Default: text.")
    parser.add_argument("--prefer", choices=["exact", "major", "sha"], default="exact", help="Recommended ref style. Default: exact tag.")
    parser.add_argument("--include-prerelease", action="store_true", help="Allow prerelease semver tags when no latest release is available.")
    parser.add_argument("--pages", type=int, default=3, help="Number of tag pages to scan, 100 tags per page. Default: 3.")
    parser.add_argument("--max-release-notes", type=int, default=3000, help="Maximum release-note characters to print/include. Default: 3000.")
    args = parser.parse_args()

    if args.pages < 1 or args.pages > 10:
        raise ToolError("--pages must be between 1 and 10", exit_code=2)
    if args.max_release_notes < 0:
        raise ToolError("--max-release-notes must be >= 0", exit_code=2)

    selection = build_selection(args)
    if args.format == "json":
        print(json.dumps(asdict(selection), indent=2, sort_keys=True))
    else:
        print_text(selection)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(exc.exit_code)
