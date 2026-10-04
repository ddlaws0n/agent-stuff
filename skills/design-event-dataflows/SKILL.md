---
name: design-event-dataflows
description: >-
  Designs log-centric event dataflows: message classification, event
  contracts, partition keys and ordering scope, outbox or CDC producer
  semantics, idempotent consumers, replayable projections, schema evolution,
  retention, and deletion propagation. Use when the user asks to design or
  review Kafka, Pub/Sub, Kinesis, or SQS event flows, transactional outbox or
  CDC pipelines, stream-to-warehouse or search-index projections, backfills,
  event schemas, or data contracts. Do not use for diagnosing live production
  anomalies, broad technology selection or ADRs, broker cluster operations, or
  simple queue usage with no ordering, replay, or consistency question.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# Design event dataflows

Hand active production anomalies to `triage-distributed-failures` and system-wide technology decisions or ADRs to `review-data-architecture`.

## Workflow

1. **Inspect before designing.** Read existing event schemas, schema-registry subjects, outbox tables, broker/topic config (partitions, retention, `cleanup.policy`), and consumer code when available. Record what is fixed versus open. Scale depth to the request: a single event question needs one contract, not the full report.
2. **Classify messages and sources of truth.** Name each business fact (`invoice-paid`, `user-deactivated`) and its authoritative system. Classify every message as one of:
   - **Domain event**: immutable completed fact; replayable under defined controls.
   - **Command**: requested action; define authorization, expiry, dedupe, rejection, and whether replay is forbidden.
   - **Notification**: delivery-oriented; define audience, expiry, and retry ceiling; historical replay is usually meaningless.
   - **State snapshot**: replaceable current state; define version/freshness and compaction.

   Keep commands and notifications off a replayable fact log unless their retention and replay rules are explicit.

3. **Define contracts.** For each message: semantic meaning, producer, entity key, partition key, event ID for dedupe, one versioning mechanism, ordering scope, `occurred_at` versus `recorded_at` versus `emitted_at`, data classification with minimized payload, access/tenant boundary, retention, and deletion behavior. Fill `assets/event-contract-template.md` when the user wants written contracts.
4. **Choose producer semantics.** Prefer a transactional outbox or CDC over publishing after commit. State what happens when the DB write succeeds but publish fails, and when publish succeeds but the ack is lost.
5. **Set log semantics.** Retention and replay window, partitioning and ordering guarantees, compaction versus append-only, backpressure and lag limits, poison-message and DLQ ownership, offset ownership and reset policy.
6. **Design consumers and projections.** Separate side-effecting consumers from those that only build derived state. Give each an idempotency strategy and a rebuild path (log replay or source snapshot). State behavior when behind, replaying, or reading an old schema version.
7. **Connect operational and analytical views.** Show how OLTP rows, the log, warehouse, search indexes, dashboards, and ML features relate. State where temporary disagreement is acceptable, its expected bound, and how it is reconciled.
8. **Plan validation.** Duplicate-delivery, replay/rebuild, and schema-compatibility tests; lag and freshness alarms; reconciliation checks against the source of truth.

## References

- Read `references/log-dataflow-patterns.md` when choosing between outbox, CDC, event sourcing, projections, or a batch-to-stream bridge, or when setting defaults for keys, timestamps, retention, and DLQs.
- Fill `assets/event-contract-template.md` when the user asks for event contracts or data contracts.

## Gotchas

- Kafka exactly-once (idempotent producer plus transactions) covers only read-process-write within Kafka. Writes to databases, APIs, email, or payments still need idempotency keys or reconciliation.
- Commit the consumer offset only after the side effect or projection write succeeds. Committing first turns a crash into silent loss; committing after means duplicates, so the consumer must be idempotent.
- Adding partitions to a Kafka topic remaps keys to new partitions and breaks per-key ordering for in-flight entities. Size partitions up front or migrate to a new topic deliberately.
- Ordering is per partition, never global. SQS standard queues have no ordering and may deliver duplicates; SQS FIFO orders only within a `MessageGroupId` and dedupes only within a 5-minute window.
- Pub/Sub ordering keys only take effect when message ordering is enabled on the subscription and the publisher sets ordering keys; a failed publish pauses that key until resumed.
- A tombstone on a compacted topic deletes the key only after compaction runs and `delete.retention.ms` passes; it does not purge non-compacted topics, consumer copies, warehouses, or backups. For hard-delete or erasure requirements, consider crypto-shredding (per-subject keys destroyed on delete).
- CDC emits row changes, not business facts. Map rows to domain events or accept that consumers depend on the table schema.
- Do not add a DLQ without an owner, triage path, and replay process.
- Do not build dashboards from derived data without stating freshness and reconciliation.

## Output

Return sections in this order, omitting any the request does not need:

1. **Summary**: recommendation and the biggest semantic risk.
2. **Dataflow**: text diagram from source of truth through log to each consumer.
3. **Messages**: one row per message.
4. **Producer semantics**: outbox, CDC, or direct publish, with failure behavior.
5. **Consumers**: one row per consumer.
6. **Failure modes**: failure, impact, defense, detection.
7. **Validation plan**: checklist of tests and alarms.

Message table shape (put governance and retention detail in per-message contracts, not the table):

<!-- prettier-ignore -->
| Message | Type | Key / ordering scope | Dedupe key | Replay |
|-|-|-|-|-|

Consumer table shape:

<!-- prettier-ignore -->
| Consumer | Purpose | Idempotency | Replay safe | Side effects |
|-|-|-|-|-|
