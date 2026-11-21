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
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("FOLIO_API_URL", "https://api.savewithfolio.com/v4")
OP_ITEM = os.environ.get("FOLIO_OP_ITEM", "op://Private/Folio")
TOKEN_FILE = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "save-to-folio"
    / "token"
)


class AuthError(Exception):
    pass


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": "save-to-folio"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise AuthError(path) from err
        detail = err.read().decode(errors="replace")[:300]
        raise RuntimeError(f"{method} {path} -> HTTP {err.code}: {detail}") from err
    return json.loads(raw) if raw else {}


def op_read(field: str) -> str:
    if os.environ.get(f"FOLIO_{field.upper()}"):
        return os.environ[f"FOLIO_{field.upper()}"]
    ref = f"{OP_ITEM}/{field}"
    try:
        out = subprocess.run(["op", "read", ref], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("error: 1Password CLI (op) not found; install it or set FOLIO_USERNAME/FOLIO_PASSWORD")
    except subprocess.CalledProcessError as err:
        sys.exit(f"error: op read {ref} failed: {err.stderr.strip()}")
    return out.stdout.strip()


def login() -> str:
    creds = {"email": op_read("username"), "password": op_read("password")}
    try:
        resp = request("POST", "/sessions", {"user": creds})
    except AuthError:
        sys.exit("error: Folio rejected the 1Password credentials (401)")
    token = resp.get("token")
    if not token:
        sys.exit("error: login response had no token")
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.touch(mode=0o600)
    TOKEN_FILE.write_text(token)
    return token


def cached_token() -> str | None:
    try:
        return TOKEN_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def with_auth(fn):
    """Call fn(token) with the cached token, logging in again once on 401."""
    token = cached_token() or login()
    try:
        return fn(token)
    except AuthError:
        return fn(login())


def save(url: str, tags: list[str]) -> dict:
    def go(token: str) -> dict:
        item = request("POST", "/items", {"item": {"url": url}}, token).get("item") or {}
        if tags and item.get("id"):
            request("PATCH", f"/items/{item['id']}", {"item": {"tags_list": tags}}, token)
        return item

    item = with_auth(go)
    return {"url": url, "ok": True, "id": item.get("id"), "title": item.get("title"), "tags": tags}


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
        user = with_auth(lambda t: request("GET", "/users/current", token=t))
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
            print(json.dumps(save(url, args.tag)), flush=True)
        except (RuntimeError, AuthError, urllib.error.URLError, TimeoutError) as err:
            print(json.dumps({"url": url, "ok": False, "error": str(err)}), flush=True)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
