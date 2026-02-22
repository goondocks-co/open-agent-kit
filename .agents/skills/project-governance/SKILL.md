---
name: project-governance
description: >-
  Create and maintain project constitutions and agent instruction files.
  Use when establishing coding standards, adding project rules, creating
  agent guidance files, syncing rules across agents, or improving AI agent
  consistency. Also supports RFC/ADR documents for formalizing technical
  decisions that feed into the constitution.
allowed-tools: Bash, Read, Edit, Write
user-invocable: true
---

# Project Governance

Create, modify, and maintain project constitutions and agent instruction files that guide AI agents. Also supports RFC/ADR documents for formalizing technical decisions.

## Quick Start

### Create a constitution

```bash
# Analyze the project, then create oak/constitution.md
# See references/constitution-guide.md for the full process
```

### Create agent instruction files

```bash
oak-dev rules detect-existing      # Discover all configured agent instruction files
oak-dev rules sync-agents          # Sync constitution references to all agent files
```

## Commands Reference

| Command | Purpose |
|---------|---------|
| `oak-dev rules detect-existing` | Discover all configured agent instruction files |
| `oak-dev rules detect-existing --json` | Machine-readable output of agent files |
| `oak-dev rules sync-agents` | Sync constitution references to all agent instruction files |
| `oak-dev rules sync-agents --dry-run` | Preview what files will be checked/updated |

## When to Use

- **Creating a new constitution** for a project that doesn't have one
- **Creating agent instruction files** for a new project (use `oak-dev rules detect-existing` to discover correct file names)
- **Adding rules** when you identify patterns that should be standardized
- **Syncing agent files** after constitution changes
- **Learning context engineering theory** behind effective rule writing -- see `/context-engineering` for the altitude concept, canonical examples, and structured context patterns

## Constitution Structure

A good constitution is **explicit, enforceable, and anchored**:

| Quality | Good | Bad |
|---------|------|-----|
| Specificity | "All API endpoints MUST validate input using Pydantic models" | "Use best practices" |
| Anchors | "Copy `src/features/auth/service.py` for new services" | "Follow good patterns" |
| Non-goals | "This tool is NOT a CI/CD orchestrator" | (no boundaries) |
| Gates | "`make check` must pass for all changes" | "Add tests if needed" |

Required sections: Metadata, Scope and Non-Goals, Golden Paths with Anchor Index, Architecture Invariants, No-Magic-Literals, CLI Behavior, Quality Gates. See `references/constitution-guide.md` for the full structure and creation process.

## Key Workflows

### Creating agent instruction files

**CRITICAL:** Do NOT guess agent file names. Always discover them dynamically.

1. **Discover** the correct file names and paths: `oak-dev rules detect-existing`
2. **Read** the output — it shows each configured agent, the expected file path, and whether the file already exists
3. **Create** only the files listed as "not found", using the exact paths from the output
4. **Content** should follow the template in `references/agent-file-good-example.md`
5. **Verify** all files are detected: `oak-dev rules detect-existing` (all should show ✓)

### Adding a rule to an existing constitution

1. **Read** the current constitution (`oak/constitution.md`)
2. **Add** the full rule to the appropriate section using RFC 2119 language (MUST, SHOULD, MAY)
3. **Sync** to all agent files: `oak-dev rules sync-agents`

**CRITICAL:** Rules MUST be added to the constitution FIRST, then synced to agent files. Never add a rule only to an agent file.

## Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| "Use best practices" | Not enforceable | Specify the practice |
| "When possible" | Loophole generator | Define when it's required |
| No anchors | Agents freestyle | Point to specific files |
| No non-goals | Scope creep | Explicitly exclude things |
| "Add tests if needed" | Permission to skip | Define coverage requirements |
| "Make reasonable assumptions" | Inconsistent patterns | Say "ask if uncertain" |

## Files

- Constitution: `oak/constitution.md` or `.constitution.md`
- Agent files: Run `oak-dev rules detect-existing` to discover all agent instruction files
- RFCs: `oak/rfc/RFC-XXX-short-title.md`

## Deep Dives

For detailed guidance, consult the reference documents:

### Constitution & Agent Files
- **`references/constitution-guide.md`** — Full constitution creation process and structure
- **`references/constitution-good-example.md`** — Complete example of a well-structured constitution
- **`references/constitution-bad-example.md`** — Anti-patterns to avoid
- **`references/agent-files-guide.md`** — Creating and syncing agent instruction files
- **`references/agent-file-good-example.md`** — Well-structured agent file example
- **`references/agent-file-bad-example.md`** — Poorly structured agent file example

### RFCs (secondary)
- **`references/creating-rfcs.md`** — Detailed RFC creation workflow
- **`references/reviewing-rfcs.md`** — RFC review checklist and feedback format

---

## RFC Support

RFCs formalize technical decisions that may eventually become constitution rules. This is a secondary capability — see the dedicated references for full details.

### RFC commands

| Command | Purpose |
|---------|---------|
| `oak-dev rfc create --title "..." --template <type>` | Create a new RFC |
| `oak-dev rfc list` | List all RFCs |
| `oak-dev rfc validate <path>` | Validate RFC structure and content |
| `oak-dev rfc show <path>` | Show RFC details |
| `oak-dev rfc adopt <path>` | Mark RFC as adopted |
| `oak-dev rfc abandon <path> --reason "..."` | Mark RFC as abandoned |

### RFC templates

| Template | Use For |
|----------|---------|
| `feature` | New features, capabilities |
| `architecture` | System architecture changes |
| `engineering` | Development practices, tooling |
| `process` | Team processes, workflows |

### RFC lifecycle

1. **Create**: `oak-dev rfc create --title "..." --template feature --author "Name"`
2. **Fill in**: Problem context, proposed solution, trade-offs, alternatives
3. **Review**: Use the review checklist (see `references/reviewing-rfcs.md`)
4. **Adopt or abandon**: `oak-dev rfc adopt <path>` or `oak-dev rfc abandon <path> --reason "..."`

### RFC review checklist (summary)

- Structure: Clear title, correct status, all required sections
- Context: Problem clearly stated, "why now?" addressed, scope defined
- Decision: Solution clear, technical approach explained
- Consequences: Positive/negative outcomes listed, mitigations proposed
- Alternatives: Other options considered, reasons for rejection explained
