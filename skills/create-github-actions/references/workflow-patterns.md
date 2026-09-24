# GitHub Actions workflow patterns

Read this file when the task involves deployments, release publishing, reusable workflows, composite actions, matrices, caching, or security-sensitive workflow design.

## Trigger selection

| Scenario | Prefer | Avoid |
| --- | --- | --- |
| PR checks | `pull_request` | `pull_request_target` unless metadata-only and hardened |
| Branch CI | `push` to protected branches | broad `push` triggers with expensive matrices on every branch |
| Manual deploy | `workflow_dispatch` + `environment` | unconstrained manual deploys with global write permissions |
| Package release | protected tag push or manual promotion | publishing from arbitrary branch pushes |
| Nightly broad tests | `schedule` + `workflow_dispatch` | blocking normal PRs on slow optional matrices |
| Privileged follow-up after CI | `workflow_run` with strict branch/conclusion checks | trusting artifacts from untrusted PRs without validation |

## Permission selection

Start with:

```yaml
permissions:
  contents: read
```

Add job-level scopes only when needed:

| Capability | Typical permission |
| --- | --- |
| Comment on PR/issue | `pull-requests: write` or `issues: write` |
| Upload SARIF/code scanning | `security-events: write` |
| Publish GitHub Release | `contents: write` |
| Publish package to GitHub Packages | `packages: write` |
| Request OIDC token | `id-token: write` |
| Update deployment status | `deployments: write` |
| Attest/provenance where supported | `attestations: write` |

Do not grant these scopes at workflow level unless every job needs them.

## Deployment pattern

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment
        type: choice
        required: true
        options: [staging, production]

permissions:
  contents: read

concurrency:
  group: deploy-${{ inputs.environment }}
  cancel-in-progress: false

jobs:
  deploy:
    name: Deploy ${{ inputs.environment }}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: ${{ inputs.environment }}
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false
      - name: Deploy
        run: ./scripts/deploy.sh "${{ inputs.environment }}"
```

Replace the deployment command with the repository's real deployment script. Add cloud-specific credential actions only after confirming provider, role/audience, region, and environment approval model.

## Reusable workflow pattern

Use reusable workflows when multiple repositories or multiple workflows need the same job sequence.

```yaml
on:
  workflow_call:
    inputs:
      node-version:
        type: string
        default: "24"
    secrets:
      npm-token:
        required: false
```

Keep secrets explicit in `workflow_call`; do not use `secrets: inherit` unless repository ownership and trust boundaries are well understood.

## Composite action pattern

Use composite actions for repeated step sequences inside one repository.

```yaml
# .github/actions/setup-project/action.yml
name: Setup project
description: Install project dependencies
runs:
  using: composite
  steps:
    - uses: actions/setup-node@v6
      with:
        node-version-file: .nvmrc
        cache: npm
    - shell: bash
      run: npm ci
```

Composite actions inherit the caller job's permissions and secrets. Do not hide privileged behavior inside a composite action.

## Matrix pattern

Use fail-fast intentionally:

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-24.04, macos-15]
    node-version: [22, 24]
```

Keep PR matrices small. Put slow compatibility sweeps behind `schedule`, `workflow_dispatch`, or protected-branch pushes.

## Caching pattern

Prefer setup actions' built-in dependency caching when available. Use explicit cache keys only when built-in caching cannot express the dependency set.

```yaml
- uses: actions/setup-node@v6
  with:
    node-version-file: .nvmrc
    cache: npm
```

For `actions/cache`, include lockfile hashes:

```yaml
key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
```
