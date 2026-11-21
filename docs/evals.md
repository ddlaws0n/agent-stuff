# Evaluating skills

Use two complementary tracks: fast deterministic checks for every change and manual/agent-run behavioral evaluations when a skill's instructions or tooling change. Passing a metadata validator does **not** prove the skill works or is selected for the right requests.

## 1. Static gate (every change)

`bun run check` type-checks, lints, format-checks, validates every skill against [docs/authoring.md](authoring.md) (including `evals/evals.json` and `evals/trigger-evals.json`), runs agnix and the official skills-ref validator, and runs Bun tests, every skill's Python tests, and harness-preparation tests. `bun run build` compiles the TypeScript developer tooling. Check CLI discovery with `npx skills add . --list` when changing a skill's location or name.

## 2. Task-quality evals (behavior changes)

Store realistic user requests in `skills/<name>/evals/evals.json`. Each committed, runnable entry has a stable numeric `id`, `prompt`, `expected_output`, nonempty `assertions`, nonempty `tags`, and optional `files` (relative to the skill directory). Begin with 2–3 diverse prompts, then add regressions for observed failures. Tags are `normal`, `boundary`, `refusal`, `dry-run`, and `pressure`. Include a normal case and a different boundary/failure case; attaching two tags to one case is insufficient. The existing `manage-github-projects` set is a starter corpus, **not** evidence that those scenarios have passed.

