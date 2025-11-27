# RFC Workflow

This document describes the RFC (Request for Comments) process in open-agent-kit, including lifecycle management, agent commands, and best practices.

## Overview

open-agent-kit supports the complete RFC lifecycle through AI agent commands:

1. **Creation** - Generate RFCs using `/oak.rfc-create`
2. **Validation** - Check RFC quality using `/oak.rfc-validate`
3. **Listing** - Analyze RFCs using `/oak.rfc-list`
4. **Review** - Collaboration via git/GitHub
5. **Adoption/Abandonment** - Lifecycle management via file organization

## RFC Lifecycle States

```
Draft → In Review → Approved → [Adopted | Abandoned]
                                   ↓
                            [Implemented | Will Not Implement]
```

| State | Description | Location |
|-------|-------------|----------|
| Draft | Being written/edited | Feature branch |
| In Review | PR created, awaiting feedback | PR open |
| Approved | CODE OWNER approved | PR approved |
| Adopted | Merged to main | `oak/rfc/adopted/` |
| Abandoned | Merged to main | `oak/rfc/abandoned/` |
| Implemented | Code deployed | Release created |

## Agent Commands

### `/oak.rfc-create <description>`

Creates a new RFC. The agent follows a reasoning-first flow:

1. **Clarify intent** – Confirm stakeholders, scope, constraints, and expected outcomes.
2. **Research context** – Inspect the repository, existing RFCs/ADRs, and tickets.
3. **Select a template** – Choose engineering, architecture, feature, or process template.
4. **Outline the document** – Produce a section-by-section plan before generating files.
5. **Scaffold & draft** – Use `oak rfc create` to create the file, then fill in content.
6. **Review & iterate** – Summarize open questions and next steps.

**Usage:**
```text
/oak.rfc-create API Versioning Strategy for multi-tenant API
```

The agent will:
- Ask clarifying questions if needed
- Generate all required sections
- Add mermaid diagrams where helpful
- Identify risks and alternatives

### `/oak.rfc-validate <rfc-number>`

Runs an interactive review session combining qualitative analysis with structural validation.

**Flow:**
1. Gather RFC metadata (status, author, date, related work).
2. Grade clarity, design depth, risks, rollout, and success metrics.
3. Optionally run `oak rfc validate RFC-###` for structural checks.
4. Group findings by severity (critical / major / minor).
5. Help apply fixes and re-run checks as needed.

**Usage:**
```text
/oak.rfc-validate RFC-001
```

### `/oak.rfc-list [filter]`

Portfolio analysis for RFCs. Invokes `oak rfc list --json` to compute statistics.

**Example prompts:**
- "List draft RFCs older than 60 days and suggest next steps."
- "Show approved RFCs tagged observability."
- "Who authored the most RFCs this quarter?"

## Manual Workflow

After creating RFCs with AI agents, use standard git workflows:

### Submitting for Review

```bash
# Create branch
git checkout -b rfc-001-api-versioning

# Commit RFC
git add oak/rfc/RFC-001-API-Versioning.md
git commit -m "Add RFC-001: API Versioning Strategy"

# Push and create PR
git push origin rfc-001-api-versioning
gh pr create --title "RFC-001: API Versioning Strategy"
```

### Lifecycle Updates

```bash
# Mark as adopted (moves to oak/rfc/adopted/)
oak rfc adopt 001

# Mark as abandoned (moves to oak/rfc/abandoned/)
oak rfc abandon 009
```

### Branch Naming Convention

```
rfc-{number}-{slug}
```

Examples: `rfc-001-api-versioning`, `rfc-009-graphql-federation`

## Validation Rules

### Template Compliance

During validation, ensure:
1. All sections defined by the chosen template are present.
2. Blockquote guidance and placeholders are replaced with concrete content.
3. Metadata (Author, Date, Status, Tags) is accurate.
4. Related RFCs/ADRs are referenced when applicable.
5. Rollout, testing, and success metrics are specific and measurable.

### Markdownlint Configuration

Default config (`.markdownlint.json`):
```json
{
  "default": true,
  "MD013": false,
  "MD033": { "allowed_elements": ["summary", "details"] },
  "MD041": false
}
```

## Best Practices

### For Authors

1. **Start with `/oak.rfc-create`** to walk through intake, discovery, and drafting.
2. **Iterate with validation** – re-run `/oak.rfc-validate` after substantial edits.
3. **Commit frequently** to preserve drafting history.
4. **Document assumptions** and follow-up tasks before handing off to reviewers.

### For Reviewers

1. **Use PR comment threads** for discussions.
2. **Request changes** with clear, actionable feedback.
3. **Approve when satisfied** – don't leave PRs hanging.

### For Teams

1. **Define CODE OWNERS** for RFC approval.
2. **Establish review SLAs** (e.g., 3 business days).
3. **Celebrate adoptions** and learn from abandonments.

## Troubleshooting

**"RFC number already exists"**
- Run `oak rfc list --json` to inspect existing numbers. The agent will pick the next available number.

**"Validation reported placeholders"**
- Replace blockquote guidance, ellipses, and checklist items with concrete content.

**"GitHub CLI not authenticated"**
- Run `gh auth login` before creating PRs.

---

*For setup and configuration, see [README](../README.md) and [QUICKSTART](../QUICKSTART.md).*
