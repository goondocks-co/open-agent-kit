---
title: Strategic Planning
description: RFC workflow for documenting technical decisions and architecture records.
---

Strategic Planning provides a structured **RFC (Request for Comments)** workflow for documenting technical decisions. RFCs live in `oak/rfc/` and serve as a persistent record of why things were built the way they were.

## Creating an RFC

Use your AI agent's command:

```text
/oak.rfc-create Implement user authentication system with OAuth2
```

The AI agent creates a comprehensive RFC at `oak/rfc/RFC-001-*.md` with all required sections filled in.

## Managing RFCs

```text
/oak.rfc-list              # List all RFCs
/oak.rfc-validate RFC-001  # Validate RFC structure
```

## RFC Templates

Available templates (specified via `--template` on `oak rfc create`):

| Template | Description |
|----------|-------------|
| `engineering` | Engineering RFC Template (default) |
| `architecture` | Architecture Decision Record |
| `feature` | Feature Proposal |
| `process` | Process Improvement |

## Configuration

RFC settings in `.oak/config.yaml`:

```yaml
rfc:
  directory: oak/rfc
  template: engineering
  auto_number: true
  number_format: sequential
  validate_on_create: true
```

## Lifecycle

RFCs follow a standard lifecycle:

1. **Draft** — Initial proposal created by the agent
2. **Review** — Team reviews and provides feedback
3. **Accepted** / **Rejected** — Decision is made
4. **Implemented** — Changes are complete
5. **Superseded** — Replaced by a newer RFC

The constitution and RFCs work together: the constitution defines *how* you build, while RFCs document *what* you decide to build and *why*.
