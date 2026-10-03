#!/usr/bin/env python3
"""Focused checks for container eval preparation; no model calls or board mutations."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare")
grade = load("grade")


class ModelSelectionTests(unittest.TestCase):
    def test_default_and_override_pin_every_child(self):
        for name, option, expected in (
            ("test-glm", [], "openrouter/z-ai/glm-5.3-flash:high"),
            ("test-luna", ["--model", "openrouter/openai/gpt-6-luna"], "openrouter/openai/gpt-6-luna:high"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as scratch:
                base = Path(scratch)
                with patch.object(prepare, "RESULTS_BASE", base / "eval/results"), patch.object(prepare, "WORKSPACES_BASE", base):
                    prepare.main(["--run-name", name, *option])
                    with self.assertRaisesRegex(SystemExit, "Refusing to overwrite"):
                        prepare.main(["--run-name", name, *option])
                root = base / "eval/results" / name
                manifest = json.loads((root / "manifest.json").read_text())
                self.assertFalse((root / "workflow.js").exists())
                self.assertEqual(expected, manifest["model"])
                self.assertEqual(6, len(manifest["cells"]))
                self.assertEqual(3, sum(cell["condition"] == "with_skill" for cell in manifest["cells"]))
                self.assertEqual(3, sum(cell["condition"] == "without_skill" for cell in manifest["cells"]))
                for cell in manifest["cells"]:
                    self.assertEqual(expected, cell["model"])
                    self.assertNotIn("output", cell)
                    self.assertFalse((Path(cell["cwd"]) / ".pi/settings.json").exists())
                    self.assertEqual((Path(cell["cwd"]) / ".agents/skills" / cell["skill"]).exists(), cell["condition"] == "with_skill")

    def test_rejects_unapproved_model_and_invalid_run_name(self):
        for args in (["--run-name", "test-direct", "--model", "openai-codex/gpt-6-luna"], ["--run-name", "../escape"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                prepare.main(args)
            self.assertEqual(2, caught.exception.code)

    def test_grader_reads_cli_json_tool_calls(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "transcript.jsonl").write_text(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "toolCall", "name": "bash", "arguments": {"command": "npm test"}}]}}) + "\n")
            self.assertEqual([("bash", {"command": "npm test"})], grade.tool_calls(root))

    def test_grader_accepts_new_ci_file_beside_existing_fixture(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            workflows = root / "outputs/.github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "existing.yml").write_text("name: Existing\non: push\n")
            (workflows / "ci.yaml").write_text("name: CI\non:\n  pull_request:\n  push:\n    branches: [main]\npermissions:\n  contents: read\njobs:\n  test:\n    timeout-minutes: 15\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm ci\n      - run: npm test\n")
            grades = grade.actions_grades({}, root, "npm test passed", [])
            self.assertTrue(all(passed for passed, _ in grades))

    def test_grader_reports_missing_workflow_as_failures(self):
        with tempfile.TemporaryDirectory() as scratch:
            grades = grade.actions_grades({}, Path(scratch), "npm test passed", [])
            self.assertEqual(5, len(grades))
            self.assertFalse(any(passed for passed, _ in grades))


    def test_board_grader_handles_markdown_and_rejected_mutations(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            log = root / "gh-calls.jsonl"
            log.write_text(json.dumps({"operation": "read"}) + "\n")
            final = "6 items total: 5 open, 1 closed (#418).\n| Todo | 3 |\n| In Progress | 1 |\n| *(unset)* | 1 |\nMissing **Priority** (2): #420, #437\nMissing **Size** (2): #430, #437\nStalest open issues: #418, #420"
            cell = {"cwd": str(root)}
            grades = grade.board_grades(cell, root, final, [])
            self.assertTrue(all(passed for passed, _ in grades))
            log.write_text(json.dumps({"operation": "mutation"}) + "\n")
            self.assertFalse(grade.board_grades(cell, root, final, [])[-1][0])

    def test_pilot_requires_assertions_before_fixture_creation(self):
        with tempfile.TemporaryDirectory() as scratch:
            base = Path(scratch)
            prepare.put(base, "skills/sample/evals/evals.json", json.dumps({"evals": [{"id": 1, "prompt": "Inspect", "expected_output": "Report"}]}))
            with patch.object(prepare, "REPO", base), patch.object(prepare, "RESULTS_BASE", base / "results"), patch.object(prepare, "WORKSPACES_BASE", base), patch.object(prepare, "CASES", [("sample", 1)]):
                with self.assertRaisesRegex(SystemExit, "needs explicit assertions"):
                    prepare.main(["--run-name", "missing-assertions"])
            self.assertFalse((base / "results").exists())

if __name__ == "__main__":
    unittest.main()
