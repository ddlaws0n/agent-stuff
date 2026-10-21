#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ijson>=3.2,<4",
# ]
# ///
"""One-pass HAR brief: workflow graph, capture facts, field kinds, and a verdict hint.

Usage:
  uv run scripts/har_brief.py session.har --out har-analysis
  uv run scripts/har_brief.py session.har --out har-analysis --indices 40-75

Prints a capped markdown brief (also written to brief.md) and writes graph.json and
workflow.md. Like har_graph.py it never emits captured values: fields are described
by kind (date, uuid, word, ...), headers and cookies by name.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import har_graph  # noqa: E402  # ty: ignore[unresolved-import]
import har_probe  # noqa: E402  # ty: ignore[unresolved-import]

CSRF_RE = re.compile(r"(?i)(csrf|xsrf|authenticity[-_]?token|requestverificationtoken|anti[-_]?forgery)")
# Interactive challenges block plain HTTP clients outright.
CHALLENGE_RE = re.compile(
    r"(?i)(recaptcha|hcaptcha|captcha|turnstile|challenges\.cloudflare\.com|/cdn-cgi/challenge|arkoselabs|funcaptcha|geetest|friendlycaptcha)"
)
# Bot-management sensors may reject scripted clients without showing a challenge.
BOT_MANAGEMENT_RE = re.compile(
    r"(?i)^(_abck|bm_sz|ak_bmsc|bm_sv|__cf_bm|cf_clearance|_px\w*|datadome|incap_ses\w*|visid_incap\w*|reese84|x-kpsdk-\w+|x-px-\w+|x-datadome\w*|x-acf-sensor-data)$"
)
BOT_HOST_RE = re.compile(r"(?i)(perimeterx|px-cdn|px-cloud|datadome|kasada|incapsula|imperva)")
OPAQUE_VALUES = {"uuid", "token", "jwt", "hex", "url"}
VALUE_LABELS = {"short": "short key", "numeric": "numeric key"}
# Links worth confirming with `show`; shared-id and timing links are weaker hints.
DRILL_KINDS = {"token", "created-id", "upload-id", "signed-url", "response-id", "redirect"}
STANDARD_REQUEST_HEADERS = har_graph.SKIP_REQUEST_HEADERS | {"authorization", "x-requested-with"}


class Facts:
    """Capture-wide facts, including what is absent, plus field kinds per candidate."""

    def __init__(self, graph: har_graph.Graph) -> None:
        self.graph = graph
        self.total = 0
        self.hosts: Counter[str] = Counter()
        self.cookie_requests = 0
        self.cookie_names: Set[str] = set()
        self.set_cookie_names: Set[str] = set()
        self.auth_schemes: Counter[str] = Counter()
        self.csrf: Dict[str, List[int]] = defaultdict(list)
        self.custom_headers: Counter[str] = Counter()
        self.challenges: Dict[str, List[int]] = defaultdict(list)
        self.bot_signals: Dict[str, List[int]] = defaultdict(list)
        self.streams: List[int] = []
        self.candidates = 0
        self.missing_bodies: List[int] = []
        self.req_fields: Dict[int, Dict[str, str]] = {}
        self.res_fields: Dict[int, Dict[str, str]] = {}
        self.req_prints: Dict[int, Dict[str, str]] = {}
        self.headers: Dict[int, List[str]] = {}

    def add(self, idx: int, entry: Dict[str, Any]) -> None:
        meta = self.graph.meta[idx]
        req = har_probe.as_dict(entry.get("request"))
        res = har_probe.as_dict(entry.get("response"))
        url = str(req.get("url", ""))
        self.total += 1
        self.hosts[meta["host"]] += 1

        pairs = har_probe.header_pairs(req.get("headers"))
        values = dict(pairs)
        custom = [n for n, _ in pairs if n and n not in STANDARD_REQUEST_HEADERS and not n.startswith(("sec-", ":"))]
        cookies = [p.split("=", 1)[0].strip() for p in values.get("cookie", "").split(";") if p.strip()]
        cookies += [str(c.get("name")) for c in req.get("cookies") or [] if isinstance(c, dict) and c.get("name")]
        if cookies:
            self.cookie_requests += 1
            self.cookie_names.update(cookies)
        res_headers = har_probe.header_pairs(res.get("headers"))
        set_cookies = {v.split("=", 1)[0].strip() for n, v in res_headers if n == "set-cookie"}
        self.set_cookie_names.update(set_cookies)
        if values.get("authorization"):
            scheme = values["authorization"].strip().split(" ", 1)
            self.auth_schemes[scheme[0] if len(scheme) == 2 else "credential"] += 1

        post = har_probe.as_dict(req.get("postData"))
        fields = har_probe.body_shapes(post)
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
        for name in list(values) + list(fields) + list(query):
            if CSRF_RE.search(name) and len(self.csrf[name]) < 5:
                self.csrf[name].append(idx)
        for name in set(cookies) | set(values) | set_cookies:
            if BOT_MANAGEMENT_RE.match(name) and len(self.bot_signals[name]) < 5:
                self.bot_signals[name].append(idx)
        if BOT_HOST_RE.search(meta["host"]):
            self.bot_signals[meta["host"]].append(idx)
        if CHALLENGE_RE.search(url):
            self.challenges[meta["endpoint"]].append(idx)
        if any(n == "cf-mitigated" for n, _ in res_headers):
            self.challenges["cf-mitigated response header"].append(idx)
        mime = meta["res_mime"].lower()
        if meta["resourceType"].lower() == "websocket" or "event-stream" in mime or entry.get("_webSocketMessages"):
            self.streams.append(idx)

        if not meta["candidate"] and meta["score"] < 0:
            return
        text = har_probe.maybe_decode_content(har_probe.as_dict(res.get("content")))
        if meta["candidate"]:
            self.candidates += 1
            if not text and meta["status"] != 204 and not 300 <= meta["status"] < 400:
                self.missing_bodies.append(idx)
            self.custom_headers.update(custom)
        self.headers[idx] = custom
        self.req_fields[idx] = {**{f"?{k}": v for k, v in har_probe.query_shapes(url).items()}, **fields}
        parsed = har_probe.parse_json_maybe(text[: self.graph.args.max_scan_chars])
        if parsed is not None:
            self.res_fields[idx] = har_probe.json_shapes(parsed, limit=30)
        prints = {f"?{k}": self.graph.fp(v) for k, v in query.items()}
        prints.update({loc.split(":", 1)[1].removeprefix("$."): self.graph.fp(v) for loc, _, v in har_graph.body_values(
            str(post.get("text") or ""), str(post.get("mimeType") or ""), post.get("params"), "request")})
        self.req_prints[idx] = prints


def workflow_edges(graph: Dict[str, Any], w: Dict[str, Any]) -> List[Dict[str, Any]]:
    members = {s["index"] for s in w["steps"]}
    return [e for e in graph["edges"] if e["from"] in members and e["to"] in members]


def verdict_hint(graph: Dict[str, Any], facts: Facts) -> Tuple[str, List[str]]:
    """Apply the skill's decision rules to graph and capture facts. A starting point, not a verdict."""
    reasons: List[str] = []
    if facts.challenges:
        signals = ", ".join(f"{k} (#{v[0]})" for k, v in list(facts.challenges.items())[:3])
        return "browser-assisted or manual-only/blocked", [f"interactive challenge signals: {signals}"]
    if not graph["workflows"]:
        return "insufficient-evidence", ["no candidate action requests; rerun with --indices around the user's action"]
    top = graph["workflows"][0]
    primary = har_graph.primary_step(top)
    if primary["status"] == 0 or primary["status"] >= 400:
        reasons.append(f"primary #{top['primary_index']} returned status {primary['status']}")
    flows: Dict[Tuple[bool, int, str, str, str], List[int]] = defaultdict(list)
    for e in workflow_edges(graph, top):
        if e["kind"] in ("temporal", "repeat", "referer", "redirect", "shared-id"):
            continue
        ev = e["evidence"][0]
        is_opaque = e["kind"] in ("token", "signed-url", "upload-id") or ev.get("value") in OPAQUE_VALUES
        flows[(is_opaque, e["from"], str(ev.get("value")), str(ev.get("from")), str(ev.get("to")))].append(e["to"])
    opaque, stable = [], []
    for (is_opaque, src, value, src_loc, dst_loc), dsts in flows.items():
        line = f"#{', #'.join(map(str, dsts))} {'sends' if len(dsts) == 1 else 'send'} a {VALUE_LABELS.get(value, value)} from #{src} ({src_loc} -> {dst_loc})"
        (opaque if is_opaque else stable).append(line)
    if reasons:
        verdict = "insufficient-evidence"
    elif opaque:
        verdict = "http-with-token-refresh"
        reasons.append("server-generated values from earlier responses feed later requests:")
        reasons += [f"  {line}" for line in opaque[:4]]
    else:
        verdict = "direct-http"
        if stable:
            reasons.append("only stable lookup keys (short/numeric) flow between steps:")
            reasons += [f"  {line}" for line in stable[:3]]
        else:
            reasons.append("no values flow from earlier responses into the primary action")
    if top["primary_index"] in facts.missing_bodies:
        reasons.append(f"caveat: primary #{top['primary_index']} has no response body in the capture")
    if top["evidence"] == "temporal-only":
        reasons.append("low confidence: the top workflow is linked only by timing")
    if facts.bot_signals:
        reasons.append(f"risk: bot-management signals ({', '.join(list(facts.bot_signals)[:4])}) may reject scripted clients")
    if facts.streams:
        reasons.append(f"WebSocket/SSE traffic (#{facts.streams[0]}) may not be fully captured")
    return verdict, reasons


