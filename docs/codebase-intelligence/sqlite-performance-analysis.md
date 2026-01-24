# SQLite Database Performance Analysis & Recommendations

## Executive Summary

This document analyzes SQLite database operations in the Codebase Intelligence feature and provides recommendations for optimizing performance at scale. The database is expected to grow significantly with:
- High-volume activity logging (every tool execution)
- Large numbers of sessions, prompt batches, and activities
- Memory observations that accumulate over time
- Full-text search operations

## Current State

### Database Schema
- **sessions**: Session metadata (~100s-1000s of records)
- **prompt_batches**: Activity batches per session (~1000s-10000s)
- **activities**: Raw tool executions (~100,000s-1,000,000s)
- **memory_observations**: Extracted memories (~10,000s-100,000s)
- **activities_fts**: FTS5 virtual table for full-text search

### Current Configuration
- **WAL mode**: ✅ Enabled (`PRAGMA journal_mode=WAL`)
- **Synchronous**: ✅ NORMAL (`PRAGMA synchronous=NORMAL`)
- **Foreign Keys**: ❌ **NOT ENABLED** (defined but not enforced)
- **Connection**: Thread-local connections with 30s timeout
- **Indexes**: Basic indexes on common query columns

## Performance Issues Identified

### 1. Missing PRAGMA Optimizations ⚠️ HIGH IMPACT

**Issue**: Several important SQLite performance PRAGMAs are not configured.

**Current State**:
```python
# Only these are set:
PRAGMA journal_mode=WAL
PRAGMA synchronous=NORMAL
```

**Missing Optimizations**:
- `PRAGMA foreign_keys = ON` - Data integrity (already identified in todos)
- `PRAGMA cache_size = -64000` - Increase cache (default is 2000 pages)
- `PRAGMA temp_store = MEMORY` - Use memory for temp tables
- `PRAGMA mmap_size = 268435456` - Use memory-mapped I/O (256MB)
- `PRAGMA optimize` - Run periodically for query planner optimization

**Impact**: 
- **Cache size**: Default 2MB cache is too small for large databases. Increasing to 64MB can improve query performance 10-50x for repeated queries.
- **Memory-mapped I/O**: Can improve read performance by 2-5x for large databases.
- **Temp store**: Reduces disk I/O for sorting/aggregation operations.

**Recommendation**: Add these PRAGMAs to `_get_connection()`:
```python
def _get_connection(self) -> sqlite3.Connection:
    if not hasattr(self._local, "conn") or self._local.conn is None:
        self._local.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0,
        )
        self._local.conn.row_factory = sqlite3.Row
        
        # Performance PRAGMAs
        self._local.conn.execute("PRAGMA journal_mode=WAL")
        self._local.conn.execute("PRAGMA synchronous=NORMAL")
        self._local.conn.execute("PRAGMA foreign_keys = ON")  # Data integrity
        self._local.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        self._local.conn.execute("PRAGMA temp_store = MEMORY")  # Use RAM for temp
        self._local.conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
        
        # Run optimize periodically (every 1000 writes or daily)
        # Can be done in background thread
```

**Estimated Improvement**: 2-10x faster queries for large datasets

---

### 2. N+1 Query Pattern ⚠️ HIGH IMPACT

**Issue**: Session listing makes N+1 queries (1 for sessions, N for stats).

**Location**: `daemon/routes/activity.py:128-133`

**Current Code**:
```python
for session in sessions:
    stats = state.activity_store.get_session_stats(session.id)  # N queries!
    items.append(_session_to_item(session, stats))
```

**Impact**:
- 10 sessions: 11 queries (~50-100ms)
- 100 sessions: 101 queries (~500ms-1s)
- 1000 sessions: 1001 queries (~5-10s)

**Recommendation**: Add bulk stats method:

```python
# In activity/store.py
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
        stats_map[row["session_id"]] = {
            "activity_count": row["activity_count"] or 0,
            "prompt_batch_count": row["prompt_batch_count"] or 0,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
            "tool_counts": {},  # Can add if needed
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

**Usage in route**:
```python
# Get all sessions
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]

# Get stats in bulk
stats_map = state.activity_store.get_bulk_session_stats([s.id for s in sessions])

# Build response
items = [_session_to_item(session, stats_map.get(session.id, {})) 
         for session in sessions]
