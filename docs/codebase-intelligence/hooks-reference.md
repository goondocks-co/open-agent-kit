# Hooks Reference

This document provides a comprehensive reference for the Codebase Intelligence hooks system, including what each hook captures, what context gets injected, and how the system processes agent activity.

## Overview

Codebase Intelligence integrates with AI agents (Claude Code, Cursor, Gemini) via **hooks** - events fired by the agent that the CI daemon responds to. The daemon:

1. **Captures** agent activity (tool calls, prompts, sessions)
2. **Processes** activity to extract observations using LLM classification
3. **Injects** relevant context back into the agent's conversation

All hooks communicate via HTTP POST requests to the daemon's API endpoints.

## OpenTelemetry Agents (Codex)

Codex emits OpenTelemetry (OTLP) log events instead of calling hook endpoints directly. The daemon translates these events into the same hook actions as other agents.

Codex event mapping (via `src/open_agent_kit/agents/codex/manifest.yaml`):

| Codex OTel Event | Hook Action |
|-----------------|-------------|
| `codex.conversation_starts` | `session-start` |
| `codex.user_prompt` | `prompt-submit` |
| `codex.tool_decision` | `prompt-submit` |
| `codex.tool_result` | `post-tool-use` |

## Agent Notifications (Codex Notify Handler)

Codex can emit structured notification events via the `notify` handler in `.codex/config.toml`. OAK configures this handler to invoke `oak ci notify`, which forwards events to the daemon endpoint `/api/oak/ci/notify`.

Codex notify mapping (via `src/open_agent_kit/agents/codex/manifest.yaml`):

| Codex Notify Event | OAK Action |
|-------------------|-----------|
| `agent-turn-complete` | `response-summary` |

For `agent-turn-complete`, OAK uses:
- `thread-id` as the session identifier
- `last-assistant-message` as the response summary to store on the active prompt batch

Codex notify handlers are configured to invoke `oak ci notify` for cross-platform reliability.

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

## Gemini CLI Hook Mapping

Gemini CLI uses different event names from Claude Code. The `oak ci hook` command
accepts both native event names and normalizes them to the OAK hook model:

| Gemini CLI Event | OAK Event | `oak ci hook` Argument | Notes |
|------------------|-----------|------------------------|-------|
| `SessionStart` | `SessionStart` | `SessionStart` | Same name |
| `BeforeAgent` | `UserPromptSubmit` | `BeforeAgent` | Fires after user sends prompt, before agent planning. Provides `prompt` |
| `AfterTool` | `PostToolUse` | `PostToolUse` | Provides `tool_name`, `tool_input`, `tool_response` |
| `AfterAgent` | `Stop` | `AfterAgent` | Fires once per turn after final response. Provides `prompt_response` |
| `PreCompress` | `PreCompact` | `PreCompress` | Before history summarization |
| `SessionEnd` | `SessionEnd` | `SessionEnd` | Same name |

