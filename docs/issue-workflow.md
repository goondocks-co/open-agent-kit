# Issue Provider Workflow

This guide documents how `oak issue plan|validate|implement` operate so the constitution
can focus on standards. Reference it whenever you need to run issue-provider commands or help a
user navigate the workflow.

## Prerequisites and Setup (Human Operators Only)

1. A constitution must already exist at `oak/constitution.md`. If missing, run
   `/oak.constitution-create` in your agent.
2. A human must configure the issue provider via `oak config` (or
   `oak config issue-provider set`). Agents must never run this command.
3. The human provides an issue identifier (Azure DevOps ID, GitHub issue, etc.).
4. Optional: verify everything with `oak config issue-provider check` before calling any
   `oak issue ...` commands.

## Agent Workflow Requirements

- Treat `oak issue ...` commands as deterministic utilities for gathering context—agents
  still do the reasoning.
- Enforce prerequisites in order (constitution, provider config, issue ID). If anything is
  missing, stop and instruct the human to resolve it.
- Users may explicitly choose to bypass issue linking, but they must acknowledge the extra
  context they will provide instead.

## Command Phases

| Command | Purpose | Requirements |
|---------|---------|--------------|
| `oak issue plan <ISSUE>` | Scaffolds artifacts (`plan.md`, `context.json`, branch), captures remote issue spec. | Provider configured + issue ID |
| `oak issue validate <ISSUE>` | Reads artifacts from the plan step, highlights missing context, enforces spec completeness. | Successful `issue plan` run |
| `oak issue implement <ISSUE>` | Re-checkouts branch and prepares implementation context, strongly encouraging validation first. | Completed plan (and ideally validation) |

- Commands never perform reasoning—agents inspect the generated artifacts and repository to
  make decisions.

## Artifacts and Exploration

- Artifacts live under `oak/issue/{provider}/{identifier}/` and include:
  - `context.json` – structured snapshot from the issue provider.
  - `plan.md` – human-readable plan scaffold.
  - `codebase.md` (optional) – repository snapshot captured during planning.
- Agents must open these artifacts before suggesting solutions; they capture real specs and
  repository state.
- After implementation, re-run `oak issue validate <ISSUE>` (or `/oak.issue-validate`) to
  confirm objectives, risks, dependencies, and definition-of-done are still satisfied.

## Reference

- `README.md` – high-level overview for humans.
- `.constitution.md` §V.5 – constitutional summary and prerequisites.
- `templates/commands/oak.issue-plan.md` – agent command template for running the workflow.
