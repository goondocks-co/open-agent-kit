---
description: Validate the engineering constitution for correctness, completeness, and quality.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

Lead a comprehensive, agent-driven validation of the engineering constitution. Your job is to reason about the document's structure, quality, and enforceability, using CLI tools only to confirm your own analysis.

## Workflow Overview

1. Preflight: locate and load the constitution.
2. Manual constitution review using the structural checklist and quality rubric.
3. Synthesize findings, gaps, and improvement opportunities.
4. (Optional) Run `oak constitution validate --json` to cross-check your conclusions.
5. Facilitate interactive fixes, justifying every change.
6. Re-assess and deliver a final health report with next steps.

## Step 1: Preflight

1. Load any provided user input from `$ARGUMENTS`.
2. Verify that `oak/constitution.md` exists. If missing, respond with:
   - "No constitution found. Please run `/oak.constitution-create` first." and stop.
3. Read the entire constitution so you can reference specific sections and lines. Example command:
   ```bash
   cat oak/constitution.md
   ```
4. If `.constitution.md` is available, review it for the canonical standards to compare against.

## Step 1A: Constitution Version Detection (NEW - Upgrade Detection)

**Detect if this is an "old-style" constitution that could benefit from modernization:**

Check for these indicators of old prescriptive templates:

1. **Hardcoded Testing Requirements** (not decision-driven):
   ```bash
   grep -E "E2E tests MUST run before production deployment" oak/constitution.md
   grep -E "Code coverage MUST be maintained above 80%" oak/constitution.md
   grep -E "Integration tests MUST cover critical user paths" oak/constitution.md
   ```

2. **Missing Decision Context Markers**:
   - No mention of "testing strategy" (comprehensive/balanced/pragmatic)
   - No architectural pattern specified (Vertical Slice, Clean Architecture, etc.)
   - Generic "System Design" section instead of specific architecture
   - No error handling pattern mentioned (Result Pattern, exceptions, etc.)

3. **Reality Misalignment Indicators**:
   ```bash
   # Check if requirements seem too strict for actual project state
   grep -c "MUST" oak/constitution.md  # If >50 MUSTs, might be over-prescriptive
   ```

**If OLD-STYLE constitution detected**, present upgrade opportunity:

```text
🔄 CONSTITUTION MODERNIZATION OPPORTUNITY

I've detected this constitution was created with an earlier version of open-agent-kit that used
prescriptive templates. The current version uses a decision-driven approach that:

✅ Tailors requirements to YOUR project needs
✅ Captures architectural patterns (Vertical Slice, Clean, etc.)  
✅ Documents error handling patterns (Result Pattern, exceptions)
✅ Aligns testing requirements with your actual infrastructure
✅ Makes requirements realistic and achievable

Would you like to:
1. **Continue with standard validation** (checks structure, fixes issues)
2. **Modernize constitution** (extract decisions from current content, regenerate with new template)
3. **Hybrid approach** (validate now, suggest modernization improvements)

Recommended: Option 3 (Hybrid) - I'll validate and suggest specific improvements.

Your choice (1/2/3): ___
```

**Based on user choice:**
- **Option 1**: Continue to Step 2 (standard validation)
- **Option 2**: Jump to Step 1B (Modernization Flow)
- **Option 3**: Continue to Step 2, but flag modernization opportunities during validation

## Step 1B: Constitution Modernization Flow (NEW)

**If user selects "Modernize constitution" (Option 2):**

### Extract Current Decisions

**1. Analyze existing constitution to infer decisions:**

```bash
# Read full constitution
cat oak/constitution.md
```

**Extract and infer:**

**Testing Strategy:**
```text
Analyzing current testing requirements...

Found in constitution:
- "Code coverage MUST be maintained above 80%"
- "Integration tests MUST cover critical user paths"
- "E2E tests MUST run before production deployment"

Inferred decision: COMPREHENSIVE testing strategy
- High coverage requirement (80%)
- All test types mandated
- Strict enforcement

Do you want to KEEP this testing strategy, or ADJUST to match reality?
a) Keep (Comprehensive - 80%+ coverage, all test types required)
b) Adjust to Balanced (60-80% coverage, E2E optional)
c) Adjust to Pragmatic (40-60% coverage, focus on unit tests)

Your answer: ___
```

