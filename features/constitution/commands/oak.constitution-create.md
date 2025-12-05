---
description: Create an engineering constitution for the project by analyzing the codebase and gathering project information.
handoffs:
  - label: Validate Constitution
    agent: oak.constitution-validate
    prompt: Validate the constitution for correctness, completeness, and quality.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** incorporate any provided context before prompting the user.

## Purpose

Lead the constitution creation process end-to-end. Gather facts, form judgments, and use CLI tools only to support or record your reasoning. You remain accountable for the structure, enforceability, and clarity of the final constitution.

## Workflow Overview

1. Establish shared context with the user (gather facts, confirm assumptions).
2. Investigate the repository and existing guidance; document your findings.
3. **Research technologies and patterns** mentioned by the user (capability-aware).
4. Synthesize requirements section-by-section before writing anything.
5. **Gather explicit user decisions** on testing, code review, documentation, CI/CD, and architecture.
6. Generate a base file via CLI with decision context, then refine with curated content.
7. Update agent instruction files only after summarizing planned changes and receiving confirmation.
8. Perform a quality review and (optionally) run validation with explicit user consent.
9. Deliver a comprehensive report with next steps and open questions.

## Step 0: Project Analysis (Before Any Questions)

**Run the OAK CLI to analyze the project before asking the user anything:**

```bash
oak constitution analyze --json
```

This single command performs comprehensive project analysis:
- Detects test infrastructure (tests/, spec/, __tests__, etc.)
- Detects CI/CD workflows (GitHub Actions, GitLab CI, Azure Pipelines, etc.)
- Detects agent instruction files WITH content analysis (filters out OAK-only content)
- Detects project type files (package.json, pyproject.toml, *.csproj, etc.)
- Detects application code directories (src/, lib/, app/, etc.)
- **Automatically excludes OAK-installed files** (.oak/, oak.* commands)
- Returns a `classification` field: `greenfield`, `brownfield-minimal`, or `brownfield-mature`

**Classification Criteria (handled by the CLI):**
- **Greenfield**: No tests, no CI workflows, no team-created agent instructions → Full consultation needed
- **Brownfield-Minimal**: Some application code, minimal patterns → Ask about aspirations vs reality
- **Brownfield-Mature**: Tests, CI workflows, existing team conventions → Extract and validate existing standards

**Key distinction**: A project with ONLY `.oak/` and `oak.*` files is still **Greenfield** - OAK tooling is not project convention.

## Step 1: Interactive Project Intake

1. Parse `$ARGUMENTS` and extract any project metadata already supplied.

2. **Present the CLI analysis results and ASK USER TO CONFIRM classification:**

   Use the JSON output from `oak constitution analyze --json` to populate this summary:

   ```text
   I've analyzed your project:

   📁 Project artifacts found:
   - Test directories: [from test_infrastructure.directories or "None found"]
   - CI/CD workflows: [from ci_cd.workflows or "None found"]
   - Team agent instructions: [from agent_instructions.files where oak_only=false, or "None found (only OAK commands)"]
   - Application code: [from application_code.directories or "None found"]
   - Project files: [from project_files.files]

   🏷️  Classification: [from classification field - GREENFIELD/BROWNFIELD-MINIMAL/BROWNFIELD-MATURE]

   Is this classification correct? (yes / no / unsure)
   ```

3. **Wait for user confirmation before proceeding.** If user says "no" or "unsure", ask them to describe their project's current state.

4. Ask for missing essentials (only what you still need):
   - Project name
   - Author name (for attribution)
   - Tech stack (primary technologies/languages) - use `project_files` from analysis as hints
   - One-sentence project description

5. **For Brownfield projects ONLY**, summarize what you found:
   ```text
   Existing conventions detected:
   - [Summary of patterns found in agent instructions - files where oak_only=false]
   - [CI/CD checks from ci_cd.workflows]
   - [Test patterns from test_infrastructure.directories]

   I'll incorporate these into the constitution and ask about gaps.
   ```

6. Confirm the collected data back to the user and note any ambiguities or assumptions you will proceed with.

## Step 2: Discovery Strategy (Agent-Led)

Plan your investigation before running commands:
- Identify directories to inspect (`src/`, `tests/`, `.github/workflows/`, `docs/`, etc.).
- List questions you need answered (e.g., “How are services structured?”, “What is the testing coverage goal?”, “Which conventions already exist in agent prompts?”).
- Share the plan with the user; invite clarifications or additional areas of interest.

