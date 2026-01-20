---
name: reviewing-rfcs
description: Review existing RFC documents for completeness, clarity, and technical soundness. Use to validate RFCs before team review or to provide structured feedback.
allowed-tools: Bash, Read
user-invocable: true
---

# Reviewing RFCs

Review RFC documents for completeness, clarity, and technical soundness.

## When to Use

Use this skill when:
- Preparing an RFC for team review
- Providing feedback on someone else's RFC
- Checking if an RFC is ready for adoption
- Validating RFC structure and content

## How It Works

1. **Read** the RFC document
2. **Validate** structure using the CLI
3. **Assess** content quality and completeness
4. **Provide** structured feedback

## Quick Start

```bash
# List all RFCs
oak rfc list

# Validate a specific RFC
oak rfc validate oak/rfc/RFC-001-your-rfc.md

# Show RFC details
oak rfc show oak/rfc/RFC-001-your-rfc.md
```

## Review Checklist

### Structure
- [ ] Has clear title and RFC number
- [ ] Status is correctly marked (Draft/Under Review/Adopted)
- [ ] All required sections present

### Context Section
- [ ] Problem is clearly stated
- [ ] "Why now?" is addressed
- [ ] Scope is well-defined

### Decision Section
- [ ] Proposed solution is clear
- [ ] Technical approach is explained
- [ ] Implementation considerations included

### Consequences
- [ ] Positive outcomes listed
- [ ] Negative outcomes/risks acknowledged
- [ ] Mitigations for risks proposed

### Alternatives
- [ ] Other options were considered
- [ ] Reasons for rejection explained
- [ ] Trade-offs are clear

## Feedback Format

When providing feedback, structure it as:

```markdown
## RFC Review: RFC-XXX

### Summary
[One-line assessment: Ready / Needs Work / Major Revision]

### Strengths
- Clear problem statement
- Good analysis of alternatives

### Areas for Improvement
- Missing risk mitigation for X
- Unclear implementation timeline

### Questions
- How does this interact with system Y?
- What's the rollback plan?

### Recommendation
[Approve / Request Changes / Reject]
```

## Validation

Run automated validation:

```bash
oak rfc validate oak/rfc/RFC-XXX-title.md
```

This checks:
- Required sections present
- Proper formatting
- No placeholder text remaining

## Common Issues

| Issue | How to Fix |
|-------|------------|
| Vague problem statement | Add specific examples, metrics |
| Missing alternatives | Document at least 2 other options |
| No risk assessment | Add "Risks" subsection to Consequences |
| Unclear implementation | Add timeline or phases |
| Too broad scope | Split into multiple RFCs |

## File Location

RFCs are in `oak/rfc/` directory. List all with:

```bash
oak rfc list
```
