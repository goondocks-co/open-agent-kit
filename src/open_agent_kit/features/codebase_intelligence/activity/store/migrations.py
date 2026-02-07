"""Database migration functions for activity store.

Contains all migration logic for upgrading database schema versions.
"""

import logging
import sqlite3
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_SESSION_COLUMN_TRANSCRIPT_PATH,
)

logger = logging.getLogger(__name__)


def apply_migrations(conn: sqlite3.Connection, from_version: int) -> None:
    """Apply schema migrations from current version to latest.

    Args:
        conn: Database connection (within transaction).
        from_version: Current schema version.
    """
    if from_version < 4:
        migrate_v3_to_v4(conn)
    if from_version < 5:
        migrate_v4_to_v5(conn)
    if from_version < 6:
        migrate_v5_to_v6(conn)
    if from_version < 7:
        migrate_v6_to_v7(conn)
    if from_version < 8:
        migrate_v7_to_v8(conn)
    if from_version < 9:
        migrate_v8_to_v9(conn)
    if from_version < 10:
        migrate_v9_to_v10(conn)
    if from_version < 11:
        migrate_v10_to_v11(conn)
    if from_version < 12:
        migrate_v11_to_v12(conn)
    if from_version < 13:
        migrate_v12_to_v13(conn)
    if from_version < 14:
        migrate_v13_to_v14(conn)
    if from_version < 15:
        migrate_v14_to_v15(conn)
    if from_version < 16:
        migrate_v15_to_v16(conn)
    if from_version < 17:
        migrate_v16_to_v17(conn)
    if from_version < 18:
        migrate_v17_to_v18(conn)
    if from_version < 19:
        migrate_v18_to_v19(conn)
    if from_version < 20:
        migrate_v19_to_v20(conn)
    if from_version < 21:
        migrate_v20_to_v21(conn)
    if from_version < 22:
        migrate_v21_to_v22(conn)
    if from_version < 23:
        migrate_v22_to_v23(conn)
    if from_version < 24:
        migrate_v23_to_v24(conn)
    if from_version < 25:
        migrate_v24_to_v25(conn)
    if from_version < 26:
        migrate_v25_to_v26(conn)


def migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migrate schema from v3 to v4: Add source_type to prompt_batches.

    Adds source_type column and backfills based on user_prompt content:
    - Prompts starting with '<task-notification>' -> 'agent_notification'
    - All others -> 'user'

    Plan batches are detected dynamically using PlanDetector.
    """
    logger.info("Migrating activity store schema v3 -> v4: Adding source_type column")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    columns = [row[1] for row in cursor.fetchall()]
    if "source_type" in columns:
        logger.info("source_type column already exists, skipping migration")
        return

    # Add the source_type column
    conn.execute("ALTER TABLE prompt_batches ADD COLUMN source_type TEXT DEFAULT 'user'")

    # Backfill agent_notification batches based on user_prompt content
    cursor = conn.execute("""
        UPDATE prompt_batches
        SET source_type = 'agent_notification'
        WHERE user_prompt LIKE '<task-notification>%'
    """)
    agent_count = cursor.rowcount

    # Backfill plan batches using PlanDetector for dynamic pattern matching
    plan_count = 0
    try:
        from open_agent_kit.features.codebase_intelligence.plan_detector import PlanDetector

        detector = PlanDetector()

        # Get all activities with Write to potential plan paths
        cursor = conn.execute("""
            SELECT DISTINCT prompt_batch_id, file_path
            FROM activities
            WHERE tool_name = 'Write' AND file_path IS NOT NULL AND prompt_batch_id IS NOT NULL
        """)

        plan_batch_ids: set[int] = set()
        for row in cursor.fetchall():
            batch_id, file_path = row
            if detector.is_plan_file(file_path):
                plan_batch_ids.add(batch_id)

        # Update plan batches
        if plan_batch_ids:
            placeholders = ",".join("?" * len(plan_batch_ids))
            cursor = conn.execute(
                f"UPDATE prompt_batches SET source_type = 'plan' WHERE id IN ({placeholders})",
                list(plan_batch_ids),
            )
            plan_count = cursor.rowcount
    except Exception as e:
        logger.warning(f"Plan detection during migration failed (non-fatal): {e}")

    logger.info(
        f"Migration v3->v4 complete: backfilled {agent_count} agent batches, "
        f"{plan_count} plan batches"
    )


def migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migrate schema from v4 to v5: Add plan_file_path to prompt_batches.

    Adds plan_file_path column and backfills from activities for plan batches.
    Also backfills plan execution batches based on user_prompt content
    (e.g., prompts starting with "Implement the following plan:").
    """
    logger.info("Migrating activity store schema v4 -> v5: Adding plan_file_path column")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    columns = [row[1] for row in cursor.fetchall()]
    if "plan_file_path" in columns:
        logger.info("plan_file_path column already exists, skipping migration")
        # Still run the plan execution backfill in case it wasn't done
    else:
        # Add the plan_file_path column
        conn.execute("ALTER TABLE prompt_batches ADD COLUMN plan_file_path TEXT")

    # Backfill plan execution batches based on user_prompt content
    # Uses PromptClassifier to detect plan execution prefixes from agent manifests
    plan_execution_count = 0
    try:
        from open_agent_kit.features.codebase_intelligence.constants import (
            PROMPT_SOURCE_PLAN,
        )
        from open_agent_kit.features.codebase_intelligence.prompt_classifier import (
            PromptClassifier,
        )

        classifier = PromptClassifier()

        # Get all batches that might be plan execution (not yet marked as plan)
        cursor = conn.execute("""
            SELECT id, user_prompt FROM prompt_batches
            WHERE source_type != 'plan' AND user_prompt IS NOT NULL
            """)
        rows = cursor.fetchall()

        for batch_id, user_prompt in rows:
            result = classifier.classify(user_prompt)
            if result.source_type == PROMPT_SOURCE_PLAN:
                conn.execute(
                    "UPDATE prompt_batches SET source_type = 'plan' WHERE id = ?",
                    (batch_id,),
                )
                plan_execution_count += 1
                prefix_preview = result.matched_prefix[:30] if result.matched_prefix else "N/A"
                logger.debug(
                    f"Backfilled batch {batch_id} as plan execution "
                    f"(agent: {result.agent_type}, prefix: {prefix_preview}...)"
                )

    except Exception as e:
        logger.warning(f"Plan execution backfill during migration failed (non-fatal): {e}")

    # Backfill plan_file_path from activities for existing plan batches
    # Find Write activities to plan directories for each plan batch
    plan_path_count = 0
    try:
        from open_agent_kit.features.codebase_intelligence.plan_detector import PlanDetector

        detector = PlanDetector()

        # Get all plan batches (including newly backfilled ones)
        cursor = conn.execute(
            "SELECT id FROM prompt_batches WHERE source_type = 'plan' AND plan_file_path IS NULL"
        )
        plan_batch_ids = [row[0] for row in cursor.fetchall()]

        for batch_id in plan_batch_ids:
            # Find Write activity with plan path
            cursor = conn.execute(
                """
                SELECT file_path FROM activities
                WHERE prompt_batch_id = ? AND tool_name = 'Write' AND file_path IS NOT NULL
                ORDER BY timestamp_epoch DESC
                LIMIT 1
                """,
                (batch_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                file_path = row[0]
                if detector.is_plan_file(file_path):
                    conn.execute(
                        "UPDATE prompt_batches SET plan_file_path = ? WHERE id = ?",
                        (file_path, batch_id),
                    )
                    plan_path_count += 1
    except Exception as e:
        logger.warning(f"Plan file path backfill during migration failed (non-fatal): {e}")

    logger.info(
        f"Migration v4->v5 complete: backfilled {plan_execution_count} plan execution batches, "
        f"{plan_path_count} plan file paths"
    )


def migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migrate schema from v5 to v6: Add plan_content to prompt_batches.

    Adds plan_content column and backfills from plan files for existing plan batches.
    This makes CI self-contained by storing plan content in the database.
    """
    logger.info("Migrating activity store schema v5 -> v6: Adding plan_content column")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    columns = [row[1] for row in cursor.fetchall()]
    if "plan_content" in columns:
        logger.info("plan_content column already exists, skipping column creation")
    else:
        # Add the plan_content column
        conn.execute("ALTER TABLE prompt_batches ADD COLUMN plan_content TEXT")

    # Backfill plan_content from plan files for existing plan batches
    content_count = 0
    try:
        # Get all plan batches with file paths but no content
        cursor = conn.execute("""
            SELECT id, plan_file_path FROM prompt_batches
            WHERE source_type = 'plan'
              AND plan_file_path IS NOT NULL
              AND (plan_content IS NULL OR plan_content = '')
            """)
        rows = cursor.fetchall()

        for batch_id, plan_file_path in rows:
            try:
                plan_path = Path(plan_file_path)
                if plan_path.exists():
                    plan_content = plan_path.read_text(encoding="utf-8")
                    # Truncate to max length
                    if len(plan_content) > 100000:
                        plan_content = plan_content[:100000]
                    conn.execute(
                        "UPDATE prompt_batches SET plan_content = ? WHERE id = ?",
                        (plan_content, batch_id),
                    )
                    content_count += 1
                    logger.debug(f"Backfilled plan content for batch {batch_id}")
            except Exception as e:
                logger.debug(f"Could not read plan file for batch {batch_id}: {e}")
    except Exception as e:
        logger.warning(f"Plan content backfill during migration failed (non-fatal): {e}")

    logger.info(f"Migration v5->v6 complete: backfilled {content_count} plan contents")


def migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Migrate schema from v6 to v7: Add plan_embedded to prompt_batches.

    Adds plan_embedded column to track ChromaDB indexing status for plans.
    This enables semantic search of plans alongside code and memories.
    """
    logger.info("Migrating activity store schema v6 -> v7: Adding plan_embedded column")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    columns = [row[1] for row in cursor.fetchall()]
    if "plan_embedded" in columns:
        logger.info("plan_embedded column already exists, skipping migration")
        return

    # Add the plan_embedded column (default 0 = not embedded)
    conn.execute("ALTER TABLE prompt_batches ADD COLUMN plan_embedded INTEGER DEFAULT 0")

    logger.info("Migration v6->v7 complete: added plan_embedded column")


def migrate_v7_to_v8(conn: sqlite3.Connection) -> None:
    """Migrate schema from v7 to v8: Add composite indexes for performance.

    Adds composite indexes for common query patterns to improve query performance:
    - activities(session_id, processed) - for unprocessed activities by session
    - activities(processed, timestamp_epoch) - for background processing
    - activities(session_id, prompt_batch_id) - for batch queries
    - memory_observations(embedded, created_at_epoch) - for rebuild operations
    - prompt_batches(session_id, status, processed) - for session batch queries
    """
    logger.info("Migrating activity store schema v7 -> v8: Adding composite indexes")

    # Composite indexes for common query patterns
    indexes = [
        # For: WHERE session_id = ? AND processed = FALSE
        "CREATE INDEX IF NOT EXISTS idx_activities_session_processed ON activities(session_id, processed)",
        # For: WHERE processed = FALSE AND timestamp_epoch > ?
        "CREATE INDEX IF NOT EXISTS idx_activities_processed_timestamp ON activities(processed, timestamp_epoch)",
        # For: WHERE session_id = ? AND prompt_batch_id = ?
        "CREATE INDEX IF NOT EXISTS idx_activities_session_batch ON activities(session_id, prompt_batch_id)",
        # For: WHERE embedded = FALSE ORDER BY created_at_epoch
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_embedded_epoch ON memory_observations(embedded, created_at_epoch)",
        # For: WHERE session_id = ? AND status = ? AND processed = ?
        "CREATE INDEX IF NOT EXISTS idx_prompt_batches_session_status ON prompt_batches(session_id, status, processed)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.OperationalError as e:
            # Index might already exist, log warning but continue
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v7->v8 complete: added composite indexes")


def migrate_v8_to_v9(conn: sqlite3.Connection) -> None:
    """Migrate schema from v8 to v9: Add title column to sessions.

    Adds a title column to store LLM-generated short session titles (10-20 words).
    This provides user-friendly session names in the UI instead of GUIDs.
    """
    logger.info("Migrating activity store schema v8 -> v9: Adding session title column")

    # Check if title column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in cursor.fetchall()}

    if "title" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
        logger.info("Migration v8->v9 complete: added title column to sessions")
    else:
        logger.info("Migration v8->v9: title column already exists, skipping")


def migrate_v9_to_v10(conn: sqlite3.Connection) -> None:
    """Migrate schema from v9 to v10: Add memory filtering indexes and FTS5.

    Adds indexes for memory filtering/browsing:
    - idx_memory_observations_type: Filter by memory_type
    - idx_memory_observations_context: Filter by context/file
    - idx_memory_observations_created: Sort by creation date
    - idx_memory_observations_type_created: Combined type filter + date sort

    Also adds FTS5 virtual table for full-text search on memories.
    """
    logger.info("Migrating activity store schema v9 -> v10: Adding memory filtering indexes + FTS5")

    # Add indexes (idempotent - IF NOT EXISTS)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_type ON memory_observations(memory_type)",
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_context ON memory_observations(context)",
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_created ON memory_observations(created_at_epoch DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_type_created ON memory_observations(memory_type, created_at_epoch DESC)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
            logger.debug(f"Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    # Create FTS5 virtual table for memory search
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                observation,
                context,
                content='memory_observations',
                content_rowid='rowid'
            )
        """)
        logger.debug("Created memories_fts virtual table")
    except sqlite3.Error as e:
        logger.warning(f"FTS5 table creation warning (may already exist): {e}")

    # Create triggers to keep FTS in sync
    triggers = [
        """CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memory_observations BEGIN
            INSERT INTO memories_fts(rowid, observation, context) VALUES (NEW.rowid, NEW.observation, NEW.context);
        END""",
        """CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memory_observations BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, observation, context) VALUES ('delete', OLD.rowid, OLD.observation, OLD.context);
        END""",
        """CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memory_observations BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, observation, context) VALUES ('delete', OLD.rowid, OLD.observation, OLD.context);
            INSERT INTO memories_fts(rowid, observation, context) VALUES (NEW.rowid, NEW.observation, NEW.context);
        END""",
    ]

    for trigger_sql in triggers:
        try:
            conn.execute(trigger_sql)
        except sqlite3.Error as e:
            logger.warning(f"Trigger creation warning (may already exist): {e}")

    # Populate FTS with existing memories
    try:
        conn.execute("""
            INSERT INTO memories_fts(rowid, observation, context)
            SELECT rowid, observation, context FROM memory_observations
        """)
        count = conn.execute("SELECT COUNT(*) FROM memory_observations").fetchone()[0]
        logger.info(f"Migration v9->v10 complete: added indexes + FTS5, populated {count} memories")
    except sqlite3.Error as e:
        # May fail if FTS already populated - that's OK
        logger.debug(f"FTS population note (may already be populated): {e}")
        logger.info("Migration v9->v10 complete: added indexes + FTS5")


def migrate_v10_to_v11(conn: sqlite3.Connection) -> None:
    """Migrate schema from v10 to v11: Add content_hash for multi-machine deduplication.

    Adds content_hash column to prompt_batches, memory_observations, and activities
    tables. These hashes enable cross-machine deduplication when merging backups
    from multiple developers.

    Hash computation:
    - prompt_batches: hash(session_id + prompt_number)
    - memory_observations: hash(observation + memory_type + context)
    - activities: hash(session_id + timestamp_epoch + tool_name)
    """
    import hashlib

    logger.info("Migrating activity store schema v10 -> v11: Adding content_hash columns")

    def compute_hash(*parts: str | int | None) -> str:
        """Compute stable hash from parts."""
        content = "|".join(str(p) if p is not None else "" for p in parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # Check which columns need to be added
    tables_to_migrate = []

    for table in ["prompt_batches", "memory_observations", "activities"]:
        cursor = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
        columns = {row[1] for row in cursor.fetchall()}
        if "content_hash" not in columns:
            tables_to_migrate.append(table)

    if not tables_to_migrate:
        logger.info("content_hash columns already exist, skipping column creation")
    else:
        # Add content_hash columns
        for table in tables_to_migrate:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN content_hash TEXT")  # noqa: S608
                logger.debug(f"Added content_hash column to {table}")
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not add content_hash to {table}: {e}")

    # Backfill prompt_batches hashes
    cursor = conn.execute(
        "SELECT id, session_id, prompt_number FROM prompt_batches WHERE content_hash IS NULL"
    )
    batch_count = 0
    for row in cursor.fetchall():
        batch_id, session_id, prompt_number = row
        hash_val = compute_hash(session_id, prompt_number)
        conn.execute(
            "UPDATE prompt_batches SET content_hash = ? WHERE id = ?",
            (hash_val, batch_id),
        )
        batch_count += 1

    # Backfill memory_observations hashes
    cursor = conn.execute(
        "SELECT id, observation, memory_type, context FROM memory_observations "
        "WHERE content_hash IS NULL"
    )
    obs_count = 0
    for row in cursor.fetchall():
        obs_id, observation, memory_type, context = row
        hash_val = compute_hash(observation, memory_type, context)
        conn.execute(
            "UPDATE memory_observations SET content_hash = ? WHERE id = ?",
            (hash_val, obs_id),
        )
        obs_count += 1

    # Backfill activities hashes
    cursor = conn.execute(
        "SELECT id, session_id, timestamp_epoch, tool_name FROM activities "
        "WHERE content_hash IS NULL"
    )
    activity_count = 0
    for row in cursor.fetchall():
        activity_id, session_id, timestamp_epoch, tool_name = row
        hash_val = compute_hash(session_id, timestamp_epoch, tool_name)
        conn.execute(
            "UPDATE activities SET content_hash = ? WHERE id = ?",
            (hash_val, activity_id),
        )
        activity_count += 1

    # Create indexes for hash lookups (idempotent)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_prompt_batches_hash ON prompt_batches(content_hash)",
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_hash ON memory_observations(content_hash)",
        "CREATE INDEX IF NOT EXISTS idx_activities_hash ON activities(content_hash)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning: {e}")

    logger.info(
        f"Migration v10->v11 complete: backfilled {batch_count} batch hashes, "
        f"{obs_count} observation hashes, {activity_count} activity hashes"
    )


def migrate_v11_to_v12(conn: sqlite3.Connection) -> None:
    """Migrate schema from v11 to v12: Add session linking and plan source tracking.

    Adds:
    - parent_session_id, parent_session_reason to sessions table
    - source_plan_batch_id to prompt_batches table

    Also backfills parent_session_id by finding sessions where one ended within
    5 seconds of another starting (same agent, same project). This links
    sessions created via "clear context and proceed" to their planning sessions.

    The 5-second threshold is based on data analysis showing:
    - Most transitions: 0.04-0.12 seconds
    - Slowest observed: ~8 seconds
    - No transitions in 10s-5min range
    We use a conservative 5 seconds to avoid false matches while catching most
    legitimate transitions. Looking at ENDED sessions only avoids false positives
    from concurrent active sessions.
    """
    logger.info("Migrating activity store schema v11 -> v12: Adding session linking columns")

    # Check which columns need to be added to sessions
    cursor = conn.execute("PRAGMA table_info(sessions)")
    session_columns = {row[1] for row in cursor.fetchall()}

    if "parent_session_id" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN parent_session_id TEXT")
        logger.debug("Added parent_session_id column to sessions")

    if "parent_session_reason" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN parent_session_reason TEXT")
        logger.debug("Added parent_session_reason column to sessions")

    # Check if source_plan_batch_id needs to be added to prompt_batches
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    batch_columns = {row[1] for row in cursor.fetchall()}

    if "source_plan_batch_id" not in batch_columns:
        conn.execute("ALTER TABLE prompt_batches ADD COLUMN source_plan_batch_id INTEGER")
        logger.debug("Added source_plan_batch_id column to prompt_batches")

    # Create indexes for efficient queries
    indexes = [
        # For finding parent sessions
        "CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id)",
        # For finding sessions by end time (for linking)
        "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at)",
        # For finding plan implementations
        "CREATE INDEX IF NOT EXISTS idx_prompt_batches_source_plan ON prompt_batches(source_plan_batch_id)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning: {e}")

    # Backfill: Link sessions where one ended within 5 seconds of another starting
    # This captures the "clear context and proceed" pattern where the planning
    # session ends and implementation session starts almost immediately.
    #
    # Algorithm:
    # 1. For each session without a parent
    # 2. Find sessions (same agent, same project) that ended within 5 seconds
    #    BEFORE this session started
    # 3. Link to the most recently ended session (closest in time)
    max_gap_seconds = 5

    # Get all sessions without parent_session_id, ordered by start time
    cursor = conn.execute("""
        SELECT id, agent, project_root, started_at, created_at_epoch
        FROM sessions
        WHERE parent_session_id IS NULL
        ORDER BY created_at_epoch ASC
        """)
    sessions_to_link = cursor.fetchall()

    linked_count = 0
    for session_id, agent, project_root, started_at, started_epoch in sessions_to_link:
        # Find the most recent session that:
        # - Is NOT this session
        # - Has the same agent and project_root
        # - Has ended_at set (is completed)
        # - Ended within max_gap_seconds BEFORE this session started
        #
        # We look for sessions that ended BEFORE this one started, and within
        # the gap window. This ensures we're linking to the session that just
        # completed, not concurrent sessions.
        cursor = conn.execute(
            """
            SELECT id, ended_at
            FROM sessions
            WHERE id != ?
              AND agent = ?
              AND project_root = ?
              AND ended_at IS NOT NULL
              AND created_at_epoch < ?
            ORDER BY created_at_epoch DESC
            LIMIT 1
            """,
            (session_id, agent, project_root, started_epoch),
        )
        candidate = cursor.fetchone()

        if candidate:
            parent_id, ended_at_str = candidate
            if ended_at_str:
                try:
                    from datetime import datetime

                    ended_at = datetime.fromisoformat(ended_at_str)
                    started_at_dt = datetime.fromisoformat(started_at)
                    gap_seconds = (started_at_dt - ended_at).total_seconds()

                    # Only link if the gap is within threshold and positive
                    # (ended before started)
                    if 0 <= gap_seconds <= max_gap_seconds:
                        conn.execute(
                            """
                            UPDATE sessions
                            SET parent_session_id = ?, parent_session_reason = 'inferred'
                            WHERE id = ?
                            """,
                            (parent_id, session_id),
                        )
                        linked_count += 1
                        logger.debug(
                            f"Linked session {session_id[:8]}... -> {parent_id[:8]}... "
                            f"(gap={gap_seconds:.2f}s)"
                        )
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse dates for session linking: {e}")

    logger.info(
        f"Migration v11->v12 complete: added session linking columns, "
        f"backfilled {linked_count} parent session links"
    )


def migrate_v12_to_v13(conn: sqlite3.Connection) -> None:
    """Migrate schema from v12 to v13: Add source_machine_id for origin tracking.

    Adds source_machine_id column to sessions, prompt_batches, memory_observations,
    and activities tables. This enables efficient team backups by tracking which
    machine originally created each record.

    On export, only records with source_machine_id matching the current machine
    are included, preventing backup file bloat from re-exporting imported records.

    Backfills existing records with the current machine identifier.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    logger.info("Migrating activity store schema v12 -> v13: Adding source_machine_id columns")

    machine_id = get_machine_identifier()
    tables = ["sessions", "prompt_batches", "memory_observations", "activities"]
    columns_added = 0

    for table in tables:
        # Check if column already exists (idempotent migration)
        cursor = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
        columns = {row[1] for row in cursor.fetchall()}

        if "source_machine_id" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN source_machine_id TEXT")  # noqa: S608
            columns_added += 1
            logger.debug(f"Added source_machine_id column to {table}")

    # Backfill existing records with current machine ID
    # These records were created on this machine, so they should be tagged as such
    backfill_counts = {}
    for table in tables:
        cursor = conn.execute(
            f"UPDATE {table} SET source_machine_id = ? WHERE source_machine_id IS NULL",  # noqa: S608
            (machine_id,),
        )
        backfill_counts[table] = cursor.rowcount

    # Create indexes for efficient filtering during export
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_sessions_source_machine ON sessions(source_machine_id)",
        "CREATE INDEX IF NOT EXISTS idx_prompt_batches_source_machine ON prompt_batches(source_machine_id)",
        "CREATE INDEX IF NOT EXISTS idx_memory_observations_source_machine ON memory_observations(source_machine_id)",
        "CREATE INDEX IF NOT EXISTS idx_activities_source_machine ON activities(source_machine_id)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    total_backfilled = sum(backfill_counts.values())
    logger.info(
        f"Migration v12->v13 complete: added {columns_added} columns, "
        f"backfilled {total_backfilled} records with machine_id={machine_id} "
        f"(sessions={backfill_counts.get('sessions', 0)}, "
        f"batches={backfill_counts.get('prompt_batches', 0)}, "
        f"observations={backfill_counts.get('memory_observations', 0)}, "
        f"activities={backfill_counts.get('activities', 0)})"
    )


def migrate_v13_to_v14(conn: sqlite3.Connection) -> None:
    """Migrate schema from v13 to v14: Add agent_runs table.

    Creates the agent_runs table for tracking CI agent executions via
    claude-code-sdk. This enables:
    - Persistent run history (survives daemon restarts)
    - Run analysis for evaluating agent effectiveness
    - Cross-machine run history via source_machine_id
    """
    logger.info("Migrating activity store schema v13 -> v14: Adding agent_runs table")

    # Check if table already exists (idempotent migration)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runs'")
    if cursor.fetchone():
        logger.info("agent_runs table already exists, skipping table creation")
    else:
        # Create the agent_runs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',

                -- Timing
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                started_at TEXT,
                started_at_epoch INTEGER,
                completed_at TEXT,
                completed_at_epoch INTEGER,

                -- Results
                result TEXT,
                error TEXT,
                turns_used INTEGER DEFAULT 0,
                cost_usd REAL,

                -- Files modified (JSON arrays)
                files_created TEXT,
                files_modified TEXT,
                files_deleted TEXT,

                -- Configuration snapshot (for reproducibility)
                project_config TEXT,
                system_prompt_hash TEXT,

                -- Machine tracking
                source_machine_id TEXT
            )
            """)
        logger.debug("Created agent_runs table")

    # Create indexes for efficient queries (idempotent)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at_epoch DESC)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_created ON agent_runs(agent_name, created_at_epoch DESC)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v13->v14 complete: added agent_runs table with indexes")


def migrate_v14_to_v15(conn: sqlite3.Connection) -> None:
    """Migrate schema from v14 to v15: Add saved_tasks table.

    Creates the saved_tasks table for reusable task templates. These can be:
    - Run on-demand from the UI
    - Scheduled via cron expressions (future feature)
    - Used as quick-start templates for common tasks

    This lays groundwork for the cron scheduler feature.
    """
    logger.info("Migrating activity store schema v14 -> v15: Adding saved_tasks table")

    # Check if table already exists (idempotent migration)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='saved_tasks'"
    )
    if cursor.fetchone():
        logger.info("saved_tasks table already exists, skipping table creation")
    else:
        # Create the saved_tasks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,

                -- Scheduling (for future cron feature)
                schedule_cron TEXT,
                schedule_enabled INTEGER DEFAULT 0,
                last_run_at TEXT,
                last_run_id TEXT,
                next_run_at TEXT,

                -- Metadata
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_at_epoch INTEGER NOT NULL,

                -- Track runs triggered by this template
                total_runs INTEGER DEFAULT 0
            )
            """)
        logger.debug("Created saved_tasks table")

    # Create indexes for efficient queries (idempotent)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_saved_tasks_agent ON saved_tasks(agent_name)",
        "CREATE INDEX IF NOT EXISTS idx_saved_tasks_schedule ON saved_tasks(schedule_enabled, next_run_at)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v14->v15 complete: added saved_tasks table")


