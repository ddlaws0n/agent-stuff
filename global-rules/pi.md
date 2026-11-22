## Pi tools

Before modifying Pi extensions, read `.agents/rules/working-with-pi.md`. Use Pi’s skill metadata and `read` to load an applicable SKILL.md. Use `bash` with `rg` or `grep` to locate file sections.

Use `todo` for non-trivial work with 3+ meaningful steps. Supported actions are `create`, `update`, `list`, `get`, `delete`, and `clear`; statuses are `pending`, `in_progress`, `completed`, and `deleted`. Create short tasks, then keep exactly one `in_progress` and update it immediately after each validated milestone. Never complete partial or failing work. Record blockers in the task description and report unresolved deferrals before handoff; delete cancelled tasks explicitly. Do not use `todo` for simple one-step or purely informational tasks.

- When you delegate, use fresh-context subagents and keep one writer per cwd/worktree.
- Enable subagents if needed and verify each required agent is executable. Pass the actual task, cwd, applicable rules, scope, and edit authority.
- Single agent: call `subagent` with `agent`, `context: "fresh"`, and `async: true`.
- Multi-step workflow: write exactly one fenced `js workflow` block, then call `subagent({ workflow: true, async: true })` in the same reply. Use awaited `runs.run(...)` calls with explicit task text and an explicit `return`; never pass scripts as JSON or use the removed top-level `chain` parameter.
- Yield for native completion; do not poll. On a launch/tooling failure, report the blocker rather than switching execution protocols. Inspect results and verify claimed changes before accepting them.

## Inline Bash

Successful `!{command}` expansions are factual user-provided context. The extension executes only its fixed informational allowlist, without a shell, for interactive input when `bash` is active. Blocked or failed expansions are not successful command output.
