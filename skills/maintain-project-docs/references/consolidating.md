# Consolidating project documentation

Use for deduplication, reorganization, file moves, broad rewrites, or removal. Consolidation is potentially destructive, so separate planning from mutation. The approval gate, scope, stale-content, validation, and output rules live in `SKILL.md`.

## 1. Inventory

Inventory tracked documentation with version-control-aware discovery, adapting extensions and paths to the repository:

```bash
git ls-files '*.md' '*.mdx' '*.rst' '*.adoc'
```

List nested `AGENTS.md`, `CLAUDE.md`, and other instruction files separately in the inventory.

## 2. Map content and links

For each in-scope file, identify audience, owner, authoritative topics, inbound and outbound links, duplicated material, conflicting claims, stale guidance, and missing navigation. Verify disputed facts before choosing a canonical source.

## 3. Plan before editing

List every proposed mutation, then stop for approval as `SKILL.md` requires:

<!-- prettier-ignore -->
| Action | Source | Destination/canonical source | Reason | Link/instruction impact |
|-|-|-|-|-|
| edit | `path` | `path` | correct conflict | update two links |
| move | `old` | `new` | match convention | update inbound links |
| delete | `path` | `canonical` | fully redundant | preserve redirect if needed |
| create | — | `path` | documented gap | add index link |

## 4. Execute an approved plan

- Establish the canonical source before replacing duplicates with links.
- Move files with `git mv` or another version-control-aware command when possible.
- Update all affected relative links, anchors, navigation config, and instruction-file path references.
- Keep commits or change groups small enough to review and revert.
- Re-run the tracked-document inventory afterwards and confirm nothing in it was lost.
