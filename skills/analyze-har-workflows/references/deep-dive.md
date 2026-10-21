# Deep-dive procedure

Use this when the brief from `scripts/har_brief.py` is not enough: its top workflow is not the user's action, links are timing-only, the capture holds several actions, or the verdict is uncertain. Keep the same guardrails as `SKILL.md`: private work directory, no raw values in the report, no replaying captured mutations.

## 1. Focus on the user's action

Rerun the brief or graph on a narrower window when the capture holds unrelated traffic. Pick the range from the brief's tables, the user's described timing, or `endpoints.tsv` below.

```bash
uv run scripts/har_brief.py /path/to/session.har --out "$ANALYSIS_DIR" --indices 40-75
```

`--indices` seeds the graph with exactly those requests. Other flags, shared with `har_graph.py`: `--gap-ms` (default 3000) sets the timing-link window, `--repeat-ms` (default 120000) the polling window, and `--max-fanout` (default 8) ignores values sent by more requests than that as session-wide noise.

## 2. Survey the whole capture

```bash
uv run scripts/har_probe.py summarize /path/to/session.har --out "$ANALYSIS_DIR" --max-body-chars 2000 --top 200
```

Read outputs with bounded commands (`head`, `jq`, `grep`), never whole:

- `summary.json`: counts by domain, method, status, and mime type, plus one line per top candidate.
- `candidates.jsonl`: likely user actions with score reasons, best first.
- `endpoints.tsv`: normalized endpoint patterns with counts and statuses.
- `entries.jsonl`: one shape per request; filter by index, never read it all.

Prioritize candidates with these signals:

- Methods `POST`, `PUT`, `PATCH`, `DELETE`, or any request with a body.
- Resource types `fetch`, `xhr`, `document`, `websocket`. Deprioritize images, fonts, stylesheets, static assets, analytics (including first-party `beacon`/`collect`/telemetry paths), CORS preflights, and blocked requests (status 0).
- JSON, GraphQL, form-urlencoded, or multipart bodies, or body keys matching the user's action.
- URL terms such as `create`, `update`, `save`, `submit`, `settings`, `upload`, `complete`, `confirm`, `checkout`, `graphql`, `api`.
- `2xx`/`3xx` responses, redirects after form posts, created or updated IDs, polling URLs.
- Timing close to the user's action.

## 3. Inspect selected requests

Prefer `show` for a few requests at a time; it prints headers by name, field kinds, and response shape in at most 1500 characters each:

```bash
uv run scripts/har_probe.py show /path/to/session.har --indices 12,18,21-24
```

Use `extract` only when you need nested body shapes beyond what `show` lists. It writes JSON; read it per entry with `jq '.entries[] | select(.index == 18)'`, not whole.

```bash
uv run scripts/har_probe.py extract /path/to/session.har --indices 12,18 --out "$ANALYSIS_DIR/selected.json" --max-body-chars 4000
```

## 4. Reconstruct the workflow

Confirm each graph edge against `show` output, then identify page or API discovery calls, token acquisition, the primary mutating request, upload handshakes, polling or status calls, and the final confirmation. Graph links are hints: a timing or Referer link alone does not prove a dependency, and a missing link may mean the value was computed client-side. `graph.json` holds every edge with its key locations (e.g. `response.json:$.data.id` -> `request.path[3]`); query it with `jq`, never read it whole.
