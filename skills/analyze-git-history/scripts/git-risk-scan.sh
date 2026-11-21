#!/usr/bin/env bash
# Read-only: runs only git rev-parse/log/shortlog/ls-tree and writes to a private temp dir.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/git-risk-scan.sh [OPTIONS]

Build a first-pass git history risk map for an unfamiliar codebase.

Options:
  --path PATH            Repository path. Default: current directory.
  --scope PATHSPEC       Path to scan, relative to the repository root, e.g. src,
                         app, packages/api. Default: . (whole repository)
  --since DATE           Lookback for churn, bug hotspots, and firefighting. Default: "1 year ago".
  --active-since DATE    Lookback for recent ownership. Default: "6 months ago".
  --limit N              Number of rows per ranking. Default: 20.
  --include-generated    Do not filter common generated/lock/vendor paths.
  --help                 Show this help.

Exit codes: 0 report printed, 2 bad option, 3 not a git work tree, 4 no commits.

Examples:
  bash scripts/git-risk-scan.sh --path ../my-repo --scope src
  bash scripts/git-risk-scan.sh --path . --scope packages/api --since "18 months ago" --limit 30
USAGE
}

REPO="."
SCOPE="."
SINCE="1 year ago"
ACTIVE_SINCE="6 months ago"
LIMIT="20"
FILTER_GENERATED="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) REPO="${2:?--path requires a value}"; shift 2 ;;
    --scope) SCOPE="${2:?--scope requires a value}"; shift 2 ;;
    --since) SINCE="${2:?--since requires a value}"; shift 2 ;;
    --active-since) ACTIVE_SINCE="${2:?--active-since requires a value}"; shift 2 ;;
    --limit) LIMIT="${2:?--limit requires a value}"; shift 2 ;;
    --include-generated) FILTER_GENERATED="0"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
  esac
done

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -lt 1 ]]; then
  echo "Error: --limit must be a positive integer. Received: $LIMIT" >&2
  exit 2
fi

if ! ROOT="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)" || [[ -z "$ROOT" ]]; then
  echo "Error: '$REPO' is not inside a git work tree." >&2
  exit 3
fi

if ! git -C "$ROOT" rev-parse --verify --quiet HEAD >/dev/null; then
  echo "Error: '$ROOT' has no commits yet; there is no history to analyze." >&2
  exit 4
fi

