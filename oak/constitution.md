# Open Agent Kit (OAK) Constitution

## Metadata

- **Project:** open-agent-kit
- **Version:** 3.3.0
- **Status:** Adopted
- **Last Updated:** 2026-01-21
- **Author:** @sirkirby
- **Tech Stack:** Python 3.13+, Typer, Pydantic, Rich, Jinja2, ChromaDB, SQLite

**Purpose:** This document defines the **hard invariants** for designing, building, and maintaining Open Agent Kit (OAK). All agent instruction files must align with this constitution.

**What OAK is:** A local-first CLI tool for AI-powered development workflows. It ships agent-agnostic templates, rules, and tooling to help humans and coding agents build consistently.

**What OAK is not (non-goals):**

- Not an agent framework
- Not an agent replacement
- Not an agent orchestrator

---

## 1. Core Invariants (Hard Rules)

### 1.1 “Proper Engineering” Always

- Prefer correct foundations over shortcuts.
- Address root cause, not symptoms.
- If a change requires more work to be done “the right way,” do it. This project is built to be maintainable by a single engineer long-term.

### 1.2 Local-First (Meaningful Definition)

“Offline” in OAK means **AI and data workflows prefer local infrastructure**:

- Prefer **local LLMs** and **local embedding models** over cloud models.
- Prefer **local vector search** and **local transactional storage**:
  - **ChromaDB** for vector search
  - **SQLite** for transactional data

Network-required integrations (e.g., issue providers) are allowed, but **must not be required for core usage**.

### 1.3 Team Adoption, Local State

- OAK supports team-wide adoption through consistent rules/templates.
- OAK stores **user-local state** (agent sessions, code index, databases) that is **not committed to git**.
- Generated work products (docs/specs) should be safe to version-control; user-local indexes and sessions are not.

### 1.4 Idempotence by Default

Commands should be rerunnable safely.

- Re-running `oak init` should not break projects.
- `oak upgrade` should be safe to repeat.
- When overwriting is required, it must be explicit and explainable.

### 1.5 Templates Are Owned By OAK (Hard Rule)

- Templates shipped by OAK are **managed by OAK** and **overwritten on upgrade**.
- No user-owned template overrides. No “local template patching.” No precedence rules. OAK is the source of truth.

---

## 2. Golden Paths (How Changes Must Be Implemented)

Agents must follow these golden paths. If uncertain, **ask**. Do not freestyle.

### 2.1 Add a New Feature (Primary Golden Path)

Adding a feature may include:

- New CLI commands
- New templates
- New services/models
- Optional daemon support + UI + API surface (feature-dependent)
- Feature-specific storage (SQLite/ChromaDB) and migrations (feature-managed when appropriate)

**Must follow:**

- Use the **vertical slice** pattern (feature code co-located).
- Use existing features as anchors for structure and conventions.
- Prefer extension through new services + registration over “if/else sprawl.”

### 2.2 Add a New Agent (Primary Golden Path)

Adding an agent requires:

- Understanding the agent’s capabilities and constraints (install/remove, command formats, interaction style).
- Updating feature support appropriately based on those capabilities.

**Must follow:**

- Implement like an existing agent with **similar capabilities**.
- If capability mapping is unclear: **stop and ask** (do not invent assumptions).

### 2.3 Add a Command

- Commands should remain thin: parse inputs, call services, render output.
- Services own business logic.

### 2.4 Add a Template

- Templates must be generated from canonical sources in the package.
- Templates must remain deterministic and upgradeable.

### 2.5 Add a Config Value

- Prefer type-safe config (Pydantic models).
- Do not introduce ad-hoc dict/YAML handling unless there is a strong reason and it is documented.

## 2.6 Anchor Index (Canonical Examples)

Anchor files are the canonical reference implementations agents and contributors must copy.
If an anchor does not fit the work, stop and ask—do not invent new patterns.

### Golden Path: Add a New Feature (vertical slice)

**Primary exemplar feature: `strategic_planning`**

- `src/open_agent_kit/features/strategic_planning/manifest.yaml`
- `src/open_agent_kit/features/strategic_planning/rfc.py`
- `src/open_agent_kit/features/strategic_planning/plan/`
- `src/open_agent_kit/features/strategic_planning/commands/`
- `src/open_agent_kit/features/strategic_planning/templates/`

**Other exemplar feature services:**

- `src/open_agent_kit/features/rules_management/constitution.py`
- `src/open_agent_kit/features/codebase_intelligence/service.py`

### Golden Path: Add a New Agent

- `src/open_agent_kit/agents/gemini/manifest.yaml`
- `src/open_agent_kit/services/agent_service.py`
- `src/open_agent_kit/services/agent_settings_service.py`
- `src/open_agent_kit/constants.py`

