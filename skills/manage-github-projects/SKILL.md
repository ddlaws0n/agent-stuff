---
name: manage-github-projects
description: Manage GitHub Projects v2 (the new board view) and the issues in them — inspect board state, set Status/Priority/Size/Estimate/Iteration and custom fields, label/assign/milestone issues, link issues (sub-issues, blocked-by, duplicate), create issues and drafts, and remove items. Use this skill whenever the user mentions a GitHub project board, project fields, t-shirt sizes or estimates, issue Status/Priority/Size columns, triaging or grooming a backlog, linking/blocking/duplicating issues, or wants a report on project coverage and staleness. Trigger on phrases like "move this issue to In Progress", "set priority to High", "size this issue as L", "what's the state of my project board", "link these issues", "add this to the Homelab project", "which issues have no size", "triage the backlog". Use it even when the user just says "the project" and means a GitHub Projects board, not a code project.
license: MIT
compatibility: Requires Python 3.10+, GitHub CLI (gh) with project scope, and GitHub access; uv is optional.
metadata:
  author: ddlaws0n
  version: "0.1.1"
---

# Manage GitHub Projects

A skill for working with **GitHub Projects v2** — the board/table product that
layers custom fields (Status, Priority, Size, Estimate, Iteration, …) on top of
issues. The Projects GraphQL API is fiddly: single-select fields need opaque
option IDs, items paginate in pages of 100, and labels/assignees/milestones live
on the *issue* not the *project item*. This skill bundles one helper script that
absorbs all of that, so you spend your time on the triage decision instead of
the API bookkeeping.

## When to use

- Reporting on board state: field coverage, stale issues, anomalies, what's
  un-sized or unprioritized
- Setting project fields: Status, Priority, Size (t-shirt), Estimate (number),
  Iteration, and any custom single-select/number/text/date field
- Managing repo-level metadata: labels, assignees, milestone
- Linking issues: parent/child sub-issues, "blocks"/"duplicate"/"relates"
- Creating issues (repo issues auto-added to the project, plus in-project drafts)
- Removing items from a board or closing issues

**Don't use this for:** plain `gh issue` work with no project-board involvement
(just use `gh` directly), or GitHub Projects *classic* (v1) — this targets v2.

## The helper script

Everything runs through `scripts/ghpm.py`. Run it with `uv run` (preferred) or
`python3`. Auth is inherited from `gh` — needs the `project` scope
(`gh auth refresh -s project` once).

```bash
uv run ~/.agents/skills/manage-github-projects/scripts/ghpm.py <command> [options]
```

The path to the script is `scripts/ghpm.py` relative to this skill directory
(`~/.agents/skills/manage-github-projects/scripts/ghpm.py`). When you cd into a repo,
omit `--repo` and it auto-detects from the git remote.

**Global options** (placed *before* the subcommand):

| Option | Purpose |
|---|---|
| `--project-number N` | Target project by number (owner-scoped) |
| `--project-name "Title"` | Target project by title |
| `--owner LOGIN` | Project owner (default: repo owner from git remote) |
| `--repo OWNER/NAME` | Override the repo (default: git remote origin) |
| `--dry-run` | Print the mutation, don't send it |

If neither `--project-number` nor `--project-name` is given, the script picks the
repo's first open linked project. When in doubt, run `fields` first to confirm
you're talking to the right board.

## Commands

### Inspecting

```bash
ghpm.py fields                          # field config: names, types, option IDs
ghpm.py items                           # all items + values as JSON
ghpm.py report                          # coverage + staleness (the session-style report)
```

`report` is the right starting point for "what's the state of my board". It
prints state totals, per-Status breakdown for OPEN issues, field coverage
(how many OPEN issues are missing each single-select field), the 10 stalest
open issues, and the anomaly list (open issues with no Status).

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

Field names and option values are **case-sensitive, exact-match** against what's
defined in the project. Run `fields` to see the legal values before bulk-setting.
The script translates `High` → its option ID, `3` → number, `2026-09-15` → date,
`Sprint 42` → iteration ID automatically.

### Repo-level metadata (NOT project fields)

Labels, assignees, and milestone are properties of the *issue*, not the project
item — `updateProjectV2ItemFieldValue` cannot touch them. Use these instead:

```bash
ghpm.py label 437 bug --remove          # or omit --remove to add
ghpm.py assign 437 ddlawson             # --remove to unassign
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

Only `subissue` creates a true GitHub parent/child link (visible in the issue
sidebar, queryable via `addSubIssue`). `blocks`/`duplicate`/`relates` have no
first-class GraphQL link — the convention is a label plus a body cross-reference.
The script tells you this when it uses the label path.

### Creating & removing

```bash
ghpm.py create "Fix the flux capacitor" --body "..." --label bug --assignee me --milestone v2.0
ghpm.py create-draft "Investigate warp drive feasibility" --body "..."
ghpm.py add-to-project 437               # add existing issue to this board
ghpm.py close 437                        # confirms unless --yes
ghpm.py remove-from-project 437          # removes from board, keeps issue open; confirms
ghpm.py delete-draft PVTI_lADO...        # drafts have no number; pass item ID. --yes to skip
```

`create` makes a repo issue and immediately adds it to the current project. To
set its fields after creation, follow with `set` commands.

## Safety model

- **Non-destructive writes** (set, clear, label, assign, milestone, link,
  create, create-draft, add-to-project) execute immediately and print a
  confirmation line. This matches how triage actually flows — you're moving a
  card, not deleting data.
- **Destructive ops** (close, remove-from-project, delete-draft) prompt for
  confirmation unless `--yes` is passed.
- **`--dry-run`** works everywhere. Use it when the user is unsure or when
  operating in bulk. It prints the exact mutation/input and sends nothing.

When operating on many issues at once, prefer a loop with `--dry-run` first,
eyeball the plan, then re-run without it. Example triage pattern:

```bash
for n in 437 438 441; do
  uv run ghpm.py --dry-run set "$n" Priority=High
done
# review output, then drop --dry-run
```

## Field naming reality check

Project fields are user-defined, so names vary wildly: `Status` vs `status` vs
`📊 Status`, `Size` vs `T-shirt` vs `Estimate`. **Never assume** a field name or
option label — always resolve from `fields` output first. The same applies to
option values: a board's priority ladder might be `P0/P1/P2` or
`Low/Medium/High` or `🔴/🟡/🟢`. The script refuses to guess and errors with the
legal values if you pass a wrong one, which is the safe behavior.

## When something isn't supported

The script covers the common surface. For anything else (custom field types like
`TRACKS`/`LINKED_PULL_REQUESTS`, bulk workflows, project settings, archived
items), drop down to raw GraphQL — see `references/graphql-reference.md` for the
full query/mutation catalog including the inline-fragment shapes for every field
value type. Auth stays the same (`gh api graphql`).

## Deeper reference

- `references/graphql-reference.md` — full query/mutation catalog, the
  pagination pattern, the footguns (single-select option IDs, issue-number vs
  item-ID, add-then-update ordering, repo-level vs project-level mutations).
