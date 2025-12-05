---
description: Create a strategic plan with clarifying questions, goals, and research topics.
requires:
  - path: oak/constitution.md
    error: "Run /oak.constitution-create first to establish your project's engineering standards."
generates:
  - oak/plan/<plan-name>/plan.md
  - oak/plan/<plan-name>/.manifest.json
  - oak/plan/<plan-name>/research/
  - git branch: plan/<plan-name>
handoffs:
  - label: Research Topics
    agent: oak.plan-research
    prompt: Research the topics identified in the plan to gather insights and inform task generation.
---

## User Input

```text
$ARGUMENTS
```

Treat the text supplied after the command as context for the planning session. This should describe what you're planning (a feature, migration, architecture change, etc.). Ask clarifying questions if anything is ambiguous.

## Interaction Guidelines

**Always ask when:**
- The scope or objectives are unclear
- There are multiple valid approaches to consider
- Key constraints or requirements are missing
- Research topics need prioritization

**Proceed without asking when:**
- Objectives are clearly stated in $ARGUMENTS
- Context is complete and unambiguous
- Standard planning workflow applies

**How to ask effectively:**
- Present specific options when clarifying
- Explain what information is needed and why
- Suggest defaults based on available context

## Responsibilities

1. Gather requirements through clarifying questions.
2. Create the plan structure via `oak plan create`.
3. Populate the plan with goals, success criteria, and research topics.
4. Read the project constitution to understand standards.
5. Identify research topics that need investigation.
6. Summarize and propose next actions (research phase).

## Prerequisites

Before executing this command, ensure these prerequisites are met:

1. **Constitution Exists** (REQUIRED): The project must have a constitution at `oak/constitution.md`.
   - If missing, **STOP** and instruct the user: "Please run `/oak.constitution-create` first to establish your project's engineering standards."

## Workflow

### 1. Clarifying Questions Phase

Before creating the plan, gather essential context:

**Scope Questions:**
- What is the primary objective of this plan?
- What problem are we solving or opportunity are we pursuing?
- What is in scope? What is explicitly out of scope?
- What are the key constraints (technical, timeline, resources)?

**Research Questions:**
- What unknowns need investigation before implementation?
- Are there competing approaches to evaluate?
- What external resources, APIs, or tools might be involved?
- What existing codebase patterns should inform this work?

**Success Questions:**
- How will we know when this is complete?
- What are the acceptance criteria for success?
- Who are the stakeholders and what do they need?

**Present questions strategically:**
- Group related questions together
- Provide examples or defaults where helpful
- Prioritize questions that unlock other answers

### 2. Create Plan Structure

Once you have sufficient context:

```bash
# Create the plan with a URL-safe name
oak plan create <plan-name> --display-name "Human Readable Name"

# Example:
oak plan create auth-redesign --display-name "Authentication System Redesign"
```

The CLI will:
- Create `oak/plan/<plan-name>/` directory
- Initialize `plan.md` with basic structure
- Create `.manifest.json` with metadata
- Create `research/` directory for findings
- Create a git branch `plan/<plan-name>`

### 3. Populate Plan Content

Edit `oak/plan/<plan-name>/plan.md` to include:

**Overview Section:**
- Executive summary of what this plan achieves
- Problem statement or opportunity description
- High-level approach

**Goals Section:**
- 3-5 specific, measurable objectives
- Each goal should be testable/verifiable

**Success Criteria Section:**
- How success will be measured
- Specific outcomes or deliverables

**Scope Section:**
- What's in scope (features, components, etc.)
- What's explicitly out of scope
- Known boundaries and limitations

**Constraints Section:**
- Technical constraints (languages, frameworks, APIs)
- Resource constraints (time, team, budget)
- Organizational constraints (approvals, dependencies)

### 4. Identify Research Topics

Based on the clarifying conversation, create research topics:

**Research Topic Structure:**
```markdown
### Topic Title
**Slug:** `url-safe-slug`
**Priority:** 1-5 (1 = highest)
**Status:** pending

Description of what to research and why.

**Questions to answer:**
- Specific question 1?
- Specific question 2?

**Sources to check:**
- Documentation links
- Similar projects
- Internal resources
```

**Good Research Topics:**
- Technology comparisons (e.g., "OAuth Providers")
- Architecture patterns (e.g., "Event Sourcing Patterns")
- Integration approaches (e.g., "Payment Gateway APIs")
- Codebase analysis (e.g., "Existing Auth Patterns")

**Research Depth:**
- `minimal`: Quick validation, 1-2 sources
- `standard`: Comprehensive overview, 3-5 sources (default)
- `comprehensive`: Deep dive, extensive sources, comparisons

### 5. Constitution Alignment

Read the project constitution and identify:

```bash
cat oak/constitution.md
```

- Relevant coding standards for this work
- Testing requirements that apply
- Documentation standards to follow
- Review or approval processes

Document in the plan how constitution standards will be applied.

### 6. Update Plan Status

```bash
oak plan status <plan-name> researching
```

### 7. Stop and Report

After creating the plan, provide a summary:

```text
## Plan Created

**Plan:** <plan-name>
**Display Name:** <Human Readable Name>
**Branch:** plan/<plan-name>
**Location:** oak/plan/<plan-name>/plan.md

### Overview
<Brief summary of the plan>

### Goals Defined
1. <Goal 1>
2. <Goal 2>
3. <Goal 3>

### Research Topics Identified
1. **<Topic 1>** (Priority 1) - <Brief description>
2. **<Topic 2>** (Priority 2) - <Brief description>
3. **<Topic 3>** (Priority 3) - <Brief description>

### Constitution Alignment
- <Key standards that will apply>

### Next Steps
1. Review and refine plan.md
2. Begin research: /oak.plan-research <plan-name>
```

**Command ends here.** The user should review the plan before proceeding to research.

## Research Strategy Guidance

{% if has_native_web %}
When researching topics in the next phase, you have access to **web search capabilities**. Use them proactively to gather current information, documentation, and best practices.
{% else %}
Note: This agent may not have native web search capabilities. During the research phase, focus on:
- Codebase exploration for existing patterns
- General knowledge for established best practices
{% if has_mcp %}
- MCP tools if web search servers are available
{% endif %}
{% endif %}

{% if has_background_agents %}
Consider using **background agents** during research to parallelize investigation of multiple topics efficiently.
{% endif %}

## Notes

- **Plans are living documents**: Update plan.md as understanding evolves
- **Research before tasks**: Thorough research leads to better task definitions
- **Constitution is authoritative**: All planning should align with project standards
- **Scope creep prevention**: Use the scope section to maintain focus
- **Prioritize research**: Not all topics are equally important - focus on high-priority unknowns first