### Golden Path: Add a Command

- `src/open_agent_kit/cli.py`
- `src/open_agent_kit/commands/skill_cmd.py`
- `src/open_agent_kit/commands/config_cmd.py`
- `src/open_agent_kit/commands/remove_cmd.py`

### Golden Path: Add a Template

- `src/open_agent_kit/services/template_service.py`
- `src/open_agent_kit/features/rules_management/templates/base_constitution.md`
- `src/open_agent_kit/features/rules_management/templates/includes/`
- `src/open_agent_kit/features/strategic_planning/templates/engineering.md`

### Golden Path: Add a Config Value

- `src/open_agent_kit/models/config.py`
- `src/open_agent_kit/models/enums.py`
- `src/open_agent_kit/config/settings.py`

### No-Magic-Literals (centralization taxonomy)

- `src/open_agent_kit/config/paths.py`
- `src/open_agent_kit/config/messages.py`
- `src/open_agent_kit/config/settings.py`
- `src/open_agent_kit/models/enums.py`
- `src/open_agent_kit/constants.py`
- `src/open_agent_kit/features/codebase_intelligence/constants.py`
- `src/open_agent_kit/features/codebase_intelligence/config.py`

### Upgrade + migrations

- `src/open_agent_kit/commands/upgrade_cmd.py`
- `src/open_agent_kit/services/upgrade_service.py`
- `src/open_agent_kit/services/migrations.py`

### Feature-managed data evolution (CI)

- `src/open_agent_kit/features/codebase_intelligence/schema.yaml`
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
- `src/open_agent_kit/features/codebase_intelligence/memory/store.py`

### CI “big rocks” (daemon, indexing, retrieval, MCP)

- `src/open_agent_kit/features/codebase_intelligence/daemon/server.py`
- `src/open_agent_kit/features/codebase_intelligence/daemon/manager.py`
- `src/open_agent_kit/features/codebase_intelligence/daemon/routes/`
- `src/open_agent_kit/features/codebase_intelligence/daemon/ui/`
- `src/open_agent_kit/features/codebase_intelligence/daemon/static/`
- `src/open_agent_kit/features/codebase_intelligence/indexing/chunker.py`
- `src/open_agent_kit/features/codebase_intelligence/indexing/indexer.py`
- `src/open_agent_kit/features/codebase_intelligence/indexing/watcher.py`
- `src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py`
- `src/open_agent_kit/features/codebase_intelligence/daemon/mcp_server.py`
- `src/open_agent_kit/features/codebase_intelligence/daemon/mcp_tools.py`
- `src/open_agent_kit/features/codebase_intelligence/mcp/mcp.yaml`
- `src/open_agent_kit/features/codebase_intelligence/hooks/claude/hooks.json`
- `src/open_agent_kit/features/codebase_intelligence/hooks/cursor/hooks.json`
- `src/open_agent_kit/features/codebase_intelligence/hooks/gemini/hooks.json`

### CI Data and Logs (Quick Reference)

Codebase Intelligence manages two databases and stores logs locally. Use these paths for debugging, data inspection, and backup operations:

| Resource | Path | Purpose |
|----------|------|---------|
| **SQLite Database** | `.oak/ci/activities.db` | Source of truth for all captured activity data (sessions, prompts, file events) |
| **ChromaDB** | `.oak/ci/chroma/` | Vector search database for semantic code search and memory retrieval |
| **Daemon Log** | `.oak/ci/daemon.log` | All CI daemon logs (startup, errors, indexing, API requests) |
| **User Backups** | `oak/history/` | SQL export files generated from the SQLite database (committed to git) |
| **Agent Configs** | `oak/agents/` | Custom agent task definitions (committed to git) |
| **Shared Port** | `oak/daemon.port` | Team-shared daemon port derived from git remote (committed to git) |
| **Analysis Reports** | `oak/insights/` | Analysis agent output reports (committed to git) |
| **Agent-Generated Docs** | `oak/docs/` | Documentation agent output (committed to git) |

**Notes:**

- The SQLite database (`.oak/ci/activities.db`) is the authoritative source; ChromaDB is derived/rebuilt from it.
- Files in `oak/` (history, agents, insights, docs, daemon.port) are intended for version control and team consistency.
- The `.oak/ci/` directory is gitignored (user-local state per §1.3).
- Port resolution priority: `.oak/ci/daemon.port` (local override) > `oak/daemon.port` (team-shared) > auto-derive from git remote.

### Quality gates + docs

- `Makefile` (must pass: `make check`)
- `pyproject.toml`
- `.github/workflows/pr-check.yml`
- `docs/development/features.md`
- `docs/development/migrations.md`
- `docs/development/releasing.md`

