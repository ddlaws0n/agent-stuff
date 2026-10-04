# DDIA-Style Architecture Review Rubric

Use this when the user wants a serious review, not a quick answer.

## 1. Data model and access patterns

Questions:

- What entities/facts exist, and which are mutable vs append-only?
- What queries must be fast? Which queries can be asynchronous or analytical?
- Is the data model optimized for writes, reads, search, analytics, or operational simplicity?
- Where will denormalization create stale or duplicated facts?

Red flags:

- Schema chosen before access patterns are known.
- Search, analytics, and OLTP treated as the same workload.
- Derived views with no rebuild path.

## 2. Consistency and transactions

Questions:

- Which invariants must never be violated?
- Which anomalies can the product tolerate: stale reads, lost updates, write skew, duplicate side effects?
- Where does the transaction start and end?
- What side effects happen outside the transaction?

Red flags:

- "ACID" stated without isolation level.
- Cross-service workflow assumes atomicity without saga/compensation/idempotency.
- Timeout interpreted as success or failure without reconciliation.

## 3. Replication, partitioning, and locality

Questions:

- Why replicate: failover, read scale, locality, durability, analytics?
- What is the expected replication lag and how is it exposed?
- What is the partition key and what creates hot partitions?
- Which operations become cross-partition and expensive?

Red flags:

- "Multi-region active-active" with no conflict model.
- Global uniqueness/counters/order assumed across partitions.
- Rebalancing and key skew ignored.

## 4. Caching and derived state

Questions:

- What is cached: object, query result, page, authorization, computed aggregate?
- What invalidates it? What staleness is acceptable?
- Can the cache be safely warmed, bypassed, or rebuilt?
- Does cache failure change correctness or only performance?

Red flags:

- Cache-as-source-of-truth by accident.
- No TTL/invalidation plan.
- Cache stampede under dependency slowness.

## 5. Async boundaries and logs

Questions:

- Are messages commands, events, or facts?
- Can consumers be idempotent?
- Is replay safe?
- What ordering matters and at what key scope?
- What happens to poison messages?

Red flags:

- At-least-once delivery with non-idempotent side effects.
- Global ordering required but partitioned log proposed.
- Dead-letter queue without ownership or reprocessing path.

## 6. Observability and operations

Questions:

- Can operators answer "where is this fact now?"
- What metrics reveal lag, retries, drops, duplicates, saturation, and hot keys?
- What correlation IDs connect user request, events, consumers, and database writes?
- What runbook exists for rollback, replay, migration, or regional failover?

Red flags:

- Happy-path architecture diagram without operational telemetry.
- No way to distinguish missing data from delayed data.
- Migration requires downtime but product assumes continuous availability.

## Review scoring

Use a 1-5 score only if it helps the user prioritize.

<!-- prettier-ignore -->
| Axis | 1 | 3 | 5 |
|-|-|-|-|
| Reliability | Unknown failure behavior | Known major risks, partial defenses | Tested failures, bounded blast radius, clear recovery |
| Scalability | Bottleneck unknown | Main load parameter known | Measured, modeled, and has headroom plan |
| Maintainability | Hard to reason/debug | Some docs and runbooks | Clear data model, evolution path, observability, ownership |
| Semantic clarity | Guarantees assumed | Some guarantees stated | Guarantees explicit per workflow and edge |
