# SQLite Performance Analysis Summary

**Date**: January 23, 2026  
**Status**: Analysis Complete - Ready for Discussion

## Overview

This document summarizes the SQLite database performance analysis for the Codebase Intelligence feature. The database handles high-volume activity logging and is expected to scale to:
- **100,000s - 1,000,000s** of activities (tool executions)
- **1,000s - 10,000s** of prompt batches
- **100s - 1,000s** of sessions
- **10,000s - 100,000s** of memory observations

## Current Implementation Status

### ✅ What's Working Well
- **WAL mode enabled**: Good for concurrent reads/writes
- **Basic indexes**: Single-column indexes on common query columns
- **Thread-local connections**: Prevents connection contention
- **FTS5 full-text search**: Properly configured with triggers

### ⚠️ Critical Issues Found

#### 1. **N+1 Query Pattern** (HIGH PRIORITY)
**Location**: `daemon/routes/activity.py:128-130`

**Problem**: For N sessions, makes N+1 queries (1 for sessions, N for stats)
```python
for session in sessions:
    stats = state.activity_store.get_session_stats(session.id)  # N queries!
```

**Impact**:
- 10 sessions: 11 queries (~50-100ms)
- 100 sessions: 101 queries (~500ms-1s)  
- 1000 sessions: 1001 queries (~5-10s) ❌

**Fix**: Implement `get_bulk_session_stats()` method (see detailed doc)

**Effort**: Low | **Impact**: Very High | **ROI**: ⭐⭐⭐⭐⭐

---

#### 2. **Missing Performance PRAGMAs** (HIGH PRIORITY)
**Location**: `activity/store.py:_get_connection()`

**Current**: Only WAL and synchronous are set
```python
PRAGMA journal_mode=WAL
PRAGMA synchronous=NORMAL
```

**Missing**:
- `PRAGMA foreign_keys = ON` - Data integrity (already in todos)
- `PRAGMA cache_size = -64000` - 64MB cache (default is 2MB)
- `PRAGMA temp_store = MEMORY` - Use RAM for temp tables
- `PRAGMA mmap_size = 268435456` - 256MB memory-mapped I/O

**Impact**: 
- Cache: 10-50x faster for repeated queries
- MMAP: 2-5x faster reads for large databases
- Temp store: Reduced disk I/O

**Effort**: Very Low | **Impact**: High | **ROI**: ⭐⭐⭐⭐⭐

---

#### 3. **Missing Composite Indexes** (MEDIUM-HIGH PRIORITY)
**Location**: Schema definition in `activity/store.py`

**Problem**: Common queries use multiple WHERE clauses but only single-column indexes exist

**Missing Indexes**:
```sql
-- For: WHERE session_id = ? AND processed = FALSE
CREATE INDEX idx_activities_session_processed ON activities(session_id, processed);

-- For: WHERE processed = FALSE AND timestamp_epoch > ?
CREATE INDEX idx_activities_processed_timestamp ON activities(processed, timestamp_epoch);

-- For: WHERE session_id = ? AND prompt_batch_id = ?
CREATE INDEX idx_activities_session_batch ON activities(session_id, prompt_batch_id);

-- For: WHERE embedded = FALSE ORDER BY created_at_epoch
CREATE INDEX idx_memory_observations_embedded_epoch ON memory_observations(embedded, created_at_epoch);

-- For: WHERE session_id = ? AND status = ? AND processed = ?
CREATE INDEX idx_prompt_batches_session_status ON prompt_batches(session_id, status, processed);
```

**Impact**: 2-5x faster for filtered queries, index-only scans instead of table scans

**Effort**: Low | **Impact**: Medium-High | **ROI**: ⭐⭐⭐⭐

---

#### 4. **Inefficient Pagination** (MEDIUM PRIORITY)
**Location**: `activity/store.py:get_recent_sessions()` and `routes/activity.py:117`

**Problem**: Fetches `limit + offset` records, then slices in Python
```python
sessions = state.activity_store.get_recent_sessions(limit=limit + offset)
sessions = sessions[offset : offset + limit]  # Python-side slicing ❌
```

**Fix**: Add `OFFSET` support to SQL query

**Impact**: 2-3x faster for paginated queries, reduced memory usage

**Effort**: Low | **Impact**: Medium | **ROI**: ⭐⭐⭐

---

#### 5. **No Bulk Insert Operations** (MEDIUM PRIORITY)
**Location**: `activity/store.py:add_activity()` and `routes/hooks.py:557`

**Problem**: Activities inserted one-at-a-time, each with its own transaction
```python
# Called individually for each tool execution
state.activity_store.add_activity(activity)  # 1 transaction per activity
```

**Impact**: 
- High transaction overhead
- FTS trigger fires for each insert
- Slow for rapid tool execution

**Fix**: Add `add_activities()` bulk method, batch in hook handler

**Effort**: Medium | **Impact**: Medium | **ROI**: ⭐⭐⭐

---

#### 6. **FTS5 Trigger Overhead** (LOW-MEDIUM PRIORITY)
**Location**: FTS5 triggers in schema

**Problem**: Triggers fire on every INSERT/UPDATE/DELETE, slow for bulk operations

**Fix**: 
- Disable triggers during bulk inserts
- Rebuild FTS index after bulk operations
- Periodic FTS optimization

**Effort**: Medium | **Impact**: Low-Medium | **ROI**: ⭐⭐

---

#### 7. **No Query Result Caching** (LOW PRIORITY)
**Location**: `activity/store.py:get_session_stats()`

**Problem**: Repeated queries execute every time (e.g., session stats)