**Architectural Pattern:**
```text
Analyzing architecture section...

Found in constitution:
- Generic "System Design" section
- Mentions "Services MUST be loosely coupled"
- No specific architectural pattern documented

Current codebase structure:
[Run: ls -la src/ to check actual structure]

Detected structure: [src/services/, src/controllers/, src/models/]
This suggests: Traditional Layered Architecture

Questions:
1. What architectural pattern do you actually use?
   a) Vertical Slice Architecture
   b) Clean Architecture  
   c) Traditional Layered (detected)
   d) Modular Monolith
   e) Pragmatic/Mixed
   f) Other

2. Do you use Result Pattern for error handling?
   yes/no: ___

3. Is dependency injection required?
   yes/no: ___
```

**Code Review & CI/CD:**
```text
Analyzing review and CI/CD requirements...

Found: [extract from existing constitution]
Inferred: [standard/strict/flexible]

Confirm or adjust: ___
```

### Generate Decision Context

After extracting all decisions:

```text
=== EXTRACTED DECISIONS SUMMARY ===

Based on your current constitution and codebase analysis:

Testing: Balanced (adjusted from Comprehensive)
- Coverage: 70% (adjusted from 80% to match reality)
- TDD: Not required
- E2E: Recommended, not mandatory

Architecture: Traditional Layered
- Error Handling: Exceptions
- DI: Yes
- Organization: presentation, business, data

Code Review: Standard
Documentation: Standard  
CI/CD: Standard

These decisions will regenerate your constitution with:
- Same intent as your current constitution
- More realistic requirements
- Better alignment with actual practices
- Captured architectural patterns

Proceed with regeneration? (yes/no/revise): ___
```

### Backup and Regenerate

```bash
# Backup old constitution
cp oak/constitution.md oak/constitution.md.backup-$(date +%Y%m%d-%H%M%S)

# Create decision context
cat > /tmp/extracted-decisions.json <<EOF
{
  "testing_strategy": "balanced",
  "coverage_target": 70,
  ... [all extracted decisions]
}
EOF

# Regenerate with decision context
oak constitution create-file \
  --project-name "$(grep '# .*Constitution' oak/constitution.md | sed 's/# //;s/ Constitution//')" \
  --author "$(grep 'Author:' oak/constitution.md | sed 's/.*Author: //')" \
  --context-file /tmp/extracted-decisions.json \
  --force  # Allow overwrite

echo "✅ Constitution modernized!"
echo "📁 Backup saved: oak/constitution.md.backup-[timestamp]"
echo "📋 Decision context: /tmp/extracted-decisions.json"
```

## Step 2: Manual Constitution Review (Primary Analysis)

Perform your own evaluation before invoking any CLI validation.

### 2A. Structural Checklist

- Confirm every required section from `CONSTITUTION_REQUIRED_SECTIONS` appears exactly once.
- Ensure section order aligns with project norms (Metadata → Principles → Architecture → Code Standards → Testing → Documentation → Governance).
- Flag any empty or placeholder sections; note missing rationale.

### 2B. Metadata Integrity

- For each field in `CONSTITUTION_REQUIRED_METADATA`, verify it is present, non-empty, and meaningful.
- Confirm semantic version format (`major.minor.patch`) and that ratification/amendment dates follow ISO `YYYY-MM-DD`.
- Check that the metadata version matches the latest amendment entry, if amendments exist.

### 2C. Token & Language Scan

- Ensure no template tokens from `CONSTITUTION_TOKENS` remain.
- Identify non-declarative language (e.g., “should”, “could”). Recommend replacements (`MUST`, `SHOULD`, `MAY`) with rationale.

### 2D. Quality Rubric (Score 1-5 each and justify)

1. **Clarity & Enforceability**: Are requirements explicit, testable, and free of ambiguity?
2. **Alignment with Standards**: Does the document reflect `.constitution.md` guidance and organizational practices?
3. **Completeness & Coverage**: Are policies thorough, with rationale and edge cases addressed?
4. **Consistency & Traceability**: Do sections avoid contradictions? Are versioning and amendments coherent?
5. **Operational Readiness**: Can teams act on the policies today? Note tooling/process gaps.

For each dimension, cite evidence (section references, quotes, observed gaps) and record a score with explanation.

### 2E. Opportunity Assessment

List high-impact improvements (e.g., missing metrics, vague policies, outdated roles). Separate mandatory fixes from recommendations.

## Step 2F: Reality Alignment Check (Enhanced for Modernization)

After structural validation, check if requirements match project reality.

### Initial Project Analysis

**Start with the OAK CLI to get a comprehensive project overview:**

```bash
oak constitution analyze --json
```

This returns structured data about:
- `test_infrastructure` - Test directories found (tests/, spec/, etc.)
- `ci_cd` - CI/CD workflow files detected
- `agent_instructions` - Agent instruction files with content analysis
- `project_files` - Project type files (package.json, pyproject.toml, etc.)
- `application_code` - Source code directories
- `classification` - greenfield/brownfield-minimal/brownfield-mature

