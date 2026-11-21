## Claude tools

Use Grep to locate relevant sections and offset/limit to read them. Never call TaskOutput twice for the same task. Increase the timeout after a timeout.

## Subagents

- Delegate side tasks that would flood the main context with output you won't reuse (broad searches, full test runs, logs, large file reads). Ask for a short summary back.
- Delegate independent pieces of work that can run in parallel. Keep dependent or iterative work inline.
- Use a fresh subagent for independent review or verification, since it hasn't seen the reasoning. Don't delegate just to get a better answer; it uses the same model by default.
- Keep quick, targeted changes and multi-phase work that shares context in the main conversation. Subagents start fresh and cost extra tokens.
