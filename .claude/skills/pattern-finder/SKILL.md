---
name: pattern-finder
description: >-
  Find recurring code patterns, architectural decisions, and shared conventions
  across projects in your organization's swarm. Use when you want to discover
  what patterns other teams use, find candidates for shared libraries, or
  standardize approaches across the org. Also use when the user asks to "find
  patterns across projects", "what conventions do other teams follow", "shared
  code opportunities", or anything about org-wide code reuse. Requires an
  active swarm connection.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
user-invocable: true
---

# Pattern Finder

Search across swarm nodes for recurring code patterns, architectural decisions,
and shared conventions that could be standardized or extracted into shared
libraries.

## Workflow

### 1. Verify Connectivity

```
swarm_status()
swarm_nodes()
```

Note the connected projects — each represents a search target.

### 2. Search for Patterns

Run searches across several dimensions:

```
# Shared utility patterns
swarm_search(query="utility functions helpers common patterns", search_type="all", limit=20)

# Architectural patterns
swarm_search(query="service layer architecture middleware patterns", search_type="memory", limit=20)

# Error handling and resilience
swarm_search(query="error handling retry logic resilience patterns", search_type="memory", limit=15)

# Testing approaches
swarm_search(query="testing conventions test patterns integration tests", search_type="memory", limit=15)

# Configuration and deployment
swarm_search(query="configuration management deployment patterns CI/CD", search_type="memory", limit=15)
```

Adjust queries based on the user's focus area. If they asked about a specific
domain (e.g., "how do other teams handle auth?"), prioritize targeted searches.

### 3. Drill into Interesting Findings

```
swarm_fetch(ids=["<chunk-id>"], project_slug="<project>")
```

Fetch details for patterns that appear across multiple projects or that
represent particularly clean solutions worth adopting.

### 4. Compare with Local Patterns

Search the current project to see how local patterns relate:

```
# Use grep/glob to find local implementations of discovered patterns
Grep(pattern="relevant pattern", path="src/")
```

This comparison makes recommendations concrete — "Team B does X, we do Y,
here's why aligning makes sense."

### 5. Write the Report

Write to `oak/insights/pattern-finder-report.md`:

```markdown
# Pattern Finder Report

> Generated: YYYY-MM-DD | Projects analyzed: N

## Executive Summary

Overview of key findings — what patterns are widely shared, where approaches
diverge, and the top extraction/standardization opportunities.

## Shared Patterns

Patterns that appear across multiple projects:

### [Pattern Name]
- **Where:** Projects A, B, C
- **What:** Brief description of the pattern
- **Variation:** How implementations differ across projects
- **Assessment:** Is convergence desirable? Which version is best?

(Repeat for each significant pattern found)

## Divergences Worth Examining

Areas where projects take notably different approaches to the same problem:

| Problem Domain | Project A Approach | Project B Approach | Notes |
|---------------|-------------------|-------------------|-------|
| ...           | ...               | ...               | ...   |

## Extraction Candidates

Code that could be extracted into shared packages:

| Candidate | Found In | Description | Effort |
|-----------|----------|-------------|--------|
| Retry utility | A, B, C | Exponential backoff with jitter | Low |
| ...       | ...      | ...         | ...    |

Include:
- Utility functions duplicated across projects
- Common middleware or service patterns
- Shared type definitions or schemas

## Convention Alignment

| Convention | Projects Aligned | Projects Diverging | Recommendation |
|-----------|-----------------|-------------------|----------------|
| Naming style | A, C (snake_case) | B (camelCase) | Align to snake_case |
| ...       | ...             | ...               | ...            |

## Recommendations

Prioritized list of actions:
1. Quick wins — patterns already nearly aligned, just need coordination
2. High-value extractions — widely duplicated code worth packaging
3. Convention decisions — divergences that need a team decision
```

### CLI Fallback

```bash
oak-dev swarm status
oak-dev swarm nodes
oak-dev swarm search "utility functions common patterns" --type all -n 20
oak-dev swarm search "architectural patterns" --type memory -n 20
oak-dev swarm search "error handling patterns" --type memory -n 15
```

## Tips

- **Adapt searches to user intent.** If the user wants patterns in a specific
  area (auth, testing, deployment), focus your queries there instead of
  searching broadly.
- **Patterns need at least 2 projects.** A pattern in a single project is just
  an implementation. Look for things that recur across teams.
- **Compare don't just catalog.** The value is in the comparison — noting where
  projects converge and diverge, not just listing what each project does.
- **Extraction candidates should be concrete.** "They all have retry logic" is
  an observation. "These three implementations of exponential backoff could
  merge into a shared `@org/retry` package" is actionable.

## Deep Dives

Consult these reference documents for deeper guidance:

- **`references/pattern-examples.md`** — Good and bad pattern reports with criteria for what makes a pattern worth reporting. Read this before writing the report.
- **`references/search-strategies.md`** — How to write effective swarm queries, when to use each search type, and how to correlate results across projects.
