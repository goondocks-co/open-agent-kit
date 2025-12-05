---
description: Prepare implementation context for a tracked issue (issue/task/story).
handoffs:
  - label: Validate Plan
    agent: oak.plan-validate
    prompt: Validate the plan for this issue and its related issues for accuracy and completeness. 
---

## User Input

```text
$ARGUMENTS
```

Treat the text supplied after the command as canonical context for this work session. It should mention the provider (Azure DevOps or GitHub) and the issue identifier. Ask clarifying questions if anything is ambiguous.

## Interaction Guidelines

**Always ask when:**
- Provider or issue ID is ambiguous or missing
- User's intent about capturing extra context is unclear
- Issue has multiple acceptance criteria interpretations

**Proceed without asking when:**
- Provider and ID are clearly stated in $ARGUMENTS
- Context seems complete and unambiguous
- Standard workflow applies

**How to ask effectively:**
- Present specific options when clarifying (e.g., "Is this ADO ticket 12345 or GitHub issue #12345?")
- Explain what information is needed and why
- Suggest a default based on context

## Responsibilities

1. Confirm provider + issue identifier (this becomes the **focus issue**).
2. Fetch the focus issue and all its related items (parents, children, dependencies) for additional context.
3. Create local artifacts under `oak/plan/{name}/issue/` with related items in `related/` subdirectory.
4. Prepare an implementation branch prefixed with the focus issue ID.
5. Read the project constitution to understand standards and requirements.
6. Explore the codebase to find relevant patterns and test strategies.
7. Summarize what happened and propose next actions.
8. Clarify that these utilities only scaffold context—the agent must still inspect the actual repo (via commands and tools you have access to) to learn idiomatic patterns and design the implementation.

## Issue Fetching Strategy

{% if has_background_agents %}
### Parallel Issue Fetching with Background Agents

**For issues with many related items, parallelize the fetching process.**

When the focus issue has 3+ related items (parents, children, dependencies):

**Parallel Fetch Workflow:**

```text
┌─────────────────────────────────────────────────────┐
│ Issue Fetch Orchestrator                             │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  Focus   │  │  Parent  │  │  Child   │          │
│  │  Issue   │  │  Issues  │  │  Issues  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│       │              │             │                │
│       └──────────────┴─────────────┘                │
│                    │                                │
│          Merge Context Summaries                    │
└─────────────────────────────────────────────────────┘
```

**Benefits of parallel fetching:**
- Faster context gathering for complex issue hierarchies
- Reduced wait time for large epics with many children
- Parallel summary generation for related items

**Subagent Fetch Template:**

```markdown
# Related Issue Fetch Assignment

## Context
- **Focus Issue:** <provider> #<focus-id>
- **Output Directory:** oak/plan/<name>/issue/related/<id>/

## Your Assignment

Fetch and summarize related issue: **<provider> #<related-id>**

**Relationship:** <parent|child|dependency|sibling>

## Deliverables

1. Fetch issue details via CLI: `oak plan issue --fetch-only <id>`
2. Create summary.md with:
   - Title, description, acceptance criteria
   - Relationship context to focus issue
   - Relevant implementation hints

## Output

Return summary and any blockers encountered.
```

{% else %}
### Sequential Issue Fetching

Fetch focus issue first, then related items in order of relevance (parents before children, dependencies before siblings).
{% endif %}

{% if has_native_web %}
### Web-Enriched Issue Context

When issues reference external resources:
- Fetch linked documentation or specs
- Check for related discussions or decisions
- Validate external API or service references
{% endif %}

{% if has_mcp %}
### MCP-Enhanced Fetching

Leverage MCP tools for richer context:
- **Issue provider tools**: Direct API access for detailed metadata
- **Document fetch**: Retrieve linked documents and attachments
- **Search tools**: Find related issues not explicitly linked
{% endif %}

**Understanding the Focus Issue:**

