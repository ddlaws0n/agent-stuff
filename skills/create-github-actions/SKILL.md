---
name: create-github-actions
description: >-
  Creates, edits, reviews, and troubleshoots secure GitHub Actions workflows,
  reusable workflows, and composite actions with minimal permissions, verified
  action versions, and static validation. Use when working on CI/CD pipelines,
  release automation, deployments, action version upgrades, OIDC authentication,
  permissions, caching, artifact handling, or files under .github/workflows and
  .github/actions, especially secure workflow YAML, pull request checks,
  test/build matrices, environment-gated deploys, or workflow failure fixes.
license: MIT
compatibility: >-
  Optional network access plus Python 3.11+ and uv or pipx to run the bundled
  action-release lookup and workflow validation scripts.
metadata:
  author: ddlaws0n
  version: "0.1.2"
---

# Create GitHub Actions workflows

Design, edit, audit, and validate GitHub Actions workflows. Optimize for secure trust boundaries, minimal permissions, maintainable YAML, clear failure modes, and action versions verified from live metadata when network access is available.

## Workflow

1. Inspect the repository before writing YAML:
   - `.github/workflows/`, `.github/actions/`, existing workflow failures, scripts, Makefile/task runner, Dockerfiles, package manifests, lockfiles, deployment config, and release config.
   - language/runtime, package manager, monorepo layout, test/build commands, branch strategy, release/deploy target, environment names, required secrets, and whether forks are expected.
2. Classify the request:
   - **CI/quality gate**: lint, typecheck, test, build, scan.
   - **release/publish**: package publishing, GitHub Releases, changelog, provenance, tags.
   - **deploy**: cloud/service deployment, environment approvals, OIDC, rollback path.
   - **reuse**: reusable workflow or composite action.
   - **repair/audit**: fix failing YAML, unsafe permissions, unpinned actions, caching, matrix, or trigger issues.
3. Choose the smallest workflow architecture that satisfies the request. Prefer one clear workflow unless permissions, triggers, runtime cost, or ownership justify splitting.
4. Classify each trigger by trust boundary:
   - **Untrusted code**: `pull_request` from forks. No secrets. Read-only token. Avoid executing untrusted text directly in shell.
   - **Trusted branch/tag**: `push`, protected branches, protected tags, and trusted `workflow_dispatch`. Secrets only in jobs that need them.
   - **Privileged release/deploy**: environment-gated jobs, explicit write scopes, OIDC/federated credentials where possible.
5. Resolve third-party action versions when network access is available:
   ```bash
   uv run scripts/fetch-action-release.py actions/checkout --format text
   uv run scripts/fetch-action-release.py actions/setup-node --format text
   ```
   If network is unavailable, state that versions were not verified and choose conservative, explicit pins based on repository context.
6. Write or edit YAML with focused changes. Preserve repository conventions unless they are unsafe or broken.
7. Validate before finalizing:
   ```bash
   uv run scripts/validate-workflows.py .github/workflows --format text
   # For privileged release/deploy workflows:
   uv run scripts/validate-workflows.py .github/workflows/deploy.yml --require-sha --strict
   ```
   Also run project-native checks where available, such as `npm test`, `pnpm test`, `pytest`, `go test ./...`, or the repository's documented CI command.

## Architecture defaults

<!-- prettier-ignore -->
| Need | Default pattern |
|-|-|
| Small project CI | one `ci.yml` with lint/typecheck/test/build jobs |
| Expensive matrices | small PR matrix; broader scheduled or main-branch matrix |
| Release publishing | protected tag or manual trigger; narrow write permissions; provenance where supported |
| Deployment | trusted branch or manual trigger; environment approvals; OIDC; serialized concurrency |
| Repeated steps inside one repo | composite action in `.github/actions/<name>` |
| Repeated jobs across repos | reusable workflow with `workflow_call` |
| Security/code scanning | separate workflow only when permissions, schedule, or ownership differ from CI |

Split workflows when trust boundaries differ. A workflow that handles untrusted PRs should not also hold deploy credentials.

## Security rules

