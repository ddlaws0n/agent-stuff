---
name: analyze-har-workflows
description: >-
  Analyzes HAR files and browser network captures to explain how a website
  action works and whether it can be scripted or automated. Use when the user
  provides a HAR file, browser network export, or DevTools capture, or asks how
  a website action works from its network requests: form submissions, uploads,
  settings changes, checkout flows, API calls, GraphQL operations, and
  auth/session handling. Use especially for large or sensitive captures; it
  extracts a compact, privacy-conscious request/response shape before reasoning.
  Do not use for live browser automation or scraping without a capture.
license: MIT
compatibility: >-
  Requires Python 3.10+. uv is recommended for streaming large HARs via the
  bundled scripts' ijson dependency; Python alone supports small HARs.
metadata:
  author: ddlaws0n
  version: "0.3.0"
---

# HAR workflow analysis

Infer from a HAR capture how a user-triggered website action works (forms, uploads, settings, record CRUD, checkout, admin actions) and whether it can be scripted.

Guardrails:

- Never paste, `cat`, or load a whole HAR or a whole script output file into context. HARs hold cookies, tokens, personal data, and file contents. Read the brief and `show` output instead.
- Never quote raw cookies, bearer or CSRF tokens, passwords, payment data, or uploaded file contents. Use placeholders such as `<session-cookie>` and `<csrf-token>`.
- Never replay captured mutating requests to test a hypothesis, and never suggest bypassing captchas, challenges, or access controls.
- Claim only what the capture shows. The brief lists what is absent (cookies, auth headers, CSRF values, challenge signals, response bodies): report an absent value as absent or user-supplied, never as present-but-hidden.
- Treat script outputs as sensitive too: redaction is best-effort. Keep them in a private directory and out of shared repositories.

## Output

```markdown
# HAR Workflow Analysis: [task/site]

## Executive summary
[What the action does, primary endpoint(s), automation verdict, confidence.]

## Key workflow sequence
| Step | Request index | Method | Endpoint | Purpose | Evidence |
|-|-:|-|-|-|-|

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
[Pseudocode or a concise script skeleton with placeholders, never captured values.]

## Evidence reviewed
[Brief, request indices inspected with `show`, and notable omissions.]
```

## Workflow

1. **Clarify only if missing:** the action performed, rough timing, expected result, target domain. If the prompt gives enough context, proceed.
2. **Run the brief** from the skill directory, writing to a private directory:

   ```bash
   ANALYSIS_DIR="$(mktemp -d)"
   uv run scripts/har_brief.py /path/to/session.har --out "$ANALYSIS_DIR"
   ```

   Without `uv`, use `python3` instead for HARs under 100 MiB. The brief (about 5 KB, printed and saved as `brief.md`) holds capture facts, the top workflows with step roles and times relative to the primary action, the field kinds the primary sends and returns, which fields differ between repeated calls, and a rule-based verdict hint.

3. **Confirm the key steps** with the indices the brief suggests:

   ```bash
   uv run scripts/har_probe.py show /path/to/session.har --indices 12,18
   ```

   It prints headers by name, query and body field kinds, and response shape, at most 1500 characters per request.

4. **Write the report** when the top workflow matches the user's action and `show` confirms it. Start from the verdict hint; if your verdict differs, say which evidence overrides it.
5. **Go deeper only when needed:** the top workflow is not the user's action, links are timing-only, the capture holds several actions, or the verdict is uncertain. Then follow `references/deep-dive.md`.

## Automation verdicts

- **direct-http:** stable endpoint, replayable request, auth representable as cookies or headers, no dynamic value beyond a standard session or CSRF token, no browser-only dependency.
- **http-with-token-refresh:** scriptable, but a page or bootstrap API must be fetched first for a CSRF token, nonce, presigned URL, job or upload ID, or other server-generated value.
- **browser-assisted:** depends on complex JS, dynamic challenges, WebAuthn, obfuscated signing, volatile tokens, or DOM state cheaper to drive with Playwright than to reverse engineer.
- **manual-only/blocked:** captcha, MFA/WebAuthn at action time, anti-automation challenge, encrypted payload with an unknown key, or human review.
- **insufficient-evidence:** missing bodies, missing session bootstrap, blocked or truncated requests, or unknown task timing.

One captured success does not prove safe replay, authorization, or supported API use.

## Gotchas

- Field kinds such as `<numeric-string>`, `<code>`, or `<date>` stand in for hidden values. Describe a field only as far as its kind and name support; a `<numeric-string>` is not a date.
- Times in the brief are seconds relative to the workflow's primary action, not to the start of the capture.
- GraphQL hides distinct actions behind one URL: group by operation name, not URL.
- Uploads are usually multi-step: initiate, upload to storage or a presigned URL, complete or attach, poll. Include every step.
- The visible result may be a `202`, `204`, `302`, or a polling response rather than the largest JSON body.
- WebSocket or SSE frames may be missing from a HAR. If the workflow depends on them, say the capture is insufficient.
- Third-party telemetry can carry action names but is rarely the automation endpoint.

## Scripts

- `scripts/har_brief.py`: one streaming pass that prints the capped brief and writes `brief.md`, `workflow.md` (every workflow as a table), and `graph.json` (typed edges with key locations and salted fingerprints, never values). `--indices` focuses on a request range.
- `scripts/har_probe.py show`: compact view of chosen requests. `summarize` and `extract` write fuller outputs for the deep dive.
- `scripts/har_graph.py`: the graph on its own (`graph.json`, `workflow.md`); the brief already runs it.

## References

- Read `references/deep-dive.md` when the brief does not settle the workflow (see step 5).
- Read `references/automation-signals.md` when the verdict is uncertain or the site uses GraphQL, uploads, CSRF, signed URLs, WebSockets, or anti-automation controls.
- Load `assets/report-template.md` when the user asks for a polished or stakeholder-ready report.