- The issue you pass to this command is the **focus** of your implementation.
- It might be a Story with child Tasks, or a Task with a parent Story and Epic - the focus is what you're implementing.
- All hierarchical relationships (parents, children, siblings, dependencies) are fetched automatically as **context**.
- The directory structure is always based on the **focus issue**, with related items stored in `related/{id}/` subdirectories.
- The plan.md includes sections for Parent, Child, and Related Issues (Context) so you understand the full scope.
- Example: If you pass Task #456 (which has parent Story #123), the directory is `oak/plan/{name}/issue/` with the parent story context at `oak/plan/{name}/issue/related/123/summary.md`.

## Prerequisites

Before executing this command, ensure these prerequisites are met **in order**:

1. **Constitution Exists** (REQUIRED): The project must have a constitution at `oak/constitution.md`.
   - If missing, **STOP** and instruct the user: "Please run `/oak.constitution-create` first to establish your project's engineering standards."
   - The constitution is foundational - all work planning references it for standards compliance.
   - **This is checked first** by the CLI before any other prerequisites.

2. **Issue Provider Configuration** (REQUIRED): The user must have configured their issue provider.
   - If not configured, **STOP** and instruct the user: "Please run `oak config` to configure your issue provider (Azure DevOps or GitHub Issues) before creating an issue plan."
   - **NEVER run `oak config` on behalf of the user** - it requires interactive setup in the terminal.
   - To check configuration status: Read `.oak/config.yaml` directly (e.g., `cat .oak/config.yaml`) and look for `issue` section with provider details.
   - Alternatively, you can run `oak config issue-provider show` (non-interactive) to see formatted config output.

3. **Issue ID** (REQUIRED or Opt-In): You must have an issue identifier to fetch from the provider.
   - If the user hasn't provided one, **STOP** and ask: "What is the issue ID? (e.g., Azure DevOps work item #12345 or GitHub issue #42)"
   - If they don't have an issue ID yet, ask: "Would you like to proceed without linking to a tracked issue? If so, please provide additional details about what you're implementing."

## Workflow

1. **Prerequisite Check**
   - Parse `$ARGUMENTS` for provider hints (e.g., "ADO 12345" or "GitHub #42").
   - If issue ID is missing, **ask the user** for it before proceeding.
   - If they want to proceed without one, they must **explicitly opt in** and provide additional context.
   - **Optional**: Run `oak constitution check` to verify the constitution exists before attempting plan creation.

2. **Validate Configuration**
   - Check if issue provider is configured by attempting to run the plan command.
   - If the CLI reports configuration issues, **instruct the user**: "Your issue provider is not configured. Please run `oak config` in your terminal to set up Azure DevOps or GitHub integration."
   - **Wait for the user to complete setup** - do not continue until they confirm it's done.
   - To verify configuration yourself: Read `.oak/config.yaml` (e.g., `cat .oak/config.yaml`) or run `oak config issue-provider show`.

3. **Execute Plan Command**
   - Once prerequisites are met, run `oak plan issue <NAME> --id <ISSUE_ID> [--provider <key>]` via the shell.
   - The CLI will:
     - Validate prerequisites (constitution, issue provider config)
     - Fetch the issue from the provider
     - Write artifacts to `oak/plan/{name}/issue/`:
       - `summary.md` - Agent-friendly summary with all issue details
       - `plan.md` - Implementation plan
     - Create/switch to an implementation branch prefixed with the issue ID

4. **Verify Branch**

   After running `oak plan issue`, verify you're on the correct implementation branch:

   ```bash
   # Check current branch
   git branch --show-current
   ```

   The branch name is saved in the plan context and will be used consistently across all plan operations (issue/validate/implement). If you need to switch branches for any reason, make sure to return to the plan's branch before continuing.

