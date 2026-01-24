# P1 CRITICAL: No Authentication on Daemon HTTP API

## Summary
The CI daemon exposes HTTP endpoints without any authentication mechanism. Any process on localhost can access all functionality including reading code, memories, and modifying data.

## Location
- `src/open_agent_kit/features/codebase_intelligence/daemon/app.py`
- All routes in `daemon/routes/`

## Risk
- **Severity**: CRITICAL
- **Impact**: Any local process can read indexed code, memories, session data
- **Attack Vector**: Malicious local process, browser-based attacks via CORS

## Evidence
```python
# daemon/app.py - No auth middleware configured
app = FastAPI(title="Codebase Intelligence Daemon")
app.include_router(search.router)  # No auth check
app.include_router(activity.router)  # No auth check
```

## Recommended Fix
1. Add authentication token validation middleware
2. Generate per-session tokens stored in a secure location
3. Require token in request headers for all non-health endpoints

## Review Agent
security-sentinel

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
