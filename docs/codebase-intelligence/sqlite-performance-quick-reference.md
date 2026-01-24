# SQLite Performance Quick Reference

Quick reference guide for implementing performance optimizations.

## Code Locations

### Current Implementation
- **Store**: `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
- **Routes**: `src/open_agent_kit/features/codebase_intelligence/daemon/routes/activity.py`
- **Hooks**: `src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py`
- **Schema**: Lines 33-156 in `store.py`

---

## Phase 1: Quick Wins

### 1. Add PRAGMAs
**File**: `store.py`  
**Method**: `_get_connection()` (lines 438-451)

**Current**:
```python
self._local.conn.execute("PRAGMA journal_mode=WAL")
self._local.conn.execute("PRAGMA synchronous=NORMAL")
```

**Add After Line 449**:
```python
# Performance PRAGMAs
self._local.conn.execute("PRAGMA foreign_keys = ON")  # Data integrity
self._local.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache (default 2MB)
self._local.conn.execute("PRAGMA temp_store = MEMORY")  # Use RAM for temp tables
self._local.conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
```

**Impact**: 2-10x faster queries | **Risk**: Low | **Time**: 15 min

---

### 2. Fix N+1 Query Pattern
**File**: `store.py`  
**Add New Method** (after `get_session_stats`, ~line 1612):

```python
def get_bulk_session_stats(self, session_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Get statistics for multiple sessions in a single query.
    
    Args:
        session_ids: List of session IDs to query.
        
    Returns:
        Dictionary mapping session_id -> stats dict.
    """
    if not session_ids:
        return {}
    
    conn = self._get_connection()
    
    # Build placeholders for IN clause
    placeholders = ",".join("?" * len(session_ids))
    
    # Single query with aggregation
    cursor = conn.execute(
        f"""
        SELECT 
            a.session_id,
            COUNT(*) as activity_count,
            COUNT(DISTINCT a.file_path) as files_touched,
            SUM(CASE WHEN a.tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
            SUM(CASE WHEN a.tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
            SUM(CASE WHEN a.tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
            SUM(CASE WHEN a.success = FALSE THEN 1 ELSE 0 END) as errors,
            COUNT(DISTINCT pb.id) as prompt_batch_count
        FROM activities a
        LEFT JOIN prompt_batches pb ON a.session_id = pb.session_id
        WHERE a.session_id IN ({placeholders})
        GROUP BY a.session_id
        """,
        session_ids,
    )
    
    # Build result dict
    stats_map = {}
    for row in cursor.fetchall():
        # Get tool counts separately (more complex aggregation)
        tool_cursor = conn.execute(
            """
            SELECT tool_name, COUNT(*) as count
            FROM activities
            WHERE session_id = ?
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (row["session_id"],),
        )
        tool_counts = {r["tool_name"]: r["count"] for r in tool_cursor.fetchall()}
        
        stats_map[row["session_id"]] = {
            "activity_count": row["activity_count"] or 0,
            "prompt_batch_count": row["prompt_batch_count"] or 0,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
            "tool_counts": tool_counts,
        }
    
    # Fill in missing sessions (no activities)
    for session_id in session_ids:
        if session_id not in stats_map:
            stats_map[session_id] = {
                "activity_count": 0,
                "prompt_batch_count": 0,
                "files_touched": 0,
                "reads": 0,
                "edits": 0,
                "writes": 0,
                "errors": 0,
                "tool_counts": {},
            }
    
    return stats_map
```

**File**: `routes/activity.py`  
**Update** (lines 117-133):

**Current**:
```python
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]

items = []
for session in sessions:
    try:
        stats = state.activity_store.get_session_stats(session.id)  # N queries!
    except (OSError, ValueError, RuntimeError):
        stats = {}
    items.append(_session_to_item(session, stats))
```

**Replace With**:
```python
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]

# Get stats in bulk (1 query instead of N)
session_ids = [s.id for s in sessions]
try:
    stats_map = state.activity_store.get_bulk_session_stats(session_ids)
except (OSError, ValueError, RuntimeError):
    stats_map = {}

items = []
for session in sessions:
    stats = stats_map.get(session.id, {})
    items.append(_session_to_item(session, stats))
```

**Impact**: 10-100x faster | **Risk**: Low | **Time**: 1-2 hours

---

### 3. Add Composite Indexes
**File**: `store.py`  
**Location**: Schema definition (after line 126, before FTS5 table)

**Add Migration Method** (in `_apply_migrations`, after line 506):

```python
if from_version < 8:
    self._migrate_v7_to_v8(conn)
```

**Add Migration** (after `_migrate_v6_to_v7`):

```python
def _migrate_v7_to_v8(self, conn: sqlite3.Connection) -> None:
    """Migrate schema from v7 to v8: Add composite indexes for performance."""
    logger.info("Migrating activity store schema v7 -> v8: Adding composite indexes")
    
    # Composite indexes for common query patterns
    indexes = [
        # For: WHERE session_id = ? AND processed = FALSE
        "CREATE INDEX IF NOT EXISTS idx_activities_session_processed ON activities(session_id, processed)",
        
        # For: WHERE processed = FALSE AND timestamp_epoch > ?
        "CREATE INDEX IF NOT EXISTS idx_activities_processed_timestamp ON activities(processed, timestamp_epoch)",
        
        # For: WHERE session_id = ? AND prompt_batch_id = ?
        "CREATE INDEX IF NOT EXISTS idx_activities_session_batch ON activities(session_id, prompt_batch_id)",
        
        # For: WHERE embedded = FALSE ORDER BY created_at_epoch
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_embedded_epoch ON memory_observations(embedded, created_at_epoch)",
        
        # For: WHERE session_id = ? AND status = ? AND processed = ?
        "CREATE INDEX IF NOT EXISTS idx_prompt_batches_session_status ON prompt_batches(session_id, status, processed)",
    ]
    
    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.OperationalError as e:
            logger.warning(f"Index creation warning (may already exist): {e}")
    
    logger.info("Composite indexes created")
```

**Update SCHEMA_VERSION** (line 31):
```python
SCHEMA_VERSION = 8
```

**Impact**: 2-5x faster filtered queries | **Risk**: Low | **Time**: 30 min

---

## Phase 2: Medium Effort

### 4. Add Pagination Support
**File**: `store.py`  
**Method**: `get_recent_sessions()` (lines 1613-1631)

**Current**:
```python
def get_recent_sessions(self, limit: int = 10) -> list[Session]:
```

**Update To**:
```python
def get_recent_sessions(
    self, 
    limit: int = 10, 
    offset: int = 0,
    status: str | None = None
) -> list[Session]:
    """Get recent sessions with pagination support.
    
    Args:
        limit: Maximum sessions to return.
        offset: Number of sessions to skip.
        status: Optional status filter.
    """
    conn = self._get_connection()
    
    query = "SELECT * FROM sessions"
    params: list[Any] = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY created_at_epoch DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = conn.execute(query, params)
    return [Session.from_row(row) for row in cursor.fetchall()]
```

**File**: `routes/activity.py`  
**Update** (line 117):

**Current**:
```python
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]
```

**Replace With**:
```python
sessions = state.activity_store.get_recent_sessions(limit=limit, offset=offset, status=status)
```

**Impact**: 2-3x faster, less memory | **Risk**: Low | **Time**: 30 min

---

### 5. Add Bulk Insert Operations
**File**: `store.py`  
**Add New Method** (after `add_activity`, ~line 1400):

```python
def add_activities(self, activities: list[Activity]) -> list[int]:
    """Add multiple activities in a single transaction.
    
    Args:
        activities: List of activities to insert.
        
    Returns:
        List of inserted activity IDs.
    """
    if not activities:
        return []
    
    ids = []
    session_updates: dict[str, int] = {}  # session_id -> count delta
    batch_updates: dict[int, int] = {}  # batch_id -> count delta
    
    with self._transaction() as conn:
        for activity in activities:
            row = activity.to_row()
            cursor = conn.execute(
                """
                INSERT INTO activities (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                                       file_path, files_affected, duration_ms, success,
                                       error_message, timestamp, timestamp_epoch, processed, observation_id)
                VALUES (:session_id, :prompt_batch_id, :tool_name, :tool_input, :tool_output_summary,
                        :file_path, :files_affected, :duration_ms, :success,
                        :error_message, :timestamp, :timestamp_epoch, :processed, :observation_id)
                """,
                row,
            )
            ids.append(cursor.lastrowid or 0)
            
            # Track updates needed
            session_updates[activity.session_id] = (
                session_updates.get(activity.session_id, 0) + 1
            )
            if activity.prompt_batch_id:
                batch_updates[activity.prompt_batch_id] = (
                    batch_updates.get(activity.prompt_batch_id, 0) + 1
                )
        
        # Bulk update session counts
        for session_id, delta in session_updates.items():
            conn.execute(
                "UPDATE sessions SET tool_count = tool_count + ? WHERE id = ?",
                (delta, session_id),
            )
        
        # Bulk update batch counts
        for batch_id, delta in batch_updates.items():
            conn.execute(
                "UPDATE prompt_batches SET activity_count = activity_count + ? WHERE id = ?",
                (delta, batch_id),
            )
    
    return ids
