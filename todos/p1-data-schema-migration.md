# P1 CRITICAL: Schema Migration Lacks Proper Versioning

## Summary
Database schema migrations apply the entire schema via `executescript()` when upgrading, which doesn't support incremental migrations and could cause data loss.

## Location
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py:413-433`

## Risk
- **Severity**: CRITICAL
- **Impact**: Data loss on schema changes, failed upgrades
- **Scenario**: Column definition changes would fail with existing data

## Evidence
```python
def _ensure_schema(self) -> None:
    if current_version < SCHEMA_VERSION:
        # Applies entire schema - doesn't support incremental migrations
        conn.executescript(SCHEMA_SQL)
```

## Recommended Fix
Implement incremental migration functions:

```python
MIGRATIONS = {
    1: """
        -- Initial schema
        CREATE TABLE IF NOT EXISTS sessions (...);
    """,
    2: """
        -- Add new column
        ALTER TABLE sessions ADD COLUMN new_field TEXT;
    """,
    3: """
        -- Create new table
        CREATE TABLE IF NOT EXISTS new_table (...);
    """,
}

def _ensure_schema(self) -> None:
    current_version = self._get_schema_version()
    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        if version in MIGRATIONS:
            conn.executescript(MIGRATIONS[version])
            self._set_schema_version(version)
```

## Review Agent
data-integrity-guardian

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
