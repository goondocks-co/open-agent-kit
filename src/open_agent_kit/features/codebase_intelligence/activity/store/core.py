"""Core ActivityStore class for activity store.

Contains the main ActivityStore class with connection management and delegation
to operation modules.
"""

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.activity.store import (
    activities,
    agent_runs,
    backup,
    batches,
    delete,
    observations,
    resolution_events,
    schedules,
    sessions,
    stats,
)
from open_agent_kit.features.codebase_intelligence.activity.store.migrations import (
    apply_migrations,
)
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
    PromptBatch,
    Session,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import (
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


class ActivityStore:
    """SQLite-based store for session activities.

    Thread-safe activity logging with FTS5 full-text search.
    Designed for high-volume append operations during sessions.
    """

    def __init__(self, db_path: Path, machine_id: str):
        """Initialize the activity store.

        Args:
            db_path: Path to SQLite database file.
            machine_id: Deterministic machine identifier for this instance.
                Resolved once at the composition root and injected here.
        """
        self.db_path = db_path
        self.machine_id = machine_id
        self._local = threading.local()
        # Cache for stats queries (low TTL for near real-time debugging)
        # Format: {cache_key: (data, timestamp)}
        self._stats_cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._cache_ttl = 5.0  # 5 seconds TTL for near real-time debugging
        self._cache_lock = threading.Lock()
        # Activity batching buffer for bulk inserts
        self._activity_buffer: list[Activity] = []
        self._buffer_lock = threading.Lock()
        self._buffer_size = 10  # Flush when buffer reaches this size
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=60.0,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent performance
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            # Performance PRAGMAs for better query performance
            # foreign_keys: Enforce referential integrity (data integrity)
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            # cache_size: 64MB cache (default is 2MB) - 10-50x faster for repeated queries
            # Negative value means KB, so -64000 = 64MB
            self._local.conn.execute("PRAGMA cache_size = -64000")
            # temp_store: Use RAM for temporary tables (reduces disk I/O)
            self._local.conn.execute("PRAGMA temp_store = MEMORY")
            # mmap_size: 256MB memory-mapped I/O (2-5x faster reads for large databases)
            self._local.conn.execute("PRAGMA mmap_size = 268435456")
        conn: sqlite3.Connection = self._local.conn
        return conn

    def _get_readonly_connection(self) -> sqlite3.Connection:
        """Get thread-local read-only database connection.

        Separate from the main read-write connection to enforce read-only access
        for analysis queries. Reused across calls to avoid connection overhead.
        """
        if not hasattr(self._local, "ro_conn") or self._local.ro_conn is None:
            self._local.ro_conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro",
                uri=True,
                timeout=60.0,
            )
            self._local.ro_conn.row_factory = sqlite3.Row
            self._local.ro_conn.execute("PRAGMA query_only = ON")
        conn: sqlite3.Connection = self._local.ro_conn
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}", exc_info=True)
            raise

    def _ensure_schema(self) -> None:
        """Create database schema if needed, applying migrations for existing databases."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._transaction() as conn:
            # Check current schema version
            try:
                cursor = conn.execute(
                    "SELECT MAX(version) FROM schema_version WHERE version <= ?",
                    (SCHEMA_VERSION,),
                )
                row = cursor.fetchone()
                current_version = row[0] if row and row[0] is not None else 0
            except sqlite3.OperationalError:
                current_version = 0

            if current_version < SCHEMA_VERSION:
                if current_version == 0:
                    # Fresh database - apply full schema
                    conn.executescript(SCHEMA_SQL)
                else:
                    # Existing database - apply migrations
                    apply_migrations(conn, current_version)

                # Clean up spurious rows and set authoritative version
                conn.execute("DELETE FROM schema_version")
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
                logger.info(f"Activity store schema initialized (v{SCHEMA_VERSION})")
            else:
                # Even when up-to-date, clean up any spurious version rows
                row_count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
                if row_count != 1:
                    conn.execute("DELETE FROM schema_version")
                    conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (SCHEMA_VERSION,),
                    )
                    logger.info(f"Cleaned up {row_count} spurious schema_version rows")

                # Always run migrations defensively — all migrations are
                # idempotent (check column existence before ALTER), so this
                # safely catches columns added mid-development that were
                # missed when the version was first bumped.
                apply_migrations(conn, current_version)

        # Backfill resolution events for existing resolutions (idempotent)
        try:
            resolution_events.backfill_resolution_events(self)
        except Exception as e:
            logger.warning(f"Resolution event backfill skipped: {e}")

    def get_schema_version(self) -> int:
        """Get current database schema version.

        Returns:
            Schema version number, or 0 if schema_version table doesn't exist.
        """
        try:
            cursor = self._get_connection().execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def optimize_database(
        self,
        *,
        vacuum: bool = True,
        analyze: bool = True,
        fts_optimize: bool = True,
        reindex: bool = False,
    ) -> list[str]:
        """Run database maintenance operations.

        This should be called periodically (weekly/monthly) or after large deletions
        to maintain performance and reclaim space.

        Args:
            vacuum: Reclaim space and defragment (can be slow for large databases).
            analyze: Update query planner statistics.
            fts_optimize: Optimize full-text search index.
            reindex: Rebuild all indexes (fixes corruption, improves performance).

        Returns:
            List of operation names that were executed.
        """
        ops: list[str] = []
        conn = self._get_connection()

        if reindex:
            conn.execute("REINDEX")
            logger.debug("Database maintenance: REINDEX complete")
            ops.append("reindex")

        if analyze:
            conn.execute("ANALYZE")
            logger.debug("Database maintenance: ANALYZE complete")
            ops.append("analyze")

        if fts_optimize:
            conn.execute("INSERT INTO activities_fts(activities_fts) VALUES('optimize')")
            logger.debug("Database maintenance: FTS optimize complete")
            ops.append("fts_optimize")

        if vacuum:
            # VACUUM requires exclusive lock and cannot run inside a transaction.
            # Python's sqlite3 module auto-starts transactions, so commit first.
            conn.commit()
            conn.execute("VACUUM")
            logger.debug("Database maintenance: VACUUM complete")
            ops.append("vacuum")

        logger.info(f"Database maintenance complete: {', '.join(ops)}")
        return ops

    # Cache helpers (exposed for operation modules)
    def _invalidate_stats_cache(self, session_id: str | None = None) -> None:
        """Invalidate stats cache."""
        stats.invalidate_stats_cache(self, session_id)

    def close(self) -> None:
        """Close database connections (read-write and read-only)."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
        if hasattr(self._local, "ro_conn") and self._local.ro_conn:
            self._local.ro_conn.close()
            self._local.ro_conn = None

    # ==========================================================================
    # Read-only SQL query execution (for analysis agents)
    # ==========================================================================

    def execute_readonly_query(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        limit: int = 100,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute a read-only SQL query and return results.

        Opens a separate read-only connection to prevent any writes.
        The query is executed with a LIMIT clause if not already present.

        Args:
            sql: SQL query string (must be SELECT or WITH).
            params: Optional query parameters.
            limit: Maximum rows to return.

        Returns:
            Tuple of (column_names, rows).

        Raises:
            ValueError: If the SQL is not a read-only statement.
            sqlite3.Error: If the query fails.
        """
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_QUERY_FORBIDDEN_KEYWORDS,
            CI_QUERY_MAX_ROWS,
        )

        # Validate SQL is read-only
        normalized = sql.strip().upper()
        if not (
            normalized.startswith("SELECT")
            or normalized.startswith("WITH")
            or normalized.startswith("EXPLAIN")
        ):
            raise ValueError(
                "Only SELECT, WITH, and EXPLAIN statements are allowed. "
                "Use MCP tools (oak_remember, etc.) for write operations."
            )

        for keyword in CI_QUERY_FORBIDDEN_KEYWORDS:
            # Check for keyword as a standalone word (not inside a string literal)
            # Simple check: keyword at word boundary in the normalized SQL
            if f" {keyword} " in f" {normalized} ":
                raise ValueError(
                    f"Forbidden keyword '{keyword}' detected. "
                    f"Only read-only queries are allowed."
                )

        # Clamp limit
        effective_limit = min(limit, CI_QUERY_MAX_ROWS)

        # Reuse thread-local read-only connection (separate from the main r/w connection)
        conn = self._get_readonly_connection()
        # Apply limit if not already in query
        query = sql.strip().rstrip(";")
        if "LIMIT" not in normalized:
            query = f"{query} LIMIT {effective_limit}"

        cursor = conn.execute(query, params or ())
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [tuple(row) for row in cursor.fetchmany(effective_limit)]
        return columns, rows

    # ==========================================================================
    # Session operations - delegate to sessions module
    # ==========================================================================

    def create_session(self, session_id: str, agent: str, project_root: str) -> Session:
        """Create a new session record."""
        return sessions.create_session(self, session_id, agent, project_root)

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        return sessions.get_session(self, session_id)

    def get_or_create_session(
        self, session_id: str, agent: str, project_root: str
    ) -> tuple[Session, bool]:
        """Get existing session or create new one."""
        return sessions.get_or_create_session(self, session_id, agent, project_root)

    def end_session(self, session_id: str, summary: str | None = None) -> None:
        """Mark session as completed."""
        sessions.end_session(self, session_id, summary)

    def update_session_title(
        self, session_id: str, title: str, manually_edited: bool = False
    ) -> None:
        """Update the session title."""
        sessions.update_session_title(self, session_id, title, manually_edited=manually_edited)

    def update_session_summary(self, session_id: str, summary: str) -> None:
        """Update the session summary."""
        sessions.update_session_summary(self, session_id, summary)

    def mark_session_summary_embedded(self, session_id: str, embedded: bool = True) -> None:
        """Mark whether a session summary has been embedded in ChromaDB."""
        sessions.mark_session_summary_embedded(self, session_id, embedded)

    def update_session_transcript_path(self, session_id: str, transcript_path: str) -> None:
        """Store the transcript file path for a session."""
        sessions.update_session_transcript_path(self, session_id, transcript_path)

    def reactivate_session_if_needed(self, session_id: str) -> bool:
        """Reactivate a session if it's currently completed."""
        return sessions.reactivate_session_if_needed(self, session_id)

    def _ensure_session_exists(self, session_id: str, agent: str) -> bool:
        """Create session if it doesn't exist."""
        return sessions.ensure_session_exists(self, session_id, agent)

    def increment_prompt_count(self, session_id: str) -> None:
        """Increment the prompt count for a session."""
        sessions.increment_prompt_count(self, session_id)

    def get_unprocessed_sessions(self, limit: int = 10) -> list[Session]:
        """Get sessions that haven't been processed yet."""
        return sessions.get_unprocessed_sessions(self, limit)

    def mark_session_processed(self, session_id: str) -> None:
        """Mark session as processed by background worker."""
        sessions.mark_session_processed(self, session_id)

    def get_recent_sessions(
        self,
        limit: int = 10,
        offset: int = 0,
        status: str | None = None,
        agent: str | None = None,
        sort: str = "last_activity",
    ) -> list[Session]:
        """Get recent sessions with pagination support."""
        return sessions.get_recent_sessions(self, limit, offset, status, agent, sort)

    def get_sessions_needing_titles(self, limit: int = 10) -> list[Session]:
        """Get sessions that need titles generated."""
        return sessions.get_sessions_needing_titles(self, limit)

    def get_completed_sessions(
        self,
        *,
        min_activities: int | None = None,
        limit: int = 500,
    ) -> list[Session]:
        """Get completed sessions, optionally filtered by minimum activity count."""
        return sessions.get_completed_sessions(self, min_activities=min_activities, limit=limit)

    def get_sessions_missing_summaries(
        self, limit: int = 10, min_activities: int | None = None
    ) -> list[Session]:
        """Get completed sessions missing session summaries."""
        return sessions.get_sessions_missing_summaries(self, limit, min_activities)

    def recover_stale_sessions(
        self,
        timeout_seconds: int = 3600,
        min_activities: int | None = None,
        vector_store: Any | None = None,
    ) -> tuple[list[str], list[str]]:
        """Auto-end or delete sessions that have been inactive for too long."""
        return sessions.recover_stale_sessions(
            self, timeout_seconds, min_activities, vector_store=vector_store
        )

    def cleanup_low_quality_sessions(
        self,
        vector_store: Any | None = None,
        min_activities: int | None = None,
    ) -> list[str]:
        """Delete completed sessions that don't meet the quality threshold."""
        return sessions.cleanup_low_quality_sessions(
            self, vector_store=vector_store, min_activities=min_activities
        )

    def is_suggestion_dismissed(self, session_id: str) -> bool:
        """Check whether the suggested-parent suggestion was dismissed."""
        return sessions.is_suggestion_dismissed(self, session_id)

    def count_session_activities(self, session_id: str) -> int:
        """Count total activities for a session."""
        return sessions.count_session_activities(self, session_id)

    def count_sessions_with_summaries(self) -> int:
        """Count sessions that have a summary."""
        return sessions.count_sessions_with_summaries(self)

    def list_sessions_with_summaries(
        self, limit: int = 5, source_machine_id: str | None = None
    ) -> list[Session]:
        """List recent sessions with non-NULL summaries."""
        return sessions.list_sessions_with_summaries(
            self, limit=limit, source_machine_id=source_machine_id
        )

    # ==========================================================================
    # Prompt batch operations - delegate to batches module
    # ==========================================================================

    def create_prompt_batch(
        self,
        session_id: str,
        user_prompt: str | None = None,
        source_type: str = "user",
        plan_file_path: str | None = None,
        plan_content: str | None = None,
        agent: str | None = None,
    ) -> PromptBatch:
        """Create a new prompt batch."""
        return batches.create_prompt_batch(
            self, session_id, user_prompt, source_type, plan_file_path, plan_content, agent
        )

    def get_prompt_batch(self, batch_id: int) -> PromptBatch | None:
        """Get prompt batch by ID."""
        return batches.get_prompt_batch(self, batch_id)

    def get_active_prompt_batch(self, session_id: str) -> PromptBatch | None:
        """Get the current active prompt batch for a session."""
        return batches.get_active_prompt_batch(self, session_id)

    def get_latest_prompt_batch(self, session_id: str) -> PromptBatch | None:
        """Get the most recent prompt batch for a session (any status)."""
        return batches.get_latest_prompt_batch(self, session_id)

    def get_session_plan_batch(
        self, session_id: str, plan_file_path: str | None = None
    ) -> PromptBatch | None:
        """Get the most recent plan batch in the current session."""
        return batches.get_session_plan_batch(self, session_id, plan_file_path)

    def end_prompt_batch(self, batch_id: int) -> None:
        """Mark a prompt batch as completed."""
        batches.end_prompt_batch(self, batch_id)

    def reactivate_prompt_batch(self, batch_id: int) -> None:
        """Reactivate a completed prompt batch (when tool activity continues)."""
        batches.reactivate_prompt_batch(self, batch_id)

    def get_unprocessed_prompt_batches(self, limit: int = 10) -> list[PromptBatch]:
        """Get prompt batches that haven't been processed yet."""
        return batches.get_unprocessed_prompt_batches(self, limit)

    def mark_prompt_batch_processed(self, batch_id: int, classification: str | None = None) -> None:
        """Mark prompt batch as processed."""
        batches.mark_prompt_batch_processed(self, batch_id, classification)

    def update_prompt_batch_source_type(
        self,
        batch_id: int,
        source_type: str,
        plan_file_path: str | None = None,
        plan_content: str | None = None,
    ) -> None:
        """Update the source type for a prompt batch."""
        batches.update_prompt_batch_source_type(
            self, batch_id, source_type, plan_file_path, plan_content
        )

    def get_session_prompt_batches(
        self, session_id: str, limit: int | None = None
    ) -> list[PromptBatch]:
        """Get all prompt batches for a session."""
        return batches.get_session_prompt_batches(self, session_id, limit)

    def get_plans(
        self,
        limit: int = 50,
        offset: int = 0,
        session_id: str | None = None,
        deduplicate: bool = True,
        sort: str = "created",
    ) -> tuple[list[PromptBatch], int]:
        """Get plan batches from prompt_batches table."""
        return batches.get_plans(self, limit, offset, session_id, deduplicate, sort)

    def recover_stuck_batches(
        self, timeout_seconds: int = 1800, project_root: str | None = None
    ) -> int:
        """Auto-end batches stuck in 'active' status for too long."""
        return batches.recover_stuck_batches(self, timeout_seconds, project_root)

    def recover_orphaned_activities(self) -> int:
        """Associate orphaned activities with appropriate batches."""
        return batches.recover_orphaned_activities(self)

    def queue_batches_for_reprocessing(
        self,
        batch_ids: list[int] | None = None,
        recover_stuck: bool = True,
    ) -> tuple[int, int]:
        """Recover stuck batches and reset processed flag for reprocessing."""
        return batches.queue_batches_for_reprocessing(self, batch_ids, recover_stuck)

    def get_batch_ids_for_reprocessing(
        self,
        machine_id: str,
        *,
        mode: str = "all",
        session_id: str | None = None,
        start_epoch: float | None = None,
        end_epoch: float | None = None,
        importance_threshold: int | None = None,
    ) -> list[int]:
        """Get batch IDs eligible for reprocessing, filtered by source machine."""
        return batches.get_batch_ids_for_reprocessing(
            self,
            machine_id,
            mode=mode,
            session_id=session_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            importance_threshold=importance_threshold,
        )

    def get_prompt_batch_activities(
        self, batch_id: int, limit: int | None = None
    ) -> list[Activity]:
        """Get all activities for a prompt batch."""
        return batches.get_prompt_batch_activities(self, batch_id, limit)

    def get_prompt_batch_stats(self, batch_id: int) -> dict[str, Any]:
        """Get statistics for a prompt batch."""
        return batches.get_prompt_batch_stats(self, batch_id)

    def get_unembedded_plans(self, limit: int = 50) -> list[PromptBatch]:
        """Get plan batches that haven't been embedded in ChromaDB yet."""
        return batches.get_unembedded_plans(self, limit)

    def mark_plan_embedded(self, batch_id: int) -> None:
        """Mark a plan batch as embedded in ChromaDB."""
        batches.mark_plan_embedded(self, batch_id)

    def mark_plan_unembedded(self, batch_id: int) -> None:
        """Mark a plan batch as not embedded in ChromaDB."""
        batches.mark_plan_unembedded(self, batch_id)

    def count_unembedded_plans(self) -> int:
        """Count plan batches not yet in ChromaDB."""
        return batches.count_unembedded_plans(self)

    def get_embedded_plan_chromadb_ids(self) -> list[str]:
        """Get ChromaDB IDs for all embedded plans (format: 'plan-{batch_id}')."""
        return batches.get_embedded_plan_chromadb_ids(self)

    def count_embedded_plans(self) -> int:
        """Count plan batches that are in ChromaDB."""
        return batches.count_embedded_plans(self)

    def mark_all_plans_unembedded(self) -> int:
        """Mark all plans as not embedded."""
        return batches.mark_all_plans_unembedded(self)

    def update_prompt_batch_response(self, batch_id: int, response_summary: str) -> None:
        """Update a prompt batch with the agent's response summary."""
        batches.update_prompt_batch_response(self, batch_id, response_summary)

    # ==========================================================================
    # Activity operations - delegate to activities module
    # ==========================================================================

    def add_activity(self, activity: Activity) -> int:
        """Add a tool execution activity."""
        return activities.add_activity(self, activity)

    def flush_activity_buffer(self) -> list[int]:
        """Flush any buffered activities to the database."""
        return activities.flush_activity_buffer(self)

    def add_activity_buffered(self, activity: Activity, force_flush: bool = False) -> int | None:
        """Add an activity with automatic batching."""
        return activities.add_activity_buffered(self, activity, force_flush)

    def add_activities(self, activity_list: list[Activity]) -> list[int]:
        """Add multiple activities in a single transaction."""
        return activities.add_activities(self, activity_list)

    def get_session_activities(
        self, session_id: str, tool_name: str | None = None, limit: int | None = None
    ) -> list[Activity]:
        """Get activities for a session."""
        return activities.get_session_activities(self, session_id, tool_name, limit)

    def get_unprocessed_activities(
        self, session_id: str | None = None, limit: int = 100
    ) -> list[Activity]:
        """Get activities that haven't been processed yet."""
        return activities.get_unprocessed_activities(self, session_id, limit)

    def mark_activities_processed(
        self, activity_ids: list[int], observation_id: str | None = None
    ) -> None:
        """Mark activities as processed."""
        activities.mark_activities_processed(self, activity_ids, observation_id)

    def search_activities(
        self, query: str, session_id: str | None = None, limit: int = 20
    ) -> list[Activity]:
        """Full-text search across activities."""
        return activities.search_activities(self, query, session_id, limit)

    # ==========================================================================
    # Observation operations - delegate to observations module
    # ==========================================================================

    def has_observation_with_hash(self, content_hash: str) -> bool:
        """Check if any observation with this content hash exists (any status)."""
        return observations.has_observation_with_hash(self, content_hash)

    def store_observation(self, observation: StoredObservation) -> str:
        """Store a memory observation in SQLite."""
        return observations.store_observation(self, observation)

    def get_observation(self, observation_id: str) -> StoredObservation | None:
        """Get an observation by ID."""
        return observations.get_observation(self, observation_id)

    def get_unembedded_observations(self, limit: int = 100) -> list[StoredObservation]:
        """Get observations that haven't been added to ChromaDB."""
        return observations.get_unembedded_observations(self, limit)

    def mark_observation_embedded(self, observation_id: str) -> None:
        """Mark an observation as embedded in ChromaDB."""
        observations.mark_observation_embedded(self, observation_id)

    def mark_observations_embedded(self, observation_ids: list[str]) -> None:
        """Mark multiple observations as embedded in ChromaDB."""
        observations.mark_observations_embedded(self, observation_ids)

    def mark_all_observations_unembedded(self) -> int:
        """Mark all observations as not embedded."""
        return observations.mark_all_observations_unembedded(self)

    def count_observations_for_batches(self, batch_ids: list[int], machine_id: str) -> int:
        """Count observations linked to specific batches from a given machine."""
        return observations.count_observations_for_batches(self, batch_ids, machine_id)

    def count_observations(self) -> int:
        """Count total observations in SQLite."""
        return observations.count_observations(self)

    def count_embedded_observations(self) -> int:
        """Count observations that are in ChromaDB."""
        return observations.count_embedded_observations(self)

    def get_embedded_observation_ids(self) -> list[str]:
        """Get all observation IDs that are embedded in ChromaDB."""
        return observations.get_embedded_observation_ids(self)

    def count_unembedded_observations(self) -> int:
        """Count observations not yet in ChromaDB."""
        return observations.count_unembedded_observations(self)

    def count_observations_by_type(self, memory_type: str) -> int:
        """Count observations by memory_type."""
        return observations.count_observations_by_type(self, memory_type)

    def update_observation_status(
        self,
        observation_id: str,
        status: str,
        resolved_by_session_id: str | None = None,
        resolved_at: str | None = None,
        superseded_by: str | None = None,
    ) -> bool:
        """Update observation lifecycle status."""
        return observations.update_observation_status(
            self, observation_id, status, resolved_by_session_id, resolved_at, superseded_by
        )

    def get_observations_by_session(
        self, session_id: str, status: str | None = None
    ) -> list[StoredObservation]:
        """Get observations for a session, optionally filtered by status."""
        return observations.get_observations_by_session(self, session_id, status)

    def count_observations_by_status(self) -> dict[str, int]:
        """Count observations grouped by lifecycle status."""
        return observations.count_observations_by_status(self)

    def get_active_observations(self, limit: int = 100) -> list[StoredObservation]:
        """Get active observations ordered oldest-first."""
        return observations.get_active_observations(self, limit)

    def list_observations(
        self,
        limit: int = 50,
        offset: int = 0,
        memory_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        tag: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_archived: bool = False,
        status: str | None = "active",
        include_resolved: bool = False,
    ) -> tuple[list[dict], int]:
        """List observations from SQLite with pagination and filtering."""
        return observations.list_observations(
            self,
            limit=limit,
            offset=offset,
            memory_types=memory_types,
            exclude_types=exclude_types,
            tag=tag,
            start_date=start_date,
            end_date=end_date,
            include_archived=include_archived,
            status=status,
            include_resolved=include_resolved,
        )

    def find_later_edit_session(
        self, file_path: str, after_epoch: float, exclude_session_id: str
    ) -> str | None:
        """Check if a file was edited in a later session."""
        return observations.find_later_edit_session(
            self, file_path, after_epoch, exclude_session_id
        )

    # ==========================================================================
    # Statistics operations - delegate to stats module
    # ==========================================================================

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get statistics for a session."""
        return stats.get_session_stats(self, session_id)

    def get_bulk_session_stats(self, session_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get statistics for multiple sessions."""
        return stats.get_bulk_session_stats(self, session_ids)

    def get_bulk_first_prompts(
        self, session_ids: list[str], max_length: int = 100
    ) -> dict[str, str | None]:
        """Get the first user prompt preview for multiple sessions."""
        return stats.get_bulk_first_prompts(self, session_ids, max_length)

    def get_bulk_child_session_counts(self, session_ids: list[str]) -> dict[str, int]:
        """Get child session counts for multiple sessions."""
        return sessions.get_bulk_child_session_counts(self, session_ids)

    # ==========================================================================
    # Cross-cutting operations
    # ==========================================================================

    def reset_processing_state(self, *, delete_memories: bool = False) -> dict[str, int]:
        """Reset processing flags on all completed records.

        Optionally deletes all memory observations from SQLite.
        ChromaDB cleanup (if needed) must be handled by the caller,
        since the store layer doesn't hold the vector store reference.

        Args:
            delete_memories: If True, delete all memory observations.

        Returns:
            Dict with counts: {observations_deleted, sessions_reset,
            batches_reset, activities_reset}.
        """
        counts: dict[str, int] = {
            "observations_deleted": 0,
            "sessions_reset": 0,
            "batches_reset": 0,
            "activities_reset": 0,
        }

        with self._transaction() as conn:
            if delete_memories:
                # Preserve agent-created observations — they were created by
                # the maintenance agent and should survive devtools resets.
                cursor = conn.execute(
                    "DELETE FROM memory_observations "
                    "WHERE source_machine_id = ? "
                    "AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'",
                    (self.machine_id,),
                )
                counts["observations_deleted"] = cursor.rowcount

            cursor = conn.execute(
                "UPDATE sessions SET processed = FALSE, summary = NULL "
                "WHERE status = 'completed' AND source_machine_id = ?",
                (self.machine_id,),
            )
            counts["sessions_reset"] = cursor.rowcount

            cursor = conn.execute(
                "UPDATE prompt_batches "
                "SET processed = FALSE, classification = NULL "
                "WHERE status = 'completed' AND source_machine_id = ?",
                (self.machine_id,),
            )
            counts["batches_reset"] = cursor.rowcount

            cursor = conn.execute(
                "UPDATE activities SET processed = FALSE WHERE source_machine_id = ?",
                (self.machine_id,),
            )
            counts["activities_reset"] = cursor.rowcount

        logger.info("Reset processing state: %s", counts)
        return counts

    def cleanup_cross_machine_pollution(self, vector_store: Any | None = None) -> dict[str, int]:
        """Remove observations that violate the machine isolation invariant.

        Finds observations where the observation's source_machine_id differs
        from its session's source_machine_id — i.e., a local processor created
        observations referencing another machine's imported sessions.

        This is a one-time cleanup for databases that were polluted before
        machine-scoped filters were added to all background processing paths.
        Idempotent: returns zeros on subsequent runs.

        Args:
            vector_store: Optional vector store for ChromaDB cleanup.

        Returns:
            Dict with cleanup counts: {observations_deleted, chromadb_deleted}.
        """
        counts: dict[str, int] = {
            "observations_deleted": 0,
            "chromadb_deleted": 0,
        }

        conn = self._get_connection()

        # Find cross-machine observations: observation created by machine X
        # referencing a session owned by machine Y
        cursor = conn.execute("""
            SELECT mo.id FROM memory_observations mo
            JOIN sessions s ON mo.session_id = s.id
            WHERE mo.source_machine_id != s.source_machine_id
            """)
        polluted_ids = [row[0] for row in cursor.fetchall()]

        if not polluted_ids:
            return counts

        # Delete from ChromaDB first (best-effort)
        if vector_store and polluted_ids:
            try:
                vector_store.delete_memories(polluted_ids)
                counts["chromadb_deleted"] = len(polluted_ids)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"ChromaDB cleanup for cross-machine pollution failed: {e}")

        # Delete from SQLite
        placeholders = ",".join("?" * len(polluted_ids))
        with self._transaction() as tx_conn:
            cursor = tx_conn.execute(
                f"DELETE FROM memory_observations WHERE id IN ({placeholders})",
                polluted_ids,
            )
            counts["observations_deleted"] = cursor.rowcount

        logger.info(
            "Cleaned up cross-machine pollution: %d observations deleted, "
            "%d ChromaDB entries removed",
            counts["observations_deleted"],
            counts["chromadb_deleted"],
        )
        return counts

    def backfill_content_hashes(self) -> dict[str, int]:
        """Backfill content_hash for records missing them."""
        return backup.backfill_content_hashes(self)

    # ==========================================================================
    # Hash retrieval for deduplication
    # ==========================================================================

    def get_all_session_ids(self) -> set[str]:
        """Get all session IDs for dedup checking during import."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT id FROM sessions")
        return {row[0] for row in cursor.fetchall()}

    def get_all_prompt_batch_hashes(self) -> set[str]:
        """Get all prompt_batch content_hash values for dedup checking.

        Falls back to computing hashes if content_hash column is empty.
        """
        conn = self._get_connection()

        # First try to get existing hashes
        cursor = conn.execute(
            "SELECT content_hash FROM prompt_batches WHERE content_hash IS NOT NULL"
        )
        hashes = {row[0] for row in cursor.fetchall()}

        # For records without hashes, compute them
        cursor = conn.execute(
            "SELECT session_id, prompt_number FROM prompt_batches WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            computed_hash = backup.compute_prompt_batch_hash(str(row[0]), int(row[1]))
            hashes.add(computed_hash)

        return hashes

    def get_all_observation_hashes(self) -> set[str]:
        """Get all memory_observation content_hash values for dedup checking.

        Falls back to computing hashes if content_hash column is empty.
        """
        conn = self._get_connection()

        # First try to get existing hashes
        cursor = conn.execute(
            "SELECT content_hash FROM memory_observations WHERE content_hash IS NOT NULL"
        )
        hashes = {row[0] for row in cursor.fetchall()}

        # For records without hashes, compute them
        cursor = conn.execute(
            "SELECT observation, memory_type, context FROM memory_observations "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            computed_hash = backup.compute_observation_hash(str(row[0]), str(row[1]), row[2])
            hashes.add(computed_hash)

        return hashes

    def get_all_activity_hashes(self) -> set[str]:
        """Get all activity content_hash values for dedup checking.

        Falls back to computing hashes if content_hash column is empty.
        """
        conn = self._get_connection()

        # First try to get existing hashes
        cursor = conn.execute("SELECT content_hash FROM activities WHERE content_hash IS NOT NULL")
        hashes = {row[0] for row in cursor.fetchall()}

        # For records without hashes, compute them
        cursor = conn.execute(
            "SELECT session_id, timestamp_epoch, tool_name FROM activities "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            computed_hash = backup.compute_activity_hash(str(row[0]), int(row[1]), str(row[2]))
            hashes.add(computed_hash)

        return hashes

    # ==========================================================================
    # Delete operations - delegate to delete module
    # ==========================================================================

    def delete_batch_observations(self, batch_id: int) -> list[str]:
        """Delete all observations for a batch (returns IDs for ChromaDB cleanup)."""
        return delete.delete_batch_observations(self, batch_id)

    def delete_observations_for_batches(self, batch_ids: list[int], machine_id: str) -> list[str]:
        """Delete observations for multiple batches and reset batch flags atomically."""
        return delete.delete_observations_for_batches(self, batch_ids, machine_id)

    def get_session_observation_ids(self, session_id: str) -> list[str]:
        """Get all observation IDs for a session."""
        return delete.get_session_observation_ids(self, session_id)

    def get_batch_observation_ids(self, batch_id: int) -> list[str]:
        """Get all observation IDs for a prompt batch."""
        return delete.get_batch_observation_ids(self, batch_id)

    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation from SQLite."""
        return delete.delete_observation(self, observation_id)

    def delete_activity(self, activity_id: int) -> str | None:
        """Delete a single activity."""
        return delete.delete_activity(self, activity_id)

    def delete_prompt_batch(self, batch_id: int) -> dict[str, int]:
        """Delete a prompt batch and all related data."""
        return delete.delete_prompt_batch(self, batch_id)

    def delete_session(self, session_id: str) -> dict[str, int]:
        """Delete a session and all related data."""
        return delete.delete_session(self, session_id)

    def delete_records_by_machine(
        self, machine_id: str, vector_store: Any | None = None
    ) -> dict[str, int]:
        """Delete all records originating from a specific machine."""
        return delete.delete_records_by_machine(self, machine_id, vector_store)

    # ==========================================================================
    # Agent run operations - delegate to agent_runs module
    # ==========================================================================

    def create_agent_run(
        self,
        run_id: str,
        agent_name: str,
        task: str,
        status: str = "pending",
        project_config: dict[str, Any] | None = None,
        system_prompt_hash: str | None = None,
    ) -> None:
        """Create a new agent run record."""
        agent_runs.create_run(
            self, run_id, agent_name, task, status, project_config, system_prompt_hash
        )

    def get_agent_run(self, run_id: str) -> dict[str, Any] | None:
        """Get an agent run by ID."""
        return agent_runs.get_run(self, run_id)

    def update_agent_run(
        self,
        run_id: str,
        status: str | None = None,
        started_at: Any | None = None,
        completed_at: Any | None = None,
        result: str | None = None,
        error: str | None = None,
        turns_used: int | None = None,
        cost_usd: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        files_created: list[str] | None = None,
        files_modified: list[str] | None = None,
        files_deleted: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Update an agent run record."""
        agent_runs.update_run(
            self,
            run_id,
            status,
            started_at,
            completed_at,
            result,
            error,
            turns_used,
            cost_usd,
            input_tokens,
            output_tokens,
            files_created,
            files_modified,
            files_deleted,
            warnings,
        )

    def list_agent_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        agent_name: str | None = None,
        status: str | None = None,
        created_after_epoch: int | None = None,
        created_before_epoch: int | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """List agent runs with optional filtering and sorting."""
        return agent_runs.list_runs(
            self,
            limit,
            offset,
            agent_name,
            status,
            created_after_epoch,
            created_before_epoch,
            sort_by,
            sort_order,
        )

    def delete_agent_run(self, run_id: str) -> bool:
        """Delete an agent run."""
        return agent_runs.delete_run(self, run_id)

    def bulk_delete_agent_runs(
        self,
        agent_name: str | None = None,
        status: str | None = None,
        before_epoch: int | None = None,
        keep_recent: int = 10,
    ) -> int:
        """Bulk delete agent runs with retention policy."""
        return agent_runs.bulk_delete_runs(self, agent_name, status, before_epoch, keep_recent)

    def recover_stale_runs(
        self,
        buffer_seconds: int = 300,
        default_timeout_seconds: int = 600,
    ) -> list[str]:
        """Mark runs stuck in RUNNING status as FAILED.

        A run is considered stale if it has been running for longer than
        default_timeout + buffer seconds. This handles daemon crashes
        that leave runs in RUNNING state.

        Args:
            buffer_seconds: Grace period beyond expected timeout (default 5 min).
            default_timeout_seconds: Default timeout if not tracked per-run.

        Returns:
            List of recovered run IDs.
        """
        return agent_runs.recover_stale_runs(self, buffer_seconds, default_timeout_seconds)

    # ==========================================================================
    # Schedule operations - delegate to schedules module
    # ==========================================================================

    def create_schedule(
        self,
        task_name: str,
        cron_expression: str | None = None,
        description: str | None = None,
        trigger_type: str = "cron",
        next_run_at: Any | None = None,
        additional_prompt: str | None = None,
    ) -> None:
        """Create a new schedule record."""
        schedules.create_schedule(
            self,
            task_name,
            cron_expression,
            description,
            trigger_type,
            next_run_at,
            additional_prompt=additional_prompt,
        )

    def get_schedule(self, task_name: str) -> dict[str, Any] | None:
        """Get a schedule by task name."""
        return schedules.get_schedule(self, task_name)

    def update_schedule(
        self,
        task_name: str,
        enabled: bool | None = None,
        cron_expression: str | None = None,
        description: str | None = None,
        trigger_type: str | None = None,
        additional_prompt: str | None = None,
        last_run_at: Any | None = None,
        last_run_id: str | None = None,
        next_run_at: Any | None = None,
    ) -> None:
        """Update a schedule record."""
        schedules.update_schedule(
            self,
            task_name,
            enabled=enabled,
            cron_expression=cron_expression,
            description=description,
            trigger_type=trigger_type,
            additional_prompt=additional_prompt,
            last_run_at=last_run_at,
            last_run_id=last_run_id,
            next_run_at=next_run_at,
        )

    def list_schedules(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """List all schedules."""
        return schedules.list_schedules(self, enabled_only)

    def get_due_schedules(self) -> list[dict[str, Any]]:
        """Get schedules that are due to run."""
        return schedules.get_due_schedules(self)

    def delete_schedule(self, task_name: str) -> bool:
        """Delete a schedule record."""
        return schedules.delete_schedule(self, task_name)

    def upsert_schedule(
        self,
        task_name: str,
        cron_expression: str | None = None,
        description: str | None = None,
        trigger_type: str = "cron",
        next_run_at: Any | None = None,
    ) -> None:
        """Create or update a schedule record."""
        schedules.upsert_schedule(
            self, task_name, cron_expression, description, trigger_type, next_run_at
        )

    def get_all_schedule_task_names(self) -> set[str]:
        """Get all schedule task names for dedup checking during import."""
        return schedules.get_all_schedule_task_names(self)

    # ==========================================================================
    # Resolution event operations - delegate to resolution_events module
    # ==========================================================================

    def store_resolution_event(
        self,
        observation_id: str,
        action: str,
        resolved_by_session_id: str | None = None,
        superseded_by: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Create and store a resolution event."""
        return resolution_events.store_resolution_event(
            self, observation_id, action, resolved_by_session_id, superseded_by, reason
        )

    def replay_unapplied_resolution_events(self, vector_store: Any | None = None) -> int:
        """Replay unapplied resolution events from imports."""
        return resolution_events.replay_unapplied_events(self, vector_store)

    def get_all_resolution_event_hashes(self) -> set[str]:
        """Get all resolution event content_hash values for dedup checking."""
        return resolution_events.get_all_resolution_event_hashes(self)

    def count_unapplied_resolution_events(self) -> int:
        """Count resolution events that haven't been applied yet."""
        return resolution_events.count_unapplied_events(self)
