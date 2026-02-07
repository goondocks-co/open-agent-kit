---
title: Feature Development
description: How to add new features, agents, commands, and templates to OAK.
---

## Vertical Slice Structure

Every OAK feature follows the vertical slice pattern — all feature code is co-located:

```
src/open_agent_kit/features/<feature_name>/
  manifest.yaml          # Feature metadata, dependencies, agent support
  commands/              # CLI commands
    __init__.py
    <feature>_cmd.py     # Typer command group
  templates/             # Jinja2 templates (owned by OAK)
  skills/                # Agent skills (slash commands)
  daemon/                # Optional: HTTP server, UI, background jobs
```

**Exemplar feature**: `strategic_planning` — use this as your reference implementation.

## Adding a New Feature

1. **Create the feature directory** under `src/open_agent_kit/features/`
2. **Write `manifest.yaml`** with metadata, dependencies, and agent support matrix
3. **Add commands** as a Typer group in `commands/`
4. **Add templates** in `templates/` (Jinja2, rendered by `template_service.py`)
5. **Register the feature** in `cli.py`
6. **Run `make check`** to verify everything passes

### manifest.yaml

```yaml
name: my-feature
version: 0.1.0
description: Short description of the feature
dependencies:
  - rules-management    # Optional: other features this depends on
agents:
  claude:
    commands: true
    hooks: false
  copilot:
    commands: true
    hooks: false
```

### Commands

Commands must remain thin — parse inputs, call services, render output:

```python
import typer

app = typer.Typer()

@app.command()
def create(name: str = typer.Argument(..., help="Name of the thing")):
    """Create a new thing."""
    result = my_service.create(name)
    typer.echo(f"Created: {result}")
```

### Templates

- Templates are generated from canonical sources in the package
- Templates must remain deterministic and upgradeable
- Templates are **owned by OAK** — overwritten on `oak upgrade`
- Rendered via `TemplateService` using Jinja2

## Adding a New Agent

1. Create `src/open_agent_kit/agents/<agent_name>/manifest.yaml`
2. Define capabilities: command format, hooks support, settings paths
3. Mirror an existing agent with **similar capabilities**
4. Update `constants.py` with the new agent name
5. Update `agent_service.py` for any agent-specific logic

If capability mapping is unclear, **stop and ask** — do not invent assumptions.

## Adding a Command

1. Add a new command file in the appropriate feature's `commands/` directory
2. Register the command group in `cli.py`
3. Keep commands thin: parse inputs, call services, render output
4. Services own business logic

## Adding a Template

1. Place the template in the feature's `templates/` directory
2. Use Jinja2 syntax with variables from the service layer
3. Templates must be deterministic and upgradeable
4. Register in `template_service.py` if needed

## Quality Gates

All changes must pass `make check` before merge:

```bash
make check    # Runs format-check, typecheck, test
```

This runs:
- **`make format-check`** — Black + Ruff formatting
- **`make typecheck`** — Mypy type checking
- **`make test`** — pytest with coverage
