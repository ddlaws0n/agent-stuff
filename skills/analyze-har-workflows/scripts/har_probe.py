#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ijson>=3.2,<4",
# ]
# ///
"""Stream-first HAR summarizer/extractor for agent workflows.

Usage:
  uv run scripts/har_probe.py summarize session.har --out har-analysis
  uv run scripts/har_probe.py show session.har --indices 12,18
  uv run scripts/har_probe.py extract session.har --indices 12,18,21-24 --out selected.json

Design goals:
- Never require loading a huge HAR into agent context.
- Stream entries with ijson where available.
- Emit compact, best-effort-redacted shapes; outputs still require private handling.
- Keep stdout small and parseable; write large details to files.
"""

from __future__ import annotations

import argparse
import base64
import csv
import heapq
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

try:
    import ijson  # type: ignore
except Exception:  # pragma: no cover - fallback for small files only
    ijson = None

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(authorization|cookie|set-cookie|csrf|xsrf|token|secret|password|passwd|pwd|api[-_]?key|session|jwt|otp|mfa|credit|card|cvv|ssn)"
)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
HEX_LONG_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ][\d:.]+(Z|[+-]\d{2}:?\d{2})?")
STATIC_EXT_RE = re.compile(r"(?i)\.(?:png|jpe?g|gif|webp|svg|ico|css|js|map|woff2?|ttf|otf|mp4|webm|mp3|wav|pdf)(?:$|[?#])")
ACTION_WORD_RE = re.compile(
    r"(?i)(api|graphql|mutation|create|update|patch|save|submit|upload|complete|attach|delete|remove|settings|profile|account|checkout|confirm|order|invite|user|admin)"
)
ANALYTICS_DOMAIN_RE = re.compile(
    r"(?i)(google-analytics|googletagmanager|doubleclick|segment|amplitude|mixpanel|hotjar|sentry|datadog|newrelic|intercom|fullstory|clarity|optimizely|facebook|linkedin"
    r"|qualtrics|omtrdc|demdex|adobedc|tealium|contentsquare|glassbox|dynatrace|quantummetric|bat\.bing|awin|onetrust|cookielaw)"
)
# First-party telemetry often lives on the app's own domain.
TELEMETRY_PATH_RE = re.compile(r"(?i)/(beacon|collect|track|tracking|telemetry|observability|rum|logs?|metrics|pixel|b/ss)(?:/|$|\?)")
# Browser-default headers that rarely matter for replay; `show` omits them.
QUIET_HEADERS = {
    "user-agent", "accept-encoding", "accept-language", "connection", "host", "content-length", "priority", "pragma",
    "te", "dnt", "upgrade-insecure-requests", "cache-control", "if-none-match", "if-modified-since",
}
PLAIN_HEADERS = {"content-type", "accept", "x-requested-with", "content-encoding"}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def redact_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if not text:
        return text
    text = JWT_RE.sub("<jwt:redacted>", text)
    text = EMAIL_RE.sub("<email:redacted>", text)
    # Mask long bearer/session-like strings while retaining shape.
    text = re.sub(r"(?i)\b(Bearer|Token)\s+[A-Za-z0-9._~+/=-]{12,}", r"\1 <token:redacted>", text)
    text = re.sub(r"\b[A-Za-z0-9._~+/=-]{40,}\b", "<redacted>", text)
    return text


def is_epoch(text: str) -> bool:
    return len(text) in (10, 13) and text.isdigit() and text[0] == "1"


