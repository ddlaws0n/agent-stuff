"""Capture facts, verdict hints, field kinds, and privacy for the one-pass HAR brief."""

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
    def test_async_job_chain_hints_token_refresh_and_states_absent_auth(self):
        entries = [
            entry(0, "POST", "https://app.example.com/api/search", status=202, body={"origin": "1234", "direction": "outbound"}, res_body={"tokens": [JOB_A]}),
            entry(1, "POST", "https://app.example.com/api/search", status=202, body={"origin": "5678", "direction": "inbound"}, res_body={"tokens": [JOB_B]}),
            entry(2, "POST", "https://app.example.com/api/results", body={"ids": [JOB_A]}, res_body={"data": {"date": "2026-01-02"}}),
        ]
        stdout, saved = run_brief(entries)
        self.assertEqual(stdout, saved)
        self.assertIn("## Verdict hint: http-with-token-refresh", stdout)
        self.assertIn("#2 sends a uuid from #0", stdout)
        self.assertIn("Cookies: none in capture", stdout)
        self.assertIn("Authorization header: none", stdout)
        self.assertIn("Captcha/challenge signals: none detected", stdout)
        self.assertIn("origin=<numeric-string>", stdout)
        self.assertIn("direction=<word>", stdout)
        self.assertIn("differ in direction, origin", stdout)
        self.assertIn("| 2 | +2.0 |", stdout, "times are relative to the primary action")
        for value in (JOB_A, JOB_B, "1234", "outbound", "2026-01-02"):
            self.assertNotIn(value, stdout)

    def test_lookup_keys_hint_direct_http_and_name_cookies_csrf_and_bot_risk(self):
        cookie = "sid=secret-cookie-1; _abck=sensor-value-2"
        entries = [
            entry(0, "GET", "https://app.example.com/api/areas", req_headers=[("Cookie", cookie)], res_body=[{"key": "L219", "label": "Town"}]),
            entry(2, "POST", "https://app.example.com/api/requests", req_headers=[("Cookie", cookie), ("X-CSRF-Token", "csrf-abcdef123456"), ("X-Appl", "a1b2c3d4e5f6")],
                  body={"area": "L219"}),
        ]
        stdout, _ = run_brief(entries)
        self.assertIn("## Verdict hint: direct-http", stdout)
        self.assertIn("Cookie on 2/2 requests; names: _abck, sid", stdout)
        self.assertIn("CSRF/XSRF values: x-csrf-token (#1)", stdout)
        self.assertIn("Bot-management signals: _abck", stdout)
        self.assertIn("risk: bot-management signals", stdout)
        self.assertIn("x-appl (1)", stdout)
        for value in ("secret-cookie-1", "sensor-value-2", "csrf-abcdef123456", "a1b2c3d4e5f6", "L219", "Town"):
            self.assertNotIn(value, stdout)

    def test_challenge_hints_browser_assisted(self):
        entries = [
            entry(0, "GET", "https://www.google.com/recaptcha/api2/anchor?k=site-key-123", res_mime="text/html"),
            entry(1, "POST", "https://app.example.com/api/login", body={"user": "someone"}),
        ]
        stdout, _ = run_brief(entries)
        self.assertIn("## Verdict hint: browser-assisted or manual-only/blocked", stdout)
        self.assertNotIn("site-key-123", stdout)

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