**Fix**: Add simple in-memory cache with TTL

**Effort**: Low | **Impact**: Low (but easy win) | **ROI**: ⭐⭐

---

#### 8. **No Database Maintenance** (LOW PRIORITY)
**Location**: No maintenance routines exist

**Problem**: Database can become fragmented over time

**Fix**: Add periodic `VACUUM` and `ANALYZE` operations

**Effort**: Low | **Impact**: Low (prevents degradation) | **ROI**: ⭐⭐

---

## Recommended Implementation Plan

### Phase 1: Quick Wins (High Impact, Low Effort) ⚡
**Estimated Time**: 2-4 hours  
**Expected Improvement**: 10-50x faster queries

1. ✅ **Add missing PRAGMAs** (30 min)
   - Add cache_size, mmap_size, temp_store, foreign_keys
   - Update `_get_connection()` method

2. ✅ **Fix N+1 query pattern** (1-2 hours)
   - Implement `get_bulk_session_stats()` method
   - Update route to use bulk method
   - Add tests

3. ✅ **Add composite indexes** (1 hour)
   - Add migration to create composite indexes
   - Test query plans with `EXPLAIN QUERY PLAN`

**Total Phase 1 Impact**: 
- Session listing: 10-100x faster
- Common queries: 2-10x faster
- Overall: Significant improvement with minimal risk

---

### Phase 2: Medium Effort (Good ROI) 📈
**Estimated Time**: 4-6 hours  
**Expected Improvement**: 2-10x faster inserts/queries

4. ✅ **Add pagination support** (1 hour)
   - Add offset parameter to `get_recent_sessions()`
   - Update route to use SQL offset
   - Test pagination edge cases

5. ✅ **Add bulk insert operations** (2-3 hours)
   - Implement `add_activities()` method
   - Add batching logic to hook handler
   - Test bulk insert performance
   - Handle FTS trigger optimization

**Total Phase 2 Impact**:
- Pagination: 2-3x faster, less memory
- Activity inserts: 5-10x faster for rapid tool execution

---

### Phase 3: Polish (Nice to Have) ✨
**Estimated Time**: 2-3 hours

6. ✅ **Add query caching** (1-2 hours)
   - Implement TTL-based cache
   - Add cache invalidation on updates
   - Monitor cache hit rates

7. ✅ **Add maintenance routines** (1 hour)
   - Add `optimize_database()` method
   - Schedule periodic maintenance
   - Add monitoring/logging

---

## Risk Assessment

### Low Risk Changes ✅
- Adding PRAGMAs (backward compatible)
- Adding indexes (read-only, can be done online)
- Adding bulk methods (new methods, doesn't break existing code)
- Adding pagination support (extends existing method)

### Medium Risk Changes ⚠️
- Modifying hook handler for batching (need to test carefully)
- FTS trigger optimization (need to ensure FTS stays in sync)

### Testing Requirements
1. **Load testing**: Test with 100K+ activities, 10K+ sessions
2. **Query profiling**: Use `EXPLAIN QUERY PLAN` to verify index usage
3. **Benchmark before/after**: Measure query times for common operations
4. **WAL monitoring**: Ensure WAL doesn't grow unbounded
5. **Integration tests**: Verify bulk operations work correctly

---

## Expected Performance Improvements

### Before Optimizations
- Session listing (100 sessions): ~500ms-1s
- Session stats query: ~5-10ms per session
- Activity insert: ~1-2ms per activity
- Filtered queries: Full table scans

### After Phase 1 Optimizations
- Session listing (100 sessions): ~10-50ms ⚡ (10-100x faster)
- Session stats query: ~0.1ms per session (bulk query)
- Activity insert: ~1-2ms per activity (no change yet)
- Filtered queries: Index-only scans (2-5x faster)

### After Phase 2 Optimizations
- Session listing: Same as Phase 1
- Session stats query: Same as Phase 1
- Activity insert: ~0.1-0.2ms per activity (5-10x faster with batching)
- Pagination: 2-3x faster, less memory

---

## Monitoring Recommendations

Add metrics for:
- Query execution time (p50, p95, p99)
- Database size (file size, WAL size)
- Cache hit rates (if implementing caching)
- Index usage (via `EXPLAIN QUERY PLAN`)
- Bulk insert batch sizes and frequencies

---

## Questions for Discussion

1. **Priority**: Should we implement all of Phase 1, or prioritize specific items?
2. **Batching Strategy**: For bulk inserts, what batch size makes sense? (10? 50? 100?)
3. **Caching**: Is in-memory caching sufficient, or should we consider Redis for distributed scenarios?
4. **Maintenance**: Should database optimization be manual, scheduled, or automatic?
5. **Foreign Keys**: Should we enable foreign keys immediately (data integrity) or wait?
6. **Testing**: What's the current database size in production? Should we test with production-sized data?

---

## Next Steps

1. **Review this analysis** with the team
2. **Prioritize** which optimizations to implement first
3. **Create tickets** for selected optimizations
4. **Implement Phase 1** (quick wins) first
5. **Measure and validate** improvements
6. **Proceed to Phase 2** if Phase 1 shows good results

---

## References

- **Detailed Analysis**: `docs/codebase-intelligence/sqlite-performance-analysis.md`
- **N+1 Issue**: `todos/p2-perf-n-plus-1-session-stats.md`
- **Memory Scan Issue**: `todos/p2-perf-list-memories-full-scan.md`
- **Foreign Keys Issue**: `todos/p2-data-foreign-keys-not-enforced.md`
- **Implementation**: `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
