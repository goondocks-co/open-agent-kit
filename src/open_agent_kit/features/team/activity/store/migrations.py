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
    if from_version < 5:
        _migrate_v4_to_v5(conn)
    if from_version < 6:
        _migrate_v5_to_v6(conn)
    if from_version < 7:
        _migrate_v6_to_v7(conn)
    if from_version < 8:
        _migrate_v7_to_v8(conn)
    if from_version < 9:
        _migrate_v8_to_v9(conn)
    if from_version < 10:
        _migrate_v9_to_v10(conn)

    # Always run idempotent column checks for the current version.
    # This catches columns added mid-development after a version was
    # first bumped (e.g. summary_embedded added to v6 after initial release).
    _ensure_v6_columns(conn)
    _ensure_v10_columns(conn)


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


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migrate schema from v4 to v5: add title_manually_edited to sessions.

    Adds a boolean flag to protect manually edited session titles from
    being overwritten by LLM-generated titles.

    Idempotent: skips column if it already exists.
    """
    logger.info("Migrating activity store schema v4 -> v5 (title_manually_edited)")

    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}

    if "title_manually_edited" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN title_manually_edited BOOLEAN DEFAULT FALSE")

    logger.info("Migration v4 -> v5 complete: title_manually_edited column added to sessions")


def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migrate schema from v5 to v6: move session summaries to sessions table.

    Moves session_summary observations from memory_observations into the
    sessions.summary column (and new summary_updated_at column), then
    deletes the migrated rows from memory_observations.

    This corrects an architectural misplacement where session summaries
    were stored as observations rather than as session metadata.

    Idempotent: skips column if it already exists; backfill and delete
    use WHERE clauses that are safe to re-run.
    """
    logger.info("Migrating activity store schema v5 -> v6 (session summary column)")

    # 1. Add summary_updated_at column to sessions (if missing)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}

    if "summary_updated_at" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN summary_updated_at INTEGER")

    if "summary_embedded" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN summary_embedded INTEGER DEFAULT 0")

    # 2. Backfill sessions.summary and summary_updated_at from memory_observations.
    #    For each session, pick the most recent session_summary observation.
    #    Only overwrite if sessions.summary is currently NULL (don't clobber
    #    summaries that were already written via the new path).
    conn.execute("""
        UPDATE sessions
        SET summary = (
                SELECT m.observation
                FROM memory_observations m
                WHERE m.session_id = sessions.id
                  AND m.memory_type = 'session_summary'
                ORDER BY m.created_at_epoch DESC
                LIMIT 1
            ),
            summary_updated_at = (
                SELECT m.created_at_epoch
                FROM memory_observations m
                WHERE m.session_id = sessions.id
                  AND m.memory_type = 'session_summary'
                ORDER BY m.created_at_epoch DESC
                LIMIT 1
            )
        WHERE summary IS NULL
          AND EXISTS (
                SELECT 1 FROM memory_observations m
                WHERE m.session_id = sessions.id
                  AND m.memory_type = 'session_summary'
          )
    """)

    # 3. Delete migrated session_summary rows from memory_observations
    conn.execute("DELETE FROM memory_observations WHERE memory_type = 'session_summary'")

    logger.info("Migration v5 -> v6 complete: session summaries moved to sessions table")


