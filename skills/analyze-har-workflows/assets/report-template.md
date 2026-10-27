# HAR Workflow Analysis: [task/site]

Adapt or omit sections to fit the question. List only observed headers and dynamic values; distinguish required, inferred, and unknown prerequisites. Example rows below are prompts, not capture facts.

For captured definitions/jobs, replace action-request sections with the definition and coverage section below. Present shared findings once; put exhaustive node/endpoint tables in the evidence appendix.

## Executive summary

- **Observed task:** [What the user did]
- **Primary endpoint(s):** [Method + normalized URL]
- **Automation verdict:** direct-http | http-with-token-refresh | browser-assisted | manual-only/blocked | insufficient-evidence
- **Confidence:** high | medium | low
- **Most important caveat:** [Token/session/body/missing-data caveat]

## Workflow sequence

<!-- prettier-ignore -->
| Step | Request index | Time | Method | Endpoint | Purpose | Evidence |
|-|-:|-|-|-|-|-|
| 1 |  |  |  |  |  |  |

## Primary action request

```http
[METHOD] [normalized URL]
[Observed header name]: <placeholder>
Content-Type: [mime]
```

Request body shape:

```json
{
  "example": "redacted shape only"
}
```

Response shape:

```json
{
  "id": "<created-or-updated-id>",
  "status": "<status>"
}
```

## Dynamic values

<!-- prettier-ignore -->
| Value | Where used | Source request/index | How to refresh |
|-|-|-:|-|
| CSRF token | header/body |  | GET page or bootstrap API |
| Resource ID | URL/body |  | Current page/API response |
| Upload URL | upload request |  | Init/presign endpoint |

## Captured definitions and runtime coverage

- **Definition:** [ID, version, update time, trigger and callable contract]
- **Active behavior:** [Control flow, disabled steps, formulas and schema/description differences]
- **Dependencies:** [Direct callers versus root/clone lineage; shared runs across captures; separate connections versus environment identity]
- **Job coverage:** [Visible page, scope/total counts, version matching, executed branches and unverified results]
- **Edit targets:** [Exact pointer, node type/operation, reference dependencies and checks]

## Automation recommendation

[Explain the simplest reliable automation path. Prefer direct HTTP only when token refresh and replayability are clear. Recommend Playwright/browser automation where the reverse-engineering cost or challenge risk is high.]

## Minimal implementation sketch

```python
# Pseudocode only. Do not include real secrets.
import httpx

with httpx.Client(follow_redirects=True) as client:
    # 1. Authenticate or attach authorized session cookies.
    # 2. Fetch bootstrap/form page if needed.
    # 3. Submit primary action request.
    # 4. Verify result.
    pass
```

## Unknowns and validation plan

1. [Specific missing evidence and what would resolve it.]
2. [Proposed future validation, with authorization required for mutations. Do not execute captured mutations as an analysis check.]

## Evidence appendix

- Brief: `[private analysis directory]/brief.md`
- Requests inspected with `show`: `[indices]`
- Gaps: [missing bodies, absent cookies or tokens, unseen bootstrap]
- Definition/node inventory: [paths, types, UUIDs/aliases, conditions, skip flags and mappings]
- Job/cross-capture inventory: [lineage joins, timestamps, version evidence and coverage limits]
- Verification: [Checks actually run, claim basis, review findings/dispositions if requested]
