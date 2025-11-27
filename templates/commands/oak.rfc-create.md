---
description: Create a new RFC document from a natural language description.
handoffs:
  - label: Validate RFC
    agent: oak.rfc-validate
    prompt: Validate this RFC for accuracy and completeness.
---

## User Input

```text
$ARGUMENTS
```

The text provided after the command is the RFC request. Treat it as canonical context (even if `$ARGUMENTS` literally appears above). Do not ask the user to repeat unless it is empty.

## Purpose

Own the end-to-end RFC authoring process. You are responsible for understanding the request, evaluating existing project context, selecting the right template, producing a thorough draft, and guiding next steps. CLI commands help you, but you must reason through every decision.

## Workflow Overview

1. Confirm intent and gather essential details from the user.
2. Investigate the repository and prior RFCs (brownfield) or existing code (greenfield) for grounding.
3. Choose the appropriate template with documented rationale.
4. Draft a structured outline before generating any files.
5. Use `oak rfc create` to scaffold the RFC, then replace placeholders with your curated content.
6. Perform a quality review, reference related RFCs, and offer validation.
7. Report outcomes, open questions, and recommended next actions.

## Step 1: Intake & Clarification

1. Parse `$ARGUMENTS` for the initial proposal. Identify:
   - Problem statement / opportunity
   - Desired outcomes and scope
   - Any explicit template hints (architecture, feature, process)
2. Engage the user to fill gaps:
   - Stakeholders and ownership
   - Target timelines or releases
   - Known constraints (compliance, dependencies, service-level objectives)
   - Existing documents or tickets to reference
3. Mirror back your understanding to confirm alignment before proceeding.

## Step 2: Context Discovery (Brownfield & Greenfield)

Plan and execute a discovery pass:
- **Existing RFCs**: run `oak rfc list --status adopted --json` (or similar) to find related decisions; summarize overlaps/questions.
- **Codebase analysis**: inspect relevant directories (`find`, `rg`, `ls`, `tree`) to understand current architecture, modules, and tests.
- **Documentation & ADRs**: search `docs/`, `adr/`, or `README` sections for prior art.
- **Operational signals**: check CI configs, monitoring dashboards references, or linked issues.

Record each finding with:
- Command executed
- Key facts learned
- Implications for the RFC (e.g., “Service already emits metrics via X → include in Observability plan”).

## Step 3: Template Selection & Justification

1. Shortlist candidate templates (engineering, architecture, feature, process) along with pros/cons.
2. If ambiguity remains, ask the user to choose. Present options with implications.
3. Document why the chosen template fits—refer to discovery evidence.
4. Capture required metadata (author, tags, related RFCs) and confirm with the user.

## Step 4: Outline & Synthesis Notebook

Before generating files, build an outline:
- Section-by-section bullet list with specific points you will cover.
- References to code commits, metrics, diagrams, or historical context you plan to cite.
- Potential risks, open questions, and alternative approaches identified.

Share the outline with the user for feedback; incorporate adjustments before drafting.

## Step 5: Scaffold via CLI (Support Tool)

Run the CLI once alignment is confirmed:
```bash
oak rfc create "{RFC_TITLE}" --template {TEMPLATE} [--author "{AUTHOR}"] [--tags "tag1,tag2"]
```
- Capture the generated RFC path and number.
- Immediately open the file to verify header metadata (number, title, author, date, status, tags).
- Note any automatic validation results printed by the CLI.

## Step 6: Author the RFC (Replace Placeholders)

1. Rewrite every placeholder with substantive content using your outline:
   - Provide measurable success criteria and acceptance gates.
   - Add diagrams, tables, or links where helpful.
   - Document trade-offs, alternatives, rollout plans, monitoring, and rollback strategies.
2. Reference previous RFCs or ADRs when superseding or extending them. Update metadata (`Supersedes`, `Superseded by`) if applicable.
3. If the proposal depends on existing code, cite concrete modules/PRs and planned changes.
4. Continually check for consistency with the project’s established patterns and terminology.

## Step 7: Related RFC & Artifact Cross-Check

1. Use the CLI to surface potentially related proposals:
   ```bash
   oak rfc list --json --status adopted
   ```
   Filter locally (or re-run with `--status review`, `--status draft`, or `--status implemented`) to identify RFCs that touch the same domain. Combine with natural-language search by piping through tools like `jq`, `rg`, or `grep`.
2. For each candidate, inspect details:
   ```bash
   oak rfc show RFC-<number>
   ```
   Summarize how the new RFC aligns with, extends, or supersedes these decisions. If conflicts exist, highlight mitigation strategies and update `Supersedes`/`Superseded by` fields as needed.
3. Confirm tags, stakeholders, and dependencies are updated accordingly.

## Step 8: Quality Review & Optional Validation

1. Self-assess the RFC using a rubric (score 1–5 with evidence):
   - Clarity & Narrative Flow
   - Technical Depth & Feasibility
   - Risks & Mitigations
   - Alignment with existing architecture and standards
   - Rollout & Measurement readiness
2. Offer to run validation:
   > "Would you like me to run `oak rfc validate RFC-{number}` now to check structural integrity?"
   - If **yes**: execute, interpret results, and fix issues immediately.
   - If **no**: document that validation was deferred and call out potential risks.
3. Ensure placeholders cannot trigger validation warnings—replace any `[text]` remnants.

## Step 9: Final Report & Next Steps

Summarize the outcome:
- RFC number, title, template, file path
- Key decisions, risks, and open questions
- Related RFCs / artifacts consulted
- Rubric scores and validation status (ran vs deferred)
- Suggested next actions (stakeholder review, ADR update, implementation plan, timeline)
- Any follow-up items for the user (e.g., “Provide metrics baseline”, “Schedule design review”).

## Response Expectations

- Keep the user informed at each decision point (template choice, major scope changes, validation).
- Provide evidence-backed reasoning for every recommendation.
- Distinguish clearly between facts (discovery) and assumptions; call out assumptions explicitly.
- Ensure the final RFC is ready for team review, not a skeleton.
