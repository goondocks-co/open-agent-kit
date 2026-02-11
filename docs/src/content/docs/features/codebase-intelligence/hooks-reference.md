---
title: Hooks Reference
description: Comprehensive reference for the CI hooks system — capture, processing, and context injection.
sidebar:
  order: 5
---

Codebase Intelligence integrates with AI agents via **hooks** — events fired by the agent that the CI daemon responds to. The daemon captures agent activity, processes it to extract observations using LLM classification, and injects relevant context back into the agent's conversation.

All hooks communicate via HTTP POST requests to the daemon's API endpoints.

## Hook Events

| Hook Event | Endpoint | When Fired | Primary Purpose |
|------------|----------|------------|-----------------|
| `SessionStart` | `/api/oak/ci/session-start` | Agent launches | Create session, inject initial context |
| `UserPromptSubmit` | `/api/oak/ci/prompt-submit` | User sends a prompt | Create prompt batch, inject memories/code |
| `PostToolUse` | `/api/oak/ci/post-tool-use` | After each tool runs | Capture activity, inject file memories |
| `PostToolUseFailure` | `/api/oak/ci/post-tool-use-failure` | Tool execution fails | Capture failed tool activity |
| `Stop` | `/api/oak/ci/stop` | Agent finishes responding | End prompt batch, trigger processing |
| `SessionEnd` | `/api/oak/ci/session-end` | Clean exit (Ctrl+D, /exit) | End session, generate summary |
| `SubagentStart` | `/api/oak/ci/subagent-start` | Subagent spawned | Track subagent lifecycle |
| `SubagentStop` | `/api/oak/ci/subagent-stop` | Subagent completes | Track subagent completion |
| `PreCompact` | `/api/oak/ci/pre-compact` | Context compaction | Track context pressure |

## Agent-Specific Mappings

### Gemini CLI

| Gemini CLI Event | OAK Event | Notes |
|------------------|-----------|-------|
| `SessionStart` | `SessionStart` | Same name |
| `BeforeAgent` | `UserPromptSubmit` | Provides `prompt` |
| `AfterTool` | `PostToolUse` | Provides `tool_name`, `tool_input`, `tool_response` |
| `AfterAgent` | `Stop` | Provides `prompt_response` |
| `PreCompress` | `PreCompact` | Before history summarization |
| `SessionEnd` | `SessionEnd` | Same name |

### Cursor

| Cursor Event | OAK Event | Notes |
|--------------|-----------|-------|
| `sessionStart` | `SessionStart` | Lowercase convention |
| `beforeSubmitPrompt` | `UserPromptSubmit` | Before prompt is sent |
| `afterFileEdit` | `PostToolUse` | Maps to tool_name="Edit" |
| `afterAgentResponse` | `PostToolUse` | Maps to tool_name="agent_response" |
| `postToolUse` | `PostToolUse` | General tool use |
| `stop` | `Stop` | Agent finishes responding |
| `sessionEnd` | `SessionEnd` | Session exits |

:::note[Cursor Dual-Hook Behavior]
Cursor reads hooks from both `.cursor/hooks.json` AND `.claude/settings.local.json`, so every hook event fires **twice**. The daemon handles this via content-based deduplication — the second call is silently dropped.
:::

### Codex CLI (OpenTelemetry)

:::note[Codex CLI only]
Hooks are fully supported when using the Codex CLI directly. However, extensions that wrap the CLI — such as the Codex VS Code extension and the Codex desktop app — ignore project-level configuration in favor of global settings, so hooks will not work through those interfaces.
:::

| Codex OTel Event | Hook Action |
|-----------------|-------------|
| `codex.conversation_starts` | `session-start` |
| `codex.user_prompt` | `prompt-submit` |
| `codex.tool_decision` | `prompt-submit` |
| `codex.tool_result` | `post-tool-use` |

## Feature Lifecycle Hooks

In addition to agent hooks, CI registers feature lifecycle hooks that fire during OAK operations:

| Hook Event | Trigger | Purpose |
|------------|---------|---------|
| `on_feature_enabled` | `oak feature enable codebase-intelligence` | Initialize data dir, constitution, hooks, start daemon |
| `on_feature_disabled` | `oak feature disable codebase-intelligence` | Stop daemon, remove hooks, clean data |
| `on_pre_remove` | `oak remove` | Cleanup before OAK removal |
| `on_agents_changed` | `oak init` with different agents | Update agent hook configurations |
| `on_pre_upgrade` | `oak upgrade` | Create backup before upgrade (if configured) |

### Pre-Upgrade Backup

The `on_pre_upgrade` hook automatically creates a backup before `oak upgrade` applies any changes. This is controlled by the `backup.on_upgrade` configuration setting (enabled by default).

When triggered, the hook:
1. Checks if `backup.on_upgrade` is enabled in the configuration
2. If enabled, creates a backup using the configured defaults (including the `include_activities` setting)
3. Logs success or failure — the upgrade proceeds regardless

To disable pre-upgrade backups:
```yaml
# In .oak/config.yaml
codebase_intelligence:
  backup:
    on_upgrade: false
```

## Context Injection

Context is injected into the agent's conversation via the `injected_context` field in the hook response.

### Injection Limits

| Constant | Value | Description |
|----------|-------|-------------|
| `INJECTION_MAX_CODE_CHUNKS` | 3 | Max code snippets per injection |
| `INJECTION_MAX_LINES_PER_CHUNK` | 50 | Max lines per code chunk |
| `INJECTION_MAX_MEMORIES` | 10 | Max memories per injection |
| `INJECTION_MAX_SESSION_SUMMARIES` | 5 | Max session summaries |

### Confidence Filtering

| Confidence | Similarity Score | Usage |
|------------|-----------------|-------|
| `high` | >= 0.75 | Prompt submit, notify context |
| `medium` | >= 0.60 | Post-tool-use file memories |
| `low` | >= 0.45 | Not used for injection |

## Deduplication

Hooks are deduplicated to prevent duplicate processing:

| Event | Dedupe Key | Notes |
|-------|-----------|-------|
| `session-start` | `agent` + `source` | Allows both claude and cursor calls through |
| `prompt-submit` | `generation_id` + `prompt_hash` | Second identical prompt is dropped |
| `post-tool-use` | `tool_use_id` | Exact tool invocation match |
| `stop` | `batch_id` | Prevents double-ending the same batch |
| `session-end` | `session_id` only | Only one end per session |

## Hook Configuration

Hooks are configured in agent-specific settings files. These files are **local-only** — they are automatically added to `.gitignore` and regenerated from templates on each `oak ci start`.

Example for Claude Code (written to `.claude/settings.local.json`):

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/path/to/oak-ci-hook.sh session-start"
      }]
    }]
  }
}
```

The hook shell script reads JSON from stdin and forwards it to the daemon's HTTP API.

## Debugging

```bash
# Watch daemon logs for hook events
tail -f .oak/ci/daemon.log | grep -E "SESSION-START|PROMPT|TOOL|STOP|SESSION-END"

# Verify injected context
grep "INJECT:" .oak/ci/daemon.log

# Check deduplication
grep "Deduped" .oak/ci/daemon.log
```

## Related Documentation

- [Session Lifecycle](/open-agent-kit/features/codebase-intelligence/session-lifecycle/) — Session state management and recovery
- [Memory](/open-agent-kit/features/codebase-intelligence/memory/) — How memories are stored and retrieved
- [API Reference](/open-agent-kit/features/codebase-intelligence/developer-api/) — REST endpoints
