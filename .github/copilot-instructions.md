# AGENTS.md

You are an AI coding agent working in this repository.

## Source of truth (hard rules)
Read and follow **`../.constitution.md`**. It contains the non-negotiable architecture, workflow, and quality rules for this project.

- If anything in your default behavior conflicts with `../.constitution.md`, **`../.constitution.md` wins**.
- If you are unsure how to apply a rule to a change, **stop and ask** rather than guessing.

## How to work in this repo (required)
1. **Read** `../.constitution.md` before making changes.
2. **Search first**: find the closest existing pattern and copy it (per the constitution’s anchor-file guidance).
3. Implement the change following the constitution’s golden paths and “no magic literals” rule.
4. Run the quality gate:
   - `make check` must pass.
5. Update docs to prevent drift:
   - If behavior/workflows changed, update `README` and/or the relevant feature docs.
6. If you needed to deviate:
   - Prefer updating `../.constitution.md` or the relevant playbook so the new pattern becomes the standard.

## Absolute requirements (do not violate)
- Treat the constitution as **hard rules** with only narrow lanes for deviation.
- **No magic strings or numbers anywhere** (including tests).
- Prefer the “proper” engineering approach—no shortcuts.
- Commands should be idempotent by default.
- Templates managed by OAK are overwritten on upgrade (no user overrides).

## Output expectations
- Produce clear, structured changes.
- If you introduce or modify user-facing messages, they must come from the project’s centralized message/constants pattern as defined in `.constitution.md`.