## Step 3: Evidence Collection

Use CLI tools to gather evidence. Prefer targeted commands over broad scans. Examples:
- `ls`, `tree`, `find` for structure reconnaissance
- `rg`/`grep` for spotting conventions (coverage thresholds, lint configs, ADR mentions)
- `cat`, `python - <<'PY'` scripts, or `jq/yq` to summarize config values
- `oak constitution detect-existing --json` to enumerate agent instruction files (record results, but do not modify yet)

For each discovery session:
- Capture the command, a concise output summary, and the implication (e.g., “CI enforces pytest with coverage 85% → Testing section MUST codify this threshold”).
- When an agent instruction file already exists (e.g., `.github/copilot-instructions.md`), read its content in full, summarize key rules, and tag each with the constitution section it should influence. Treat these artifacts as authoritative for brownfield projects unless the user explicitly asks to change direction.
- Flag conflicting or missing information for user review.

## Step 3B: Research Phase (Capability-Aware)

**Before presenting decision options, conduct research on technologies and patterns mentioned by the user.**

This step ensures the constitution reflects current best practices rather than outdated or generic patterns.

### Research Trigger Detection

Scan user input (project description, tech stack, $ARGUMENTS) for research-worthy topics:

1. **Version-specific patterns**: "Python 3.13", "TypeScript 5.x", "Node 22" → Research current best practices for that version
2. **Framework patterns**: "FastAPI", "Ink CLI", "Next.js 15" → Research idiomatic patterns for that framework
3. **Architecture patterns**: "vertical slice", "hexagonal", "DDD" → Research real-world implementations
4. **Testing frameworks**: "pytest", "Vitest", "Playwright" → Research current testing best practices
5. **Industry/Compliance**: "fintech", "healthcare", "GDPR" → Research regulatory requirements

**Reference `features/constitution/templates/decision_points.yaml` section `research_triggers` for the full pattern list.**

### Capability-Based Research Execution

{% if has_native_web %}
**🌐 NATIVE WEB SEARCH AVAILABLE**

You have built-in web search capabilities. For each research topic identified:

1. **Search for current best practices:**
   ```
   Search: "[technology] best practices 2025"
   Search: "[framework] idiomatic patterns"
   Search: "[pattern] implementation examples [tech_stack]"
   ```

2. **Synthesize findings** into 3-5 actionable patterns per topic

3. **Present findings to user BEFORE relevant decision points**

4. **Document sources** for traceability in the constitution
{% elif has_mcp %}
**🔌 MCP WEB SEARCH AVAILABLE**

Use your configured MCP web-search server. {{ research_strategy }}

For each research topic:
1. Query MCP web-search with: "[topic] best practices 2025"
2. Synthesize top results into actionable patterns
3. Present findings before relevant decisions
{% else %}
**📚 LIMITED RESEARCH MODE**

No web search available. When encountering unfamiliar patterns:
1. Use your training knowledge but note the knowledge cutoff
2. **Ask the user for clarification:**
   ```
   You mentioned "[pattern]". I want to ensure the constitution reflects
   current best practices. Can you:
   a) Describe what you mean by this pattern
   b) Share any resources/docs you're following
   c) Tell me if you'd like me to use general patterns instead
   ```
3. Flag any patterns you're uncertain about in the final report
{% endif %}

### Research Presentation Format

Present research findings BEFORE each relevant decision point:

```text
═══════════════════════════════════════════════════════════════════
📚 RESEARCH FINDINGS: [Topic Title]
═══════════════════════════════════════════════════════════════════

Based on current best practices research, here are the key patterns:

1. **[Pattern Name]**
   - Description: [What it is and why it matters]
   - When to use: [Appropriate contexts]
   - Example: [Brief code/structure example if relevant]

2. **[Pattern Name]**
   - Description: ...
   - When to use: ...

3. **[Pattern Name]**
   ...

**How this affects your constitution decisions:**
→ Testing: [Implication for testing strategy]
→ Architecture: [Implication for architectural decisions]
→ Documentation: [Implication for documentation requirements]

═══════════════════════════════════════════════════════════════════
Would you like me to incorporate these patterns? (yes / no / tell me more)
```

### Research Topics Checklist

Based on user input, mark which topics require research:

