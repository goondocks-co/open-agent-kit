# Session Lifecycle Fixes Plan

## Problem Summary

The session lifecycle has multiple bugs causing:
1. Sessions never properly closing (SessionEnd hook not firing)
2. New sessions being incorrectly marked as stale
3. Activities logged to "completed" sessions
4. Old sessions remaining "active" indefinitely

## Root Causes Identified

### 1. SessionEnd Hook Not Firing
**Hypothesis:** Claude Code may not be firing SessionEnd when the session ends, OR the curl command fails silently.

**Investigation needed:**
- Test the SessionEnd hook manually to verify daemon endpoint works
- Check if Claude Code actually fires SessionEnd events
- Add error logging to the hook command

### 2. Stale Session Recovery Bug (CRITICAL)
**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Lines:** 800-810

**Current SQL:**
```sql
SELECT s.id, MAX(a.timestamp_epoch) as last_activity
FROM sessions s
LEFT JOIN activities a ON s.id = a.session_id
WHERE s.status = 'active'
GROUP BY s.id
HAVING last_activity IS NULL OR last_activity < ?
```

**Problem:** `last_activity IS NULL` catches brand new sessions with no activities yet.

**Fix:** Also check session `created_at_epoch` for sessions without activities:
```sql
SELECT s.id, MAX(a.timestamp_epoch) as last_activity, s.created_at_epoch
FROM sessions s
LEFT JOIN activities a ON s.id = a.session_id
WHERE s.status = 'active'
GROUP BY s.id
HAVING (last_activity IS NOT NULL AND last_activity < ?)
    OR (last_activity IS NULL AND s.created_at_epoch < ?)
```

### 3. State Synchronization Issue
**Problem:** In-memory session state and SQLite are independent. Activity logging doesn't check DB status.

**Fix options:**
a) Before logging activities, check if session is still active in DB (adds latency)
b) When marking session as completed in DB, also clear in-memory state
c) Use DB as source of truth, remove in-memory session tracking

**Recommended:** Option (b) - when `recover_stale_sessions` marks a session completed, also notify in-memory state to clear that session.

### 4. No Session Cleanup at Start
**Problem:** New session start doesn't close previous sessions from same agent.

**Fix:** In `hook_session_start`, before creating new session:
1. Find active sessions for this agent that are > 1 hour old
2. Mark them as completed
3. Then create the new session

## Implementation Plan

### Phase 1: Fix Stale Session Recovery (Immediate)
1. Update SQL in `recover_stale_sessions()` to check `created_at_epoch` for sessions without activities
2. Add `created_at_epoch` column if not exists (migration)
3. Add tests for edge case: new session with no activities

### Phase 2: Add Session Cleanup at Start
1. In `hook_session_start`, add logic to close old active sessions
2. Log when closing orphaned sessions
3. Add tests

### Phase 3: Investigate SessionEnd Hook
1. Add verbose logging to SessionEnd hook command
2. Test manually: `echo '{"session_id":"test"}' | curl -X POST localhost:38283/api/oak/ci/session-end -d @-`
3. Check Claude Code documentation for SessionEnd behavior
4. Consider adding fallback: if no activity for 5 minutes, trigger session end check

### Phase 4: State Synchronization
1. When `recover_stale_sessions` runs, also clear in-memory sessions
2. Add periodic sync between in-memory and DB state
3. Consider removing in-memory session tracking entirely (DB as source of truth)

## Files to Modify

1. `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
   - Fix `recover_stale_sessions()` SQL
   - Ensure `created_at_epoch` column exists

2. `src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py`
   - Add session cleanup logic to `hook_session_start()`
   - Add logging for session lifecycle events

3. `src/open_agent_kit/features/codebase_intelligence/activity/processor.py`
   - When calling `recover_stale_sessions`, also clear in-memory state
   - Pass recovered session IDs to state manager

4. `src/open_agent_kit/features/codebase_intelligence/daemon/state.py`
   - Add method to clear sessions by ID
   - Add method to sync with DB state

5. `tests/unit/features/codebase_intelligence/daemon/test_routes_hooks.py`
   - Add tests for session cleanup at start
   - Add tests for stale session edge cases

## Testing Strategy

1. **Unit tests:** Each bug fix has corresponding tests
2. **Integration test:** Full session lifecycle from start to end
3. **Manual test:** Start/stop Claude Code sessions, verify proper cleanup

## Rollback Plan

All changes are additive. If issues arise:
1. Revert to previous `recover_stale_sessions` logic
2. Remove session cleanup from `hook_session_start`
3. State sync can be disabled via config flag

## Success Criteria

- [ ] New sessions are NOT marked stale within first hour
- [ ] SessionEnd properly closes sessions (or fallback recovery works)
- [ ] Activities only logged to active sessions
- [ ] Old sessions properly closed when new session starts
- [ ] All existing tests pass
- [ ] New tests for edge cases pass
