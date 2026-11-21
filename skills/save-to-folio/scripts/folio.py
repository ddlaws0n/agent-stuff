# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Save article URLs to Folio (savewithfolio.com) through its private v4 API.

Logs in with credentials from 1Password, caches the bearer token, and reuses it
until the API answers 401. Prints one JSON object per line and exits 1 if any
URL failed.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

API = os.environ.get("FOLIO_API_URL", "https://api.savewithfolio.com/v4")
OP_ITEM = os.environ.get("FOLIO_OP_ITEM", "op://Private/Folio")
TOKEN_FILE = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "save-to-folio"
    / "token"
)


class AuthError(RuntimeError):
    pass


def origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None:
        raise ValueError("invalid HTTP origin")
    port = parts.port
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    return parts.scheme, parts.hostname, port


class SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            allowed = origin(req.full_url) == origin(newurl)
        except ValueError:
            allowed = False
        if not allowed:
            # The caller closes the response and reports only the original request status.
            raise urllib.error.HTTPError(req.full_url, code, "redirect outside API origin", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameOriginRedirects())


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": "save-to-folio"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
    try:
        with OPENER.open(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        err.close()
        error = AuthError if err.code == 401 else RuntimeError
        raise error(f"{method} {path} -> HTTP {err.code}") from None
    except http.client.HTTPException:
        raise RuntimeError(f"{method} {path} -> invalid or incomplete HTTP response") from None
    try:
        payload = json.loads(raw) if raw else {}
    except (ValueError, UnicodeError):
        raise RuntimeError(f"{method} {path} returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {path} returned an unexpected response")
    return payload


def op_read(field: str) -> str:
    if os.environ.get(f"FOLIO_{field.upper()}"):
        return os.environ[f"FOLIO_{field.upper()}"]
    ref = f"{OP_ITEM}/{field}"
    try:
        out = subprocess.run(["op", "read", "--no-newline", ref], capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("1Password CLI (op) not found; install it or set FOLIO_USERNAME/FOLIO_PASSWORD") from None
    except subprocess.CalledProcessError as err:
        raise RuntimeError(f"op read {ref} failed (exit {err.returncode})") from None
    return out.stdout.decode("utf-8")


def login() -> str:
    creds = {"email": op_read("username"), "password": op_read("password")}
    try:
        resp = request("POST", "/sessions", {"user": creds})
    except AuthError:
        raise RuntimeError("Folio rejected the login credentials (HTTP 401)") from None
    token = resp.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("login response had no token")
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=TOKEN_FILE.parent, delete=False) as tmp:
        try:
            tmp.write(token)
            tmp.close()
            os.replace(tmp.name, TOKEN_FILE)
        finally:
            Path(tmp.name).unlink(missing_ok=True)
    return token


def cached_token() -> str | None:
    try:
        with TOKEN_FILE.open() as stream:
            os.fchmod(stream.fileno(), 0o600)
            return stream.read().strip() or None
    except FileNotFoundError:
        return None


def authenticated(method: str, path: str, body: dict | None = None) -> dict:
    token = cached_token()
    if token:
        try:
            return request(method, path, body, token)
        except AuthError:
            pass
    return request(method, path, body, login())


def save(url: str, tags: list[str]) -> dict:
    item = authenticated("POST", "/items", {"item": {"url": url}}).get("item")
    if not isinstance(item, dict) or not item.get("id"):
        raise RuntimeError("unconfirmed save: Folio returned no item ID")
    result = {"url": url, "ok": True, "id": item["id"], "title": item.get("title"), "tags": []}
    if tags:
        try:
            authenticated("PATCH", f"/items/{item['id']}", {"item": {"tags_list": tags}})
        except (RuntimeError, OSError) as err:
            return {**result, "ok": False, "saved": True, "error": f"tagging failed: {err}"}
        result["tags"] = tags
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_save = sub.add_parser("save", help="save one or more URLs")
    p_save.add_argument("urls", nargs="+")
    p_save.add_argument("--tag", action="append", default=[], help="tag to set (repeatable)")
    p_save.add_argument("--dry-run", action="store_true", help="print requests, send nothing")
    sub.add_parser("check", help="verify the token works (logs in if needed)")
    sub.add_parser("logout", help="forget the cached token")
    args = parser.parse_args()

    if args.cmd == "logout":
        TOKEN_FILE.unlink(missing_ok=True)
        print(json.dumps({"ok": True, "logged_out": True}))
        return 0
    if args.cmd == "check":
        user = authenticated("GET", "/users/current")
        print(json.dumps({"ok": True, "email": (user.get("user") or user).get("email")}))
        return 0

    failed = 0
    for url in args.urls:
        if not url.startswith(("http://", "https://")):
            print(json.dumps({"url": url, "ok": False, "error": "not an http(s) URL"}))
            failed += 1
            continue
        if args.dry_run:
            print(json.dumps({"url": url, "ok": True, "dry_run": True, "request": f"POST {API}/items", "tags": args.tag}))
            continue
        try:
            result = save(url, args.tag)
            print(json.dumps(result), flush=True)
            failed += int(not result["ok"])
        except (RuntimeError, OSError) as err:
            print(json.dumps({"url": url, "ok": False, "error": str(err)}), flush=True)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as err:
        sys.exit(str(err))
