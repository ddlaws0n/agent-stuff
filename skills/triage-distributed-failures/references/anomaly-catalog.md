# Distributed Data-System Anomaly Catalog

Use this catalog to generate hypotheses quickly. Do not stop at the first plausible explanation; list evidence needed to disconfirm it.

## Symptom: user saw old data after a successful write

Likely mechanisms:

- Read routed to async replica with replication lag.
- Cache served stale value after write.
- Write succeeded but read used a different key/entity ID.
- Client retried and saw response from previous state.
- Transaction committed but event/materialized view update lagged.

Evidence to collect:

- Primary DB commit timestamp and row version.
- Replica lag at read time.
- Cache key, TTL, invalidation event, and cache hit/miss.
- Request IDs for write and read.
- Whether UI reads source-of-truth or projection.

## Symptom: duplicate processing or duplicate external side effect

Likely mechanisms:

- Client retry after timeout.
- Queue at-least-once redelivery.
- Consumer crashed after side effect before offset commit.
- Producer published duplicate events.
- Replay/backfill mixed with live processing.

Evidence to collect:

- Idempotency key presence and dedupe-store state.
- Queue delivery count and offset commits.
- Consumer logs around crash/restart.
- External provider request IDs.
- Event IDs and payload hashes.

## Symptom: data missing downstream

Likely mechanisms:

- Direct publish failed after DB commit.
- Outbox/CDC relay lag or crash.
- Consumer lag, poison message, or DLQ.
- Retention expired before consumer caught up.
- Schema incompatibility caused consumer drops.

Evidence to collect:

- Source DB row and commit time.
- Outbox row / CDC position.
- Topic offset, consumer group lag, DLQ entries.
- Schema registry compatibility errors.
- Retention policy and earliest available offset.

## Symptom: analytics disagree with product UI

Likely mechanisms:

- Dashboard is eventually consistent and behind.
- Different definitions/filters between OLTP and analytics.
- Late-arriving events or watermark behavior.
- Backfill duplicated or omitted historical facts.
- Deletes/updates handled differently in warehouse.

Evidence to collect:

- Metric definition and query in each system.
- Data freshness timestamp shown to users.
- Ingestion lag and processing lag.
- Reconciliation for sample entity IDs.
- Backfill and dedupe logic.

## Symptom: failover caused data loss or conflicting writes

Likely mechanisms:

- Replica promoted before fully caught up.
- Old primary accepted writes after network partition.
- Split-brain leadership.
- Client wrote to wrong region during isolation.
- Async replication acknowledged before durable majority.

Evidence to collect:

- Failover timeline and leader-election logs.
- Last applied log position on primary and replica.
- Client routing records.
- Write acknowledgment mode.
- Conflicting row versions or vector/causal metadata if available.

## Symptom: order-dependent bug

Likely mechanisms:

- Multiple partition keys used for same entity.
- Concurrent writers racing.
- Global ordering assumed from partitioned log.
- Consumers process events in parallel without per-key serialization.
- Clock timestamps used as ordering source.

Evidence to collect:

- Event IDs, keys, partitions, offsets, and timestamps.
- Producer concurrency and retry behavior.
- Consumer parallelism configuration.
- Per-entity event history.

## Symptom: client timed out but the outcome is unknown

Likely mechanisms:

- Server committed; response lost or arrived after the client deadline.
- Request still queued or executing when the client gave up.
- Client retried, so the operation ran twice or the retry hit a conflict.

Evidence to collect:

- Server-side commit or provider record for the request ID.
- Client and server timeout settings, including proxies and load balancers.
- Retry count and whether retries reused the idempotency key.

## Symptom: one partition, shard, or consumer saturated

Likely mechanisms:

- Skewed key (large tenant, null or default key, celebrity entity).
- Retries or redeliveries concentrated on one key.
- Slow poison message blocking a partition.

Evidence to collect:

- Per-partition throughput, lag, and error rate, not cluster averages.
- Top keys by volume in the affected window.
- Consumer processing time per message and rebalance events.

## Symptom: events or records appear in the wrong time order

Likely mechanisms:

- Clock skew between producers or hosts.
- Event time vs processing time vs ingestion time confused.
- Process pause (GC, VM migration) delayed writes past a lease or deadline.
- Late-arriving data dropped or misassigned by a watermark.

Evidence to collect:

- Which clock produced each timestamp and its NTP offset.
- Log offsets or sequence numbers alongside timestamps.
- Watermark and allowed-lateness configuration.

## Symptom: consumers fail or drop fields after a deploy or backfill

Likely mechanisms:

- Producer shipped a schema the consumer cannot read.
- Compatibility mode allowed a change readers mishandle (renamed field, changed default).
- Backfill wrote records in an old or new format.

Evidence to collect:

- Schema registry versions and compatibility mode.
- Producer and consumer deploy times on the timeline.
- Deserialization errors and DLQ entries by schema version.
