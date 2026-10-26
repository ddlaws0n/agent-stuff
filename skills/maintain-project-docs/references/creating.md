# Creating project documentation

Use for a new documentation file or structure. Shared scope, evidence, validation, and output rules live in `SKILL.md`.

## 1. Establish purpose and location

Identify the audience, the task the document enables, its authoritative sources, and the intended location. Inspect existing documentation before choosing a path so the new file does not duplicate an existing source of truth. Resolve the path as `SKILL.md` Gotchas describe, and confirm it is project-owned.

If the target exists, switch to `references/updating.md` unless the user explicitly requests a replacement.

## 2. Choose the document contract

Read `references/standard.md` § Content contracts for the doc type; § How to apply says when to create a type and which choices (license, security contact) are the user's.

A package README has no separate contract: local purpose, API, setup, tests, and ownership, from the README template.

## 3. Draft

Start from the matching template in `assets/` when one exists. Put the minimum successful path first, then link to deeper concepts, reference, troubleshooting, and decisions. Write for the identified audience and task rather than for document length.

## 4. Connect navigation

Add a link from the closest established index only when that index is in scope or the user approves the related edit.