```

**Estimated Improvement**: 10-100x faster for session listing

---

### 3. Missing Composite Indexes ⚠️ MEDIUM IMPACT

**Issue**: Common query patterns use multiple WHERE clauses but indexes are single-column.

**Current Indexes**:
```sql
CREATE INDEX idx_activities_session ON activities(session_id);
CREATE INDEX idx_activities_processed ON activities(processed);
CREATE INDEX idx_activities_timestamp ON activities(timestamp_epoch);
```

**Common Query Patterns**:
1. `WHERE session_id = ? AND processed = FALSE` - Used frequently
2. `WHERE processed = FALSE AND timestamp_epoch > ?` - Background processing
3. `WHERE session_id = ? AND prompt_batch_id = ?` - Batch queries
4. `WHERE embedded = FALSE ORDER BY created_at_epoch` - Rebuild operations

**Recommendation**: Add composite indexes:

```sql
-- For unprocessed activities by session
CREATE INDEX IF NOT EXISTS idx_activities_session_processed 
    ON activities(session_id, processed);

-- For background processing (processed + timestamp)
CREATE INDEX IF NOT EXISTS idx_activities_processed_timestamp 
    ON activities(processed, timestamp_epoch);

-- For batch queries
CREATE INDEX IF NOT EXISTS idx_activities_session_batch 
    ON activities(session_id, prompt_batch_id);

-- For unembedded observations (rebuild operations)
CREATE INDEX IF NOT EXISTS idx_memory_observations_embedded_epoch 
    ON memory_observations(embedded, created_at_epoch);

-- For session prompt batches
CREATE INDEX IF NOT EXISTS idx_prompt_batches_session_status 
    ON prompt_batches(session_id, status, processed);
```

**Impact**: 
- Query planner can use index-only scans instead of table scans
- 2-5x faster for filtered queries
- Reduced I/O for common operations

**Estimated Improvement**: 2-5x faster for filtered queries

---

### 4. Inefficient Pagination ⚠️ MEDIUM IMPACT

**Issue**: `get_recent_sessions()` fetches all records then slices in Python.

**Current Code** (`store.py:1613-1631`):
```python
def get_recent_sessions(self, limit: int = 10) -> list[Session]:
    conn = self._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM sessions
        ORDER BY created_at_epoch DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]
```

**Problem**: Route code does `get_recent_sessions(limit + offset)` then slices:
```python
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]  # Python-side slicing
```

**Impact**: 
- Fetches more data than needed
- Transfers unnecessary rows from SQLite to Python
- Wastes memory for large offsets

**Recommendation**: Add offset support to database method:

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
    
    query = """
        SELECT * FROM sessions
    """
    params: list[Any] = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY created_at_epoch DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = conn.execute(query, params)
    return [Session.from_row(row) for row in cursor.fetchall()]
```

**Estimated Improvement**: 2-3x faster for paginated queries, reduced memory usage

---

### 5. Missing Bulk Insert Operations ⚠️ MEDIUM IMPACT

**Issue**: Activities are inserted one-at-a-time, causing transaction overhead.

**Current Code** (`store.py:1367-1400`):
```python
def add_activity(self, activity: Activity) -> int:
    with self._transaction() as conn:
        # Insert activity
        cursor = conn.execute("INSERT INTO activities ...", row)
        # Update session count
        conn.execute("UPDATE sessions SET tool_count = tool_count + 1 ...")
        # Update batch count
        conn.execute("UPDATE prompt_batches SET activity_count = activity_count + 1 ...")
    return cursor.lastrowid
```

**Impact**: 
- Each activity = 1 transaction commit
- High overhead for rapid tool execution
- FTS trigger fires for each insert

**Recommendation**: Add bulk insert method:

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
                INSERT INTO activities (...)
                VALUES (...)
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

**Usage**: Hook can batch activities and insert in chunks:
```python
# In hook handler
activity_buffer = []
for tool_call in tool_calls:
    activity_buffer.append(Activity(...))
    if len(activity_buffer) >= 10:  # Batch size
        store.add_activities(activity_buffer)
        activity_buffer = []
if activity_buffer:
    store.add_activities(activity_buffer)
```

**Estimated Improvement**: 5-10x faster for high-frequency tool execution

---

### 6. FTS5 Trigger Performance ⚠️ LOW-MEDIUM IMPACT

**Issue**: FTS5 triggers fire on every INSERT/UPDATE/DELETE, which can be slow for bulk operations.

**Current Triggers**: 
- `activities_ai` - Fires on every INSERT
- `activities_au` - Fires on every UPDATE (does delete + insert)
- `activities_ad` - Fires on every DELETE

**Impact**: 
- Each activity insert triggers FTS update
- Bulk inserts become slower due to trigger overhead
- FTS index can become fragmented

