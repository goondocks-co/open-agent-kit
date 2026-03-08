# Cross-Project Report Examples

## Good Report (Excerpt)

This excerpt demonstrates what a useful cross-project report looks like —
concrete data, specific comparisons, and actionable recommendations.

---

### Executive Summary

The swarm currently connects 4 projects: `api-gateway`, `user-service`,
`billing-service`, and `mobile-app`. All four are active, with `billing-service`
seeing the heaviest recent activity (payment provider migration). Two significant
patterns emerged: all backend services independently implemented retry logic
with exponential backoff, and three projects use different major versions of
the `pydantic` library (v1.10, v2.4, v2.6). The top recommendation is
extracting the shared retry utility into an internal package and aligning
pydantic versions to v2.6.

### Node Inventory

| Project | Status | Tech Stack | Recent Focus |
|---------|--------|------------|--------------|
| api-gateway | Connected | Python 3.12, FastAPI | Rate limiting refactor |
| user-service | Connected | Python 3.12, FastAPI | Auth module cleanup |
| billing-service | Connected | Python 3.11, FastAPI | Payment provider migration |
| mobile-app | Connected | TypeScript, React Native | Push notification overhaul |

### Shared Patterns

**Retry with exponential backoff** — Found in `api-gateway`, `user-service`,
and `billing-service`. All three implement similar retry decorators with jitter.
The `api-gateway` version is the most mature (includes circuit breaker logic).

**Structured logging** — All four projects use `structlog` with JSON output.
Convention is well-aligned; only `mobile-app` uses a slightly different field
naming scheme (`userId` vs `user_id`).

### Recommendations

1. **Extract retry utility** (High priority) — The `api-gateway` retry
   decorator with circuit breaker should become a shared `@org/resilience`
   package. Three projects already need it; extracting prevents further drift.

2. **Align pydantic to v2.6** (Medium priority) — `billing-service` is still
   on v1.10 due to the payment migration. Once that's complete, upgrading
   should be prioritized to prevent API contract divergence.

---

## Why This Report is Good

- **Executive summary leads with findings**, not process. The reader
  immediately knows what matters.
- **Node inventory includes context** — not just "connected/disconnected" but
  what each team is actually doing.
- **Shared patterns are specific** — names the projects, describes the
  implementations, notes which version is best.
- **Recommendations are actionable** — says what to do, who's affected, and
  why it matters. Includes priority.
- **Data over opinion** — "three projects use different pydantic versions" is
  a fact. "pydantic versions should be aligned" follows from the fact.

---

## Bad Report (Excerpt)

This excerpt shows common failure modes — vague observations, no specifics,
and aspirational recommendations.

---

### Executive Summary

The swarm has several connected projects. They seem to be working on various
things. There are some shared patterns and some differences.

### Shared Patterns

- Several projects use Python
- Some projects have similar error handling
- Testing approaches vary

### Recommendations

- Teams should communicate more
- Consider standardizing on common tools
- It would be good to share code where possible

---

## Why This Report is Bad

- **Executive summary says nothing** — "several projects working on various
  things" contains zero information.
- **Patterns lack specifics** — "similar error handling" doesn't say what's
  similar, which projects, or what the pattern actually is. An agent reading
  this learns nothing.
- **Recommendations are platitudes** — "communicate more" and "share code"
  are always true and never actionable. No specifics on what to share, how,
  or with whom.
- **No data** — no project names, no version numbers, no counts, no
  comparisons. The report could apply to any organization.

---

## The Difference

| Aspect | Good Report | Bad Report |
|--------|-------------|------------|
| Executive summary | Findings + top recommendation | "There are some things" |
| Project details | Name, stack, recent focus | "Several projects" |
| Patterns | Specific: which projects, what code, how they differ | "Some projects do X" |
| Recommendations | Action, who, why, priority | "Should do better" |
| Evidence | Concrete data from search results | Vague impressions |

The core principle: **every claim should be traceable to specific search
results from specific projects.** If you can't point to the data, don't
include the claim.
