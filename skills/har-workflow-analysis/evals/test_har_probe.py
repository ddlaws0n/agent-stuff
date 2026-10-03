"""Deterministic smoke and privacy regressions for the bundled HAR helper."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import har_probe  # noqa: E402


class HarProbeTests(unittest.TestCase):
    def test_sensitive_fields_are_not_emitted(self):
        entry = {
            "request": {
                "method": "POST",
                "url": "https://user:pw@example.com/api/upload/jane@example.com?code=short-secret",
                "headers": [
                    {"name": "Cookie", "value": "sid=short-secret"},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Referer", "value": "https://example.com/?token=short-secret"},
                ],
                "postData": {
                    "mimeType": "application/json",
                    "text": json.dumps({"displayName": "Jane Doe", "pin": "1234", "nested": {"card": 12345}}),
                },
            },
            "response": {
                "status": 302,
                "redirectURL": "https://example.com/success?session=short-secret",
                "content": {"mimeType": "application/json", "text": '{"message":"Jane Doe"}'},
            },
        }
        output = har_probe.compact_entry(entry, 0, max_body_chars=2000)
        serialized = json.dumps(output)
        for secret in ("user:pw", "short-secret", "jane@example.com", "Jane Doe", "1234", "12345"):
            self.assertNotIn(secret, serialized)
        self.assertIn('"displayName"', serialized)
        self.assertEqual(output["url"]["path"], "/api/upload/{redacted}")
        self.assertEqual(output["response"]["redirectURL"], "https://example.com/success?session=<value>")

    def test_multipart_filename_is_not_emitted(self):
        info = har_probe.post_data_info({
            "mimeType": "multipart/form-data; boundary=sensitive-boundary",
            "params": [{"name": "file", "fileName": "patient-record.pdf"}],
        })
        self.assertEqual(info["mime"], "multipart/form-data")
        self.assertEqual(info["file_names"], ["<file>"])
        self.assertNotIn("patient-record.pdf", json.dumps(info))

    def test_fixtures_stream_and_limit_candidates(self):
        for fixture in (ROOT / "evals" / "files").glob("*.har"):
            with self.subTest(fixture=fixture.name), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run([
                    sys.executable, str(ROOT / "scripts" / "har_probe.py"), "summarize",
                    str(fixture), "--out", tmp, "--top", "1",
                ], capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(result.stdout)["ok"], True)
                summary = json.loads((Path(tmp) / "summary.json").read_text())
                self.assertGreater(summary["total_entries"], 0)
                self.assertLessEqual(len(summary["top_candidates"]), 1)
                self.assertLessEqual(len((Path(tmp) / "candidates.jsonl").read_text().splitlines()), 1)
                selected = Path(tmp) / "selected.json"
                subprocess.run([
                    sys.executable, str(ROOT / "scripts" / "har_probe.py"), "extract",
                    str(fixture), "--indices", "0", "--out", str(selected),
                ], capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(selected.read_text())["entries_found"], 1)


if __name__ == "__main__":
    unittest.main()
