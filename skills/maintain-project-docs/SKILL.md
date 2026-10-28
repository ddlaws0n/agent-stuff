---
name: maintain-project-docs
description: >-
  Creates, updates, consolidates, and reorganizes project-owned Markdown
  documentation such as README, CONTRIBUTING, SECURITY, ADRs, plans, glossary,
  runbooks, architecture maps, guides, research notes, post-mortems and audit
  records, and package READMEs, verifying commands
  and links against the repository and gating moves or deletions behind an
  approved plan. Use when the user asks to write, refresh, or fix stale commands
  or broken links in project docs, record a decision as an ADR, start or finish
  a multi-session plan, add a glossary, runbook, or architecture map, sync docs
  after a migration, or deduplicate, move, or remove documentation files.
  Do not use for AGENTS.md, CLAUDE.md, GEMINI.md, or
  .github/copilot-instructions.md (use create-agentsmd), CHANGELOG maintenance
  (use update-changelog), summarizing docs without edits, code comments or
  docstrings, generated API reference, or agent and skill definitions.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.2.0"
---

# Maintain project documentation

Create and maintain accurate project-owned documentation without expanding scope silently, breaking links, or deleting content without approval.

## Workflow

1. Classify the request and follow the matching reference; it holds only mode-specific steps, and the rules below apply to every mode.
   - New document or documentation structure: `references/creating.md`.
   - Targeted edits to existing documents: `references/updating.md`.
   - Deduplication, reorganization, moves, broad rewrites, or deletion: `references/consolidating.md`.
2. Bound scope to tracked, project-owned files (see Gotchas).
3. Verify every command, version, path, and behavior you write against manifests, code, tests, CI, configuration, release metadata, or an authoritative external source when current library behavior matters. Reuse repository terminology. Never invent commands, file contracts, or versions; mark unverified external or future-facing claims. Moving text does not verify it: when you move, split, or label text canonical, re-check every port, address, binding, exposure, and access rule in it against the file that defines it.
4. Gate destructive work. Separate safe targeted edits from approval-gated actions, and list every proposed create, rewrite, move, and delete with its link impact. Get explicit user approval before:
   - deleting documentation
   - moving or renaming files
   - broad rewrites across many files
   - repurposing an operational instruction file

   If approval is not available, stop after the plan or apply only independently safe, explicitly requested edits. Targeted edits the user explicitly requested need no extra gate.

5. Apply the change, keeping edits within the requested scope.
6. Validate using the checklist in Gotchas, then report using Output.

## References

- `references/creating.md`: read for any new document; it holds the per-type document contracts.
- `references/updating.md`: read for focused edits to existing documents and docs-vs-code freshness checks.
- `references/consolidating.md`: read before planning any move, delete, merge, or multi-file rewrite; it holds the plan format.
- `references/standard.md`: the project docs standard. Read § How to apply this standard, § Layout, § Doc types, and § Content contracts for where a document lives and what it must contain, § Manifest for path and budget overrides, and § Trust and safety for plans and generated docs.
- `assets/readme-template.md`, `assets/contributing-template.md`, `assets/security-template.md`, `assets/guide-template.md`, `assets/adr-template.md`, `assets/plan-template.md`, `assets/glossary-template.md`, `assets/runbook-template.md`, `assets/architecture-template.md`: read only the template for the requested document type. Remove unused sections, every placeholder, and the leading `Synced from` comment of the last five before finishing.

## Gotchas

- **Scope excludes non-owned content.** Exclude dependencies, generated output and sites, vendored content, caches, build directories, coverage, fixtures, temporary or tool workspaces, and archived snapshots unless the user explicitly includes them. Choose a document's path from `docs/manifest.json` when it declares one for that type (for example `paths.decisions: "adr"`), else the repository's existing locations, else standard.md § Doc types; never impose a universal `docs/` taxonomy. Budgets come from standard.md § Context tiers and budgets, with manifest overrides.
- **Markdown that CI or a tool reads is configuration.** Before editing or moving a file, `git grep` its path in CI config and scripts. If one reads it, it is configuration: leave it unchanged and report it (standard.md § How to apply this standard).
- **AGENTS.md, CLAUDE.md, GEMINI.md, and `.github/copilot-instructions.md` are load-bearing agent configuration.** Do not author, rewrite, or overwrite them here, even as a side effect; use the create-agentsmd skill. Moves and rewrites can change agent behavior, so leave them in place, honor nested precedence, and update only the paths they reference.
- **Current guidance must be current.** Correct stale commands, versions, paths, and behavior, and remove unsupported instructions by default; version control preserves history. Do not hide obsolete copy-paste commands in collapsible "legacy" sections. Keep migration guidance only while readers still operate that version, labeled with the affected version or date, replacement, support or removal status, and owner when applicable.
- **One authoritative source per fact.** Summarize and link instead of copying instructions that will drift. A short quick start may repeat a command if it links to the full source. Never copy values a config file declares (image pins, ports, networks, volumes); name and link the file.
- **Split rather than summarize.** When a file is too long, split it by topic; summarizing loses content. Draft code and configuration in a plan stay until the work lands (standard.md § Content contracts, Plans).
- **Replace an unsafe instruction, don't just remove it.** Name the approved way to do the job, or who to escalate to (standard.md § Trust and safety).
- **Docs-site navigation breaks silently on moves.** Search for and update nav config such as `mkdocs.yml`, Docusaurus `sidebars.js`, VitePress `config`, `SUMMARY.md`, or `_toc.yml` alongside relative links.
- **CHANGELOG.md belongs to update-changelog.** Do not create or edit it here, even as a side effect of a docs sync; that skill also detects generated changelogs. Report any changelog content that needs a follow-up.
- **Check links concretely.** Use relative links for repository-local content. After a move or rename, `git grep -n 'old/path'` and `git grep -n 'old-anchor'` must return nothing outside intended history. Resolve each changed relative link against the file's directory, respect case-sensitive paths, and match anchors to actual heading slugs. Use a repository link checker (for example `lychee` or `markdown-link-check`) when one is configured.
- **Examples must run.** Use safe placeholders, never secrets, include a verification signal, and state when an example was not run. Use four backticks for an outer Markdown example that contains triple-backtick fences.
- **Validate before finishing.** Check every changed link and anchor as above; run documented commands and examples where practical; check Markdown formatting and fenced blocks; search for unresolved placeholders and for stale variants of renamed terms, versions, paths, and commands, and for conflicting versions; confirm no secrets, private data, or unsupported values were introduced; review the final diff for unrelated rewrites, generated or vendored edits, and lost or accidentally changed instruction content. After a multi-file change, audit removals (consolidating.md step 5).

## Output

List created, changed, or moved files; facts corrected and evidence used; security-relevant claims (exposure, ports, bindings, authentication, access rules, credential handling) as their own list, each verified, corrected, or unverified; deliberate deletions with their `git show` pointers; validation performed and anything not run; assumptions and unresolved uncertainty or conflicts; and approval-gated, approved-but-unperformed, or out-of-scope work left undone, with any residual link or tooling limitations.
