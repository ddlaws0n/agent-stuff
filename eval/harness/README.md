# Local skill-eval pilot harness

Run each of the six pilot cells in its own disposable container (not through host subagents). Install Docker, Varlock and the 1Password CLI; sign in to 1Password. The committed `.env.schema` resolves the dedicated OpenRouter key at launch, without copying it into the image or this repository.

```sh
./eval/harness/docker-run.sh --smoke
./eval/harness/docker-run.sh local-1
# Or: ./eval/harness/docker-run.sh local-luna-1 openrouter/openai/gpt-6-luna
```

The default model is `openrouter/z-ai/glm-5.3-flash:high`, explicitly pinned on each Pi process; the second option is a **different provider cohort** from the historical `openai-codex/gpt-6-luna` runs. Do not pool providers in paired comparisons. A trusted Bun orchestrator on the host prepares fixtures and captures each container's Pi CLI JSON event output. It verifies the resolved provider/model and completion, then writes transcripts, outputs, timings, and grades under ignored `eval/results/<run-name>/`. Each run name is exclusive and is never overwritten. The original sol pilot stays at `pilot-1`.

The image follows [Pi's plain-Docker starter](https://pi.dev/docs/latest/containerization) with pinned Pi and uv versions. Node runs the Pi CLI and sample app checks; Python runs the bundled skill scripts and mock `gh`. Bun is needed only by the host orchestrator. Only **one disposable fixture workspace** is mounted into each child; the skill source is copied into with-skill fixtures and absent from baselines. Results, the real repo, `.local/`, host home, host Pi auth, and Docker socket are not mounted into Pi. It runs as a non-root user on a read-only root filesystem with dropped capabilities. This isolates host files, **not the API key**: evaluated commands can read the key from the environment, and ordinary Docker bridge networking allows outbound traffic beyond OpenRouter. Use a disposable, tightly budgeted, revocable key; use a proxy-managed sandbox with egress policy if key secrecy or egress isolation is required. Never run this as a trusted network/credential boundary. Results may contain sensitive agent output; inspect before sharing.

`docker-run.sh` uses `prepare.py`, the host Bun `run.ts` orchestrator/collector, and `grade.py`. Historical results are retained, but the old host-subagent collector and workflow launcher are not supported. Docker smoke verifies tools without model calls; live evals require a working 1Password session and consume API credits.

This prepares only case 1 from each skill, not the full 11-case corpus. Adapt `CASES`/fixture builders and grading before adding other cases. The original prompts and assertions live under `skills/*/evals/`.

The project-board fixture has a synthetic, read-only `bin/gh` that rejects writes and unknown commands. The container excludes the real `gh` executable and GitHub credentials, but it still has network access for the model. Keep project-board cases read-only until a network-deny or allowlisted-egress boundary is tested. The runner prepends the mock directory to each child's PATH.

`grade.py` grades **only** the three pilot cases, regardless of run name. Use skill-creator's existing benchmark aggregator and `eval-viewer/generate_review.py` for review; do not treat one pair as a statistical benchmark.

## Verification status

As of 3 October 2026, the Docker smoke test and fixture/model-selection/grader tests pass. All six OpenRouter cells in `review-20261003` completed; execution, collection, redaction plumbing, model verification, and regrading were exercised. Grader fixes accept new CI filenames, tolerate Markdown board tables, detect logged mock mutation attempts, and require pilot assertions before execution.

The automated result is 13/14 with skill and 12/14 without. Transcript review also found a CI network probe against the task instructions and a rejected baseline board mutation. Scores do not capture every protocol deviation. Historical results use a separate provider cohort; human feedback remains pending. See [the verification snapshot](../../docs/evals.md#verification-snapshot--3-october-2026) for scope and limitations, and the ignored `eval/results/review-20261003/summary.md` for the reviewed run.
