# Varlock schema patterns

Use this reference when creating or editing `.env.schema` or other @env-spec `.env.*` files. Check the [current schema](https://varlock.dev/guides/schema/), [root decorators](https://varlock.dev/reference/root-decorators/), [item decorators](https://varlock.dev/reference/item-decorators/), and [data types](https://varlock.dev/reference/data-types/) when syntax or version support matters.

## File role

`.env.schema` should be the committed source of truth for:

- env var names and descriptions
- root decorators controlling loading behavior
- item decorators controlling requiredness, sensitivity, validation, generated types, and docs
- non-sensitive defaults
- secret resolver references, not secret values

## Recommended header

```env-spec
# @currentEnv=$APP_ENV
# @defaultSensitive=false @defaultRequired=infer
# @generateTsTypes(path=./env.d.ts)
# ---
# Current runtime environment. Controls .env.[APP_ENV] loading.
# @type=enum(development, preview, production, test)
APP_ENV=development
```

Prefer `APP_ENV`, `VARLOCK_ENV`, or a project-specific flag over `NODE_ENV`. `NODE_ENV` is often controlled by frameworks or tooling and can have unrelated semantics.

## Item pattern

```env-spec
# Clear human-readable description of why this config exists.
# @required=forEnv(production)
# @sensitive
# @type=string(startsWith=sk-)
# @docs("Provider API key docs", https://example.com/docs/api-keys)
# @example="sk-example"
SERVICE_API_KEY=
```

Use `@example` instead of fake default values. Empty/no value means `undefined` (and does not override a lower-precedence definition); `""` means an explicit empty string.

## Common decorators

Root decorators:

- `@currentEnv=$APP_ENV` — selects the current environment and enables `.env.[currentEnv]` loading.
- `@defaultRequired=infer|true|false` — default required behavior. `infer` means items with values/functions are required and blank items are optional.
- `@defaultSensitive=true|false|inferFromPrefix(PUBLIC_)` — default sensitivity, applied to items defined in that file only. Varlock's built-in default is `true`; `varlock init` commonly writes `false`. Mark public flags, numbers, and the environment flag non-sensitive when using `true`.
- `@generateTsTypes(path=./env.d.ts)` — generate TypeScript types in current releases. In monorepos with different per-package schemas, consider `exposeEnv=local` and `path=./env.ts`. Older CLIs (e.g. v1.6.0) only support the deprecated `@generateTypes(lang=ts, path=...)`; test against the installed version.
- `@import(./.env.shared)` or `@import(../shared-env/)` — share config across files/services.
- `@setValuesBulk(...)` — load many values from an external source, often with provider plugins.

Item decorators:

- `@required`, `@required=forEnv(prod)`, `@optional`
- `@sensitive`, `@sensitive=false`, `@public`; avoid marking short strings, booleans, numbers, or the `@currentEnv` flag sensitive—Varlock cannot reliably redact them.
- `@internal` — omit provider credentials/secret-zero tokens from app injection.
- `@type=...`
- `@example="..."`
- `@docs(url)` or `@docs("label", url)`

## Types to reach for

- `string(minLength=..., maxLength=..., startsWith=..., endsWith=..., matches=regex("^...$"))`
- `number(min=..., max=..., isInt=true, precision=...)`
- `boolean`
- `url(prependHttps=true, allowedDomains=[...], noTrailingSlash=true, matches=regex("^https://"))`
- `enum(development, preview, production, test)`
- `email(normalize=true)`
- `port(min=1024, max=9999)`
- `ip(version=4|6)`
- `domain`, `duration`, `array(email, minLength=0)`, `record(url)` for structured values
- `semver`, `isoDate`, `uuid`, `md5`; prefer `record` to legacy `simple-object`

When ambiguous, add `@type` explicitly. Quoted numbers remain strings unless coerced by `@type=number`.

## Values and functions

Values may be static, references, or resolver functions:

```env-spec
API_PORT=8080
API_BASE_URL=http://localhost:${API_PORT}
DATABASE_URL=exec(`op read "op://app-dev/db/url"`)
REGION=fallback($DEPLOY_REGION, "eu-west-2")
APP_ENV=remap($VERCEL_ENV, production, production, preview, preview, undefined, development)
```

Use bracketed references inside larger strings: `${API_PORT}`. Direct `$APP_ENV` is fine when the value is only the reference.

## Environment-specific files

With `# @currentEnv=$APP_ENV`, Varlock loads files in increasing precedence:

1. `.env.schema`
2. `.env`
3. `.env.local`
4. `.env.[currentEnv]`
5. `.env.[currentEnv].local`

Process environment variables have highest precedence. Use local override files for developer-specific values; keep secrets out of committed files unless they are encrypted or external resolver references.

## Imports

Use imports to share schema across monorepos or large projects:

```env-spec
# @import(../shared-env/)
# @import(./.env.features, FEATURE_X, enabled=eq($ENABLE_FEATURES, "true"), allowMissing=true)
# ---
SERVICE_NAME=api
```

Rules:

- File import paths must start with `./`, `../`, `/`, or `~/` and imported file names should begin with `.env.`. For monorepos, prefer `@import(../../, pick=[SHARED_KEY])` when the imported project's `.env.local` overrides should also load; importing `../../.env.schema` alone does not load those overrides.
- Directory imports end with `/` and inherit the current environment unless the directory defines its own `@currentEnv`.
- Later imports override earlier imports; the importing file overrides imported files. Use `pick=[...]` or `omit=[...]` to limit which shared keys a service inherits.

## Style conventions

- Use `ALL_CAPS_WITH_UNDERSCORES` keys.
- Use `# ---` dividers between logical sections.
- Be generous with descriptions and docs links.
- Keep quote style consistent; use triple quotes for multiline values.
- Avoid optional `export` prefixes.
- Do not add extra whitespace around `KEY=value`.
