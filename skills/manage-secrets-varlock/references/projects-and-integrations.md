# Varlock project and integration patterns

Use this reference when wiring Varlock into an application, repository, CI job, Docker setup, or monorepo. Check the [current CLI](https://varlock.dev/reference/cli-commands/), [integration index](https://varlock.dev/integrations/overview/), and [monorepo guide](https://varlock.dev/guides/monorepos/) for stack- and version-specific behavior.

## Installation

JavaScript / TypeScript project:

```bash
npx varlock init --agent
# Alternatively: pnpm dlx varlock init --agent
# Or: bunx varlock init --agent
```

This installs Varlock where appropriate, scans existing `.env` files, and creates a starter `.env.schema`. Review the result manually.

Standalone binary:

```bash
brew install dmno-dev/tap/varlock
# Alternatively, inspect and run the verified installer documented at:
# https://varlock.dev/getting-started/installation/
varlock init --agent
```

## Core commands

```bash
varlock load --agent                      # flat redacted JSON
varlock load --agent --format json-full   # redacted per-key errors and metadata
varlock explain DATABASE_URL             # redacted single-key source trace
varlock run -- <command>
varlock audit                             # schema vs code references
varlock scan --staged                     # resolved secret leak check before commit
```

Use `load` for validation/debugging, `run` to inject resolved and validated env vars into a subprocess, `audit` to find schema/code mismatches, and `scan` to detect resolved sensitive values copied into files. `scan` defaults to non-ignored files; use explicit paths for build output. `varlock reveal` and `printenv` output raw values and belong only in human-only sessions. `varlock run` does not make arbitrary child-process output safe: piped output is redacted by default, but interactive TTY output passes through and an app can still leak unmarked secrets.

## package.json scripts

```json
{
  "scripts": {
    "dev": "varlock run -- vite dev",
    "test": "APP_ENV=test varlock run -- vitest",
    "build": "APP_ENV=production varlock run -- vite build",
    "migrate": "APP_ENV=production varlock run -- prisma migrate deploy",
    "env:check": "varlock load --agent --format json-full",
    "secrets:scan": "varlock scan"
  }
}
```

For frameworks with official integrations, prefer the integration and keep `varlock run` for external tools, scripts, migrations, and CLIs.

## JS/TS runtime patterns

Backend JS/TS direct load:

```diff
- import 'dotenv/config';
+ import 'varlock/auto-load';
```

Typed access:

```ts
import { ENV } from 'varlock/env';

console.log(ENV.API_BASE_URL);
```

For transitive dotenv usage, dependency overrides may be needed. In monorepos, apply overrides at the root.

## Non-JS projects

Use the standalone binary and wrap the app command:

```bash
APP_ENV=production varlock run -- python manage.py migrate
APP_ENV=production varlock run -- uvicorn app:app
APP_ENV=production varlock run -- go run ./cmd/server
```

## CI/CD

At minimum, add a validation step:

```yaml
- name: Validate environment schema without exposing marked secrets in logs
  run: varlock load --agent --format json-full
```

If the project needs resolved env vars in later steps:

```yaml
- name: Run tests with Varlock env
  run: APP_ENV=test varlock run -- pnpm test
```

For GitHub Actions, the [official Varlock action](https://varlock.dev/integrations/github-action/) can validate and export env vars. When using secret providers, inject only the secret-zero token or platform-native auth needed to resolve secrets. Never export resolved secrets through build arguments or commit them into image layers.

## Docker

Use the official image for validation:

```bash
docker run --rm -v "$(pwd):/work" -w /work -e PWD=/work ghcr.io/dmno-dev/varlock:<pinned-version> load --agent
```

Pin a tested image version; replace `<pinned-version>` above with the version used by the project. Or copy the binary into an app image with a multi-stage build. In Compose, run the app through Varlock at **runtime** only when the container needs provider resolution:

```yaml
command: ["varlock", "run", "--", "node", "app.js"]
```

## Git ignore policy

Typical policy:

```gitignore
# Ignore populated local and environment overrides unless reviewed as public
.env
.env.*
!.env.schema
# If other committed env-spec files contain only safe public values, allowlist them individually.
# Commit or ignore generated types according to the project's codegen policy.
```

Check the existing `.gitignore` before changing it; preserve intentional committed public `.env.*` files. If an AI/coding tool has its own ignore file, explicitly allow `.env.schema` there too. Never allow plaintext secret files into AI context or git history.

## Monorepos

Use one schema per service and import only shared keys. Directory imports include root local overrides; file imports include only that file. Ensure directory imports and paths remain available in Docker/CI:

```text
repo/
  .env.schema
  services/api/.env.schema
  services/web/.env.schema
```

The root `.env.schema` defines `APP_ENV` and `SHARED_KEY`; `services/api/.env.schema` imports them:

```env-spec
# @import(../../, pick=[APP_ENV, SHARED_KEY])
# @currentEnv=$APP_ENV
# ---
SERVICE_NAME=api
```

Turborepo strict mode gotcha: also pass any CI-detection variables and ambient resolver inputs needed by Varlock (not only the environment flag):

```json
{
  "globalEnv": ["APP_ENV"],
  "tasks": {
    "build": { "env": ["APP_ENV"] },
    "dev": { "env": ["APP_ENV"] }
  }
}
```

## Pre-commit scanning

Use `varlock scan --install-hook` or configure a hook manager. Stage-aware checks cover exactly the files to commit:

```bash
#!/bin/sh
varlock scan --staged
```
