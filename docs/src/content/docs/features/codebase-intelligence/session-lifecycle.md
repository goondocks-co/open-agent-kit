---
title: Session Lifecycle
description: Complete session lifecycle including hooks, events, background jobs, and state management.
sidebar:
  order: 4
---

Sessions track all activity within an agent invocation. While the diagrams reference Claude Code, the same lifecycle applies to Cursor and Gemini via equivalent hook events.

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

    CC_EXIT_CLEAN --> H_END --> API_END
    API_END --> |"End session<br/>status=completed"| DB
    API_END --> |"Remove session"| MEM

    CC_EXIT_UNCLEAN -.-> |"NO HOOK FIRES"| MEM

    JOB_STALE --> |"Mark completed<br/>after 1 hour inactive"| DB
```

## Session States

```mermaid
stateDiagram-v2
    [*] --> active: SessionStart hook
    active --> active: Activities logged
    active --> completed: SessionEnd hook (clean exit)
    active --> completed: Stale recovery (1hr inactive)
    completed --> [*]
```

## Hook Events

| Hook | When Fired | What We Do | Notes |
|------|------------|------------|-------|
| `SessionStart` | Agent launches | Create session in memory + DB, inject context | Includes `source`: startup, resume, clear, compact |
| `UserPromptSubmit` | User sends a prompt | End previous batch, create new batch, search context | Creates prompt batches for grouping activities |
| `PostToolUse` | After each tool runs | Record activity to DB, update counters | Liberal capture for LLM processing |
| `Stop` | Agent finishes responding | End current prompt batch, queue for processing | Triggers async observation extraction |
| `SessionEnd` | Clean exit (/exit, Ctrl+D) | End session, generate summary | May not fire on unclean exits |

## Background Jobs

All jobs run every 60 seconds:

### 1. Recover Stuck Batches
- **Timeout**: 5 minutes
- **Condition**: Prompt batch with `status='active'` and no activity for 5+ minutes
- **Action**: Mark batch as `status='completed'`

### 2. Recover Stale Sessions
- **Timeout**: 1 hour
- **Condition**: Session with `status='active'` and no recent activity
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

1. **We do NOT close other active sessions** — multiple concurrent sessions are valid (multiple terminal windows)
2. **We create a new session** with unique UUID
3. **If same session_id provided** (e.g., daemon restart), we resume the existing session
4. **Context is injected** based on `source` parameter:
   - `startup`: Full context (memories, stats)
   - `resume`: Minimal context
   - `clear`/`compact`: Varies

## Configuration

Key constants:

```python
SESSION_INACTIVE_TIMEOUT_SECONDS = 3600  # 1 hour
BATCH_ACTIVE_TIMEOUT_SECONDS = 300       # 5 minutes
BACKGROUND_PROCESSING_INTERVAL = 60      # seconds
```

## Debugging

```bash
# Check session states
sqlite3 .oak/ci/activities.db \
  "SELECT id, status, started_at, ended_at FROM sessions ORDER BY started_at DESC LIMIT 5;"

# Check daemon logs for lifecycle events
grep -E "Session start|Session end|Recovered" .oak/ci/daemon.log | tail -20

# Force close a session
sqlite3 .oak/ci/activities.db \
  "UPDATE sessions SET status='completed', ended_at=datetime('now') WHERE id='SESSION_ID';"
```
