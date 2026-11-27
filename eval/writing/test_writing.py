import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import build
import evaluate


class WritingTests(unittest.TestCase):
    def test_inventory_and_routing_fixtures(self):
        cases = evaluate.cases()
        tested = {g for row in cases.values() for g in row.get("required", [])}
        guides = set(build.GUIDES) | {f"{g}-detail" for g in build.DETAIL}
        self.assertEqual(tested, guides)
        for split in ("dev", "held-out"):
            self.assertEqual(
                {
                    c["should_trigger"]
                    for c in cases.values()
                    if "should_trigger" in c and c["split"] == split
                },
                {True, False},
            )
            self.assertTrue(
                any(
                    c["suite"] == "quality" and c["split"] == split
                    for c in cases.values()
                )
            )
        files = {
            f"references/{g}.md": (build.SKILL / f"references/{g}.md").read_bytes()
            for g in guides
        }
        files["LICENSE"] = (build.SKILL / "LICENSE").read_bytes()
        build.check(files)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one, two = root / "one.zip", root / "two.zip"
            build.package(files, one)
            build.package(dict(reversed(list(files.items()))), two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with ZipFile(one) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"writing/" + p for p in files} | {"writing/SKILL.md"},
                )
            shutil.copytree(build.SKILL / "references", root / "references")
            (root / "LICENSE").write_bytes(files["LICENSE"])
            (root / "SKILL.md").write_text(
                (build.SKILL / "SKILL.md").read_text().split("---", 2)[2]
            )
            with (
                patch.object(build, "SKILL", root),
                self.assertRaisesRegex(ValueError, "frontmatter"),
            ):
                build.check(files)
            (root / "SKILL.md").write_text(
                (build.SKILL / "SKILL.md").read_text().split("## Credits")[0]
            )
            with (
                patch.object(build, "SKILL", root),
                self.assertRaisesRegex(ValueError, "credit"),
            ):
                build.check(files)

    def test_import_rejects_link_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "writing"
            (skill / "references").mkdir(parents=True)
            marker = root / "other"
            marker.write_text("keep")
            (skill / "references/yoda.md").symlink_to(marker)
            files = {"LICENSE": b"new", "references/yoda.md": b"guide"}
            with (
                patch.object(build, "SKILL", skill),
                self.assertRaisesRegex(ValueError, "symlink"),
            ):
                build.write_import(files)
            self.assertEqual(marker.read_text(), "keep")
            self.assertFalse((skill / "LICENSE").exists())

    def test_only_successful_reads_and_completed_turns_count(self):
        cwd = Path("/fixture")
        turns = [
            {
                "type": "tool_execution_start",
                "toolCallId": "x",
                "toolName": "read",
                "args": {"path": "skills/writing/SKILL.md"},
            },
            {
                "type": "tool_execution_end",
                "toolCallId": "x",
                "isError": False,
                "result": {"content": [{"type": "text", "text": "body"}]},
            },
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "provider": "p",
                    "model": "m",
                    "stopReason": "stop",
                    "content": [{"type": "text", "text": "references/yoda.md"}],
                    "usage": {"input": 2, "output": 5},
                },
            },
            {"type": "agent_settled", "aborted": False},
        ]
        ok = evaluate.observe(turns, cwd, "p/m")
        self.assertEqual(ok["reads"], ["skills/writing/SKILL.md"])
        self.assertEqual(ok["usage"]["output"], 5)
        self.assertIsNone(ok["usage"]["cacheRead"])
        failed = [turns[0], {**turns[1], "isError": True}, *turns[2:]]
        self.assertEqual(evaluate.observe(failed, cwd, "p/m")["reads"], [])
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            evaluate.observe(turns[:-1], cwd, "p/m")
        with self.assertRaisesRegex(ValueError, "model"):
            evaluate.observe(turns, cwd, "p/other")
        grade = evaluate.grade(
            {"required": ["yoda"], "allowed": [], "max_reads": 1}, "unified", ok
        )
        self.assertFalse(grade["checks"]["required"])

    def test_frozen_controls_must_match_the_case_and_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "q1").mkdir()
            manifest = {
                "pin": build.PIN,
                "model": "p/m",
                "pi": "1",
                "cases": ["q1"],
                "sha256": {"cases.json": "one"},
            }
            evaluate.save(directory / "manifest.json", manifest)
            for variant in ("none", "upstream"):
                evaluate.save(
                    directory / "q1" / f"{variant}.json",
                    {"case": "q1", "variant": variant, "model": "p/m"},
                )
            evaluate.check_controls(directory, manifest)
            with self.assertRaisesRegex(ValueError, "fixtures"):
                evaluate.check_controls(
                    directory, {**manifest, "sha256": {"cases.json": "two"}}
                )
            evaluate.save(
                directory / "q1/none.json",
                {"case": "q2", "variant": "none", "model": "p/m"},
            )
            with self.assertRaisesRegex(ValueError, "control cell"):
                evaluate.check_controls(directory, manifest)

    def test_precedence_of_material_failures(self):
        self.assertGreater(
            evaluate.preference(3, []), evaluate.preference(5, ["lost quotation"])
        )
        self.assertEqual(evaluate.preference(4, []), evaluate.preference(4, []))