| Topic Category | Detected Pattern | Research Status | Findings Summary |
|----------------|------------------|-----------------|------------------|
| Language/Version | [e.g., Python 3.13] | ⬜ Pending / ✅ Done | [Brief summary] |
| Framework | [e.g., FastAPI] | ⬜ Pending / ✅ Done | [Brief summary] |
| Architecture | [e.g., vertical slice] | ⬜ Pending / ✅ Done | [Brief summary] |
| Testing | [e.g., pytest] | ⬜ Pending / ✅ Done | [Brief summary] |
| Compliance | [e.g., none] | ⬜ N/A | - |

**Complete all relevant research BEFORE proceeding to Step 4.**

### Research Integration with Decisions

When presenting decision options in Step 4A, integrate research findings:

```text
=== Testing Strategy Decision ===

📚 Based on my research of [Framework] testing patterns:
- [Framework] projects commonly use [X coverage] as a baseline
- [Specific testing pattern] is recommended for [use case]
- E2E testing with [Tool] is the community standard

With this context, what testing approach fits your project?
[Present standard options, but highlight research-informed recommendations]
```

---

## Step 4: Synthesis Notebook

Compile your findings into a working outline before generating content:
- Create a table (textual is fine) mapping evidence → source (code, config, agent instructions) → constitution section → proposed requirement.
- Note which areas need clarification or additional assumptions.
- Highlight any legacy-agent guidance you plan to reconcile or supersede and seek the user's approval when changes to existing practices are required.
- Review with the user; pause if major decisions require approval.

## Step 4A: Interactive Decision Gathering (NEW - CRITICAL)

**⚠️ NEVER generate a constitution without explicit user decisions on these key areas:**

### Decision Point 1: Testing Strategy

**For Greenfield projects**, present ALL options:

```text
=== Testing Strategy Decision ===

What testing approach fits your project?

1️⃣  Comprehensive Testing
   - Test-first (TDD) development
   - 80%+ code coverage required
   - Unit + Integration + E2E tests mandatory
   ✅ Best for: Production systems, regulated industries, large teams
   ⚠️  Requires: E2E infrastructure, testing discipline, more time

2️⃣  Balanced Testing (RECOMMENDED for most projects)
   - Test-after acceptable
   - 60-80% code coverage target
   - Unit tests required, integration for critical paths
   - E2E tests optional/recommended
   ✅ Best for: Most production applications, standard reliability needs
   ⚠️  Requires: Standard testing frameworks

3️⃣  Pragmatic Testing
   - Tests for critical functionality
   - 40-60% coverage acceptable
   - Focus on unit tests
   - Integration/E2E as needed
   ✅ Best for: Prototypes, MVPs, internal tools, small teams
   ⚠️  Requires: Clear definition of "critical"

4️⃣  Custom
   - Define your own requirements

Which option fits your project? (1-4)
```

**Wait for user response. DO NOT proceed without selection.**

**For Brownfield projects**, present current state FIRST:

```text
=== Testing Strategy Decision ===

I've detected these existing patterns:
- Test directories: tests/
- Current coverage: ~67% (estimated)
- CI runs: pytest
- No E2E tests found

Based on this, I recommend option 2 (Balanced) to match your current practice.
Would you like to:
a) Keep current approach (Balanced - 60-70% coverage)
b) Elevate standards (move to Comprehensive)
c) Relax standards (move to Pragmatic)
d) Custom requirements

Your choice: ___
```

**Follow-up questions based on selection:**

**If Comprehensive or Balanced selected:**
```text
Follow-up questions:

1. What coverage % target should I codify?
   (e.g., 70, 75, 80, 85)
   Your answer: ___

2. Should coverage checks BLOCK CI/CD merges?
   yes = Strict enforcement
   no = Advisory only (track but don't block)
   Your answer: ___

3. [If Comprehensive] Do you have E2E test infrastructure set up?
   (Examples: Playwright, Cypress, Selenium)
   yes/no/planned: ___

4. [If no E2E] Are E2E tests planned for the future?
   yes/no: ___

5. [If Comprehensive] Is TDD (test-first) required?
   yes/no: ___

6. Which integration points require integration tests?
   (comma-separated, or "critical paths")
   Your answer: ___

7. Brief rationale for this testing strategy:
   Your answer: ___
```

**Record all answers in a decision object.**

### Decision Point 2: Code Review Policy