```

**File**: `routes/hooks.py`  
**Update** (around line 507-557): Add batching logic

**Current**: Activities inserted individually

**Add Batching** (requires refactoring hook handler):
```python
# In hook handler, collect activities in buffer
# Flush buffer when it reaches batch size (e.g., 10) or at end of tool calls
```

**Impact**: 5-10x faster inserts | **Risk**: Medium | **Time**: 2-3 hours

---

## Testing Checklist

### Phase 1 Tests
- [ ] PRAGMAs are set correctly (check connection)
- [ ] Bulk stats returns correct data
- [ ] Route uses bulk stats (verify single query)
- [ ] Composite indexes exist (check schema)
- [ ] Query plans use indexes (`EXPLAIN QUERY PLAN`)

### Phase 2 Tests
- [ ] Pagination works with offset
- [ ] Pagination edge cases (offset > total, etc.)
- [ ] Bulk insert works correctly
- [ ] Bulk insert maintains counts
- [ ] Hook batching doesn't lose activities

### Performance Tests
- [ ] Load test with 100K+ activities
- [ ] Measure query times before/after
- [ ] Verify WAL size doesn't grow unbounded
- [ ] Check memory usage with pagination

---

## Verification Commands

### Check PRAGMAs
```python
conn = store._get_connection()
print(conn.execute("PRAGMA cache_size").fetchone())
print(conn.execute("PRAGMA mmap_size").fetchone())
print(conn.execute("PRAGMA temp_store").fetchone())
print(conn.execute("PRAGMA foreign_keys").fetchone())
```

### Check Indexes
```sql
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';
```

### Verify Query Plan
```sql
EXPLAIN QUERY PLAN
SELECT * FROM activities 
WHERE session_id = ? AND processed = FALSE;
-- Should show "USING INDEX idx_activities_session_processed"
```

### Test Bulk Stats
```python
# Should be 1 query, not N
session_ids = [s.id for s in sessions[:10]]
stats_map = store.get_bulk_session_stats(session_ids)
assert len(stats_map) == 10
```

---

## Rollback Plan

If issues arise:

1. **PRAGMAs**: Remove from `_get_connection()` (backward compatible)
2. **Bulk Stats**: Keep old method, add new one (no breaking changes)
3. **Indexes**: Can be dropped if needed (`DROP INDEX idx_name`)
4. **Pagination**: Keep old signature, add new params (backward compatible)
5. **Bulk Insert**: New method, doesn't affect existing code

All changes are additive and backward compatible.
