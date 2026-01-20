# Review RFC

Review an RFC document for completeness, clarity, and technical soundness.

## Usage

When the user wants to review an RFC:

```bash
# List all RFCs
oak rfc list

# Validate structure
oak rfc validate oak/rfc/RFC-XXX-title.md

# Show RFC details
oak rfc show oak/rfc/RFC-XXX-title.md
```

## Review Checklist

### Structure
- [ ] Clear title and RFC number
- [ ] Status correctly marked
- [ ] All required sections present

### Content
- [ ] Problem clearly stated
- [ ] Proposed solution is clear
- [ ] Risks acknowledged with mitigations
- [ ] Alternatives considered

## Feedback Format

```markdown
## RFC Review: RFC-XXX

### Summary
[Ready / Needs Work / Major Revision]

### Strengths
- ...

### Areas for Improvement
- ...

### Recommendation
[Approve / Request Changes]
```

## After Review

```bash
# If approved
oak rfc adopt oak/rfc/RFC-XXX-title.md

# If abandoned
oak rfc abandon oak/rfc/RFC-XXX-title.md --reason "Reason"
```

## Notes

- RFCs are in `oak/rfc/`
- Run `oak rfc validate` to check structure automatically
