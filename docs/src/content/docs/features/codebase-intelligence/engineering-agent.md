---
title: Engineering Agent
description: An autonomous engineering team powered by Codebase Intelligence.
---

The Engineering Agent is an autonomous AI agent that operates as your engineering team — with tasks for different team roles like Senior Engineer and Product Manager. Each task brings a distinct perspective and methodology, while all share access to CI's full knowledge base.

Unlike the [Documentation Agent](/open-agent-kit/features/codebase-intelligence/documentation-agent/) (which focuses on maintaining docs) or the [Analysis Agent](/open-agent-kit/features/codebase-intelligence/analysis-agent/) (which focuses on insights and reports), the Engineering Agent performs hands-on engineering work: reviewing code, implementing features, fixing bugs, and triaging issues.

## How It Works

The agent has access to your filesystem (with broad permissions for engineering work) and CI's full knowledge base, plus optional shell access for git operations and running tests:

| CI Tool | What the agent uses it for |
|---------|---------------------------|
| `ci_search` | Semantic search across code, memories, and plans |
| `ci_memories` | Filter observations by type (decision, gotcha, bug_fix, discovery, trade_off) |
| `ci_sessions` | Access recent coding sessions with summaries |
| `ci_project_stats` | Get codebase structure and statistics |
| `ci_query` | Direct SQL access for advanced queries |

For every task, the agent follows a consistent methodology:

1. **Research** — Query CI for related code, prior decisions, known gotchas, and past bug fixes
2. **Analyze** (for review work) — Use Glob/Grep to find patterns, compare against constitution rules
3. **Implement** (for coding work) — Create branches, write tests, follow existing patterns, commit with context
4. **Verify** — Run tests, check against CI learnings, ensure quality gates pass

## Built-in Tasks

OAK ships two built-in tasks that represent different engineering team roles. Run them from the Agents page in the dashboard, or trigger them via the API.

### Senior Engineer

The team's hands-on builder and technical expert. Reviews architecture, hunts bugs, implements features, and fixes issues.

**Perspective:** Think like an engineer who owns this code. Care about correctness, maintainability, test coverage, and following established patterns.

**What it does:**
- Reads `oak/constitution.md` for project standards before making changes
- Searches CI for related code, prior work, and design intent
- Finds closest existing implementations and mirrors their patterns
- Creates feature branches for code changes
- Writes tests for new functionality
- Runs existing tests before considering work complete
- Commits with descriptive messages explaining "why" not just "what"

**For review and investigation work:**
- Uses Glob/Grep to find code patterns across the codebase
- Compares against constitution rules and established conventions
- Classifies findings by severity (critical/warning/info)
- Includes file:line references and rule citations
- Crafts detailed fix prompts for each finding
- Writes findings to `oak/insights/`

**Safety rules:**
- Never pushes to main/master directly
- Never commits secrets or credentials
- Never force-pushes or rebases shared branches
- Always runs tests before considering implementation complete
- Always creates a new branch for code changes
- Always verifies claims against CI data

**Shell access:** Yes (for git operations and running tests)

### Product Manager

The team's strategic reviewer and quality gatekeeper. Reviews proposed work for alignment with project goals and constitution.

**Perspective:** Think like someone who owns the product roadmap. Care about alignment with goals, completeness of requirements, and well-defined work items.

**What it does:**
- Reads `oak/constitution.md` for project tenets and core goals
- Queries CI for strategic decisions and existing roadmap
- Reviews each work item for goal alignment
- Checks for clear problem statements and testable acceptance criteria
- Identifies duplicate or conflicting work
- Suggests appropriate priority and categorization
- Writes triage results to `oak/insights/issue-triage.md`

**For each item, produces:**
- Alignment assessment (aligned / needs adjustment / out of scope)
- Missing acceptance criteria (if any)
- Suggested labels/categories
- Recommended priority
- Questions or concerns that need resolution

**Shell access:** No (analysis-focused task)

## Running Tasks

1. Navigate to the **Agents** page in the dashboard
2. Select a task from the Engineering Team section
3. Provide an assignment in the task input (e.g., "Review the authentication module for security issues")
4. Click **Run** to start the agent
5. Watch progress in real time — output streams as the agent works
6. View completed runs in the **Run History** section

### Assignment Prompts

Unlike Documentation and Analysis agents which have fixed task scopes, Engineering Agent tasks expect an **assignment** — what specifically you want the agent to work on:

```
# For Senior Engineer
Review src/auth/ for security issues and code quality
Implement the user settings feature from oak/rfc/RFC-003-user-settings.md
Fix the failing test in tests/test_session.py
Hunt for bugs in the payment processing flow

# For Product Manager
Triage these GitHub issues: #42, #47, #51
Review the proposed features in oak/rfc/ for priority and completeness
Assess whether RFC-005 aligns with our Q1 goals
```

### Run History

Every agent run is recorded with:
- **Status** — Running, completed, failed, or cancelled
- **Output** — Full agent output including findings or changes made
- **Timing** — Start time, duration, and token usage
- **Cancellation** — Cancel a running agent at any time

## Scheduling

Engineering tasks can be scheduled to run automatically using cron expressions. Manage schedules from the Agents page in the dashboard.

**Example schedules:**

| Task | Cron | Frequency | Use Case |
|------|------|-----------|----------|
| Senior Engineer | `0 6 * * MON` | Weekly Monday 6 AM | Weekly code review of recent changes |
| Product Manager | `0 9 * * MON` | Weekly Monday 9 AM | Weekly issue triage |

## Custom Tasks

You can create custom tasks that the Engineering Agent will automatically pick up. Custom tasks live in `oak/agents/` (git-tracked) and use the same YAML format as built-in tasks.

### Example: Security Auditor

```yaml
# oak/agents/security-auditor.yaml
name: security-auditor
display_name: "Security Auditor"
agent_type: engineering
description: "Weekly security audit of authentication and authorization code"

default_task: |
  ## Your Role: Security Auditor

  Review authentication and authorization code for security issues.

  ## Methodology

  1. Read oak/constitution.md for security requirements
  2. ci_memories(filter="gotcha") for known security issues
  3. ci_memories(filter="bug_fix") for past security fixes
  4. Search for: hardcoded secrets, SQL injection, XSS, auth bypasses
  5. For each finding: severity, file:line, description, remediation

  Write findings to oak/insights/security-audit.md

execution:
  timeout_seconds: 900
  max_turns: 100
  permission_mode: acceptEdits

# Bash access for running security scanners
additional_tools:
  - "Bash"

maintained_files:
  - path: "{project_root}/oak/insights/security-audit.md"
    purpose: "Security audit findings"
    auto_create: true

ci_queries:
  discovery:
    - tool: ci_search
      query_template: "authentication authorization security"
      search_type: code
      limit: 30
      purpose: "Find auth-related code"
  context:
    - tool: ci_memories
      filter: gotcha
      limit: 20
      purpose: "Known security gotchas"
    - tool: ci_memories
      filter: bug_fix
      limit: 20
      purpose: "Past security fixes"

schedule:
  cron: "0 5 * * MON"
  description: "Weekly Monday morning"

schema_version: 1
```

### Key Fields for Engineering Tasks

| Field | Required | Description |
|-------|----------|-------------|
| `agent_type` | Yes | Must be `engineering` |
| `additional_tools` | No | Add `["Bash"]` to enable shell access for the task |
| `default_task` | Yes | The methodology prompt — describes the role's perspective and workflow |

## Provider Configuration

The Engineering Agent uses the shared OAK Agents provider configured in **Agents page → Settings** (`/agents/settings`).

See [OAK Agents](/open-agent-kit/features/codebase-intelligence/agents/#provider-configuration) for supported providers and setup details.

## Security

The Engineering Agent operates within configurable boundaries:

**Allowed file access (template defaults):**
- `src/**`, `tests/**`, `oak/**`, `docs/**`
- `*.md`, `*.yaml`, `*.yml`, `*.json`, `*.toml`, `*.cfg`, `*.txt`
- `Makefile`, `pyproject.toml`

**Blocked file access:**
- `.env`, `.env.*` — Environment files
- `*.pem`, `*.key`, `*.crt` — Certificates and keys
- `**/credentials*`, `**/secrets*` — Sensitive directories
- `.oak/ci/**` — CI internal data

**Shell access:**
- **Disabled at template level** — Tasks must explicitly opt in via `additional_tools: ["Bash"]`
- Senior Engineer task opts in for git and test operations
- Product Manager task does not have shell access

**Safety rules enforced by methodology:**
- Never push to main/master directly
- Never commit secrets
- Always create branches for code changes
- Always run tests before completing implementation work
