"""Deterministic smoke and privacy regressions for the bundled HAR helper."""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_prefixed_ids_are_normalized(self):
        self.assertEqual(har_probe.normalize_path("/api/records/rec_7f3a91c2/files/upl_123"), "/api/records/{id}/files/{id}")
        self.assertEqual(har_probe.normalize_path("/oauth2/v2/settings"), "/oauth2/v2/settings")

    def test_value_ids_compare_submitted_values_and_verification_reads_privately(self):
        fixture = ROOT / "evals/files/repeated-save.synthetic.har"
        result = subprocess.run([
            sys.executable, str(ROOT / "scripts/har_probe.py"), "show", str(fixture),
            "--indices", "0-5", "--value-ids", "--max-chars", "2500",
        ], capture_output=True, text=True, check=True)
        blocks = re.split(r"(?m)^#\d+ ", result.stdout)[1:]

        def identifier(index, field):
            match = re.search(rf"\b{field}=<[^:>]+:(v\d+)>", blocks[index])
            self.assertIsNotNone(match, (index, field))
            return match.group(1)

        self.assertEqual(identifier(0, "nonce"), identifier(1, "nonce"))
        self.assertEqual(identifier(3, "nonce"), identifier(4, "nonce"))
        self.assertNotEqual(identifier(0, "nonce"), identifier(3, "nonce"))
        self.assertEqual(identifier(0, "resourceId"), identifier(3, "resourceId"))
        self.assertEqual(identifier(1, "title"), identifier(2, "title"))
        self.assertEqual(identifier(4, "title"), identifier(5, "title"))
        self.assertNotEqual(identifier(1, "title"), identifier(4, "title"))
        self.assertEqual(identifier(1, "version"), identifier(2, "version"))
        self.assertNotEqual(identifier(1, "version"), identifier(4, "version"))
        for secret in ("547892", "932871", "3f2b1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", "Private first title", "Private second title", "synthetic-session-secret-4242"):
            self.assertNotIn(secret, result.stdout)

    def test_value_shapes_name_kinds_without_values(self):
        cases = {
            "2026-01-02": "date", "2026-01-02T10:00:00Z": "datetime", "1234": "numeric-string", "LHR": "code",
            "outbound": "word", "Jane Doe": "text", "rec_7f3a91c2": "id", "jane@example.com": "email",
            "3f2b1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d": "uuid", "https://example.com/x": "url", "": "empty",
            1700000000: "epoch", 12: "integer", 1.5: "number", True: "boolean", None: "null",
        }
        for value, kind in cases.items():
            with self.subTest(value=value):
                self.assertEqual(har_probe.value_shape(value), kind)
        shapes = har_probe.body_shapes({"mimeType": "application/json", "text": json.dumps({"a": {"b": ["x1y2z3"]}, "c": []})})
        self.assertEqual(shapes, {"a.b[]": "id", "c[]": "empty-list"})

    def test_show_names_headers_and_hides_values(self):
        entry = {
            "startedDateTime": "2026-01-01T10:00:00.000Z",
            "_resourceType": "fetch",
            "request": {
                "method": "POST",
                "url": "https://app.example.com/api/save?date=2026-01-02",
                "headers": [
                    {"name": "Cookie", "value": "sid=cookie-secret-1; theme=dark"},
                    {"name": "Authorization", "value": "Bearer bearer-secret-123456"},
                    {"name": "X-CSRF-Token", "value": "csrf-secret-9876"},
                    {"name": "X-Appl", "value": "a1b2c3d4e5f6"},
                    {"name": "User-Agent", "value": "Mozilla/5.0"},
                ],
                "postData": {"mimeType": "application/json", "text": json.dumps({"origin": "1234", "note": "Jane Doe"})},
            },
            "response": {"status": 202, "headers": [], "content": {"mimeType": "text/plain", "text": ""}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            har = Path(tmp) / "one.har"
            har.write_text(json.dumps({"log": {"entries": [entry]}}))
            out = subprocess.run([sys.executable, str(ROOT / "scripts" / "har_probe.py"), "show", str(har), "--indices", "0"],
                                 capture_output=True, text=True, check=True).stdout
        for expected in ("cookie=<names: sid, theme>", "authorization=<Bearer redacted>", "x-csrf-token=<redacted>", "x-appl=<id>",
                         "query: date=<date>", "origin=<numeric-string> note=<text>", "no body in capture"):
            self.assertIn(expected, out)
        for secret in ("cookie-secret-1", "dark", "bearer-secret-123456", "csrf-secret-9876", "a1b2c3d4e5f6", "1234", "Jane Doe", "Mozilla"):
            self.assertNotIn(secret, out)
        self.assertLessEqual(len(out), 1500)

    def test_multipart_filename_is_not_emitted(self):
        info = har_probe.post_data_info({
            "mimeType": "multipart/form-data; boundary=sensitive-boundary",
            "params": [{"name": "file", "fileName": "patient-record.pdf"}],
        })
        self.assertEqual(info["mime"], "multipart/form-data")
        self.assertEqual(info["file_names"], ["<file>"])
        self.assertNotIn("patient-record.pdf", json.dumps(info))

    def test_telemetry_preflight_and_blocked_requests_rank_low(self):
        def score(method, url, status=200):
            c = har_probe.compact_entry({
                "_resourceType": "fetch",
                "request": {"method": method, "url": url, "headers": [{"name": "Content-Type", "value": "application/json"}],
                            "postData": {"mimeType": "application/json", "text": "{}"}},
                "response": {"status": status, "content": {"mimeType": "application/json", "text": "{}"}},
            }, 0)
            return har_probe.candidate_score(c)[0]
        action = score("POST", "https://app.example.com/api/records")
        self.assertLess(score("POST", "https://app.example.com/beacon"), action - 25)
        self.assertLess(score("POST", "https://metrics.example.com/b/ss/suite/1"), action - 25)
        self.assertLess(score("OPTIONS", "https://app.example.com/api/records"), action - 25)
        self.assertLess(score("POST", "https://app.example.com/api/records", status=0), action - 15)

    def test_streams_fractional_timings(self):
        entry = {
            "startedDateTime": "2026-01-01T10:00:00.123Z",
            "time": 1.5,
            "request": {"method": "POST", "url": "https://example.com/api/save", "headers": []},
            "response": {"status": 200, "headers": [], "content": {"mimeType": "application/json", "text": "{}"}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            har = Path(tmp) / "float.har"
            har.write_text(json.dumps({"log": {"entries": [entry]}}))
            subprocess.run([sys.executable, str(ROOT / "scripts" / "har_probe.py"), "summarize", str(har), "--out", tmp], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads((Path(tmp) / "entries.jsonl").read_text())["time_ms"], 1.5)

    def test_streaming_and_fallback_preserve_large_integer_metadata(self):
        self.assertIsNotNone(har_probe.ijson, "streaming regression requires the test dependency")
        entry = {"time": 1.25, "_recordId": 2**80, "request": {}, "response": {}}
        with tempfile.TemporaryDirectory() as tmp:
            har = Path(tmp) / "numbers.har"
            har.write_text(json.dumps({"log": {"entries": [entry]}}))
            for reader in (har_probe.ijson, None):
                with self.subTest(streaming=reader is not None), patch.object(har_probe, "ijson", reader):
                    parsed = next(har_probe.iter_har_entries(har))
                    self.assertEqual(parsed["_recordId"], 2**80)
                    compact = har_probe.compact_entry(parsed, 0)
                    self.assertEqual(json.loads(json.dumps(compact))["time_ms"], 1.25)

    def test_redacted_array_reports_omitted_items(self):
        result = har_probe.redact_mapping({"jobs": list(range(203))})
        self.assertEqual(len(result["jobs"]), 201)
        self.assertEqual(result["jobs"][-1], {"_har_probe_omitted_items": 3})
        self.assertEqual(har_probe.redact_mapping([True, False]), ["<boolean>", "<boolean>"])

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