```text
=== Code Review Policy Decision ===

What code review process do you want?

1️⃣  Strict Review
   - All code MUST be reviewed before merge
   - At least 1 approval required
   - No direct commits to main
   - No exceptions (even for hotfixes)
   ✅ Best for: Production systems, regulated environments, distributed teams

2️⃣  Standard Review (RECOMMENDED for most projects)
   - Reviews required before merge
   - At least 1 approval required
   - Hotfixes allowed but must be reviewed post-merge
   ✅ Best for: Most production applications, teams with on-call

3️⃣  Flexible Review
   - Reviews recommended but not enforced
   - Team members may merge without approval
   - Complex changes should be reviewed
   ✅ Best for: Small teams, prototypes, internal tools

4️⃣  Custom

Which option fits your project? (1-3)
```

**Follow-ups for Standard/Strict:**
```text
1. How many reviewers required? (usually 1 or 2)
   Your answer: ___

2. [If Standard] What qualifies as an urgent hotfix?
   Your answer: ___
```

### Decision Point 3: Documentation Level

```text
=== Documentation Requirements Decision ===

How comprehensive should documentation be?

1️⃣  Extensive Documentation
   - All public APIs documented
   - All modules have docstrings
   - ADRs for architectural decisions
   - Maintained README, CHANGELOG, CONTRIBUTING
   ✅ Best for: Open source, large teams, high turnover

2️⃣  Standard Documentation (RECOMMENDED)
   - Public APIs documented
   - Complex logic has comments
   - README + setup instructions
   - ADRs for major decisions (encouraged)
   ✅ Best for: Most projects

3️⃣  Minimal Documentation
   - README with basic setup
   - Critical functions documented
   - Focus on getting started
   ✅ Best for: Prototypes, small teams with high context

4️⃣  Custom

Which option fits your project? (1-3)
```

**Follow-ups for Extensive/Standard:**
```text
1. Are ADRs (Architecture Decision Records) required?
   yes/no: ___

2. Preferred docstring style?
   google/numpy/sphinx/other: ___
```

### Decision Point 4: CI/CD Enforcement

```text
=== CI/CD Enforcement Decision ===

What CI/CD checks should be enforced?

1️⃣  Full Enforcement
   - Linting + type checking + tests + security scans
   - All MUST pass before merge (blocking)
   ✅ Best for: Production systems, mature projects

2️⃣  Standard Enforcement (RECOMMENDED)
   - Linting + tests MUST pass
   - Type checking encouraged
   - Core checks block merges
   ✅ Best for: Most projects, growing codebases

3️⃣  Basic Enforcement
   - Tests SHOULD pass
   - Other checks advisory only (non-blocking)
   ✅ Best for: Early-stage projects, rapid iteration

4️⃣  None (Planning Phase)
   - No CI/CD yet
   ✅ Best for: New projects, pre-CI phase

Which option fits your project? (1-4)
```

**Follow-ups for Full/Standard:**
```text
1. Which checks are required? (select all that apply)
   - tests
   - linting
   - type-checking
   - security
   - coverage
   Your answer: ___

2. CI/CD platform? (optional)
   (GitHub Actions, GitLab CI, CircleCI, etc.)
   Your answer: ___
```

### Decision Point 5: Architectural Patterns (NEW)

```text
=== Architectural Patterns Decision ===

What architectural patterns and principles guide your codebase?

1️⃣  Vertical Slice Architecture
   - Organize by features/use-cases (not technical layers)
   - Each slice contains all layers it needs
   - Features are self-contained and minimally coupled
   📋 Patterns: Feature folders, CQRS-lite, Mediator
   ✅ Best for: Feature-driven development, microservices prep, rapid iteration

2️⃣  Clean Architecture (Onion/Hexagonal)
   - Business logic at center with no external dependencies
   - Dependencies point inward toward domain
   - Ports & Adapters for external integrations
   📋 Patterns: Domain entities, Use cases, Repository, DI
   ✅ Best for: Complex domains, long-lived apps, high testability

3️⃣  Traditional Layered Architecture
   - Horizontal separation by technical concern
   - Presentation → Business → Data access
   - Each layer depends on layer below
   📋 Patterns: Controllers, Services, Repositories, DTOs
   ✅ Best for: Enterprise apps, CRUD-heavy systems

4️⃣  Modular Monolith
   - Single deployment with strong module boundaries
   - Clear module interfaces and contracts
   - Path to eventual microservices if needed
   📋 Patterns: Module APIs, Domain events, Shared kernel
   ✅ Best for: Growing apps, cost-conscious deployments

5️⃣  Pragmatic / Adaptive
   - Mix patterns based on context
   - Simple code for simple features
   - Architecture emerges from needs
   ✅ Best for: Small-medium projects, rapid prototyping

6️⃣  Custom
   - Define your own architectural approach

Which option fits your project? (1-6)
```

