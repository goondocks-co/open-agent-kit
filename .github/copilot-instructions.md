# GitHub Copilot Instructions for open-agent-kit

Copilot complements human contributors, but it must follow the same standards spelled out in
[../.constitution.md](../.constitution.md). This file only highlights how to stay aligned
without duplicating that content.

---

## 1. Required References

1. **Standards:** `../.constitution.md` – architecture, coding rules, workflows.
2. **Feature playbook:** `../docs/development/features.md` – end-to-end checklist when adding
   functionality.
3. **Migration playbook:** `../docs/development/migrations.md` – when to create migrations and
   how to test them.
4. **User docs:** `../README.md`, `../QUICKSTART.md`, `../docs/` – update when behavior changes.

---

## 2. Copilot's Operating Rules

- Always import literals from `oak.constants` (constants-first rule, constitution §IV).
- Follow the layered architecture (constitution §III) when suggesting new code: CLI → command →
  service → models/utilities.
- Ensure every CLI helper offers `--json` output so agents can consume responses.
- Suggest Google-style docstrings and exhaustive type hints on public functions.
- Never add or modify issue-provider configuration—humans run `oak config`.

---

## 3. Contribution Flow (Pointer Summary)

1. Clarify the task and required inputs.
2. Inspect existing implementations before generating code.
3. Produce diffs that respect formatting (`black` 100-char lines) and linting (`ruff`).
4. Include or update tests (`pytest`), type checks (`mypy`), and docs when behavior changes.
5. Reference the relevant constitution section(s) in explanations so reviewers can trace the
   standard applied.

---

## 4. RFC Work

- **Creation/Review:** Follow the structure and feedback guidelines in constitution §VI. Include
  diagrams or file references rather than inventing new formats.
- **Agent commands:** When templates or agent workflows need updates, pair changes with the
  feature playbook to ensure `AgentService` and `UpgradeService` command lists stay in sync.

---

## 5. Quick Resource Map

| Need help with...        | Go to...                                |
|--------------------------|-----------------------------------------|
| Coding standards         | `../.constitution.md` §IV               |
| Architecture patterns    | `../.constitution.md` §III & `docs/`    |
| Feature delivery steps   | `../docs/development/features.md`       |
| Migration authoring      | `../docs/development/migrations.md`     |
| User-facing references   | `../README.md`, `../QUICKSTART.md`      |

Keep this table handy and defer to the linked docs whenever details are required.