5. **Discover Artifacts**

   After running `oak plan issue`, use `oak plan show <NAME>` to discover:
   - All artifact paths (context, plan, codebase)
   - The saved branch name for this issue
   - Related issues (parents, children, etc.)
   - JSON output available with `--json` flag for parsing

   The CLI generates these key files:

   **`summary.md`**
   - Issue title, description, acceptance criteria from the provider
   - Labels/tags, assigned user, status, priority, effort
   - Type-specific fields (test steps for Test Cases, repro steps for Bugs)
   - Related issues with simplified relationship types
   - Clean, agent-friendly markdown format optimized for LLM consumption
   - Use this as your primary source for requirements understanding

   **`plan.md`**
   - Structured implementation plan with sections:
     - **Objectives**: What success looks like
     - **Approach**: Technical strategy and design decisions
     - **Tasks**: Step-by-step work breakdown
     - **Risks & Mitigations**: Known blockers and solutions
     - **Definition of Done**: Completion criteria and verification steps
   - Fill in any PENDING sections before implementing
   - This becomes your implementation roadmap


   **Related Items** (discovered via `oak plan show`)
   - Run `oak plan show <NAME>` to see all related issues with their paths
   - Context for parent issues (epics, stories above the focus)
   - Context for child issues (tasks, sub-tasks below the focus)
   - Context for other related items (dependencies, pull requests, etc.)
   - Helps understand the bigger picture and downstream impacts
   - All related items are for **context only** - the focus issue drives the implementation

6. **Read the Constitution**

   Open `oak/constitution.md` and identify rules relevant to this work:

   ```bash
   # Read the full constitution
   cat oak/constitution.md

   # Or search for specific guidance
   rg "MUST" oak/constitution.md
      rg "testing" oak/constitution.md -i
   ```

