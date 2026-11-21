# Authoring skills

Conventions for every skill in `skills/`. `bun run skills:check` enforces the rules marked **(checked)**; the rest are review guidance. Start from [`templates/skill-template/`](../templates/skill-template/SKILL.md), which the validator also checks.

## Naming

- `skills/<verb>-<object>[-<tool>]/`: lowercase, hyphenated, at most 64 characters, matching the frontmatter `name` **(checked)**. Examples: `create-github-actions`, `manage-secrets-varlock`, `analyze-har-workflows`.
- Lead with what the agent does (`create`, `manage`, `analyze`, `review`), then the object. Add the tool only when it is the point of the skill.
- Renaming a published skill breaks existing installs. Treat it as a breaking change: bump the minor version (major after 1.0) and update the README catalog.

## Directory layout

Only these entries may appear in a skill directory **(checked)**:

<!-- prettier-ignore -->
| Entry | Purpose |
|-|-|
| `SKILL.md` | Required. Instructions loaded when the skill triggers. |
| `LICENSE` | Required. A copy of the root `LICENSE`, so the notice travels with installs. |
| `references/` | Detail the agent reads on demand, one level deep. |
| `scripts/` | Executable helpers. State runtime requirements in `compatibility`. |
| `assets/` | Templates and files the agent copies or fills in. |
| `evals/` | Required `evals.json` and `trigger-evals.json`; inputs under `evals/files/` or `evals/fixtures/`. |
| `tests/` | Required for bundled scripts: discoverable `test_*.py` tests; optional `tests/requirements.txt`. |

