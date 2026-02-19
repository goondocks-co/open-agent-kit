---
title: Governance
description: Monitor and control what your AI agents are allowed to do with rules, audit logging, and enforcement modes.
sidebar:
  order: 8
---

**Governance** gives you observability and control over AI agent actions. Define rules that match tool calls, choose whether to observe, warn, or deny, and review everything in a detailed audit log.

Open the Governance page from the dashboard sidebar, or navigate to `http://localhost:{port}/governance`.

## Why Governance?

AI coding agents are powerful, but that power comes with risk. An agent might accidentally delete critical files, expose secrets, or make changes you didn't expect. Governance helps you:

- **Observe** all tool calls across all agents in one place
- **Detect** risky patterns with regex-based rules
- **Block** dangerous operations before they happen (in enforce mode)
- **Audit** historical activity for compliance and debugging

## Enforcement Modes

Governance has two modes:

| Mode | Behavior |
|------|----------|
| **Observe** | Rules are evaluated, but deny/warn actions are downgraded to observe. Tool calls are never blocked. Safe for rollout. |
| **Enforce** | Deny rules block tool calls in real time. Warn rules allow the call but show a warning to the agent. |

:::tip[Start in Observe Mode]
When first enabling governance, use observe mode to see what rules would match without affecting agent behavior. Review the audit log to tune your rules before switching to enforce.
:::

## Rules

Rules define what to watch for. Each rule can match on:

- **Tool name** — The tool being called (e.g., `Bash`, `Write`, `*` for all)
- **Input pattern** — A regex matched against the serialized tool input
- **Path pattern** — An fnmatch pattern matched against the `file_path` field

When a rule matches, it triggers one of four actions:

| Action | Effect (Enforce Mode) | Effect (Observe Mode) |
|--------|----------------------|----------------------|
| **Deny** | Block the tool call, show message to agent | Log only (downgraded) |
| **Warn** | Allow call, warn the agent | Log only (downgraded) |
| **Observe** | Log only | Log only |
| **Allow** | Explicit allow, stop evaluating further rules | Allow |

Rules are evaluated in order. The first matching rule wins.

### Example Rules

**Block destructive shell commands:**

```yaml
id: no-destructive-bash
description: Block rm -rf and similar dangerous commands
enabled: true
tool: Bash
pattern: "rm\\s+-rf|DROP\\s+TABLE|truncate\\s+"
action: deny
message: "This command is blocked by governance policy."
```

**Block writes to .env files:**

```yaml
id: no-env-writes
description: Prevent modification of environment files
enabled: true
tool: Write
path_pattern: "*.env*"
action: deny
message: "Writing to .env files is not allowed."
```

**Observe all file operations:**

```yaml
id: observe-file-ops
description: Log all file system activity
enabled: true
tool: "*"
pattern: "file_path"
action: observe
```

### Creating Rules in the UI

1. Go to **Governance → Rules**
2. Click **Add Rule**
3. Fill in the rule fields:
   - **Rule ID** — Lowercase with dashes (e.g., `no-env-writes`)
   - **Description** — Human-readable explanation
   - **Action** — Deny, Warn, or Observe
   - **Tool name** — Which tool to match (`*` for all)
   - **Input pattern** — Optional regex
   - **Path pattern** — Optional fnmatch for file paths
   - **Agent message** — Shown to the agent on deny/warn
4. Click **Add Rule**
5. Click **Save** to persist changes

## Audit Log

The **Audit Log** tab shows every governance evaluation. Each event includes:

- **Decision** — Allow, Deny, Warn, or Observe
- **Tool** — Which tool was called
- **Category** — Tool category (filesystem, shell, network, agent, other)
- **Rule** — Which rule matched (if any)
- **Session** — Link to the full session
- **Time** — When the evaluation occurred

### Filtering the Audit Log

Use the filter panel to narrow down events:

- **Decision** — Show only allow, deny, warn, or observe events
- **Tool** — Filter by tool name (e.g., `Bash`)
- **Time range** — Last hour, 24 hours, 7 days, 30 days, or all time

