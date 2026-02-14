"""Database migration functions for activity store.

Contains all migration logic for upgrading database schema versions.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def apply_migrations(conn: sqlite3.Connection, from_version: int) -> None:
    """Apply schema migrations from current version to latest.

    Args:
        conn: Database connection (within transaction).
        from_version: Current schema version.
    """
    if from_version < 2:
        _migrate_v1_to_v2(conn)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate schema from v1 to v2: add observation lifecycle columns.

    Adds status, resolution tracking, and session origin type to
    memory_observations for lifecycle management.

    Idempotent: skips columns that already exist (handles partial migrations
    and databases created with the v2 schema).
    """
    logger.info("Migrating activity store schema v1 -> v2 (observation lifecycle)")

    # Get existing columns to make migration idempotent
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(memory_observations)").fetchall()
    }

    # Add lifecycle columns (only if missing)
    new_columns = {
        "status": "TEXT DEFAULT 'active'",
        "resolved_by_session_id": "TEXT",
        "resolved_at": "TEXT",
        "superseded_by": "TEXT",
        "session_origin_type": "TEXT",
    }
    for col_name, col_def in new_columns.items():
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE memory_observations ADD COLUMN {col_name} {col_def}")

    # Add indexes for lifecycle queries (IF NOT EXISTS is inherently idempotent)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_status "
        "ON memory_observations(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_resolved_by "
        "ON memory_observations(resolved_by_session_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_origin_type "
        "ON memory_observations(session_origin_type)"
    )

    logger.info("Migration v1 -> v2 complete: observation lifecycle columns added")