**Gemini-specific data fields:**
- `BeforeAgent` provides `prompt` (user's text) — equivalent to Claude's `UserPromptSubmit`
- `AfterAgent` provides `prompt_response` (agent's final answer) — maps to `response_summary` in the Stop handler
- All Gemini hooks include `session_id`, `transcript_path`, `cwd`, `timestamp` in their stdin JSON

**Gemini events NOT used by OAK** (available but not needed for session capture):
- `BeforeTool` — pre-tool validation (OAK captures post-tool only)
- `BeforeToolSelection` — tool filtering (not relevant to capture)
- `BeforeModel` / `AfterModel` — LLM request/response interception (too low-level)
- `Notification` — system alerts (could be added if needed)

## Cursor Hook Mapping

Cursor uses its own hook event names configured in `.cursor/hooks.json` with a flat
structure (no matcher/nested hooks). The `oak ci hook` command normalizes these to
the OAK hook model:

| Cursor Event | OAK Event | `oak ci hook` Argument | Notes |
|--------------|-----------|------------------------|-------|
| `sessionStart` | `SessionStart` | `sessionStart` | Lowercase convention |
| `beforeSubmitPrompt` | `UserPromptSubmit` | `beforeSubmitPrompt` | Fires before prompt is sent to agent |
| `afterFileEdit` | `PostToolUse` | `afterFileEdit` | File edit specific; maps to tool_name="Edit" |
| `afterAgentResponse` | `PostToolUse` | `afterAgentResponse` | Agent response text; maps to tool_name="agent_response" |
| `afterAgentThought` | `AgentThought` | `afterAgentThought` | Agent thinking/reasoning block |
| `postToolUse` | `PostToolUse` | `postToolUse` | General tool use (Read, Shell, Grep, etc.) |
| `preCompact` | `PreCompact` | `preCompact` | Context window compaction |
| `stop` | `Stop` | `stop` | Agent finishes responding |
| `sessionEnd` | `SessionEnd` | `sessionEnd` | Session exits |
| `postToolUseFailure` | `PostToolUseFailure` | `postToolUseFailure` | Tool execution failure |
| `subagentStart` | `SubagentStart` | `subagentStart` | Task/subagent spawned |
| `subagentStop` | `SubagentStop` | `subagentStop` | Task/subagent completed |

### Cursor Dual-Hook Behavior

**Important**: Cursor reads hooks from both `.cursor/hooks.json` AND `.claude/settings.json`.
This means every hook event fires **twice** for the same session — once from the Claude
config (with `--agent claude`) and once from the Cursor config (with `--agent cursor`).

This is handled at the daemon API level:

1. **Deduplication**: Most hook events (prompt-submit, post-tool-use, stop, session-end,
   etc.) are deduplicated by content-based keys (prompt hash, tool_use_id, batch ID).
   The second call is silently dropped.

2. **Session agent label**: `SessionStart` is the one exception — its dedupe key includes
   the agent name, so both calls pass through. The first call (from Claude config) creates
   the session with `agent=claude`. The second call (from Cursor config) updates the agent
   label to `cursor` via `get_or_create_session`, which always applies the latest agent
   label when it differs. This ensures sessions are correctly attributed to Cursor.

3. **Response formatting**: The `oak ci hook` CLI formats output differently per `--agent`
   flag. Cursor ignores the Claude-formatted response (wrong key structure) and properly
   consumes the Cursor-formatted response. Context injection works correctly.

## Hook Configuration

Hooks are configured in `.claude/settings.json` (Claude Code), `.cursor/hooks.json` (Cursor),
or `.gemini/settings.json` (Gemini CLI). Example for Claude Code:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/path/to/oak-ci-hook.sh session-start"
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "/path/to/oak-ci-hook.sh prompt-submit"
      }]
    }]
  }
}
```

The hook shell script reads JSON from stdin and forwards it to the daemon's HTTP API.

---

## Detailed Hook Reference

### SessionStart

**When**: Agent process launches (startup, resume, clear, compact)

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique session identifier |
| `conversation_id` | string | Alternative to session_id |
| `agent` | string | Agent name (claude, cursor, gemini) |
| `source` | string | Start type: `startup`, `resume`, `clear`, `compact` |

**What We Capture**:
- Create session record in SQLite (idempotent via `get_or_create_session`)
- Update agent label if it differs from the existing session (handles Cursor dual-hook scenario)
- Reactivate session if previously completed (e.g., on resume)
- Create in-memory session tracking
- Track session start time

**What We Inject** (via `injected_context`):

On fresh starts (`startup`, `clear`), injects:

```markdown
**Codebase Intelligence Active**: 150 code chunks indexed, 42 memories stored.

## Recent Session History

**Session 1** (claude-code): Implemented user authentication...
**Session 2** (claude-code): Fixed database connection pooling...

## Recent Project Memories

- ! **gotcha**: Database connections leak under load _(context: src/db.py)_
- [decision] **decision**: Use async for I/O operations
- [fix] **bug_fix**: Fixed race condition in cache invalidation
```

On `resume`/`compact`, minimal context is injected to avoid bloat.

**Response**:
```json
{
  "status": "ok",
  "session_id": "abc-123",
  "context": {
    "session_id": "abc-123",
    "agent": "claude",
    "injected_context": "**Codebase Intelligence Active**...",
    "project_root": "/Users/chris/project",
    "index": {
      "code_chunks": 150,
      "memory_observations": 42,
      "status": "ready"
    }
  }
}
```

---

### UserPromptSubmit

**When**: User sends a prompt to the agent

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `prompt` | string | Full user prompt text |
| `agent` | string | Agent name |
| `hook_origin` | string | Origin context |
| `generation_id` | string | Unique generation identifier |

**What We Capture**:
- End previous prompt batch (if exists)
- Create new prompt batch record
- Queue previous batch for async LLM processing
- Classify prompt source type (user, plan, internal)
- Extract plan content if present in prompt

**Prompt Source Types**:
| Type | Description |
|------|-------------|
| `user` | Normal user prompt |
| `plan` | Plan execution prompt (auto-injected) |
| `internal` | System/internal prompts |

**What We Inject** (via `injected_context`):

Searches for high-confidence relevant memories AND code:

```markdown
## Relevant Code

**src/auth/handler.py** (L45-78) - `authenticate_user`
```python
async def authenticate_user(request: Request) -> User:
    token = request.headers.get("Authorization")
    if not token:
        raise AuthError("Missing token")
    ...
```

