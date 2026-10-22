"""Capture facts, matching values, coverage, and privacy for the one-pass HAR brief."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "har_brief.py"
JOB_A = "3f2b1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
JOB_B = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"


def entry(t, method, url, status=200, req_headers=(), body=None, res_body=None, res_mime="application/json"):
    req = {"method": method, "url": url, "headers": [{"name": k, "value": v} for k, v in req_headers]}
    if body is not None:
        req["postData"] = {"mimeType": "application/json", "text": json.dumps(body)}
    return {
        "startedDateTime": f"2026-01-01T10:00:{t:02d}.000Z",
        "_resourceType": "fetch",
        "request": req,
        "response": {"status": status, "headers": [], "content": {"mimeType": res_mime, "text": json.dumps(res_body) if res_body is not None else ""}},
    }


def run_brief(entries, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        har = Path(tmp) / "session.har"
        har.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}))
        out = Path(tmp) / "out"
        result = subprocess.run([sys.executable, str(SCRIPT), str(har), "--out", str(out), *extra], capture_output=True, text=True, check=True)
        saved = (out / "brief.md").read_text()
        for name in ("graph.json", "workflow.md"):
            assert (out / name).exists(), name
    return result.stdout, saved


class HarBriefTests(unittest.TestCase):
    def test_async_job_chain_exposes_matches_and_states_absent_auth(self):
        entries = [
            entry(0, "POST", "https://app.example.com/api/search", status=202, body={"origin": "1234", "direction": "outbound"}, res_body={"tokens": [JOB_A]}),
            entry(1, "POST", "https://app.example.com/api/search", status=202, body={"origin": "5678", "direction": "inbound"}, res_body={"tokens": [JOB_B]}),
            entry(2, "POST", "https://app.example.com/api/results", body={"ids": [JOB_A]}, res_body={"data": {"date": "2026-01-02"}}),
        ]
        stdout, saved = run_brief(entries)
        self.assertEqual(stdout, saved)
        self.assertNotIn("Verdict hint", stdout)
        self.assertIn("#0 response.json:$.tokens[] -> #2 request.json:$.ids[]", stdout)
        self.assertIn("Cookies: none in capture", stdout)
        self.assertIn("Authorization header: none", stdout)
        self.assertIn("Captcha/challenge signals: none detected", stdout)
        self.assertIn("origin=<numeric-string>", stdout)
        self.assertIn("direction=<word>", stdout)
        self.assertIn("differ in direction, origin", stdout)
        self.assertIn("| 2 | +2.0 |", stdout, "times are relative to the primary action")
        for value in (JOB_A, JOB_B, "1234", "outbound", "2026-01-02"):
            self.assertNotIn(value, stdout)

    def test_lookup_keys_expose_matches_and_name_cookies_csrf_and_bot_signals(self):
        cookie = "sid=secret-cookie-1; _abck=sensor-value-2"
        entries = [
            entry(0, "GET", "https://app.example.com/api/areas", req_headers=[("Cookie", cookie)], res_body=[{"key": "L219", "label": "Town"}]),
            entry(2, "POST", "https://app.example.com/api/requests", req_headers=[("Cookie", cookie), ("X-CSRF-Token", "csrf-abcdef123456"), ("X-Appl", "a1b2c3d4e5f6")],
                  body={"area": "L219"}),
        ]
        stdout, _ = run_brief(entries)
        self.assertIn("#0 response.json:$[].key -> #1 request.json:$.area", stdout)
        self.assertIn("Cookie on 2/2 requests; names: _abck, sid", stdout)
        self.assertIn("CSRF/XSRF values: x-csrf-token (#1)", stdout)
        self.assertIn("Bot-management signals: _abck", stdout)
        self.assertNotIn("direct-http", stdout)
        self.assertIn("x-appl (1)", stdout)
        for value in ("secret-cookie-1", "sensor-value-2", "csrf-abcdef123456", "a1b2c3d4e5f6", "L219", "Town"):
            self.assertNotIn(value, stdout)

    def test_unrelated_challenge_is_a_capture_signal_without_verdict(self):
        entries = [
            entry(0, "GET", "https://www.google.com/recaptcha/api2/anchor?k=site-key-123", res_mime="text/html"),
            entry(1, "POST", "https://app.example.com/api/login", body={"user": "someone"}),
        ]
        stdout, _ = run_brief(entries)
        self.assertIn("Captcha/challenge signals:", stdout)
        self.assertIn("recaptcha", stdout)
        self.assertNotIn("browser-assisted", stdout)
        self.assertNotIn("site-key-123", stdout)

    def test_numeric_nonce_and_uuid_resource_expose_locations_without_lifecycle_claims(self):
        entries = [
            entry(0, "GET", "https://app.example.com/api/bootstrap", res_body={"nonce": 987654, "resourceId": JOB_A}),
            entry(1, "POST", "https://app.example.com/api/save", body={"nonce": 987654, "resourceId": JOB_A}, res_body={"ok": True}),
        ]
        stdout, _ = run_brief(entries)
        for field in ("nonce", "resourceId"):
            self.assertIn(f"#0 response.json:$.{field} -> #1 request.json:$.{field}", stdout)
        for claim in ("direct-http", "http-with-token-refresh", "stable lookup", "server-generated"):
            self.assertNotIn(claim, stdout)
        for value in ("987654", JOB_A):
            self.assertNotIn(value, stdout)

    def test_missing_body_and_no_matches_do_not_produce_replayability_claim(self):
        stdout, _ = run_brief([entry(0, "POST", "https://app.example.com/api/save", body={"title": "Private title"})])
        self.assertIn("missing #0", stdout)
        self.assertIn("no match does not establish independence", stdout)
        self.assertNotIn("direct-http", stdout)

    def test_coverage_reports_exclusions_and_response_scan_limit(self):
        entries = [
            entry(0, "GET", "https://app.example.com/app.js", res_mime="application/javascript"),
            entry(1, "POST", "https://app.example.com/api/save", body={"a": 1}, res_body={"long": "x" * 200}),
        ]
        stdout, _ = run_brief(entries, "--max-scan-chars", "40")
        self.assertIn("1/2 requests selected", stdout)
        self.assertIn("Response scans skipped: 1; cut at scan limit: 1", stdout)

    def test_brief_respects_length_cap(self):
        entries = [entry(i, "POST", f"https://app.example.com/api/thing{i}/save", body={"n": i}) for i in range(40)]
        stdout, _ = run_brief(entries, "--max-chars", "800")
        self.assertLessEqual(len(stdout), 800)
        self.assertIn("brief truncated", stdout)

    def test_fixtures_build(self):
        for fixture in (ROOT / "evals" / "files").glob("*.har"):
            with self.subTest(fixture=fixture.name), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run([sys.executable, str(SCRIPT), str(fixture), "--out", tmp], capture_output=True, text=True, check=True)
                self.assertTrue(result.stdout.startswith("# HAR brief"))
                self.assertLessEqual(len(result.stdout), 5000)


if __name__ == "__main__":
    unittest.main()
