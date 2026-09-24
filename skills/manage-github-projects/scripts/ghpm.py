#!/usr/bin/env python3
"""
ghpm.py — GitHub Projects (v2) manager.

A thin wrapper over `gh api graphql` that handles the bookkeeping that makes
the Projects v2 GraphQL API tedious to use directly:

  - resolving "which project?" from git remote or explicit args
  - paginating project items (the API caps at 100/page)
  - resolving single-select *option IDs* and iteration IDs (mutations require
    these opaque IDs, not the human-readable names)
  - mapping issue numbers (repo-level, e.g. #437) to project *item IDs*
    (the row in the board, e.g. PVTI_lADO...)
  - routing field writes through updateProjectV2ItemFieldValue while routing
    labels / assignees / milestone through the correct repo-level mutations
    (updateProjectV2ItemFieldValue CANNOT touch those — a common footgun)

Auth: inherits whatever `gh` is authed as. Requires the `project` scope
(`gh auth refresh -s project` if missing). No Python deps beyond stdlib.

Usage:
    uv run ghpm.py <command> [options]
    python3 ghpm.py <command> [options]   # if uv isn't desired

See SKILL.md for the workflow and references/graphql-reference.md for the
raw query/mutation catalog.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

# --------------------------------------------------------------------------- #
# Low-level gh wrapper
# --------------------------------------------------------------------------- #

def gh_graphql(query: str, variables: dict[str, Any] | None = None) -> dict:
    """Run a GraphQL query/mutation via `gh api graphql`. Returns parsed JSON.

    Raises RuntimeError on non-zero exit or a top-level 'errors' block.

    Variables are sent as a JSON request body over stdin (the
    `{"query":..., "variables":...}` shape), which gh forwards to the GraphQL
    endpoint verbatim. This avoids gh's CLI-flag value-coercion pitfalls:
    `-F` mangles JSON-looking strings into quoted strings, and `-f` forces
    everything to a string — neither works for the complex input objects that
    Projects v2 mutations need (e.g. UpdateProjectV2ItemFieldValueInput).
    Passing the whole request as JSON is the one approach that works uniformly
    for scalars, enums, nested objects, and null.
    """
    body = json.dumps({"query": query, "variables": variables or {}})
    r = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=body, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh api graphql failed (exit {r.returncode}):\n{r.stderr.strip()}")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"non-JSON response from gh:\n{r.stdout[:500]}") from e
    if data.get("errors"):
        raise RuntimeError("GraphQL errors:\n" + json.dumps(data["errors"], indent=2))
    return data.get("data", {})


def gh_rest(method: str, path: str, *, fields: list[str] | None = None,
            input_field: str | None = None, input_json: dict | None = None) -> Any:
    """Run a gh REST/CLI command. Used for create/close/label where `gh issue`
    is simpler and better-tested than hand-rolled REST calls."""
    args = ["gh"] + method.split() + [path]
    for f in fields or []:
        args += ["-F", f] if "=" in f and f.split("=", 1)[1].replace(".", "").lstrip("-").isdigit() else ["-f", f]
    if input_field:
        args += ["--field", input_field]
    if input_json is not None:
        args += ["--input", "-"]
        r = subprocess.run(args, input=json.dumps(input_json), capture_output=True, text=True)
    else:
        r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(method.split() + [path])} failed:\n{r.stderr.strip()}")
    txt = r.stdout.strip()
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return txt


def git_remote_repo() -> str | None:
    """Return 'OWNER/NAME' from the current repo's origin remote, or None."""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return None
    url = r.stdout.strip()
    # ssh: git@github.com:OWNER/NAME.git   https: https://github.com/OWNER/NAME.git
    for fmt in ("git@github.com:", "https://github.com/", "git://github.com/"):
        if url.startswith(fmt):
            repo = url[len(fmt):]
            return repo[:-4] if repo.endswith(".git") else repo
    return None


# --------------------------------------------------------------------------- #
# Project resolution
# --------------------------------------------------------------------------- #