---

## 3. Architecture Rules

### 3.1 Layering

OAK follows a layered architecture:

- **CLI Layer (Typer):** user entry points, flags, dispatch
- **Command Layer:** command implementations
- **Service Layer:** business logic
- **Model Layer (Pydantic):** typed data structures
- **Storage Layer:** filesystem, YAML, SQLite, ChromaDB

### 3.2 Vertical Slice Features

Features are self-contained packages under `src/open_agent_kit/features/<feature_name>/`:

- Feature services live with feature code.
- Feature manifests declare defaults and install assets.
- Feature-specific storage logic is owned by the feature.

### 3.3 “Extend, Don’t Patch”

When adding functionality:

- Prefer **new service + registration** or **new strategy** rather than modifying unrelated code paths.
- Avoid growing god-services and mega-constants files. Refactor early.

### 3.4 Prefer Dependency Injection Over Service Location

When a component depends on a shared value or service (e.g., machine identity, configuration):

- **Inject via constructor parameters** rather than having each call site independently resolve.
- **Compute once, pass everywhere:** resolve at the composition root (daemon startup, CLI entry point) and thread through constructors.
- **No silent fallbacks.** If a dependency is required, make the parameter required. Optional parameters with auto-resolve fallbacks perpetuate the service-locator pattern.
- **Do not use late imports to resolve global state** in hot-path functions — this is a service-locator anti-pattern that creates implicit coupling and harms testability.

Rationale: service-locator patterns cause data mismatches (different resolution context per call site), redundant I/O, and test fragility requiring monkeypatch at multiple references.

Canonical example: `ActivityStore(db_path, machine_id)` — `machine_id` is a required parameter resolved once at the composition root, exposed as `store.machine_id` for all operations.

---

## 4. No-Magic-Literals (Zero Tolerance)

**No literal strings or numbers in code.** This includes tests.

Rationale: literals create silent drift and hard-to-find bugs.

### 4.1 Where Values Must Live

Default approach: centralize in `constants.py` until it becomes unwieldy; then decompose by domain.

- Start simple (central constants), evolve into domain modules when necessary.
- Decomposition is allowed, but the rule remains: **no literals in code**.

Recommended decomposition pattern when `constants.py` becomes too large:

- `config/paths.py` — file/dir names and paths
- `config/messages.py` — user-facing text
- `config/settings.py` — runtime settings (env vars via Pydantic Settings)
- `models/enums.py` — type-safe enums for statuses/keys
- `constants/*.py` — domain constants (validation, agent configs, feature registry, etc.)

### 4.2 Type Safety Preferred

- Prefer Pydantic models and enums over raw dicts and string lists.
- If a value crosses a boundary (CLI ↔ config ↔ storage ↔ templates), it must be centralized and typed.

---

## 5. CLI Behavior and Output

### 5.1 Human vs Agent Output

- Humans default to Rich, friendly CLI output.
- Agent-facing commands may return more efficient structured output (e.g., JSON) **when it improves agent reliability**, but `--json` is not a global requirement.

### 5.2 Logging and Observability (Hard Requirement)

- Logging must be consistent, structured, and leveled for both humans and agents.
- Prefer predictable error output with enough context to debug without guesswork.
- If error codes are introduced, they must be consistent and centrally managed.

### 5.3 Error Handling

- Error output must be actionable: what failed + why + what to do next.
- Prefer stable error messages via centralized message constants (no inline strings).

---

## 6. Upgrade, Migrations, and Data Evolution

### 6.1 Upgrade Must Be Explainable (Hard Rule)

- `oak upgrade` must support a dry-run mode that explains what will happen.
- Users should be able to understand what changes are going to be applied before they commit.

### 6.2 What “Migrations” Mean in OAK

There are two categories of migration:

1) **Init/Upgrade System Migrations (OAK-managed)**

- Reserved for major changes that affect what OAK installs into the user’s project.
- Use existing migrations as anchors and follow established patterns.

2) **Feature-Managed Migrations**

- Some features (e.g., codebase intelligence) may manage their own schema/data migrations after upgrade.
- Feature-managed migrations must be automatic, safe, and testable.

Rule of thumb:

- If it mutates or restructures **installed user project assets** in a major way → OAK migration.
- If it evolves **feature-owned databases/data** → feature-managed migration.

---

## 7. Quality Gates and Definition of Done (DoD)

### 7.1 Hard Gate

- `make check` must pass for every change.

### 7.2 Definition of Done (Non-Negotiables)

For every change:

- `make check` passes (lint, format, typing, tests, etc.)
- README is reviewed and updated if behavior, install, or workflows changed
- Documentation is updated to prevent drift:
  - If you touch a feature, update the feature's doc (or create one if missing)
