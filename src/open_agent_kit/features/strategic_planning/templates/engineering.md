# RFC-{{ rfc_number }}: {{ title }}

**Author:** {{ author }}
**Date:** {{ date }}
**Status:** {{ status }}
**Tags:** {{ tags | join(', ') }}

## Summary

> Provide a 2-3 sentence executive summary covering the current state, the proposed change, and the expected impact. Cite key metrics or user pain where possible.

## Motivation

> Explain why this change is required now. Reference incidents, metrics, OKRs, or user feedback that make the problem urgent.

**Problem Statement**
> Describe the problem or opportunity in concrete terms, including quantitative evidence.

**Impact**
> Identify who is affected and the consequences of not acting.

**Goals**
- [ ] Goal: State a measurable outcome (e.g., "Reduce P99 latency from X to Y by date").
- [ ] Goal: …
- [ ] Goal: …

**Non-Goals**
- [ ] Explicitly list work that is out of scope to avoid ambiguity.

## Detailed Design

> Outline the technical approach with enough depth that reviewers can assess feasibility, risks, and effort.

### Architecture
> Provide a high-level diagram or description of component interactions. Mention new services, data flows, or protocols.

### Implementation Details
> Document algorithms, data structures, configuration changes, deployment updates, and any code modules impacted.

### API/Interface Changes
> Specify new or modified APIs. Include request/response schemas, backwards-compatibility guarantees, and versioning plans.

```python
# Replace with representative pseudocode or remove this block.
def example_function():
    ...
```

### Data Model
> Describe schema changes, migration requirements, retention policies, and rollbacks.

### Dependencies
> List external services, libraries, feature flags, or infrastructure work required.

### Migration Strategy
> Explain how to transition from current to future state, including sequencing, dark launches, and rollback triggers.

## Drawbacks

> Enumerate risks, trade-offs, and costs (operational, performance, product). Provide mitigation plans for each.

- [ ] Drawback / risk, with mitigation ownership.
- [ ] …

## Alternatives

> Summarize other approaches considered. Highlight why they were rejected (data, complexity, risk, timeline).

### Alternative 1
**Description**
> Outline the alternative approach.

**Pros**
- [ ] Advantage …

**Cons**
- [ ] Concern …

### Alternative 2
**Description**
> Outline another viable option.

**Pros**
- [ ] Advantage …

**Cons**
- [ ] Concern …

## Security Considerations

> Detail authentication, authorization, encryption, data privacy, and threat-model changes. Link to security reviews if applicable.

## Performance Implications

> Provide expected performance impact, benchmarking plans, scaling considerations, and capacity estimates.

## Testing Strategy

> Describe how you will validate correctness at each layer. Include automated coverage, integration environments, and load testing.

- Unit tests: …
- Integration tests: …
- Performance tests: …

## Rollout Plan

> Define rollout phases, feature flag strategy, blast-radius controls, and rollback procedures with owners and timelines.

1. Phase 1 – …
2. Phase 2 – …
3. Phase 3 – …

## Monitoring and Observability

> List metrics, logs, traces, and alerts required to ensure the change is healthy. Include SLO/SLA amendments if relevant.

- Metrics: …
- Logs: …
- Alerts: …

## Documentation

> Note which runbooks, user guides, architecture docs, or onboarding materials must be updated.

- [ ] User documentation
- [ ] API documentation
- [ ] Architecture diagrams / ADRs
- [ ] Runbooks / on-call guides

## Unresolved Questions

> Track outstanding decisions or unknowns that need resolution before implementation.

- [ ] Question …
- [ ] Question …

## Future Work

> Capture follow-on efforts that are out of scope now but enabled by this change.

- [ ] Future item …
- [ ] Future item …

## References

> Link to supporting resources (tickets, dashboards, ADRs, research, prior RFCs).

- Reference: …
- Reference: …

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| {{ date }} | 0.1 | Initial draft | {{ author }} |
