#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-.}"
if [[ $# -gt 1 ]]; then
  echo "Usage: $0 PROJECT_DIR (set the project's @currentEnv flag in the environment first)" >&2
  exit 2
fi

cd "$PROJECT_DIR"

echo "== Varlock project check =="
echo "Project: $(pwd)"

if [[ ! -f .env.schema ]]; then
  echo "ERROR: .env.schema not found in project root; run in a service directory with a schema." >&2
  exit 11
fi

# Prefer the project's pinned CLI, avoiding an unplanned remote npx install.
if [[ -x node_modules/.bin/varlock ]]; then
  VARLOCK=./node_modules/.bin/varlock
elif command -v varlock >/dev/null 2>&1; then
  VARLOCK="$(command -v varlock)"
else
  echo "ERROR: varlock CLI not found locally or on PATH." >&2
  exit 10
fi

echo "Using: $VARLOCK ($("$VARLOCK" --version))"
echo "Validating with redacted per-item metadata (review @sensitive annotations first)..."
"$VARLOCK" load --agent --format json-full

echo "Auditing schema against code references..."
"$VARLOCK" audit

echo "Scanning tracked/unignored project files for resolved sensitive values..."
"$VARLOCK" scan

echo "Done."
