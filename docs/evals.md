# Evaluating skills

Use two complementary tracks: fast deterministic checks for every change and manual/agent-run behavioral evaluations when a skill's instructions or tooling change. Passing a metadata validator does **not** prove the skill works or is selected for the right requests.

## 1. Static gate (every change)

`bun run check` type-checks, lints, formats-checks, validates every `skills/*/SKILL.md` and `evals/evals.json`, and runs repository tests. `bun run build` compiles the TypeScript developer tooling. Check CLI discovery with `npx skills add . --list` when changing a skill's location or name. Optionally cross-check a changed skill against the reference implementation with `skills-ref validate skills/<name>` if `skills-ref` is installed; this is not a Bun dependency.

## 2. Task-quality evals (behavior changes)

Store realistic user requests in `skills/<name>/evals/evals.json`. Each entry has a stable numeric `id`, `prompt`, `expected_output`, optional `files` (relative to the skill directory), and optional `assertions`. Begin with 2–3 diverse prompts, then add regressions for observed failures. Include normal, ambiguous/boundary, and safe-refusal or dry-run cases when applicable. The existing `manage-github-projects` set is a starter corpus, **not** evidence that those scenarios have passed.

For each prompt:

1. Run in a fresh context with the skill and in another fresh context without it. For revisions, compare to a snapshot of the previous skill instead. Use the same agent/model, task, inputs, tools, and environment; vary only the skill. Save outputs and transcripts outside `skills/` (e.g. ignored `eval-results/<skill>/iteration-N/`).
2. **Isolate side effects.** Use disposable repositories/fixtures and mocks for GitHub, network, and other external writes, or make the case explicitly dry-run. Never execute the existing project-board mutation prompts against a real board for an eval. Separate real-account integration testing and require explicit approval for it.
3. Add observable assertions after reviewing the first outputs. Verify mechanical properties (files, JSON, exact operations) with scripts; grade semantic quality with a reviewer and concrete cited evidence. Record pass/fail per assertion, plus unexpected unsafe behavior. Do not award a pass on intent alone.
4. Compare the with-skill run to baseline on assertion pass rate, failure types, elapsed time, and token use. Inspect transcripts for unnecessary steps or ignored instructions. Have a human review outputs for usefulness, correctness, and safety; objective grades cannot catch everything.
5. Improve the skill to address *general* failures, bump its version, then rerun the entire set. Add a regression case for each meaningful new bug. Avoid assertions that always pass even without the skill or brittle exact-wording tests.

Suggested result layout (generated results are not committed):

```text
eval-results/<skill>/iteration-1/
  eval-1/with_skill/{outputs/,transcript,grading.json,timing.json}
  eval-1/without_skill/{outputs/,transcript,grading.json,timing.json}
  benchmark.json
  feedback.json
```

## 3. Trigger selection

Separately test the frontmatter `description` with realistic *should-trigger* and near-miss *should-not-trigger* prompts in the target agents. Record false negatives and false positives, and revise the description rather than adding trigger rules only in the body (which is loaded after selection). Repeat runs where activation is nondeterministic. This is a manual, agent-specific gate, not a promise made by `bun run check`.

## Shipping bar

Static gate passes; CLI discovers the skill; changed workflows have a reviewed with-skill vs baseline comparison; no unexplained regressions or unsafe actions; requirements and limitations are documented in the skill. If an integration eval cannot run safely, report it as **not run**, not passing.

References: [Agent Skills specification](https://agentskills.io/specification), [evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills), [optimizing descriptions](https://agentskills.io/skill-creation/optimizing-descriptions).