**Use this data to understand:**
- What testing infrastructure exists
- What CI/CD is configured
- The overall project maturity level

### Deeper Validation (Stack-Specific)

After the initial analysis, use targeted commands to verify specific constitution requirements:

**Use your knowledge to interpret findings:**
- Identify the tech stack from `project_files` in the analysis
- Understand what testing tools are appropriate for this stack
- Compare constitution requirements with actual capabilities
- Flag realistic vs aspirational requirements

**If user selected "Hybrid approach" in Step 1A**, also flag modernization opportunities.

### Modernization Opportunity Flags (for Hybrid approach)

When checking reality alignment, also identify missing decision context:

**Missing Architectural Pattern:**
```text
📊 MODERNIZATION OPPORTUNITY: Architecture Not Documented

Your constitution has a generic "System Design" section but doesn't document:
- Specific architectural pattern (Vertical Slice, Clean, Layered, etc.)
- Error handling approach (Result Pattern, exceptions, mixed)
- Whether dependency injection is required
- Coding principles (SOLID, DRY, etc.)

Recommendation: Add Architecture decision to capture your actual patterns.
This helps new team members understand your architectural philosophy.

Would you like me to help document this? (yes/later/skip)
```

**Generic Testing Requirements:**
```text
📊 MODERNIZATION OPPORTUNITY: Testing Strategy Not Explicit

Your constitution has testing requirements but doesn't specify:
- Testing philosophy (Comprehensive/Balanced/Pragmatic)
- Whether TDD is required or test-after is acceptable
- Rationale for your coverage target
- Whether E2E is truly required or aspirational

Recommendation: Document your testing strategy explicitly to set clear expectations.

Would you like me to help clarify this? (yes/later/skip)
```

### Coverage Reality Check

If constitution requires specific coverage, use stack-appropriate commands:

```bash
# Python: pytest with coverage
pytest --cov --cov-report=term 2>/dev/null | grep "TOTAL"

# .NET: Check for coverage reports
find . -name "coverage.cobertura.xml" -o -name "*.coverage" 2>/dev/null

# JS/TS: Check coverage directory or run npm/yarn test with coverage
cat coverage/lcov-report/index.html 2>/dev/null | grep -o ">[0-9]*\.[0-9]*%"
```

**If constitution requires 80% but current is 45%:**
```text
⚠️  ALIGNMENT ISSUE: Coverage Gap

Constitution requires: 80% coverage (strict enforcement)
Current coverage: 45%
Gap: 35 percentage points

This is a significant gap. Options:
1. **Aspirational**: Add note "Working toward 80% coverage goal" with timeline
2. **Realistic**: Lower requirement to achievable target (e.g., "Maintain 50%, target 65%")
3. **Phased**: "New code must meet 70%, existing code exempt until refactor"
4. **Correct as-is**: Team commits to achieving 80% (provide plan)

Which approach fits your situation?
```

### E2E Test Reality Check

If constitution requires E2E tests:
```bash
# Check for E2E test infrastructure (stack-agnostic)
find . -name "*e2e*" -o -name "*integration*" 2>/dev/null | grep -i test | head -10

# Check for E2E-specific tools (use your knowledge of different stacks)
# JS/TS: playwright.config.*, cypress.json, cypress/, e2e/
# .NET: Selenium configs, SpecFlow, TestResults/
# Python: pytest with selenium, behave/
ls -la playwright.config.* cypress.json docker-compose*.yml 2>/dev/null
```

**If no E2E infrastructure found but constitution requires E2E:**
```text
⚠️  ALIGNMENT ISSUE: E2E Infrastructure Missing

Constitution requires: E2E tests for key user flows
Infrastructure found: None
Test frameworks detected: None

Recommendation: Change requirement to reflect reality:

Current (misaligned):
"E2E tests MUST run before production deployment"

Suggested (aligned):
"E2E tests SHOULD be implemented when infrastructure is ready (Q2 2024 target)"

OR if E2E is truly needed now:
"E2E infrastructure MUST be established by [date]. Until then, manual testing required."

Apply this change? (yes/no)
```

### CI/CD Reality Check

If constitution mandates CI/CD enforcement:
```bash
# Detect CI/CD files (stack-agnostic)
ls -la .github/workflows/ .gitlab-ci.yml .circleci/ azure-pipelines.yml 2>/dev/null

# Check CI configuration for enforcement (adapt to stack):
# Python: grep for pytest, coverage, mypy, ruff, black
# .NET: grep for dotnet test, coverage, analyzers
# JS/TS: grep for jest, vitest, eslint, prettier
cat .github/workflows/*.yml .gitlab-ci.yml azure-pipelines.yml 2>/dev/null | grep -E "test|coverage|lint" -A 2
```

