# Hooks Reference

This document provides a comprehensive reference for the Codebase Intelligence hooks system, including what each hook captures, what context gets injected, and how the system processes agent activity.

## Overview

Codebase Intelligence integrates with AI agents (Claude Code, Cursor, Gemini) via **hooks** - events fired by the agent that the CI daemon responds to. The daemon:

1. **Captures** agent activity (tool calls, prompts, sessions)
2. **Processes** activity to extract observations using LLM classification
3. **Injects** relevant context back into the agent's conversation

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

## Hook Configuration

Hooks are configured in `.claude/settings.json` (Claude Code) or `.cursor/hooks.json` (Cursor). Example for Claude Code:

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
- Create session record in SQLite (idempotent)
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

Hooks are deduplicated to prevent duplicate processing from multiple hook invocations:

1. **Build dedupe key**: `event_name|session_id|unique_parts`
2. **Check cache**: LRU cache of recent keys (max 1000 entries)
3. **Skip if seen**: Return early if already processed

Deduplication uses:
- `tool_use_id` for PostToolUse
- `generation_id + prompt_hash` for UserPromptSubmit
- `agent_id` for SubagentStart/Stop
- `session_id + source` for SessionStart

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
