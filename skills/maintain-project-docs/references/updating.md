# Updating project documentation

Use for targeted changes to existing documentation. Shared scope, evidence, stale-content, validation, and output rules live in `SKILL.md`.

## 1. Confirm the target

Use the files the user named. If the target is ambiguous, discover likely project-owned documentation and ask before choosing among materially different targets. Common locations include, but are not limited to:

- root documents such as `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`
- `docs/`, `doc/`, or repository-specific documentation trees
- package/module READMEs
- ADR directories such as `adr/`, `decisions/`, or `architecture/decisions/`

## 2. Read before editing

Understand the current document's audience, link graph, and style before changing it.

## 3. Make focused edits

- Preserve accurate content and the document's existing style.
- When a renamed concept or path appears in multiple in-scope documents, update all of them together.
- If the correction requires a new document, explain why and follow `references/creating.md` only when the user's request permits creating documentation.
- For a docs-vs-code freshness pass, compare each documented claim against the code and configuration, present the proposed diffs for review, and apply them only after the user approves.
