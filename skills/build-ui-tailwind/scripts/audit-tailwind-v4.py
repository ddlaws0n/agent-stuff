#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Audit a project for Tailwind CSS v4.3 readiness issues.

This script is intentionally dependency-free so agents can run it in most
repositories. It reports likely issues; it does not modify files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", ".next",
    ".nuxt", ".svelte-kit", "coverage", ".turbo", ".cache", "vendor",
}
DOC_DIRS = {"docs", "documentation"}
SKIP_FILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb",
}
STYLE_EXTS = {".css", ".pcss", ".scss", ".sass", ".less"}
SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".mdx", ".vue", ".svelte", ".astro"}
TEXT_EXTS = STYLE_EXTS | SOURCE_EXTS
TAILWIND_IMPORT_RE = re.compile(r"""@import\s+(?:url\(\s*)?["']tailwindcss(?:/[^"']*)?["']""")
VITE_CONFIGS = ("vite.config.ts", "vite.config.js", "vite.config.mts", "vite.config.mjs")
WEBPACK_CONFIGS = ("webpack.config.js", "webpack.config.cjs", "webpack.config.mjs", "webpack.config.ts")

@dataclass
class Finding:
    severity: str
    code: str
    path: str
    line: Optional[int]
    message: str
    suggestion: str


def iter_files(root: Path, max_bytes: int, include_docs: bool = False) -> Iterable[Path]:
    excluded = SKIP_DIRS if include_docs else SKIP_DIRS | DOC_DIRS
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        current = Path(dirpath)
        for name in filenames:
            if name in SKIP_FILES:
                continue
            path = current / name
            if path.suffix not in TEXT_EXTS and not name.startswith("tailwind.config") and name != "package.json":
                continue
            try:
                if path.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def add_pattern_findings(findings: List[Finding], root: Path, path: Path, text: str) -> None:
    rel = str(path.relative_to(root))
    kinds = set()
    if path.name.startswith("tailwind.config"):
        kinds.add("config")
    if path.suffix in STYLE_EXTS:
        kinds.add("style")
    if path.suffix in SOURCE_EXTS:
        kinds.add("source")

    # Each check applies to files of any kind listed first.
    checks = [
        (
            ("style",), "warning", "v3-css-directives", r"@tailwind\s+(base|components|utilities)\s*;",
            "v3-style @tailwind directive found in CSS.",
            "For v4 CSS-first entry files, prefer @import \"tailwindcss\";",
        ),
        (
            ("config",), "warning", "legacy-safelist", r"\bsafelist\s*:",
            "Legacy safelist configuration found.",
            "In v4, safelist generated classes with @source inline(...) in CSS.",
        ),
        (
            ("config",), "info", "legacy-content-config", r"\bcontent\s*:\s*(\[|\{)",
            "Tailwind content scanning configuration found.",
            "For new v4 code, prefer automatic detection plus @source/@source not/source(none). Keep only if maintaining legacy config.",
        ),
        (
            ("style", "source"), "warning", "deprecated-start-end", r"(?<![\w-])(start|end)-(\[|\d|px|full|auto)",
            "Possible deprecated start-* or end-* positioning utility found.",
            "Prefer inset-s-* and inset-e-* in Tailwind v4.2+.",
        ),
        (
            ("style", "source"), "info", "tnum-font-feature", r"font-features-\[(['\"])tnum\1\]",
            "Low-level tnum OpenType feature found.",
            "Use tabular-nums for routine tabular numeric alignment.",
        ),
        (
            ("style", "source"), "info", "hover-zoom", r"hover:zoom-",
            "hover:zoom-* found.",
            "zoom affects layout; use hover:scale-* for visual-only hover animation.",
        ),
        (
            ("style", "source"), "info", "scrollbar-none", r"(?<![\w-])scrollbar-none(?![\w-])",
            "scrollbar-none found.",
            "Use sparingly; consider scrollbar-thin or visible scrollbar styling for affordance.",
        ),
        (
            ("style", "source"), "warning", "dynamic-template-class", r"`[^`]*(bg|text|border|from|to|via|ring|shadow)-\$\{[^`]+`",
            "Likely dynamic Tailwind class generated with template interpolation.",
            "Map possible values to explicit class strings or safelist exact values with @source inline(...).",
        ),
    ]

    for applies_to, severity, code, pattern, message, suggestion in checks:
        if kinds.isdisjoint(applies_to):
            continue
        for match in re.finditer(pattern, text):
            findings.append(Finding(severity, code, rel, line_number(text, match.start()), message, suggestion))


def major_version(spec: str) -> Optional[int]:
    """Return the major version from a semver range such as ^4.3.0 or ~3.4, if any."""
    spec = spec.strip()
    if spec.startswith("npm:") and "@" in spec[4:]:
        spec = spec.rsplit("@", 1)[1]
    match = re.search(r"(?<![\w.])v?(\d+)(?=\.|\s|$|x|\*)", spec)
    return int(match.group(1)) if match else None


