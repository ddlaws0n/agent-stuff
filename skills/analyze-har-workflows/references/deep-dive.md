# Additional evidence tools

Use the tools that address the unresolved question. Keep the privacy and mutation limits from `SKILL.md`.

## Focus candidate selection

```bash
uv run scripts/har_brief.py /path/to/session.har --out "$ANALYSIS_DIR" --indices 40-75
```

`--indices` selects graph candidates, including requests the default ranking excludes; earlier response sources can still be linked. Capture-wide facts cover the whole file. Other graph options: `--gap-ms` controls timing links (default 3000), `--repeat-ms` repeat links (120000), `--max-fanout` high-fanout filtering (8), and `--max-scan-chars` response scan length (2000000). Narrow candidates when nearby independent actions have been grouped together. These options rerun the capture scan.

## Find requests the brief omitted

```bash
uv run scripts/har_probe.py summarize /path/to/session.har --out "$ANALYSIS_DIR" --max-body-chars 0 --top 200
```

Inspect bounded selections from:

- `summary.json`: capture counts and top candidates.
- `candidates.jsonl`: ranked requests with score reasons.
- `endpoints.tsv`: endpoint patterns, counts, and statuses.
- `entries.jsonl`: every request's metadata, including requests excluded from candidate ranking.

Match the user's action using domain, time, method, GraphQL operation, or body field names. Low-ranked traffic may still be relevant; names resembling telemetry or static files can mislead heuristics.

## Expand selected requests

```bash
uv run scripts/har_probe.py show /path/to/session.har --indices 12,18,21-24 --max-chars 3000
uv run scripts/har_probe.py show /path/to/session.har --indices 12,18 --value-ids --max-chars 3000
uv run scripts/har_probe.py extract /path/to/session.har --indices 12,18 --out "$ANALYSIS_DIR/selected.json" --max-body-chars 4000
jq '.entries[] | select(.index == 18)' "$ANALYSIS_DIR/selected.json"
```

`show` exposes compact shapes; `extract` preserves more nested JSON structure. Both redact values, and both have output limits. Avoid treating a sampled shape as a complete request specification.

`show --value-ids` gives equal sampled query/body values the same opaque ID, such as `title=<text:v3>`. Compare across the selected requests and responses to check reuse, changes, and verification reads without writing a custom comparison script. IDs distinguish JSON types, are local to one command, and are separate from graph fingerprints. Arrays/fields are sampled; matching placeholders do not establish whole-body equality. Header values and file contents are not included.

## Inspect matching values

```bash
jq '.edges[] | select(.to == 18)' "$ANALYSIS_DIR/graph.json"
```

Edges include field locations and per-run matching-value fingerprints. A response field matching a later request field is stronger evidence than timing proximity, but equality alone does not establish causality. Edge kinds such as `created-id`, `token`, or `signed-url` are guesses from names and formats. Fingerprints are comparable within one run only.

`graph.json` also contains coverage counts and limitations. Matching filters generic and high-fanout values, samples fields/arrays, caps response scans, and supports only certain body formats. A missing edge cannot prove independence. Relative timing is unreliable for entries without timestamps.
