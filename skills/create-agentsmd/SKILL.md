---
name: create-agentsmd
description: >-
  Creates or improves AGENTS.md files with concise, evidence-backed guidance
  derived from the repository: setup, development, testing, code conventions,
  architecture constraints, validation, and repo-specific gotchas. Use when the
  user asks to create, write, regenerate, review, audit, or improve an AGENTS.md
  file for a code repository, including monorepos or nested package
  instructions. Do not invent commands or copy generic templates.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.1"
---

# Create or improve AGENTS.md

Create the smallest `AGENTS.md` that materially helps coding agents work correctly in the repository. Prefer project-specific facts, constraints, and gotchas over generic software advice.

## Workflow

### 1. Establish scope

- Find the repository root and any existing `AGENTS.md` files.
- Determine whether the request is to create, replace, audit, or improve instructions.
- When updating an existing file, preserve useful project-specific guidance unless current repository evidence contradicts it.
- In a monorepo, keep root guidance cross-cutting. Use nested `AGENTS.md` files only for materially different subproject commands, conventions, or constraints; do not repeat root guidance.
- Do not create extra nested files unless the user requested repository-wide coverage or they are clearly necessary. Otherwise, note where one would help.

### 2. Inspect repository sources of truth

Use targeted inspection rather than reading the entire codebase. Prioritize:

1. Existing `AGENTS.md`, `README*`, `CONTRIBUTING*`, and relevant docs
2. Package manifests, lockfiles, workspace files, runtime/version files, and task runners
3. Linter, formatter, type-checker, test, build, and framework configuration
4. CI workflows and required checks
5. Environment templates and local-development configuration
6. Key directories or representative source files only when needed to resolve architecture or convention questions

Treat executable configuration and manifests as stronger evidence for commands than stale prose. If sources conflict and the correct behavior is unclear, do not invent a resolution; either qualify the instruction or omit it.

### 3. Extract only agent-useful guidance

Capture information that changes how an agent should work, such as:

- Canonical setup and dependency commands
- Package manager, workspace, runtime, and version constraints
- Development, build, lint, format, type-check, and test commands
- Fast ways to run a focused test or check when the repository supports them
- Required validation after common changes
- Generated files, migrations, schemas, codegen, or directories agents should not edit manually
- Architectural boundaries and invariants that affect correctness
- Non-obvious naming, file-placement, import, or API conventions not already enforced automatically
- Security, secret-handling, production, or destructive-operation constraints that matter during agent work
- Repository-specific gotchas and failure modes
- PR or commit requirements only when they actually exist in repository guidance or automation

Exclude:

- Generic explanations of languages, frameworks, Git, testing, or `AGENTS.md`
- Advice a capable coding agent already knows, such as "write clean code" or "handle errors"
- Rules already enforced mechanically unless the agent needs the command to run the check
- Empty sections, placeholders, or template text
- Secret values or credentials; reference variable names or setup docs instead
- Deployment instructions unless agents are expected to deploy from this repository
- Unsupported claims presented as requirements

### 4. Resolve commands precisely

- Derive the package manager from repository evidence such as lockfiles, workspace configuration, or manifest metadata.
- Prefer repository-defined scripts and task-runner commands over ad hoc direct invocations.
- Copy commands exactly from manifests, docs, CI, or configuration; do not guess flags or script names.
- Distinguish repository-root commands from package-local commands.
- If a command requires prerequisites, state the minimum useful prerequisite or point to the existing setup documentation.

### 5. Draft an adaptive document

Do not force a fixed template. Use only the sections this repository needs. A strong document often includes some subset of:

- `# AGENTS.md`
- `## Scope` or a one-sentence project overview
- `## Setup and development`
- `## Validation and testing`
- `## Architecture and conventions`
- `## Generated files and migrations`
- `## Security and safety`
- `## Repository gotchas`

Writing rules:

- Put the highest-impact constraints and commands early.
- Use direct, imperative language and exact paths or commands.
- Prefer short bullets and compact tables over explanatory prose.
- Link to existing repository docs with relative paths instead of duplicating long instructions.
- For nested files, state the directory scope when useful and include only guidance specific to that subtree.
- Avoid provider-specific features or filenames unless the repository explicitly depends on them.

### 6. Verify before finishing

Check the finished instructions against the repository:

- Every command exists in repository evidence or was explicitly supplied by the user.
- The package manager and working directory are correct.
- Test and validation instructions align with CI where applicable.
- No placeholders, generic boilerplate, stale claims, or duplicated inherited guidance remain.
- No secrets or credential values are included.
- Existing high-value instructions were not accidentally lost during an update.

When practical, run fast, local, non-destructive validation commands that are already supported by the current environment. Do **not** install dependencies, start long-running servers, deploy, mutate external systems, or run destructive migrations solely to validate `AGENTS.md` unless the user explicitly asks.

### 7. Report the result

After writing or updating the file, briefly state:

- Which `AGENTS.md` files were created or changed
- Why nested files were or were not used
- Which commands or checks were actually executed
- Any material instructions that could not be verified