**Relevant memories for this task:**
- [gotcha] JWT tokens expire after 1 hour, refresh required
- [decision] Use bcrypt for password hashing
```

**Confidence Filtering**: Only HIGH confidence results are injected (precision over recall).

**Response**:
```json
{
  "status": "ok",
  "context": {
    "injected_context": "## Relevant Code\n..."
  },
  "prompt_batch_id": "batch-uuid-123"
}
```

---

### PostToolUse

**When**: After each tool execution completes successfully

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `tool_name` | string | Tool name (Read, Edit, Write, Bash, etc.) |
| `tool_input` | dict/string | Tool input parameters |
| `tool_output` | string | Tool output text |
| `tool_output_b64` | string | Base64-encoded output (preferred) |
| `tool_use_id` | string | Unique tool use identifier |

**What We Capture**:
- Store Activity record in SQLite with:
  - Sanitized tool input (large content replaced with `<N chars>`)
  - Output summary (truncated to 500 chars)
  - File path (for file operations)
  - Error detection (stderr presence)
  - Associated prompt batch ID

**Plan Detection**: If `tool_name == "Write"` to a plan directory (`.claude/plans/`, `.cursor/plans/`), marks the prompt batch as a plan and stores plan content.

**What We Inject** (via `injected_context`):

For file operations (Read, Edit, Write), searches for memories about the file using a **rich search query**:

```
file_path + tool_output_excerpt + user_prompt_excerpt
```

Example injection:
```markdown
**Memories about src/db.py:**
- GOTCHA: Database connections leak under load - always use context manager
- [decision] Use connection pooling with max 10 connections
```

**Confidence Filtering**: HIGH and MEDIUM confidence memories are injected.

**Response**:
```json
{
  "status": "ok",
  "observations_captured": 0,
  "injected_context": "**Memories about src/db.py:**\n..."
}
```

---

### PostToolUseFailure

**When**: Tool execution fails

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `tool_name` | string | Tool that failed |
| `tool_input` | dict | Tool input parameters |
| `error_message` | string | Error message |
| `tool_use_id` | string | Unique tool use identifier |

**What We Capture**:
- Activity record with `success=False`
- Error message (truncated to 500 chars)

**What We Inject**: Nothing (no context injection for failures)

---

### Stop

**When**: Agent finishes responding to a user prompt

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |

**What We Capture**:
- Flush buffered activities to SQLite
- End current prompt batch
- Get batch statistics

**What We Process**:
Triggers async LLM processing of the prompt batch:
1. Classifies batch type (feature, exploration, bug_fix, etc.)
2. Extracts observations from activities
3. Stores observations as memories in ChromaDB

**What We Inject**: Nothing (no context injection at stop)

**Response**:
```json
{
  "status": "ok",
  "prompt_batch_id": "batch-uuid-123",
  "prompt_batch_stats": {
    "activity_count": 15,
    "files_touched": 3,
    "tool_counts": {"Read": 8, "Edit": 4, "Bash": 3}
  },
  "processing_scheduled": true
}
```

---

### SessionEnd

**When**: Clean session exit (Ctrl+D, /exit command)

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `agent` | string | Agent name |

**What We Capture**:
- Flush buffered activities
- End any remaining prompt batch
- End session record in SQLite
- Calculate session duration

**What We Process**:
- Queue final prompt batch for processing
- Generate session summary (async LLM call)
- Store session summary as memory

**What We Inject**: Nothing (session is ending)

**Response**:
```json
{
  "status": "ok",
  "observations_captured": 12,
  "tool_calls": 45,
  "files_modified": 8,
  "files_created": 2,
  "duration_minutes": 23.5,
  "activity_stats": {
    "files_touched": 10,
    "tool_counts": {"Read": 20, "Edit": 15, "Bash": 10}
  }
}
```

**Note**: SessionEnd may not fire reliably on unclean exits (Ctrl+C, crash). Background recovery handles these cases.

---

### SubagentStart / SubagentStop

**When**: Parent agent spawns/completes a subagent (Task tool)

**Input Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `agent_id` | string | Subagent identifier |
| `agent_type` | string | Subagent type (explore, bash, etc.) |
| `agent_transcript_path` | string | Path to transcript (stop only) |
| `stop_hook_active` | bool | Whether stop hook was active |

**What We Capture**:
- SubagentStart/SubagentStop Activity records
- Subagent type and identifier
- Transcript path (for future parsing)

**What We Inject**: Nothing

---

## Context Injection Mechanism

Context is injected into the agent's conversation via the `injected_context` or `additionalContext` field in the hook response. The agent reads this and includes it in its context window.

### Injection Limits

Configured in `constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `INJECTION_MAX_CODE_CHUNKS` | 3 | Max code snippets per injection |
| `INJECTION_MAX_LINES_PER_CHUNK` | 50 | Max lines per code chunk |
| `INJECTION_MAX_MEMORIES` | 10 | Max memories per injection |
| `INJECTION_MAX_SESSION_SUMMARIES` | 5 | Max session summaries |

