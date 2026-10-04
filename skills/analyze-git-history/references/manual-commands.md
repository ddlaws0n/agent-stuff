# Manual git history commands

Use these commands when `scripts/git-risk-scan.sh` cannot run, or when you need a query the script does not offer. They are all read-only. Replace `REPO` and `SCOPE`, where `SCOPE` is relative to the repository root.

The keyword patterns match whole words, so `prefix` does not count as a fix and `product` does not count as `prod`.

## Setup and sanity checks

```bash
git -C REPO rev-parse --show-toplevel          # fails outside a work tree
git -C REPO rev-parse --verify --quiet HEAD    # fails when there are no commits
git -C REPO rev-parse --is-shallow-repository  # "true" means truncated history
```

## Churn hotspots

```bash
git -C REPO -c core.quotePath=false log --format=format: --name-only --since="1 year ago" HEAD -- SCOPE \
  | grep -vE '^$|(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|Cargo\.lock|go\.sum|Gemfile\.lock|poetry\.lock|uv\.lock)$|(^|/)(dist|build|vendor|node_modules|generated|coverage)/|\.snap$' \
  | sort | uniq -c | sort -nr | head -20
```

This counts deleted and renamed-away paths too. Confirm a file still exists with `git -C REPO ls-tree --name-only HEAD -- <file>`.

## Ownership

```bash
git -C REPO shortlog -sn --no-merges HEAD -- SCOPE                          # all time
git -C REPO shortlog -sn --no-merges --since="6 months ago" HEAD -- SCOPE   # recent
git -C REPO shortlog -sne --no-merges HEAD -- SCOPE                         # show emails to find split identities
git -C REPO shortlog -sn --no-merges HEAD -- SCOPE | grep -viE '\[bot\]|dependabot|renovate'   # without bots
```

Find co-authors that squash merges hide in trailers:

```bash
git -C REPO log --since="1 year ago" --format='%(trailers:key=Co-authored-by,valueonly)' HEAD -- SCOPE \
  | sed '/^$/d' | sort | uniq -c | sort -nr
```

## Bug-fix hotspots

```bash
git -C REPO -c core.quotePath=false log -i -E \
  --grep='(^|[^[:alnum:]_])(fix(e[sd]|ing)?|bug(s|fix(es)?)?|broken|regression|hotfix(es)?|roll ?back|revert(ed|s)?)([^[:alnum:]_]|$)' \
  --format=format: --name-only --since="1 year ago" HEAD -- SCOPE \
  | grep -v '^$' | sort | uniq -c | sort -nr | head -20
```

If the team references issues instead of describing fixes, swap the keyword group for their prefix, such as `--grep='BUG-[0-9]+'`.

## Velocity by month

```bash
git -C REPO log --format='%ad' --date=format:'%Y-%m' HEAD -- SCOPE | sort | uniq -c
```

How to read the shape:

- Steady activity suggests a normal maintenance rhythm.
- A sharp drop can mean a team change, a rewrite, deprecation, or lost ownership.
- A decline over 6 to 12 months can mean reduced investment.
- Spikes between quiet months usually mean release batching.

## Firefighting commits

```bash
git -C REPO log -i -E \
  --grep='(^|[^[:alnum:]_])(revert(ed|s)?|hotfix(es)?|emergency|roll ?back|incident|outage|prod|production fix)([^[:alnum:]_]|$)' \
  --format='%h %ad %s' --date=short --since="1 year ago" HEAD -- SCOPE
```

A handful in a year is normal. Reverts or hotfixes every few weeks suggest weak tests, risky deploys, or brittle areas. Zero matches can mean stability, or just vague messages.

## Single-file drill-down

```bash
git -C REPO log --follow --stat --since="1 year ago" -- path/to/file
git -C REPO log --follow -p --since="3 months ago" -- path/to/file
```
