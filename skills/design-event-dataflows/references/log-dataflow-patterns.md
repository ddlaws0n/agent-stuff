# Log and Dataflow Patterns

## Pattern: Transactional outbox

Use when an application writes to a database and must reliably emit an event for the same business change.

Shape:

1. Write business row and outbox row in the same database transaction.
2. Relay publishes outbox rows to the log.
3. Relay marks rows sent or advances cursor.
4. Consumers remain idempotent because relay/publish may duplicate.

Best for:

- Avoiding lost events after DB commit.
- Keeping event emission coupled to the source-of-truth write.

Watch for:

- Outbox table growth.
- Relay lag.
- Schema drift between business row and event payload.

## Pattern: Change Data Capture (CDC)

Use when database changes should become a stream without requiring application code to publish events.

Best for:

- Integration from existing systems.
- Rebuilding projections from write logs.
- Reducing application coupling.

Watch for:

- Low-level row changes may not equal business events.
- Deletes and schema changes need explicit handling.
- Transaction ordering and snapshot bootstrap must be understood.

## Pattern: Event sourcing

Use when application state is intentionally derived from an append-only event log.

Best for:

- Auditability.
- Temporal queries.
- Rebuildable materialized views.

Watch for:

- Event schema evolution is harder than table schema evolution.
- Querying current state requires projections.
- Incorrect historical events need compensating events, not silent mutation.

## Pattern: Materialized view / projection

Use when reads need a shape different from the write model.

Best for:

- Search indexes.
- Dashboards.
- Customer-facing read models.
- ML feature generation.

Watch for:

- Staleness must be acceptable or visible.
- Rebuild path must exist.
- Projection bugs can persist until replay/rebuild.

## Pattern: Batch-to-stream bridge

Use when bounded historical data and unbounded future events must feed the same derived system.

Best for:

- Backfills.
- Migration from batch pipelines to streaming.
- Building a new projection from historical facts.

Watch for:

- Duplicate historical/live records at cutover.
- Different schema assumptions between batch and stream.
- Watermarks and completeness semantics.

## Key design choices

<!-- prettier-ignore -->
| Choice | Useful default | Risk if ignored |
|-|-|-|
| Message type | Immutable domain fact by default; explicit command/notification/snapshot semantics otherwise | Unsafe replay, missing authorization, or stale actions. |
| Event ID | Stable UUID or source-system change ID | Consumers cannot dedupe. |
| Partition key | Entity ID whose ordering matters | Hot partitions or broken ordering. |
| Ordering scope | Per entity, not global | Accidental global ordering dependency. |
| Timestamp fields | occurred_at, recorded_at, emitted_at | Bad analytics and debugging. |
| Data governance | Classification, purpose, least-privilege access, tenant boundary, owner | Sensitive data spreads to durable logs and consumers. |
| Retention/deletion | Long enough for replay/rebuild, with explicit tombstone, legal-hold, and privacy behavior | Irrecoverable drift or indefinite retention of deleted data. |
| Versioning | Additive changes first | Consumer breakage. |
| DLQ policy | Owner + replay path | Permanent silent data loss. |
