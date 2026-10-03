# Varlock + 1Password patterns

Use this reference for `@varlock/1password-plugin`, `op://` secret references, service accounts, desktop app auth, and 1Password Environments. Check the [current plugin guide](https://varlock.dev/plugins/1password/) and [plugin installation rules](https://varlock.dev/guides/plugins/#installation) when implementing.

## Recommended model

- `.env.schema` is committed and contains schema metadata plus 1Password resolver references.
- Actual secret values remain in 1Password.
- Local development can use desktop app auth for convenience.
- CI/CD and production should use narrowly scoped service accounts.
- Production secrets should usually live in a separate vault and plugin instance from dev/preview secrets.

## Basic plugin setup

```env-spec
# @plugin(@varlock/1password-plugin)
# @initOp(token=$OP_TOKEN, allowAppAuth=forEnv(development), account=acmeco)
# ---
# 1Password service account token used outside local desktop-app auth.
# @type=opServiceAccountToken @sensitive @internal
OP_TOKEN=

# @required @sensitive
DATABASE_PASSWORD=op(op://app-dev/database/password)
```

In JS/TS projects, install the plugin as a dependency and reference it without a version (or with a compatible range check). For the standalone binary without a package.json, `@plugin(@varlock/1password-plugin@<exact-version>)` must use a pinned version. The `@internal` secret-zero item is resolved by Varlock but omitted from application injection, including when set in the ambient environment; only override this deliberately (e.g. nested Varlock runs).

## Vault and access design

1Password access is vault-scoped, not individual-field-scoped. If a vault mixes application secrets with unrelated sensitive data, create a dedicated app vault. Minimum recommended split:

- non-production app secrets vault
- production app secrets vault

For larger systems, split by environment, service, or team where it meaningfully limits blast radius.

## Service accounts for CI/prod

Create service accounts for machine-to-machine access and grant only the vaults/environments required. The token is the “secret zero” that unlocks other secrets.

Schema:

```env-spec
# @plugin(@varlock/1password-plugin)
# @initOp(id=prod, token=$OP_TOKEN_PROD, allowAppAuth=false)
# ---
# @type=opServiceAccountToken @sensitive @internal
OP_TOKEN_PROD=

# @required=forEnv(production) @sensitive
STRIPE_SECRET_KEY=op(prod, op://prod-app/stripe/secret-key)
```

Set `OP_TOKEN_PROD` in the deployment platform’s secret UI, not in committed files.

## Desktop app auth for local development

Desktop auth uses the installed `op` CLI and the local 1Password app. It may trigger biometric/system unlock. This is convenient but authenticates as the human user, who may have broader access than a service account.

```env-spec
# @plugin(@varlock/1password-plugin)
# @initOp(id=dev, allowAppAuth=forEnv(development), account=acmeco)
# ---
DEV_API_KEY=op(dev, op://dev-app/service/api-key)
```

Requirements:

- 1Password CLI installed and on `PATH`
- 1Password desktop app integration enabled
- Optional `account=` set when the user has multiple accounts

## Multiple instances

Use named instances to prevent accidental prod access in local workflows:

```env-spec
# @plugin(@varlock/1password-plugin)
# @initOp(id=dev, token=$OP_TOKEN_DEV, allowAppAuth=forEnv(development), account=acmeco)
# @initOp(id=prod, token=$OP_TOKEN_PROD, allowAppAuth=false, account=acmeco)
# ---
# @type=opServiceAccountToken @sensitive @internal
OP_TOKEN_DEV=
# @type=opServiceAccountToken @sensitive @internal
OP_TOKEN_PROD=

# @required @sensitive
PAYMENTS_API_KEY=op(dev, op://app-dev/payments/api-key)
```

`.env.production`:

```env-spec
PAYMENTS_API_KEY=op(prod, op://app-prod/payments/api-key)
```

## 1Password secret references

Individual fields use the format:

```text
op://vault-name/item-name/field-name
```

In the 1Password app, copy the secret reference from the field menu when possible. Prefer stable IDs in highly automated contexts where names may change.

## 1Password Environments

Use `opLoadEnvironment()` with `@setValuesBulk` to load a complete 1Password Environment instead of wiring each variable individually:

```env-spec
# @plugin(@varlock/1password-plugin)
# @initOp(token=$OP_TOKEN, allowAppAuth=forEnv(development), account=acmeco)
# @setValuesBulk(opLoadEnvironment(your-environment-id))
# ---
# @type=opServiceAccountToken @sensitive @internal
OP_TOKEN=

# @sensitive
API_KEY=
# @sensitive
DB_PASSWORD=
```

With a named instance:

```env-spec
# @initOp(id=prod, token=$OP_TOKEN_PROD, allowAppAuth=false)
# @setValuesBulk(opLoadEnvironment(prod, your-environment-id))
```

Verify the installed `op` CLI supports 1Password Environments when using desktop auth; use service account auth for headless CI/prod. `op()` and `opLoadEnvironment()` can cache provider results via the plugin's `cacheTtl` setting—choose an expiry appropriate to secret rotation.

## Fallback pattern: exec + op read

When the plugin is not available, use `exec()` with `op read`:

```env-spec
# @sensitive @required
ANTHROPIC_API_KEY=exec('op read "op://api-local/anthropic/api-key"')
```

Prefer the plugin for richer validation and named instances, but `exec()` is useful where adding plugins is impractical. Its command must not print secrets to stderr, and untrusted resolver scripts should be reviewed before executing them.

For memory-limited CI containers using service accounts, the plugin also supports `@initOp(token=$OP_TOKEN, useCliWithServiceAccount=true)`; install `op` CLI in the image. This avoids the SDK's larger WASM memory footprint without enabling interactive desktop auth.
