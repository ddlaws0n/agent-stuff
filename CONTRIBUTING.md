# Contributing

Create a focused branch from current `main` and open a pull request. Keep unrelated
skill changes separate. Skill versions are independent; the private root package
is development tooling. Follow [authoring conventions](docs/authoring.md) and the
[skill evaluation policy](docs/evals.md).

## Validate and review

1. Run `bun install --frozen-lockfile`, then `bun run check`, `bun run build`, and
   `bun run skills:versions`. Skill changes also need `bun run skills:scan`.
2. Run `bun run test:python:minimum` when changing Python scripts or their runtime
   requirements. This uses each skill's declared Python minimum and script metadata;
   development-only suites use the version in `.python-version`.
3. Run `bun run test:installed` for distribution or runtime changes. It requires
   Docker and network access to prepare the pinned image and CLI. It installs skills
   into a disposable project, compares bundled files, and exercises installed entry
   points (executable bits removed) through Python or Bash in a read-only container
   with networking disabled and no checkout or host credentials mounted. It is a
   deterministic smoke test, not a model eval.
4. Summarize results and anything not run in the PR template. For behavior changes,
   include reviewed paired-eval and trigger-selection conclusions. Keep raw evidence
   under ignored `eval/results/`; no live external mutations for evaluations.
5. Review the current commit, including changes to workflows and the validators
   themselves. Record the reviewed SHA and findings in the PR. After fixes or a
   base update, rerun relevant checks and review the resulting diff again.
6. Merge only after `Check`, `Security scan`, and `Skill versions` succeed, the
   branch is current with `main`, and review threads are resolved. Use a clear
   conventional PR title and a self-contained description for the squash commit.

CI runs the installed smoke test, minimum-runtime checks, and digest-pinned
actionlint in addition to the local repository checks. All of these feed the
existing `Check` job. The three required check names must remain stable; avoid
path-filtering the required workflow so skipped workflows do not leave PRs waiting.
Zero mandatory approvals accommodates solo maintenance; it does not guarantee
independent review. Request another person or a fresh agent review when appropriate.

One existing HAR inference error is excluded in `ty.toml` until the HAR feature
branch merges; remove that exclusion after merging the fix. Its unit and
minimum-runtime tests remain enabled.

### HAR schema transition

Keep HAR skill changes on `feat/har-workflow-graph`. Merge the CI/schema branch
first, then update the HAR branch from `main` before its eval migration lands. The
CI validator permits only the exact main HAR corpus, identified by
`LEGACY_HAR_EVAL_SHA256` in `scripts/validate-skills.ts`, to defer the new tags
and pressure policy. It emits a warning, and still checks assertions and every
existing rule. Any corpus change disables that exception and requires the complete
new schema. Remove the guard after the HAR migration merges. Validate the combined
branches meanwhile; the HAR branch's older validator does not understand case tags.

## Dependency maintenance

Dependabot opens grouped weekly Bun, Actions, and Python requirements updates.
Review bot PRs normally. Changes to installed script dependencies require a skill
version bump; test-only requirements do not. Do not automatically merge bot updates.

<!-- prettier-ignore -->
| Dependency source | Maintenance |
|-|-|
| `package.json`, `bun.lock` | Dependabot `bun` |
| Action references in `.github/workflows/` | Dependabot `github-actions`; preserve full SHAs |
| Skill test requirements and `scripts/installed-skills/requirements.txt` | Dependabot `pip`; add new requirement locations to its configuration |
| PEP 723 dependency ranges in skill scripts | Review manually; test declared entry points with `test:python:minimum` |
| `uvx`/`uv --with` pins (including `shellcheck-py`) and the skills CLI version in development scripts | Review manually; validate updated pins before committing |
| Docker image digests and evaluation-harness agent pins | Review manually; rebuild and rerun the affected smoke tests/harness checks |

The root Python version is in `.python-version`; CI pins uv separately. When
changing that runtime, also update `ty.toml` and the installed-test Docker image.
Per-skill minimums come from the skill's `compatibility` declaration. New Python
entry points must document a `Python X.Y+` minimum there. Release summaries belong
in reviewed PR descriptions or root documentation, not inside installed skills.

## Repository settings

The intended settings are version controlled in `.github/main-ruleset.json`,
`.github/repository-settings.json`, and `.github/actions-permissions.json`. They
require PRs and the three GitHub Actions checks, current base branches, and resolved
threads; block default-branch deletion/force pushes; allow only squash merges with
automatic branch cleanup; enable secret scanning, push protection, and Dependabot
security updates; default workflow tokens to read-only; require approval for
first-time fork contributors; and require action SHA pins. There is no routine bypass
actor. Administrators retain the ability to edit rules for recovery. Dependabot waits
seven days after a release before proposing a version update.

After validating a settings change, an administrator can apply the repository JSON
through `PATCH /repos/{owner}/{repo}` and each top-level key of the Actions JSON
through `PUT /repos/{owner}/{repo}/actions/<key>`. Create the ruleset
once, then update its existing ID; do not create duplicate rulesets. Before enabling
required checks, verify that all three names have been reported by GitHub Actions
(app ID `15368`) and match the workflow. Verify live settings after applying them.
These administration operations are intentionally not run by PR workflows, whose
token remains read-only.
