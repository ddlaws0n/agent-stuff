"""folio.py against a local fake Folio API. Never touches the real service."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

SCRIPT = Path(__file__).parents[1] / "scripts" / "folio.py"
GOOD = "good-token"


class FakeFolio(BaseHTTPRequestHandler):
    calls: ClassVar[list[tuple[str, str, dict, str]]] = []

    def log_message(self, format, *args):  # noqa: A002 - matches base signature
        pass

    def handle_any(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else {}
        auth = self.headers.get("Authorization", "")
        FakeFolio.calls.append((self.command, self.path, body, auth))
        if self.path == "/sessions":
            ok = body.get("user") == {"email": "me@example.com", "password": "pw"}
            return self.reply(200 if ok else 401, {"token": GOOD} if ok else {})
        if auth != f"Bearer {GOOD}":
            return self.reply(401, {"error": "unauthorized"})
        if self.command == "POST" and self.path == "/items":
            return self.reply(201, {"item": {"id": "i1", "title": "Hello", "url": body["item"]["url"]}})
        if self.command == "PATCH" and self.path == "/items/i1":
            return self.reply(200, {"item": {"id": "i1"}})
        if self.path == "/users/current":
            return self.reply(200, {"user": {"email": "me@example.com"}})
        self.reply(404, {})

    do_GET = do_POST = do_PATCH = handle_any

    def reply(self, code: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeFolio)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeFolio.calls = []
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)
        self.token_file = self.cache / "save-to-folio" / "token"
        self.env = {
            "FOLIO_API_URL": f"http://127.0.0.1:{self.server.server_port}",
            "XDG_CACHE_HOME": str(self.cache),
            "FOLIO_USERNAME": "me@example.com",
            "FOLIO_PASSWORD": "pw",
            "PATH": "/usr/bin:/bin",  # keep a real op CLI out of reach
        }

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, *args: str) -> tuple[int, list[dict]]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args], env=self.env, capture_output=True, text=True, check=False
        )
        return proc.returncode, [json.loads(line) for line in proc.stdout.splitlines()]

    def test_logs_in_caches_token_and_saves_with_tags(self):
        code, out = self.run_script("save", "https://example.com/a", "--tag", "plane")
        self.assertEqual(code, 0)
        self.assertEqual(out, [{"url": "https://example.com/a", "ok": True, "id": "i1", "title": "Hello", "tags": ["plane"]}])
        self.assertEqual(self.token_file.read_text(), GOOD)
        self.assertEqual(self.token_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual([c[:2] for c in FakeFolio.calls], [("POST", "/sessions"), ("POST", "/items"), ("PATCH", "/items/i1")])
        self.assertEqual(FakeFolio.calls[2][2], {"item": {"tags_list": ["plane"]}})

    def test_reuses_cached_token_without_logging_in(self):
        self.token_file.parent.mkdir(parents=True)
        self.token_file.write_text(GOOD)
        code, _ = self.run_script("save", "https://example.com/a")
        self.assertEqual(code, 0)
        self.assertEqual([c[:2] for c in FakeFolio.calls], [("POST", "/items")])

    def test_expired_token_relogs_in_once(self):
        self.token_file.parent.mkdir(parents=True)
        self.token_file.write_text("stale")
        code, out = self.run_script("save", "https://example.com/a")
        self.assertEqual(code, 0)
        self.assertTrue(out[0]["ok"])
        self.assertEqual([c[:2] for c in FakeFolio.calls], [("POST", "/items"), ("POST", "/sessions"), ("POST", "/items")])
        self.assertEqual(self.token_file.read_text(), GOOD)

    def test_bad_credentials_fail_without_success_report(self):
        self.env["FOLIO_PASSWORD"] = "wrong"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "save", "https://example.com/a"], env=self.env, capture_output=True, text=True, check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("rejected", proc.stderr)
        self.assertNotIn('"ok": true', proc.stdout)
        self.assertFalse(self.token_file.exists())

    def test_dry_run_sends_nothing(self):
        code, out = self.run_script("save", "https://example.com/a", "--dry-run")
        self.assertEqual(code, 0)
        self.assertTrue(out[0]["dry_run"])
        self.assertEqual(FakeFolio.calls, [])

    def test_rejects_non_http_url(self):
        code, out = self.run_script("save", "file:///etc/passwd", "--dry-run")
        self.assertEqual(code, 1)
        self.assertFalse(out[0]["ok"])
        self.assertEqual(FakeFolio.calls, [])

    def test_check_reports_email(self):
        code, out = self.run_script("check")
        self.assertEqual((code, out), (0, [{"ok": True, "email": "me@example.com"}]))


if __name__ == "__main__":
    unittest.main()