**Recommendation**: 
1. **For bulk inserts**: Temporarily disable triggers, rebuild FTS after:
```python
def add_activities_bulk(self, activities: list[Activity]) -> list[int]:
    """Bulk insert with FTS optimization."""
    with self._transaction() as conn:
        # Disable triggers temporarily
        conn.execute("DROP TRIGGER IF EXISTS activities_ai")
        conn.execute("DROP TRIGGER IF EXISTS activities_au")
        
        # Bulk insert
        ids = self._bulk_insert_activities(conn, activities)
        
        # Rebuild FTS index
        conn.execute("INSERT INTO activities_fts(activities_fts) VALUES('rebuild')")
        
        # Recreate triggers
        # ... recreate trigger SQL ...
    
    return ids
```

2. **Periodic FTS optimization**: Run `INSERT INTO activities_fts(activities_fts) VALUES('optimize')` periodically (daily/weekly).

**Estimated Improvement**: 2-3x faster for bulk inserts

---

### 7. Missing Query Result Caching ⚠️ LOW IMPACT (but easy win)

**Issue**: Repeated queries (e.g., session stats, counts) are executed every time.

**Recommendation**: Add simple in-memory cache for frequently accessed data:

```python
from functools import lru_cache
from time import time

class ActivityStore:
    def __init__(self, db_path: Path):
        # ... existing code ...
        self._stats_cache: dict[str, tuple[dict, float]] = {}
        self._cache_ttl = 60.0  # 60 seconds
    
    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get stats with caching."""
        cache_key = f"stats:{session_id}"
        now = time()
        
        # Check cache
        if cache_key in self._stats_cache:
            cached_stats, cached_time = self._stats_cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_stats
        
        # Query database
        stats = self._get_session_stats_from_db(session_id)
        
        # Update cache
        self._stats_cache[cache_key] = (stats, now)
        
        # Clean old cache entries periodically
        if len(self._stats_cache) > 1000:
            self._stats_cache = {
                k: v for k, v in self._stats_cache.items()
                if now - v[1] < self._cache_ttl
            }
        
        return stats
```

**Estimated Improvement**: 10-100x faster for repeated queries

---

### 8. Database Vacuum & Analyze ⚠️ LOW IMPACT (maintenance)

**Issue**: SQLite databases can become fragmented over time, especially with many DELETE operations.

**Recommendation**: Add periodic maintenance:

```python
def optimize_database(self) -> None:
    """Run database optimization (vacuum + analyze).
    
    Should be called periodically (weekly/monthly) or after large deletions.
    """
    logger.info("Optimizing database (vacuum + analyze)...")
    
    conn = self._get_connection()
    
    # Analyze to update query planner statistics
    conn.execute("ANALYZE")
    
    # Vacuum to reclaim space and defragment
    conn.execute("VACUUM")
    
    # Rebuild FTS index
    conn.execute("INSERT INTO activities_fts(activities_fts) VALUES('rebuild')")
    
    logger.info("Database optimization complete")
```

**Estimated Improvement**: Prevents gradual performance degradation

---

## Summary of Recommendations

### High Priority (Immediate Impact)
1. ✅ **Add missing PRAGMAs** (cache_size, mmap_size, temp_store, foreign_keys)
2. ✅ **Fix N+1 query pattern** (bulk session stats)
3. ✅ **Add composite indexes** (common query patterns)

### Medium Priority (Significant Improvement)
4. ✅ **Add pagination support** (offset in SQL, not Python)
5. ✅ **Add bulk insert operations** (reduce transaction overhead)
6. ✅ **Optimize FTS triggers** (bulk operations)

### Low Priority (Nice to Have)
7. ✅ **Add query caching** (repeated queries)
8. ✅ **Periodic maintenance** (vacuum + analyze)

## Implementation Priority

**Phase 1** (Quick wins, high impact):
- Add PRAGMAs
- Fix N+1 queries
- Add composite indexes

**Phase 2** (Medium effort, good ROI):
- Pagination improvements
- Bulk insert operations

**Phase 3** (Polish):
- Query caching
- Maintenance routines

## Testing Recommendations

1. **Load testing**: Test with 100K+ activities, 10K+ sessions
2. **Query profiling**: Use `EXPLAIN QUERY PLAN` to verify index usage
3. **Benchmark before/after**: Measure query times for common operations
4. **Monitor WAL size**: Ensure WAL doesn't grow unbounded

## Monitoring

Add metrics for:
- Query execution time (p50, p95, p99)
- Database size
- WAL file size
- Cache hit rates (if implementing caching)
- Index usage (via EXPLAIN QUERY PLAN)

## Notes

- All changes should be backward compatible
- Consider adding feature flags for new optimizations
- Test migrations carefully (especially PRAGMA changes)
- Document PRAGMA settings in code comments
