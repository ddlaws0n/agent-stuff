# Audit notes

Original package reviewed: `create-github-actions.zip`.

Resolved in version 2.1.0:

- Directory and frontmatter names align.
- Security guidance covers PR, issue/comment, dispatch, `pull_request_target`, `workflow_run`, protected refs, and deployments.
- Static validation checks external actions and job-level reusable workflows for missing, floating, short, and nonstandard refs.
- `--require-sha` enforces full commit SHAs for privileged workflows.
- Untrusted event text and dispatch inputs interpolated directly into `run:` are flagged heuristically.
- Explicit `permissions: {}` and complete job-level permission boundaries no longer produce a missing-permissions warning.
- Output evals use the canonical schema and include an unsafe workflow fixture.
- Contrastive trigger evals distinguish GitHub Actions from adjacent CI/deployment work.

Validation performed:

- Python syntax compilation.
- Five focused validator regression tests.
- Static validation of `assets/node-ci.yml` with zero strict findings.
- Unsafe fixture detection for mutable reusable workflows, direct event-text shell interpolation, overbroad permissions, and privileged checkout.
- Frontmatter, resource, eval-schema, trigger-balance, Markdown-fence, and relative-link checks.
