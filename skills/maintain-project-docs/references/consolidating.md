# Consolidating project documentation

Use for deduplication, reorganization, file moves, broad rewrites, or removal. Consolidation is potentially destructive, so separate planning from mutation. The approval gate, scope, stale-content, validation, and output rules live in `SKILL.md`.

## 1. Inventory

Inventory tracked documentation with version-control-aware discovery, adapting extensions and paths to the repository:

```bash
git ls-files '*.md' '*.mdx' '*.rst' '*.adoc'
```

List nested `AGENTS.md`, `CLAUDE.md`, and other instruction files separately in the inventory, and mark files that CI or a tool reads as out of scope (`SKILL.md` Gotchas). When `docs/manifest.json` exists, read it first: its `paths` and `exclude` define the layout and scope. Note files with uncommitted changes (`git status --porcelain`); rewriting them, or a copy of them on another branch, will conflict with the author's local edits.

## 2. Map content and links

For each in-scope file, identify audience, owner, authoritative topics, inbound and outbound links, duplicated material, conflicting claims, stale guidance, and missing navigation. Verify disputed facts before choosing a canonical source, and verify every fact in a file before labeling it canonical.

## 3. Plan before editing

List every proposed mutation, then stop for approval as `SKILL.md` requires:

<!-- prettier-ignore -->
| Action | Source | Destination/canonical source | Reason | Link/instruction impact |
|-|-|-|-|-|
| edit | `path` | `path` | correct conflict | update two links |
| move | `old` | `new` | match convention | update inbound links |
| split | `path` | `a.md`, `b.md` | over budget | update inbound links |
| delete | `path` | `canonical` | fully redundant | preserve redirect if needed |
| create | — | `path` | documented gap | add index link |

## 4. Execute an approved plan

- Establish the canonical source before replacing duplicates with links.
- Move files with `git mv` or another version-control-aware command when possible.
- Update all affected relative links, anchors, navigation config, and instruction-file path references.
- Never renumber an ADR; the ADR and plan lifecycle rules are in `references/standard.md` § Content contracts.
- Keep commits or change groups small enough to review and revert.

## 5. Audit removals

Re-run the tracked-document inventory and confirm no file was lost. List the removed lines with `git diff <base> -- <changed paths> | grep '^-[^-]'`. Search the tree for each substantive block (code fences, commands, tables, values) and confirm it exists elsewhere. Restore anything missing, or report it as a deliberate deletion with its `git show <base>:<path>` pointer.
