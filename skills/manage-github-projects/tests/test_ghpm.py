"""CLI contracts against a recording, fail-closed GitHub subprocess fixture."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts/ghpm.py"
SPEC = importlib.util.spec_from_file_location("ghpm", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PROJECT = {"id": "PVT_FIXTURE", "number": 7, "title": "Fixture", "url": "https://example.test/projects/7"}
FIELDS = [{"id": "F_STATUS", "name": "Status", "dataType": "SINGLE_SELECT",
           "options": [{"id": "O_TODO", "name": "Todo"}]}]
ITEM = {"id": "ITEM_418", "content": {"number": 418, "title": "Fixture issue", "state": "OPEN"},
        "fieldValues": {"nodes": [{"name": "Todo", "field": {"name": "Status"}}]}}


class GhpmTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.writes = []
        self.patch = mock.patch.object(MODULE.subprocess, "run", side_effect=self.fake_run)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def fake_run(self, argv, **kwargs):
        body = json.loads(kwargs.get("input", "{}"))
        query = body.get("query", "")
        self.calls.append((argv, body))
        if "mutation" in query.lower() or argv[:2] == ["gh", "issue"]:
            self.writes.append((argv, body))
            return subprocess.CompletedProcess(argv, 1, "", "fixture refuses writes")
        if argv[:3] != ["gh", "api", "graphql"]:
            raise AssertionError(f"Unexpected external command: {argv}")
        if "projectV2(number:" in query:
            data = {"user": {"projectV2": PROJECT}}
        elif "fields(first:" in query:
            data = {"node": {"fields": {"nodes": FIELDS}}}
        elif "items(first:" in query:
            data = {"node": {"items": {"nodes": [ITEM], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
        elif "a:issue" in query:
            data = {"repository": {"a": {"id": "ISSUE_418"}, "b": {"id": "ISSUE_420"}}}
        elif "issue(number:" in query:
            data = {"repository": {"issue": {"id": "ISSUE_418"}}}
        else:
            raise AssertionError(f"Unsupported fixture query: {query}")
        return subprocess.CompletedProcess(argv, 0, json.dumps({"data": data}), "")

    def invoke(self, *arguments, dry_run=False):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = MODULE.main(["--repo", "fixture/project", "--project-number", "7",
                                  *(["--dry-run"] if dry_run else []), *arguments])
        return status, output.getvalue()

    def test_all_mutation_commands_send_no_writes_in_dry_run(self):
        cases = [
            ["set", "418", "Status=Todo"], ["clear", "418", "Status"],
            ["label", "418", "triaged"], ["label", "418", "triaged", "--remove"],
            ["assign", "418", "fixture"], ["milestone", "418", "Sprint"],
            ["add-to-project", "418"], ["remove-from-project", "418", "--yes"],
            ["link", "418", "420"], ["link", "418", "420", "--relation", "relates"],
            ["create-draft", "Fixture draft"], ["create", "Fixture issue"],
            ["close", "418", "--yes"], ["delete-draft", "DRAFT_1", "--yes"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                status, output = self.invoke(*arguments, dry_run=True)
                self.assertEqual(status, 0)
                self.assertIn("[dry-run]", output)
                self.assertEqual(self.writes, [])

    def test_recording_fixture_detects_an_attempted_write(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke("label", "418", "triaged")
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(len(self.writes), 1)
        self.assertIn("--add-label", self.writes[0][0])

    def test_items_output_is_json_with_fixture_values(self):
        status, output = self.invoke("items")
        self.assertEqual(status, 0)
        rows = json.loads(output)
        self.assertEqual(rows[0]["number"], 418)
        self.assertEqual(rows[0]["fields"]["Status"], "Todo")
        self.assertEqual(self.writes, [])

    def test_invalid_assignment_fails_without_a_write(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke("set", "418", "MissingEquals", dry_run=True)
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(self.writes, [])

    def test_invalid_arguments_fail_before_any_external_call(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            MODULE.main(["--unsupported"])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.calls, [])

    def test_graphql_failure_is_reported(self):
        with mock.patch.object(MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "fixture offline")):
            with self.assertRaisesRegex(RuntimeError, "fixture offline"):
                MODULE.gh_graphql("query { viewer { login } }")


if __name__ == "__main__":
    unittest.main()