def fact_lines(facts: Facts) -> List[str]:
    def where(d: Dict[str, List[int]]) -> str:
        return ", ".join(f"{k} (#{','.join(map(str, v[:3]))})" for k, v in list(d.items())[:5])

    if facts.cookie_requests:
        cookies = f"Cookie on {facts.cookie_requests}/{facts.total} requests; names: {', '.join(sorted(facts.cookie_names)[:10])}"
    else:
        cookies = ("none in capture (no Cookie headers or HAR cookies). If the site needs login, the export probably dropped them: "
                   "treat the session as user-supplied and don't invent cookie names")
    return [
        f"- Cookies: {cookies}",
        f"- Set-Cookie: {', '.join(sorted(facts.set_cookie_names)[:10]) or 'none'}",
        "- Authorization header: " + (", ".join(f"{k} on {v} requests" for k, v in facts.auth_schemes.items()) or "none"),
        f"- CSRF/XSRF values: {where(facts.csrf) or 'none in headers, query, or bodies'}",
        "- Custom request headers on candidates: " + (", ".join(f"{k} ({v})" for k, v in facts.custom_headers.most_common(8)) or "none"),
        f"- Captcha/challenge signals: {where(facts.challenges) or 'none detected'}",
        f"- Bot-management signals: {where(facts.bot_signals) or 'none detected'}",
        f"- Candidate response bodies: {facts.candidates - len(facts.missing_bodies)}/{facts.candidates} present"
        + (f"; missing #{', #'.join(map(str, facts.missing_bodies[:8]))}: don't infer their content" if facts.missing_bodies else ""),
        f"- WebSocket/SSE: {'#' + ', #'.join(map(str, facts.streams[:5])) if facts.streams else 'none'}",
    ]


