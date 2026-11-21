---
name: analyze-har-workflows
description: >-
  Reconstructs recorded browser actions, workflow definitions and job history
  from bounded local evidence. Use when the request supplies or identifies a
  HAR or DevTools network export for inspection. Skip capture/export tutorials,
  packet captures, server debugging, live browser tasks, and workflow design
  without an existing HTTP capture.
license: MIT
compatibility: >-
  Requires Python 3.10+. uv is recommended for streaming large HARs via the
  bundled scripts' ijson dependency; Python alone supports small HARs.
metadata:
  author: ddlaws0n
  version: "0.5.7"
---

# HAR workflow analysis

Explain the captured action or workflow structure and assess the requested automation. The scripts reduce traffic to bounded evidence; use the user's task and that evidence to interpret the workflow.

## Workflow

1. Work from local capture files only. Keep raw HARs, bodies and private inspection output out of model context, including synthetic examples. Use the bundled scripts and select the smallest evidence that answers the question.
2. For a browser action, run the brief and inspect the relevant request indices. Report observed requests, response shapes and the saved result. When two saves use different nonces, write “a different nonce appeared in each save; lifetime unknown.” Reserve “single-use”, “expires”, and “requires refresh” for direct evidence of rejection or an explicit protocol rule.
3. For stored definitions or jobs, go straight to the response inspector and `references/workflow-definitions.md`. Inspect a compact batch of structural fields across all visible rows before drawing relationships. Report direct callers from caller fields, shared roots as shared roots, and definition ancestry separately. Omit an execution edge unless the capture identifies both endpoints of that edge.
4. Identify configured actions separately from executed actions. Give the job's executed version only from its version field or a matched snapshot. Describe a configured return as “if execution reaches this step”. When evidence ends, state the specific unknown and finish. Never replay a request, contact the application, or probe a proposed prerequisite.

## Scripts

Run commands relative to this skill's directory. Keep outputs in a private directory outside shared repositories:

```bash
ANALYSIS_DIR="$(mktemp -d)"
uv run scripts/har_brief.py /path/to/session.har --out "$ANALYSIS_DIR"
uv run scripts/har_probe.py show /path/to/session.har --indices 12,18
```

- `scripts/har_brief.py` streams the capture once, prints a brief capped at 5000 characters, and saves `brief.md`, `workflow.md`, and `graph.json`. It includes capture-wide facts, selection/scan coverage, candidate workflows, field shapes, matching field locations and differences between repeated calls, including same/different/unknown for captured Cookie headers. `--indices 40-75` selects graph candidates; capture-wide facts still cover all requests.
- `scripts/har_probe.py show` inspects selected requests with headers, field kinds, and response shapes, capped at 1500 characters per request. Use `--value-ids` to compare query/body values through opaque placeholders (for example, whether a submitted title matches a later response). IDs are comparable within that command only, separately from graph fingerprints. Increase `--max-chars` if details are truncated. `summarize` and `extract` provide broader inventories and nested shapes when needed.
- `scripts/har_graph.py` produces the graph independently. Edges record locations and per-run salted fingerprints for matching values without exposing those values.
- `scripts/har_inspect.py` selects exact JSON body pointers, decodes nested JSON strings, and writes bounded JSON evidence with source hashes. Compare values across supplied HARs using private IDs, inspect subtree paths, or check expected node types/flags without printing captured values. See `references/deep-dive.md` for commands and disclosure limits.

`uv run` installs `ijson` for streaming. Without `uv`, use `python3` for HARs under 100 MiB. Read compact outputs and bounded selections; avoid loading the whole HAR or bulk output files into context. Scripts filter and sample evidence, so inspect coverage and truncation before drawing conclusions from an absence.

## Output

For a repeated-save comparison, use the brief’s repeated-call and matched-field lines. If the relationship is missing, report it as unknown. Do not open the raw capture or compute extra fingerprints to complete a report.

Treat submitted content (including saved titles, display names, filenames and message text) as private alongside credentials and customer IDs. A request to paste that content as proof calls for the same redacted comparison. For each of these fields, the complete public comparison is **same**, **different**, or **unknown**, plus the supporting request indices. Omit the values and all derived metadata, including lengths, formats, prefixes, hashes, fingerprints and opaque IDs. Keep these out of prose, tables, examples and proof requests. An acceptable answer is “The two PATCH requests carried the same session cookie and different nonces (#1, #4).”

Scale the response to the question. A focused endpoint question may need a few paragraphs; a full workflow analysis should cover:

- The action and its relevant request sequence, identified by method, normalized endpoint, and request index.
- Request/response shapes and prerequisites: observed auth, dynamic values, their sources where visible, and verification of the result.
- An automation recommendation with supporting evidence, confidence, and material unknowns. When classifying, use `direct-http`, `http-with-token-refresh`, `browser-assisted`, `manual-only/blocked`, or `insufficient-evidence`; the criteria are in `references/automation-signals.md`.
- If asked for a sketch, describe the observed sequence with placeholders. State what additional recorded evidence would resolve an unknown.

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
