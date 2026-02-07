---
title: Rules Management
description: Create and maintain a project constitution with shared coding standards.
---

Rules Management lets you create and maintain a **project constitution** — a living document that codifies your team's engineering standards, architecture patterns, and conventions. AI agents reference this constitution for consistent behavior across all sessions.

## What is a Constitution?

A constitution (`oak/constitution.md`) is a structured document that defines:

- **Hard rules** — invariants that must never be violated
- **Golden paths** — standard ways to implement common changes
- **Anchor files** — canonical reference implementations to copy from
- **Design principles** — local-first, idempotence, template ownership

## Creating a Constitution

Use your AI agent's command:

```text
/oak.constitution-create
```

The AI will:
1. Check for existing agent instructions and use them as context
2. Analyze your codebase for patterns (testing, linting, CI/CD, etc.)
3. Create `oak/constitution.md` with comprehensive standards
4. Update agent instruction files with constitution references (additively)

## Managing Your Constitution

```text
/oak.constitution-validate    # Validate structure
/oak.constitution-amend       # Add amendments as standards evolve
```

## How Agents Use It

All agent instruction files (`.claude/CLAUDE.md`, `AGENTS.md`, etc.) reference the constitution. When an agent starts working, it reads these instructions and follows the standards defined in your constitution.

This ensures consistent behavior whether you're using Claude, Copilot, Cursor, or any other supported agent.
