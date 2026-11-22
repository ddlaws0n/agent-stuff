"""folio.py against a local fake Folio API. Never touches the real service."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

SCRIPT = Path(__file__).parents[1] / "scripts" / "folio.py"
GOOD = "good-token"


class FakeFolio(BaseHTTPRequestHandler):
    calls: ClassVar[list[tuple[str, str, dict, str]]] = []

    truncate_once: ClassVar[tuple[str, str] | None] = None
    redirects: ClassVar[dict[str, str]] = {}
    scripted_replies: ClassVar[dict[tuple[str, str], list[tuple[int, dict]]]] = {}

    def log_message(self, format, *args):  # noqa: A002 - matches base signature
        pass

    def handle_any(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else {}
        auth = self.headers.get("Authorization", "")
        FakeFolio.calls.append((self.command, self.path, body, auth))
        if FakeFolio.truncate_once == (self.command, self.path):
            FakeFolio.truncate_once = None
            self.send_response(200)
            self.send_header("Content-Length", "128")
            self.end_headers()
            self.wfile.write(b"private-partial-response")
            self.close_connection = True
            return
        if target := FakeFolio.redirects.get(self.path):
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()
            return
        if responses := FakeFolio.scripted_replies.get((self.command, self.path)):
            return self.reply(*responses.pop(0))
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
        FakeFolio.truncate_once = None
        FakeFolio.redirects = {}
        FakeFolio.calls = []
        FakeFolio.scripted_replies = {}
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

    def test_redirect_origin_compares_scheme_host_and_effective_port(self):
        handler = runpy.run_path(str(SCRIPT))["SameOriginRedirects"]()
        req = urllib.request.Request("https://api.example.test/resource")
        for target in ("http://api.example.test:443", "https://api.example.test:8443",
                       "https://other.example.test", "https://name@api.example.test"):
            with self.subTest(target=target), self.assertRaises(urllib.error.HTTPError):
                handler.redirect_request(req, None, 302, "", {}, target)
        target = "https://API.EXAMPLE.TEST:443/new-path"
        redirected = handler.redirect_request(req, None, 302, "", {}, target)
        self.assertEqual(redirected.full_url, target)

    def test_cross_origin_redirect_stops_at_original_endpoint(self):
        # Both loopback hostnames reach this recorder, but identify different origins.
        target = f"http://localhost:{self.server.server_port}/redirect-target"
        for path in ("/sessions", "/items", "/items/i1", "/users/current"):
            with self.subTest(path=path):
                self.token_file.unlink(missing_ok=True)
                FakeFolio.calls.clear()
                FakeFolio.redirects = {path: target}
                args = ("check",) if path == "/users/current" else ("save", "https://example.com", "--tag", "test")
                code, _ = self.run_script(*args)
                self.assertEqual(code, 1)
                paths = [call[1] for call in FakeFolio.calls]
                self.assertIn(path, paths)
                self.assertNotIn("/redirect-target", paths)

    def test_relative_same_origin_redirect_preserves_authenticated_get(self):
        FakeFolio.redirects = {"/users/current": "/account"}
        FakeFolio.scripted_replies[("GET", "/account")] = [(200, {"user": {"email": "me@example.com"}})]
        code, out = self.run_script("check")
        self.assertEqual(code, 0)
        self.assertEqual(out[0]["email"], "me@example.com")
        self.assertEqual(FakeFolio.calls[-1], ("GET", "/account", {}, f"Bearer {GOOD}"))

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
        self.token_file.chmod(0o644)
        code, _ = self.run_script("save", "https://example.com/a")
        self.assertEqual(code, 0)
        self.assertEqual([c[:2] for c in FakeFolio.calls], [("POST", "/items")])
        self.assertEqual(self.token_file.stat().st_mode & 0o777, 0o600)

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
        self.assertIn("rejected", json.loads(proc.stdout)["error"])
        self.assertNotIn('"ok": true', proc.stdout)
        self.assertFalse(self.token_file.exists())

    def test_tag_retry_does_not_repeat_create(self):
        FakeFolio.scripted_replies[("PATCH", "/items/i1")] = [(401, {})]
        code, out = self.run_script("save", "https://example.com/a", "--tag", "plane")
        self.assertEqual(code, 0)
        self.assertTrue(out[0]["ok"])
        self.assertEqual([c[:2] for c in FakeFolio.calls], [
            ("POST", "/sessions"), ("POST", "/items"), ("PATCH", "/items/i1"),
            ("POST", "/sessions"), ("PATCH", "/items/i1"),
        ])

    def test_tag_failure_reports_saved_item_without_response_body(self):
        FakeFolio.scripted_replies[("PATCH", "/items/i1")] = [(422, {"error": "sensitive"})]
        code, out = self.run_script("save", "https://example.com/a", "--tag", "plane")
        self.assertEqual(code, 1)
        self.assertEqual(out[0], {"url": "https://example.com/a", "id": "i1", "title": "Hello",
                                  "ok": False, "saved": True, "tags": [],
                                  "error": "tagging failed: PATCH /items/i1 -> HTTP 422"})

    def test_missing_id_fails_without_tagging_or_retry(self):
        FakeFolio.scripted_replies[("POST", "/items")] = [(201, {"item": {"title": "Hello"}})]
        code, out = self.run_script("save", "https://example.com/a", "--tag", "plane")
        self.assertEqual(code, 1)
        self.assertFalse(out[0]["ok"])
        self.assertIn("no item ID", out[0]["error"])
        self.assertEqual([c[:2] for c in FakeFolio.calls], [("POST", "/sessions"), ("POST", "/items")])

    def test_truncated_create_or_tag_response_continues_batch(self):
        first, second = "https://example.com/first", "https://example.com/second"
        for method, path in (("POST", "/items"), ("PATCH", "/items/i1")):
            with self.subTest(method=method):
                FakeFolio.calls.clear()
                FakeFolio.truncate_once = (method, path)
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), "save", first, second, "--tag", "plane"],
                    env=self.env, capture_output=True, text=True,
                )
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(proc.stderr, "")
                self.assertNotIn("private-partial-response", proc.stdout)
                failed, saved = map(json.loads, proc.stdout.splitlines())
                self.assertEqual(failed["url"], first)
                self.assertFalse(failed["ok"])
                self.assertIn("HTTP response", failed["error"])
                if method == "PATCH":
                    self.assertTrue(failed["saved"])
                    self.assertEqual(failed["id"], "i1")
                else:
                    self.assertNotIn("saved", failed)
                self.assertEqual((saved["url"], saved["ok"], saved["tags"]), (second, True, ["plane"]))
                self.assertEqual([body["item"]["url"] for m, p, body, _ in FakeFolio.calls
                                  if (m, p) == ("POST", "/items")], [first, second])

    def test_op_password_preserves_whitespace(self):
        password = "  fixture\tvalue\r\n \t\n"
        (self.cache / "password").write_bytes(password.encode())
        op = self.cache / "op"
        op.write_text(
            '#!/bin/sh\n[ "$1" = read ] || exit 1\n'
            'cat "$FIXTURE_PASSWORD"\n[ "$2" = --no-newline ] || echo\n'
        )
        op.chmod(0o700)
        del self.env["FOLIO_PASSWORD"]
        self.env.update(PATH=f"{self.cache}:/usr/bin:/bin", FIXTURE_PASSWORD=str(self.cache / "password"))
        FakeFolio.scripted_replies[("POST", "/sessions")] = [(200, {"token": GOOD})]
        code, _ = self.run_script("check")
        self.assertEqual(code, 0)
        self.assertEqual(FakeFolio.calls[0][2]["user"]["password"], password)

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
