---
name: manage-secrets-1password
description: >-
  Runs the 1Password CLI (op) from an agent shell with the fewest desktop-app
  approval prompts and without exposing secret values: batching every lookup
  into one process, reading item metadata without values, creating items from
  generated or piped values, and diagnosing op failures. Use when an agent
  needs to call op, op read, op run, op inject, or op item, resolve op://
  references, or run a tool whose secrets resolve through 1Password, or when
  the user complains about repeated 1Password prompts. Do not use for writing
  Varlock .env.schema files or designing vault and service-account layouts.
license: MIT
compatibility: >-
  Requires the 1Password CLI (op) v2 and either the 1Password desktop app with
  CLI integration enabled or a service-account token. Examples assume macOS or
  Linux.
metadata:
  author: ddlaws0n
  version: "0.1.1"
---

# 1Password CLI for agents

## Why agents trigger so many prompts

With desktop-app integration, op ties an authorization to the terminal session: on macOS and Linux the session ID comes from the current TTY plus its start time, and it extends to sub-shells. Agent shell tools usually start a new process with **no TTY** for every command (`tty` prints `not a tty`), so no authorization carries over, and every command that reaches 1Password can ask for approval again. That includes anything that resolves secrets indirectly: `varlock run`, `op run`, a package script wrapping either, or an `exec(op read ...)` resolver.

## Workflow

1. **Detect the auth mode without touching secrets.**
   - If `OP_SERVICE_ACCOUNT_TOKEN` is set (check with `[ -n "$OP_SERVICE_ACCOUNT_TOKEN" ]`, never print it), op uses the service account: no prompts, but only the vaults it was granted.
   - Otherwise op uses desktop-app integration. `op account list` shows configured accounts without prompting.
   - `op whoami` reports `account is not signed in` under app integration even when op works. That message is not a failure.
2. **Plan every 1Password access before the first call.** List the secrets, item lookups, and writes the task needs, including the tools that resolve secrets themselves (for example `varlock run -- <cli>`). Find wrapper scripts in `package.json`, `Makefile`, or `.env.schema` so you know which commands prompt.
3. **Batch them into one tool call.** Put every op-dependent command for the step into a single shell invocation, so op authorizes once. See [Batching patterns](#batching-patterns).
4. **Tell the user before the batch.** Say in one line how many prompts to expect ("this will ask 1Password once") and what the batch does. If op is likely locked, ask them to unlock it first.
5. **Keep values out of the transcript.** Resolve secrets straight into the consuming command's environment or stdin. Test that a reference resolves with `op read "$REF" >/dev/null && echo ok`, never by printing it.
6. **On failure, diagnose once, then ask.** Do not retry op commands in a loop: each retry can prompt again. See [Diagnosing failures](#diagnosing-failures).

## Batching patterns

Wrap all dependent commands once so they share the resolved environment. Use the wrapper configured by the project:

```bash
varlock run -- sh -c 'cmd-one && cmd-two && cmd-three'
# Or, for a project using op references in an env file:
op run --env-file=.env.op -- sh -c 'cmd-one && cmd-two && cmd-three'
```

- Write intermediate results to files inside the batch and read them in later, prompt-free tool calls (`jq` on the saved JSON), instead of re-querying.
- Look items up once: `op item list --vault V --format json` and filter with `jq`, rather than one `op item get` per candidate.
- Keep secret-free calls out of the batch only when they come first and decide what the batch does. Otherwise include them: an extra command costs nothing, an extra prompt costs the user.

## Reading and writing items safely

- `op item get` conceals sensitive fields unless you pass `--reveal`. Never pass `--reveal` in an agent transcript. `op item list` returns metadata only.
- Pass `--fields label=username` only for non-secret fields you need to see.
- Never put a secret in a command's arguments (`op item create ... password=<value>`): arguments are visible to other processes and land in shell history and transcripts. Use `--generate-password` or pipe a JSON template on stdin: `op item template get Login | jq '...' | op item create --vault V -`, building the value inside the pipe.
- To copy a secret from 1Password into another system (an n8n credential, a CI secret store), pipe it from `op read` straight into that system's CLI or API in the same process. Some Node and Bun CLIs fail on piped stdin with `EAGAIN`. Then write the payload to a private temp file instead (`umask 077; D=$(mktemp -d); trap 'rm -rf "$D"' EXIT`) and pass it with the CLI's `--file` flag.
- Inside a wrapper such as `varlock run -- bash -c '...'`, project binaries (`node_modules/.bin`) are not on `PATH`. Call them by relative path, or every failed attempt costs another prompt.
- Report item locations as `op://vault/item/field`, never values.

## Diagnosing failures

Check these in order, inside one tool call where possible:

1. `command -v op && op --version`: the CLI exists.
2. `op account list`: the account is configured. An empty list means `op account add` or app integration is not set up.
3. `pgrep -lf 1Password`: the desktop app is running. A process started with `--just-updated` means the app updated and restarted, and it is locked until the user unlocks it.
4. One real call, for example `op vault list >/dev/null && echo ok`. If it fails, ask the user to unlock 1Password and confirm that **Settings > Developer > Integrate with 1Password CLI** is on, then wait for their reply before retrying.

## Gotchas

- An authorization lasts until 10 minutes of inactivity, with a 12-hour hard limit, and locking the app revokes it. Agents without a TTY rarely benefit from that window: plan for one prompt per process.
- An `exec(op read ...)` resolver in `.env.schema` runs on every `varlock run`. Every wrapped CLI call is an op call.
- `--cache` (the default on Unix) caches item data in a daemon to reduce API calls. It does not remove approval prompts.
- A service account removes prompts for headless or long agent sessions, but its token is a "secret zero". Suggest one to the user; do not create or store one without their approval.
- Prompts are per account. A batch that touches two accounts can prompt twice.

## Output

Before an op batch: one line naming the expected prompt count and what the batch does. After it: outcomes per item as `op://` references or item titles with `ok` or the redacted error, never values. When op is blocked, state what was checked and the single action the user needs to take.
