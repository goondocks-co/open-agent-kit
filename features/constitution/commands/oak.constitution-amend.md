---
description: Add a versioned amendment to the engineering constitution.
handoffs:
  - label: Validate Constitution
    agent: oak.constitution-validate
    prompt: Validate the constitution and its amendments for correctness, completeness, and quality.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** incorporate any provided context before prompting the user.

## Purpose

Shepherd the amendment process from intent to execution. You are responsible for understanding the requested change, assessing impact, selecting the correct amendment type, updating the constitution, and keeping all agent instruction files in sync without harming existing guidance.

## Workflow Overview

1. Confirm the constitution exists and establish the current baseline.
2. Collaboratively gather amendment details and clarify intent.
3. Analyze the existing constitution and related artifacts to gauge impact.
4. Decide on amendment type and version bump with justification.
5. Apply the amendment using CLI tools, then verify the results manually.
6. Detect and update agent instruction files safely (brownfield-first mindset).
7. Perform a quality review and offer to run validation (user opt-in).
8. Deliver a thorough change log with next steps.

## Step 1: Preflight & Context Check

1. Ensure `oak/constitution.md` exists. If missing, inform the user and stop.
2. Read the constitution to capture:
   - Current version
   - Metadata (author, last amendment date)
   - Recent amendments (especially if they relate to the same section)
   - **Constitution generation approach** (check for decision context markers):
     - Does it document architectural patterns explicitly?
     - Does it specify testing philosophy/strategy?
     - Does it document error handling patterns?
3. Parse `$ARGUMENTS` for amendment details already supplied.
4. Share what you found with the user and highlight any inconsistencies or prerequisites (e.g., constitution not ratified yet, pending validations).

**Decision Context Check**:
- If the constitution was generated with decision context (has sections like "Architectural Pattern: Vertical Slice", "Testing Philosophy", "Error Handling Pattern"), note this.
- If the constitution is old-style (prescriptive without documented decisions), flag a modernization opportunity:
  ```text
  ℹ️  Note: Your constitution appears to be from an earlier version of open-agent-kit.
  Consider running `/oak.constitution-validate` to check for modernization opportunities
  before adding amendments. See docs/constitution-upgrade-guide.md for details.
  ```

## Step 2: Collaborative Requirements Gathering

Engage the user to collect or confirm:
- Summary (concise, under 80 characters)
- Detailed rationale (why now, what problem it solves)
- Amendment type candidates (major/minor/patch) with preliminary reasoning
- Target section(s) and stakeholders/impacts
- Author attribution (if different from user)

Validate user intent by restating the amendment in your own words and asking for confirmation before proceeding.

## Step 2B: Research Phase for Pattern-Based Amendments (Capability-Aware)

**If the amendment introduces new patterns, technologies, or architectural changes, conduct research before proceeding.**

### When to Trigger Research

Scan the amendment summary and rationale for research-worthy topics:

- **New architectural patterns**: "adopting vertical slice", "switching to CQRS", "adding event sourcing"
- **New frameworks/libraries**: "migrating to FastAPI", "adding Playwright for E2E"
- **Technology upgrades**: "upgrading to Python 3.13", "moving to .NET 8"
- **New compliance requirements**: "adding HIPAA compliance", "PCI DSS requirements"

**Reference `features/constitution/templates/decision_points.yaml` section `research_triggers` for the full pattern list.**

### Research Execution (Based on Agent Capabilities)

{% if has_native_web %}
**🌐 NATIVE WEB SEARCH AVAILABLE**

For pattern-introducing amendments:

1. **Research current best practices:**
   ```
   Search: "[pattern] best practices 2025"
   Search: "[pattern] implementation in [tech_stack]"
   Search: "[pattern] common pitfalls"
   ```

2. **Synthesize 3-5 key requirements** the amendment should address

3. **Present findings before finalizing amendment language:**
   ```text
   ═══════════════════════════════════════════════════════════════════
   📚 RESEARCH: [Pattern/Technology] Best Practices
   ═══════════════════════════════════════════════════════════════════

   Before codifying this amendment, here's what current best practices suggest:

   1. **[Key Requirement]** - [Why it matters]
   2. **[Key Requirement]** - [Why it matters]
   3. **[Key Requirement]** - [Why it matters]

   **Suggested amendment additions based on research:**
   - [Specific requirement to add]
   - [Specific requirement to add]

   Would you like to incorporate these into the amendment? (yes/no/customize)
   ═══════════════════════════════════════════════════════════════════
   ```
{% elif has_mcp %}
**🔌 MCP WEB SEARCH AVAILABLE**

Use your configured MCP web-search server. {{ research_strategy }}

For pattern-introducing amendments, query for best practices and present findings before finalizing.
{% else %}
**📚 LIMITED RESEARCH MODE**

When the amendment introduces patterns you're uncertain about:

1. **Flag the uncertainty:**
   ```text
   ⚠️  This amendment introduces [pattern]. I want to ensure the requirements
   reflect current best practices. Can you:
   a) Share any resources/docs you're following for this pattern
   b) Confirm the specific requirements you want to codify
   c) Tell me if general patterns are acceptable
   ```

2. **Note any knowledge limitations** in the final report
{% endif %}

### Skip Research When

- Amendment is clarifying existing language (patch)
- Amendment adjusts thresholds (e.g., coverage 70% → 75%)
- Amendment removes outdated requirements
- User explicitly states they don't need research

## Step 3: Impact Analysis

