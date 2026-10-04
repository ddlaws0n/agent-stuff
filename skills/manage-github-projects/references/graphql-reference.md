# GraphQL Reference — GitHub Projects v2

Full query/mutation catalog underpinning `ghpm.py`. Read this when you need to
understand _why_ the script does something, debug a raw response, or extend
the script with a new operation.

## Table of contents

1. [Auth & invocation](#auth--invocation)
2. [Project discovery](#project-discovery)
3. [Field configuration](#field-configuration)
4. [Reading items (pagination)](#reading-items-pagination)
5. [Mutations](#mutations)
6. [Repo-level mutations (labels/assignees/milestone)](#repo-level-mutations)
7. [Common footguns](#common-footguns)

---

## Auth & invocation

```bash
gh auth login --scopes "project"          # one-time; project scope for writes
gh auth refresh -s project                # add scope to existing login
```

All calls go through `gh api graphql`. For variables, use `-f` for strings and
`-F` for numbers/bools/null:

```bash
gh api graphql -f query='query($org:String!,$n:Int!){organization(login:$org){projectV2(number:$n){id}}}' \
  -f org=octo-org -F n=5
```

**Footgun for complex inputs:** `-F` and `-f` do NOT correctly pass _input
object_ variables (like `UpdateProjectV2ItemFieldValueInput`). `-F` leaves
JSON-looking strings quoted (so GitHub sees a string where it expects an
object), and `-f` forces everything to a string. For mutations with input
objects, send the whole request as JSON over stdin instead:

```bash
echo '{"query":"mutation($input:UpdateProjectV2ItemFieldValueInput!){updateProjectV2ItemFieldValue(input:$input){projectV2Item{id}}}","variables":{"input":{"projectId":"...","itemId":"...","fieldId":"...","value":{"singleSelectOptionId":"..."}}}}' \
  | gh api graphql --input -
```

This is what `ghpm.py` does for every call — it's the one approach that works
uniformly for scalars, enums, nested objects, and null.

`project` scope = read+write. `read:project` = read-only.

---

## Project discovery

**All projects visible to the viewer:**

```graphql
query { viewer { projectsV2(first: 20) { nodes { title number url closed } } } }
```

**User-owned projects (the common case for personal boards):**

```graphql
query($login: String!) {
  user(login: $login) { projectsV2(first: 50) { nodes { id number title url closed } } }
}
```

**Projects linked to a repository:**

```graphql
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 10) { nodes { id number title url closed } }
  }
}
```

**Organization projects** — replace `user(login:...)` with `organization(login:...)`.

---

## Field configuration

Every project field has a stable node ID. **Single-select and iteration fields
also have option/iteration IDs** that mutations require — you cannot write
"In Progress" by name alone, you need the opaque option ID.

```graphql
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
```

Data types: `TITLE`, `ASSIGNEES`, `LABELS`, `STATUS` (system single-select),
`SINGLE_SELECT`, `NUMBER`, `TEXT`, `DATE`, `ITERATION`, `REPOSITORY`, `MILESTONE`,
`TRACKS`, `LINKED_PULL_REQUESTS`.

**The system Status field is a `SINGLE_SELECT`** — it has options just like a
custom single-select. Its option IDs are needed to move an item across columns.

---

## Reading items (pagination)

Hard cap of **100 items per page**. Always loop on `pageInfo.hasNextPage`:

```graphql
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue { number title state url createdAt updatedAt closedAt
              labels(first: 20) { nodes { name } }
              assignees(first: 5) { nodes { login } }
              milestone { title } }
            ... on DraftIssue { title }
            ... on PullRequest { number title state url }
          }
          fieldValues(first: 50) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2SingleSelectField { name } } }
              ... on ProjectV2ItemFieldNumberValue     { number field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldTextValue       { text   field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldDateValue       { date   field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldIterationValue  { title  field { ... on ProjectV2IterationField { name } } }
            }
          }
        }
      }
    }
  }
}
```

**Why the inline fragments:** field values are polymorphic. Each typed value
fragment exposes the relevant scalar (`name` / `number` / `text` / `date` /
`title`) plus the parent field's name. Without these fragments the response is
empty.

---

## Mutations

You **cannot add and update an item in the same call** — add first, then update.

### Add an existing issue/PR to a project (idempotent — returns existing ID if already present)

```graphql
mutation($input: AddProjectV2ItemByIdInput!) {
  addProjectV2ItemById(input: $input) { item { id } }
}
# input: { projectId, contentId }   # contentId = issue/PR node ID
```

### Create a draft issue in the project

```graphql
mutation($input: AddProjectV2DraftIssueInput!) {
  addProjectV2DraftIssue(input: $input) { projectItem { id } }
}
# input: { projectId, title, body }
```

### Update a single-select field

```graphql
mutation($input: UpdateProjectV2ItemFieldValueInput!) {
  updateProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
}
# input: { projectId, itemId, fieldId, value: { singleSelectOptionId: "OPT_ID" } }
```

### Update text / number / date

```graphql
# value: { text: "..." }        | { number: 3.0 }      | { date: "2026-09-01" }
```

### Update an iteration field

```graphql
# value: { iterationId: "IT_ID" }
```

### Clear a field

```graphql
mutation($input: ClearProjectV2ItemFieldValueInput!) {
  clearProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
}
# input: { projectId, itemId, fieldId }
```

### Remove an item from the project

```graphql
mutation($input: DeleteProjectV2ItemInput!) {
  deleteProjectV2Item(input: $input) { deletedItemId }
}
# input: { projectId, itemId }
# NOTE: removes from board only; does NOT close the underlying issue.
```

### Link a sub-issue (true parent/child relationship)

```graphql
mutation($input: AddSubIssueInput!) {
  addSubIssue(input: $input) { subissue { id } }
}
# input: { parentId, subIssueId }   # both are issue node IDs
```

Also available: `removeSubIssue`.

---

## Repo-level mutations

`updateProjectV2ItemFieldValue` **cannot** change Assignees, Labels, Milestone,
or Repository — these are properties of the issue/PR, not the project item. Use:

<!-- prettier-ignore -->
| Operation | Mutation |
|-|-|
| Add assignees | `addAssigneesToAssignable(input: {assignableId, assigneeIds})` |
| Remove assignees | `removeAssigneesFromAssignable(...)` |
| Add labels | `addLabelsToLabelable(input: {labelableId, labelIds})` |
| Remove labels | `removeLabelsFromLabelable(...)` |
| Set milestone | `updateIssue(input: {id, milestoneId})` |

In practice, `gh issue edit <n> --add-label X --add-assignee Y --milestone Z`
is simpler than hand-rolling these — `ghpm.py` shells out to it.

---

## Common footguns

1. **Single-select needs the option ID, not the name.** "In Progress" →
   `47fc0ee4`... The script resolves this via `fields()`; if you write raw
   GraphQL you must fetch it yourself.
2. **Iteration needs the iteration ID.** Same pattern — fetch from
   `configuration.iterations`.
3. **Issue number ≠ item ID.** `#437` is the repo issue number; `PVTI_...` is
   the project row. To mutate a field you need the _item ID_, which means
   looking the issue up inside `project.items` (the script does this).
4. **Draft issues have no number.** They can only be addressed by item ID.
5. **Add-then-update ordering.** A freshly added item has no field values; you
   must call `updateProjectV2ItemFieldValue` in a second mutation.
6. **`gh issue list --limit` caps at ~1000.** For >1000 issues, use the
   paginated GraphQL `items` query (the script's default).
7. **Cost.** Large `items` queries cost GraphQL points; paginate in batches of
   100 and don't re-fetch the whole board when updating one item. The script
   caches the item index per invocation.
8. **Labels/assignees via project field mutation silently no-op.** The mutation
   accepts the input shape but the change doesn't stick — there's no error.
   Route through repo-level mutations.
9. **`gh api graphql -F`/`-f` cannot pass input-object variables.** Use
   `--input -` with a JSON `{"query":...,"variables":...}` body (see above).
   This is the single most common reason a hand-written mutation returns
   "provided invalid value" while the same query works in the GitHub docs
   (which assume raw curl with a JSON body, not gh's flag layer).
