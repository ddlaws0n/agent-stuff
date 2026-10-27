#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ijson>=3.2,<4"]
# ///
"""Inspect exact HAR body locations; compare values across captures without printing them.

Selectors are SOURCE:ENTRY:/json/pointer, with zero-based source and entry indices.
Only --values reveals explicitly selected scalars; containers and --walk stay private.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

import har_probe


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def selector(value: str) -> Tuple[int, int, str]:
    try:
        source, entry, pointer = value.split(":", 2)
        source, entry = int(source), int(entry)
        if source < 0 or entry < 0 or (pointer and not pointer.startswith("/")):
            raise ValueError()
        if re.search(r"~(?![01])", pointer):
            raise ValueError()
        return source, entry, pointer
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use SOURCE:ENTRY:/json/pointer (zero-based indices)") from exc


def decode(value: Any, max_chars: int, decoded_at: Dict[str, int] | None = None, pointer: str = "") -> Any:
    # Workflow roots and schemas are often JSON strings inside JSON responses.
    for layer in range(1, 5):
        if not isinstance(value, str) or not value.lstrip().startswith(("{", "[", '"')):
            return value
        if len(value) > max_chars:
            raise ValueError("encoded JSON exceeds --max-json-chars")
        try:
            value = json.loads(value)
        except ValueError:
            return value
        if decoded_at is not None:
            decoded_at[pointer] = max(decoded_at.get(pointer, 0), layer)
    if isinstance(value, str) and value.lstrip().startswith(("{", "[", '"')):
        raise ValueError("nested JSON exceeds four decoding layers")
    return value


def sensitive_key(key: str) -> bool:
    return bool(har_probe.SENSITIVE_KEY_RE.search(key)) or key.lower() in {"pin", "credentials"}


def sensitive_record(value: Any) -> bool:
    return isinstance(value, dict) and any(
        isinstance(value.get(key), str) and sensitive_key(value[key])
        for key in ("name", "key", "label")
    )


def resolve(value: Any, pointer: str, max_chars: int, decoded_at: Dict[str, int] | None = None) -> Tuple[Any, bool]:
    hidden = False
    current = ""
    parts = pointer[1:].split("/") if pointer else []
    for encoded in parts:
        value = decode(value, max_chars, decoded_at, current)
        part = encoded.replace("~1", "/").replace("~0", "~")
        hidden |= sensitive_record(value) or sensitive_key(part)
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9]\d*", part):
                raise ValueError("array pointer requires a nonnegative canonical index")
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise ValueError("pointer traverses a scalar")
        current += "/" + encoded
    value = decode(value, max_chars, decoded_at, pointer)
    return value, hidden or sensitive_record(value)


def leaves(value: Any, pointer: str, hidden: bool, max_chars: int, decoded_at: Dict[str, int]) -> Iterator[Tuple[str, Any, bool]]:
    value = decode(value, max_chars, decoded_at, pointer)
    hidden |= sensitive_record(value)
    if isinstance(value, dict) and value:
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            private = hidden or sensitive_key(key)
            yield from leaves(child, pointer + "/" + escaped, private, max_chars, decoded_at)
    elif isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from leaves(child, pointer + "/" + str(index), hidden, max_chars, decoded_at)
    else:
        yield pointer, value, hidden


def describe(value: Any, hidden: bool, identities: Dict[str, str], reveal: bool) -> Dict[str, Any]:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    kind = "object" if isinstance(value, dict) else "array" if isinstance(value, list) else har_probe.value_shape(value)
    result: Dict[str, Any] = {"kind": kind, "value_id": identities.setdefault(digest, f"v{len(identities) + 1}")}
    if hidden:
        return {**result, "redacted": True}
    if isinstance(value, dict):
        result.update(length=len(value), keys=[har_probe.redact_scalar(k) for k in list(value)[:30]])
        result["keys_omitted"] = max(0, len(value) - 30)
    elif isinstance(value, list):
        result["length"] = len(value)
    elif reveal:
        safe = har_probe.redact_scalar(value)
        if isinstance(value, str) and value.lstrip().startswith(("http://", "https://")):
            safe = har_probe.normalize_url(value)["normalized"]
        if isinstance(safe, str) and len(safe) > 1000:
            safe = safe[:1000]
            result["value_truncated"] = True
        result["value"] = safe
    return result


def inspect(args: argparse.Namespace) -> Tuple[Dict[str, Any], bool]:
    selected = args.select or []
    expected = [(selector(location), json.loads(literal)) for location, literal in (args.expect or [])]
    locations = selected + [location for location, _ in expected]
    if not locations:
        raise ValueError("provide --select or --expect")
    if any(source >= len(args.har) for source, _, _ in locations):
        raise ValueError("selector source index is outside the supplied HAR list")
    if args.values and args.walk:
        raise ValueError("--values requires explicit scalar pointers; it cannot be combined with --walk")
    result: Dict[str, Any] = {"sources": [], "observations": [], "checks": [], "decoded_json": [], "truncated": False,
                              "notes": ["Value IDs compare JSON values within this command only; equality does not establish causality.",
                                        "Values are hidden by default. Explicit scalar disclosure is best-effort redacted; review before sharing."]}
    bodies: Dict[Tuple[int, int], Any] = {}
    for source, path in enumerate(args.har):
        wanted = {entry for s, entry, _ in locations if s == source}
        if not wanted:
            continue
        last_wanted = max(wanted)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        scanned = 0
        for index, entry in enumerate(har_probe.iter_har_entries(path)):
            scanned += 1
            if index in wanted:
                if args.body == "response":
                    text = har_probe.maybe_decode_content(har_probe.as_dict(har_probe.as_dict(entry.get("response")).get("content")))
                else:
                    text = str(har_probe.as_dict(har_probe.as_dict(entry.get("request")).get("postData")).get("text") or "")
                if not text:
                    raise ValueError(f"source {source}, entry {index}: body is missing")
                if len(text) > args.max_json_chars:
                    raise ValueError(f"source {source}, entry {index}: body exceeds --max-json-chars")
                bodies[source, index] = json.loads(text)
            if index >= last_wanted:
                break
        result["sources"].append({"source": source, "file": har_probe.redact_scalar(path.name), "sha256": digest.hexdigest(),
                                  "entries_scanned": scanned, "requested_entries": sorted(wanted)})
        for index in wanted:
            if (source, index) not in bodies:
                raise ValueError(f"source {source}, entry {index}: not found in capture")
    identities: Dict[str, str] = {}
    encodings: Dict[Tuple[int, int], Dict[str, int]] = {}
    for source, index, pointer in selected:
        decoded_at = encodings.setdefault((source, index), {})
        value, hidden = resolve(bodies[source, index], pointer, args.max_json_chars, decoded_at)
        rows = leaves(value, pointer, hidden, args.max_json_chars, decoded_at) if args.walk else iter([(pointer, value, hidden)])
        for location, child, private in rows:
            if len(result["observations"]) >= args.max_items:
                result["truncated"] = True
                break
            result["observations"].append({"source": source, "entry": index, "pointer": har_probe.redact_scalar(location),
                                           **describe(child, private, identities, args.values)})
    passed = True
    for (source, index, pointer), wanted in expected:
        decoded_at = encodings.setdefault((source, index), {})
        value, _ = resolve(bodies[source, index], pointer, args.max_json_chars, decoded_at)
        matches = type(value) is type(wanted) and value == wanted
        passed &= matches
        result["checks"].append({"source": source, "entry": index, "pointer": har_probe.redact_scalar(pointer), "matches": matches})
    result["decoded_json"] = [{"source": source, "entry": index, "pointer": har_probe.redact_scalar(pointer), "layers": layers}
                              for (source, index), paths in encodings.items() for pointer, layers in paths.items()]
    # Remove whole rows rather than emitting invalid, character-truncated JSON.
    while len(json.dumps(result, ensure_ascii=False)) > args.max_chars:
        result["truncated"] = True
        if result["observations"]:
            result["observations"].pop()
        elif result["checks"]:
            result["checks"].pop()
        else:
            raise ValueError("source metadata exceeds --max-chars; narrow the selection or increase the limit")
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("har", type=Path, nargs="+")
    parser.add_argument("--select", type=selector, action="append", help="SOURCE:ENTRY:/pointer; repeat to compare locations")
    parser.add_argument("--expect", nargs=2, action="append", metavar=("SELECTOR", "JSON"), help="check an exact JSON value without printing the captured value; repeatable")
    parser.add_argument("--body", choices=("request", "response"), default="response")
    parser.add_argument("--walk", action="store_true", help="inventory selected subtrees as bounded leaf paths and private value IDs")
    parser.add_argument("--values", action="store_true", help="reveal only explicitly selected scalar values with best-effort redaction")
    parser.add_argument("--max-items", type=positive, default=100)
    parser.add_argument("--max-chars", type=positive, default=6000)
    parser.add_argument("--max-json-chars", type=positive, default=2000000)
    args = parser.parse_args()
    try:
        result, passed = inspect(args)
    except (ValueError, KeyError, IndexError, OSError, argparse.ArgumentTypeError) as exc:
        # Do not echo unknown keys or malformed body fragments containing captured data.
        message = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print(json.dumps({"ok": False, "error": message}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