Click any event to expand it and see full details: agent, session, enforcement mode, evaluation time, matched pattern, and a summary of the tool input.

### Summary Stats

The top of the Audit Log shows aggregate stats for the last 7 days:

- Total events
- Breakdown by decision (Allow, Observe, Warn, Deny)

Use these to quickly understand what's happening across your agents.

## Configuration

Governance settings are stored in your project's `.oak/config.yaml`:

```yaml
codebase_intelligence:
  governance:
    enabled: true
    enforcement_mode: observe  # or "enforce"
    log_allowed: false         # if true, log allow decisions too (verbose)
    retention_days: 30         # how long to keep audit events
    rules:
      - id: no-destructive-bash
        description: Block destructive shell commands
        enabled: true
        tool: Bash
        pattern: "rm\\s+-rf"
        action: deny
        message: "Blocked by governance policy."
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Whether governance evaluation is active |
| `enforcement_mode` | `observe` | `observe` (log only) or `enforce` (can block) |
| `log_allowed` | `false` | Log allow decisions too (can be verbose) |
| `retention_days` | `30` | Days to keep audit events before pruning (1–365) |
| `rules` | `[]` | List of governance rules |

### Rule Schema

Each rule has these fields:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (lowercase, dashes only) |
| `description` | No | Human-readable description |
| `enabled` | No | Whether the rule is active (default: true) |
| `tool` | No | Tool name or glob pattern (default: `*`) |
| `pattern` | No | Regex matched against serialized tool input |
| `path_pattern` | No | fnmatch pattern for file paths |
| `action` | No | `allow`, `deny`, `warn`, or `observe` (default: `observe`) |
| `message` | No | Message shown to agent on deny/warn |

## Tool Categories

Governance automatically categorizes tools for filtering and analysis:

| Category | Tools |
|----------|-------|
| **Filesystem** | Read, Write, Edit, Glob, Grep |
| **Shell** | Bash |
| **Network** | WebFetch, WebSearch |
| **Agent** | Task |
| **Other** | Everything else |

## Audit Retention

Audit events are automatically pruned based on the `retention_days` setting. You can also trigger manual pruning:

1. Go to **Governance → Rules**
2. Click the **Prune** button next to Audit Retention

This removes all events older than the configured retention period.

:::caution[Audit events and backups]
Governance audit events are **not** included in team backups. They're considered machine-local observability data. If you need to preserve audit history, export it separately before the retention window expires.
:::

## Agent Support

Governance works with all agents that support the PreToolUse hook:

| Agent | Governance Support |
|-------|-------------------|
| **Claude Code** | Full (deny via hookSpecificOutput) |
| **Cursor** | Full (deny via permission format) |
| **Gemini CLI** | Full (deny via hookSpecificOutput) |
| **VS Code Copilot** | Full (deny via hookSpecificOutput) |
| **Windsurf** | Observe only (no deny hook support) |
| **OpenCode** | Full (deny via hookSpecificOutput) |
| **Codex CLI** | Observe only |

Agents that don't support deny hooks will have deny/warn rules logged but not enforced, even in enforce mode.

## Testing Rules

Before enabling enforce mode, test your rules against hypothetical tool calls:

1. Go to **Governance → Rules**
2. Find the **Test Policy** panel
3. Enter a tool name (e.g., `Bash`)
4. Enter tool input as JSON (e.g., `{"command": "rm -rf /"}`)
5. Click **Test**

The result shows which rule would match and what action would be taken.

## Best Practices

1. **Start with observe mode** — Get visibility before enforcement
2. **Review the audit log regularly** — Look for unexpected patterns
3. **Use specific patterns** — Avoid overly broad rules that block legitimate work
4. **Test rules before enforcing** — Use the Test Policy feature
5. **Document your rules** — Add clear descriptions so teammates understand the intent
6. **Set reasonable retention** — 30 days is a good default; increase if you need longer audit trails
