---
title: Backup & Restore
description: Preserve and share CI history across machines and developers.
sidebar:
  order: 8
---

The backup system enables teams to preserve and share Codebase Intelligence history across machines, developers, and reinstalls.

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

## Schema Evolution

### Forward Compatibility (older backup, newer schema)

- Missing columns use SQLite defaults (usually NULL)
- Works automatically — no action required

### Backward Compatibility (newer backup, older schema)

- Extra columns are automatically stripped during import
- A warning is logged but import proceeds
- No data loss for columns that exist in both schemas

## CLI Commands

```bash
oak ci backup [--include-activities]  # Create backup
oak ci restore [--file PATH]          # Restore from backup
oak ci backup --list                  # List available backups
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/backup/status` | GET | Check backup status and list all backups |
| `/api/backup/create` | POST | Create new backup |
| `/api/backup/restore` | POST | Restore from backup |

:::note
Backup input/output paths are restricted to `oak/ci/history/` within the project. Requests that specify paths outside this directory are rejected.
:::

## Troubleshooting

### ChromaDB Out of Sync

After restore, ChromaDB is automatically rebuilt in the background. If issues persist:

```bash
curl -X POST http://localhost:PORT/api/devtools/rebuild-memories
```

## Best Practices

1. **Commit backups to git**: The `oak/ci/history/` directory is designed for git tracking
2. **Regular backups**: Run `oak ci backup` before major changes
3. **Team sharing**: Each developer's backup has a unique machine ID suffix
4. **Merge on restore**: Multiple backups can be restored; duplicates are skipped
