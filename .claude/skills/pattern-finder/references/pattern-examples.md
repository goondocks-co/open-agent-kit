# Pattern Finder Examples

## Good Pattern Report (Excerpt)

This excerpt demonstrates a useful pattern analysis — specific code patterns
identified across projects with concrete extraction recommendations.

---

### Executive Summary

Analyzed 4 projects across the swarm. Found 5 significant shared patterns: retry
logic (3 projects), structured logging setup (4 projects), health check endpoints
(3 projects), configuration loading (4 projects), and database migration helpers
(2 projects). The retry logic and health check patterns are strong extraction
candidates — implementations are similar enough to merge with minimal effort.

### Shared Patterns

#### Retry with Exponential Backoff

- **Where:** api-gateway, user-service, billing-service
- **What:** All three implement an async retry decorator with configurable max
  retries, base delay, and jitter. The core algorithm is identical:
  `delay = base_delay * (2 ** attempt) + random.uniform(0, jitter)`.
- **Variation:** api-gateway adds circuit breaker logic (trips after N
  consecutive failures). user-service adds per-exception-type retry config.
  billing-service is the simplest (no extras).
- **Assessment:** Strong extraction candidate. The api-gateway version is
  the most complete and could serve as the base for a shared package. The
  user-service per-exception config is a useful addition. Estimated effort:
  low (1-2 days to package and replace in all three).

#### Health Check Endpoints

- **Where:** api-gateway, user-service, billing-service
- **What:** All expose `GET /health` returning `{"status": "ok", "version": "..."}`.
  Each adds service-specific checks (database connectivity, cache reachability).
- **Variation:** api-gateway includes upstream dependency health. billing-service
  adds payment provider ping. user-service checks auth provider.
- **Assessment:** Good extraction candidate. The base health check pattern
  (status + version + configurable dependency checks) could be a shared
  middleware. Each project would register its own dependency checkers.

### Extraction Candidates

| Candidate | Found In | Description | Effort | Priority |
|-----------|----------|-------------|--------|----------|
| Retry decorator | api-gw, user-svc, billing-svc | Exponential backoff with jitter + circuit breaker | Low | High |
| Health check middleware | api-gw, user-svc, billing-svc | Standardized health endpoint with pluggable checks | Low | High |
| Config loader | all 4 projects | Environment-based config with validation | Medium | Medium |
| Structured log setup | all 4 projects | structlog configuration boilerplate | Low | Low (already well-aligned) |

### Convention Alignment

| Convention | Aligned | Diverging | Recommendation |
|-----------|---------|-----------|----------------|
| Logging field names | api-gw, user-svc, billing-svc (`user_id`) | mobile-app (`userId`) | Align mobile-app to snake_case for log aggregation |
| Error response format | api-gw, user-svc (`{"error": {"code": ..., "message": ...}}`) | billing-svc (`{"detail": "..."}`) | Align billing-svc to structured error format |
| Test naming | all (`test_<thing>_<scenario>`) | (none) | Already aligned — document as convention |

---

## Why This Report is Good

- **Patterns are specific and comparative** — not just "they all have retry
  logic" but exactly how the implementations are similar and how they differ.
- **Extraction candidates are realistic** — includes effort estimates and
  explains which version should be the base.
- **Convention table is scannable** — a team lead can immediately see where
  alignment exists and where it doesn't.
- **Priority is justified** — high priority for retry (3 projects, diverging
  implementations, real duplication cost) vs low for logging (already aligned).
- **Absent patterns noted** — mobile-app not having health checks is
  informative even though it's a frontend project.

---

## Bad Pattern Report (Excerpt)

---

### Patterns Found

- Error handling: Various approaches used
- Logging: Most projects log things
- Testing: Tests exist in all projects
- Configuration: All projects have config files
- API design: REST endpoints present

### Recommendations

- Share more code between projects
- Standardize error handling
- Create shared utilities

---

## Why This Report is Bad

- **"Various approaches" tells you nothing** — which approaches? In which
  projects? How do they differ?
- **Observations are trivially true** — "most projects log things" and "tests
  exist" are not findings. Every project logs and tests.
- **No comparison** — the entire value of a cross-project pattern analysis is
  the comparison. This report never compares anything.
- **No extraction specifics** — "share more code" doesn't say what code, how
  to share it, or whether it's actually worth sharing.
- **No effort estimates** — extracting a shared library is work. Without effort
  context, recommendations are wishes.

---

## What Makes a Pattern Worth Reporting

Not every shared practice is a pattern worth calling out. Apply these filters:

| Filter | Include | Exclude |
|--------|---------|---------|
| **Recurrence** | Appears in 2+ projects with substantive implementation | Appears in 1 project, or is trivial (e.g., "uses Python") |
| **Specificity** | Can point to specific code, files, or decisions | Vague category ("error handling") |
| **Actionability** | Leads to a concrete recommendation (extract, align, document) | Just an observation with no next step |
| **Divergence** | Implementations differ in ways that matter (different behavior, breaking API) | Minor style differences (tabs vs spaces) |
| **Impact** | Affects shared interfaces, deployment, or developer experience | Internal implementation detail with no cross-project effect |

A good pattern report has 3-7 well-documented patterns, not 20 shallow
observations. Depth over breadth.