# Unquoted paths so names with spaces or non-ASCII characters match across commands.
g() { git -C "$ROOT" -c core.quotePath=false "$@"; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/git-risk-scan.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
TAB="$(printf '\t')"

# Whole-word keyword matches, so "prefix" is not a fix and "product" is not prod.
B='(^|[^[:alnum:]_])'
E='([^[:alnum:]_]|$)'
BUG_RE="${B}(fix(e[sd]|ing)?|bug(s|fix(es)?)?|broken|regression|hotfix(es)?|roll ?back|revert(ed|s)?)${E}"
FIRE_RE="${B}(revert(ed|s)?|hotfix(es)?|emergency|roll ?back|incident|outage|prod|production fix)${E}"
export GENERATED_RE='(^|/)(package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|uv\.lock|poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum|Gemfile\.lock|composer\.lock)$|(^|/)(dist|build|vendor|node_modules|generated|coverage|__snapshots__)/|\.snap$|\.min\.(js|css)$'
export FILTER_GENERATED

warnings=()
if [[ "$(g rev-parse --is-shallow-repository 2>/dev/null || echo false)" == "true" ]]; then
  warnings+=("Shallow clone: history is truncated, so churn, ownership, and velocity are undercounted. Unshallowing needs network access and changes the repository; ask before running it.")
fi
if [[ -z "$(g rev-list -n 1 HEAD -- "$SCOPE")" ]]; then
  warnings+=("No commits touch scope '$SCOPE'. Check the path is relative to the repository root.")
fi
if [[ ${#warnings[@]} -gt 0 ]]; then
  for w in "${warnings[@]}"; do echo "Warning: $w" >&2; done
fi

# Paths that still exist at HEAD; deleted or renamed-away paths are not worth reading first.
g ls-tree -r --name-only HEAD > "$WORK/live.txt"

# stdin: one path per line. stdout: "count<TAB>path", highest first.
# awk and sort consume all input, so nothing upstream gets SIGPIPE under pipefail.
count_paths() {
  awk -v filter="$FILTER_GENERATED" '
    FNR == NR { live[$0] = 1; next }
    $0 == "" || !($0 in live) { next }
    filter == "1" && $0 ~ ENVIRON["GENERATED_RE"] { next }
    { c[$0]++ }
    END { for (p in c) printf "%d\t%s\n", c[p], p }
  ' "$WORK/live.txt" - | sort -t "$TAB" -k1,1nr -k2,2
}

g log --format=format: --name-only --since="$SINCE" HEAD -- "$SCOPE" \
  | count_paths > "$WORK/churn.tsv"
g log -i -E --grep="$BUG_RE" --format=format: --name-only --since="$SINCE" HEAD -- "$SCOPE" \
  | count_paths > "$WORK/bugs.tsv"
# Join the full lists, not the truncated top-N, then rank by bug touches.
awk -F '\t' 'FNR == NR { c[$2] = $1; next } ($2 in c) { printf "%d\t%d\t%s\n", $1, c[$2], $2 }' \
  "$WORK/churn.tsv" "$WORK/bugs.tsv" | sort -t "$TAB" -k1,1nr -k2,2nr -k3,3 > "$WORK/overlap.tsv"
g shortlog -sn --no-merges HEAD -- "$SCOPE" > "$WORK/owners-all.txt"
g shortlog -sn --no-merges --since="$ACTIVE_SINCE" HEAD -- "$SCOPE" > "$WORK/owners-recent.txt"
g log --format='%ad' --date=format:'%Y-%m' HEAD -- "$SCOPE" | sort | uniq -c > "$WORK/velocity.txt"
g log -i -E --grep="$FIRE_RE" --format='%h %ad %s' --date=short --since="$SINCE" HEAD -- "$SCOPE" \
  > "$WORK/fire.txt"

fence() { printf '\n```\n'; if [[ -s "$1" ]]; then "${@:2}" "$1"; else echo "(none)"; fi; printf '```\n\n'; }
top() { awk -v n="$LIMIT" 'NR <= n' "$1"; }
counts() { awk -F '\t' -v n="$LIMIT" 'NR <= n { printf "%6d  %s\n", $1, $2 }' "$1"; }
pairs() { awk -F '\t' -v n="$LIMIT" 'NR <= n { printf "%s  bug_touches=%d churn_touches=%d\n", $3, $1, $2 }' "$1"; }
all() { cat "$1"; }

echo "# Git History Risk Map"
echo
echo "- Repository: $ROOT"
echo "- HEAD: $(g rev-parse --short HEAD)"
echo "- Scope: $SCOPE"
echo "- Churn / bug / firefighting lookback: $SINCE"
echo "- Active ownership lookback: $ACTIVE_SINCE"
echo "- Limit: $LIMIT"
echo "- Generated and lockfile filtering: $([[ "$FILTER_GENERATED" == "1" ]] && echo enabled || echo disabled)"
echo "- .mailmap: $([[ -f "$ROOT/.mailmap" ]] && echo present || echo absent)"
echo "- Paths no longer in HEAD are omitted from file rankings."
if [[ ${#warnings[@]} -gt 0 ]]; then
  printf '\n## Warnings\n\n'
  for w in "${warnings[@]}"; do echo "- $w"; done
fi
printf '\n## Churn hotspots\n'
fence "$WORK/churn.tsv" counts
printf '## Ownership: all time\n'
fence "$WORK/owners-all.txt" top
printf '## Ownership: recent\n'
fence "$WORK/owners-recent.txt" top
printf '## Bug-fix hotspots\n'
fence "$WORK/bugs.tsv" counts
printf '## Files appearing in both churn and bug-fix hotspots\n'
fence "$WORK/overlap.tsv" pairs
printf '## Commit velocity by month\n'
fence "$WORK/velocity.txt" all
printf '## Firefighting commits (%s total)\n' "$(awk 'END { print NR }' "$WORK/fire.txt")"
fence "$WORK/fire.txt" top
cat <<'REPORT'
## Suggested interpretation

- Highest-priority files are those appearing in both churn and bug-fix hotspots.
- Treat ownership concentration and inactive historical owners as knowledge-transfer risk, not blame.
- Treat velocity drops and firefighting commits as prompts for investigation, not proof of process failure.
- Before final conclusions, inspect recent diffs for the top files and note caveats such as squash merges, split identities, bots, generated files, and weak commit messages.
REPORT
