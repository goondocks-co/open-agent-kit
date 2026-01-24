# Session Lifecycle Architecture

This document describes the complete session lifecycle for Codebase Intelligence, including hooks, events, background jobs, and state management.

## Overview

Sessions track all activity within an agent invocation. While the diagrams reference Claude Code,
the same lifecycle applies to Cursor and Gemini via equivalent hook events. The lifecycle is driven by:

1. **Hooks** - Events fired by the agent that we respond to
2. **Background Jobs** - Periodic cleanup and processing tasks
3. **State Management** - Dual tracking in memory and SQLite

## Lifecycle Diagram

```mermaid
flowchart TB
    subgraph "Claude Code Process"
        CC_START[User launches Claude Code]
        CC_PROMPT[User sends prompt]
        CC_TOOL[Tool execution]
        CC_STOP[Agent stops responding]
        CC_EXIT_CLEAN[User types /exit or Ctrl+D]
        CC_EXIT_UNCLEAN[User closes terminal / Ctrl+C / crash]
    end

    subgraph "Hooks Layer"
        H_START[SessionStart Hook]
        H_PROMPT[UserPromptSubmit Hook]
        H_TOOL[PostToolUse Hook]
        H_STOP[Stop Hook]
        H_END[SessionEnd Hook]
    end

    subgraph "Daemon API"
        API_START[POST /session-start]
        API_PROMPT[POST /prompt-submit]
        API_TOOL[POST /post-tool-use]
        API_STOP[POST /stop]
        API_END[POST /session-end]
    end

    subgraph "State Management"
        MEM[In-Memory State<br/>SessionInfo dict]
        DB[(SQLite Database<br/>sessions table)]
    end

    subgraph "Background Jobs<br/>(every 60 seconds)"
        JOB_STUCK[Recover stuck batches<br/>5 min timeout]
        JOB_STALE[Recover stale sessions<br/>1 hour timeout]
        JOB_ORPHAN[Recover orphaned activities]
        JOB_PROCESS[Process pending batches]
    end

    %% Normal flow
    CC_START --> H_START --> API_START
    API_START --> |"Create session"| MEM
    API_START --> |"Create session"| DB

    CC_PROMPT --> H_PROMPT --> API_PROMPT
    API_PROMPT --> |"End prev batch<br/>Create new batch"| DB
    API_PROMPT --> |"Update batch ID"| MEM

    CC_TOOL --> H_TOOL --> API_TOOL
    API_TOOL --> |"Record activity"| DB
    API_TOOL --> |"Update counters"| MEM

    CC_STOP --> H_STOP --> API_STOP
    API_STOP --> |"End prompt batch"| DB
    API_STOP --> |"Queue for processing"| JOB_PROCESS

    %% Clean exit
    CC_EXIT_CLEAN --> H_END --> API_END
    API_END --> |"End session<br/>status=completed"| DB
    API_END --> |"Remove session"| MEM

    %% Unclean exit - NO hook fires
    CC_EXIT_UNCLEAN -.-> |"NO HOOK FIRES"| MEM

    %% Background recovery handles unclean exits
    JOB_STALE --> |"Mark completed<br/>after 1 hour inactive"| DB

    %% Styling
    classDef hook fill:#e1f5fe,stroke:#01579b
    classDef api fill:#f3e5f5,stroke:#4a148c
    classDef state fill:#e8f5e9,stroke:#1b5e20
    classDef job fill:#fff3e0,stroke:#e65100
    classDef claude fill:#fce4ec,stroke:#880e4f

    class H_START,H_PROMPT,H_TOOL,H_STOP,H_END hook
    class API_START,API_PROMPT,API_TOOL,API_STOP,API_END api
    class MEM,DB state
    class JOB_STUCK,JOB_STALE,JOB_ORPHAN,JOB_PROCESS job
    class CC_START,CC_PROMPT,CC_TOOL,CC_STOP,CC_EXIT_CLEAN,CC_EXIT_UNCLEAN claude
```

## Session States

```mermaid
stateDiagram-v2
    [*] --> active: SessionStart hook
    active --> active: Activities logged
    active --> completed: SessionEnd hook (clean exit)
    active --> completed: Stale recovery (1hr inactive)
    completed --> [*]

    note right of active
        In-memory: SessionInfo exists
        SQLite: status = 'active'
    end note

    note right of completed
        In-memory: SessionInfo removed
        SQLite: status = 'completed'
    end note
```

## Hook Events

