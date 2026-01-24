# P1 CRITICAL: SQL Injection Risk in FTS5 Search

## Summary
The FTS5 full-text search implementation may be vulnerable to SQL injection through specially crafted search queries.

## Location
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py` (FTS5 queries)

## Risk
- **Severity**: HIGH
- **Impact**: Database manipulation, data exfiltration
- **Attack Vector**: Malicious search queries with FTS5 special characters

## Evidence
FTS5 has special syntax characters (`AND`, `OR`, `NOT`, `NEAR`, `*`, `-`, `^`) that may not be properly escaped in user input.

## Recommended Fix
1. Escape or strip FTS5 special characters from user input
2. Use parameterized queries consistently
3. Add input validation for search queries

```python
def sanitize_fts_query(query: str) -> str:
    # Escape FTS5 special characters
    special_chars = ['"', "'", '*', '-', '^', '(', ')', 'AND', 'OR', 'NOT', 'NEAR']
    sanitized = query
    for char in special_chars:
        sanitized = sanitized.replace(char, f'"{char}"')
    return sanitized
```

## Review Agent
security-sentinel

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