**Follow-up questions:**

**For Vertical Slice, Clean Architecture, or Modular Monolith:**
```text
1. What error/result handling pattern do you use?
   a) Result Pattern (Result<T, Error>) - explicit success/failure
   b) Exception-based - use exceptions for all errors
   c) Mixed - Result for domain, exceptions for infrastructure
   d) Other
   Your answer: ___

2. Is dependency injection required?
   yes/no: ___

3. Do you use domain events for decoupling?
   yes/no: ___
```

**For Vertical Slice or Modular Monolith:**
```text
4. How are features/modules organized?
   (e.g., features/{feature-name}/ or modules/{module-name}/)
   Your answer: ___
```

**For Clean Architecture or Layered:**
```text
4. What are your primary layers?
   (e.g., domain, application, infrastructure, presentation)
   Your answer: ___
```

**For all architectures:**
```text
5. Key coding principles? (comma-separated, optional)
   (e.g., SOLID, DRY, YAGNI, KISS)
   Your answer: ___

6. Why does this architecture fit your project?
   Your answer: ___
```

### Decision Confirmation Checkpoint

**After gathering ALL decisions, STOP and present summary:**

```text
==============================================
📋 CONSTITUTION DECISION SUMMARY
==============================================

Based on our conversation, here's what will be codified in your constitution:

## 🧪 Testing Strategy: [Selected Option]
- Approach: [TDD/Test-after]
- Coverage Target: [X%] ([Strict/Advisory])
- Required Tests:
  * Unit tests: [requirements]
  * Integration tests: [requirements]
  * E2E tests: [requirements/planned/optional]
- Rationale: [user's rationale]

## 👥 Code Review: [Selected Option]
- Policy: [Strict/Standard/Flexible]
- Approvals Required: [X]
- Hotfix Handling: [policy]

## 📚 Documentation: [Selected Option]
- Level: [Extensive/Standard/Minimal]
- ADRs: [Required/Optional]
- Docstring Style: [style]
- Requirements: [summary]

## 🔄 CI/CD: [Selected Option]
- Enforcement: [Full/Standard/Basic/None]
- Required Checks: [list]
- Platform: [platform]

## 🏗️  Architecture: [Selected Pattern]
- Pattern: [Vertical Slice/Clean/Layered/Modular Monolith/Pragmatic]
- Error Handling: [Result Pattern/Exceptions/Mixed]
- Dependency Injection: [Required/Optional]
- Domain Events: [Used/Not Used]
- Organization: [feature structure or layer structure]
- Principles: [SOLID, DRY, etc.]
- Rationale: [architectural rationale]

---

This will result in:
- [X] MUST requirements (mandatory)
- [Y] SHOULD recommendations (encouraged)
- [Z] MAY options (flexible)

Overall Philosophy: [summary of approach]

==============================================

⚠️  CRITICAL CHECKPOINT ⚠️

Do these decisions accurately reflect your project needs?

Type your response:
- "yes" → Proceed with constitution generation
- "no" → Cancel and restart decision process
- "revise [topic]" → Modify specific decision (e.g., "revise testing")

Your response: ___
```

**DO NOT PROCEED until user types "yes".**

If user says "revise [topic]", go back to that specific decision point and re-ask.

## Step 5: Generate Base Constitution with Decision Context (CLI Assist)

1. **First, create a decision context JSON file** with all gathered decisions:

   ```bash
   cat > /tmp/decisions.json <<'EOF'
   {
     "testing_strategy": "balanced",
     "coverage_target": 70,
     "coverage_strict": false,
     "has_e2e_infrastructure": false,
     "e2e_planned": true,
     "critical_integration_points": ["authentication", "payment processing"],
     "tdd_required": false,
     "testing_rationale": "Balanced approach for production application without over-engineering",
     "code_review_policy": "standard",
     "num_reviewers": 1,
     "hotfix_definition": "Production-critical bugs affecting users",
     "documentation_level": "standard",
     "adr_required": true,
     "docstring_style": "google",
     "ci_enforcement": "standard",
     "required_checks": ["tests", "linting", "coverage"],
     "ci_platform": "GitHub Actions"
   }
   EOF
   ```

   **Replace values with actual user decisions from Step 4A.**

