---
description: Validate RFC document structure and content quality.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** incorporate any provided context before prompting the user.

## Purpose

Lead a comprehensive validation of the target RFC. Combine automated checks with your own qualitative review, collaborate with the user on fixes, and ensure the document is ready for the next stage of the RFC process.

## Workflow Overview

1. Identify the RFC to validate and gather metadata (status, author, date).
2. Run discovery to understand related context and expectations.
3. Perform structural and qualitative analysis (CLI + manual review).
4. Prioritize findings, recommend fixes, and offer assistance applying them.
5. Summarize the validation outcome and next steps.

## Step 1: Target Identification & Context

1. Determine the RFC identifier from `$ARGUMENTS`. If absent, ask the user which RFC should be validated.
2. Resolve the RFC path using `oak rfc list --verbose` or `oak rfc show {number}`.
3. Collect metadata:
   - Current status (draft, review, approved, etc.)
   - Creation date, author, tags
   - References or supersedes links
4. Share the information with the user to confirm the RFC under review and understand validation goals (e.g., ready for review vs. ready to adopt).

## Step 2: Discovery & Preparation

1. Inspect surrounding context:
   - Related RFCs (same tags, similar scope) using the RFC service helper.
   - Recent commits or documentation changes that impact the proposal.
   - Open questions or TODOs noted elsewhere (issues, discussions).
2. Record findings and potential focus areas (e.g., “Architecture decisions must align with ADR-005”).

## Step 3: Automated Checks (Optional, With Consent)

Ask the user whether to run automated validation:
> "Would you like me to run `oak rfc validate RFC-{number}` (strict mode if needed) to check structure automatically?"

- If **yes**: execute the command, capture the output (success or issue list), and translate it into actionable insights.
- If **no**: note the deferral and proceed with manual inspection.

## Step 4: Manual Review & Analysis

Review the RFC file directly. Evaluate:

### Structural Completeness
- Required sections present and ordered per template
- No placeholder text or `[TODO]` markers remaining
- Metadata (status, tags, references) accurate

### Content Quality
- Clear summary that frames the problem
- Motivation grounded in data or user outcomes
- Design details precise, technically feasible, and scoped
- Risks/drawbacks acknowledged with mitigation strategies
- Alternatives thoughtfully considered (not token placeholders)
- Success metrics measurable and aligned with goals
- Rollout/implementation plan realistic for stakeholders

### Consistency & Traceability
- References to prior RFCs or ADRs are valid and linked
- Terminology matches existing documentation
- Dependencies and ownership clearly assigned
- No contradictions with adopted standards

Record findings with severity levels:
- **Critical**: Must fix before progressing (missing sections, incorrect status, blocking inconsistencies)
- **Major**: Should fix soon (ambiguous scope, weak success metrics)
- **Minor**: Nice-to-have improvements (stylistic, optional examples)

## Step 5: Collaborate on Fixes

1. Present findings grouped by severity with supporting evidence (line snippets, section references).
2. Offer suggested fixes or next steps for each issue.
3. Ask the user if they want assistance applying fixes now. If so:
   - Propose concrete edits (diffs or rewritten paragraphs).
   - After each fix, re-run targeted validation if applicable.

## Step 6: Final Assessment & Recommendations

1. Provide an overall rating (Ready / Needs Work / Blocked) with justification.
2. Summarize fixes applied (if any) and outstanding issues.
3. Highlight any follow-up tasks (e.g., gather metrics, schedule architecture review).
4. Suggest when to rerun `oak rfc validate` (if deferred earlier) and other quality gates (peer review, prototype testing).

## Response Expectations

- Maintain an interactive tone—confirm target RFC, seek consent before running commands or editing content, and pause for decisions on major issues.
- Reference specific sections and line snippets when describing findings.
- Ensure the user leaves with a clear action plan, not just a list of problems.
- Keep automated tooling in a supporting role; your qualitative judgment drives the final recommendation.
