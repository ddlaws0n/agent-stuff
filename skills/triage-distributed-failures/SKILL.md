---
name: triage-distributed-failures
description: >-
  Triages observed anomalies in distributed and data-intensive production
  systems: duplicate side effects, stale reads after writes, missing downstream
  data, replication lag, failover data loss, consumer lag, out-of-order events,
  clock skew, and disagreeing dashboards. Builds evidence timelines, falsifiable
  hypotheses, reversible containment, and approval-gated repair plans. Use when
  investigating an incident, postmortem, or intermittent production symptom
  involving retries, timeouts, queues, Kafka, CDC, replicas, caches, or derived
  data. Do not use for designing new pipelines or event contracts, architecture
  reviews or ADRs, single-process deterministic bugs, or explaining concepts.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# Triage distributed failures

Diagnose from evidence, not from the architecture diagram. For each component, establish what it knew, when, and how fresh that knowledge was. Treat timeouts, retries, partial failure, duplicate delivery, and lost acknowledgments as normal conditions, not exceptions.

Production mutations are a separate authorization boundary. Never execute retries, replays, rewinds, offset resets, failovers, repairs, or deletions; present them as an approval-gated runbook for the user to run or authorize explicitly.

## Workflow

1. **Pin down the symptom.** Record what was observed, its scope, start/stop times, whether it is ongoing, and which data is at risk: lost, duplicated, stale, reordered, corrupted, or only delayed. Keep user impact, data correctness, and operational symptoms separate.
2. **Build an evidence timeline.** One row per fact: time, component, observation, source, confidence, and what it does and does not prove. Note each timestamp's clock source; do not merge clocks from different hosts without caveat.
3. **Classify the anomaly** using the symptom headings in `references/anomaly-catalog.md`. Consider more than one class; incidents often combine, e.g. a timeout plus redelivery plus a non-idempotent side effect.
4. **Generate competing hypotheses.** For each: the mechanism, evidence for and against, the fastest read-only test that would falsify it, and the repair if it is true. Do not stop at the first plausible explanation.
5. **Contain and preserve.**
   - Prefer reversible containment: disable the affected side effect, pause or isolate the consumer, reduce concurrency, or route reads to the primary.
   - Preserve logs, offsets, consumer-group positions, DLQ contents, provider request IDs, and current row state before retention, compaction, or operator action destroys them.
   - Before any replay, retry, or offset reset, prove the path is idempotent or define dedupe/reconciliation controls, and estimate the replay range and blast radius.
   - Write any mutation as a runbook step with preconditions, stop/rollback conditions, and an explicit operator decision.
6. **Recommend durable fixes** tied to the confirmed mechanism, not a generic list. For a pipeline or contract redesign, recommend handing off to `design-event-dataflows`; for a technology or architecture change, to `review-data-architecture`.
7. **Report** using the Output section.

When evidence is missing, do not block or guess. Proceed with explicitly labeled assumptions, rank hypotheses by what the available evidence supports, and list the specific logs, metrics, or queries that would discriminate between them under open questions. Ask the user only for facts that change the containment decision.

## References

- Read `references/anomaly-catalog.md` during steps 3–4: open the section matching the symptom for likely mechanisms and evidence to collect.
- Use `assets/incident-analysis-template.md` only when the user asks for a postmortem or incident writeup.

## Gotchas

- A timeout does not mean the operation failed; the server or payment provider may have committed. Check the provider or database before retrying.
- If a consumer performs an external side effect before committing its offset or ack, a crash or rebalance in between redelivers the message and repeats the side effect.
- Cache-aside with invalidate-on-write can repopulate the cache from a lagging replica right after invalidation, pinning the stale value for a full TTL. Check where cache fills read from.
- Provider idempotency keys expire after a provider-specific retention window; a retry or replay after expiry is a new operation (for payments, a new charge). Check the window before replaying old requests.
- Run reconciliation queries against a replica, snapshot, or warehouse with limits, not the production primary under incident load.
- Do not assume the latest timestamp is the latest event unless timestamp semantics and clock behavior are known.
- Do not treat dashboard disagreement as data loss until freshness, lag, and metric definitions are compared.
- Use tail latency and retry counts, not averages; retry storms explain most overload cascades.

## Output

A Markdown report with these sections, in order:

1. **Summary**: likely anomaly class, user and data impact, immediate next action.
2. **Evidence timeline**: table of time, component, observation, source, confidence, interpretation.
3. **Hypotheses**: table of hypothesis, mechanism, evidence for, evidence against, fastest falsifying test, repair if true; most likely first.
4. **Containment and evidence preservation**: read-only and reversible steps the user can take now.
5. **Approval-gated actions**: any mutation, with preconditions, range, blast radius, and stop conditions; omit if none.
6. **Durable fixes**.
7. **Open questions**: evidence still needed, with assumptions labeled.
