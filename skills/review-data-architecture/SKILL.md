---
name: review-data-architecture
description: >-
  Reviews architecture decisions for data-intensive systems by starting from
  constraints, making guarantees explicit per workflow, and comparing options
  by failure mode, operational burden, and validation plan. Use when the user
  asks for an architecture review, ADR, migration design, or technology choice
  involving databases, transactions, caching, replication, partitioning,
  multi-region, or managed data services. Do not use for active incident triage
  (triage-distributed-failures), detailed event or pipeline contracts
  (design-event-dataflows), query or index tuning, or formatting and filing
  existing documentation (maintain-project-docs).
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# Review data architecture

## Workflow

1. Read what the user provided first: diagrams, ADRs, schemas, configs, or code in the repository. Cite those artifacts, not generic patterns.
2. Ask for the numbers that would change the answer before recommending: read/write rates and burstiness, data size and growth, p99 latency targets, RPO/RTO, and the business invariants that must never break. If the user wants an answer now, proceed and label each missing number as an assumption.
3. Frame the decision in one sentence and separate facts, assumptions, and open questions.
4. Annotate each component and data edge: source of truth; sync, async, batch, stream, CDC, or cache fill; delivery semantics; ordering scope (global, partition key, entity, none); transaction boundary and the side effects outside it; behavior on timeout, retry, duplicate, replay, and consumer lag.
5. Compare options with failure modes, complexity moved, and operational burden as explicit dimensions. Judge guarantees per workflow, not per database brand.
6. Recommend only after the constraints and trade-offs are visible. State what must stay true for the recommendation to hold, and give a conservative alternative when one exists.
7. Propose concrete validation: invariant checks, load tests, failure drills, or migration checks that could falsify the design.

## References

- Read `references/review-rubric.md` for a full review or an ADR, or when the user asks for a scored assessment. Skip it for a quick question.
- Fill in `assets/adr-template.md` when the user asks for a new ADR or decision record. Only reformatting or filing an existing ADR belongs to maintain-project-docs.

## Gotchas

- Do not reduce database choice to "SQL for consistency, NoSQL for scale." Name the exact invariants and access patterns.
- Cloud-managed services do not remove operations. They move the work and can reduce visibility.
- Do not accept an "exactly once" claim without naming the boundary where duplicates are still possible, such as external side effects like payments or email.
- A timeout is neither success nor failure. Require reconciliation or idempotency keys wherever a caller retries.
- Do not use CAP as a slogan. Discuss operation-specific behavior during partitions, latency, and failover.
- "ACID" without an isolation level says nothing about lost updates or write skew.
- Optimize for p99, not average latency, when tail latency affects users or retries amplify load.
- Do not recommend microservices or eventing when a local invariant would be protected more simply by a single transaction.
- Hand off when the primary goal shifts: a production anomaly goes to triage-distributed-failures, and event contracts or replay policy go to design-event-dataflows.

## Output

Scale the response to the request:

- **Quick question** (one choice, few constraints): a direct recommendation, the two or three constraints that decide it, the main failure mode, and the assumptions that would change the answer. No headings beyond what aids reading.
- **Full review**: an executive summary (recommendation, biggest risk, next validation step); facts and assumptions; critical workflows and invariants; edge semantics with hidden failure modes; a trade-off matrix; the recommendation and alternatives; a validation checklist; and the open questions that could change the recommendation.
- **ADR**: follow `assets/adr-template.md`.

Use this trade-off matrix shape in full reviews:

<!-- prettier-ignore -->
| Option | Gains | Costs | Complexity moved | Failure modes | Operational burden | Confidence |
|-|-|-|-|-|-|-|