7. **Systematic Codebase Exploration**
   rg "documentation" oak/constitution.md -i
   ```

   **Extract and apply:**
   - **Code Standards**: Type hints, docstrings, naming conventions, formatting rules
   - **Testing Requirements**: Coverage expectations, test patterns, test organization
   - **Documentation Standards**: What requires docs, format guidelines, examples
   - **Review Protocols**: Approval requirements, validation steps, merge criteria

   **Update plan.md** to explicitly reference applicable constitution rules in your approach section.

7. **Systematic Codebase Exploration**

   **Step 1: Find Similar Features**

   ```bash
   # Search for related functionality
   rg "keyword_from_issue" src/
   rg "class.*Service" src/           # If implementing a service
   rg "class.*Command" src/commands/  # If implementing a command
   rg "def test_" tests/               # Find test patterns
   ```

   **Step 2: Identify Patterns**
   - Look at 2-3 similar implementations
   - Note common patterns: error handling, logging, validation, type hints
   - Check how they're tested (unit tests, integration tests, fixtures)
   - Review recent changes: `git log -p --since="1 month ago" path/to/relevant/`
   - Check imports and dependencies used by similar code

   **Step 3: Understand Testing Strategy**

   ```bash
   # Find test files for similar features
   find tests/ -name "*similar_feature*"

   # See how services are tested
   rg "class Test.*Service" tests/

   # Check test fixtures and mocking patterns
   rg "@pytest.fixture" tests/
   rg "Mock" tests/
   ```

   **Step 4: Document Findings**
   - Update `plan.md` with patterns you found
   - Note file/module naming conventions
   - Document test strategy (where tests go, what patterns to follow)
   - Reference specific files/functions as examples

8. **Identify Unknowns and Questions**

   Before creating the detailed plan, identify what you don't know yet:

   - **Technical unknowns**: Libraries, APIs, or technologies you need to research
   - **Integration questions**: How does this connect with existing systems?
   - **Pattern questions**: Which approach best fits the codebase?
   - **Constitution gaps**: Are there constitution rules that need clarification?

   **For each unknown:**
   - Mark it as **NEEDS CLARIFICATION** in your notes
   - Ask the user directly if it's something they can answer
   - Document what research is needed if it requires investigation

   **Examples:**
   ```text
   NEEDS CLARIFICATION: Which authentication library is used for API calls?
   → Ask user or search codebase: rg "auth" src/

   NEEDS CLARIFICATION: Should validation use Pydantic or custom validators?
   → Check existing patterns: rg "BaseModel" src/

   NEEDS CLARIFICATION: Where do shared utilities live?
   → Constitution says "centralized utilities" - check constitution for path
   ```

   **Resolve before proceeding**: Don't write the full plan until all NEEDS CLARIFICATION items are resolved.

9. **Constitution Compliance Check & Test Strategy Extraction**

   Create a Constitution Check section in your plan analysis:

   **Load constitution rules:**
   ```bash
   # Extract MUST rules
   rg "MUST" oak/constitution.md

   # Extract SHOULD rules
   rg "SHOULD" oak/constitution.md

   # Find relevant sections
   rg "testing|documentation|code standards" oak/constitution.md -i

   # Extract test strategy specifically
   rg "test.*first|TDD|coverage|unit.*test|integration.*test" oak/constitution.md -i
   ```

   **Extract test strategy from constitution:**
   - **Test timing**: Does constitution require test-first (TDD) or allow test-after?
   - **Coverage requirements**: What coverage % is required? Are there exemptions?
   - **Test organization**: Where do tests live? What naming conventions?
   - **Test types**: Are unit tests required? Integration tests? E2E tests?
   - **Flexibility**: Is testing strictly required or recommended/optional?

   **Check compliance:**
   - ✅ **PASS**: Implementation approach follows all MUST rules
   - ⚠️ **NEEDS ATTENTION**: SHOULD rule requires consideration
   - ❌ **VIOLATION**: MUST rule cannot be met (requires justification)

   **Document in plan.md:**
   ```markdown
   ## Constitution Compliance

   ### Test Strategy (from constitution)
   - **Timing**: Test-after allowed (not strict TDD)
   - **Coverage**: 80% minimum required for new code
   - **Required**: Unit tests for all public functions
   - **Optional**: Integration tests recommended for workflows
   - **Organization**: Tests mirror src/ structure in tests/

   ### MUST Rules
   - ✅ All public functions have type hints (constitution Section 4.1)
   - ✅ Tests required for new functionality (constitution Section 7.1)
   - ✅ No magic strings - use constants (constitution Section 4.4)

   ### SHOULD Rules
   - ⚠️ Consider extracting helper to shared utilities (constitution Section 4.2)
     - Approach: Will add to existing utils module per constitution pattern

   ### Violations (if any)
   - ❌ None - all MUST rules satisfied
   ```

   **Use test strategy for task planning**: Apply the constitution's test requirements when creating Phase 3 (Testing) tasks. If constitution is strict, make all tests explicit. If flexible, suggest optional tests.

10. **Create Detailed Implementation Plan with Structured Tasks**

    Open and edit `oak/plan/<name>/issue/plan.md` to fill in the details:

    **A. Plan Sections (Standard)**

    - **Objectives**: Refined based on acceptance criteria and constitution
    - **Constitution Check**: Document compliance with MUST/SHOULD rules (from step 9)
    - **Technical Context**:
      - Technologies/libraries to use
      - Integration points
      - **All NEEDS CLARIFICATION resolved**
    - **Approach**:
      - Which patterns you'll follow (reference specific files)
      - Where new code will live (module, class, function names)
      - How you'll handle edge cases
      - Constitution rules you're applying

    **B. Task Breakdown (Structured Phases)**

    **Leverage issue data to create concrete, actionable tasks:**

    Use this phased structure (adjust based on constitution's test strategy):

    **Phase 1: Setup & Investigation**
    ```markdown
    - [ ] Setup: Review parent issue context (if exists) from related/{parent-id}/context-summary.md
    - [ ] Setup: Identify affected modules/files from codebase exploration
    - [ ] Setup: Install/configure any new dependencies per constitution
    - [ ] Setup: Create feature branch (already done by CLI)
    ```

    **Phase 2: Core Implementation** (map to acceptance criteria)
    ```markdown
    # For each acceptance criterion from context-summary.md, create specific task(s)
    - [ ] Implement AC1: [Criterion 1 from context-summary.md]
      - File: [specific file path]
      - Function/Class: [specific names]
      - Pattern: [reference to similar implementation found in step 7]
    - [ ] Implement AC2: [Criterion 2 from context-summary.md]
      - File: [specific file path]
      - Function/Class: [specific names]
      - Pattern: [reference to similar implementation]
    # Continue for all acceptance criteria
    ```

    **Phase 3: Testing** (constitution-driven, leverage issue test cases)
    ```markdown
    # Test phase structure depends on constitution guidance:
    # - If constitution requires test-first (TDD): Phase 3 becomes Phase 2 (tests before implementation)
    # - If constitution requires high coverage: Create explicit tasks for each test scenario
    # - If constitution is flexible: Make testing optional but recommended

    # If issue includes test cases, convert them to tasks:
    - [ ] Test: [Test case 1 title from issue]
      - Test file: [specific test file path per constitution structure]
      - Test function: test_[specific_name]
      - Covers: [acceptance criteria reference]
    - [ ] Test: [Test case 2 title from issue]
      - Test file: [specific test file path per constitution structure]
      - Test function: test_[specific_name]
      - Covers: [acceptance criteria reference]

    # If constitution requires comprehensive testing, add:
    - [ ] Test: Unit tests for [component] (per constitution coverage requirements)
    - [ ] Test: Integration tests for [workflow] (if required by constitution)
    - [ ] Test: Edge case handling for [scenario]

    # If constitution is flexible on testing, make it optional:
    - [ ] (Optional) Test: Consider adding tests for [critical paths]
    ```

    **Phase 4: Integration** (check child issues if they exist)
    ```markdown
    # If issue has children in related/, consider integration
    - [ ] Integration: Connect with [related issue child-1]
    - [ ] Integration: Verify compatibility with [system component]
    - [ ] Integration: Test end-to-end workflow
    ```

    **Phase 5: Polish & Documentation**
    ```markdown
    - [ ] Documentation: Update [specific files per constitution]
    - [ ] Documentation: Add inline code comments for complex logic
    - [ ] Documentation: Update API docs (if applicable)
    - [ ] Quality: Run linters and formatters per constitution
    - [ ] Quality: Verify constitution compliance (all MUST rules)
    - [ ] Quality: Review against definition of done
    ```

    **Task Guidelines:**
    - **Be specific**: "Add user_id validation to IssueService.validate_provider()" not "Add validation"
    - **Reference files**: Always include actual file paths and function/class names
    - **Map to AC**: Each acceptance criterion should have at least one implementation task
    - **Leverage test cases**: If issue includes test cases, create corresponding test tasks
    - **Use parent context**: Reference parent issues to understand broader goals
    - **Check children**: Review child issues to ensure your implementation supports downstream work
    - **Constitution-driven testing**:
      - Read constitution's test strategy (TDD vs test-after, coverage requirements, test organization)
      - Adjust phase order if constitution requires test-first approach
      - Make testing explicit if constitution has strict requirements, optional if flexible
      - Always leverage issue test cases when available, regardless of constitution flexibility
    - **Constitution alignment**: Reference specific constitution rules in relevant tasks

    **C. Additional Plan Sections**

    - **Testing Strategy** (constitution-driven):
      - **Constitution requirements**: Document what the constitution mandates (TDD, coverage %, test organization)
      - **Test timing**: Test-first (TDD) or test-after (per constitution guidance)
      - **Issue test cases**: {count} test cases to implement from issue
      - **Unit tests**: Specific test files and functions to write (if required/recommended by constitution)
      - **Integration tests**: Specific scenarios to test (if required/recommended by constitution)
      - **Test fixtures**: Reference existing patterns found in codebase exploration
      - **Expected coverage**: Per constitution requirements (or recommend % if constitution is flexible)
      - **Optional tests**: If constitution is flexible, suggest additional valuable tests
    - **Risks & Mitigations**: Technical blockers and solutions
    - **Definition of Done**:
      - ✅ All acceptance criteria met (from context-summary.md)
      - ✅ All test cases passing (from issue + additional)
      - ✅ Tests written and passing (per constitution coverage)
      - ✅ Documentation updated (per constitution standards)
      - ✅ Constitution standards followed (all MUST rules)
      - ✅ Code reviewed (if required by constitution)
      - ✅ Related issues considered (parents for context, children for integration)

11. **Stop and Report**

    After creating the plan, provide a comprehensive summary:

    ```text
    ## Planning Complete

    **Issue**: {provider} #{id} - {title}
    **Branch**: {branch_name}
    **Plan Location**: oak/plan/{name}/issue/plan.md

    ### Artifacts Created
    - ✅ summary.md - Agent-friendly issue summary with all details
    - ✅ plan.md - Implementation plan with structured task phases
    - ✅ related/{id}/summary.md - {count} related items for context

    ### Issue Context Leveraged
    - **Acceptance Criteria**: {count} criteria mapped to implementation tasks
    - **Test Cases**: {count} test cases from issue converted to test tasks
    - **Parent Context**: {parent issue info if exists}
    - **Child Items**: {count} child items reviewed for integration planning
    - **Related Issues**: {count} related items analyzed for dependencies

    ### Task Breakdown
    - **Phase 1 (Setup)**: {count} tasks
    - **Phase 2 (Implementation)**: {count} tasks (mapped to acceptance criteria)
    - **Phase 3 (Testing)**: {count} tasks (includes {count} from issue test cases)
    - **Phase 4 (Integration)**: {count} tasks
    - **Phase 5 (Polish)**: {count} tasks
    - **Total**: {total count} specific, actionable tasks

    ### Key Findings
    - **Patterns Identified**: {list key patterns found}
    - **Test Strategy (from constitution)**: {TDD/test-after, coverage %, required/optional}
    - **Constitution Rules**: {count} MUST rules, {count} SHOULD rules documented
    - **Unknowns Resolved**: {count} NEEDS CLARIFICATION items addressed

    ### Constitution Compliance
    - ✅ All MUST rules satisfied
    - ⚠️ {count} SHOULD rules require consideration (documented in plan)
    - ℹ️ Test strategy: {constitution test requirements summary}

    ### Next Steps
    1. Review plan.md to confirm approach and tasks
    2. Validate plan: /oak.plan-validate
    3. Once validated, implement: /oak.plan-implement
    ```

    **Command ends here**. The user should review the plan before proceeding to validation or implementation.

## Notes

- **CLI is scaffolding only**: These commands are deterministic utilities for data gathering and artifact creation. All reasoning about code design, patterns, and implementation strategy is your responsibility.
- **You drive exploration**: Use your full toolset (grep, find, git, read files, etc.) to understand the codebase.
- **Constitution is authoritative**: The project's `oak/constitution.md` always overrides general guidance. Read it thoroughly and apply its rules.
- **Testing strategy**: Always identify test patterns and extract test requirements from the constitution. Plan test creation according to constitution requirements (may be mandatory, recommended, or optional).
- **Git errors**: If git operations fail (e.g., dirty worktree, merge conflicts), explain the error clearly and wait for the user to resolve it before proceeding.
- **Plan is a living document**: The plan.md file should be updated as you learn more during exploration and implementation.
- **Open-agent-kit's unique advantage**: Unlike generic spec tools, open-agent-kit integrates with issue providers (Azure DevOps, GitHub Issues) to pull structured data: acceptance criteria, test cases, descriptions, parent/child relationships. **Use this data** to create more specific, actionable tasks. Map each acceptance criterion to implementation tasks, convert test cases to test tasks, and leverage parent/child context for planning. This is open-agent-kit's differentiator - don't create generic plans when you have rich structured data available.
- **Constitution-driven testing**: The test strategy (TDD vs test-after, coverage requirements, test organization) comes from the project's constitution, not from open-agent-kit. Extract test requirements from `oak/constitution.md` during step 9 and apply them when creating Phase 3 (Testing) tasks. If constitution is strict about testing, make all test tasks explicit and required. If constitution is flexible, suggest optional tests while still encouraging best practices. Always leverage issue test cases when available, regardless of constitution flexibility.
