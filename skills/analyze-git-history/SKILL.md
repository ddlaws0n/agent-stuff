---
name: analyze-git-history
description: >-
  Builds a read-only risk map of a git repository from its history: churn
  hotspots, ownership concentration, bug-fix clusters, velocity, and
  revert/hotfix patterns, to decide what to read first. Use when onboarding to
  an unfamiliar or legacy repo, auditing tech debt, finding risky files or bus
  factor, or asking where to start reading code. Do not use for security
  scanning, line-level code review, or git operations such as rebase or blame.
license: MIT
compatibility: >-
  Requires git 2.x and bash 3.2+ with standard awk and sort. Read-only; needs
  no network access.
metadata:
  author: ddlaws0n
  version: "0.2.0"
---

# Analyze Git History

Build a triage map from git history before reading source, so you know which files to read first, which areas are risky to change, and which assumptions to confirm with the team. History points at code worth inspecting; it never proves code quality.

Stay read-only. Do not check out, reset, fetch, unshallow, or otherwise change the repository unless the user explicitly asks.

## Workflow

1. **Scope.** Choose the narrowest meaningful path: the user's subsystem, `src/`, `app/`, or `packages/<service>/`. Scan the repo root only for small repos or when the user asks for a repo-wide view; lockfiles, generated code, and changelogs dominate root-level counts.
2. **Scan.** Run `bash scripts/git-risk-scan.sh` (see [Scripts](#scripts)) with that scope. Widen `--since` for slow-moving repos. Read its Warnings first: a shallow clone or an empty scope changes what you can claim.
3. **Cross-check.** Rank files that appear in both churn and bug-fix lists highest. Compare all-time and recent owners to spot departed experts. Sample `git log --format=%s -n 50` to judge commit-message quality before trusting keyword counts, and check for split identities and bots (see [Gotchas](#gotchas)).
4. **Drill down.** For the top three to five files, run `git log --follow --stat --since="1 year ago" -- <file>` and `git log --follow -p --since="3 months ago" -- <file>`, then read the current source. Use the diffs to name repeated failure modes before judging the implementation.
5. **Report.** Write the risk map in the [Output](#output) shape and label each claim with a confidence level.

## Scripts

- `scripts/git-risk-scan.sh`: Prints a Markdown report with churn hotspots, all-time and recent ownership, bug-fix hotspots, their overlap, monthly velocity, and firefighting commits. It filters lock, vendored, and generated paths (unless `--include-generated` is set), skips paths that no longer exist at HEAD, and warns about shallow clones. Run it with `bash scripts/git-risk-scan.sh --path <repo> --scope src --since "1 year ago" --active-since "6 months ago" --limit 20`. `--scope` is relative to the repository root. Exit codes: 3 means the path is not a git work tree and 4 means the repository has no commits. Use `--help` for all options.

## References

- Read `references/manual-commands.md` when the script cannot run (no bash), or when you need a custom query: bot filtering, co-author trailers, identity checks, or a different keyword set.

## Gotchas

- **Squash merges:** GitHub records each squash-merged PR as one commit under the PR author. Co-authors survive only as `Co-authored-by` trailers, which `shortlog` ignores, so counts measure PRs, not commits. With rebase merges, authors are kept and the maintainer becomes the committer. `--no-merges` drops merge commits.
- **Identities:** `shortlog` applies `.mailmap` when it exists. Without one, a person who changed name or email appears as several people, which understates concentration. Check `git shortlog -sne HEAD -- <scope>` and merge obvious duplicates in your report, saying you did so.
- **Bots:** Dependabot, Renovate, and release bots inflate churn and ownership. Exclude them before calling anyone an owner.
- **Keywords:** Bug and firefighting counts depend on commit-message discipline. Vague messages ("update stuff") or issue-ID-only messages mean low confidence; search the team's issue prefixes if you know them.
- **Renames and deletions:** The script ranks only paths that exist at HEAD, and a file renamed inside the lookback window loses its pre-rename touches. Use `--follow` only for single-file drill-down.
- **Shallow clones:** History is truncated. Report the limitation; `git fetch --unshallow` uses the network and changes the repository, so ask first.
- **Churn:** High churn in an active product area can be healthy. Generated, snapshot, and migration files can still slip past the filter.
- **Imported or young repos:** History converted from another VCS, or only a few months old, cannot support strong conclusions.
- Treat contributor counts as knowledge-transfer risk, never as a performance judgement.

## Output

Use this shape:

```markdown
# Git History Risk Map: [repo/scope]

## Executive summary

[3-6 bullets: highest-risk areas, strongest signals, biggest caveats]

## Top risk files

<!-- prettier-ignore -->
| Rank | File | Why it matters | Evidence | Confidence | Next step |
|-|-|-|-|-|-|
| 1 | path/to/file | Churn + bug fixes | 42 changes; 11 bug-fix touches | High | Read last 3 months of diffs and tests |

## Ownership and bus factor

[Concentration (flag one author at roughly 60%+ of commits), departed historical owners, active maintainers]

## Velocity and delivery shape

[Monthly pattern; separate facts from hypotheses]

## Firefighting signals

[Reverts, hotfixes, rollbacks; quote short commit subjects]

## Caveats

[Squash merges, identities, bots, generated files, weak messages, scope, renames, shallow history]

## Recommended first-code-reading path

1. [file/dir]: [reason]
```

Confidence levels:

- **High:** the file shows up in churn and bug-fix lists, plus firefighting or ownership risk.
- **Medium:** the signal is strong in one dimension, but caveats remain.
- **Low:** history is weak or shallow, the workflow is squash-heavy, commit messages are vague, or generated files contaminate the counts.

Before sending, check that every top file has cited evidence, that hypotheses are labeled as hypotheses, and that the report ends with a concrete reading path. Never call code "bad" from history alone; say it "deserves first inspection" or "is a likely maintenance risk".