def migrate_v15_to_v16(conn: sqlite3.Connection) -> None:
    """Migrate schema from v15 to v16: Update source_machine_id to privacy-preserving format.

    Replaces old PII-exposing machine identifiers (hostname_username) with the new
    privacy-preserving format (github_username_hash).

    Only updates records that match the CURRENT machine's old identifier,
    so each machine updates its own records when the migration runs.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        _compute_legacy_machine_identifier,
        get_machine_identifier,
    )

    logger.info("Migrating activity store schema v15 -> v16: Updating source_machine_id format")

    # Get old and new identifiers for THIS machine
    old_machine_id = _compute_legacy_machine_identifier()
    new_machine_id = get_machine_identifier()

    if old_machine_id == new_machine_id:
        logger.info("Machine identifier unchanged, skipping migration")
        return

    logger.info(f"Updating source_machine_id: {old_machine_id} -> {new_machine_id}")

    tables = ["sessions", "prompt_batches", "memory_observations", "activities", "agent_runs"]
    update_counts: dict[str, int] = {}

    for table in tables:
        cursor = conn.execute(
            f"UPDATE {table} SET source_machine_id = ? WHERE source_machine_id = ?",  # noqa: S608
            (new_machine_id, old_machine_id),
        )
        update_counts[table] = cursor.rowcount

    total_updated = sum(update_counts.values())
    logger.info(
        f"Migration v15->v16 complete: updated {total_updated} records "
        f"(sessions={update_counts.get('sessions', 0)}, "
        f"batches={update_counts.get('prompt_batches', 0)}, "
        f"observations={update_counts.get('memory_observations', 0)}, "
        f"activities={update_counts.get('activities', 0)}, "
        f"agent_runs={update_counts.get('agent_runs', 0)})"
    )


def migrate_v16_to_v17(conn: sqlite3.Connection) -> None:
    """Migrate schema from v16 to v17: Add suggestion tracking for user-driven linking.

    Adds:
    - suggested_parent_dismissed column to sessions table
    - session_link_events table for analytics

    This enables the user-driven session linking system where:
    - Users see suggested parent sessions when auto-linking doesn't happen
    - Users can accept, dismiss, or pick different parents
    - Link corrections are tracked for improving heuristics
    """
    logger.info("Migrating activity store schema v16 -> v17: Adding suggestion tracking")

    # Check if suggested_parent_dismissed column needs to be added to sessions
    cursor = conn.execute("PRAGMA table_info(sessions)")
    session_columns = {row[1] for row in cursor.fetchall()}

    if "suggested_parent_dismissed" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN suggested_parent_dismissed INTEGER DEFAULT 0")
        logger.debug("Added suggested_parent_dismissed column to sessions")

    # Check if session_link_events table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_link_events'"
    )
    if not cursor.fetchone():
        # Create the session_link_events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_link_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_parent_id TEXT,
                new_parent_id TEXT,
                suggested_parent_id TEXT,
                suggestion_confidence REAL,
                link_reason TEXT,
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL
            )
            """)
        logger.debug("Created session_link_events table")

    # Create indexes for efficient queries (idempotent)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_session_link_events_session ON session_link_events(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_link_events_type ON session_link_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_session_link_events_created ON session_link_events(created_at_epoch DESC)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v16->v17 complete: added suggestion tracking")


