# Instructions for AI Contributors

You are an AI coding agent working in this repository.

## Source of truth (hard rules)
Read and follow **`oak/constitution.md`**. It is the authoritative specification for architecture, conventions, golden paths, and quality gates.

- If anything conflicts with `oak/constitution.md`, **`oak/constitution.md` wins**.
- If you are unsure how to apply a rule, **stop and ask** rather than guessing.
- The **canonical Anchor Index** lives in `oak/constitution.md`.

## Required workflow
1. Read `oak/constitution.md` (especially the golden paths + hard rules + DoD).
2. **Search first**: find the closest existing implementation and mirror it (use the Top Anchors below).
3. Implement the change following the constitution.
4. Run the quality gate: `make check` (must pass).
5. Update docs to prevent drift:
   - Review/update `README` if behavior/workflows changed.
   - Update the relevant feature docs (or create them) when touching feature behavior.
6. If a better pattern is needed:
   - Record the decision (RFC for formal, doc for informal) and update rules/docs so the new pattern becomes standard.

## Non-negotiables
- **No magic strings or numbers anywhere** (including tests).
- Prefer proper engineering over shortcuts; fix root causes, not symptoms.
- Commands should be idempotent by default.
- Templates shipped by OAK are managed by OAK and overwritten on upgrade (no user overrides).
- Narrow lanes for deviation; when unclear, ask.

---

## Top Anchors (shorthand)

These are the first places to look. The full Anchor Index is in `oak/constitution.md`.

### Add a New Feature (vertical slice exemplar)
- `src/open_agent_kit/features/strategic_planning/manifest.yaml`
- `src/open_agent_kit/features/strategic_planning/rfc.py`
- `src/open_agent_kit/features/strategic_planning/commands/`
- `src/open_agent_kit/features/strategic_planning/templates/`

### Add a New Agent
- `src/open_agent_kit/agents/gemini/manifest.yaml`
- `src/open_agent_kit/services/agent_service.py`
- `src/open_agent_kit/constants.py`

### Add a Command
- `src/open_agent_kit/cli.py`
- `src/open_agent_kit/commands/skill_cmd.py`

### Templates (rendering + exemplar assets)
- `src/open_agent_kit/services/template_service.py`
- `src/open_agent_kit/features/rules_management/templates/base_constitution.md`

### Upgrade + migrations
- `src/open_agent_kit/commands/upgrade_cmd.py`
- `src/open_agent_kit/services/upgrade_service.py`
- `src/open_agent_kit/services/migrations.py`

### Quality gate
- `Makefile` (must pass: `make check`)
- `pyproject.toml`
- `oak/constitution.md` (DoD + canonical Anchor Index)
