# har-workflow-analysis

Agent Skill for analyzing HAR files from browser DevTools captures to understand how user workflows work and whether they can be scripted or automated.

## Install/use

Install this skill using your agent's skill manager. The bundled `scripts/har_probe.py` turns HAR files into compact request/response shapes before reasoning. Requires Python 3.10+; `uv` installs `ijson` for streaming large captures (without it, the script falls back to loading HARs under 100 MiB). Run commands from the skill directory or use its absolute script path. Work in a private local directory outside shared repositories: HARs and even the summarized outputs may contain sensitive URLs, hostnames, or field names.

## First command to run on a HAR

```bash
ANALYSIS_DIR="$(mktemp -d)"
uv run scripts/har_probe.py summarize /path/to/session.har --out "$ANALYSIS_DIR" --max-body-chars 2000 --top 200
```

## Then extract selected request indices

```bash
uv run scripts/har_probe.py extract /path/to/session.har --indices 12,18,21-24 --out "$ANALYSIS_DIR/selected.json" --max-body-chars 12000
```

## Outputs

- `summary.json`: high-level counts and top candidates.
- `entries.jsonl`: one compact, best-effort-redacted request/response shape per HAR entry.
- `candidates.jsonl`: likely user-action requests sorted by heuristic score.
- `endpoints.tsv`: normalized endpoint patterns and counts.
- `selected.json`: details for chosen request indices.

## Evaluation

Starter eval prompts live in `evals/evals.json`; synthetic HAR fixtures live in `evals/files/`. Run the script regression checks with `uv run --with 'ijson>=3.2,<4' python -B -m unittest discover -s evals -p 'test_*.py'` from the skill directory.