QUERY_PROJECT_BY_REPO = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 10) { nodes { id number title url closed } }
  }
}
"""

QUERY_PROJECT_BY_USER_NUMBER = """
query($login: String!, $number: Int!) {
  user(login: $login) { projectV2(number: $number) { id number title url closed } }
}
"""

QUERY_PROJECT_BY_USER_TITLE = """
query($login: String!) {
  user(login: $login) { projectsV2(first: 50) { nodes { id number title url closed } } }
}
"""


def resolve_project(args: argparse.Namespace) -> dict:
    """Resolve the target project to {id, number, title, url}. Owner is the
    repo owner by default (covers the common user-project-linked-to-repo case)."""
    repo = args.repo or git_remote_repo()
    if not repo and not args.owner:
        die("No git remote found and --owner not given. Pass --owner LOGIN or --repo OWNER/NAME.")
    owner = args.owner or (repo.split("/")[0] if repo else None)

    if args.project_number:
        d = gh_graphql(QUERY_PROJECT_BY_USER_NUMBER,
                       {"login": owner, "number": int(args.project_number)})
        proj = (d.get("user") or {}).get("projectV2")
        if not proj:
            die(f"No project #{args.project_number} found for user '{owner}'.")
        return proj

    if args.project_name:
        d = gh_graphql(QUERY_PROJECT_BY_USER_TITLE, {"login": owner})
        candidates = [p for p in d["user"]["projectsV2"]["nodes"]
                      if p["title"].lower() == args.project_name.lower()]
        if not candidates:
            die(f"No project titled '{args.project_name}' for user '{owner}'.")
        if len(candidates) > 1:
            die(f"Ambiguous title '{args.project_name}': {[p['number'] for p in candidates]}. Use --project-number.")
        return candidates[0]

    # Auto-detect: prefer the repo's first open linked project.
    if repo:
        d = gh_graphql(QUERY_PROJECT_BY_REPO,
                       {"owner": repo.split("/")[0], "name": repo.split("/")[1]})
        nodes = d["repository"]["projectsV2"]["nodes"]
        open_nodes = [n for n in nodes if not n["closed"]]
        if open_nodes:
            return open_nodes[0]
        if nodes:
            return nodes[0]
    die(f"No project found. Specify with --project-number N (under owner '{owner}').")


# --------------------------------------------------------------------------- #
# Field configuration & item lookup (the tedious part)
# --------------------------------------------------------------------------- #

QUERY_FIELDS = """
query($id: ID!) {
  node(id: $id) {
    ... on ProjectV2 {
      fields(first: 50) {
        nodes {
          ... on ProjectV2FieldCommon { id name dataType }
          ... on ProjectV2SingleSelectField { options { id name } }
          ... on ProjectV2IterationField {
            configuration { iterations { id title startDate } }
          }
        }
      }
    }
  }
}
"""

QUERY_ITEMS_PAGED = """
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue { number title state url }
            ... on DraftIssue { title }
            ... on PullRequest { number title state url }
          }
          fieldValues(first: 50) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2SingleSelectField { name } } }
              ... on ProjectV2ItemFieldNumberValue  { number field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldTextValue    { text   field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldDateValue    { date   field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldIterationValue { title field { ... on ProjectV2IterationField { name } } }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_project_items(project_id: str, query: str) -> list[dict]:
    items: list[dict] = []
    cursor = None
    while True:
        data = gh_graphql(query, {"id": project_id, "cursor": cursor})
        page = data["node"]["items"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


class Project:
    """Resolved project with lazily-fetched field config and item index."""

    def __init__(self, proj: dict, dry_run: bool):
        self.id = proj["id"]
        self.number = proj["number"]
        self.title = proj["title"]
        self.url = proj["url"]
        self.dry_run = dry_run
        self._fields: dict[str, dict] | None = None
        self._items: list[dict] | None = None

    # -- field config: {name: {id, dataType, options:{name:id}, iterations:{title:id}}} --
    def fields(self) -> dict[str, dict]:
        if self._fields is None:
            d = gh_graphql(QUERY_FIELDS, {"id": self.id})
            out: dict[str, dict] = {}
            for n in d["node"]["fields"]["nodes"]:
                name = n.get("name")
                if not name:
                    continue
                entry = {"id": n["id"], "dataType": n["dataType"], "options": {}, "iterations": {}}
                for opt in n.get("options") or []:
                    entry["options"][opt["name"]] = opt["id"]
                for it in (n.get("configuration") or {}).get("iterations", []) or []:
                    entry["iterations"][it["title"]] = it["id"]
                out[name] = entry
            self._fields = out
        return self._fields

    # -- all items (paginated) --
    def items(self) -> list[dict]:
        if self._items is None:
            self._items = fetch_project_items(self.id, QUERY_ITEMS_PAGED)
        return self._items

    def item_by_issue_number(self, number: int) -> dict:
        for it in self.items():
            c = it.get("content") or {}
            if c.get("number") == number:
                return it
        die(f"Issue #{number} is not in project '{self.title}'. "
            f"Run: add-to-project {number} first, or check the number.")

    def current_value(self, item: dict, field_name: str) -> Any:
        for fv in item.get("fieldValues", {}).get("nodes", []):
            f = fv.get("field") or {}
            if f.get("name") == field_name:
                return fv.get("name") or fv.get("number") or fv.get("text") or fv.get("date") or fv.get("title")
        return None


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #

M_SET_FIELD = """
mutation($input: UpdateProjectV2ItemFieldValueInput!) {
  updateProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
}
"""
M_CLEAR_FIELD = """
mutation($input: ClearProjectV2ItemFieldValueInput!) {
  clearProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
}
"""
M_ADD_ITEM = """
mutation($input: AddProjectV2ItemByIdInput!) {
  addProjectV2ItemById(input: $input) { item { id } }
}
"""
M_ADD_DRAFT = """
mutation($input: AddProjectV2DraftIssueInput!) {
  addProjectV2DraftIssue(input: $input) { projectItem { id } }
}
"""
M_DELETE_ITEM = """
mutation($input: DeleteProjectV2ItemInput!) {
  deleteProjectV2Item(input: $input) { deletedItemId }
}
"""
M_ADD_SUBISSUE = """
mutation($input: AddSubIssueInput!) {
  addSubIssue(input: $input) { subissue { id } }
}
"""


def build_field_value(project: Project, field_name: str, raw: str) -> tuple[str, dict]:
    """Translate 'Status=In Progress' style raw value into a GraphQL
    ProjectV2FieldValue input object. Returns (fieldId, value_obj)."""
    f = project.fields().get(field_name)
    if not f:
        die(f"Unknown field '{field_name}'. Known: {sorted(project.fields())}.")
    dt = f["dataType"]
    if dt == "SINGLE_SELECT":
        opt = f["options"].get(raw)
        if not opt:
            die(f"'{raw}' is not an option for '{field_name}'. "
                f"Options: {sorted(f['options'])}.")
        return f["id"], {"singleSelectOptionId": opt}
    if dt == "NUMBER":
        try:
            return f["id"], {"number": float(raw)}
        except ValueError:
            die(f"'{raw}' is not a number, but '{field_name}' is a NUMBER field.")
    if dt == "TEXT":
        return f["id"], {"text": raw}
    if dt == "DATE":
        # Accept YYYY-MM-DD; nothing fancier — keep the skill predictable.
        return f["id"], {"date": raw}
    if dt == "ITERATION":
        it = f["iterations"].get(raw)
        if not it:
            die(f"'{raw}' is not an iteration of '{field_name}'. "
                f"Iterations: {sorted(f['iterations'])}.")
        return f["id"], {"iterationId": it}
    die(f"Unsupported field dataType {dt} for '{field_name}'.")


# --------------------------------------------------------------------------- #
# Command implementations
# --------------------------------------------------------------------------- #

def cmd_fields(project: Project, _args) -> None:
    """Print the project's field configuration (names, types, options)."""
    print(json.dumps(project.fields(), indent=2))


def cmd_items(project: Project, args) -> None:
    """Dump all project items with their field values (paginated)."""
    rows = []
    for it in project.items():
        c = it.get("content") or {}
        row = {
            "itemId": it["id"],
            "number": c.get("number"),
            "title": c.get("title"),
            "type": "draft" if "number" not in c else ("pullrequest" if c.get("url", "").endswith("/pull") else "issue"),
            "state": c.get("state"),
            "url": c.get("url"),
            "fields": {},
        }
        for fv in it.get("fieldValues", {}).get("nodes", []):
            fn = (fv.get("field") or {}).get("name")
            if fn:
                row["fields"][fn] = fv.get("name") or fv.get("number") or fv.get("text") or fv.get("date") or fv.get("title")
        rows.append(row)
    print(json.dumps(rows, indent=2))


def cmd_report(project: Project, args) -> None:
    """Coverage + staleness analysis (mirrors the session's report)."""
    from collections import Counter
    from datetime import datetime, timezone

    # Need createdAt/updatedAt — re-query with richer content selection.
    rich = """
    query($id: ID!, $cursor: String) {
      node(id: $id) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              fieldValues(first: 50) { nodes {
                ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2SingleSelectField { name } } }
              } }
              content {
                ... on Issue { number title state createdAt updatedAt closedAt
                  labels(first:20){nodes{name}} assignees(first:5){nodes{login}} milestone{title} }
              }
            }
          }
        }
      }
    }
    """
    all_items = fetch_project_items(project.id, rich)

    now = datetime.now(timezone.utc)
    def age(iso): return (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days if iso else None

    # Determine which single-select fields exist so coverage is field-aware.
    sel_fields = [n for n, f in project.fields().items() if f["dataType"] == "SINGLE_SELECT"]

    recs = []
    for it in all_items:
        c = it.get("content") or {}
        if not c: continue
        r = {"number": c.get("number"), "title": c.get("title"), "state": c.get("state")}
        for fv in it.get("fieldValues", {}).get("nodes", []):
            fn = (fv.get("field") or {}).get("name")
            if fn: r[fn] = fv.get("name")
        r["_created"] = age(c.get("createdAt")); r["_updated"] = age(c.get("updatedAt"))
        r["_labels"] = [l["name"] for l in (c.get("labels") or {}).get("nodes", [])]
        r["_milestone"] = (c.get("milestone") or {}).get("title")
        recs.append(r)

    open_recs = [r for r in recs if r["state"] == "OPEN"]
    print(f"Project: {project.title} (#{project.number})")
    print(f"Total items: {len(recs)}   OPEN: {len(open_recs)}   CLOSED: {len(recs)-len(open_recs)}")
    print(f"\nSingle-select fields: {', '.join(sel_fields) or '(none)'}")
    for f in sel_fields:
        print(f"\n=== OPEN issues by {f} ===")
        for k, v in Counter(r.get(f) or "(unset)" for r in open_recs).most_common():
            print(f"  {v:>3}  {k}")
    print("\n=== OPEN field coverage ===")
    for f in sel_fields:
        set_ct = sum(1 for r in open_recs if r.get(f))
        print(f"  {f}: {set_ct}/{len(open_recs)} set")
    # staleness
    if open_recs:
        open_recs.sort(key=lambda r: r["_updated"] or 0, reverse=True)
        print("\n=== 10 stalest OPEN issues (days since update) ===")
        for r in open_recs[:10]:
            print(f"  #{r['number']:<4} upd={r['_updated']}d  {r['title'][:70]}")
    # anomalies
    print("\n=== Anomalies: OPEN issues with no Status set ===")
    statusless = [r for r in open_recs if not r.get("Status")]
    print(f"  {len(statusless)} issue(s)")


def cmd_set(project: Project, args) -> None:
    """set <issue> <Field>=<value> [<Field>=<value>...]  — update one or more fields.
    Uses '=' so field names containing spaces (e.g. 'Start Date') work unquoted."""
    item = project.item_by_issue_number(args.issue)
    changed = False
    for pair in args.pairs:
        if "=" not in pair:
            die(f"Expected Field=value, got '{pair}'. Use '=' e.g. Priority=High.")
        field_name, raw = pair.split("=", 1)
        field_id, value = build_field_value(project, field_name, raw)
        old = project.current_value(item, field_name)
        print(f"#{args.issue}  {field_name}: {old!r} → {raw!r}")
        if project.dry_run:
            continue
        gh_graphql(M_SET_FIELD, {"input": {
            "projectId": project.id, "itemId": item["id"],
            "fieldId": field_id, "value": value,
        }})
        changed = True
    if project.dry_run:
        print("[dry-run] no mutation sent.")
    elif changed:
        print(f"✓ updated (item {item['id']})")


def cmd_clear(project: Project, args) -> None:
    """clear <issue> <Field>  — clear a single field value."""
    f = project.fields().get(args.field)
    if not f:
        die(f"Unknown field '{args.field}'.")
    item = project.item_by_issue_number(args.issue)
    mutation_input = {"projectId": project.id, "itemId": item["id"], "fieldId": f["id"]}
    if project.dry_run:
        print(f"[dry-run] would clear {args.field} on #{args.issue}."); return
    gh_graphql(M_CLEAR_FIELD, {"input": mutation_input})
    print(f"✓ cleared {args.field} on #{args.issue}")


def cmd_label(project: Project, args) -> None:
    """label <issue> <label> [--remove]  — repo-level (not a project field)."""
    action = "remove" if args.remove else "add"
    if project.dry_run:
        print(f"[dry-run] would {action} label '{args.label}' on #{args.issue}."); return
    cmd = ["gh", "issue", "edit", str(args.issue), ("--remove-label" if args.remove else "--add-label"), args.label]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh issue edit failed:\n{r.stderr.strip()}")
    print(f"✓ {'removed' if args.remove else 'added'} label '{args.label}' on #{args.issue}")


def cmd_assign(project: Project, args) -> None:
    """assign <issue> <login> [--remove]."""
    action = "remove" if args.remove else "add"
    if project.dry_run:
        print(f"[dry-run] would {action} assignee @{args.login} to #{args.issue}."); return
    flag = "--remove-assignee" if args.remove else "--add-assignee"
    r = subprocess.run(["gh", "issue", "edit", str(args.issue), flag, args.login], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh issue edit failed:\n{r.stderr.strip()}")
    print(f"✓ {'removed' if args.remove else 'added'} assignee @{args.login} on #{args.issue}")


def cmd_milestone(project: Project, args) -> None:
    """milestone <issue> <title>  (pass '' to clear)."""
    if project.dry_run:
        print(f"[dry-run] would set milestone '{args.milestone}' on #{args.issue}."); return
    # gh resolves milestone by title; '' clears via REST.
    cmd = ["gh", "issue", "edit", str(args.issue)]
    cmd += ["--remove-milestone"] if args.milestone == "" else ["--milestone", args.milestone]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh issue edit milestone failed:\n{r.stderr.strip()}")
    print(f"✓ milestone {'cleared' if args.milestone=='' else repr(args.milestone)} on #{args.issue}")


def cmd_add_to_project(project: Project, args) -> None:
    """add-to-project <issue>  — add an existing repo issue/PR to this project."""
    repo = args.repo or git_remote_repo() or die("--repo required (no git remote).")
    # Get the content node ID for the issue.
    owner, name = repo.split("/")
    q = 'query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){id}}}'
    d = gh_graphql(q, {"owner": owner, "name": name, "n": args.issue})
    content_id = (d["repository"].get("issue") or {}).get("id")
    if not content_id:
        die(f"Issue #{args.issue} not found in {repo}.")
    if project.dry_run:
        print(f"[dry-run] would add #{args.issue} to {project.title}."); return
    res = gh_graphql(M_ADD_ITEM, {"input": {"projectId": project.id, "contentId": content_id}})
    print(f"✓ added #{args.issue} to '{project.title}' (item {res['addProjectV2ItemById']['item']['id']})")


def cmd_remove_from_project(project: Project, args) -> None:
    """remove-from-project <issue>  — DELETE is destructive; confirm unless --yes."""
    item = project.item_by_issue_number(args.issue)
    if not args.yes:
        if not confirm(f"Remove #{args.issue} (item {item['id']}) from '{project.title}'? "
                       f"This does NOT close the issue, only removes it from the board."):
            print("aborted."); return
    if project.dry_run:
        print(f"[dry-run] would remove #{args.issue}."); return
    gh_graphql(M_DELETE_ITEM, {"input": {"projectId": project.id, "itemId": item["id"]}})
    print(f"✓ removed #{args.issue} from '{project.title}'")


def cmd_link(project: Project, args) -> None:
    """link <parent> <child> [--subissue|--blocks|--duplicate|--relates].

    subissue  → addSubIssue mutation (true parent/child, shows in issue sidebar)
    blocks/duplicate/relates → applied as a label (GitHub has no first-class
                               'blocks' link via GraphQL; labels + body refs are the convention)
    """
    repo = args.repo or git_remote_repo() or die("--repo required (no git remote).")
    owner, name = repo.split("/")
    q = ('query($owner:String!,$name:String!,$a:Int!,$b:Int!){'
         'repository(owner:$owner,name:$name){a:issue(number:$a){id} b:issue(number:$b){id}}}')
    d = gh_graphql(q, {"owner": owner, "name": name, "a": args.parent, "b": args.child})
    parent_id = d["repository"]["a"]["id"]; child_id = d["repository"]["b"]["id"]
    rel = args.relation or "subissue"
    if rel == "subissue":
        if project.dry_run:
            print(f"[dry-run] would link #{args.child} as sub-issue of #{args.parent}."); return
        gh_graphql(M_ADD_SUBISSUE, {"input": {"parentId": parent_id, "subIssueId": child_id}})
        print(f"✓ #{args.child} is now a sub-issue of #{args.parent}")
    else:
        # blocks/duplicate/relates → label on the child, mention in body
        label = {"blocks": "blocks", "duplicate": "duplicate", "relates": "relates"}[rel]
        if project.dry_run:
            print(f"[dry-run] would add label '{label}' to #{args.child} (linking to #{args.parent})."); return
        subprocess.run(["gh", "issue", "edit", str(args.child), "--add-label", label],
                       capture_output=True, text=True, check=True)
        print(f"✓ labeled #{args.child} with '{label}' (ref #{args.parent}). "
              f"Note: GitHub has no first-class {rel} link via GraphQL; label+body-ref is the convention.")


def cmd_create_draft(project: Project, args) -> None:
    """create-draft <title> [--body TEXT]  — draft issue inside the project."""
    if project.dry_run:
        print(f"[dry-run] would create draft '{args.title}' in {project.title}."); return
    res = gh_graphql(M_ADD_DRAFT, {"input": {"projectId": project.id, "title": args.title, "body": args.body or ""}})
    print(f"✓ created draft '{args.title}' (item {res['addProjectV2DraftIssue']['projectItem']['id']})")


def cmd_create(project: Project, args) -> None:
    """create <title> --repo O/N [--body --label --assignee --milestone]
    then add to project + set initial fields via repeated `set`."""
    repo = args.repo or git_remote_repo() or die("--repo required (no git remote).")
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", args.title]
    if args.body: cmd += ["--body", args.body]
    for l in args.label or []: cmd += ["--label", l]
    for a in args.assignee or []: cmd += ["--assignee", a]
    if args.milestone: cmd += ["--milestone", args.milestone]
    if project.dry_run:
        print("[dry-run] would run: " + " ".join(cmd)); return
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh issue create failed:\n{r.stderr.strip()}")
    url = r.stdout.strip()
    # extract number from url
    try:
        num = int(url.rstrip("/").split("/")[-1])
    except ValueError:
        print(f"✓ created {url} (could not parse number to auto-add to project)"); return
    # add to project
    gh_graphql(M_ADD_ITEM, {"input": {"projectId": project.id, "contentId": _content_id(repo, num)}})
    print(f"✓ created #{num} {url} and added to '{project.title}'")


def _content_id(repo: str, num: int) -> str:
    owner, name = repo.split("/")
    d = gh_graphql('query($o:String!,$n:String!,$num:Int!){repository(owner:$o,name:$n){issue(number:$num){id}}}',
                   {"o": owner, "n": name, "num": num})
    return d["repository"]["issue"]["id"]


def cmd_close(project: Project, args) -> None:
    """close <issue>  — destructive; confirm unless --yes."""
    if not args.yes:
        if not confirm(f"Close #{args.issue}?"):
            print("aborted."); return
    if project.dry_run:
        print(f"[dry-run] would close #{args.issue}."); return
    r = subprocess.run(["gh", "issue", "close", str(args.issue)], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh issue close failed:\n{r.stderr.strip()}")
    print(f"✓ closed #{args.issue}")


def cmd_delete_draft(project: Project, args) -> None:
    """delete-draft <itemId>  — DRAFT issues have no number; pass the item ID."""
    if not args.yes:
        if not confirm(f"Delete draft item {args.item_id} from '{project.title}'? Permanent."):
            print("aborted."); return
    if project.dry_run:
        print(f"[dry-run] would delete {args.item_id}."); return
    gh_graphql(M_DELETE_ITEM, {"input": {"projectId": project.id, "itemId": args.item_id}})
    print(f"✓ deleted draft {args.item_id}")


# --------------------------------------------------------------------------- #
# CLI wiring
# --------------------------------------------------------------------------- #

def confirm(prompt: str) -> bool:
    return input(prompt + " [y/N] ").strip().lower() in ("y", "yes")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr); sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ghpm.py",
        description="GitHub Projects v2 manager (pagination + field/option IDs handled).",
    )
    # Global options (must come BEFORE the subcommand on the argv after the prog).
    p.add_argument("--project-number", help="project number (owner-scoped)")
    p.add_argument("--project-name", help="project title (owner-scoped)")
    p.add_argument("--owner", help="project owner login (default: repo owner)")
    p.add_argument("--repo", help="OWNER/NAME (default: git remote origin)")
    p.add_argument("--dry-run", action="store_true", help="print mutations, don't send")

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fields", help="print project field configuration")
    s.set_defaults(fn=cmd_fields)

    s = sub.add_parser("items", help="dump all items + field values as JSON")
    s.set_defaults(fn=cmd_items)

    s = sub.add_parser("report", help="coverage + staleness report")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("set", help="set field(s): set <issue> <Field>=<value> [<F>=<v>...]")
    s.add_argument("issue", type=int)
    s.add_argument("pairs", nargs="+", metavar="Field=value",
                   help="one or more Field=value pairs (e.g. Priority=High Size=L)")
    s.set_defaults(fn=cmd_set)

    s = sub.add_parser("clear", help="clear a project field: clear <issue> <Field>")
    s.add_argument("issue", type=int)
    s.add_argument("field")
    s.set_defaults(fn=cmd_clear)

    s = sub.add_parser("label", help="add/remove a label (repo-level)")
    s.add_argument("issue", type=int)
    s.add_argument("label")
    s.add_argument("--remove", action="store_true")
    s.set_defaults(fn=cmd_label)

    s = sub.add_parser("assign", help="add/remove an assignee (repo-level)")
    s.add_argument("issue", type=int)
    s.add_argument("login")
    s.add_argument("--remove", action="store_true")
    s.set_defaults(fn=cmd_assign)

    s = sub.add_parser("milestone", help="set milestone by title ('' clears)")
    s.add_argument("issue", type=int)
    s.add_argument("milestone")
    s.set_defaults(fn=cmd_milestone)

    s = sub.add_parser("add-to-project", help="add an existing issue/PR to this project")
    s.add_argument("issue", type=int)
    s.set_defaults(fn=cmd_add_to_project)

    s = sub.add_parser("remove-from-project", help="remove an item from the board (keeps issue open)")
    s.add_argument("issue", type=int)
    s.add_argument("--yes", action="store_true", help="skip confirmation")
    s.set_defaults(fn=cmd_remove_from_project)

    s = sub.add_parser("link", help="link issues (sub-issue / blocks / duplicate / relates)")
    s.add_argument("parent", type=int)
    s.add_argument("child", type=int)
    s.add_argument("--relation", choices=["subissue", "blocks", "duplicate", "relates"], default="subissue")
    s.set_defaults(fn=cmd_link)

    s = sub.add_parser("create-draft", help="create a draft issue inside the project")
    s.add_argument("title")
    s.add_argument("--body", default="")
    s.set_defaults(fn=cmd_create_draft)

    s = sub.add_parser("create", help="create a repo issue and add it to the project")
    s.add_argument("title")
    s.add_argument("--body", default="")
    s.add_argument("--label", action="append")
    s.add_argument("--assignee", action="append")
    s.add_argument("--milestone")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("close", help="close an issue")
    s.add_argument("issue", type=int)
    s.add_argument("--yes", action="store_true")
    s.set_defaults(fn=cmd_close)

    s = sub.add_parser("delete-draft", help="delete a draft issue (by item ID)")
    s.add_argument("item_id")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(fn=cmd_delete_draft)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # argparse with global options + subparsers: globals parse fine when before subcmd.
    # (If user puts --project-number after the subcommand, argparse rejects it —
    #  documented in SKILL.md: globals go first.)
    proj = resolve_project(args)
    project = Project(proj, dry_run=args.dry_run)
    args.fn(project, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
