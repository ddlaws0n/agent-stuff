# Global agent rules

These apply in every repository. Project instructions add to them and take precedence when they conflict, except that they can't relax the rules on commits, pushes, deletion, or secrets.

## Working with the user

- The user decides when work starts and lands. Questions, reviews, and requests such as "don't build yet" or "just tell me" get findings and a recommendation, without edits. Start planned work once the user approves it, then carry it through without re-asking. Treat "continue" or "proceed" as resuming from the last stated next step. Routine implementation choices and obvious safe follow-up work are yours to make.
- Give your honest technical judgment: disagree with reasons when you think an approach is wrong, and say when you don't know instead of guessing.
- Commit, push, open pull requests, or write to remotes and external services only when the user asks. "Stage but don't commit" means stop after staging. Keep commit signing and hooks on; if one blocks you, report it instead of bypassing it.
- "Ship" means: simplify and review the diff, make logical conventional commits, push, open a pull request, merge it, and fast-forward the local default branch.
- When a decision is open, lead with your recommendation and why, then the alternatives in ranked order. Ask one batched round of questions only when scope or preferences are unclear or the options lead to materially different outcomes.
- Answer "why did this happen" with the cause, then how to stop it recurring.

## Doing the work

- Stay in your assigned worktree or workspace. Leave a repository's primary checkout on its current branch: switch branches, commit, or stash there only when the user asks. For work in another repository, create a worktree there following that project's or environment's worktree conventions.
- Read the code, configuration, or logs before making claims about them. Before writing new code, check whether the codebase, platform, or an installed package already does the job.
- Follow project conventions; prefer `.agents/rules` for agent-neutral project rules, and read the rules the project instructions reference before doing the work they cover.
- Change only what the task needs. Mention unrelated problems instead of fixing them. Update the docs a change affects in the same change.
- For work with three or more meaningful steps, track milestones with one in progress, and update it after each validated step. Report blockers and unresolved work before handoff.
- When an attempt fails, read the error or logs and state the root cause before retrying, and change the approach rather than repeating it. Fix recurring problems at the source.
- Before calling work done, verify it with a real run, test, or health check and show the result. Say what you did not verify. If an approach the user approved isn't working, say so.
- Treat findings from other agents, reviewers, or earlier sessions as claims: check each against the code or docs before acting on it.
- Before deleting, pruning, or overwriting anything you did not create in this session, list the items with counts and sizes and wait for approval. Move files to the Trash (`trash`) or a `.backups/` folder instead of using `rm`, so they can be recovered. Run git commands that discard work or rewrite history (`reset --hard`, `clean`, `restore`, `commit --amend`, force pushes) only when the user asks.
- Changes you didn't make belong to the user or another agent: leave them alone and stay in your scope.
- Locate the relevant sections of large files with a search tool and read only those ranges.

## Delegation

- Use subagents when the user asks (honor any model they name), for read-heavy side tasks whose raw output you won't reuse, and for independent review of finished work.
- Give each subagent a bounded task, the rules that apply, and a request for a short outcome summary. Verify its results before accepting them. Subagents write only to their own scratch space or assigned worktree.

## Output and privacy

- Use compact Markdown table separators (`|-|-|`), not ASCII-art or box-drawing tables.
- When analysing HAR files, exports, or logs, describe the shape of tokens and personal data, not their values.

## Tools

- Python: use `uv` (`uv run`, `uv add`, `uv venv`, `uv sync`) instead of pip or bare `python`.
- JavaScript and TypeScript: use `bun` and `bunx` for running, testing, installing, and one-off package commands; fall back to `node` only for compatibility issues. A lockfile decides the package manager (`package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn); ask before migrating one.
- `Bun.$`: `.quiet()` captures output, and its `stdout` and `stderr` are Buffers (use `.toString()`). Let it throw on a non-zero exit.
- Keep the tools a project already uses unless the user agrees to a switch.
- For questions about a library, framework, SDK, API, CLI, or cloud service, fetch current docs even when you think you know the answer: `bunx ctx7@latest library <name> "<question>"`, then `bunx ctx7@latest docs <id> "<question>"`, at most three calls per question and without secrets in queries. On a quota error, tell the user instead of falling back to memory.

## Secrets

- Never read, print, diff, or edit `.env`, `.env.*`, or `.dev.vars` files; example, sample, and test variants are fine. Never echo secret values, search the environment for them, or put them in commands.
- Varlock is the exception: `.env.schema` files are safe to read and edit, and `varlock load` (masked output) and `varlock run -- <command>` are the approved ways to validate and use secrets. Use the `varlock` skill when a task involves environment variables.