**Compare with constitution requirements:**
```text
Constitution says: "Coverage checks MUST pass in CI/CD"
CI configuration: No coverage check found in workflows

⚠️  ALIGNMENT ISSUE: CI doesn't enforce what constitution requires

Options:
1. **Add CI check**: Implement coverage gate in CI/CD
2. **Update constitution**: Change MUST to SHOULD (advisory only)
3. **Plan implementation**: Add "Coverage enforcement planned for [date]"

Which approach do you prefer?
```

### TDD Reality Check

If constitution requires TDD:
```bash
# Check git history for test-first patterns
git log --all --oneline --grep="test" --grep="TDD" -i | head -10
# Check if tests exist for recent features
recent_files=$(git diff --name-only HEAD~10 HEAD | grep -v test)
```

**If constitution requires TDD but evidence suggests test-after:**
```text
⚠️  ALIGNMENT ISSUE: TDD Requirement vs Practice

Constitution requires: "All functions MUST have unit tests written before implementation (TDD)"
Evidence: Recent commits show features implemented before tests

This suggests TDD isn't current practice. Options:
1. **Reflect reality**: Change to "Tests MUST be written, may be after implementation"
2. **Mandate change**: Keep TDD requirement, team must adapt workflow
3. **Aspirational**: "TDD is encouraged and will be adopted over time"

Which reflects your team's commitment?
```

### Code Review Reality Check

If constitution has review requirements:
```bash
# Check branch protection rules (if on GitHub)
gh repo view --json branchProtectionRules 2>/dev/null || echo "Can't check programmatically"
# Check recent PRs for review patterns
gh pr list --state merged --limit 20 --json reviews 2>/dev/null
```

**If reviews required but not enforced:**
```text
⚠️  ALIGNMENT ISSUE: Review Policy vs Enforcement

Constitution requires: "All PRs MUST be reviewed before merge"
Branch protection: Not configured (direct pushes allowed)

Your constitution won't be effective without enforcement. Options:
1. **Enable branch protection**: Configure in GitHub/GitLab settings
2. **Soften requirement**: Change to "PRs SHOULD be reviewed"
3. **Document gap**: "Review required per policy (enforcement pending)"

Recommended: Enable branch protection now to match constitution
```

## Step 3: Findings Summary

Prepare a structured summary including:
- Structural issues (missing/empty sections, metadata gaps, tokens).
- Language/style concerns with suggested declarative rewrites.
- Rubric scores with reasoning.
- **Reality alignment issues** (NEW: gaps between requirements and actual project state).
- Outstanding risks or contradictions.
- Questions that require human clarification.

## Step 4: Optional CLI Cross-Check

If you need supporting data, run the CLI validator:
```bash
oak constitution validate --json
```
Use the JSON output to corroborate or refine your findings. Never rely on it as the primary assessment—highlight any discrepancies between your review and the CLI results.

When referencing CLI findings:
- Mention category, priority, and location.
- Explain whether it aligns with your manual assessment or exposes new issues.

## Step 5: Interactive Fix Mode

Work issue-by-issue from highest to lowest priority (your judgment first, then CLI priorities if applicable).

For each issue:
1. Present the problem with context (quote the relevant text, cite section/line).
2. Explain the risk or impact.
3. Propose at least two options (agent-generated content, guided edits, or defer).
4. When the user selects an option, describe exactly how you will modify the constitution and why it resolves the issue.
5. Apply the change, showing the updated snippet.
6. Confirm the fix and note any follow-up actions.

Require an explicit explanation-before-change for every modification. If the user skips an issue, document the rationale and residual risk.

## Step 6: Re-Assessment & Final Report

1. After all fixes, re-run your manual checklist and rubric. Only then (optionally) re-run the CLI validator to confirm alignment.
2. Summarize improvements: number of issues resolved, rubric score changes, remaining concerns.
3. Provide a clear status recommendation:
   - **Valid**: ready for adoption
   - **Conditionally Valid**: acceptable with noted follow-ups
   - **Invalid**: critical issues remain
