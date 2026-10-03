# HAR Workflow Analysis: [task/site]

## Executive summary

- **Observed task:** [What the user did]
- **Primary endpoint(s):** [Method + normalized URL]
- **Automation verdict:** direct-http | http-with-token-refresh | browser-assisted | manual-only/blocked | insufficient-evidence
- **Confidence:** high | medium | low
- **Most important caveat:** [Token/session/body/missing-data caveat]

## Workflow sequence

| Step | Request index | Time | Method | Endpoint | Purpose | Evidence |
|---|---:|---|---|---|---|---|
| 1 |  |  |  |  |  |  |

## Primary action request

```http
[METHOD] [normalized URL]
Authorization: <redacted-if-present>
Cookie: <session-cookie-if-needed>
X-CSRF-Token: <csrf-token-if-needed>
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

| Value | Where used | Source request/index | How to refresh |
|---|---|---:|---|
| CSRF token | header/body |  | GET page or bootstrap API |
| Resource ID | URL/body |  | Current page/API response |
| Upload URL | upload request |  | Init/presign endpoint |

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

1. [Run with fresh session to confirm tokens can be refreshed.]
2. [Test minimal payload versus full captured payload.]
3. [Verify server-side result via GET endpoint or UI.]

## Evidence reviewed

- Summary: `[private analysis directory]/summary.json`
- Candidates: `[private analysis directory]/candidates.jsonl`
- Selected entries: `[indices]`
