"""Import, check or package the reviewed Git blobs. No runtime tool dependencies."""

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/writing"
PIN = "03bd5bb33e0760cf44c32822d2d79d7e2c42c6a6"
URL = "https://github.com/surendranb/writing-skills"
GUIDES = """asd-ste100 blameless-postmortem bob-ross brevity-briefing business-writing
corporate-communication de-ai google-dev-docs gov-uk-style jack-sparrow journalism-ap
microsoft-style orwells-rules paddington plain-language prfaq-amazon scott-adams shrek
ted-lasso winnie-the-pooh yoda""".split()
DETAIL = {"asd-ste100", "google-dev-docs", "gov-uk-style"}
LAST = "- Last step: run the `de-ai` skill on the draft before you deliver it"
ADAPT = {
    "the style another skill set": "the selected style",
    "re-check the upstream skill's rules": "re-check the selected guide's rules",
    "**The upstream skill wins.** If a rule here conflicts with the skill that wrote the draft, keep the upstream rule.": "**Follow the brief and selected guide.** Preserve required language, format and voice.",
    "- The upstream skill's Verify checklist still passes": "- The selected guide's Verify checklist still passes",
    "Override the upstream skill.": "Override the brief or selected guide.",
    "Zero literal hits from the puffery list (rule 1) and the vocabulary list (rule 7)": "Review listed phrases in context. Keep precise terminology and exact quotations",
}


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise ValueError(f"Reviewed edit no longer matches exactly once: {old}")
    return body.replace(old, new)


def imported(source):
    names = {f"skills/{g}/SKILL.md" for g in GUIDES}
    names |= {f"skills/{g}/references/REFERENCE.md" for g in DETAIL}
    actual = (
        git(source, "ls-tree", "-r", "--name-only", PIN, "skills").decode().splitlines()
    )
    if set(actual) != names:
        raise ValueError(f"Unexpected upstream inventory: {set(actual) ^ names}")

    def blob(path):
        return git(source, "show", f"{PIN}:{path}")

    notice = blob("LICENSE")
    if not notice.startswith(b"MIT License\n\nCopyright (c) 2026 Surendran B\n"):
        raise ValueError("Review upstream license")
    output = {
        "LICENSE": f"Original guides and supplements from Surendran B's writing-skills\n{URL}/tree/{PIN}\n\n".encode()
        + notice
        + b"\nUnified router and adaptations\n\n"
        + (ROOT / "LICENSE").read_bytes()
    }
    for name in GUIDES:
        raw = blob(f"skills/{name}/SKILL.md").decode()
        front = re.fullmatch(r"---\n(.+?)\n---\n\n(.+)", raw, re.S)
        if not front or f"name: {name}" not in front[1].splitlines():
            raise ValueError(f"Invalid upstream frontmatter: {name}")
        body = front[2]
        if name == "de-ai":
            for old, new in ADAPT.items():
                body = replace_once(body, old, new)
        else:
            body = replace_once(body, LAST + "\n", "")
        if name in DETAIL:
            detail = f"{name}-detail.md"
            body = replace_once(
                body, "`references/REFERENCE.md`", f"[the detail sheet]({detail})"
            )
            output[f"references/{detail}"] = blob(
                f"skills/{name}/references/REFERENCE.md"
            )
        output[f"references/{name}.md"] = body.encode()
    return output


def check_paths(files):
    for path in (
        SKILL.parent,
        SKILL,
        SKILL / "references",
        SKILL / "SKILL.md",
        *(SKILL / name for name in files),
    ):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink: {path}")


def write_import(files):
    check_paths(files)
    refs = SKILL / "references"
    if refs.exists():
        extras = {
            p.relative_to(SKILL).as_posix() for p in refs.iterdir()
        } - files.keys()
        if extras:
            raise ValueError(f"Unexpected reference files: {sorted(extras)}")
    for name in files:
        path = SKILL / name
        if path.exists() and not path.is_file():
            raise ValueError(f"Expected a file: {name}")
    refs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SKILL) as tmp:
        for name, data in files.items():
            target = SKILL / name
            if not target.exists() or target.read_bytes() != data:
                staged = Path(tmp) / target.name
                staged.write_bytes(data)
                os.replace(staged, target)


def check(files):
    check_paths(files)
    expected = {name for name in files if name.startswith("references/")}
    real = {p.relative_to(SKILL).as_posix() for p in (SKILL / "references").rglob("*")}
    if expected != real:
        raise ValueError(f"Reference inventory differs: {real ^ expected}")
    for name, data in files.items():
        path = SKILL / name
        if path.read_bytes() != data:
            raise ValueError(f"Drift in {name}")
    entry = (SKILL / "SKILL.md").read_text()
    header = (
        re.fullmatch(
            r"---\nname: writing\ndescription: >-\n((?:  [^\n]+\n)+)license: MIT\n"
            r'metadata:\n  author: ddlaws0n\n  version: "\d+\.\d+\.\d+"\n---\n\n(.+)',
            entry,
            re.S,
        )
        if entry.startswith("---\n")
        else None
    )
    if (
        not header
        or not 1 <= len(" ".join(header[1].split())) <= 1024
        or len(entry.splitlines()) > 500
    ):
        raise ValueError("Invalid writing frontmatter or entrypoint length")
    if "Surendran B" not in entry or f"{URL}/tree/{PIN}/skills" not in entry:
        raise ValueError(
            "Missing credit or pinned source link in the writing entrypoint"
        )
    links = set(re.findall(r"\]\((references/[^)]+)\)", entry))
    if links != expected:
        raise ValueError(f"Router coverage differs: {links ^ expected}")
    for name in sorted(expected | {"SKILL.md"}):
        path = SKILL / name
        body = path.read_text()
        if LAST in body or "references/REFERENCE.md" in body:
            raise ValueError(f"Unresolved upstream instruction in {name}")
        for link in re.findall(r"\]\(([^)\s]+)\)", body):
            if not link.startswith(("https://", "#")) and not (
                path.parent / link
            ).resolve().is_relative_to(SKILL):
                raise ValueError(f"Link escapes skill: {link}")
            if (
                not link.startswith(("https://", "#"))
                and not (path.parent / link).is_file()
            ):
                raise ValueError(f"Broken link: {link}")


def package(files, destination):
    members = {"writing/" + k: v for k, v in files.items()}
    members["writing/SKILL.md"] = (SKILL / "SKILL.md").read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix != ".zip":
        raise ValueError("Output must be a ZIP archive")
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        temp = Path(staging) / "writing.zip"
        with ZipFile(temp, "w") as archive:
            for name, data in sorted(members.items()):
                info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        with ZipFile(temp) as archive:
            if (
                archive.testzip()
                or archive.namelist() != sorted(members)
                or any(archive.read(k) != v for k, v in members.items())
            ):
                raise ValueError("ZIP round-trip failed")
        os.replace(temp, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["import", "check", "package"])
    parser.add_argument(
        "source", type=Path, help="Git clone containing the pinned commit"
    )
    parser.add_argument("--out", type=Path, default=ROOT / "dist/writing.zip")
    args = parser.parse_args()
    files = imported(args.source)
    if args.action == "import":
        write_import(files)
    check(files)
    if args.action == "package":
        package(files, args.out)
        print(args.out)
    print(
        f"Verified {len(GUIDES)} guides, {len(DETAIL)} supplements and MIT notices at {PIN}"
    )


if __name__ == "__main__":
    main()
