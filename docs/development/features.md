# Feature Development Playbook

This guide expands on the high-level expectations captured in `.constitution.md`. Use it any
time you add or significantly extend an open-agent-kit feature to ensure all integration points,
tests, and docs stay in sync.

## Critical Integration Points

When a feature introduces new agent commands, update both services so fresh installs and
upgrades behave consistently:

1. `src/open_agent_kit/services/agent_service.py::create_default_commands()` – controls which
   commands `oak init` installs.
2. `src/open_agent_kit/services/upgrade_service.py::_get_upgradeable_commands()` – ensures
   `oak upgrade` delivers the same commands to existing projects.

## Phase Checklist

### Phase 1 – Planning & Design

- Define feature scope and success criteria.
- Identify new constants (paths, statuses, messages) and add them to `constants.py`.
- Design required models, services, CLI commands, agent workflows, and configuration
  needs.

### Phase 2 – Core Implementation

- Add constants to `src/open_agent_kit/constants.py`.
- Create or update models (and export them in `models/__init__.py`).
- Add supporting utilities in `src/open_agent_kit/utils/` when needed.
- Implement services (remember `from_config()` helpers and `services/__init__.py` exports).
- Provide document/command templates in `templates/`.

### Phase 3 – CLI Integration

- Add Typer commands under `src/open_agent_kit/commands/`.
- Register them in `src/open_agent_kit/cli.py`.
- Ensure every utility command supports `--json`.
- Update `AgentService` and `UpgradeService` command lists (critical!).

### Phase 4 – Agent Commands

- Add agent command templates (e.g., `templates/commands/oak.feature-action.md`).
- Run `oak init` in a fresh sandbox to confirm commands install for all agents.

### Phase 5 – Testing

- Write unit tests for models, utilities, services, and CLI flows.
- Cover new templates or rendering logic.
- Run the full suite (`pytest`, `ruff`, `black`, `mypy`) before opening a PR.
- Verify `oak init` and `oak upgrade` succeed end to end.

### Phase 6 – Documentation

- Update `README.md`, `QUICKSTART.md`, and relevant docs.
- Refresh agent instructions if the workflow changes.
- Amend `.constitution.md` only when standards or patterns evolve.

## Common Pitfalls

- **Forgetting service command lists** → new commands never reach users.
- **Magic strings** → always import from `open_agent_kit.constants`.
- **Missing exports** → add new models/services to `__init__.py`.
- **No JSON output** → agents cannot parse CLI responses.

## Configuration Guidance

Use dedicated config sections when a feature exposes user-facing options (multiple
templates, numbering strategies, directory overrides). Skip config when the feature has a
single, fixed behavior (e.g., constitution files).

## File Touchpoints

Expect to modify:

```
src/open_agent_kit/constants.py
src/open_agent_kit/models/**/*.py
src/open_agent_kit/services/**/*.py
src/open_agent_kit/commands/**/*.py
src/open_agent_kit/cli.py
templates/**/*
tests/**/*  (matching the source you changed)
docs/**/*   (README, QUICKSTART, feature docs)
.constitution.md (only if standards change)
```

## Validation Steps

1. **Fresh install:** `oak init`, ensure new files appear in `.oak/` and agent command
   folders.
2. **Upgrade:** run `oak upgrade` in an older project to confirm commands/templates
   update.
3. **Command execution:** exercise each new CLI subcommand with and without `--json`.
4. **Agent integration:** invoke the agent command (`/oak.feature-action`) and verify the
   workflow completes.

## Example Scenario

When adding a review workflow:

1. Create review constants (`REVIEW_DIR`, `REVIEW_STATUSES`, ...).
2. Define `Review` models and services.
3. Build CLI commands (`oak review create`, etc.) with JSON output.
4. Register commands in `cli.py`, `AgentService`, and `UpgradeService`.
5. Supply agent command templates under `templates/commands/`.
6. Write unit/integration tests covering the new flow.
7. Document usage in README/QUICKSTART.

Follow this playbook alongside the constitution to keep contributions predictable and
upgrade-safe.

