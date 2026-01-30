# Backup and Restore

The backup system enables teams to preserve and share Codebase Intelligence history across machines, developers, and reinstalls. This document covers usage, architecture, and maintenance guidelines.

## Quick Start

```bash
# Create backup (saved to oak/ci/history/{machine}.sql)
oak ci backup

# Restore from backup
oak ci restore

# Restore from a specific file
oak ci restore --file oak/ci/history/teammate_a7b3c2.sql
```

## Architecture

### Storage Layers

| Layer | Purpose | Location |
|-------|---------|----------|
| SQLite (source of truth) | Sessions, prompts, observations, activities | `.oak/ci/activities.db` |
| ChromaDB (search index) | Vector embeddings for semantic search | `.oak/ci/chroma/` |
| Backup files (git-tracked) | Portable SQL dumps for sharing | `oak/ci/history/*.sql` |

### What Gets Backed Up

- **sessions**: Full session metadata including parent/child links
- **prompt_batches**: User prompts, classifications, plan content
- **memory_observations**: All learned observations (gotchas, decisions, etc.)
- **activities** (optional): Raw tool execution logs (can be large)

### Deduplication

Backups use content-based hashing for cross-machine deduplication:

| Table | Hash Based On |
|-------|---------------|
| sessions | Primary key (session ID) |
| prompt_batches | session_id + prompt_number |
| memory_observations | observation + type + context |
| activities | session_id + timestamp + tool_name |

This allows multiple developers' backups to be merged without duplicates.

## Schema Evolution & Compatibility

The backup system is designed to handle schema changes gracefully.

### Forward Compatibility (older backup → newer schema)

- Missing columns use SQLite defaults (usually NULL)
- Works automatically - no action required

### Backward Compatibility (newer backup → older schema)

- Extra columns are automatically stripped during import
- A warning is logged but import proceeds
- No data loss for columns that exist in both schemas

### Foreign Key Handling

| FK | Handling |
|----|----------|
| `prompt_batches.id` | Auto-generated on import, all references remapped |
| `source_plan_batch_id` | Self-reference remapped after import |
| `parent_session_id` | Validated; orphaned references set to NULL |
| `prompt_batch_id` (in observations/activities) | Remapped to new IDs |

## Maintenance Guidelines for Schema Changes

When modifying the schema, follow this checklist to ensure backup/restore remains healthy:

### Checklist for Adding New Columns

1. **Use nullable columns or defaults**: New columns should be `NULL` or have a `DEFAULT` value so older backups can be restored.

2. **No special backup code needed**: The export uses `SELECT *` which automatically includes new columns.

3. **Test the roundtrip**:
   ```bash
   # Create backup with current schema
   oak ci backup

   # Verify restore works
   oak ci restore --dry-run
   ```

### Checklist for Adding New Foreign Keys

1. **Self-referencing FKs** (e.g., `prompt_batches.source_plan_batch_id`):
   - Add remapping logic to `_remap_source_plan_batch_id()` in `backup.py`
   - Track old→new ID mapping during import

2. **Cross-table FKs** (e.g., `activities.prompt_batch_id`):
   - Ensure the referenced table is imported first (order matters)
   - Add remapping in `_remap_prompt_batch_id()` if ID is auto-generated

3. **Session references** (e.g., `parent_session_id`):
   - Add validation in `_validate_parent_session_ids()` to handle orphans

### Checklist for Adding New Tables

1. Add table name to the `tables` list in `export_to_sql()` (order matters for FKs)
2. Add table to `statements_by_table` dict in `import_from_sql_with_dedup()`
3. Add deduplication logic in `_should_skip_record()` if needed
4. Add counter fields to `ImportResult` dataclass
5. Update `_increment_imported()` and `_increment_skipped()`

### Testing Requirements

Always run these tests after schema changes:

```bash
# Run all backup tests
python -m pytest tests/unit/features/codebase_intelligence/ -k backup -v

# Key tests to verify:
# - test_roundtrip_preserves_data_integrity
# - test_import_handles_unknown_columns_from_newer_schema
# - test_import_preserves_parent_session_links
# - test_import_remaps_source_plan_batch_id
```

## Troubleshooting

### Import Errors

**"table X has no column named Y"**
- The backup is from a newer schema version
- This should be automatically handled by column filtering
- If not, check that `_filter_columns_for_schema()` is being called

**"FOREIGN KEY constraint failed"**
- A referenced record wasn't included in the backup
- Check FK validation/remapping logic
- Consider adding to `_validate_parent_session_ids()` pattern

**"UNIQUE constraint failed"**
- Duplicate record exists
- Check content hash computation
- Verify `_should_skip_record()` is detecting duplicates

### ChromaDB Out of Sync

After restore, ChromaDB is automatically rebuilt in the background. If issues persist:

```bash
# Force full rebuild via DevTools API
curl -X POST http://localhost:44827/api/devtools/rebuild-memories
```

## API Reference

### Daemon Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/backup/status` | GET | Check backup status and list all backups |
| `/api/backup/create` | POST | Create new backup |
| `/api/backup/restore` | POST | Restore from backup |

### CLI Commands

```bash
oak ci backup [--include-activities]  # Create backup
oak ci restore [--file PATH]          # Restore from backup
oak ci backup --list                  # List available backups
```

## Best Practices

1. **Commit backups to git**: The `oak/ci/history/` directory is designed for git tracking
2. **Regular backups**: Run `oak ci backup` before major changes
3. **Team sharing**: Each developer's backup has a unique machine ID suffix
4. **Merge on restore**: Multiple backups can be restored; duplicates are skipped
