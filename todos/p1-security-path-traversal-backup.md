# P1 CRITICAL: Path Traversal Vulnerability in Backup/Restore

## Summary
The backup and restore endpoints accept user-controlled file paths without validation, allowing writing to or reading from arbitrary filesystem locations.

## Location
- `src/open_agent_kit/features/codebase_intelligence/daemon/routes/backup.py:93-96`
- `src/open_agent_kit/features/codebase_intelligence/daemon/routes/backup.py:136-139`

## Risk
- **Severity**: HIGH
- **Impact**: Arbitrary file read/write, potential code execution
- **Attack Vector**: Path traversal via `../../etc/passwd` style paths

## Evidence
```python
# backup.py:93-96
if request.output_path:
    backup_path = Path(request.output_path)  # No validation!
else:
    backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE
```

## Recommended Fix
```python
if request.output_path:
    backup_path = Path(request.output_path).resolve()
    # Ensure path is within project root
    if not backup_path.is_relative_to(state.project_root):
        raise HTTPException(status_code=400, detail="Backup path must be within project")
    # Prevent symlink attacks
    if backup_path.is_symlink():
        raise HTTPException(status_code=400, detail="Symlinks not allowed")
```

## Review Agent
security-sentinel

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