def migrate_v17_to_v18(conn: sqlite3.Connection) -> None:
    """Migrate schema from v17 to v18: Add session_relationships table.

    Creates the session_relationships table for many-to-many semantic
    relationships between sessions. This complements the existing parent-child
    model (designed for temporal continuity after "clear context") with
    relationships that capture semantic similarity regardless of time gap.

    Use cases:
    - Working on a feature a month ago and iterating on it now
    - Related sessions working on the same component/concept
    - User-driven linking of sessions that work on similar topics
    """
    logger.info("Migrating activity store schema v17 -> v18: Adding session_relationships table")

    # Check if table already exists (idempotent migration)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_relationships'"
    )
    if cursor.fetchone():
        logger.info("session_relationships table already exists, skipping table creation")
    else:
        # Create the session_relationships table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_a_id TEXT NOT NULL,
                session_b_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                similarity_score REAL,
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                created_by TEXT NOT NULL,

                FOREIGN KEY (session_a_id) REFERENCES sessions(id),
                FOREIGN KEY (session_b_id) REFERENCES sessions(id),
                UNIQUE(session_a_id, session_b_id)
            )
            """)
        logger.debug("Created session_relationships table")

    # Create indexes for efficient queries (idempotent)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_session_relationships_a ON session_relationships(session_a_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_relationships_b ON session_relationships(session_b_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_relationships_type ON session_relationships(relationship_type)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v17->v18 complete: added session_relationships table")


def migrate_v18_to_v19(conn: sqlite3.Connection) -> None:
    """Migrate schema from v18 to v19: Add agent_schedules table.

    Creates the agent_schedules table for tracking cron scheduling runtime state.
    The schedule definition (cron expression, description) lives in YAML,
    while the runtime state (enabled, last_run, next_run) lives in the database.
    """
    logger.info("Migrating activity store schema v18 -> v19: Adding agent_schedules table")

    # Check if table already exists (idempotent migration)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_schedules'"
    )
    if cursor.fetchone():
        logger.info("agent_schedules table already exists, skipping table creation")
    else:
        # Create the agent_schedules table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_schedules (
                instance_name TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                last_run_at TEXT,
                last_run_at_epoch INTEGER,
                last_run_id TEXT,
                next_run_at TEXT,
                next_run_at_epoch INTEGER,
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_at_epoch INTEGER NOT NULL
            )
            """)
        logger.debug("Created agent_schedules table")

    # Create index for efficient due schedule queries (idempotent)
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_schedules_enabled_next "
            "ON agent_schedules(enabled, next_run_at_epoch)"
        )
    except sqlite3.Error as e:
        logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v18->v19 complete: added agent_schedules table")


