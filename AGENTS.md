# Agent instructions

This is the source repository for ddlaws0n's first-party Agent Skills, distributed from `skills/` via the `skills` npm CLI. The root Bun/TypeScript setup is **development tooling**, not a runtime dependency of installed skills.

## Layout and conventions

- Author published skills only under `skills/<name>/SKILL.md`, one flat, lowercase-hyphenated directory per skill. Keep references, assets, scripts, tests, and evals inside the same skill directory. Follow [docs/authoring.md](docs/authoring.md) for naming (`<verb>-<object>`), layout, frontmatter, section names, and evals; start new skills from `templates/skill-template/`.
- Follow the [Agent Skills specification](https://agentskills.io/specification). Required frontmatter: `name` (matching directory) and a description saying what it does **and when to use it**. Repository convention: `license: MIT`, `metadata.author: ddlaws0n`, `metadata.version: "<semver>"`, and a copy of root `LICENSE` within each skill so the notice travels with installations. Add `compatibility` only if necessary. Keep metadata values strings.
- Version each skill independently; bump its version when changing behavior, public workflow, or a bundled script (`bun run skills:versions`; CI checks pull requests). Skill versions are unrelated to the private root package version.
- Keep `SKILL.md` concise and self-contained. Refer to optional `references/` files from the skill root when detailed material is needed. Explain requirements for scripts/credentials in the skill itself. Do not write machine-specific absolute paths or put secrets in published files.
- `standard/` is the canonical source of the project docs standard. Never edit its synced copies in skills (`references/standard.md`, the synced `assets/*-template.md`, `assets/manifest.schema.json`) by hand: edit `standard/` and run `bun run standard:sync`; `bun run check` fails on drift.
- `.local/` is private scratch work and is ignored. Do not publish, move, or import it without explicit approval. Keep `CLAUDE.md` as a symlink to this file to avoid divergent instructions.

## Validation and evaluation

1. Run `bun install` after dependency changes; commit `bun.lock` with `package.json`.
2. Run `bun run check` before proposing a skill change; Lefthook runs a subset on commit and the full check plus `bun run skills:scan` on push. Keep Markdown tables compact (`|-|-|`) with `<!-- prettier-ignore -->` above each. `bun run build` compiles the TypeScript developer tooling, not the skills.
3. For skill behavior changes, follow `docs/evals.md`: realistic prompts, isolated with-skill and baseline runs, objective assertions plus human review. Keep all generated evidence, including audits, in the ignored `eval/results/` tree ([layout](docs/evals.md#results-layout)); commit only reviewed conclusions. Runs that mutate external systems need a fixture/sandbox or dry-run; never run live mutations just to evaluate a skill.
4. Check discovery with `npx skills add . --list` when adding/renaming skills. Without `--list` it installs files.

Preserve existing behavior and bundled files unless the task calls for changing them. Prefer focused edits; do not reformat unrelated skill prose.
