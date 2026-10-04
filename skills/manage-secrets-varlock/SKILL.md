---
name: manage-secrets-varlock
description: >-
  Adopts, migrates, debugs, validates, and improves Varlock / @env-spec
  environment variable management: .env.schema authoring, dotenv migration,
  multi-environment setup, CI/CD validation, framework integration, AI-safe
  secrets, leak scanning, and 1Password-backed secrets. Use when Varlock is
  named or when the user explicitly wants schema-driven environment
  configuration, dotenv migration, leak-safe validation, or secret-provider
  integration. Do not use for routine environment-variable or API-key questions;
  never force Varlock onto them.
license: MIT
compatibility: >-
  Requires shell access in the target project. Varlock JS package requires
  Node.js 22+; standalone binary works for non-JS projects. 1Password
  integration may require @varlock/1password-plugin and/or op CLI.
metadata:
  author: ddlaws0n
  version: "0.3.1"
---

# Varlock environment management

Use this skill to help users design, migrate, validate, or troubleshoot Varlock-backed environment configuration. Treat `.env.schema` as the safe, committed source of truth for config names, descriptions, types, validation rules, environment loading, and secret resolver references. Do **not** ask the user to paste secret values.

## Workflow

1. **Identify the project shape**
   - Check for `package.json`, framework config, monorepo tooling, existing `.env*` files, CI config, and any current dotenv usage.
   - For JS/TS projects, prefer project-local Varlock installed as a dependency. Check its version (`npm exec -- varlock --version` or the project's package-manager equivalent) against the [current documentation](https://varlock.dev/llms.txt); an older CLI may not recognize newer decorators.
   - For non-JS projects, prefer the standalone binary and `varlock run -- <command>`.

2. **Inspect current config without exposing secrets**
   - List environment-file names and inspect `.env.schema`, manifests, ignore rules, and code references; do not read, print, search, diff, or copy the contents of populated `.env*` files into agent context.
   - Use `varlock load --agent --format json-full` for redacted per-key validation errors and sources, or `varlock explain <KEY>` to debug one key. `varlock load --agent` alone returns a redacted flat JSON map; `--show-all` only changes the pretty failure view.
   - `--agent` only redacts items correctly marked sensitive. Review sensitivity annotations before trusting diagnostics. Never capture plain `--format json`, `json-full`, `env`, `shell`, `printenv`, `reveal`, or the output of a command that intentionally prints secrets in an agent transcript.
   - If raw values are required for local validation, ask the user to inspect them outside the agent transcript and report only redacted diagnostics.

3. **Create or improve `.env.schema`**
   - Before `varlock init --agent`, inspect repository state and preserve existing `.env.example`/manifest changes; init is non-interactive and may remove `.env.example` or install dependencies. Review its diff and generated schema against existing config references afterward.
   - Add root decorators first, usually:
     ```env-spec
     # @currentEnv=$APP_ENV
     # @defaultSensitive=false @defaultRequired=infer
     # @generateTsTypes(path=./env.d.ts)
     # ---
     # @type=enum(development, preview, production, test)
     APP_ENV=development
     ```
   - The current docs prefer `@generateTsTypes`. Older releases (for example v1.6.0) only support the legacy `@generateTypes(lang=ts, path=...)`; use that only when a project cannot upgrade, and verify the actual installed CLI.
   - Add every app dependency as a config item with a useful description, explicit `@type` when ambiguous, `@required` rules, and `@sensitive` for credentials.
   - Store non-sensitive defaults directly. Store secrets as empty required items, encrypted local values, `exec(...)`, or plugin resolver references. Choose `@defaultSensitive` intentionally: `false` requires explicit secret markings; `true` protects by default but can misclassify flags, ports, and environment names (which cannot safely be redacted).

4. **Choose the right project integration**
   - Framework integration when available: Next.js, Vite, Astro, Expo, etc.
   - `import 'varlock/auto-load'` for backend JS/TS where direct loading is practical.
   - `varlock run -- <command>` for non-JS, CLIs, migrations, AI coding tools, or places where code integration is not practical.
   - For monorepos, consider `@import()` for shared schemas and service-local schemas.

5. **Validate and iterate**
   - Run `varlock load --agent --format json-full` for redacted validation details; use exit status rather than parsing pretty output. Beware that resolvers may contact secret providers or prompt for desktop auth.
   - Run `varlock audit` to compare source references with schema keys and `varlock scan --staged` before committing (or `varlock scan` for the working tree; explicit paths for generated build output). Scan checks _resolved_ sensitive values, not arbitrary unknown secrets; it is not a substitute for reviewing git history and credential hygiene.
   - Fix schema errors, missing values, unsafe sensitivity markings, and environment-selection issues before finalizing.

6. **Summarize changes clearly**
   - Report what files changed, how environments resolve, where secrets live, and how developers/CI should run commands.
   - Include copy-paste commands for install, validation, dev, test, build, and production.

## References

- Read `references/schema-patterns.md` when creating or editing `.env.schema`, decorators, functions, data types, imports, or validation rules.
- Read `references/projects-and-integrations.md` when wiring Varlock into a real app, framework, package scripts, CI/CD, Docker, monorepo, or non-JS project.
- Read `references/onepassword.md` when the user mentions 1Password, `op://`, `op read`, 1Password Environments, service accounts, desktop app auth, vaults, or secret-zero handling.

## Scripts

- `scripts/varlock-project-check.sh PROJECT_DIR` performs a lightweight project check with `varlock load --agent --format json-full`, `varlock audit`, and `varlock scan`. It resolves secrets; ask before using it in projects where resolver side effects or interactive authentication are unexpected. Select the target environment via the project's own `@currentEnv` flag before calling it.

## Gotchas

- Never replace a secret with a fake placeholder value in `.env.schema`; use `@example` for examples and leave the actual value blank or resolved dynamically.
- `@currentEnv` must reference a config item defined in the same file or brought in by `@import`, usually `$APP_ENV`. Do not use `NODE_ENV` as the main environment flag unless the user explicitly requires it.
- Process environment variables have highest precedence. A shell or CI override can make local debugging look different from committed files.
- `.env.schema` should be committed. Plaintext `.env`, `.env.local`, and other populated override files should be ignored unless a specific file is verified to contain only safe public values. Generated type files may be committed or ignored according to the project's codegen policy.
- Sensitive values must never be statically inlined into browser/client bundles. When in doubt, mark the item `@sensitive`.
- In Turborepo strict environment mode, include the environment flag and other ambient values used by resolvers or CI detection in `globalEnv` or task `env` or Varlock may load the wrong environment.
- For 1Password desktop app auth, remember the user authenticates as themselves; do not enable it for production secrets unless explicitly intended.
- For production 1Password access, prefer narrowly scoped service accounts and separate production vaults/instances.

## Output

### Migration plan

````markdown
## Varlock migration plan

### Current state
- Existing env files:
- Current loading mechanism:
- Framework/runtime:
- Secret provider:

### Proposed target state
- Source of truth:
- Environment flag:
- Secret resolution:
- Runtime loading:
- CI validation:

### Changes to make
1.
2.
3.

### Commands
```bash
# install/init
# validate
# run app/tests/build
```

### Risks / follow-ups
-
````

### Final implementation summary

````markdown
## Varlock implementation summary

Changed:
- `...`

How to run:
```bash
varlock load --agent --format json-full
varlock run -- <command>
```

Secret handling:
- Sensitive values are resolved from ...
- No plaintext secrets were added to committed files.

Developer notes:
-
CI/CD notes:
-
````
