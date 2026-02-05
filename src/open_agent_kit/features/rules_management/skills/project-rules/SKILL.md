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

**CRITICAL:** The constitution is the single source of truth. Rules MUST be added to the constitution FIRST, then synced to agent files. Never add a rule only to an agent file (CLAUDE.md, AGENTS.md, etc.) — those files reference the constitution, not the other way around.

### Step 1: Read current constitution and discover agent files

Read the constitution and use OAK's built-in commands to discover all configured agent instruction files:

```bash
# Read the constitution (source of truth)
cat oak/constitution.md  # or .constitution.md

# Discover all agent instruction files dynamically
# This reads .oak/config.yaml for configured agents, then checks each
# agent's manifest (src/open_agent_kit/agents/{name}/manifest.yaml)
# for its instruction_file path.
oak rules detect-existing
oak rules detect-existing --json  # machine-readable output
```

**Do NOT hardcode agent file names.** Agents are configured dynamically in `.oak/config.yaml` and each agent's manifest defines its own `installation.instruction_file` path. The list of files can grow or shrink as agents are added or removed.

### Step 2: Add the full rule to the constitution

Find the appropriate section in the constitution and add the complete rule with:
- The rule statement using RFC 2119 language (MUST, MUST NOT, SHOULD, etc.)
- Rationale explaining WHY the rule exists
- Verification steps (how to check compliance)
- Troubleshooting guidance (what to do when the rule is violated)

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

### Step 3: Sync the rule to ALL agent instruction files

After the constitution is updated, ensure every agent instruction file references the new rule. Use OAK's sync command to discover and update all configured agent files:

```bash
# Preview what files will be checked/updated
oak rules sync-agents --dry-run

# Sync constitution references to all agent files
oak rules sync-agents
```

If `oak rules sync-agents` only handles constitution references (not rule-specific sections), manually add a concise reference to each agent file. Use `oak rules detect-existing` to get the full list of files:

```bash
oak rules detect-existing --json
```

For each agent file that exists, add a short section that:

1. States the rule concisely (1-2 sentences)
2. References the constitution section for full details

Example:

```markdown
## [Rule Name]

**MUST NOT** [brief prohibition]. See §[section] of `oak/constitution.md` for the full rule, rationale, and verification command.
```

**Important:** Agent instruction file paths are defined in each agent's manifest (`installation.instruction_file`). Do not assume fixed file names — always discover dynamically via `oak rules detect-existing`.

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
- Agent files: Dynamically configured per agent manifest (`installation.instruction_file`). Run `oak rules detect-existing` to discover all agent instruction files for the current project.
- Agent manifests: `src/open_agent_kit/agents/{name}/manifest.yaml`
- Agent config: `.oak/config.yaml` (lists configured agents)
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
