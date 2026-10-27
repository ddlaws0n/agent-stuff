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

## Inspect exact body locations

```bash
uv run scripts/har_inspect.py first.har second.har --select '0:12:/result/jobs' --select '1:6:/jobs' --walk --max-items 300 > "$ANALYSIS_DIR/evidence.json"
uv run scripts/har_inspect.py first.har --select '0:12:/result/version_no' --values
uv run scripts/har_inspect.py first.har --expect '0:12:/result/block/1/keyword' '"action"' --expect '0:12:/result/block/1/skip' 'false'
```

Selectors are `SOURCE:ENTRY:/json/pointer`; source and entry indices are zero-based. Source numbers follow the supplied HAR order. Escape `/` in keys as `~1` and `~` as `~0`. Response bodies are the default; use `--body request` for JSON request bodies. Nested JSON strings are decoded during traversal (at most four consecutive layers, with a default 2,000,000-character body/encoded-string limit). `decoded_json` records each decoded pointer and its layer count; preserve those string boundaries when planning an edit. It covers inspected paths, not unvisited fields.

Without `--values`, scalars are represented by kinds and opaque IDs. Equal IDs within **one command**, including across files, establish JSON-value equality; object key order and decoded string encoding do not affect comparison. Different commands have unrelated identity scopes. Compare full selected code roots for snapshot equality rather than inferring equality from matching node counts. IDs do not establish causality or timestamp ordering.

`--walk` inventories leaf pointers and IDs without revealing values. Containers expose their size, and objects list at most 30 keys with `keys_omitted`. `--max-items` caps observations (100 by default); `--max-chars` caps valid JSON output (6000 by default). Check `truncated` before relying on an absence or a missing check. Narrow pointers or increase limits deliberately; retained source metadata records the requested indices and number of entries scanned, not a claim that every job/page was captured. `extract` uses an `_har_probe_omitted_items` marker when array shapes exceed 200 items.

`--values` reveals only explicitly selected scalar values, never container contents, and cannot accompany `--walk`. Credential keys and records labelled as secrets stay redacted; strings and URLs receive best-effort redaction. Short or unlabelled secrets and personal data can still escape detection: select only structural facts needed for the task and review before sharing. Do not point it at arbitrary property values or uploaded content. `--expect` compares exact JSON values without printing the captured value; failed checks exit 1, invalid/missing selections exit 2. Do not put secrets in expected-value arguments.

## Inspect matching values

```bash
jq '.edges[] | select(.to == 18)' "$ANALYSIS_DIR/graph.json"
```

Edges include field locations and per-run matching-value fingerprints. A response field matching a later request field is stronger evidence than timing proximity, but equality alone does not establish causality. Edge kinds such as `created-id`, `token`, or `signed-url` are guesses from names and formats. Fingerprints are comparable within one run only.

`graph.json` also contains coverage counts and limitations. Matching filters generic and high-fanout values, samples fields/arrays, caps response scans, and supports only certain body formats. A missing edge cannot prove independence. Relative timing is unreliable for entries without timestamps.
