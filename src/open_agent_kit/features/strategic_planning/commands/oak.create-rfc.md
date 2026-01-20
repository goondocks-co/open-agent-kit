# Create RFC

Create an RFC (Request for Comments) or ADR (Architecture Decision Record) document for formal technical planning.

## Usage

When the user wants to create a formal planning document:

```bash
# Create an RFC with a template
oak rfc create --title "Your RFC Title" --template feature --author "Name"

# Available templates: feature, architecture, engineering, process
```

## Templates

| Template | Use For |
|----------|---------|
| `feature` | New features, capabilities |
| `architecture` | System architecture changes |
| `engineering` | Development practices, tooling |
| `process` | Team processes, workflows |

## RFC Structure

A good RFC includes:
- **Context**: What problem are we solving? Why now?
- **Decision**: What are we proposing?
- **Consequences**: Positive/negative outcomes, risks
- **Alternatives**: What else was considered?

## Workflow

1. Create: `oak rfc create --title "Title" --template feature`
2. Edit the generated file in `oak/rfc/`
3. Share for review
4. When approved: `oak rfc adopt oak/rfc/RFC-XXX-title.md`

## Notes

- RFCs are stored in `oak/rfc/`
- List existing RFCs: `oak rfc list`
- Validate structure: `oak rfc validate oak/rfc/RFC-XXX.md`
