#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"
image=agent-skills-eval:local

if [[ "${1:-}" == --smoke && $# -eq 1 ]]; then
  docker build -q -t "$image" -f eval/harness/Dockerfile eval/harness >/dev/null
  docker run --rm --read-only --tmpfs /tmp:rw,nosuid,size=256m \
    --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
    "$image" bash -c 'test ! -e /repo && test ! -e /root/.pi && pi --version && python3 --version && uv --version'
  exit
fi

if [[ $# -lt 1 || $# -gt 2 || ! "$1" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]]; then
  echo 'Usage: eval/harness/docker-run.sh <new-run-name> [openrouter/z-ai/glm-5.3-flash|openrouter/openai/gpt-6-luna]' >&2
  echo '       eval/harness/docker-run.sh --smoke' >&2
  exit 2
fi
run_name="$1"
model="${2:-openrouter/z-ai/glm-5.3-flash}"
if [[ "$model" != openrouter/z-ai/glm-5.3-flash && "$model" != openrouter/openai/gpt-6-luna ]]; then
  echo 'Unsupported eval model; use a pinned OpenRouter model' >&2
  exit 2
fi
if [[ -e "eval/results/$run_name" ]]; then
  echo "Refusing to overwrite eval/results/$run_name" >&2
  exit 2
fi
command -v varlock >/dev/null || { echo 'Install varlock before running live evals' >&2; exit 2; }
command -v op >/dev/null || { echo 'Install and sign in to 1Password CLI before running live evals' >&2; exit 2; }

docker build -q -t "$image" -f eval/harness/Dockerfile eval/harness >/dev/null
# The trusted Bun orchestrator stays on the host; each untrusted Pi child gets
# its own container with only its disposable fixture workspace mounted.
# Varlock resolves the key from 1Password at launch, never during image build.
varlock run -- bun eval/harness/run.ts --run-name "$run_name" --model "$model"