def _migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Migrate schema v6 -> v7: add governance audit events table."""
    logger.info("Migrating activity store schema v6 -> v7 (governance audit events)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS governance_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            tool_use_id TEXT,
            tool_category TEXT,
            rule_id TEXT,
            rule_description TEXT,
            action TEXT NOT NULL,
            reason TEXT,
            matched_pattern TEXT,
            tool_input_summary TEXT,
            enforcement_mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL,
            evaluation_ms INTEGER,
            source_machine_id TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gov_audit_session ON governance_audit_events(session_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gov_audit_action ON governance_audit_events(action)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gov_audit_created ON governance_audit_events(created_at_epoch DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gov_audit_tool ON governance_audit_events(tool_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gov_audit_rule ON governance_audit_events(rule_id)"
    )

    logger.info("Migration v6 -> v7 complete: governance_audit_events table created")


def _migrate_v7_to_v8(conn: sqlite3.Connection) -> None:
    """Migrate schema v7 -> v8: add origin_type to memory_observations.

    Adds an origin_type column to distinguish auto-extracted observations
    (created by background processing) from agent-created observations
    (created via ci_remember / oak_remember). Devtools operations that
    delete or rebuild observations will exclude agent_created entries.

    Existing observations default to 'auto_extracted' since they were all
    created by the background processor before this migration.

    Idempotent: skips column if it already exists.
    """
    logger.info("Migrating activity store schema v7 -> v8 (observation origin_type)")

    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(memory_observations)").fetchall()
    }

    if "origin_type" not in existing_columns:
        conn.execute(
            "ALTER TABLE memory_observations ADD COLUMN origin_type TEXT DEFAULT 'auto_extracted'"
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_origin_type "
        "ON memory_observations(origin_type)"
    )

    logger.info("Migration v7 -> v8 complete: origin_type column added to memory_observations")


def _migrate_v8_to_v9(conn: sqlite3.Connection) -> None:
    """Migrate schema v8 -> v9: add relay-based team sync tables.

    Creates all tables needed for relay-based team sync:
    - team_outbox: queued observation events for push to relay
    - team_pull_cursor: tracks last-seen cursor per relay server
    - team_sync_state: key-value store for sync metadata
    - team_reconcile_state: per-machine reconciliation tracking

    Also cleans up stub prompt_batches and adds a unique partial index
    on prompt_batches.content_hash for cross-machine deduplication.

    Idempotent: uses CREATE TABLE/INDEX IF NOT EXISTS throughout.
    """
    logger.info("Migrating activity store schema v8 -> v9 (relay-based team sync)")

    # --- Team outbox (queued events for push to relay) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            source_machine_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            error_message TEXT
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_team_outbox_status ON team_outbox(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_team_outbox_created ON team_outbox(created_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_outbox_flush "
        "ON team_outbox(status, retry_count, id)"
    )

    # --- Team pull cursor (tracks last-seen cursor per relay server) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_pull_cursor (
            server_url TEXT PRIMARY KEY,
            cursor_value TEXT,
            updated_at TEXT NOT NULL
        )
    """)

    # --- Clean up stub prompt_batches (NULL content_hash, no linked activities) ---
    conn.execute("""
        DELETE FROM prompt_batches
        WHERE content_hash IS NULL
          AND id NOT IN (
              SELECT DISTINCT prompt_batch_id
              FROM activities
              WHERE prompt_batch_id IS NOT NULL
          )
    """)

    # --- Unique partial index on prompt_batches.content_hash ---
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_batches_content_hash
        ON prompt_batches(content_hash)
        WHERE content_hash IS NOT NULL
    """)

    # --- Team sync state (key-value store for sync metadata) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # --- Team reconcile state (per-machine reconciliation tracking) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_reconcile_state (
            machine_id TEXT PRIMARY KEY,
            last_reconcile_at TEXT,
            last_hash_count INTEGER,
            last_missing_count INTEGER
        )
    """)

    logger.info("Migration v8 -> v9 complete: relay-based team sync tables created")


def _migrate_v9_to_v10(conn: sqlite3.Connection) -> None:
    """v9 -> v10: Add timeout_seconds column to agent_runs for watchdog recovery.

    The watchdog previously used a hardcoded 600s default for all runs,
    which caused premature recovery of long-running tasks (e.g. docs-site-sync
    with 1200s timeout). Now each run stores its configured timeout so the
    watchdog can use it.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(agent_runs)").fetchall()}

    if "timeout_seconds" not in existing:
        conn.execute("ALTER TABLE agent_runs ADD COLUMN timeout_seconds INTEGER")

    logger.info("Migration v9 -> v10 complete: added timeout_seconds to agent_runs")


def _ensure_v10_columns(conn: sqlite3.Connection) -> None:
    """Ensure v10 columns exist even if the migration ran before they were added.

    This handles databases where the version was bumped to 10 but the
    timeout_seconds column was never actually created. Runs unconditionally
    (cheap PRAGMA check).
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(agent_runs)").fetchall()}

    if "timeout_seconds" not in existing:
        conn.execute("ALTER TABLE agent_runs ADD COLUMN timeout_seconds INTEGER")
        logger.info("Added missing timeout_seconds column to agent_runs table")


def _ensure_v6_columns(conn: sqlite3.Connection) -> None:
    """Ensure v6 columns exist even if the migration ran before they were added.

    This handles databases that ran v5→v6 from an earlier version of the code
    that didn't include summary_embedded. Runs unconditionally (cheap PRAGMA check).
    """
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}

    if "summary_embedded" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN summary_embedded INTEGER DEFAULT 0")
        logger.info("Added missing summary_embedded column to sessions table")
