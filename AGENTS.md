# AI Agent Instructions for open-agent-kit

**Audience:** Codex CLI, Cursor, and any compatible AI agents
**Primary rule:** Always anchor decisions in [.constitution.md](.constitution.md). That file is the
canonical reference for architecture, coding standards, workflows, and governance.

This document simply orients agents and points to the right sections so we avoid duplicating
guidance.

---

## 1. Read This First

1. Skim `.constitution.md` to understand current standards.
2. Use the new playbooks when you need deeper detail:
   - Feature delivery: `docs/development/features.md`
   - Migration workflow: `docs/development/migrations.md`
3. Keep `README.md`, `QUICKSTART.md`, and `docs/` open for user-facing context.

---

## 2. Core Expectations (Pointers Only)

- **Coding standards:** `.constitution.md` §IV – covers formatting, error handling, constants,
  and testing expectations. Never introduce magic strings; import from
  `src/open_agent_kit/constants.py`.
- **Architecture:** `.constitution.md` §III – layered patterns plus key services to inspect
  before implementing new logic.
- **Workflow:** `.constitution.md` §V – outlines the before/after coding checklist, release
  gates, and issue-provider prerequisites.

Refer to those sections instead of re-stating the rules here.

---

## 3. Agent Workflow Checklist

1. **Clarify the request.** Ask users for missing inputs (issue IDs, constraints, etc.).
2. **Consult the constitution.** Identify the relevant section(s) before coding or writing.
3. **Inspect the codebase.** Use the prescribed utilities (`codebase_search`, `read_file`, CLI
   commands) to gather context instead of guessing.
4. **Apply standards.** Follow the layered architecture, constants-first rule, and testing
   requirements from the constitution.
5. **Document outcomes.** Update README/QUICKSTART/docs only when behavior changes, keeping the
   constitution for standards-level edits.

---

## 4. Task Shortcuts

- **Implementing features:** use the Feature Development Playbook for step-by-step coverage,
  then summarize in PR/response referencing the sections you touched.
- **Writing migrations:** follow the Migration Playbook and note the migration ID + rationale in
  your response.
- **RFC generation/review:** `.constitution.md` §VI outlines required sections, diagrams, and
  review format—quote that instead of duplicating checklists here.
- **Issue provider commands:** ensure prerequisites from `.constitution.md` §V are satisfied
  (constitution present, provider configured, issue ID supplied) before running any
  `oak issue ...` commands.

---

## 5. Resources

- `.constitution.md` – definitive standards
- `docs/development/features.md` – feature playbook
- `docs/development/migrations.md` – migration playbook
- `README.md` / `QUICKSTART.md` – user documentation
- `docs/architecture.md` – deeper architectural background

Pin these references in your workspace so future updates stay centralized and duplication is
avoided.
