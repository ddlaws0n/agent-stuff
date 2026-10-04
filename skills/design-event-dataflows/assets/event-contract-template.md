# Message contract: [message.name]

## Message classification and semantics

- Type: domain event/fact | command | notification | state snapshot
- Semantic meaning:
- Replay allowed: yes | no | conditional
- Replay authorization/preconditions:
- Expiry or freshness rule (required for commands, notifications, and snapshots):
- Command authorization/rejection behavior (if applicable):

[State precisely what completed fact, requested action, delivery intent, or current-state observation this message represents.]

## Producer

- Service/system:
- Source-of-truth record/table:
- Emission mechanism: outbox | CDC | direct publish | batch export | other

## Payload

```json
{
  "event_id": "uuid-or-source-change-id",
  "event_type": "domain.entity.action",
  "occurred_at": "2026-01-01T00:00:00Z",
  "recorded_at": "2026-01-01T00:00:01Z",
  "emitted_at": "2026-01-01T00:00:02Z",
  "entity_id": "...",
  "schema_version": 1,
  "data": {}
}
```

## Keys and ordering

- Partition key:
- Required ordering scope:
- Expected duplicate behavior:

## Consumer contract

- Delivery semantics:
- Idempotency/deduplication key:
- Replay safe: yes | no | conditional
- Side-effect retry ceiling:
- Retention:

## Data governance

- Data classification: public | internal | confidential | personal | regulated | credential
- Permitted purpose and minimized fields:
- Access roles and tenant boundary:
- Encryption requirements:
- Residency restrictions:
- Privacy/security owner:
- Deletion or tombstone propagation:
- Legal hold exceptions:
- Replay implications after deletion:

## Schema evolution

- Version carrier: `schema_version` only (do not also encode the version in `event_type` or the topic name unless breaking changes move to a new topic)
- Compatible changes:
- Breaking changes:
- Deprecation policy:

## Observability

- Metrics:
- Logs/traces:
- Reconciliation checks:
