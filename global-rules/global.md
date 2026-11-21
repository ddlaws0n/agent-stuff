# Global agent rules

## Worktrees

Stay in your assigned worktree or workspace. Never switch branches, commit, or stash in a repository’s primary checkout unless the user explicitly asks. For work in another repository, create an Orca worktree there with `orca worktree create --repo <repo> --no-parent --name <task>` and make the changes in that worktree.

## Working practices

- Check files, git, and commands to resolve uncertainty. Ask a concise question when scope or preferences remain unclear, several approaches have materially different outcomes, or an action is hard to reverse.
- For work with three or more meaningful steps, track milestones, keep one in progress, and update it after validation. Report blockers and unresolved work before handoff. Skip tracking for simple tasks.
- Locate relevant sections with a search tool before reading large files. For files over 500 lines, read only the ranges needed. Avoid redundant reads, repeated file contents, and routine tool narration. Keep explanations proportional to the task.
- Follow project conventions. Prefer `.agents/rules` for agent-neutral project rules and retain Claude compatibility links where needed. Read rules referenced by the active project instructions before doing the work they cover.
- Check available skills for relevant specialized guidance. Skip specialized skills for routine coding where built-in tools suffice.
- When delegating, use bounded assignments and request outcomes under 2,000 characters. Verify results before accepting them.
- Use compact Markdown table separators (`|-|-|`) without padding. Avoid ASCII-art and box-drawing tables.

## Tool Preferences

### Python

- Always use `uv` instead of `pip`, `pip3`, `python -m pip`, or raw `python`
- `uv run` to execute scripts, `uv add` to install packages, `uv venv` for virtual environments, `uv sync` to install from a lockfile

### JavaScript / TypeScript

- Prefer `bun` over `node` as the runtime: `bun run`, `bun test`, `bun install`
- Fall back to `node` only when bun compatibility is an issue

### Package Management

- Prefer `bun install`, `bun add`, `bun run` over npm/yarn/pnpm equivalents
- If a lockfile dictates otherwise, use that tool: `package-lock.json` → `npm`, `pnpm-lock.yaml` → `pnpm`, `yarn.lock` → `yarn`. Do not migrate lockfiles without asking.

### Bun shell (`Bun.$`)

- `result.stdout` and `result.stderr` from ``Bun.$`...`.quiet()`` are `Buffer`, not `BunFile`: use `.toString()`, not `.text()`
- `.quiet()` captures output instead of passing it through; always use it when you need to read the output
- `Bun.$` throws a `ShellError` on non-zero exit by default; let it throw rather than checking `.exitCode`

### General

- Respect existing project conventions; if a project already uses a specific tool, do not switch without asking
- When creating new projects, default to the preferred tools above

## Secrets

- Never read, print, diff, or edit `.env`, `.env.*`, or `.dev.vars` files. Example, sample, and test variants (`.env.example`, `.env.sample`, `.env.test`) are fine.
- Never echo secret values, grep the environment for them, or put them literally in commands.
- Exception: varlock. `.env.schema` files are safe to read and edit, and `varlock load` (masked output) and `varlock run -- <command>` are the approved way to validate and use secrets. Use the `varlock` skill when a task involves environment variables.

<!-- context7 -->

Use the `ctx7` CLI to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service -- even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer -- your training data may not reflect recent changes. Prefer this over web search for library docs.

Do not use for: refactoring, writing scripts from scratch, debugging business logic, code review, or general programming concepts.

## Steps

1. Resolve library: `npx ctx7@latest library <name> "<user's question>"` — use the official library name with proper punctuation (e.g., "Next.js" not "nextjs", "Customer.io" not "customerio", "Three.js" not "threejs")
2. Pick the best match (ID format: `/org/project`) by: exact name match, description relevance, code snippet count, source reputation (High/Medium preferred), and benchmark score (higher is better). If results don't look right, try alternate names or queries (e.g., "next.js" not "nextjs", or rephrase the question)
3. Fetch docs: `npx ctx7@latest docs <libraryId> "<user's question>"`
4. Answer using the fetched documentation

You MUST call `library` first to get a valid ID unless the user provides one directly in `/org/project` format. Use the user's full question as the query -- specific and detailed queries return better results than vague single words. Do not run more than 3 commands per question. Do not include sensitive information (API keys, passwords, credentials) in queries.

For version-specific docs, use `/org/project/version` from the `library` output (e.g., `/vercel/next.js/v14.3.0`).

If a command fails with a quota error, inform the user and suggest `npx ctx7@latest login` or setting `CONTEXT7_API_KEY` env var for higher limits. Do not silently fall back to training data.
<!-- context7 -->
