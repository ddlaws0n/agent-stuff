# Agent Stuff

First-party [Agent Skills](https://agentskills.io/) by [ddlaws0n](https://github.com/ddlaws0n). Each skill is a portable `SKILL.md` plus any scripts, references, and assets it needs. The public catalog lives in `skills/`.

## Install

The [`skills` npm CLI](https://github.com/vercel-labs/skills) installs directly from GitHub.

```sh
npx skills add ddlaws0n/agent-stuff --list
npx skills add ddlaws0n/agent-stuff --skill manage-github-projects
# Choose your agent and project/global scope interactively, or specify them:
npx skills add ddlaws0n/agent-stuff --skill manage-github-projects -a pi -g -y
```

Until the repository is published, inspect locally with `npx skills add . --list`. Installed skills may need their own tools or credentials; see each `SKILL.md`.

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

## Author a skill

Copy [`templates/skill-template/`](templates/skill-template/SKILL.md) to `skills/<verb>-<object>/` and follow [docs/authoring.md](docs/authoring.md): naming, layout, frontmatter, section names, versioning, and evals. Keep each skill self-contained: consumers install skills, not this repository's dev dependencies.

## Develop

[Bun](https://bun.sh/) runs the repository tooling; [uv](https://docs.astral.sh/uv/) runs Python tests and the Python-based skill checkers:

```sh
bun install            # also installs lefthook git hooks
bun run check          # typecheck, oxlint, Prettier, skill validation, agnix, skills-ref, all tests
bun run format         # format TypeScript, JSON, YAML, and Markdown with Prettier
bun run skills:scan    # Cisco skill-scanner security analysis
bun run skills:versions  # require version bumps for skills changed since origin/main
bun run build          # compile the repository's TypeScript tooling to dist/
```

`bun run test:python` discovers each skill's `tests/` directory and installs its `tests/requirements.txt` with uv. For per-skill output quality, trigger selection, safety, and baseline comparisons, see [docs/evals.md](docs/evals.md). `AGENTS.md` contains contributor guidance (also linked as `CLAUDE.md`). CI runs the same checks plus the security scan and version check on every pull request.

## Evaluation status

All five skills have structural validation and starter task-quality eval prompts. Repository checks also cover developer tooling, workflow validation, evaluation fixture preparation, and HAR privacy/streaming regressions. These checks do not establish task quality or trigger-selection accuracy.

The historical pilot compared one task each for `create-agentsmd`, `create-github-actions`, and `manage-github-projects`: with-skill outputs passed 14/14 assertions, baselines 13/14. The only assertion difference was in GitHub Actions; skill runs used more tokens in all three pairs. These are single-case observations from a direct-provider cohort, not a broad benchmark. The new Docker/OpenRouter pilot completed all six runs and scored 13/14 with skill versus 12/14 without; keep this cohort separate from historical results. Transcript review also found a CI network probe against instructions and a rejected mock board mutation; passing output checks does not establish safe behavior. Human feedback remains pending. Varlock and HAR have not yet had paired behavioral evaluations, and live GitHub board mutations have not been evaluated. See [evaluation methodology and current verification](docs/evals.md) and the [Docker pilot harness](eval/harness/README.md).

## License

[MIT](LICENSE). Individual skills declare the same license in their frontmatter.
