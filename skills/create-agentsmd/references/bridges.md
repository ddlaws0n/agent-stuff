# Cross-agent bridges

A bridge exists only so an agent that does not read `AGENTS.md` by default still sees it; `AGENTS.md` stays the single source of truth (standard.md § Content contracts, AGENTS.md and bridges).

## When to bridge

Bridge only when an agent in use does not read `AGENTS.md`. [standard.md § Agent loading reference](standard.md#agent-loading-reference) says which agents and versions need one and holds all version-specific facts.

## Claude Code bridge

A `CLAUDE.md` that imports the file, with optional Claude-only notes below:

```markdown
@AGENTS.md

## Claude Code

- Claude-only notes, if any.
```

- Prefer the import over a symlink: Windows and `core.symlinks=false` checkouts turn symlinks into plain text files.
- If a standalone `CLAUDE.md` already has content, audit it as an instruction file, merge shared guidance into `AGENTS.md`, and get the user's confirmation before replacing it with the import.

## Gemini CLI bridge

`GEMINI.md` is the default name and `context.fileName` takes a list: set `["AGENTS.md"]` when no `GEMINI.md` exists; otherwise list both (`["AGENTS.md", "GEMINI.md"]`) and review `GEMINI.md` as an instruction file. Change this only when the user uses Gemini CLI.

## Copilot

If `.github/copilot-instructions.md` already exists, keep it consistent with `AGENTS.md` without duplicating shared guidance. Do not create one unprompted.