def migrate_v19_to_v20(conn: sqlite3.Connection) -> None:
    """Migrate schema from v19 to v20: Add sessions created_at index for sorting.

    Adds index for common dashboard query pattern:
    - idx_sessions_created_at: Sort sessions by creation time (for pagination)
    """
    logger.info("Migrating activity store schema v19 -> v20: Adding sessions created_at index")

    indexes = [
        # For: ORDER BY created_at_epoch DESC (dashboard session listing)
        "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at_epoch DESC)",
    ]

    for index_sql in indexes:
        try:
            conn.execute(index_sql)
        except sqlite3.OperationalError as e:
            logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info("Migration v19->v20 complete: added sessions created_at index")


def migrate_v20_to_v21(conn: sqlite3.Connection) -> None:
    """Migrate schema from v20 to v21: Add response_summary to prompt_batches.

    Adds response_summary column to store the agent's final response/summary
    for each prompt batch. This captures what the agent said after completing
    a task, enabling full prompt→work→response tracking.
    """
    logger.info("Migrating activity store schema v20 -> v21: Adding response_summary column")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(prompt_batches)")
    columns = {row[1] for row in cursor.fetchall()}

    if "response_summary" in columns:
        logger.info("response_summary column already exists, skipping migration")
        return

    # Add the response_summary column
    conn.execute("ALTER TABLE prompt_batches ADD COLUMN response_summary TEXT")

    logger.info("Migration v20->v21 complete: added response_summary column to prompt_batches")


