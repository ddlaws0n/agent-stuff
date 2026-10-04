# Incident analysis: [incident title]

## Summary

[What happened, who was affected, and current status.]

## Impact

- Users/customers affected:
- Data affected: lost | duplicated | stale | delayed | inconsistent | unknown
- Duration:
- Severity:

## Timeline

<!-- prettier-ignore -->
| Time | Event | Evidence/source | Confidence |
|-|-|-|-|

## What each component knew

<!-- prettier-ignore -->
| Component | Knowledge/state | Freshness | Confidence | Notes |
|-|-|-|-|-|

## Root cause hypothesis

[Mechanism, not just component name.]

## Contributing factors

- [Factor]

## Detection gaps

- [Gap]

## Remediation

### Immediate containment

[Prefer reversible, evidence-preserving actions.]

### Approval-gated production actions

- Proposed mutation:
- Preconditions and idempotency/replay proof:
- Estimated range and blast radius:
- Stop/rollback conditions:
- Approver/operator:

### Data repair

### Durable fixes

## Follow-up validation

- [ ] Replay test in an isolated or non-production environment before any production replay
- [ ] Duplicate delivery test
- [ ] Failover drill
- [ ] Reconciliation query
- [ ] Alert threshold change
