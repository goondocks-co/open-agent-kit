---
name: dependency-audit
description: >-
  Audit dependencies across projects in your organization's swarm. Use when you
  need to find version conflicts, outdated packages, or security risks across
  teams. Also use when the user asks for a "dependency audit", "version check
  across projects", "package alignment", or wants to standardize dependencies
  org-wide. Requires an active swarm connection.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
user-invocable: true
---

# Dependency Audit

Audit dependencies across connected swarm nodes to find version conflicts,
outdated packages, and standardization opportunities.

## Workflow

### 1. Verify Connectivity

```
swarm_status()
swarm_nodes()
```

If disconnected or fewer than 2 nodes are available, inform the user — a
cross-project audit needs multiple projects to compare.

### 2. Gather Dependency Data

Search for dependency-related information across the swarm:

```
# Package manifests and dependency choices
swarm_search(query="package.json dependencies pyproject.toml requirements", search_type="all", limit=20)

# Dependency decisions and rationale
swarm_search(query="dependency choices and version decisions", search_type="memory", limit=20)

# Known dependency issues
swarm_search(query="dependency conflicts outdated packages security vulnerabilities", search_type="memory", limit=15)
```

Also read the local project's dependency manifests for comparison:

```
# Check what exists locally
Glob("**/package.json")
Glob("**/pyproject.toml")
Glob("**/requirements*.txt")
Glob("**/Cargo.toml")
Glob("**/go.mod")
```

Read the relevant manifests to extract dependency lists.

### 3. Fetch Details for Key Findings

For search results that indicate conflicts or interesting patterns:

```
swarm_fetch(ids=["<chunk-id>"], project_slug="<project>")
```

### 4. Write the Audit Report

Write to `oak/insights/dependency-audit-report.md`:

```markdown
# Dependency Audit Report

> Generated: YYYY-MM-DD | Projects audited: N

## Executive Summary

Brief overview of findings — number of conflicts found, critical risks, and
top recommendations for alignment.

## Version Conflict Analysis

| Package | Project A | Project B | Risk Level | Notes |
|---------|-----------|-----------|------------|-------|
| ...     | v1.2.3    | v3.0.0    | High       | Major version mismatch |

Focus on:
- Same package at different major versions across projects
- Pinned versions that differ significantly
- Transitive dependency risks

## Security Assessment

Flag dependencies that may pose risks:
- Very outdated packages (2+ major versions behind current)
- Packages with known deprecation notices
- Unusual or unmaintained dependencies

## Standardization Recommendations

| Action | Packages | Projects Affected | Priority |
|--------|----------|-------------------|----------|
| Align to v4.x | react | project-a, project-b | High |
| ...    | ...      | ...               | ...      |

Suggest:
- Packages that should converge to one version
- Shared internal packages that could reduce duplication
- Upgrade paths for outdated dependencies

## Shared Dependencies

Packages used across multiple projects (potential extraction candidates):
- List common utilities, frameworks, and tools
- Note where versions already align (positive signal)
```

### CLI Fallback

```bash
oak-dev swarm status
oak-dev swarm nodes
oak-dev swarm search "dependencies packages versions" --type all -n 20
oak-dev swarm search "dependency decisions" --type memory -n 20
```

## Tips

- **Local manifests are your ground truth.** Always read the current project's
  actual dependency files — swarm search results are summaries and may be stale.
- **Focus on actionable conflicts.** Minor patch version differences aren't
  worth reporting. Highlight major version mismatches and known-broken
  combinations.
- **Group by risk level.** Security issues first, then breaking conflicts, then
  alignment opportunities.
- **Limited data is normal.** Swarm search returns what teams have discussed
  and committed — it may not have complete dependency lists. Note coverage gaps.

## Deep Dives

Consult these reference documents for deeper guidance:

- **`references/audit-examples.md`** — Good and bad audit report examples with a risk assessment framework. Read this before writing the report.
- **`references/search-strategies.md`** — How to write effective swarm queries, when to use each search type, and how to correlate results across projects.