| Hook | When Fired | What We Do | Notes |
|------|------------|------------|-------|
| `SessionStart` | Claude Code launches | Create session in memory + DB, inject context | Includes `source`: startup, resume, clear, compact |
| `UserPromptSubmit` | User sends a prompt | End previous batch, create new batch, search context | Creates prompt batches for grouping activities |
| `PostToolUse` | After each tool runs | Record activity to DB, update counters | Liberal capture for LLM processing |
| `Stop` | Agent finishes responding | End current prompt batch, queue for processing | Triggers async observation extraction |
| `SessionEnd` | Clean exit (/exit, Ctrl+D) | End session, generate summary | **BUG: May not fire reliably** |

## Background Jobs

All jobs run every 60 seconds via `schedule_background_processing()`:

### 1. Recover Stuck Batches
- **Timeout**: 5 minutes (`BATCH_ACTIVE_TIMEOUT_SECONDS`)
- **Condition**: Prompt batch with `status='active'` and no activity for 5+ minutes
- **Action**: Mark batch as `status='completed'`

### 2. Recover Stale Sessions
- **Timeout**: 1 hour (`SESSION_INACTIVE_TIMEOUT_SECONDS`)
- **Condition**: Session with `status='active'` AND:
  - Has activities: `last_activity < cutoff` (1 hour ago)
  - No activities: `created_at_epoch < cutoff` (created 1+ hour ago)
- **Action**: Mark session as `status='completed'`
- **Purpose**: Handles unclean exits where SessionEnd never fires

### 3. Recover Orphaned Activities
- **Condition**: Activities with `prompt_batch_id = NULL`
- **Action**: Associate with most recent batch or create recovery batch

### 4. Process Pending Batches
- **Condition**: Completed batches not yet processed
- **Action**: Send to LLM for observation extraction, store to ChromaDB

## Session Start Behavior

When a new session starts:

1. **We do NOT close other active sessions** - Multiple concurrent sessions are valid (multiple terminal windows)
2. **We create a new session** with unique UUID
3. **If same session_id provided** (e.g., daemon restart), we resume the existing session
4. **Context is injected** based on `source` parameter:
   - `startup`: Full context (memories, stats)
   - `resume`: Minimal context
   - `clear`/`compact`: Varies

```mermaid
flowchart LR
    START[SessionStart received] --> CHECK{session_id<br/>provided?}
    CHECK -->|No| GEN[Generate UUID]
    CHECK -->|Yes| LOOKUP[Lookup in DB]

    GEN --> CREATE[Create new session]
    LOOKUP --> EXISTS{Exists?}
    EXISTS -->|No| CREATE
    EXISTS -->|Yes| STATUS{Status?}
    STATUS -->|active| RESUME[Resume session]
    STATUS -->|completed| REACTIVATE[Reactivate session]

    CREATE --> MEM_CREATE[Add to in-memory state]
    RESUME --> MEM_UPDATE[Update in-memory state]
    REACTIVATE --> MEM_UPDATE

    MEM_CREATE --> INJECT[Inject context]
    MEM_UPDATE --> INJECT
```

## Known Issues

### SessionEnd Hook Not Firing
**Status**: Under investigation

Even when using `/exit` to cleanly close Claude Code, the SessionEnd hook does not appear to fire. The hook is correctly configured in `.claude/settings.json` and the endpoint works when tested manually.

**Workaround**: The stale session recovery job (1-hour timeout) will eventually close orphaned sessions.

**Investigation needed**:
- Verify Claude Code actually fires SessionEnd events
- Add logging to hook command to diagnose failures
- Consider opening a bug report with Anthropic

### State Synchronization
In-memory state and SQLite database can become desynchronized if:
- Daemon restarts mid-session (in-memory state lost)
- Stale recovery marks session completed while still active in memory

**Mitigation**: Activities continue to log based on session_id regardless of database status.

## Configuration

Key constants in `constants.py`:

```python
SESSION_INACTIVE_TIMEOUT_SECONDS = 3600  # 1 hour
BATCH_ACTIVE_TIMEOUT_SECONDS = 300       # 5 minutes
BACKGROUND_PROCESSING_INTERVAL = 60      # seconds
```

## Debugging

### Check session states
```bash
sqlite3 .oak/ci/activities.db "SELECT id, status, started_at, ended_at FROM sessions ORDER BY started_at DESC LIMIT 5;"
```

### Check daemon logs for lifecycle events
```bash
grep -E "Session start|Session end|Recovered" .oak/ci/daemon.log | tail -20
```

### Manually test SessionEnd
```bash
echo '{"session_id":"test-123","agent":"claude"}' | curl -s -X POST http://localhost:PORT/api/oak/ci/session-end -H 'Content-Type: application/json' -d @-
```

### Force close a session
```bash
sqlite3 .oak/ci/activities.db "UPDATE sessions SET status='completed', ended_at=datetime('now') WHERE id='SESSION_ID';"
```
