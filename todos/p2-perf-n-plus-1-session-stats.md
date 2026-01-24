# P2 IMPORTANT: N+1 Query Pattern in Session Stats

## Summary
For N sessions, the code makes N additional database queries to fetch stats. This is a classic N+1 query pattern.

## Location
- `src/open_agent_kit/features/codebase_intelligence/daemon/routes/activity.py:123-130`

## Evidence
```python
for session in sessions:
    try:
        stats = state.activity_store.get_session_stats(session.id)  # N queries!
    except (OSError, ValueError, RuntimeError):
        stats = {}
    items.append(_session_to_item(session, stats))
```

## Impact
- 10 sessions: 11 queries
- 100 sessions: 101 queries (~200-500ms total)

## Recommended Fix
Add a bulk stats method using SQL aggregation:

```python
# In activity/store.py
def get_bulk_session_stats(self, session_ids: list[str]) -> dict[str, dict]:
    placeholders = ",".join("?" * len(session_ids))
    query = f"""
        SELECT
            session_id,
            COUNT(*) as activity_count,
            COUNT(DISTINCT file_path) as file_count,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count
        FROM activities
        WHERE session_id IN ({placeholders})
        GROUP BY session_id
    """
    cursor = conn.execute(query, session_ids)
    return {row["session_id"]: dict(row) for row in cursor}

# In routes/activity.py
stats_map = state.activity_store.get_bulk_session_stats([s.id for s in sessions])
for session in sessions:
    stats = stats_map.get(session.id, {})
    items.append(_session_to_item(session, stats))
```

## Review Agent
performance-oracle

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
