"""Evidence inspection regressions: bounded output, precise paths, and private comparisons."""

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import har_inspect  # noqa: E402


class HarInspectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def capture(self, filename, body, encoding=None):
        text = json.dumps(body)
        if encoding == "base64":
            text = base64.b64encode(text.encode()).decode()
        path = self.directory / filename
        path.write_text(json.dumps({"log": {"entries": [{
            "request": {"method": "POST", "url": "https://example.test/schema", "postData": {"text": json.dumps(body)}},
            "response": {"status": 200, "content": {"text": text, "encoding": encoding}},
        }]}}))
        return path

    def run_probe(self, paths, *args, code=0):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/har_inspect.py"), *map(str, paths), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_nested_json_and_escaped_pointers_reveal_only_selected_scalars(self):
        path = self.capture("nested.har", {"result": json.dumps(json.dumps({"a/b": {"~flag": False}, "version_no": 19}))}, "base64")
        out = self.run_probe([path], "--select", "0:0:/result/a~1b/~0flag", "--select", "0:0:/result/version_no",
                             "--expect", "0:0:/result/version_no", "19", "--values")
        self.assertEqual([r["value"] for r in out["observations"]], [False, 19])
        self.assertEqual(len(out["sources"][0]["sha256"]), 64)
        self.assertEqual(out["decoded_json"], [{"source": 0, "entry": 0, "pointer": "/result", "layers": 2}])
        walked = self.run_probe([path], "--select", "0:0:/result", "--walk", "--expect", "0:0:/result/version_no", "19")
        self.assertEqual(walked["decoded_json"], out["decoded_json"])
        request = self.run_probe([path], "--body", "request", "--select", "0:0:/result/version_no", "--values")
        self.assertEqual(request["observations"][0]["value"], 19)

    def test_cross_capture_ids_and_snapshot_equality_are_private_and_typed(self):
        first = self.capture("first.har", {"root_job_id": "private-shared-job", "definition": json.dumps({"skip": True, "number": 2})})
        second = self.capture("second.har", {"calling_job_id": "private-shared-job", "definition": '{ "number":2, "skip":true }', "other": 1})
        out = self.run_probe([first, second], "--select", "0:0:/root_job_id", "--select", "1:0:/calling_job_id",
                             "--select", "0:0:/definition", "--select", "1:0:/definition", "--select", "1:0:/other")
        rows = out["observations"]
        self.assertEqual(rows[0]["value_id"], rows[1]["value_id"])
        self.assertEqual(rows[2]["value_id"], rows[3]["value_id"])
        self.assertNotIn("private-shared-job", json.dumps(out))
        self.assertNotEqual(rows[2]["value_id"], rows[4]["value_id"])

    def test_container_values_are_not_dumped_and_walk_is_bounded(self):
        path = self.capture("large.har", {"jobs": [{"title": "Private customer", "id": n} for n in range(205)]})
        container = self.run_probe([path], "--select", "0:0:/jobs", "--values")["observations"][0]
        self.assertEqual(container["length"], 205)
        self.assertNotIn("value", container)
        out = self.run_probe([path], "--select", "0:0:/jobs", "--walk", "--max-items", "3")
        self.assertEqual(len(out["observations"]), 3)
        self.assertTrue(out["truncated"])
        self.assertNotIn("Private customer", json.dumps(out))
        self.assertEqual(out["observations"][2]["pointer"], "/jobs/1/title")

    def test_secret_keys_record_labels_and_url_credentials_are_redacted(self):
        path = self.capture("private.har", {"password": "short-pass", "headers": [{"name": "Authorization", "value": "short-token"}],
                                            "properties": [{"name": "airtable_secret", "value": "another-short-secret"},
                                                           {"label": "PIN", "value": "short-pin"}, {"key": "credentials", "value": "short-credentials"}],
                                            "nonce": 547892, "email": "person@example.test", "url": "https://user:pass@example.test/a?token=secret"})
        out = self.run_probe([path], "--values", "--select", "0:0:/password", "--select", "0:0:/headers/0/value",
                             "--select", "0:0:/properties/0/value", "--select", "0:0:/properties/1/value", "--select", "0:0:/properties/2/value",
                             "--select", "0:0:/nonce", "--select", "0:0:/email", "--select", "0:0:/url")
        for row in out["observations"][:6]:
            self.assertTrue(row["redacted"])
        for private in ("short-pass", "short-token", "another-short-secret", "short-pin", "short-credentials", "547892", "person@example.test", "user:pass", "token=secret"):
            self.assertNotIn(private, json.dumps(out))

    def test_expectations_validate_patch_node_types_and_skip_flags(self):
        path = self.capture("nodes.har", {"block": [{"keyword": "else"}, {"keyword": "action", "skip": True}]})
        passed = self.run_probe([path], "--expect", "0:0:/block/1/keyword", '"action"', "--expect", "0:0:/block/1/skip", "true")
        self.assertTrue(all(c["matches"] for c in passed["checks"]))
        failed = self.run_probe([path], "--expect", "0:0:/block/0/keyword", '"action"', code=1)
        self.assertFalse(failed["checks"][0]["matches"])
        self.run_probe([path], "--expect", "0:0:/block/1/skip", "1", code=1)

    def test_caps_are_explicit_and_output_remains_valid_json(self):
        path = self.capture("limits.har", {"rows": ["x" * 2000] * 100})
        out = self.run_probe([path], "--select", "0:0:/rows", "--walk", "--max-chars", "1000")
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(json.dumps(out, ensure_ascii=False)), 1000)
        value = self.run_probe([path], "--select", "0:0:/rows/0", "--values")["observations"][0]
        # Long opaque strings are redacted before disclosure.
        self.assertNotIn("x" * 2000, json.dumps(value))
        text = self.capture("text.har", {"text": "word " * 300})
        value = self.run_probe([text], "--select", "0:0:/text", "--values")["observations"][0]
        self.assertTrue(value["value_truncated"])
        self.assertEqual(len(value["value"]), 1000)
        self.run_probe([path], "--select", "0:0:/rows", "--max-json-chars", "10", code=2)

    def test_invalid_or_missing_locations_fail_without_exposing_body_values(self):
        path = self.capture("errors.har", {"value": "private"})
        for location in ("0:0:/missing", "0:5:/value", "1:0:/value", "0:0:/value/x"):
            with self.subTest(location=location):
                out = self.run_probe([path], "--select", location, code=2)
                self.assertFalse(out["ok"])
                self.assertNotIn("private", json.dumps(out))
        self.run_probe([path], "--select", "0:0:", "--walk", "--values", code=2)
        self.run_probe([path], "--expect", "invalid-selector", "false", code=2)
        with self.assertRaises(ValueError):
            har_inspect.decode(json.dumps(json.dumps(json.dumps(json.dumps(json.dumps({"x": 1}))))), 1000)
        with self.assertRaises(argparse.ArgumentTypeError):
            har_inspect.selector("0:0:/bad~escape")


if __name__ == "__main__":
    unittest.main()