Investigate how the amendment interacts with the current constitution:
- Locate the relevant section(s) and quote the existing language.
- Identify supporting artifacts (tests, configs, agent instructions) that justify or conflict with the change.
- If the amendment introduces new standards, verify they align with actual codebase practices or planned initiatives (use `rg`, `find`, `jq`, etc., as needed).
- Summarize the findings in a mini report (current state → desired state → evidence). Share with the user for alignment, especially when trade-offs exist.

**Special Considerations for Architectural/Pattern Amendments**:

If the amendment affects architectural sections (patterns, error handling, testing philosophy):

1. **Check if the section exists**:
   - If adding architectural documentation to an old-style constitution, this is a **minor** amendment (new requirement).
   - If modifying existing architectural documentation, assess if it's breaking (major), additive (minor), or clarifying (patch).

2. **Suggest decision context documentation**:
   ```text
   This amendment adds/modifies architectural guidance. Consider also documenting:
   - Architectural Pattern (Vertical Slice, Clean, Layered, etc.)
   - Error Handling Pattern (Result Pattern, exceptions, mixed)
   - Rationale for the chosen approach

   This helps future team members understand the "why" behind the architecture.
   ```

3. **Reality check**:
   - Does the codebase actually follow this pattern?
   - Are there existing implementations that demonstrate it?
   - If not, is this aspirational or does it need adjustment?

## Step 4: Decide Amendment Type & Version Bump

1. Compare the planned change against semantic versioning rules:
   - **Major**: breaks existing requirements or core principles.
   - **Minor**: introduces new requirements without breaking existing ones.
   - **Patch**: clarifies or corrects wording only.
2. Present your recommendation with evidence (e.g., “This adds a new CI requirement → minor bump from 1.2.3 to 1.3.0”).
3. Confirm the choice with the user before applying.
4. Record the current version and the target version in your notes for later reporting.

## Step 5: Apply Amendment via CLI (With Safeguards)

1. Once all fields are ready, run:
   ```bash
   oak constitution add-amendment \
     --summary "{SUMMARY}" \
     --rationale "{RATIONALE}" \
     --type "{TYPE}" \
     --author "{AUTHOR}" \
     {OPTIONAL_ARGS}
   ```
   - Include `--section` and `--impact` only if information is available and agreed upon.
2. After execution:
   - Re-open `oak/constitution.md` and verify:
     - Amendment appended correctly with proper markdown formatting
     - Metadata version and last amendment date updated
     - Amendments section order and dates remain chronological
   - Document any discrepancies and fix manually if needed (e.g., adjust ordering or typo corrections using direct edits).
3. If the CLI fails (invalid type, missing data), interpret the error, adjust inputs, and retry after consulting the user.

## Step 6: Agent Instruction File Alignment (User Approval Required)

1. Detect current agent instruction files:
   ```bash
   oak constitution list-agent-files --json
   ```
   - Identify new agents that may have been added since the last amendment.
2. For each existing file:
   - Read its content, noting current constitution references (version, last updated date, specific guidance).
   - Summarize how the new amendment affects this file (e.g., “Copilot prompt needs version 1.3.0 and mention of new security rule”).
3. Present a synchronization plan to the user covering:
   - Files to update
   - Exact changes (version bump, date, any additional guidance referencing the amendment)
   - Confirmation that backups will be created automatically
4. Only after approval:
   - Preview changes:
     ```bash
     oak constitution update-agent-files --dry-run
     ```
   - Share the preview output (including diffs if practical) and ensure no legacy guidance is being overwritten or duplicated.
   - Apply updates:
     ```bash
     oak constitution update-agent-files
     ```
   - For any newly detected agent file that lacks a constitution reference, confirm the append includes the latest version and relevant amendment context.
5. Capture the outcome: files updated, created, skipped, and backup locations. If conflicts arise, resolve or document manual follow-up instructions.

## Step 7: Quality Review & Optional Validation

1. Perform a self-check:
   - Amendment type and version bump alignment
   - Consistency between constitution metadata and amendment entries
   - Agent instruction files now reference the latest version and highlight the change where appropriate
2. Provide rubric scores (1–5 with justification) for:
   - Clarity & Enforceability of the amendment
   - Alignment with existing practices and artifacts
   - Completeness of downstream updates (agent instructions, documentation)
   - Risk level and mitigation steps
3. Offer to run validation:
   > "Would you like me to run `oak constitution validate --json` now to confirm structural integrity?"
   - If **yes**: execute, interpret the results, fix outstanding issues, or note any low-priority warnings.
   - If **no**: acknowledge validation was deferred and caution the user about potential risks.

## Step 8: Final Report

Summarize the entire process for the user:
- Old version → new version, amendment type, summary, section(s) impacted
- Key excerpts added/updated in the constitution
- Agent instruction file updates (with backup paths and notes about how the references were adjusted)
- Rubric scores, remaining risks, or TODOs
- Validation status (ran vs deferred) and recommended next steps (team review, commit, schedule follow-up validation)
- Any open questions requiring stakeholder input

**If architectural sections were added/modified**:
- Note that these amendments document key decisions for the team
- If this was adding architectural documentation to an old-style constitution, consider this a step toward modernization
- Suggest reviewing `docs/constitution-upgrade-guide.md` for additional modernization opportunities

## Response Expectations

- Maintain a collaborative tone; pause for user confirmation at critical junctures (amendment intent, version bump, agent-file updates, optional validation).
- Reference commands executed and explain the conclusions drawn.
- Protect existing instructions—never overwrite or discard prior content without explicit user agreement.
- Ensure all reported steps are traceable and actionable for both greenfield and brownfield contexts.
