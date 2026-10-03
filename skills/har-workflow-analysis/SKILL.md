---
name: har-workflow-analysis
description: >-
  Use this skill when the user provides a HAR file, browser network export,
  DevTools capture, or asks how a website action works from network requests.
  Inspect form submissions, uploads, settings changes, checkout flows, API
  calls, GraphQL operations, auth/session handling, and whether the action can
  be scripted or automated. Use especially for large or sensitive captures:
  extract a compact, privacy-conscious request/response shape before reasoning.
license: MIT
compatibility: >-
  Requires Python 3.10+. uv is recommended for streaming large HARs via the
  bundled script's ijson dependency; Python alone supports small HARs.
metadata:
  author: ddlaws0n
  version: "0.1.1"
---

# HAR workflow analysis

## Goal

Analyze a HAR capture to infer how a website task works and whether it can be scripted. Common tasks include filling forms, uploading files, changing account settings, creating/updating/deleting records, checkout flows, admin actions, and other user-triggered workflows.

Never paste or load an entire HAR into the model. HAR files often contain cookies, bearer tokens, CSRF tokens, personal data, file contents, and large static assets. Extract a compact working set first. Treat even script outputs as sensitive: redaction is best-effort, not a guarantee of anonymity. Keep outputs local and out of shared repositories, and do not publish or upload the HAR or analysis without the user's permission.

## Default workflow

1. **Clarify the user task only if missing.** Useful details: what action was performed, approximate time in the recording, expected visible result, and target domain. If the prompt already gives enough context, proceed.
2. **Choose a private work directory** outside shared or version-controlled folders, e.g. `ANALYSIS_DIR="$(mktemp -d)"`. Resolve `scripts/har_probe.py` relative to the installed skill directory; the commands below assume that directory is your working directory. Never run captured mutating requests just to validate a hypothesis.
3. **Summarize by streaming the HAR:**

   ```bash
   uv run scripts/har_probe.py summarize /path/to/session.har --out "$ANALYSIS_DIR" --max-body-chars 2000 --top 200
   ```

   If `uv` is unavailable and the HAR is under 100 MiB, use the script's in-memory fallback:

   ```bash
   python3 scripts/har_probe.py summarize /path/to/session.har --out "$ANALYSIS_DIR" --max-body-chars 2000 --top 200
   ```

4. **Read only compact outputs first:**
   - `$ANALYSIS_DIR/summary.json` for domains, counts, mime types, methods, status codes, and top candidate actions.
   - `$ANALYSIS_DIR/candidates.jsonl` for likely user-action requests.
   - `$ANALYSIS_DIR/endpoints.tsv` for repeated API patterns.
   - `$ANALYSIS_DIR/entries.jsonl` only with bounded line filters (e.g. selected indices), never the whole file.
5. **Select a small slice** of likely workflow requests by candidate score, method, domain, timestamp, endpoint pattern, GraphQL operation name, upload markers, or request body keys.
6. **Extract details for selected request indices only:**

   ```bash
   uv run scripts/har_probe.py extract /path/to/session.har --indices 12,18,21-24 --out "$ANALYSIS_DIR/selected.json" --max-body-chars 12000
   ```

7. **Reconstruct the workflow:** identify page/API discovery calls, token acquisition, the primary mutating request, file upload handshakes, follow-up polling/status calls, and final confirmation.
8. **Assess automation feasibility:** classify as `direct-http`, `http-with-token-refresh`, `browser-assisted`, `manual-only/blocked`, or `insufficient-evidence`. A capture of one successful action does not prove safe replay, access authorization, or supported API behavior. Do not provide ways to bypass challenges or access controls.
9. **Produce the report** using the structure below. If writing a longer report, load `assets/report-template.md`.

## Candidate selection heuristics

Prioritize requests with these signals:

- Methods: `POST`, `PUT`, `PATCH`, `DELETE`, or any request with `postData`.
- Resource types: `fetch`, `xhr`, `document`, `websocket`; deprioritize `image`, `font`, `stylesheet`, analytics, and static assets.
- Body types: JSON, GraphQL, form-urlencoded, multipart/form-data, binary upload metadata, or request body keys matching the user action.
- URL terms: `create`, `update`, `save`, `submit`, `settings`, `profile`, `upload`, `complete`, `confirm`, `checkout`, `graphql`, `api`, `v1`, `v2`.
- Responses: `2xx`, `3xx`, JSON bodies, redirects after form posts, created/updated IDs, status messages, validation errors, or polling URLs.
- Temporal proximity to the user action when timestamps are available.

## Automation decision rules

- **direct-http:** stable API endpoint, replayable request structure, auth can be represented as cookies/headers, no dynamic one-time token beyond standard session or CSRF, no browser-only dependency.
- **http-with-token-refresh:** endpoint is scriptable but requires first fetching a page or bootstrap API to obtain CSRF, nonce, presigned URL, or upload session ID.
- **browser-assisted:** request depends on complex JS, dynamic challenge, WebAuthn, captchas, obfuscated signing, volatile tokens, or DOM state that is cheaper and safer to drive with Playwright than to reverse engineer.
- **manual-only/blocked:** captcha, MFA/WebAuthn required at action time, clear anti-automation challenge, encrypted client payload with unknown signing key, or workflow depends on human review. Never suggest bypassing these controls.
- **insufficient-evidence:** HAR lacks request/response bodies, missing earlier session bootstrap, relevant requests blocked/truncated, or task timing is unknown.

## Report structure

```markdown
# HAR Workflow Analysis: [task/site]

## Executive summary
[What the action does, primary endpoint(s), automation verdict, confidence.]

## Key workflow sequence
| Step | Request index | Method | Endpoint | Purpose | Evidence |
|---|---:|---|---|---|---|

## Primary action request
- Method + URL pattern:
- Required headers/cookies:
- Request body shape:
- Response shape:
- Dynamic values and where they come from:

## Automation feasibility
- Verdict: direct-http | http-with-token-refresh | browser-assisted | manual-only/blocked | insufficient-evidence
- Why:
- Suggested implementation approach:
- Risks/unknowns:

## Minimal automation sketch
[Use pseudocode or a concise script skeleton. Never include real secrets from the HAR.]

## Evidence reviewed
[List compact summaries, selected request indices, and notable omissions.]
```

## Gotchas

- HAR captures often include secrets. Never quote raw cookies, bearer tokens, CSRF tokens, passwords, payment data, or uploaded file contents. Use placeholders like `<session-cookie>` and `<csrf-token>`. Even normalized URLs, hostnames, field names, and filenames may be sensitive: check selected outputs before sharing a report.
- Do not assume a request is replayable just because it works once. Check token sources, nonce fields, timestamp fields, upload session IDs, signed URLs, and request ordering.
- GraphQL often hides distinct actions behind one `/graphql` URL. Group by `operationName` and top-level query/mutation name, not URL alone.
- Multipart uploads are usually multi-step: initiate upload, upload to storage/presigned URL, complete/attach file, poll processing. Include all required steps.
- A successful visible action may be a `204`, `302`, or background polling response rather than the largest JSON response.
- WebSocket/SSE messages may not be fully represented in standard HAR. If the workflow depends on socket frames, state that the HAR is insufficient and recommend browser instrumentation.
- Ignore noisy third-party telemetry unless it carries the primary action. Analytics requests can contain action names but are rarely the automation endpoint.
- When the HAR is huge, use script filters and request indices. Do not paste or load the whole file into the agent context. If a request depends on unseen body values, describe the limitation rather than copying raw data into the report.

## When to load references

- Load `references/automation-signals.md` when the verdict is uncertain or the site uses GraphQL, uploads, CSRF, signed URLs, WebSockets, or anti-automation controls.
- Load `assets/report-template.md` when the user asks for a polished deliverable or stakeholder-ready report.