- Set `permissions:` explicitly. Start with `contents: read`; add scopes only where needed, preferably at job level. Never use top-level `permissions: write-all`.
- Do not use `pull_request_target` to check out, build, test, or run untrusted PR code. Use it only for hardened metadata-only automation unless the design is intentionally privileged and reviewed.
- Prefer OIDC/federated identity over long-lived cloud credentials. Grant `id-token: write` only to the job that needs OIDC.
- Store staging/production secrets in GitHub Environments and use required reviewers for sensitive environments.
- Treat PR title, body, labels, branch names, issue comments, and other event text as untrusted. Pass them through `env:` and quote shell variables instead of interpolating `${{ github.event... }}` directly inside `run:`.
- Pin third-party actions explicitly. For high-risk, privileged, or deployment workflows, prefer full commit SHAs and record the human-readable version in a comment.
- Use `persist-credentials: false` on checkout when subsequent steps do not need `GITHUB_TOKEN`-backed Git authentication.

## Maintainability rules

- Keep workflow YAML orchestration-focused. Move shell logic longer than about 5-10 lines into repository scripts or Makefile/task targets.
- Name workflows, jobs, and steps so the GitHub Actions UI explains what is happening without reading logs.
- Add `timeout-minutes` to every job that could hang.
- Use `concurrency`:
  - PR/branch CI: cancel stale runs.
  - Deployments: serialize by environment; usually do not cancel in-progress production deploys.
- Cache dependencies only when lockfiles exist. Include lockfile hashes in cache keys.
- Upload artifacts once and reuse them downstream rather than rebuilding the same output.
- Use `$GITHUB_STEP_SUMMARY` for information developers will read: test summaries, artifact links, deployment URLs, scan summaries.

## Common patterns

### PR-safe CI skeleton

Start from `assets/node-ci.yml` and swap the setup, install, and test steps for other stacks. Keep its explicit read-only `permissions`, stale-run `concurrency`, job `timeout-minutes`, and `persist-credentials: false`. Its action versions are examples; verify them with `scripts/fetch-action-release.py` when possible.

### Safe handling of untrusted text

```yaml
- name: Print pull request title safely
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: |
    printf 'Pull request title: %s\n' "$PR_TITLE"
```

## Scripts

- `scripts/fetch-action-release.py` — Fetches latest GitHub Action release/tag context and emits text or JSON for version selection. Sends `GITHUB_TOKEN` from the environment, if set, to avoid API rate limits.
- `scripts/validate-workflows.py` — Performs heuristic static checks for workflow YAML, top- or job-level permissions, timeouts, action and reusable-workflow pinning, dangerous triggers, cache keys, and unsafe shell interpolation. Use `--require-sha` for privileged workflows.

## References

- Read `references/workflow-patterns.md` when the request involves cloud deployment with OIDC, protected environments, release publishing, reusable workflows, or composite actions.
- `assets/node-ci.yml` is a starting point for Node.js CI.

## Gotchas

- Static validation is heuristic and cannot prove a workflow safe. Review event-specific trust boundaries, expression flow, called workflows, and runtime scripts manually.
- PyYAML and some generic YAML parsers treat `on` as a boolean unless configured. Use GitHub-Actions-aware parsing when validating workflow files.
- `pull_request_target` runs in the context of the base repository and can access configured token permissions/secrets. Never combine it casually with checkout or execution of PR-controlled code.
- `workflow_run` is also a trust-boundary transition. Treat downstream privileged workflows as deploy/release workflows, not normal CI.
- `github.ref` differs across `pull_request`, `pull_request_target`, `push`, tags, and reusable workflows. Be explicit about whether a workflow should run against the merge ref, head SHA, tag, or protected branch.
- Scheduled workflows run on the default branch and can go stale if dependencies or secrets change without PR coverage.
- `actions/cache` restore keys can restore stale dependencies. Lockfile-based keys reduce cross-branch surprises.
- GitHub-hosted runner labels such as `ubuntu-latest` move over time. Pin OS versions when compiler/toolchain drift matters.

## Output

When returning workflow changes, include:

1. Files created or changed.
2. Why the workflow structure was chosen.
3. Security-sensitive assumptions, especially secrets, environments, `pull_request_target`, `workflow_run`, OIDC, and write permissions.
4. Action versions verified, including any versions that could not be verified.
5. Validation performed and commands the user should run locally.
