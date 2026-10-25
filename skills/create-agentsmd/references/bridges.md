# Cross-agent bridges

`AGENTS.md` is the single source of truth. A bridge exists only so an agent that does not read `AGENTS.md` by default still sees it. Never create a bridge without an `AGENTS.md`, and never copy its content into the bridge.

## Which agents need one

Loading behavior below was checked against vendor docs on 25 October 2026. Re-check when the user depends on a specific agent version.

<!-- prettier-ignore -->
|Agent|Loads|Bridge|
|-|-|-|
|Codex|Project root to cwd; per directory: override, then `AGENTS.md`, then configured fallbacks. 32 KiB combined budget, not per file.|None|
|pi|Agent directory plus ancestors to cwd; one file per directory, preferring override, `AGENTS.md`, then `CLAUDE.md`. No automatic descendant walk.|None|
|Claude Code|`AGENTS.md` natively since 2.1.277, normally suppressed by a `CLAUDE.md` or `CLAUDE.local.md` in the ancestors or cwd.|`CLAUDE.md` importing `@AGENTS.md` for older versions or when a `CLAUDE.md` exists|
|Gemini CLI|`context.fileName: ["AGENTS.md"]` is valid; file access triggers additional hierarchical discovery.|Gemini CLI setting, only for Gemini users|
|Cursor|Nested `AGENTS.md` applies automatically to relevant files, combined with parents.|None|
|Copilot|Cloud reads `AGENTS.md`, including nested files with nearest precedence. VS Code's local harness needs experimental nested discovery enabled.|None in cloud|

Sources: [Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude Code](https://code.claude.com/docs/en/memory), [pi](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/src/core/resource-loader.ts), [Gemini CLI](https://geminicli.com/docs/cli/gemini-md/), [Cursor](https://cursor.com/docs/rules), [Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions).

## Claude Code bridge

A `CLAUDE.md` that imports the file, with optional Claude-only notes below:

```markdown
@AGENTS.md

## Claude Code

- Claude-only notes, if any.
```

- Imports resolve relative to the containing file, up to four hops.
- Prefer the import over a symlink. Windows and `core.symlinks=false` checkouts turn symlinks into plain text files, and Claude's edit tools refuse to write through a symlink (symlinks do load).
- If the repo already has a working `CLAUDE.md` symlink to `AGENTS.md`, keep it unless the user asks to replace it. Edit `AGENTS.md`, not the link.
- If a standalone `CLAUDE.md` already has content, audit it as an instruction file, merge shared guidance into `AGENTS.md`, and get the user's confirmation before replacing it with the import.

## Gemini CLI bridge

`GEMINI.md` is the default name and `context.fileName` takes a list: set `["AGENTS.md"]` when no `GEMINI.md` exists; otherwise list both (`["AGENTS.md", "GEMINI.md"]`) and review `GEMINI.md` as an instruction file.

## Copilot

If `.github/copilot-instructions.md` already exists, keep it consistent with `AGENTS.md` without duplicating shared guidance. Do not create one unprompted.