def migrate_v21_to_v22(conn: sqlite3.Connection) -> None:
    """Migrate schema from v21 to v22: Add token tracking to agent_runs.

    Adds input_tokens and output_tokens columns to agent_runs table for
    tracking SDK token usage. This enables cost analysis and context
    window monitoring for agent executions.
    """
    logger.info("Migrating activity store schema v21 -> v22: Adding token tracking columns")

    # Check if columns already exist (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(agent_runs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "input_tokens" not in columns:
        conn.execute("ALTER TABLE agent_runs ADD COLUMN input_tokens INTEGER")
        logger.debug("Added input_tokens column to agent_runs")

    if "output_tokens" not in columns:
        conn.execute("ALTER TABLE agent_runs ADD COLUMN output_tokens INTEGER")
        logger.debug("Added output_tokens column to agent_runs")

    logger.info("Migration v21->v22 complete: added input_tokens, output_tokens to agent_runs")


def migrate_v22_to_v23(conn: sqlite3.Connection) -> None:
    """Migrate schema from v22 to v23: Move schedule definitions to database.

    This migration moves schedule definitions (cron expression, description) from
    YAML files to the database. Previously, YAML defined the schedule while the
    database only tracked runtime state (enabled, last_run, next_run).

    Now the database is the sole source of truth for schedules, which:
    - Prevents user-modified schedules from being overwritten during `oak upgrade`
    - Allows schedule management via UI without editing YAML files
    - Avoids git merge conflicts for team projects

    Adds:
    - cron_expression TEXT: The cron schedule expression
    - description TEXT: Human-readable schedule description
    - trigger_type TEXT: Type of trigger ('cron', 'manual') for future expansion
    - source_machine_id TEXT: Machine that created this schedule (for backup filtering)
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    logger.info("Migrating activity store schema v22 -> v23: Moving schedules to database-only")

    # Check which columns already exist (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(agent_schedules)")
    columns = {row[1] for row in cursor.fetchall()}

    columns_added = 0

    if "cron_expression" not in columns:
        conn.execute("ALTER TABLE agent_schedules ADD COLUMN cron_expression TEXT")
        columns_added += 1
        logger.debug("Added cron_expression column to agent_schedules")

    if "description" not in columns:
        conn.execute("ALTER TABLE agent_schedules ADD COLUMN description TEXT")
        columns_added += 1
        logger.debug("Added description column to agent_schedules")

    if "trigger_type" not in columns:
        conn.execute("ALTER TABLE agent_schedules ADD COLUMN trigger_type TEXT DEFAULT 'cron'")
        columns_added += 1
        logger.debug("Added trigger_type column to agent_schedules")

    if "source_machine_id" not in columns:
        conn.execute("ALTER TABLE agent_schedules ADD COLUMN source_machine_id TEXT")
        columns_added += 1
        logger.debug("Added source_machine_id column to agent_schedules")

    # Backfill source_machine_id for existing schedules
    machine_id = get_machine_identifier()
    cursor = conn.execute(
        "UPDATE agent_schedules SET source_machine_id = ? WHERE source_machine_id IS NULL",
        (machine_id,),
    )
    backfilled = cursor.rowcount

    # Create index for source_machine_id filtering during backup
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_schedules_source_machine "
            "ON agent_schedules(source_machine_id)"
        )
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")

    logger.info(
        f"Migration v22->v23 complete: added {columns_added} columns to agent_schedules, "
        f"backfilled {backfilled} records with source_machine_id={machine_id}"
    )


def migrate_v23_to_v24(conn: sqlite3.Connection) -> None:
    """Migrate schema from v23 to v24: Rename instance_name to task_name.

    Renames the primary key column in agent_schedules from instance_name to task_name
    to align with the updated terminology (agent tasks instead of agent instances).

    SQLite 3.25+ supports ALTER TABLE RENAME COLUMN which we use here.
    """
    logger.info("Migrating activity store schema v23 -> v24: Renaming instance_name to task_name")

    # Check if already migrated (task_name exists)
    cursor = conn.execute("PRAGMA table_info(agent_schedules)")
    columns = {row[1] for row in cursor.fetchall()}

    if "task_name" in columns:
        logger.info("task_name column already exists, skipping migration")
        return

    if "instance_name" not in columns:
        logger.warning("instance_name column not found, skipping migration")
        return

    # Rename the column (SQLite 3.25+)
    conn.execute("ALTER TABLE agent_schedules RENAME COLUMN instance_name TO task_name")

    logger.info("Migration v23->v24 complete: renamed instance_name to task_name")


def migrate_v24_to_v25(conn: sqlite3.Connection) -> None:
    """Migrate schema from v24 to v25: Add warnings column to agent_runs.

    Adds a warnings column (JSON array) to store non-fatal issues detected
    during agent execution, such as:
    - No response from provider (compatibility issues)
    - Insufficient context window
    - Other runtime warnings
    """
    logger.info("Migrating activity store schema v24 -> v25: Adding warnings to agent_runs")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(agent_runs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "warnings" in columns:
        logger.info("warnings column already exists, skipping migration")
        return

    # Add the warnings column
    conn.execute("ALTER TABLE agent_runs ADD COLUMN warnings TEXT")

    logger.info("Migration v24->v25 complete: added warnings column to agent_runs")


def migrate_v25_to_v26(conn: sqlite3.Connection) -> None:
    """Migrate schema from v25 to v26: Add transcript_path to sessions.

    Adds transcript_path column to store the path to the session's JSONL
    transcript file. This enables:
    - Recovery of lost data by re-parsing the transcript
    - Session reconstruction without filesystem scanning
    - Audit trail linking database records to their source transcript

    Backfills existing sessions using the TranscriptResolver where possible.
    """
    logger.info("Migrating activity store schema v25 -> v26: Adding transcript_path to sessions")

    # Check if column already exists (idempotent migration)
    cursor = conn.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in cursor.fetchall()}

    if CI_SESSION_COLUMN_TRANSCRIPT_PATH in columns:
        logger.info("transcript_path column already exists, skipping column creation")
    else:
        conn.execute(f"ALTER TABLE sessions ADD COLUMN {CI_SESSION_COLUMN_TRANSCRIPT_PATH} TEXT")
        logger.debug("Added transcript_path column to sessions")

    # Backfill existing sessions using TranscriptResolver
    backfill_count = 0
    try:
        from open_agent_kit.features.codebase_intelligence.transcript_resolver import (
            resolve_transcript_path,
        )

        cursor = conn.execute(
            f"SELECT id, agent, project_root FROM sessions "
            f"WHERE {CI_SESSION_COLUMN_TRANSCRIPT_PATH} IS NULL"
        )
        rows = cursor.fetchall()

        for session_id, agent, project_root in rows:
            try:
                path = resolve_transcript_path(session_id, agent, project_root)
                if path and path.exists():
                    conn.execute(
                        f"UPDATE sessions SET {CI_SESSION_COLUMN_TRANSCRIPT_PATH} = ? WHERE id = ?",
                        (str(path), session_id),
                    )
                    backfill_count += 1
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug(f"Could not resolve transcript for session {session_id}: {e}")
    except Exception as e:
        logger.warning(f"Transcript backfill during migration failed (non-fatal): {e}")

    logger.info(
        f"Migration v25->v26 complete: added transcript_path column, "
        f"backfilled {backfill_count} sessions"
    )