Everything in the directory is installed, so leave out READMEs, changelogs, audit notes, and per-skill `.gitignore` files. Audits, eval runs, and reviews go in the ignored `eval/results/` tree described in [evals.md](evals.md#results-layout).

## Frontmatter

```yaml
---
name: create-example
description: >-
  Creates example things with specific guarantees. Use when the user asks to
  create, review, or fix example things, or mentions example-file.yml. Do not
  use for adjacent-thing work.
license: MIT
compatibility: >-
  Requires Python 3.11+ and network access for the bundled lookup script.
metadata:
  author: ddlaws0n
  version: "0.1.0"
---
```

- Keys are limited to the spec's `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`, in that order **(checked)**. Avoid `allowed-tools` (experimental, agent-specific) unless a skill needs it.
- `description` (at most 1024 characters, **checked**) is the only text agents see before choosing a skill. Write it as a folded `>-` block **(checked)** in three parts:
  1. What the skill does, in the third person ("Creates…", "Manages…"), never starting with "Use" **(checked)**.
  2. `Use when…` followed by the requests, file types, tools, and phrases that should trigger it **(checked)**.
  3. Optionally `Do not use for…` naming near-misses the trigger evals exercise.

  Put the main use case and trigger words early. Descriptions over 600 characters and `Use when` after the first 300 characters produce advisory warnings, not failures. Preserve useful routing boundaries when shortening. The validator also prints an estimated catalog size for this checkout, not a universal host limit. Codex normally budgets 2% of its model's context window for discovery, falling back to 8,000 characters when that window is unknown ([OpenAI docs](https://learn.chatgpt.com/docs/build-skills)).

- Descriptions must not contain `<` or `>` **(checked)**; some agents reject them.
- `compatibility` (at most 500 characters) lists real runtime requirements only: tools, platform, network, authentication.
- `metadata` holds exactly `author: ddlaws0n` and a quoted SemVer `version` **(checked)**.

## Versioning

Each skill has its own SemVer version, independent of the root `package.json`. CI requires a bump whenever a skill's installed behavior can change: any file outside `evals/` and `tests/` (`bun run skills:versions`):

- **patch**: wording, formatting, or fixes that keep behavior and triggers the same.
- **minor**: new or changed behavior, workflow, scripts, trigger scope, or a rename.
- **major**: reserved for after 1.0.

## SKILL.md body

- At most 500 lines **(checked)**. Move detail into `references/` and say when to read each file.
- Write imperative instructions for an agent, not documentation for a person. Cover what the agent would get wrong without the skill; skip what it already knows.
- Use these section names. Use only the ones that apply, and put skill-specific sections in between:
  - `## Workflow`: numbered steps; required **(checked)**.
  - `## Scripts`: each script, its purpose, and how to run it; required when `scripts/` exists **(checked)**.
  - `## References`: when to read each reference or asset; required when `references/` exists **(checked)**.
  - `## Gotchas`: traps, non-obvious defaults, and safety limits.
  - `## Output`: the shape of the final response or report.
- Prefer one complete, realistic example over several partial ones. When examples illustrate categories, vary their order so the agent doesn't learn the sequence.
- When output must parse (JSON, YAML), say how to validate it and what to do if it is truncated or invalid.
- Run bundled scripts through their interpreter (`uv run scripts/tool.py`, `bash scripts/tool.sh`), never by bare path. Installers can drop the executable bit. The validator checks real bundled commands in shell examples and explicit execution instructions, while allowing path mentions, subcommand labels, and hypothetical consumer scripts **(checked)**.
- Python CLI entry points use an `if __name__ == "__main__":` guard and a PEP 723 `# /// script` block. Use valid TOML with `requires-python = ">=X.Y"` matching the documented `Python X.Y+` minimum; declare third-party `dependencies` (or `[]` for stdlib-only scripts). Metadata and matching minimums are **checked** for entry points; imported helper modules need no independent script block.
- Bundled Python and shell scripts need discoverable tests **(checked)**. The runner rejects zero collected tests. Test meaningful CLI behavior with fixtures: JSON must parse and contain required fields, exit status must match success/failure, and invalid input must not produce a success report. For mutation-capable tools, record attempted writes and prove dry-run sends none. Never use a live account for these tests.
- Every `scripts/`, `references/`, or `assets/` path mentioned must exist **(checked)**.
- Refer to bundled files relative to the skill directory. Never write home-relative or machine-specific paths such as `~/.agents/...` or `/Users/...` **(checked)**.
- Keep tables compact (`|-|-|`) and put `<!-- prettier-ignore -->` on the line above each one, so Prettier doesn't pad them into wasted context **(checked)**.

## Evals

Every skill ships two eval files **(checked)**:

- `evals/evals.json`: task-quality prompts with `id`, `prompt`, `expected_output`, nonempty `assertions` and `tags`, and optional `files`. The corpus includes a reviewed `pressure: {required, reason}` decision and distinct normal and boundary/failure cases **(checked)**. See [evals.md](evals.md) for tags, pressure coverage, and execution.
- `evals/trigger-evals.json`: an array of `{ "query", "should_trigger" }` covering both realistic triggers and near-misses. About eight of each works well. Duplicate normalized queries within a skill fail; shared positive queries across skills produce a review warning **(checked)**.

## Checks

<!-- prettier-ignore -->
| Command | What it runs |
|-|-|
| `bun run check` | TypeScript/Python type checks, oxlint/Ruff/ShellCheck, Bash syntax, workflow lint, Prettier, skill validators, and all unit tests |
| `bun run lint:shell` | Bash syntax and pinned ShellCheck for repository `.sh` files, including the eval launcher |
| `bun run skills:check` | Repository conventions above, the template, and the README catalog |
| `bun run skills:lint` | [agnix](https://github.com/agent-sh/agnix) skill rules in strict mode |
| `bun run skills:spec` | The official [skills-ref](https://github.com/agentskills/agentskills) validator, per skill |
| `bun run skills:scan` | [Cisco skill-scanner](https://github.com/cisco-ai-defense/skill-scanner) static security analysis (fails on high severity) |
| `bun run skills:versions` | Version bumps for skills changed since `origin/main` (or `BASE_REF`) |

Lefthook runs formatting, lint, and the skill validator on commit, and the full check plus the security scan on push. `bun install` installs the hooks.