def value_shape(value: Any) -> str:
    """Name a captured value's kind (date, uuid, word, ...) so outputs keep its meaning without the value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "epoch" if is_epoch(str(value)) else "integer"
    if isinstance(value, float):
        return "number"
    text = str(value).strip()
    if not text:
        return "empty"
    if JWT_RE.fullmatch(text):
        return "jwt"
    if UUID_RE.fullmatch(text):
        return "uuid"
    if EMAIL_RE.fullmatch(text):
        return "email"
    if re.match(r"(?i)https?://", text):
        return "url"
    if DATE_RE.fullmatch(text):
        return "date"
    if DATETIME_RE.fullmatch(text):
        return "datetime"
    if re.fullmatch(r"-?\d+", text):
        return "epoch" if is_epoch(text) else "numeric-string"
    if re.fullmatch(r"-?\d+\.\d+", text):
        return "decimal-string"
    if text.lower() in ("true", "false"):
        return "boolean-string"
    if HEX_LONG_RE.fullmatch(text):
        return "hex"
    if re.fullmatch(r"[A-Z]{2,4}", text):
        return "code"
    if re.fullmatch(r"[a-z][a-z_-]{1,31}", text):
        return "word"
    if re.search(r"\s", text):
        return "text"
    if len(text) >= 20 and re.fullmatch(r"[A-Za-z0-9._~+/=-]+", text):
        return "token"
    if re.fullmatch(r"[A-Za-z0-9_-]+", text) and re.search(r"\d", text):
        return "id"
    return "string"


def redact_mapping(obj: Any) -> Any:
    """Keep body structure for analysis, but never emit captured leaf values."""
    if isinstance(obj, dict):
        return {str(redact_scalar(k)): redact_mapping(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_mapping(v) for v in obj[:200]]
    if obj is None:
        return None
    return f"<{value_shape(obj)}>"


def json_shapes(obj: Any, prefix: str = "", out: Optional[Dict[str, str]] = None, limit: int = 60, shape: Callable[[Any], str] = value_shape) -> Dict[str, str]:
    """Flatten JSON into {path: kind}, collapsing list items into `[]`."""
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:200]:
            if len(out) >= limit:
                break
            json_shapes(v, f"{prefix}.{redact_scalar(k)}" if prefix else str(redact_scalar(k)), out, limit, shape)
    elif isinstance(obj, list):
        if not obj:
            out.setdefault(prefix + "[]", "empty-list")
        for v in obj[:3]:
            json_shapes(v, prefix + "[]", out, limit, shape)
    elif len(out) < limit:
        out.setdefault(prefix or "$", shape(obj))
    return out


def body_shapes(post: Dict[str, Any], limit: int = 60, shape: Callable[[Any], str] = value_shape) -> Dict[str, str]:
    """{field: kind} for a request body (form params, urlencoded, JSON, multipart)."""
    text = str(post.get("text") or "")
    mime = str(post.get("mimeType") or "")
    params = post.get("params")
    if isinstance(params, list) and params:
        return {str(redact_scalar(p["name"])): "file" if p.get("fileName") else shape(p.get("value"))
                for p in params[:limit] if isinstance(p, dict) and p.get("name")}
    if "x-www-form-urlencoded" in mime:
        return {str(redact_scalar(k)): shape(v) for k, v in parse_qsl(text, keep_blank_values=True)[:limit]}
    parsed = parse_json_maybe(text)
    if parsed is not None:
        return json_shapes(parsed, limit=limit, shape=shape)
    if "multipart/form-data" in mime:
        return {str(redact_scalar(k)): "part" for k in re.findall(r'name="([^"\r\n]+)"', text)[:limit]}
    return {}


def query_shapes(url: str, shape: Callable[[Any], str] = value_shape) -> Dict[str, str]:
    return {str(redact_scalar(k)): shape(v) for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True)[:50]}


def format_shapes(shapes: Dict[str, str], limit: int = 25) -> str:
    items = [f"{k}=<{v}>" for k, v in list(shapes.items())[:limit]]
    if len(shapes) > limit:
        items.append(f"(+{len(shapes) - limit} more)")
    return " ".join(items)


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def header_pairs(headers: Any) -> List[Tuple[str, str]]:
    """(lowercase name, value) for each HAR header, in capture order."""
    if not isinstance(headers, list):
        return []
    return [(str(h.get("name", "")).strip().lower(), str(h.get("value", ""))) for h in headers if isinstance(h, dict)]


def headers_to_map(headers: Any) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not isinstance(headers, list):
        return result
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = str(h.get("name", "")).strip()
        value = str(h.get("value", ""))
        if not name:
            continue
        lname = name.lower()
        if SENSITIVE_KEY_RE.search(lname):
            result[lname] = "<redacted>"
        else:
            result[lname] = str(redact_scalar(value))
    return result


def parse_json_maybe(text: str) -> Optional[Any]:
    if not text:
        return None
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except Exception:
        return None


def truncate_text(text: str, limit: int) -> Tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n...<truncated {len(text) - limit} chars>", True


def maybe_decode_content(content: Dict[str, Any]) -> str:
    text = content.get("text")
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    encoding = str(content.get("encoding", "")).lower()
    if encoding == "base64":
        try:
            raw = base64.b64decode(text, validate=False)
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return "<base64 content not decoded>"
    return text


def normalize_path(path: str) -> str:
    parts: List[str] = []
    for part in path.split("/"):
        if not part:
            continue
        p = UUID_RE.sub("{uuid}", part)
        if EMAIL_RE.search(p) or len(p) > 48:
            parts.append("{redacted}")
            continue
        if p != part:
            parts.append(p)
            continue
        if re.fullmatch(r"\d+", part):
            parts.append("{id}")
        elif HEX_LONG_RE.fullmatch(part):
            parts.append("{hex}")
        elif len(part) > 48 and re.fullmatch(r"[A-Za-z0-9._~-]+", part):
            parts.append("{token}")
        elif re.fullmatch(r"[A-Za-z0-9_~-]+", part) and (len(re.findall(r"\d", part)) >= 3 or (len(part) >= 8 and re.search(r"\d", part))):
            # Prefixed or mixed IDs such as rec_7f3a91c2, upl_123, AB12345678.
            parts.append("{id}")
        else:
            parts.append(part)
    return "/" + "/".join(parts)


def normalize_url(url: str, graphql_operation: Optional[str] = None) -> Dict[str, Any]:
    parsed = urlparse(url or "")
    query_keys = sorted({str(redact_scalar(k)) for k, _ in parse_qsl(parsed.query, keep_blank_values=True)})[:50]
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    safe_path = normalize_path(parsed.path or "/")
    normalized = f"{parsed.scheme}://{host}{safe_path}"
    if query_keys:
        normalized += "?" + "&".join(f"{k}=<value>" for k in query_keys)
    if graphql_operation:
        normalized += f"#{graphql_operation}"
    return {
        "scheme": parsed.scheme,
        "host": host,
        "path": safe_path,
        "normalized": normalized,
        "query_keys": query_keys,
    }


def post_data_info(post_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(post_data, dict):
        return {"has_body": False}
    mime = str(post_data.get("mimeType", ""))
    text = post_data.get("text") or ""
    if not isinstance(text, str):
        text = str(text)
    params = post_data.get("params") if isinstance(post_data.get("params"), list) else []
    keys: List[str] = []
    files: List[str] = []
    if params:
        for p in params[:200]:
            if not isinstance(p, dict):
                continue
            if p.get("name"):
                keys.append(str(redact_scalar(p.get("name"))))
            if p.get("fileName"):
                files.append("<file>")
    elif "application/x-www-form-urlencoded" in mime:
        keys = [str(redact_scalar(k)) for k, _ in parse_qsl(text, keep_blank_values=True)][:200]
    else:
        parsed = parse_json_maybe(text)
        if isinstance(parsed, dict):
            keys = sorted(str(redact_scalar(k)) for k in parsed.keys())[:200]
        elif text and "multipart/form-data" in mime:
            keys = [str(redact_scalar(k)) for k in re.findall(r'name="([^"\r\n]+)"', text)[:200]]
            files = ["<file>"] if re.search(r'filename="[^"\r\n]+"', text) else []
    return {
        "has_body": bool(text or params),
        "mime": mime.split(";", 1)[0],
        "body_chars": len(text),
        "keys": sorted(set(keys))[:100],
        "file_names": sorted(set(files))[:50],
    }


def graphql_info(url: str, post_text: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"is_graphql": bool(re.search(r"(?i)graphql", url or ""))}
    parsed = parse_json_maybe(post_text or "")
    operation_name = None
    query_head = None
    variables_keys: List[str] = []
    if isinstance(parsed, dict):
        operation_name = parsed.get("operationName")
        query = parsed.get("query")
        if isinstance(parsed.get("variables"), dict):
            variables_keys = sorted(parsed["variables"].keys())[:100]
        if isinstance(query, str):
            m = re.search(r"\b(mutation|query)\s+([A-Za-z0-9_]+)?", query)
            if m:
                query_head = " ".join(x for x in m.groups() if x)
            if re.search(r"\bmutation\b", query):
                info["is_mutation"] = True
    if operation_name:
        info["operationName"] = str(operation_name)
        info["is_graphql"] = True
    if query_head:
        info["query_head"] = query_head
        info["is_graphql"] = True
    if variables_keys:
        info["variables_keys"] = variables_keys
    return info


def iter_har_entries(path: Path) -> Iterator[Dict[str, Any]]:
    if ijson is not None:
        with path.open("rb") as f:
            # use_float avoids Decimal values that json.dumps cannot serialize.
            for entry in ijson.items(f, "log.entries.item", use_float=True):
                yield entry
    else:
        # Fallback is intentionally only for small HARs.
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 100:
            raise RuntimeError("ijson is not installed and HAR is too large for fallback json.load. Run with: uv run scripts/har_probe.py ...")
        with path.open("r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        for entry in data.get("log", {}).get("entries", []):
            yield entry


def compact_entry(entry: Dict[str, Any], idx: int, max_body_chars: int = 0) -> Dict[str, Any]:
    req = entry.get("request", {}) if isinstance(entry.get("request"), dict) else {}
    res = entry.get("response", {}) if isinstance(entry.get("response"), dict) else {}
    method = str(req.get("method", ""))
    url = str(req.get("url", ""))
    status = int(res.get("status") or 0)
    started = entry.get("startedDateTime")
    resource_type = entry.get("_resourceType") or entry.get("resourceType") or ""
    req_headers = headers_to_map(req.get("headers"))
    res_headers = headers_to_map(res.get("headers"))
    post = req.get("postData", {}) if isinstance(req.get("postData"), dict) else {}
    post_text = str(post.get("text") or "")
    gql = graphql_info(url, post_text)
    norm = normalize_url(url, gql.get("operationName") or gql.get("query_head"))
    post_info = post_data_info(post)
    content = res.get("content", {}) if isinstance(res.get("content"), dict) else {}
    mime = str(content.get("mimeType") or res_headers.get("content-type", ""))
    response_text = maybe_decode_content(content)
    request_sample = ""
    response_sample = ""
    request_truncated = False
    response_truncated = False
    if max_body_chars and post_text and "json" in str(post_info.get("mime", "")).lower():
        parsed = parse_json_maybe(post_text)
        if parsed is not None:
            request_sample, request_truncated = truncate_text(json.dumps(redact_mapping(parsed), ensure_ascii=False, indent=2), max_body_chars)
    if max_body_chars and response_text and "json" in mime.lower():
        parsed = parse_json_maybe(response_text)
        if parsed is not None:
            response_sample, response_truncated = truncate_text(json.dumps(redact_mapping(parsed), ensure_ascii=False, indent=2), max_body_chars)

    request_out: Dict[str, Any] = {
        "headers_present": sorted(req_headers.keys())[:80],
        "content_type": req_headers.get("content-type", "").split(";", 1)[0],
        "postData": post_info,
    }
    out: Dict[str, Any] = {
        "index": idx,
        "startedDateTime": started,
        "method": method,
        "status": status,
        "time_ms": entry.get("time"),
        "resourceType": resource_type,
        "url": {
            "host": norm["host"],
            "path": norm["path"],
            "normalized": norm["normalized"],
            "query_keys": norm["query_keys"],
        },
        "request": request_out,
        "response": {
            "mime": mime.split(";", 1)[0],
            "body_chars": len(response_text),
            "headers_present": sorted(res_headers.keys())[:80],
            "redirectURL": normalize_url(str(res.get("redirectURL")))["normalized"] if res.get("redirectURL") else "",
        },
    }
    if gql.get("is_graphql"):
        out["graphql"] = gql
    if request_sample:
        out["request"]["sample"] = request_sample
        out["request"]["sample_truncated"] = request_truncated
    if response_sample:
        out["response"]["sample"] = response_sample
        out["response"]["sample_truncated"] = response_truncated
    return out


def candidate_score(c: Dict[str, Any]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    method = c.get("method", "")
    status = int(c.get("status") or 0)
    normalized = c.get("url", {}).get("normalized", "")
    path = c.get("url", {}).get("path", "")
    host = c.get("url", {}).get("host", "")
    resource_type = str(c.get("resourceType") or "").lower()
    post_info = c.get("request", {}).get("postData", {})
    req_ct = str(c.get("request", {}).get("content_type", ""))
    res_mime = str(c.get("response", {}).get("mime", ""))

    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        score += 40
        reasons.append(f"mutating method {method}")
    if post_info.get("has_body"):
        score += 20
        reasons.append("request body present")
    if resource_type in {"xhr", "fetch", "websocket"}:
        score += 15
        reasons.append(f"resource type {resource_type}")
    if 200 <= status < 400:
        score += 10
        reasons.append(f"successful status {status}")
    elif status >= 400 and method in {"POST", "PUT", "PATCH", "DELETE"}:
        score += 6
        reasons.append(f"mutating request with error/status {status}")
    if ACTION_WORD_RE.search(normalized):
        score += 12
        reasons.append("action-like endpoint terms")
    if "graphql" in c:
        score += 12
        reasons.append("GraphQL operation")
        if c.get("graphql", {}).get("is_mutation"):
            score += 12
            reasons.append("GraphQL mutation")
    if re.search(r"(?i)(multipart|octet-stream|application/pdf|image/|video/)", req_ct):
        score += 15
        reasons.append("upload-like content type")
    if post_info.get("file_names"):
        score += 15
        reasons.append("multipart file fields")
    if re.search(r"(?i)(json|x-www-form-urlencoded|multipart)", req_ct):
        score += 8
        reasons.append("scriptable body content type")
    if re.search(r"(?i)(json|html)", res_mime):
        score += 4
        reasons.append("structured/textual response")
    if STATIC_EXT_RE.search(path):
        score -= 35
        reasons.append("static asset extension")
    if ANALYTICS_DOMAIN_RE.search(host):
        score -= 30
        reasons.append("third-party telemetry domain")
    elif TELEMETRY_PATH_RE.search(path):
        score -= 30
        reasons.append("telemetry endpoint path")
    if method == "OPTIONS":
        score -= 40
        reasons.append("CORS preflight")
    if status == 0:
        score -= 20
        reasons.append("no response (blocked or aborted)")
    if method == "GET" and not post_info.get("has_body") and resource_type in {"image", "font", "stylesheet", "script"}:
        score -= 25
        reasons.append("static page asset")
    return score, reasons


def header_summary(headers: Any) -> List[str]:
    """Header names with safe values: kinds for custom headers, names only for cookies."""
    out: List[str] = []
    for lname, value in header_pairs(headers):
        if not lname or lname in QUIET_HEADERS or lname.startswith(("sec-", ":")):
            continue
        if lname in ("cookie", "set-cookie"):
            parts = value.split(";") if lname == "cookie" else value.split(";", 1)[:1]
            names = [str(redact_scalar(p.split("=", 1)[0].strip())) for p in parts if p.strip()]
            out.append(f"{lname}=<names: {', '.join(names[:12])}>")
        elif lname == "authorization":
            out.append(f"authorization=<{value.split(' ', 1)[0] if ' ' in value.strip() else 'credential'} redacted>")
        elif SENSITIVE_KEY_RE.search(lname):
            out.append(f"{lname}=<redacted>")
        elif lname in ("origin", "referer", "location"):
            out.append(f"{lname}={normalize_url(value)['normalized']}")
        elif lname in PLAIN_HEADERS:
            out.append(f"{lname}={str(redact_scalar(value.split(';', 1)[0]))[:60]}")
        else:
            out.append(f"{lname}=<{value_shape(value)}>")
    return out


def show_entry(entry: Dict[str, Any], idx: int, max_chars: int, shape: Callable[[Any], str] = value_shape) -> str:
    c = compact_entry(entry, idx)
    score, reasons = candidate_score(c)
    req = as_dict(entry.get("request"))
    res = as_dict(entry.get("response"))
    post = as_dict(req.get("postData"))
    lines = [
        f"#{idx} {c['method']} {c['status']} {c['resourceType'] or '-'} {c['url']['normalized']}",
        f"  at {c['startedDateTime']}; score {score} ({'; '.join(reasons[:4])})",
    ]
    req_headers = header_summary(req.get("headers"))
    if not any(h.startswith("cookie=") for h in req_headers) and isinstance(req.get("cookies"), list) and req["cookies"]:
        req_headers.append(f"cookie=<names: {', '.join(str(redact_scalar(k.get('name'))) for k in req['cookies'][:12] if isinstance(k, dict))}>")
    lines.append("  request headers: " + (" ".join(req_headers) or "none beyond browser defaults"))
    if query := query_shapes(str(req.get("url", "")), shape=shape):
        lines.append("  query: " + format_shapes(query))
    info = c["request"]["postData"]
    if info.get("has_body"):
        lines.append(f"  body: {info['mime'] or '-'}, {info['body_chars']} chars: {format_shapes(body_shapes(post, shape=shape)) or '(no fields parsed)'}")
    if "graphql" in c:
        lines.append(f"  graphql: {c['graphql'].get('operationName') or c['graphql'].get('query_head') or 'unnamed'}")
    text = maybe_decode_content(as_dict(res.get("content")))
    lines.append(f"  response: {c['response']['mime'] or '-'}, " + (f"{len(text)} chars" if text else "no body in capture"))
    if res_headers := [h for h in header_summary(res.get("headers")) if h.startswith(("set-cookie=", "location="))]:
        lines.append("  response headers: " + " ".join(res_headers))
    parsed = parse_json_maybe(text)
    if parsed is not None:
        lines.append("  response fields: " + (format_shapes(json_shapes(parsed, shape=shape)) or "(empty)"))
    out, _ = truncate_text("\n".join(lines), max_chars)
    return out


def parse_indices(spec: str) -> List[int]:
    result: List[int] = []
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
            if end < start:
                start, end = end, start
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def cmd_summarize(args: argparse.Namespace) -> int:
    har = Path(args.har)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    entries_path = outdir / "entries.jsonl"
    candidates_path = outdir / "candidates.jsonl"
    endpoints_path = outdir / "endpoints.tsv"
    summary_path = outdir / "summary.json"

    method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    host_counts: Counter[str] = Counter()
    resource_counts: Counter[str] = Counter()
    mime_counts: Counter[str] = Counter()
    endpoint_counts: Counter[Tuple[str, str]] = Counter()
    endpoint_statuses: Dict[Tuple[str, str], Counter[str]] = defaultdict(Counter)
    total = 0
    scored_candidates: List[Tuple[int, str, int, Dict[str, Any]]] = []

    eprint(f"Streaming HAR: {har} ({har.stat().st_size / (1024*1024):.1f} MB)")
    with entries_path.open("w", encoding="utf-8") as ef:
        for idx, entry in enumerate(iter_har_entries(har)):
            total += 1
            c = compact_entry(entry, idx, max_body_chars=args.max_body_chars)
            score, reasons = candidate_score(c)
            c_small = dict(c)
            c_small["candidate_score"] = score
            c_small["candidate_reasons"] = reasons
            ef.write(json.dumps(c_small, ensure_ascii=False) + "\n")

            method_counts[c.get("method", "")] += 1
            status_counts[str(c.get("status", ""))] += 1
            host_counts[c.get("url", {}).get("host", "")] += 1
            resource_counts[str(c.get("resourceType") or "")] += 1
            mime_counts[str(c.get("response", {}).get("mime") or "")] += 1
            ep_key = (c.get("method", ""), c.get("url", {}).get("normalized", ""))
            endpoint_counts[ep_key] += 1
            endpoint_statuses[ep_key][str(c.get("status", ""))] += 1
            if score >= args.min_candidate_score:
                cand = {
                    "index": idx,
                    "candidate_score": score,
                    "candidate_reasons": reasons,
                    "startedDateTime": c.get("startedDateTime"),
                    "method": c.get("method"),
                    "status": c.get("status"),
                    "resourceType": c.get("resourceType"),
                    "url": c.get("url"),
                    "request": {
                        "content_type": c.get("request", {}).get("content_type"),
                        "postData": c.get("request", {}).get("postData"),
                    },
                    "response": {
                        "mime": c.get("response", {}).get("mime"),
                        "body_chars": c.get("response", {}).get("body_chars"),
                        "redirectURL": c.get("response", {}).get("redirectURL"),
                    },
                }
                if "graphql" in c:
                    cand["graphql"] = c["graphql"]
                ranked = (score, str(cand.get("startedDateTime")), -idx, cand)
                if len(scored_candidates) < args.top:
                    heapq.heappush(scored_candidates, ranked)
                elif args.top and ranked[:3] > scored_candidates[0][:3]:
                    heapq.heapreplace(scored_candidates, ranked)
            if total % 5000 == 0:
                eprint(f"  processed {total} entries...")

    top_candidates = [item[3] for item in sorted(scored_candidates, reverse=True)]
    with candidates_path.open("w", encoding="utf-8") as cf:
        for cand in top_candidates:
            cf.write(json.dumps(cand, ensure_ascii=False) + "\n")

    with endpoints_path.open("w", encoding="utf-8", newline="") as tf:
        writer = csv.writer(tf, delimiter="\t")
        writer.writerow(["count", "method", "normalized_url", "statuses"])
        for (method, normalized), count in endpoint_counts.most_common(args.top_endpoints):
            statuses = ",".join(f"{k}:{v}" for k, v in endpoint_statuses[(method, normalized)].most_common())
            writer.writerow([count, method, normalized, statuses])

    summary = {
        "har_file": str(har),
        "har_size_mb": round(har.stat().st_size / (1024 * 1024), 2),
        "total_entries": total,
        "outputs": {
            "entries_jsonl": str(entries_path),
            "candidates_jsonl": str(candidates_path),
            "endpoints_tsv": str(endpoints_path),
            "summary_json": str(summary_path),
        },
        "counts": {
            "methods": method_counts.most_common(),
            "statuses": status_counts.most_common(50),
            "hosts": host_counts.most_common(50),
            "resourceTypes": resource_counts.most_common(50),
            "response_mimes": mime_counts.most_common(50),
        },
        # One line per candidate; full details stay in candidates.jsonl.
        "top_candidates": [
            {"index": c["index"], "score": c["candidate_score"], "method": c["method"], "status": c["status"], "endpoint": c["url"]["normalized"]}
            for c in top_candidates[:20]
        ],
        "notes": [
            "Body samples contain key/type shapes only; non-JSON body values are omitted. Outputs remain sensitive and should not be shared without review.",
            "Candidate scores are heuristics. Confirm workflow sequence against the user's described action and timestamps.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "summary_file": str(summary_path), "total_entries": total}, ensure_ascii=False))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    har = Path(args.har)
    indices = set(parse_indices(args.indices))
    if not indices:
        raise SystemExit("--indices produced no request indices")
    selected: List[Dict[str, Any]] = []
    max_idx = max(indices)
    eprint(f"Extracting {len(indices)} selected entries from {har}")
    for idx, entry in enumerate(iter_har_entries(har)):
        if idx in indices:
            c = compact_entry(entry, idx, max_body_chars=args.max_body_chars)
            score, reasons = candidate_score(c)
            c["candidate_score"] = score
            c["candidate_reasons"] = reasons
            selected.append(c)
        if idx >= max_idx and len(selected) == len(indices):
            break
    result = {"har_file": str(har), "selected_indices": sorted(indices), "entries_found": len(selected), "entries": selected}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "out": str(args.out), "entries_found": len(selected)}, ensure_ascii=False))
    else:
        print(text)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    indices = set(parse_indices(args.indices))
    if not indices:
        raise SystemExit("--indices produced no request indices")
    found = 0
    value_ids: Dict[str, int] = {}

    def shape(value: Any) -> str:
        kind = value_shape(value)
        if not args.value_ids:
            return kind
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        identifier = value_ids.setdefault(key, len(value_ids) + 1)
        return f"{kind}:v{identifier}"

    if args.value_ids:
        print("Value IDs compare sampled query/body fields within this command only; they are separate from graph fingerprints.")
    max_idx = max(indices)
    for idx, entry in enumerate(iter_har_entries(Path(args.har))):
        if idx in indices:
            print(show_entry(entry, idx, args.max_chars, shape=shape))
            found += 1
        if idx >= max_idx:
            break
    if found < len(indices):
        print(f"({len(indices) - found} requested indices not in capture)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream and redact HAR files for agent-friendly workflow analysis.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("summarize", help="Stream a HAR and emit compact summary files.")
    s.add_argument("har", help="Path to .har file")
    s.add_argument("--out", required=True, help="Output directory")
    s.add_argument("--max-body-chars", type=int, default=2000, help="Max JSON body shape chars per entry in entries.jsonl (default: 2000). Use 0 for no samples.")
    s.add_argument("--top", type=int, default=200, help="Number of candidate action requests to write (default: 200)")
    s.add_argument("--top-endpoints", type=int, default=500, help="Number of endpoint patterns to write (default: 500)")
    s.add_argument("--min-candidate-score", type=int, default=25, help="Minimum heuristic score to include in candidates (default: 25)")
    s.set_defaults(func=cmd_summarize)

    x = sub.add_parser("extract", help="Extract redacted details for selected request indices.")
    x.add_argument("har", help="Path to .har file")
    x.add_argument("--indices", required=True, help="Comma/space-separated indices or ranges, e.g. 12,18,21-24")
    x.add_argument("--out", help="Output JSON file. If omitted, prints JSON to stdout.")
    x.add_argument("--max-body-chars", type=int, default=12000, help="Max JSON body shape chars per selected entry (default: 12000)")
    x.set_defaults(func=cmd_extract)

    w = sub.add_parser("show", help="Print a compact, redacted view of selected requests (headers, field kinds, response shape).")
    w.add_argument("har", help="Path to .har file")
    w.add_argument("--indices", required=True, help="Comma/space-separated indices or ranges, e.g. 12,18,21-24")
    w.add_argument("--max-chars", type=int, default=1500, help="Max output chars per request (default: 1500)")
    w.add_argument("--value-ids", action="store_true", help="Add per-command opaque IDs to query/body field kinds for value comparison without printing values.")
    w.set_defaults(func=cmd_show)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0
    except Exception as exc:
        eprint(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