4. **If modernization opportunities were identified**, summarize them:
   ```text
   📊 MODERNIZATION OPPORTUNITIES IDENTIFIED
   
   Your constitution is valid but could benefit from these modern features:
   
   1. ⚠️  Architectural patterns not documented
      - Add: Specific architecture (Vertical Slice, Clean, Layered, etc.)
      - Add: Error handling pattern (Result Pattern, exceptions)
      - Impact: Better onboarding, clearer architectural philosophy
   
   2. ⚠️  Testing strategy not explicit
      - Add: Testing philosophy (Comprehensive/Balanced/Pragmatic)
      - Add: Rationale for coverage target
      - Impact: Clearer expectations, better alignment with reality
   
   3. ✅ Reality alignment checked
      - Coverage target adjusted to match actual capability
      - E2E requirement adjusted to reflect infrastructure
   
   Next Steps for Modernization:
   - Option A: Full modernization via `/oak.constitution-validate` (select Option 2)
   - Option B: Incremental improvements via amendments
   - Option C: Continue with current constitution (defer modernization)
   
   Recommendation: Option B (Incremental) - Add architectural decisions via amendment,
   keeping most of your current constitution intact.
   ```

5. List next steps (e.g., stakeholder review, additional metrics, process rollouts).
6. Encourage the user to review the diff in version control and document amendments.

## Step 7: Incremental Modernization Guide (NEW)

**If user wants incremental modernization instead of full regeneration:**

Provide specific amendment recommendations:

```text
=== INCREMENTAL MODERNIZATION PLAN ===

Instead of regenerating your entire constitution, you can modernize it incrementally
by adding these sections via amendments:

**Amendment 1: Document Architectural Pattern**

Run: `/oak.constitution-amend`

Add a new subsection to Architecture:

### Architectural Pattern: [Your Pattern]

This project follows **[Vertical Slice/Clean/Layered]** architecture.

**Core Principles:**
- [Document your actual architectural principles]

**Requirements:**
- [Document your actual requirements]

**Rationale:**
[Why this architecture fits your project]

---

**Amendment 2: Add Error Handling Pattern**

Add to Architecture section:

### Error Handling Pattern

This project uses **[Result Pattern/Exceptions/Mixed]** for error handling.

**Requirements:**
- [Document your error handling requirements]

**Rationale:**
[Why this approach fits your project]

---

**Amendment 3: Clarify Testing Strategy**

Update Testing section to add:

### Testing Philosophy

This project follows a **[Comprehensive/Balanced/Pragmatic]** testing approach.

**Rationale:**
[Why this testing strategy fits your project - reference infrastructure, team size, etc.]

---

These amendments preserve your current constitution while adding modern decision context.
Each can be done independently at your own pace.
```

## Response Expectations

- Lead with findings, then actions, then summary.
- Reference sections and quotes directly for transparency.
- Maintain declarative tone; avoid vague advice.
- Always distinguish between your assessment and CLI output.
- Keep a running log of decisions, scores, and remaining risks for auditability.

## Guidelines for Fixing

### Empty Sections
**Generate based on codebase analysis:**
- Scan for relevant files and patterns
- Create realistic, enforceable requirements
- Use declarative language (MUST, SHALL)
- Include rationale for each requirement

### Non-declarative Language
**Replacement strategy:**
- "should" → "MUST" (for requirements) or "SHOULD" (for recommendations)
- "could" → "MAY" (for options) or remove if not a requirement
- "might" → Rephrase to be definitive
- "maybe" → Remove or make specific

### Date Formats
**Always use ISO 8601:**
- Convert MM/DD/YYYY → YYYY-MM-DD
- Convert DD/MM/YYYY → YYYY-MM-DD
- Validate format: `YYYY-MM-DD`

### Template Tokens
**Replace with actual values:**
- `{{PROJECT_NAME}}` → Get from config or repo name
- `{{TECH_STACK}}` → Get from codebase analysis
- `{{AUTHOR}}` → Get from git config or ask user
- Never leave tokens unreplaced

## Important Notes

- **Interactive mode is default** - Always ask before applying fixes
- **Explain changes** - Tell user what was changed and why
- **Preserve content** - Never delete sections, only add or modify
- **Use CLI tools** - Don't manually parse/write files, use CLI commands
- **Be thorough** - Check every issue, don't skip without user consent
- **Validate after fixes** - Always re-run validation to confirm

## Example Session

```
Running constitution validation...

❌ HIGH Priority Issues (3 found)
  1. Section "Testing" is empty
  2. Missing section "Governance"
  3. Token "{{PROJECT_NAME}}" not replaced

⚠️  MEDIUM Priority Issues (2 found)
  1. Invalid date format "11/15/2025"
  2. Non-declarative language "should" in Principles

ℹ️  LOW Priority Issues (1 found)
  1. Ambiguous requirement in Code Standards

Starting interactive fix mode...

[Proceed through each issue with options and fixes]

Validation complete! Fixed 6/6 issues.
Constitution is now valid ✓
```