### Confidence Filtering

Search results are filtered by confidence level before injection:

| Confidence | Similarity Score | Usage |
|------------|-----------------|-------|
| `high` | >= 0.75 | Prompt submit, notify context |
| `medium` | >= 0.60 | Post-tool-use file memories |
| `low` | >= 0.45 | Not used for injection |

### Code Formatting

Code chunks are formatted as markdown with syntax highlighting:

```markdown
**filepath** (Lstart-end) - `function_name`
```language
code content here
```
```

Language is auto-detected from file extension using `LANG_MAP`:

| Extension | Language |
|-----------|----------|
| `.py` | python |
| `.ts`, `.tsx` | typescript |
| `.js`, `.jsx` | javascript |
| `.go` | go |
| `.rs` | rust |
| `.rb` | ruby |
| `.java` | java |
| `.kt` | kotlin |
| `.c`, `.h` | c |
| `.cpp`, `.hpp` | cpp |
| `.sh` | bash |
| `.yaml`, `.yml` | yaml |
| `.json` | json |
| `.md` | markdown |
| `.sql` | sql |

---

## Deduplication

Hooks are deduplicated to prevent duplicate processing from multiple hook invocations.
This is especially important for Cursor, which fires every hook twice (see
[Cursor Dual-Hook Behavior](#cursor-dual-hook-behavior)).

**Mechanism**:

1. **Build dedupe key**: `event_name|session_id|unique_parts`
2. **Check cache**: LRU cache of recent keys (max 1000 entries)
3. **Skip if seen**: Return early with cached response if already processed

**Dedupe keys by event type**:

| Event | Unique Parts in Key | Notes |
|-------|---------------------|-------|
| `session-start` | `agent` + `source` | Agent name included — allows both claude and cursor calls through for label correction |
| `prompt-submit` | `generation_id` + `prompt_hash` | Second call with identical prompt is dropped |
| `post-tool-use` | `tool_use_id` | Exact tool invocation match |
| `post-tool-use-failure` | `tool_use_id` | Same as post-tool-use |
| `stop` | `batch_id` (from active batch) | Prevents double-ending the same batch |
| `session-end` | (session_id only) | Only one end per session |
| `subagent-start` | `agent_id` | Subagent lifecycle tracking |
| `subagent-stop` | `agent_id` | Subagent lifecycle tracking |
| `pre-compact` | (session_id only) | One compaction event at a time |

**Session-start special case**: Unlike other events, session-start intentionally does
NOT deduplicate across different agent names for the same session. This allows the
`get_or_create_session` function to update the agent label from `claude` to `cursor`
when Cursor's dual-hook scenario fires both. The second call is idempotent for session
creation (the session already exists) but applies the correct agent label.

---

## Activity Processing Pipeline

```
Hook Event
    │
    ▼
┌─────────────────┐
│ Capture Activity │ ◄── Liberal capture (store everything)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Buffer in Memory │ ◄── Batch inserts for performance
└─────────────────┘
    │
    ▼ (on Stop/SessionEnd)
┌─────────────────┐
│ Flush to SQLite │
└─────────────────┘
    │
    ▼ (async)
┌─────────────────────────┐
│ LLM Batch Classification │ ◄── feature, exploration, bug_fix, etc.
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ LLM Observation Extract  │ ◄── gotcha, decision, discovery, trade_off
└─────────────────────────┘
    │
    ▼
┌─────────────────┐
│ Store in ChromaDB │ ◄── Vector embeddings for semantic search
└─────────────────┘
```

---

## Debugging

### Check Hook Delivery

```bash
# Watch daemon logs for hook events
tail -f .oak/ci/daemon.log | grep -E "SESSION-START|PROMPT|TOOL|STOP|SESSION-END"
```

### Verify Injected Context

```bash
# Look for injection log entries
grep "INJECT:" .oak/ci/daemon.log
```

### Test Hook Manually

```bash
# Test session-start
echo '{"session_id":"test-123","agent":"claude","source":"startup"}' | \
  curl -X POST http://localhost:PORT/api/oak/ci/session-start \
  -H 'Content-Type: application/json' -d @-
```

### Check Deduplication

```bash
# Look for deduped events
grep "Deduped" .oak/ci/daemon.log
```

---

## Related Documentation

- [Session Lifecycle](./session-lifecycle.md) - Session state management and recovery
- [Memory System](./memory.md) - How memories are stored and retrieved
- [Developer API](./developer-api.md) - MCP tools and CLI commands
