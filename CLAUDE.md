# Claude Code Instructions for open-agent-kit

Claude is treated as a senior engineer on this project. Everything below points back to
[.constitution.md](.constitution.md), which remains the single source of truth for
architecture, coding standards, workflows, and governance.

---

## 1. Orientation

1. Read `.constitution.md` before touching code or drafting an RFC.
2. Use the companion playbooks when you need deeper detail:
   - Feature delivery: `docs/development/features.md`
   - Migration workflow: `docs/development/migrations.md`
3. Keep `README.md`, `QUICKSTART.md`, and `docs/` handy for user-facing context.

---

## 2. Claude's Role

- Generate and review RFCs with the structure defined in `.constitution.md` §VI.
- Implement features, fix bugs, and write tests following the layered architecture in
  `.constitution.md` §III and the coding standards in §IV.
- Keep responses explanatory—summarize reasoning, reference the sections you followed, and
  highlight follow-up steps for the user.

---

## 3. Standard Workflow (Pointer Summary)

1. **Clarify requirements.** Ask for missing inputs (issue ID, constraints, success
   metrics) before acting.
2. **Inspect the repo.** Use the prescribed tooling to read files, run targeted commands, or
   gather context from `oak` CLI utilities.
3. **Implement to spec.** Apply the constants-first rule, Google-style docstrings, and testing
   expectations described in `.constitution.md` §IV.
4. **Validate.** Run the required checks (`ruff`, `black`, `mypy`, `pytest`) when the task
   involves code changes. Mention anything you could not execute.
5. **Document outcomes.** Update README/QUICKSTART/docs only when behavior changes; update the
   constitution only when standards change.

---

## 4. RFC Coverage

- **Creation:** Follow the template requirements (header, objective, problem, proposed
  solution, implementation plan, risks, and alternatives). Include mermaid diagrams and file
  references when helpful.
- **Review:** Use the checklist and feedback format from `.constitution.md` §VI. Findings come
  first, ordered by severity.

---

## 5. Resources

- `.constitution.md` – canonical standards
- `docs/development/features.md` – feature delivery playbook
- `docs/development/migrations.md` – migration playbook
- `README.md`, `QUICKSTART.md`, `docs/architecture.md` – user and architectural references

Pin these links in your workspace so future updates stay centralized and duplication across
agent files is minimized.
