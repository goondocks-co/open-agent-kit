---
name: project-rules
description: Create and maintain project constitutions (.constitution.md), CLAUDE.md, AGENTS.md, .cursorrules, and agent instruction files. Use when establishing coding standards, adding project rules, creating agent guidance files, or improving AI agent consistency.
allowed-tools: Bash, Read, Edit, Write
user-invocable: true
---

# Project Constitution and Agent Rules Management

Create, modify, and maintain project constitutions (`.constitution.md`) and agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`, etc.) that guide AI agents working in the codebase.

## Purpose

A project constitution establishes:
- **Hard rules** that must be followed (no exceptions)
- **Golden paths** showing how to implement common patterns
- **Anchor files** as canonical examples to copy
- **Quality gates** defining when work is complete
- **Non-goals** to prevent scope creep

Agent instruction files point to the constitution and provide quick-reference anchors.

## When to Use This Skill

- **Creating a new constitution** for a project that doesn't have one
- **Adding rules** when you identify patterns that should be standardized
- **Improving structure** when existing rules are vague or unenforceable
- **Syncing agent files** after constitution changes
- **Creating CLAUDE.md, AGENTS.md, or .cursorrules** for a new project

## What Makes a Good Constitution

A good constitution is **explicit, enforceable, and anchored**:

| Quality | Good | Bad |
|---------|------|-----|
| Specificity | "All API endpoints MUST validate input using Pydantic models" | "Use best practices" |
| Anchors | "Copy `src/features/auth/service.py` for new services" | "Follow good patterns" |
| Non-goals | "This tool is NOT a CI/CD orchestrator" | (no boundaries) |
| Gates | "`make check` must pass for all changes" | "Add tests if needed" |
| Scope | Defines what "local-first" means concretely | "Prefer local when possible" |

See `references/good-constitution-example.md` for a complete example.
See `references/bad-constitution-example.md` for anti-patterns to avoid.

## Constitution Structure

### Required Sections

```markdown
# Project Constitution

## Metadata
- Project, version, status, tech stack

## 1. Scope and Non-Goals (Hard Constraints)
- What the project IS and IS NOT
- Definitions (e.g., what "local-first" means)

## 2. Golden Paths
- How to add features, agents, commands, templates, config
- Anchor Index with specific file paths

## 3. Architecture Invariants (Hard Rules)
- Layering rules
- Extension patterns

## 4. No-Magic-Literals
- Where constants must live
- Type safety requirements

## 5. CLI Behavior
- Idempotence rules
- Error handling standards

## 6. Upgrade and Migrations
- Template ownership
- Migration patterns

## 7. Quality Gates (Definition of Done)
- What must pass before changes are complete

## 8. Execution Model (Optional)
- Plan-first requirements
- Sub-agent delegation rules
```

## Creating a Constitution

### Step 1: Analyze the project

```bash
# Understand the project structure
ls -la
cat README.md
cat pyproject.toml  # or package.json, Cargo.toml, etc.
```

### Step 2: Identify existing patterns

Look for:
- Configuration files and their conventions
- Service/model/controller layering
- Test patterns
- Build/lint/format tooling

### Step 3: Create the constitution

Create `oak/constitution.md` (or `.constitution.md` at root):

```markdown
# Project Constitution

## Metadata
- **Project:** your-project
- **Version:** 1.0.0
- **Status:** Draft
- **Last Updated:** YYYY-MM-DD
- **Tech Stack:** [list technologies]

## 1. Scope and Non-Goals
[Define what this project is and is NOT]

## 2. Golden Paths
[List how common changes should be made]

### Anchor Index
[Point to specific files as canonical examples]

## 3. Architecture Invariants
[Hard rules about structure]

## 4. No-Magic-Literals
[Where values must live]

## 5. CLI/API Behavior
[Idempotence, error handling]

## 6. Quality Gates
- `make check` / `npm test` / etc. must pass
- Docs updated to prevent drift
```

### Step 4: Create agent instruction files

After creating the constitution, create agent files that reference it:

```bash
oak rules sync-agents
```

Or create manually (see `references/good-agent-file-example.md`):

```markdown
# CLAUDE.md (or AGENTS.md)

You are an AI coding agent working in this repository.

## Source of truth
Read and follow **`.constitution.md`** (or `oak/constitution.md`).
- If anything conflicts, the constitution wins.
- If uncertain, ask rather than inventing patterns.

## Required workflow
1. Read the constitution
2. Find and copy the closest anchor
3. Run quality gates
4. Update docs

## Top anchors
[List 3-5 most common anchor files]
```

## Adding Rules to Existing Constitution

### Step 1: Read current constitution

```bash
oak rules get-content
# or
cat oak/constitution.md
```

### Step 2: Add rule to appropriate section

Use RFC 2119 language:

| Keyword | Meaning |
|---------|---------|
| **MUST** | Absolute requirement |
| **MUST NOT** | Absolute prohibition |
| **SHOULD** | Strong recommendation (exceptions need justification) |
| **SHOULD NOT** | Strong discouragement |
| **MAY** | Optional |

Example rules:
```markdown
- All API endpoints MUST validate input using Pydantic models
- Database queries MUST use parameterized statements
- Services SHOULD be stateless; if state is needed, document why
- Teams MAY use dependency injection frameworks
```

### Step 3: Sync to agent files

```bash
oak rules sync-agents
```

## Common Anti-Patterns to Avoid

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| "Use best practices" | Not enforceable | Specify the practice |
| "When possible" / "When appropriate" | Loophole generator | Define when it's required |
| No anchors | Agents freestyle | Point to specific files |
| No non-goals | Scope creep | Explicitly exclude things |
| "Add tests if needed" | Permission to skip | Define coverage requirements |
| "Make reasonable assumptions" | Agents invent patterns | Say "ask if uncertain" |

## Files

- Constitution: `oak/constitution.md` or `.constitution.md`
- Agent files: `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`, etc.
- Reference examples: See `references/` subdirectory in this skill

## Example Workflow

User: "We need to establish coding standards for this Python project"

1. **Analyze**: Read `pyproject.toml`, check for existing linters/formatters
2. **Create constitution** with:
   - Tech stack (Python 3.12+, pytest, ruff, mypy)
   - No-magic-literals rule (use constants.py)
   - Architecture (services/models/cli layers)
   - Quality gate (`make check` or equivalent)
   - Anchor files (point to best existing modules)
3. **Create agent files** referencing the constitution
4. **Sync**: `oak rules sync-agents`
