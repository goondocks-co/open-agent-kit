# RFC-{{ rfc_number }}: {{ title }}

**Author:** {{ author }}
**Date:** {{ date }}
**Status:** {{ status }}
**Tags:** {{ tags | join(', ') }}

## Summary

> Provide a concise summary of the feature, the user benefit, and the desired outcome.

## User Story

**As a** …  **I want** …  **So that** …

> Capture the primary user persona, the capability they need, and the value delivered.

## Background

> Explain why users need this capability now. Reference support tickets, analytics, usability studies, or business commitments.

### Current State
> Describe how users achieve (or fail to achieve) this today.

### Pain Points
- [ ] Pain point …
- [ ] Pain point …

## Proposed Solution

> Detail what will change. Include scope boundaries and links to supporting documents or mockups.

### User Experience
> Describe interaction flows, accessibility considerations, and the desired end-to-end experience.

#### User Flow
1. Step …
2. Step …
3. Step …

#### Wireframes / Mockups
> Link to designs or embed key visuals.

### Functional Requirements
- [ ] Requirement … (use MUST/SHALL language with acceptance criteria)
- [ ] Requirement …

### Non-Functional Requirements
- **Performance:** …
- **Scalability:** …
- **Accessibility:** …
- **Security / Privacy:** …

## Technical Design

> Explain how the feature will be built end-to-end.

### Architecture
> Provide a high-level architecture diagram or narrative. Note new services/components.

### Components
**Frontend**
- Component …
- …

**Backend**
- Service …
- …

**Database / Storage**
- Schema or data model changes …

### API Design
```json
// Replace with representative request/response payloads
POST /api/resource
{
  "field": "value"
}
```

### Data Model
> Describe schema updates, migrations, retention, and governance considerations.

## Dependencies

> List upstream/downstream services, libraries, feature flags, or team deliverables required.

- Dependency …
- Dependency …

## Acceptance Criteria

> Define how reviewers will confirm the feature is complete.

- [ ] Criterion …
- [ ] Criterion …

## Testing Plan

### Test Scenarios
1. **Scenario:** …
   - Given …
   - When …
   - Then …

2. **Scenario:** …
   - Given …
   - When …
   - Then …

### Test Coverage
- Unit tests: …
- Integration tests: …
- E2E tests: …

## Implementation Plan

> Break work into phases with owners, timelines, and deliverables.

### Phases
**Phase 1 – …** (Est: …)
- Task …
- Task …

**Phase 2 – …** (Est: …)
- Task …
- Task …

### Milestones
- [ ] Milestone … – Date …
- [ ] Milestone … – Date …

## Rollout Strategy

> Describe launch mode (feature flag, beta, controlled rollout) and blast-radius controls.

- [ ] Feature flag configured
- [ ] Beta cohort defined
- [ ] Phased rollout approved
- [ ] Full release readiness confirmed

### Launch Checklist
- [ ] Documentation updated
- [ ] Monitoring/alerts defined
- [ ] Support/Success teams trained
- [ ] Marketing/Comms plan ready

## Success Metrics

> Define quantitative targets that demonstrate user and business value.

- Metric … (target …)
- Metric … (target …)

## Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| … | H/M/L | H/M/L | … |
| … | H/M/L | H/M/L | … |

## Alternatives Considered

### Alternative 1
> Summarize the alternative and why it was rejected.

### Alternative 2
> Summarize the alternative and why it was rejected.

## Open Questions

- [ ] Question …
- [ ] Question …

## Future Enhancements

> Note ideas intentionally deferred from this iteration.

- [ ] Enhancement …
- [ ] Enhancement …

## References

> Link to supporting artifacts (tickets, dashboards, research, related RFCs).

- Reference …
- Reference …

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| {{ date }} | 0.1 | Initial draft | {{ author }} |
