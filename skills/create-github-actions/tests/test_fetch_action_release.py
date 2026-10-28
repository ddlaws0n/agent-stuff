"""Exercise release lookup with an in-memory HTTP transport; no live GitHub calls."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

SCRIPT = Path(__file__).parents[1] / "scripts/fetch-action-release.py"
SPEC = importlib.util.spec_from_file_location("fetch_action_release", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
SHA = "a" * 40


class FetchActionReleaseTests(unittest.TestCase):
    def test_json_cli_contains_verified_tag_sha_and_release_context(self):
        requests = []

        def respond(request):
            requests.append(str(request.url))
            if request.url.path.endswith("/tags"):
                if request.url.params.get("page") != "1":
                    return httpx.Response(200, json=[])
                return httpx.Response(200, json=[{"name": "v2.3.4", "commit": {"sha": SHA}},
                                                 {"name": "v2", "commit": {"sha": SHA}}])
            if request.url.path.endswith("/releases/latest"):
                return httpx.Response(200, json={"tag_name": "v2.3.4", "name": "Fixture release",
                                                 "html_url": "https://example.test/release", "body": "Fixture notes"})
            raise AssertionError(f"Unexpected API request: {request.url}")

        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        output = io.StringIO()
        with mock.patch.object(MODULE, "make_client", return_value=client), \
                mock.patch.object(sys, "argv", [str(SCRIPT), "fixture/action", "--format", "json", "--prefer", "sha"]), \
                contextlib.redirect_stdout(output):
            status = MODULE.main()
        self.assertEqual(status, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["repository"], "fixture/action")
        self.assertEqual(report["selected_tag"], "v2.3.4")
        self.assertEqual(report["commit_sha"], SHA)
        self.assertEqual(report["recommended_ref"], SHA)
        self.assertEqual(report["release_url"], "https://example.test/release")
        self.assertEqual(report["notes"], "Fixture notes")
        self.assertIsInstance(report["warnings"], list)
        self.assertEqual(len(requests), 3)

    def test_api_failure_has_explicit_error_instead_of_a_success_report(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503, text="fixture unavailable")))
        self.addCleanup(client.close)
        with mock.patch.object(MODULE, "make_client", return_value=client), \
                mock.patch.object(sys, "argv", [str(SCRIPT), "fixture/action", "--format", "json"]), \
                self.assertRaises(MODULE.ToolError) as error:
            MODULE.main()
        self.assertEqual(error.exception.exit_code, 3)
        self.assertIn("HTTP 503", str(error.exception))

    def test_invalid_arguments_exit_before_network(self):
        for arguments in [["fixture/action", "--pages", "0"], ["invalid-slug"],
                          ["fixture/action", "--format", "invalid"]]:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), *arguments],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