def inspect_package(root: Path, pkg: Path, findings: List[Finding]) -> bool:
    """Record package-level findings; return True when the package depends on tailwindcss."""
    rel = str(pkg.relative_to(root))
    try:
        data = json.loads(read_text(pkg))
    except (OSError, json.JSONDecodeError):
        findings.append(Finding("warning", "package-json-invalid", rel, None, "package.json is not valid JSON.", "Fix package.json before auditing Tailwind dependencies."))
        return False
    if not isinstance(data, dict):
        return False

    deps: dict = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update(section)

    tw = deps.get("tailwindcss")
    if not isinstance(tw, str):
        return False
    if major_version(tw) == 3:
        findings.append(Finding("warning", "tailwind-v3-installed", rel, None, f"tailwindcss version appears to be v3 ({tw}).", "Migrate to the latest v4 release when the project target allows it."))

    pkg_dir = pkg.parent
    has_vite_config = any((pkg_dir / f).exists() for f in VITE_CONFIGS)
    has_webpack_config = any((pkg_dir / f).exists() for f in WEBPACK_CONFIGS)

    if has_vite_config and "@tailwindcss/vite" not in deps:
        findings.append(Finding("info", "vite-plugin-missing", rel, None, "Vite config found but @tailwindcss/vite is not listed.", "For Tailwind v4 Vite projects, prefer @tailwindcss/vite."))
    if has_webpack_config and "@tailwindcss/webpack" not in deps:
        findings.append(Finding("info", "webpack-loader-missing", rel, None, "Webpack config found but @tailwindcss/webpack is not listed.", "For controlled webpack pipelines, prefer @tailwindcss/webpack."))
    if "@tailwindcss/postcss" in deps and ("@tailwindcss/vite" in deps or "@tailwindcss/webpack" in deps):
        findings.append(Finding("info", "stacked-integrations", rel, None, "Multiple Tailwind integration packages found.", "Confirm the project really needs stacked integrations; otherwise keep only the build-tool-specific path."))
    return True


def run(root: Path, max_bytes: int, include_docs: bool = False) -> dict:
    findings: List[Finding] = []
    if not root.exists():
        raise SystemExit(f"Error: path does not exist: {root}")

    packages: List[Path] = []
    configs: List[Path] = []
    css_count = 0
    has_import = False
    # Single bounded traversal: pattern checks and structure facts are gathered together.
    for path in iter_files(root, max_bytes, include_docs):
        if path.name == "package.json":
            packages.append(path)
            continue
        if path.name.startswith("tailwind.config"):
            configs.append(path)
        try:
            text = read_text(path)
        except OSError:
            continue
        if path.suffix == ".css":
            css_count += 1
            has_import = has_import or bool(TAILWIND_IMPORT_RE.search(text))
        add_pattern_findings(findings, root, path, text)

    uses_tailwind = [inspect_package(root, pkg, findings) for pkg in sorted(packages)]
    if packages and not any(uses_tailwind):
        findings.append(Finding("info", "tailwind-missing", "package.json", None, "No tailwindcss dependency found in any package.json.", "Install tailwindcss plus the build-tool-specific integration package."))

    for cfg in sorted(configs):
        rel = str(cfg.relative_to(root))
        if has_import:
            findings.append(Finding("info", "config-with-css-first", rel, None, "tailwind.config.* exists alongside a v4-style CSS import.", "Keep the config only if plugins or legacy constraints require it, and load it with @config; otherwise move tokens/utilities/source controls into CSS."))
        else:
            findings.append(Finding("info", "tailwind-config-present", rel, None, "tailwind.config.* found.", "For new v4 projects, avoid config files unless explicitly needed."))

    if css_count and not has_import:
        findings.append(Finding("info", "css-import-not-found", ".", None, "No @import \"tailwindcss\" found in scanned CSS files.", "A v4 CSS entry file should usually include @import \"tailwindcss\";"))

    counts = {"warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] += 1
    return {
        "root": str(root),
        "summary": {"total": len(findings), **counts},
        "findings": [asdict(f) for f in findings],
    }


def print_text(report: dict) -> None:
    s = report["summary"]
    print(f"Tailwind v4 audit: {s['total']} findings ({s['warning']} warnings, {s['info']} info)")
    for f in report["findings"]:
        loc = f["path"] if f["line"] is None else f"{f['path']}:{f['line']}"
        print(f"\n[{f['severity'].upper()}] {f['code']} at {loc}")
        print(f"  {f['message']}")
        print(f"  Suggestion: {f['suggestion']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a project for Tailwind CSS v4.3 readiness issues.")
    parser.add_argument("root", nargs="?", default=".", help="Project root to scan (default: current directory).")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    parser.add_argument("--max-bytes", type=int, default=512_000, help="Skip individual files larger than this many bytes.")
    parser.add_argument("--include-docs", action="store_true", help="Also scan docs/ and documentation/; excluded by default to avoid reporting prose examples as source violations.")
    args = parser.parse_args()

    report = run(Path(args.root).resolve(), args.max_bytes, include_docs=args.include_docs)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print_text(report)


if __name__ == "__main__":
    main()