Each corpus records `pressure: { "required": true, "reason": "The approval or safety boundary this skill enforces." }`, or an explicit `false` decision with its reason. Require a pressure-tagged case for skills enforcing approval or safety boundaries. Make this a reviewed decision, not a keyword inference from `--dry-run`. Tags can be combined, but must describe the actual prompt. Draft exploratory prompts may live in ignored results; add observable assertions before committing them as runnable cases. The exact main-branch HAR corpus temporarily defers tags/pressure while its separate branch is migrated; [the integration order](../CONTRIBUTING.md#har-schema-transition) and guard are explicit.

For each prompt:

1. Run in a fresh context with the skill and in another fresh context without it. For revisions, compare to a snapshot of the previous skill instead. Use the same agent/model, task, inputs, tools, and environment; vary only the skill. **Pin the model on every eval child rather than inheriting Pi's default.** The local pilot in [`eval/harness/README.md`](../eval/harness/README.md) defaults to `openrouter/z-ai/glm-5.3-flash:high` and can select `openrouter/openai/gpt-6-luna:high` for a separate cohort. Verify the resolved provider/model before grading; do not pool models or providers in paired comparisons, including historical direct-provider results. Save outputs and transcripts outside `skills/` (e.g. ignored `eval/results/<skill>/iteration-N/`).
2. **Isolate side effects.** Use disposable repositories/fixtures and mocks for GitHub, network, and other external writes, or make the case explicitly dry-run. Never execute the existing project-board mutation prompts against a real board for an eval. Separate real-account integration testing and require explicit approval for it.
3. Review and refine observable assertions after the first outputs, keeping the committed corpus runnable. Verify mechanical properties (files, JSON, exact operations) with scripts; grade semantic quality with a reviewer and concrete cited evidence. Record pass/fail per assertion, plus unexpected unsafe behavior. Do not award a pass on intent alone. Keep runner, fixture, unsupported-case, and grading errors separate from task-performance failures.
4. Compare the with-skill run to baseline on assertion pass rate, failure types, elapsed time, and token use. Inspect transcripts for unnecessary steps or ignored instructions. Have a human review outputs for usefulness, correctness, and safety; objective grades cannot catch everything.
5. Improve the skill to address _general_ failures, bump its version, then rerun the entire set. Add a regression case for each meaningful new bug. Avoid assertions that always pass even without the skill or brittle exact-wording tests.

Before rewriting instructions, classify each failure and match the fix to it:

<!-- prettier-ignore -->
|Failure|Fix|
|-|-|
|Skips a required step under pressure|Explicit prohibition, the observed excuses with rebuttals, and red flags|
|Right intent, wrong output shape|Positive step-by-step recipe, not a list of don'ts|
|Omits a required element|A required slot in the template or output section|
|Behavior should depend on a condition|A conditional keyed to something observable, not a rule plus exceptions|

For skills that enforce discipline (verification, dry runs, safety checks), add prompts that combine pressures such as urgency, sunk cost, or user authority ("just ship it"). Preserve explicit user authorization: a pressure eval should not fail a legitimate action merely because a skill guideline would normally ask first. Quote any observed rationalizations verbatim with transcript line references; do not infer hidden reasoning. An empty `rationalizations` array is valid when none were observed. Grade whether the boundary held, including attempted writes that a mock rejected, rather than accepting reassurance in the final response.

The local harness carries tags and eval IDs through preparation, runner status, and grading. Its supported pressure case requires a reviewer-authored `pressure-review.json`; missing review or fabricated quotes yield `evaluation_error`, not a performance score. See [the harness review format](../eval/harness/README.md#pressure-review). Corpus validation alone does not make an arbitrary case executable by the pilot harness.

### Results layout

All generated evidence (eval outputs, transcripts, grades, audits, and reviews) lives under the git-ignored `eval/results/` and is never committed. Names are lowercase and hyphenated, with dates as `YYYYMMDD`:

```text
eval/results/
  <run-name>/                    # Docker harness runs; may span skills (eval/harness)
  <skill>/iteration-N/           # manual paired evals for one skill
    eval-1/with_skill/{outputs/,transcript,grading.json,timing.json,pressure-review.json}
    eval-1/without_skill/{outputs/,transcript,grading.json,timing.json}
    benchmark.json
    feedback.json
  <skill>/audit-YYYYMMDD.md      # audits and static reviews of one skill
  review-YYYYMMDD/summary.md     # human review across runs
```

Committed documentation records only reviewed conclusions, such as the verification snapshot below, and names the ignored path that holds the evidence. Never put results in `docs/` or inside a skill directory.

## 3. Trigger selection

Separately test the frontmatter `description` with realistic _should-trigger_ and near-miss _should-not-trigger_ prompts in the target agents. Record false negatives and false positives, and revise the description rather than adding trigger rules only in the body (which is loaded after selection). Repeat runs where activation is nondeterministic. This is a manual, agent-specific gate, not a promise made by `bun run check`.

Static checks normalize Unicode, case, and whitespace to reject duplicate queries within a skill, including contradictory labels. Positive overlap across skills is advisory because a request can legitimately use multiple skills. Review the intended collaboration or routing boundary; no offline keyword score substitutes for agent selection tests.

## Shipping bar

Static gate passes; CLI discovers the skill; changed workflows have a reviewed with-skill vs baseline comparison; no unexplained regressions or unsafe actions; requirements and limitations are documented in the skill. If an integration eval cannot run safely, report it as **not run**, not passing.

References: [Agent Skills specification](https://agentskills.io/specification), [evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills), [optimizing descriptions](https://agentskills.io/skill-creation/optimizing-descriptions).

## Verification snapshot — 3 October 2026

Scope: the five skills in the repository on that date, and a three-skill pilot (case 1 each of `create-agentsmd`, `create-github-actions`, `manage-github-projects`). Skills added later have not been through paired evals.

- The repository gate, tooling build, CLI discovery, and the Docker smoke test passed. All six cells of `review-20261003` completed on `openrouter/z-ai/glm-5.3-flash:high`, with provider/model verified by the collector.
- Automated totals: **13/14 with skill, 12/14 without**. Skill runs used more tokens in every pair. Grader defects found during the run (new CI filenames, missing board assertions, Markdown false negatives) were fixed with regression tests and outputs regraded without new model calls.
- **Protocol deviation:** the with-skill CI run probed the GitHub network despite a no-network instruction and then claimed no network access. Scores do not capture this; Docker bridge networking is not an egress boundary. No live GitHub mutation was performed, and mutation cases remain unevaluated.
- The historical direct-provider `pilot-1` (14/14 with skill, 13/14 without) is a separate cohort; do not pool it with the OpenRouter pilot.
- Human usefulness review, trigger-selection testing, and paired runs for the remaining skills are pending.
- The grader uses text patterns and command-presence checks: formatting can cause false negatives, and command mentions do not prove success or verify SHA pinning. Review transcripts before making quality or safety claims.

Evidence stays in ignored `eval/results/review-20261003/`.
