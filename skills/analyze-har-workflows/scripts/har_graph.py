#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ijson>=3.2,<4",
# ]
# ///
"""Build a workflow sequence graph from likely user-action requests in a HAR.

Usage:
  uv run scripts/har_graph.py session.har --out har-analysis
  uv run scripts/har_graph.py session.har --out har-analysis --indices 40-75

Links requests by:
- response-created IDs reused in later requests (path, query, body, headers)
- upload/session IDs and signed URLs handed from one response to a later request
- tokens (CSRF, nonce, bearer) issued in a response or HTML form and sent later
- the same resource ID shared by several requests
- redirects and Referer relationships
- timestamp proximity for requests with no stronger link

Writes graph.json and workflow.md. Values are never emitted: evidence uses value
kinds, key locations, and per-run salted fingerprints so edges stay comparable
inside one output without exposing the captured value.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, unquote, urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import har_probe  # noqa: E402  # ty: ignore[unresolved-import]

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
HEX_RE = re.compile(r"[0-9a-fA-F]{8,}")
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-.~+/=:]{8,512}")
SHORT_ID_RE = re.compile(r"(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{3,7}")
HIDDEN_INPUT_RE = re.compile(r"<input\b[^>]*>", re.I)
# "key":"value" in inline JSON, or "key","value" in transit-encoded page state.
INLINE_PAIR_RE = re.compile(r'"([A-Za-z_][\w-]{1,63})"\s*[:,]\s*"([^"\\]{4,512})"')
META_RE = re.compile(r"<meta\b[^>]*>", re.I)
ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
ID_KEY_RE = re.compile(r"(?i)(id|key|ref|uuid|guid|handle|number|code)$")
UPLOAD_KEY_RE = re.compile(r"(?i)(upload|file|blob|attachment|part|chunk|multipart|media|document)")
TOKEN_KEY_RE = re.compile(r"(?i)(csrf|xsrf|token|nonce|authenticity|verification|state|session|auth|signature|viewstate)")
# Cache-buster query keys carry per-load values that link unrelated requests.
CACHE_BUSTER_RE = re.compile(r"(?i)^(_|cb|cache|cachebust(er)?|nocache|rnd|rand(om)?|t|ts|timestamp)$")
SKIP_REQUEST_HEADERS = har_probe.QUIET_HEADERS | {"cookie", "accept", "content-type", "origin", "referer"}
STRONG_KINDS = {"created-id", "upload-id", "signed-url", "token", "response-id", "shared-id", "redirect"}
GROUPING_KINDS = STRONG_KINDS | {"temporal", "repeat"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Probe reasons that keep a request out of the default candidate set, whatever its score.
NOISE_REASONS = {"third-party telemetry domain", "telemetry endpoint path", "CORS preflight", "no response (blocked or aborted)"}
MAX_PRODUCERS = 50


def parse_time_ms(value: Any) -> Optional[float]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    # Python 3.10 accepts at most 6 fractional digits.
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        return datetime.fromisoformat(text).timestamp() * 1000
    except ValueError:
        return None


def site(host: str) -> str:
    """Approximate registrable domain so temporal links stay first-party."""
    labels = host.split(":", 1)[0].split(".")
    keep = 3 if len(labels) >= 3 and len(labels[-1]) == 2 and len(labels[-2]) <= 3 else 2
    return ".".join(labels[-keep:])


def value_kind(value: str, key: str) -> Optional[str]:
    """Classify a captured value as linkable, or None when it is too generic to link."""
    v = value.strip()
    if not v or len(v) > 4096:
        return None
    if v.startswith(("http://", "https://")):
        return "url"
    if har_probe.JWT_RE.fullmatch(v):
        return "jwt"
    if UUID_RE.fullmatch(v):
        return "uuid"
    if har_probe.DATE_RE.fullmatch(v) or har_probe.DATETIME_RE.fullmatch(v):
        return None
    if v.isdigit():
        # Epoch timestamps (s or ms) appear everywhere and would create false links.
        if har_probe.is_epoch(v):
            return None
        if len(v) >= 5 or (len(v) >= 3 and ID_KEY_RE.search(key)):
            return "numeric"
        return None
    if HEX_RE.fullmatch(v) and any(c.isdigit() for c in v):
        return "hex"
    if TOKEN_RE.fullmatch(v) and any(c.isdigit() for c in v) and any(c.isalpha() for c in v):
        return "token"
    if len(v) >= 4 and ID_KEY_RE.search(key) and re.fullmatch(r"[A-Za-z0-9_-]+", v) and any(c.isdigit() for c in v):
        return "token"
    return None


def walk_json(obj: Any, path: str = "$") -> Iterator[Tuple[str, str, Any]]:
    """Yield (location, last key, scalar) for JSON leaves."""
    if isinstance(obj, dict):
        items = [(f"{path}.{k}", str(k), v) for k, v in list(obj.items())[:500]]
    elif isinstance(obj, list):
        # Lookup lists (e.g. every town in a province) often hold the chosen key deep inside.
        items = [(f"{path}[]", "", v) for v in obj[:2000]]
    else:
        return
    for loc, key, v in items:
        if isinstance(v, (dict, list)):
            yield from walk_json(v, loc)
        else:
            yield loc, key, v


def url_values(url: str, prefix: str) -> Iterator[Tuple[str, str, str]]:
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    for i, seg in enumerate(segments):
        previous = segments[i - 1] if i else ""
        value = unquote(seg)
        # Only segments the probe would normalize as IDs; RPC names like ReadThing.v1 are not.
        if har_probe.normalize_path("/" + value) != "/" + value:
            yield f"{prefix}.path[{i}]", previous, value
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        if not CACHE_BUSTER_RE.match(k):
            yield f"{prefix}.query:{k}", k, v


def body_values(text: str, mime: str, params: Any, prefix: str) -> Iterator[Tuple[str, str, str]]:
    if isinstance(params, list) and params:
        for p in params[:500]:
            if isinstance(p, dict) and p.get("name") and p.get("value") is not None and not p.get("fileName"):
                yield f"{prefix}.form:{p['name']}", str(p["name"]), str(p["value"])
        return
    if not text:
        return
    if "x-www-form-urlencoded" in mime:
        for k, v in parse_qsl(text, keep_blank_values=False):
            yield f"{prefix}.form:{k}", k, v
        return
    parsed = har_probe.parse_json_maybe(text)
    if parsed is not None:
        for loc, key, v in walk_json(parsed):
            if isinstance(v, (str, int)) and not isinstance(v, bool):
                yield f"{prefix}.json:{loc}", key, str(v)
        return
    if "multipart/form-data" in mime:
        for name, v in re.findall(r'name="([^"\r\n]+)"\r?\n\r?\n([^\r\n]{1,512})', text):
            yield f"{prefix}.form:{name}", name, v


def html_values(text: str) -> Iterator[Tuple[str, str, str]]:
    for tag_re, label in ((HIDDEN_INPUT_RE, "input"), (META_RE, "meta")):
        for tag in tag_re.findall(text)[:500]:
            attrs = {m[0].lower(): m[1] or m[2] for m in ATTR_RE.findall(tag)}
            name = attrs.get("name") or attrs.get("id") or attrs.get("property") or ""
            value = attrs.get("value") if label == "input" else attrs.get("content")
            if name and value:
                yield f"response.html:{label}[{name}]", name, value
    unescaped = text.replace('\\"', '"')
    for key, value in INLINE_PAIR_RE.findall(unescaped)[:2000]:
        if ID_KEY_RE.search(key) or TOKEN_KEY_RE.search(key):
            yield f"response.html:script[{key}]", key, value
    for m in list(UUID_RE.finditer(text))[:200]:
        yield "response.html:uuid", "", m.group(0)


class Graph:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.seeds = set(har_probe.parse_indices(args.indices)) if args.indices else None
        self.salt = os.urandom(16)
        self.meta: Dict[int, Dict[str, Any]] = {}
        self.producers: Dict[str, List[Tuple[float, int, str, str, str]]] = defaultdict(list)
        self.consumers: Dict[int, List[Tuple[str, str, str, str]]] = {}
        self.url_index: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        self.request_fanout: Counter[str] = Counter()
        self.referers: Dict[int, str] = {}
        self.redirects: Dict[int, str] = {}
        self.coverage: Dict[str, Any] = {
            "selection": "explicit indices" if self.seeds is not None else "heuristic ranking",
            "requests": 0,
            "candidates": 0,
            "excluded_reasons": Counter(),
            "missing_timestamps": 0,
            "response_scans_skipped": 0,
            "response_scans_truncated": 0,
            "max_scan_chars": args.max_scan_chars,
        }

    def fp(self, value: str) -> str:
        return hmac.new(self.salt, value.encode("utf-8", "replace"), hashlib.sha256).hexdigest()[:10]

    def ingest(self, idx: int, entry: Dict[str, Any]) -> None:
        c = har_probe.compact_entry(entry, idx)
        score, reasons = har_probe.candidate_score(c)
        req = har_probe.as_dict(entry.get("request"))
        res = har_probe.as_dict(entry.get("response"))
        url = str(req.get("url", ""))
        t = parse_time_ms(entry.get("startedDateTime"))
        if self.seeds is not None:
            is_candidate = idx in self.seeds
        else:
            is_candidate = score >= self.args.min_score and not NOISE_REASONS.intersection(reasons)
        self.coverage["requests"] += 1
        self.coverage["candidates"] += int(is_candidate)
        self.coverage["missing_timestamps"] += int(t is None)
        if not is_candidate:
            excluded = ["outside explicit indices"] if self.seeds is not None else sorted(NOISE_REASONS.intersection(reasons)) or ["below score threshold"]
            self.coverage["excluded_reasons"].update(excluded)
        self.meta[idx] = {
            "index": idx,
            "t": t if t is not None else float(idx),
            "method": c["method"],
            "status": c["status"],
            "host": c["url"]["host"],
            "endpoint": c["url"]["normalized"],
            "resourceType": c.get("resourceType") or "",
            "score": score,
            "candidate": is_candidate,
            "req_mime": c["request"]["content_type"],
            "res_mime": c["response"]["mime"],
            "url": url.split("#", 1)[0],
        }
        noise = score < 0
        self.url_index[self.meta[idx]["url"]].append((self.meta[idx]["t"], idx))

        headers = dict(har_probe.header_pairs(req.get("headers")))
        if headers.get("referer"):
            self.referers[idx] = headers["referer"].split("#", 1)[0]
        res_headers = har_probe.header_pairs(res.get("headers"))
        location = str(res.get("redirectURL") or next((v for n, v in res_headers if n == "location"), ""))
        if location:
            location = urljoin(url, location)
            self.redirects[idx] = location.split("#", 1)[0]

        # Request side: what this request sends.
        consumed: List[Tuple[str, str, str, str]] = []
        post = har_probe.as_dict(req.get("postData"))
        values: List[Tuple[str, str, str]] = list(url_values(url, "request"))
        for name, value in headers.items():
            if name not in SKIP_REQUEST_HEADERS and not name.startswith("sec-"):
                if name == "authorization":
                    value = re.sub(r"(?i)^(bearer|token|basic)\s+", "", value)
                values.append((f"request.header:{name}", name, value))
        values.extend(body_values(str(post.get("text") or ""), str(post.get("mimeType") or ""), post.get("params"), "request"))
        seen: Set[str] = set()
        for loc, key, value in values:
            # Short keys (e.g. L219) link only when a response handed them out; see build().
            kind = value_kind(value, key) or ("short" if SHORT_ID_RE.fullmatch(value) else None)
            if not kind or kind == "url":
                continue
            f = self.fp(value)
            if f not in seen:
                seen.add(f)
                if not noise:
                    self.request_fanout[f] += 1
                consumed.append((f, kind, loc, key))
        if is_candidate:
            self.consumers[idx] = consumed

        # Response side: what this response hands out.
        if noise or har_probe.STATIC_EXT_RE.search(urlparse(url).path):
            self.coverage["response_scans_skipped"] += 1
            return
        content = har_probe.as_dict(res.get("content"))
        mime = str(content.get("mimeType") or "").lower()
        text = har_probe.maybe_decode_content(content)
        self.coverage["response_scans_truncated"] += int(len(text) > self.args.max_scan_chars)
        text = text[: self.args.max_scan_chars]
        produced: List[Tuple[str, str, str]] = []
        if "json" in mime or text.lstrip()[:1] in ("[", "{"):
            produced.extend(body_values(text, "application/json", None, "response"))
        elif "html" in mime:
            produced.extend(html_values(text))
        if location:
            produced.extend(url_values(location, "response.location"))
        for name, value in res_headers:
            if name == "set-cookie":
                cookie_name, _, rest = value.partition("=")
                produced.append((f"response.set-cookie:{cookie_name.strip()}", cookie_name.strip(), rest.split(";", 1)[0]))
            elif name.startswith("x-") or TOKEN_KEY_RE.search(name):
                produced.append((f"response.header:{name}", name, value))
        seen.clear()
        for loc, key, value in produced:
            kind = value_kind(value, key)
            if not kind:
                continue
            target = value.split("#", 1)[0] if kind == "url" else value
            f = self.fp(target)
            if f in seen or len(self.producers[f]) >= MAX_PRODUCERS:
                continue
            seen.add(f)
            self.producers[f].append((self.meta[idx]["t"], idx, loc, key, kind))

    @staticmethod
    def latest_before(items: Iterable[Tuple[Any, ...]], t: float, idx: int) -> Optional[Tuple[Any, ...]]:
        """The latest (t, idx, ...) item strictly before (t, idx)."""
        return max((item for item in items if item[:2] < (t, idx)), default=None)

    def edge_kind(self, src: int, kind: str, src_key: str, dst_loc: str, dst_key: str) -> str:
        keys = f"{src_key} {dst_key} {dst_loc}"
        if kind == "url":
            return "signed-url"
        if UPLOAD_KEY_RE.search(keys):
            return "upload-id"
        if kind == "jwt" or TOKEN_KEY_RE.search(keys) or dst_loc == "request.header:authorization":
            return "token"
        m = self.meta[src]
        if m["method"] in MUTATING and 200 <= m["status"] < 400:
            return "created-id"
        return "response-id"

    def build(self) -> Dict[str, Any]:
        edges: Dict[Tuple[int, int, str], List[Dict[str, str]]] = defaultdict(list)

        def add(src: int, dst: int, kind: str, evidence: Dict[str, str]) -> None:
            bucket = edges[(src, dst, kind)]
            if len(bucket) < 5:
                bucket.append(evidence)

        candidates = sorted((i for i in self.meta if self.meta[i]["candidate"]), key=lambda i: (self.meta[i]["t"], i))
        last_user: Dict[str, int] = {}
        for idx in candidates:
            m = self.meta[idx]
            t = m["t"]
            for f, kind, loc, key in self.consumers.get(idx, []):
                if self.request_fanout[f] > self.args.max_fanout:
                    continue
                producer = self.latest_before(self.producers.get(f, []), t, idx)
                if producer:
                    _, src, src_loc, src_key, _ = producer
                    add(src, idx, self.edge_kind(src, kind, src_key, loc, key), {"value": kind, "fp": f, "from": src_loc, "to": loc})
                elif f in last_user and kind != "short" and not loc.startswith("request.header:"):
                    # Constant client headers are session-wide, not shared resources.
                    add(last_user[f], idx, "shared-id", {"value": kind, "fp": f, "to": loc})
                last_user[f] = idx
            # Signed or handed-out URLs requested later.
            for target in dict.fromkeys((m["url"], m["url"].split("?", 1)[0])):
                f = self.fp(target)
                producer = self.latest_before(self.producers.get(f, []), t, idx)
                if producer:
                    location = "request.url" if target == m["url"] else "request.url (without query)"
                    add(producer[1], idx, "signed-url", {"value": "url", "fp": f, "from": producer[2], "to": location})
                    break
            ref = self.referers.get(idx)
            referer = self.latest_before(self.url_index.get(ref, []), t, idx) if ref else None
            if referer:
                add(referer[1], idx, "referer", {"to": "request.header:referer"})
        for src, target in self.redirects.items():
            items = self.url_index.get(target, [])
            dst = next((i for ti, i in sorted(items) if (ti, i) > (self.meta[src]["t"], src)), None)
            if dst is not None and (self.meta[src]["candidate"] or self.meta[dst]["candidate"]):
                add(src, dst, "redirect", {"to": "request.url"})

        # Timestamp proximity for consecutive same-site candidates.
        by_site: Dict[str, List[int]] = defaultdict(list)
        for idx in candidates:
            by_site[site(self.meta[idx]["host"])].append(idx)
        for members in by_site.values():
            for a, b in zip(members, members[1:]):
                gap = self.meta[b]["t"] - self.meta[a]["t"]
                if 0 <= gap <= self.args.gap_ms:
                    add(a, b, "temporal", {"gap_ms": str(round(gap))})

        # Repeated calls to one endpoint (status polling) stay in the same workflow.
        previous: Dict[Tuple[str, str], int] = {}
        for idx in candidates:
            key = (self.meta[idx]["method"], self.meta[idx]["endpoint"])
            if key in previous and self.meta[idx]["t"] - self.meta[previous[key]]["t"] <= self.args.repeat_ms:
                add(previous[key], idx, "repeat", {"gap_ms": str(round(self.meta[idx]["t"] - self.meta[previous[key]]["t"]))})
            previous[key] = idx

        nodes = set(candidates)
        for src, dst, _ in edges:
            nodes.update((src, dst))
        return self.workflows(sorted(nodes, key=lambda i: (self.meta[i]["t"], i)), edges)

    def workflows(self, nodes: List[int], edges: Dict[Tuple[int, int, str], List[Dict[str, str]]]) -> Dict[str, Any]:
        parent = {n: n for n in nodes}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for (src, dst, kind) in edges:
            if kind in GROUPING_KINDS:
                parent[find(src)] = find(dst)
        groups: Dict[int, List[int]] = defaultdict(list)
        for n in nodes:
            groups[find(n)].append(n)

        t0 = min((self.meta[n]["t"] for n in nodes), default=0)
        incoming: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
        outgoing: Dict[int, Set[str]] = defaultdict(set)
        for (src, dst, kind) in edges:
            incoming[dst].append((src, kind))
            outgoing[src].add(kind)

        ranked: List[Tuple[Tuple[bool, bool, int, int], Dict[str, Any]]] = []
        for members in groups.values():
            members.sort(key=lambda i: (self.meta[i]["t"], i))
            kinds = Counter(k for (s, d, k) in edges if s in members and d in members)
            # Prefer the request that starts a chain over continuations that reuse its created/upload IDs.
            primary = max(members, key=lambda i: (
                self.meta[i]["method"] in MUTATING,
                not {k for _, k in incoming[i]} & {"created-id", "upload-id"},
                bool(({k for _, k in incoming[i]} | outgoing[i]) & STRONG_KINDS),
                self.meta[i]["score"],
                -self.meta[i]["t"],
            ))
            hosts = Counter(self.meta[i]["host"] for i in members)
            app_host = hosts.most_common(1)[0][0]
            endpoint_counts = Counter((self.meta[i]["method"], self.meta[i]["endpoint"]) for i in members)
            steps = []
            for i in members:
                m = self.meta[i]
                in_kinds = {k for _, k in incoming[i]}
                if i == primary:
                    role = "primary-action"
                elif m["host"] != app_host and m["method"] in {"PUT", "POST"} and in_kinds & {"signed-url", "upload-id"}:
                    role = "storage-upload"
                elif m["method"] == "GET" and endpoint_counts[(m["method"], m["endpoint"])] >= 3 and m["t"] > self.meta[primary]["t"]:
                    role = "poll"
                elif outgoing[i] & {"token"} and not in_kinds & STRONG_KINDS:
                    role = "token-source"
                elif m["t"] > self.meta[primary]["t"] and in_kinds & {"created-id", "upload-id", "redirect"}:
                    role = "follow-up"
                elif not m["candidate"]:
                    role = "source"
                else:
                    role = "step"
                steps.append({
                    "index": i,
                    "t_ms": round(m["t"] - t0),
                    "t_rel_ms": round(m["t"] - self.meta[primary]["t"]),
                    "method": m["method"],
                    "status": m["status"],
                    "endpoint": m["endpoint"],
                    "score": m["score"],
                    "role": role,
                    "links_in": sorted({f"{k}<-{s}" for s, k in incoming[i] if s in members}),
                })
            strong = sum(v for k, v in kinds.items() if k in STRONG_KINDS)
            workflow: Dict[str, Any] = {
                "nodes": len(members),
                "start_ms": steps[0]["t_ms"],
                "end_ms": steps[-1]["t_ms"],
                "primary_index": primary,
                "evidence": "linked" if strong else "temporal-only",
                "edge_kinds": dict(kinds),
                "steps": steps,
            }
            ranked.append(((strong > 0, self.meta[primary]["method"] in MUTATING, self.meta[primary]["score"], strong), workflow))
        ranked.sort(key=lambda r: r[0], reverse=True)
        workflows = [w for _, w in ranked]
        for i, w in enumerate(workflows, 1):
            w["id"] = f"wf{i}"
        return {
            "coverage": self.coverage,
            "notes": [
                "Workflow groups, primary indices, roles and edge kinds are heuristic suggestions.",
                "Equal fingerprints identify matching values within this run; equality does not prove dependency or token lifetime.",
                "Matching samples fields and arrays, filters generic/high-fanout values, and may miss unsupported body formats.",
                "Missing timestamps use request order as a fallback; relative times involving them are unreliable.",
            ],
            "nodes": len(nodes),
            "edges": [
                {"from": s, "to": d, "kind": k, "evidence": ev}
                for (s, d, k), ev in sorted(edges.items(), key=lambda e: (self.meta[e[0][1]]["t"], e[0][1], e[0][0]))
            ],
            "workflows": workflows,
        }


def fmt_rel(ms: int) -> str:
    return f"{ms / 1000:+.1f}" if ms else "0.0"


def primary_step(w: Dict[str, Any]) -> Dict[str, Any]:
    return next(s for s in w["steps"] if s["index"] == w["primary_index"])


def render_workflow(w: Dict[str, Any], link_kinds: Optional[Set[str]] = None) -> List[str]:
    """One workflow as a table; times are seconds relative to its primary action."""
    kinds = ", ".join(f"{k}:{v}" for k, v in sorted(w["edge_kinds"].items())) or "none"
    primary = primary_step(w)
    lines = [
        f"## {w['id']}: candidate #{w['primary_index']} {primary['method']} {primary['endpoint']} ({w['evidence']})",
        "",
        f"{w['nodes']} requests over {(w['end_ms'] - w['start_ms']) / 1000:.1f}s; edges {kinds}",
        "",
        "<!-- prettier-ignore -->",
        "| idx | s vs candidate | method | status | endpoint | role hint | links in |",
        "|-|-|-|-|-|-|-|",
    ]
    previous = None
    repeats = 0
    for s in w["steps"]:
        key = (s["method"], s["endpoint"], s["role"])
        if key == previous and s["role"] == "poll":
            repeats += 1
            continue
        if repeats:
            lines.append(f"| | | | | ...repeated {repeats}x | poll | |")
            repeats = 0
        previous = key
        links = [link for link in s["links_in"] if link_kinds is None or link.split("<-", 1)[0] in link_kinds]
        lines.append(f"| {s['index']} | {fmt_rel(s['t_rel_ms'])} | {s['method']} | {s['status']} | {s['endpoint']} | {s['role']} | {' '.join(links) or '-'} |")
    if repeats:
        lines.append(f"| | | | | ...repeated {repeats}x | poll | |")
    lines.append("")
    return lines


def render_markdown(graph: Dict[str, Any], top: int) -> str:
    lines = [
        "# Workflow sequence graph",
        "",
        f"{graph['nodes']} nodes, {len(graph['edges'])} edges, {len(graph['workflows'])} workflows. "
        "Roles and links are heuristics; confirm against extracted request details.",
        "",
    ]
    for w in [w for w in graph["workflows"] if w["nodes"] > 1][:top]:
        lines += render_workflow(w)
    singles = [w["steps"][0] for w in graph["workflows"] if w["nodes"] == 1]
    if singles:
        lines += ["## Unlinked candidates", ""]
        lines += [f"- #{s['index']} +{s['t_ms']}ms {s['method']} {s['status']} {s['endpoint']} (score {s['score']})" for s in singles[: top * 3]]
        lines.append("")
    return "\n".join(lines)


def write_graph(graph: Dict[str, Any], out: Path, top: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "workflow.md").write_text(render_markdown(graph, top), encoding="utf-8")


def add_graph_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--indices", help="Seed request indices/ranges (e.g. 40-75). Default: candidates by score.")
    parser.add_argument("--min-score", type=int, default=25, help="Candidate score threshold when --indices is omitted (default: 25)")
    parser.add_argument("--gap-ms", type=int, default=3000, help="Link consecutive candidates closer than this (default: 3000)")
    parser.add_argument("--repeat-ms", type=int, default=120000, help="Link repeat calls to one endpoint within this window (default: 120000)")
    parser.add_argument("--max-fanout", type=int, default=8, help="Ignore values sent by more than this many requests (default: 8)")
    parser.add_argument("--max-scan-chars", type=int, default=2_000_000, help="Max response chars scanned per entry (default: 2000000)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a workflow sequence graph from likely user-action requests in a HAR.")
    parser.add_argument("har", help="Path to .har file")
    parser.add_argument("--out", required=True, help="Output directory for graph.json and workflow.md")
    add_graph_args(parser)
    parser.add_argument("--top", type=int, default=10, help="Workflows rendered in workflow.md (default: 10)")
    args = parser.parse_args(argv)
    try:
        g = Graph(args)
        for idx, entry in enumerate(har_probe.iter_har_entries(Path(args.har))):
            g.ingest(idx, entry)
        graph = g.build()
        outdir = Path(args.out)
        write_graph(graph, outdir, args.top)
        linked = [w["id"] for w in graph["workflows"] if w["evidence"] == "linked"]
        print(json.dumps({
            "ok": True,
            "graph_json": str(outdir / "graph.json"),
            "workflow_md": str(outdir / "workflow.md"),
            "nodes": graph["nodes"],
            "edges": len(graph["edges"]),
            "workflows": len(graph["workflows"]),
            "linked_workflows": linked[:10],
        }))
    except BrokenPipeError:
        return 0
    except Exception as exc:
        har_probe.eprint(f"Error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