- No "drive-by" changes without docs/tests when behavior changes
- No literals added anywhere (including tests)

### 7.3 Development Tooling (Hard Rules)

**Python Version:** OAK requires Python 3.13. The project's `.python-version` file enforces this.

**Editable Install (MUST preserve):** OAK is developed locally via `uv tool install -e . --force` (see `make setup` / `make sync`). The `-e` flag creates an editable install so Python's `__file__` resolves to the **source tree**, not site-packages. This is critical because:

- The CI daemon uses `Path(__file__)` to locate static assets and templates at runtime.
- Without `-e`, changes to Python files and rebuilt UI assets are invisible to the running daemon.
- Breaking the editable install silently causes stale behavior with no error messages.

**Hard rules for install commands:**

- **MUST NOT** run `uv tool install` without the `-e` flag.
- **MUST NOT** run `uv pip install` without `-e`.
- **MUST** use Makefile targets (`make setup`, `make sync`) instead of ad-hoc install commands. These targets ensure both the correct Python version and the `-e` flag.
- After any install or sync operation, **MUST** verify the editable install is intact:

```bash
oak --python-path -c "import open_agent_kit; print(open_agent_kit.__file__)"
# Output MUST contain the source tree path (e.g., src/open_agent_kit/__init__.py)
# Output MUST NOT contain .local/share/uv/tools/
```

**Troubleshooting:** If the CI daemon serves stale assets or Python changes are not reflected, the editable install is the first suspect. Run the verification command above.

**Project-scoped commands:** For project-scoped operations (`uv sync`, `uv run`, etc.), the `.python-version` file ensures the correct Python version is used automatically.

---

## 8. Execution Model (Specialized + Background Agents)

To manage context effectively and speed up delivery, agents must use specialized/background agents for parallelizable work whenever available.

### 8.1 Plan First (Hard Rule)

Before making non-trivial changes, the primary agent must produce a short plan that includes:

- the intended approach (high level)
- impacted areas (files/modules/features)
- delegated tasks (specialized/background agents) and expected outputs
- verification steps (how `make check` + docs will be satisfied)

**Trivial change exception:** A change is considered trivial only if all are true:

- single-file edit
- no new behavior or workflow
- no config, templates, migrations, or schema changes
- no new tests required (existing tests already cover it)

If any of the above are false, the change is non-trivial and requires a plan + delegation.

### 8.2 When to Delegate

Delegate whenever the work includes any of:

- repo discovery (“where should this live?” / “what’s the closest anchor?”)
- design exploration (multiple approaches or tradeoffs)
- test planning (edge cases, failure modes, scenarios)
- migration or upgrade impact analysis
- performance, reliability, or security review
- external documentation or library research

### 8.3 Allowed Sub-Agent Outputs

Sub-agents may produce:

- candidate file/path lists (anchors, impacted modules)
- short design proposals with tradeoffs
- test plan + edge-case matrix
- migration plan and risks
- documentation drafts
- acceptance criteria / Definition of Done checklist for the change

Sub-agents must not produce final code changes unless explicitly instructed with:

- the applicable golden path
- the anchor files to copy
- the non-negotiables that must be preserved

### 8.4 Integration Rule: Single Source of Truth

The primary agent remains responsible for:

- selecting the final approach (anchored to existing repo patterns)
- implementing changes in-repo using golden paths and anchors
- enforcing invariants (no magic literals, idempotence, template ownership, etc.)
- running `make check` and ensuring it passes
- updating docs to prevent drift

### 8.5 Conflict Resolution

When sub-agent results conflict:

- prefer anchors and established repo patterns
- if uncertainty remains, ask rather than inventing a new pattern
- if a better pattern is adopted, update the constitution/playbooks so it becomes the standard

## 9. Deviation Process (Narrow Lanes)

These are hard rules with narrow lanes for deviation.

### 9.1 When Unsure: Ask

If a rule seems to conflict with the change:

- Stop and ask rather than guessing.

### 9.2 If a New Pattern Is Adopted

If you deviate because a better pattern is needed:

- Update this constitution (or the relevant playbook) so the new pattern becomes the default going forward.

### 9.3 Where Decisions Live

- Formal design decisions → RFC
- Less formal decisions → feature doc or project doc
- All deviations should result in clearer future rules (reduce repeat friction)

---

## 10. Canonical Project Layout (Reference)

OAK source layout and generated user layout are defined in the project docs.
This constitution defines invariants; detailed playbooks live in:

- `docs/development/features.md`
- `docs/development/migrations.md`
- `docs/issue-workflow.md`

---

**This constitution is the source of truth for how OAK is built. Agents and contributors must follow it.**
