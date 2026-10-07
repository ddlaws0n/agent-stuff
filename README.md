# Agent Stuff

First-party [Agent Skills](https://agentskills.io/) by [ddlaws0n](https://github.com/ddlaws0n). Each skill in `skills/` is a self-contained `SKILL.md` plus any scripts, references, and assets it needs.

## Install

```sh
npx skills add ddlaws0n/agent-stuff --list
npx skills add ddlaws0n/agent-stuff --skill manage-github-projects
```

Uses the [`skills` CLI](https://github.com/vercel-labs/skills). Some skills need their own tools or credentials; see each `SKILL.md`.

## Catalog

<!-- prettier-ignore -->
| Skill | Purpose |
|-|-|
| [`analyze-git-history`](skills/analyze-git-history/SKILL.md) | Map churn, ownership, and bug-fix hotspots from git history to decide what to read first. |
| [`analyze-har-workflows`](skills/analyze-har-workflows/SKILL.md) | Analyze browser network captures and assess workflow automation. |
| [`build-ui-tailwind`](skills/build-ui-tailwind/SKILL.md) | Build, migrate, and audit Tailwind CSS v4 projects with the CSS-first model. |
| [`create-agentsmd`](skills/create-agentsmd/SKILL.md) | Create repository-grounded agent instructions. |
| [`create-github-actions`](skills/create-github-actions/SKILL.md) | Create and review secure GitHub Actions workflows. |
| [`design-event-dataflows`](skills/design-event-dataflows/SKILL.md) | Design event contracts, ordering, outbox/CDC, and replayable projections for log-centric dataflows. |
| [`maintain-project-docs`](skills/maintain-project-docs/SKILL.md) | Create, update, and consolidate project Markdown documentation against the repository. |
| [`manage-environments-orbstack`](skills/manage-environments-orbstack/SKILL.md) | Configure, migrate, and troubleshoot OrbStack containers and Linux machines on macOS. |
| [`manage-github-projects`](skills/manage-github-projects/SKILL.md) | Manage GitHub Projects v2 boards and their issues via `gh` and Python. |
| [`manage-secrets-varlock`](skills/manage-secrets-varlock/SKILL.md) | Manage schema-driven environment configuration and secrets with Varlock. |
| [`review-data-architecture`](skills/review-data-architecture/SKILL.md) | Review data-intensive architecture decisions by guarantees, failure modes, and operational cost. |
| [`triage-distributed-failures`](skills/triage-distributed-failures/SKILL.md) | Triage production anomalies in distributed systems with evidence timelines and approval-gated repair. |

## Develop

Requires [Bun](https://bun.sh/) and [uv](https://docs.astral.sh/uv/).

```sh
bun install       # also installs git hooks
bun run check     # typecheck, lint, format, skill validation, tests
```

New skills start from [`templates/skill-template/`](templates/skill-template/SKILL.md); see [docs/authoring.md](docs/authoring.md) and [docs/evals.md](docs/evals.md). Contributor and agent guidance is in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