2. Now run CLI with decision context:
   ```bash
   oak constitution create-file \
     --project-name "{PROJECT_NAME}" \
     --author "{AUTHOR}" \
     --tech-stack "{TECH_STACK}" \
     --description "{PROJECT_DESCRIPTION}" \
     --context-file /tmp/decisions.json
   ```

3. Confirm `oak/constitution.md` now exists; read its contents (`cat oak/constitution.md`).

4. The generated file will now have conditional sections based on decisions - verify they match user expectations.

## Step 6: Review Generated Constitution (Minimal Edits Needed)

**The template now handles most content based on your decisions!**

Review the generated constitution for:

1. **Accuracy Check**: Verify that conditional sections match user decisions:
   - Testing strategy sections reflect chosen approach
   - Coverage requirements match specified target
   - Code review policy matches selected option
   - Documentation level is appropriate
   - CI/CD enforcement is correct

2. **Customization** (only if needed):
   - Add project-specific architectural patterns discovered in Step 3
   - Incorporate brownfield-specific conventions from existing agent instructions
   - Add any domain-specific requirements (e.g., security, compliance)
   - Refine rationale statements to be project-specific

3. **Quality Check**:
   - Ensure normative language is used appropriately (MUST, SHOULD, MAY)
   - Verify at least two actionable statements per section
   - Confirm rationale is provided for non-obvious requirements

**Key Principle**: The constitution should now be ~80% ready based on user decisions. You're refining, not rewriting.

Only make manual edits where:
- Brownfield-specific patterns need to be incorporated
- Project-specific context adds value
- User provided additional requirements beyond the decision framework

## Step 7: Align Agent Instruction Files (Confirmation Required)

1. Summarize proposed changes to agent instruction files (what references you plan to append, which agents are affected, how the new constitution content aligns with existing instructions).
2. Ask the user for permission to proceed. If they decline, document the reason and skip updates.
3. When approved:
   - Preview changes:
     ```bash
     oak constitution update-agent-files --dry-run
     ```
   - Share the preview output, including the diff for each file, and confirm again if there are surprises or potential conflicts with legacy guidance.
   - Before finalizing, ensure the appended reference does not duplicate existing constitution links or contradict the file's current instructions. If needed, adjust the reference (or skip) to avoid regressions.
   - Apply updates:
     ```bash
     oak constitution update-agent-files
     ```
4. Record which files were created, updated, skipped, and the location of backups. For updated files, summarize how the appended reference complements the existing guidance instead of overwriting it.

## Step 8: Quality Review & Optional Validation

1. Conduct your own quality rubric (score 1–5 with justification):
   - Clarity & Enforceability
   - Alignment with observed practices
   - Completeness & Coverage
   - Consistency & Traceability
   - Operational Readiness
2. Outline remaining risks, assumptions, and TODOs.
3. Strongly recommend running validation. Ask explicitly:
   > "Would you like me to run `oak constitution validate --json` now to confirm structural integrity?"
   - If **yes**: execute the command, interpret the output, and note any discrepancies to resolve immediately.
   - If **no**: document that validation was deferred and highlight potential consequences.

## Step 9: Final Report

Provide a structured summary:
- Constitution location, version, status, and notable highlights.
- Section-by-section synopsis referencing evidence.
- Agent instruction file updates (including backups).
- Rubric scores, outstanding issues, and recommended follow-up actions.
- Reminder about validation status (run now vs deferred) and suggested next steps (team review, commit to VCS, schedule amendments process).

## Response Expectations

- Maintain interactive tone; pause for user input at key decision points (testing strategy, code review, documentation, CI/CD, agent file updates, optional validation).
- Cite commands run and the conclusions drawn from them.
- Keep the user informed of assumptions, especially when evidence is missing or contradictory.
- Ensure all instructions you provide to the user are actionable and grounded in discovered facts.

## Critical Rules: No Defaults Without Asking

**⛔ NEVER assume or apply defaults for:**
- Testing requirements (especially E2E tests, coverage targets, TDD vs test-after)
- Code review processes (strict vs flexible)
- Documentation standards (extensive vs minimal)
- CI/CD enforcement (blocking vs advisory)

**✅ ALWAYS ask explicitly when:**
- The user hasn't provided specific requirements
- Brownfield analysis reveals gaps in existing standards
- Multiple reasonable options exist

**The goal is user-driven decisions, not AI-assumed defaults.**
