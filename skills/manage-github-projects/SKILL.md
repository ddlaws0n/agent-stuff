---
name: manage-github-projects
description: >-
  Manages GitHub Projects v2 boards and the issues in them: inspects board
  state, sets Status/Priority/Size/Estimate/Iteration and custom fields,
  labels/assigns/milestones issues, links issues (sub-issues, blocked-by,
  duplicate), creates issues and drafts, and removes items. Use when the user
  mentions a GitHub project board, project fields, t-shirt sizes or estimates,
  issue Status/Priority/Size columns, triaging or grooming a backlog,
  linking/blocking/duplicating issues, or wants a report on project coverage and
  staleness, including phrases like "move this issue to In Progress", "set
  priority to High", "size this issue as L", "what's the state of my project
  board", "link these issues", "add this to the Homelab project", "which issues
  have no size", or "triage the backlog". Also use when the user says "the
  project" and means a GitHub Projects board. Do not use for plain issue work
  without a board, or Projects classic.
license: MIT
compatibility: >-
  Requires Python 3.10+, GitHub CLI (gh) with project scope, and GitHub access;
  uv is optional.
metadata:
  author: ddlaws0n
  version: "0.1.2"
---

# Manage GitHub Projects

GitHub Projects v2 layers custom fields (Status, Priority, Size, Estimate,
Iteration, …) on top of issues. Its GraphQL API needs opaque option IDs,
paginates items 100 at a time, and keeps labels, assignees, and milestones on
the _issue_, not the _project item_. The bundled script absorbs that
bookkeeping. For plain `gh issue` work with no board, use `gh` directly.

## Workflow

1. Confirm the board and its vocabulary: run `fields` before any change, and `report` for state questions. Take field names and option values from that output.
2. For bulk or uncertain changes, run the commands with `--dry-run` first and review the planned mutations.
3. Apply the changes. Destructive commands (`close`, `remove-from-project`, `delete-draft`) need the user's confirmation.
4. Report what changed, and say when a link was recorded as a label rather than a first-class GitHub relationship.

## Scripts

Everything runs through `scripts/ghpm.py` with `uv run` (preferred) or
`python3`. Auth is inherited from `gh`, which needs the `project` scope
(`gh auth refresh -s project` once).

```bash
uv run <skill-dir>/scripts/ghpm.py <command> [options]
```

`<skill-dir>` is this skill's installed directory, which varies by agent and
scope. Run the script by absolute path from inside the target repository so
`--repo` can be omitted and auto-detected from the git remote. Examples below
abbreviate the invocation to `ghpm.py`.

**Global options** (placed _before_ the subcommand):

<!-- prettier-ignore -->
| Option | Purpose |
|-|-|
| `--project-number N` | Target project by number (owner-scoped) |
| `--project-name "Title"` | Target project by title |
| `--owner LOGIN` | Project owner (default: repo owner from git remote) |
| `--repo OWNER/NAME` | Override the repo (default: git remote origin) |
| `--dry-run` | Print the mutation, don't send it |

Without `--project-number` or `--project-name`, the script picks the repo's
first open linked project.

### Inspecting

```bash
ghpm.py fields                          # field config: names, types, option IDs
ghpm.py items                           # all items + values as JSON
ghpm.py report                          # coverage + staleness
```

`report` prints state totals, the per-Status breakdown of OPEN issues, field
coverage (OPEN issues missing each single-select field), the 10 stalest open
issues, and open issues with no Status.

### Setting project fields

```bash
ghpm.py set 437 Status="In Progress"
ghpm.py set 437 Priority=High
ghpm.py set 437 Size=L
ghpm.py set 437 Estimate=3
ghpm.py set 437 Iteration="Sprint 42"
ghpm.py set 437 "Start Date"=2026-09-15
ghpm.py clear 437 Priority
```

The script translates option names, numbers, dates, and iteration titles into
the IDs and types the API needs.

### Repo-level metadata (not project fields)

`updateProjectV2ItemFieldValue` cannot touch labels, assignees, or milestone;
use these instead:

```bash
ghpm.py label 437 bug --remove          # or omit --remove to add
ghpm.py assign 437 @me                  # any login; --remove to unassign
ghpm.py milestone 437 "v2.0"            # '' (empty string) clears it
```

### Linking issues

```bash
ghpm.py link 100 437                          # default: #437 becomes sub-issue of #100
ghpm.py link 100 437 --relation subissue      # explicit, same as above
ghpm.py link 100 437 --relation blocks        # labels #437 "blocks" + body ref
ghpm.py link 100 437 --relation duplicate     # labels #437 "duplicate"
ghpm.py link 100 437 --relation relates       # labels #437 "relates"
```

Only `subissue` creates a true GitHub parent/child link. `blocks`, `duplicate`,
and `relates` have no first-class GraphQL link, so the script adds a label plus
a body cross-reference and says so.

### Creating and removing

```bash
ghpm.py create "Fix the flux capacitor" --body "..." --label bug --assignee @me --milestone v2.0
ghpm.py create-draft "Investigate warp drive feasibility" --body "..."
ghpm.py add-to-project 437               # add existing issue to this board
ghpm.py close 437                        # confirms unless --yes
ghpm.py remove-from-project 437          # removes from board, keeps issue open; confirms
ghpm.py delete-draft PVTI_lADO...        # drafts have no number; pass item ID. --yes to skip
```

`create` makes a repo issue and adds it to the current project; follow with
`set` commands to fill its fields.

For bulk changes, loop with `--dry-run` first, review the plan, then re-run
without it:

```bash
for n in 437 438 441; do
  uv run <skill-dir>/scripts/ghpm.py --dry-run set "$n" Priority=High
done
```

## References

- `references/graphql-reference.md`: read when the script does not cover the
  task (field types like `TRACKS`/`LINKED_PULL_REQUESTS`, project settings,
  archived items) and you must drop to raw `gh api graphql`, or when debugging
  a raw response. It holds the query/mutation catalog, inline-fragment shapes
  for every field value type, the pagination pattern, and the footguns
  (option IDs, issue number vs item ID, add-then-update ordering, repo-level vs
  project-level mutations).

## Gotchas

- Field names and option values are user-defined, case-sensitive, and
  exact-match: `Status` vs `📊 Status`, `Size` vs `T-shirt`, `P0/P1/P2` vs
  `Low/Medium/High`. Never assume them; resolve from `fields` first. The script
  refuses to guess and lists the legal values on a mismatch.
- Non-destructive writes (`set`, `clear`, `label`, `assign`, `milestone`,
  `link`, `create`, `create-draft`, `add-to-project`) execute immediately.
  Destructive ones (`close`, `remove-from-project`, `delete-draft`) prompt
  unless `--yes` is passed; get the user's confirmation before passing it.
- `--dry-run` works for every command and sends nothing.
