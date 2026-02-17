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
    if from_version < 3:
        _migrate_v2_to_v3(conn)
    if from_version < 4:
        _migrate_v3_to_v4(conn)


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


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate schema from v2 to v3: add resolution_events table.

    Creates the resolution_events table for cross-machine resolution
    propagation. Each resolution action is recorded as a first-class,
    machine-owned entity that flows through the backup pipeline.

    Idempotent: uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
    """
    logger.info("Migrating activity store schema v2 -> v3 (resolution events)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS resolution_events (
            id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resolved_by_session_id TEXT,
            superseded_by TEXT,
            reason TEXT,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL,
            source_machine_id TEXT NOT NULL,
            content_hash TEXT,
            applied BOOLEAN DEFAULT TRUE
        )
        """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resolution_events_observation "
        "ON resolution_events(observation_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resolution_events_source_machine "
        "ON resolution_events(source_machine_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resolution_events_applied " "ON resolution_events(applied)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resolution_events_epoch "
        "ON resolution_events(created_at_epoch DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resolution_events_content_hash "
        "ON resolution_events(content_hash)"
    )

    logger.info("Migration v2 -> v3 complete: resolution_events table created")


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migrate schema from v3 to v4: add additional_prompt to agent_schedules.

    Adds an optional additional_prompt column to agent_schedules for persistent
    assignments that are prepended to the task prompt on each scheduled run.

    Idempotent: skips column if it already exists.
    """
    logger.info("Migrating activity store schema v3 -> v4 (schedule additional_prompt)")

    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(agent_schedules)").fetchall()
    }

    if "additional_prompt" not in existing_columns:
        conn.execute("ALTER TABLE agent_schedules ADD COLUMN additional_prompt TEXT")

    logger.info("Migration v3 -> v4 complete: additional_prompt column added to agent_schedules")
