---
name: analyze-har-workflows
description: >-
  Analyzes HAR captures to reconstruct website actions, captured workflow
  definitions, configuration, and job evidence, and assess automation. Use when
  the user provides HAR files or DevTools network exports to investigate API
  calls, forms, uploads, settings, or workflow structure. Extracts bounded,
  privacy-conscious evidence before reasoning.
  Do not use for live browser automation or scraping without a capture.
license: MIT
compatibility: >-
  Requires Python 3.10+. uv is recommended for streaming large HARs via the
  bundled scripts' ijson dependency; Python alone supports small HARs.
metadata:
  author: ddlaws0n
  version: "0.5.0"
---

# HAR workflow analysis

Explain the captured action or workflow structure and assess the requested automation. The scripts reduce traffic to bounded evidence; use the user's task and that evidence to interpret the workflow.

## Workflow

1. Establish the action and expected result from the prompt. Ask only when missing context prevents identifying the relevant traffic.
2. For traffic triage, use the brief below, then follow promising requests and relationships with `show`. Rankings, workflow groups, roles, and link kinds are navigation hints. For stored definitions, configuration, or execution history, read `references/workflow-definitions.md` and inspect the relevant bodies; GET responses may contain the primary evidence without a captured mutation.
3. Develop an evidence-backed explanation. Distinguish observations, inferences, and unknowns; cite request indices for material claims. A matching value supports a possible relationship, but its shape does not establish its purpose or lifetime. Missing links or challenge signals do not establish replayability.
4. Before synthesizing multiple captures, compare their available job/dependency evidence, not just one example per file. Validate material claims and proposed edit locations against exact source paths; resolve contradictory evidence or label it unknown. Answer when the evidence supports a useful explanation, or identify the specific gap preventing one. Expand only the evidence needed to resolve uncertainty; `references/deep-dive.md` describes additional inspection tools.

## Scripts

Run commands relative to this skill's directory. Keep outputs in a private directory outside shared repositories:

```bash
ANALYSIS_DIR="$(mktemp -d)"
uv run scripts/har_brief.py /path/to/session.har --out "$ANALYSIS_DIR"
uv run scripts/har_probe.py show /path/to/session.har --indices 12,18
```

- `scripts/har_brief.py` streams the capture once, prints a brief capped at 5000 characters, and saves `brief.md`, `workflow.md`, and `graph.json`. It includes capture-wide facts, selection/scan coverage, candidate workflows, field shapes, matching-value placeholders, and differences between repeated calls. `--indices 40-75` selects graph candidates; capture-wide facts still cover all requests.
- `scripts/har_probe.py show` inspects selected requests with headers, field kinds, and response shapes, capped at 1500 characters per request. Use `--value-ids` to compare query/body values through opaque placeholders (for example, whether a submitted title matches a later response). IDs are comparable within that command only, separately from graph fingerprints. Increase `--max-chars` if details are truncated. `summarize` and `extract` provide broader inventories and nested shapes when needed.
- `scripts/har_graph.py` produces the graph independently. Edges record locations and per-run salted fingerprints for matching values without exposing those values.
- `scripts/har_inspect.py` selects exact JSON body pointers, decodes nested JSON strings, and writes bounded JSON evidence with source hashes. Compare values across supplied HARs using private IDs, inspect subtree paths, or check expected node types/flags without printing captured values. See `references/deep-dive.md` for commands and disclosure limits.

`uv run` installs `ijson` for streaming. Without `uv`, use `python3` for HARs under 100 MiB. Read compact outputs and bounded selections; avoid loading the whole HAR or bulk output files into context. Scripts filter and sample evidence, so inspect coverage and truncation before drawing conclusions from an absence.

## Output

Scale the response to the question. A focused endpoint question may need a few paragraphs; a full workflow analysis should cover:

- The action and its relevant request sequence, identified by method, normalized endpoint, and request index.
- Request/response shapes and prerequisites: observed auth, dynamic values, their sources where visible, and verification of the result.
- An automation recommendation with supporting evidence, confidence, and material unknowns. When classifying, use `direct-http`, `http-with-token-refresh`, `browser-assisted`, `manual-only/blocked`, or `insufficient-evidence`; the criteria are in `references/automation-signals.md`.
- A concise implementation sketch when useful, using placeholders, plus any validation needed before relying on it.

For a full technical report, present shared architecture and material findings once; keep exhaustive node identifiers, endpoint inventories, and evidence locations in appendices. Keep a private structured evidence inventory for complex synthesis so claims and edit targets can be rechecked. A requested independent review supplements these checks; no particular model, CLI, or delegation scheme is required.

Captured headers show what was sent, not which headers are required. Distinguish missing capture data from absent site requirements. One successful capture does not establish safe replay or token refresh behavior.

## Gotchas

- HARs and script outputs can contain sensitive URLs, field names, filenames, and credentials despite best-effort redaction. Keep them private; review before sharing and obtain permission before uploading or publishing capture-derived artifacts. Never quote cookies, tokens, passwords, payment data, or uploaded file contents; use placeholders.
- Do not replay captured mutations to test a hypothesis or suggest bypassing challenges or access controls.
- GraphQL operations can share a URL; uploads can span application and storage hosts. Follow the complete action through its result rather than relying on one request's size or status.
- Challenge/bot signals are capture-wide observations; establish their relevance to the action. WebSocket/SSE frames, bootstrap traffic, and bodies may be missing.
- Field kinds describe representation only. Times are relative to each suggested primary candidate; missing timestamps make those times unreliable.

## References

- Read `references/deep-dive.md` for broader inventories, focused selections, nested shapes, and graph queries.
- Read `references/workflow-definitions.md` for stored workflow graphs, connections, historical jobs, and cross-capture synthesis.
- Read `references/automation-signals.md` when assessing automation prerequisites or choosing a verdict.
- Use `assets/report-template.md` as an adaptable starting point for a stakeholder-ready report.
