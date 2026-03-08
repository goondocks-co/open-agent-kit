# Swarm Search Strategies

How to get useful results from swarm search. The quality of any swarm report
depends entirely on the quality of the searches that feed it.

## The Search-Fetch-Refine Loop

Swarm analysis follows a consistent pattern:

```
1. Broad search → scan results for themes
2. Targeted search → drill into specific themes
3. Fetch → get full details for the best hits
4. Synthesize → combine findings into insights
```

Don't try to get everything in one search. Plan 3-5 searches minimum, adapting
each based on what the previous ones revealed.

## Search Types and When to Use Them

| search_type | Returns | Best For |
|-------------|---------|----------|
| `all` | Everything — code, memories, sessions | Initial broad sweep when you don't know what's there |
| `memory` | Observations, decisions, gotchas, trade-offs | Finding what teams have *learned* and *decided* |
| `code` | Code chunks with context | Finding actual implementations (limited to indexed code) |
| `sessions` | Session summaries | Understanding what teams have been *doing* recently |
| `plans` | Planning docs, RFCs, architectural decisions | Finding strategic thinking and design rationale |

**Start with `all`, narrow from there.** If `all` returns mostly memories,
that's a signal to dig deeper with `memory`. If it's mostly sessions, switch
to `sessions` for better ranking.

## Writing Good Queries

### Good Queries

Specific, intent-driven queries that describe what you're looking for:

```
# Looking for patterns
"error handling retry logic with exponential backoff"
"authentication middleware patterns and session management"
"database migration strategies and schema versioning"

# Looking for decisions
"chose PostgreSQL over MongoDB and why"
"decision to use microservices vs monolith"
"API versioning approach and deprecation policy"

# Looking for problems
"known issues with deployment pipeline"
"performance bottlenecks in data processing"
"technical debt and refactoring priorities"
```

### Bad Queries

Vague, keyword-only queries that return noise:

```
# Too vague — returns everything and nothing
"code"
"patterns"
"issues"

# Too narrow — misses synonyms and related concepts
"useEffect cleanup function"  (won't find React lifecycle management in general)
"asyncio.gather"  (won't find concurrency patterns broadly)

# Implementation-specific — assumes naming conventions
"UserService.authenticate()"  (searches are semantic, not grep)
```

### Query Adaptation

When a search returns few results, broaden:
- `"JWT token refresh"` → `"authentication token management"`
- `"Redis cache invalidation"` → `"caching strategies and cache management"`

When a search returns too many results, narrow:
- `"testing"` → `"integration test patterns for API endpoints"`
- `"error handling"` → `"error handling in payment processing pipelines"`

## Fetch Selectively

`swarm_fetch` is for depth, not breadth. Fetch when:
- A search result mentions something specific you need to understand
- You see the same pattern referenced across multiple projects
- A result's summary suggests actionable content (a decision, a solution)

Don't fetch when:
- The search result summary already tells you what you need
- You're just establishing that a pattern exists (the search hit is enough)
- You're scanning for themes (save fetches for the drill-down phase)

## Multi-Project Correlation

The most valuable swarm insights come from comparing across projects. When
reviewing search results:

1. **Note which projects appear.** If 3 of 5 projects have results for "retry
   logic", that's a shared pattern worth reporting.
2. **Note which projects are absent.** If only 1 project discusses "deployment
   rollback", the others may be missing something important.
3. **Look for contradictions.** If project A decided "use Redis for caching"
   and project B decided "avoid Redis, use in-memory caching", that's a
   divergence worth highlighting.
4. **Count recurrence.** A pattern mentioned once might be noise. A pattern
   mentioned across 3+ projects is a convention (whether intentional or not).
