# Agent Stuff

First-party [Agent Skills](https://agentskills.io/) by [ddlaws0n](https://github.com/ddlaws0n). Each skill is a portable `SKILL.md` plus any scripts, references, and assets it needs. The public catalog lives in `skills/`.

## Install

The [`skills` npm CLI](https://github.com/vercel-labs/skills) installs directly from GitHub.

```sh
npx skills add ddlaws0n/agent-stuff --list
npx skills add ddlaws0n/agent-stuff --skill manage-github-projects
# Choose your agent and project/global scope interactively, or specify them:
npx skills add ddlaws0n/agent-stuff --skill manage-github-projects -a pi -g -y
```

Until the repository is published, inspect locally with `npx skills add . --list`. Installed skills may need their own tools or credentials; see each `SKILL.md`.

## Catalog

| Skill | Purpose |
|-|-|
| [`manage-github-projects`](skills/manage-github-projects/SKILL.md) | Manage GitHub Projects v2 boards and their issues via `gh` and Python. |

## Author a skill

Create `skills/<name>/SKILL.md` (flat layout) and copy the root `LICENSE` into that directory so the license notice accompanies installations. The directory and `name` must match. Put optional supporting material in `scripts/`, `references/`, or `assets/` inside that directory. Keep the skill self-contained: consumers install skills, not this repository's dev dependencies.

Use this frontmatter (quoted version is a string, not a YAML number):

```yaml
---
name: my-skill
description: Do a specific task. Use when the user asks for the task or mentions its relevant context.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.0"
---
```

- `name` and `description` are required by the [Agent Skills specification](https://agentskills.io/specification). Write descriptions for **both** capability and trigger conditions; keep them specific and under 1024 characters.
- `license: MIT`, `metadata.author`, and `metadata.version` are this repository's conventions. Version each skill independently with SemVer; bump it when its behavior or interface changes, and use a patch bump for corrections. The root `package.json` version does not version skills.
- Add `compatibility` only for actual runtime requirements (tools, platform, network, authentication); explain setup in the body. Avoid `allowed-tools` unless an agent-specific need justifies its experimental portability trade-off.
- Prefer concise instructions and relative links to on-demand references. Never embed secrets or unpublished/private material in a public skill.

## Develop

[Bun](https://bun.sh/) is needed for repository checks and TypeScript tooling; [uv](https://docs.astral.sh/uv/) is needed to run the Python tests:

```sh
bun install
bun run check          # typecheck, lint, format, skill/eval validation, Bun and Python tests
bun run test:python    # run only the Python workflow-validator tests (uv installs PyYAML)
bun run build          # compile the repository's TypeScript tooling to dist/
bun run format         # format TypeScript/JSON configuration
```

`bun run skills:check` validates skill metadata and eval definitions. For per-skill output quality, trigger selection, safety, and baseline comparisons, see [docs/evals.md](docs/evals.md). `AGENTS.md` contains contributor guidance (also linked as `CLAUDE.md`).

## License

[MIT](LICENSE). Individual skills declare the same license in their frontmatter.