def differing_fields(w: Dict[str, Any], facts: Facts) -> List[str]:
    """For repeated calls to one endpoint, name the fields whose values differ (values stay hidden)."""
    groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for s in w["steps"]:
        if s["role"] != "poll":
            groups[(s["method"], s["endpoint"])].append(s["index"])
    lines = []
    for (method, endpoint), members in groups.items():
        if not 2 <= len(members) <= 6:
            continue
        prints = [facts.req_prints.get(i, {}) for i in members]
        keys = sorted({k for p in prints for k in p})
        differ = [k for k in keys if len({p.get(k) for p in prints}) > 1]
        what = f"differ in {', '.join(differ[:8])}" if differ else "send identical fields"
        lines.append(f"- #{', #'.join(map(str, members))} {method} {endpoint}: {what}")
    return lines


def render_brief(graph: Dict[str, Any], facts: Facts, har: Path, out: Path, top: int, max_chars: int) -> str:
    app_host = facts.hosts.most_common(1)[0][0] if facts.hosts else "-"
    head = [
        f"# HAR brief: {har.name}",
        "",
        f"{facts.total} requests across {len(facts.hosts)} hosts (most: {app_host}); {facts.candidates} action candidates. "
        f"Outputs in {out}: brief.md, workflow.md, graph.json. Links and roles are heuristics; no captured values are shown.",
        "",
        "## Capture facts",
        "",
        *fact_lines(facts),
        "",
    ]
    verdict, reasons = verdict_hint(graph, facts)
    head += [f"## Verdict hint: {verdict}", "", *[f"- {r}" if not r.startswith("  ") else f"  - {r.strip()}" for r in reasons],
             "", "Rule-based starting point: confirm with `show`, and say why if your verdict differs.", ""]
    body: List[str] = []
    multi = [w for w in graph["workflows"] if w["nodes"] > 1]
    # Full tables for linked workflows; timing-only groups are usually page chatter.
    full = [w for w in multi if w["evidence"] == "linked"][:top] or multi[:1]
    for w in full:
        body += har_graph.render_workflow(w, link_kinds=har_graph.STRONG_KINDS | {"repeat"})
        p = w["primary_index"]
        if facts.req_fields.get(p):
            body.append(f"Primary #{p} sends: {har_probe.format_shapes(facts.req_fields[p], 15)}")
        if facts.headers.get(p):
            body.append(f"Primary #{p} custom headers: {', '.join(facts.headers[p][:8])}")
        if facts.res_fields.get(p):
            body.append(f"Primary #{p} returns: {har_probe.format_shapes(facts.res_fields[p], 8)}")
        body += differing_fields(w, facts)
        body.append("")
    if rest := [w for w in multi if w not in full]:
        body += ["## Other workflows", ""]
        for w in rest[:5]:
            p = har_graph.primary_step(w)
            body.append(f"- {w['id']}: primary #{p['index']} {p['method']} {p['endpoint']}, {w['nodes']} requests ({w['evidence']})")
        body.append("")
    singles = [w["steps"][0] for w in graph["workflows"] if w["nodes"] == 1]
    if singles:
        body += ["## Unlinked candidates", ""]
        body += [f"- #{s['index']} {s['method']} {s['status']} {s['endpoint']} (score {s['score']})" for s in singles[:5]]
        body.append("")
    drill: Set[int] = set()
    if graph["workflows"]:
        drill.add(graph["workflows"][0]["primary_index"])
        drill.update(i for e in workflow_edges(graph, graph["workflows"][0]) if e["kind"] in DRILL_KINDS for i in (e["from"], e["to"]))
    tail = [f"Next: `har_probe.py show {har} --indices {','.join(map(str, sorted(drill)[:6]))}` for headers and field kinds of key steps."] if drill else []
    text = "\n".join(head + body + tail)
    if len(text) > max_chars:
        note = "\n\n(brief truncated; see workflow.md for every workflow)\n" + "\n".join(tail)
        text = "\n".join(head + body)[: max(0, max_chars - len(note) - 1)].rsplit("\n", 1)[0] + note
    return text + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize a HAR into a capped brief: workflows, capture facts, field kinds, verdict hint.")
    parser.add_argument("har", help="Path to .har file")
    parser.add_argument("--out", required=True, help="Output directory for brief.md, graph.json, and workflow.md")
    har_graph.add_graph_args(parser)
    parser.add_argument("--top", type=int, default=2, help="Workflows shown in full in the brief (default: 2)")
    parser.add_argument("--max-chars", type=int, default=5000, help="Brief length cap in characters (default: 5000)")
    args = parser.parse_args(argv)
    try:
        har = Path(args.har)
        g = har_graph.Graph(args)
        facts = Facts(g)
        for idx, entry in enumerate(har_probe.iter_har_entries(har)):
            g.ingest(idx, entry)
            facts.add(idx, entry)
        graph = g.build()
        out = Path(args.out)
        har_graph.write_graph(graph, out, 10)
        brief = render_brief(graph, facts, har, out, args.top, args.max_chars)
        (out / "brief.md").write_text(brief, encoding="utf-8")
        print(brief, end="")
    except BrokenPipeError:
        return 0
    except Exception as exc:
        har_probe.eprint(f"Error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
