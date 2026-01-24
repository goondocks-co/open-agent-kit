# P2 IMPORTANT: Foreign Key Constraints Not Enforced

## Summary
SQLite does not enforce foreign keys by default. The schema defines foreign keys but they are not actually enforced.

## Location
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py:43-50`
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py:386-399`

## Evidence
```sql
-- Schema defines foreign keys
FOREIGN KEY (session_id) REFERENCES sessions(id),
FOREIGN KEY (prompt_batch_id) REFERENCES prompt_batches(id)
```

```python
# But connection doesn't enable enforcement
def _get_connection(self) -> sqlite3.Connection:
    self._local.conn = sqlite3.connect(...)
    # Missing: PRAGMA foreign_keys = ON
```

## Risk
- Orphaned records (activities without sessions)
- Referential integrity violations
- Data inconsistency

## Recommended Fix
```python
def _get_connection(self) -> sqlite3.Connection:
    if not hasattr(self._local, "conn") or self._local.conn is None:
        self._local.conn = sqlite3.connect(...)
        self._local.conn.execute("PRAGMA foreign_keys = ON")
    return self._local.conn
```

## Review Agent
data-integrity-guardian

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
