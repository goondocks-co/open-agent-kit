"""Core ActivityStore class for activity store.

Contains the main ActivityStore class with connection management.
Operation methods are auto-delegated to focused modules via __getattr__.
"""

import functools
import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.activity.store import (
    activities,
    agent_runs,
    backup,
    batches,
    delete,
    governance,
    maintenance,
    observations,
    resolution_events,
    schedules,
    sessions,
    stats,
)
from open_agent_kit.features.team.activity.store.migrations import (
    apply_migrations,
)
from open_agent_kit.features.team.activity.store.models import (
    Activity,
    Session,
)
from open_agent_kit.features.team.activity.store.schema import (
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.config.governance import DataCollectionPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Delegation registry
# ---------------------------------------------------------------------------
# Grouped by module. Each entry is either a plain string (method name ==
# function name) or a tuple (method_name, function_name) for renames.
# Built into _DELEGATION_REGISTRY: {method_name: (module, func_name)} at
# module load time.

_MODULE_METHODS: list[tuple[ModuleType, list[str | tuple[str, str]]]] = [
    (
        sessions,
        [
            "create_session",
            # get_session: kept as explicit method for mypy type safety
            "get_or_create_session",
            "end_session",
            "update_session_title",
            "update_session_summary",
            "mark_session_summary_embedded",
            "update_session_transcript_path",
            "reactivate_session_if_needed",
            ("_ensure_session_exists", "ensure_session_exists"),
            "increment_prompt_count",
            "get_unprocessed_sessions",
            "mark_session_processed",
            "get_session_members",
            "get_recent_sessions",
            "get_sessions_needing_titles",
            "get_completed_sessions",
            "get_sessions_missing_summaries",
            "recover_stale_sessions",
            "cleanup_low_quality_sessions",
            "is_suggestion_dismissed",
            "count_session_activities",
            "count_sessions_with_summaries",
            "list_sessions_with_summaries",
            "get_bulk_child_session_counts",
            "enrich_sessions_with_lineage",
        ],
    ),
    (
        batches,
        [
            "create_prompt_batch",
            "get_prompt_batch",
            "get_active_prompt_batch",
            "get_latest_prompt_batch",
            "get_session_plan_batch",
            "end_prompt_batch",
            "reactivate_prompt_batch",
            "get_unprocessed_prompt_batches",
            "mark_prompt_batch_processed",
            "update_prompt_batch_source_type",
            "get_session_prompt_batches",
            "get_plans",
            "recover_stuck_batches",
            "recover_orphaned_activities",
            "queue_batches_for_reprocessing",
            "get_batch_ids_for_reprocessing",
            "get_prompt_batch_activities",
            "get_prompt_batch_stats",
            "get_unembedded_plans",
            "mark_plan_embedded",
            "mark_plan_unembedded",
            "count_unembedded_plans",
            "get_embedded_plan_chromadb_ids",
            "count_embedded_plans",
            "mark_all_plans_unembedded",
            "update_prompt_batch_response",
            "get_bulk_plan_counts",
        ],
    ),
    (
        activities,
        [
            "add_activity",
            "flush_activity_buffer",
            "add_activity_buffered",
            "add_activities",
            "get_session_activities",
            "get_unprocessed_activities",
            "mark_activities_processed",
            "search_activities",
            "execute_readonly_query",
        ],
    ),
    (
        observations,
        [
            "has_observation_with_hash",
            "store_observation",
            "get_observation",
            "get_unembedded_observations",
            "mark_observation_embedded",
            "mark_observations_embedded",
            "mark_all_observations_unembedded",
            "count_observations_for_batches",
            "count_observations",
            "count_embedded_observations",
            "get_embedded_observation_ids",
            "count_unembedded_observations",
            "count_observations_by_type",
            "update_observation_status",
            "get_observations_by_session",
            "count_observations_by_status",
            "get_active_observations",
            # list_observations: kept as explicit method for mypy type safety
            "find_later_edit_session",
        ],
    ),
    (stats, ["get_session_stats", "get_bulk_session_stats", "get_bulk_first_prompts"]),
    (
        delete,
        [
            "delete_batch_observations",
            "delete_observations_for_batches",
            "get_session_observation_ids",
            "get_batch_observation_ids",
            "delete_observation",
            "delete_activity",
            "delete_prompt_batch",
            "delete_session",
            "delete_records_by_machine",
        ],
    ),
    (
        agent_runs,
        [
            ("create_agent_run", "create_run"),
            ("get_agent_run", "get_run"),
            ("update_agent_run", "update_run"),
            ("list_agent_runs", "list_runs"),
            ("delete_agent_run", "delete_run"),
            ("bulk_delete_agent_runs", "bulk_delete_runs"),
            "recover_stale_runs",
        ],
    ),
    (
        schedules,
        [
            "create_schedule",
            "get_schedule",
            "update_schedule",
            "list_schedules",
            # get_due_schedules: kept as explicit method for mypy type safety
            "delete_schedule",
            "upsert_schedule",
            "get_all_schedule_task_names",
        ],
    ),
    (
        resolution_events,
        [
            "store_resolution_event",
            ("replay_unapplied_resolution_events", "replay_unapplied_events"),
            "get_all_resolution_event_hashes",
            ("count_unapplied_resolution_events", "count_unapplied_events"),
        ],
    ),
    (governance, ["query_governance_audit_events", "get_governance_audit_summary"]),
    (
        backup,
        [
            "backfill_content_hashes",
            "get_all_session_ids",
            "get_all_prompt_batch_hashes",
            "get_all_observation_hashes",
            "get_all_activity_hashes",
        ],
    ),
    (maintenance, ["reset_processing_state", "cleanup_cross_machine_pollution"]),
]

# Flatten into lookup dict: {method_name: (module, func_name)}
_DELEGATION_REGISTRY: dict[str, tuple[ModuleType, str]] = {}
for _mod, _entries in _MODULE_METHODS:
    for _entry in _entries:
        if isinstance(_entry, tuple):
            _method_name, _func_name = _entry
        else:
            _method_name = _func_name = _entry
        _DELEGATION_REGISTRY[_method_name] = (_mod, _func_name)


class ActivityStore:
    """SQLite-based store for session activities.

    Thread-safe activity logging with FTS5 full-text search.
    Designed for high-volume append operations during sessions.

    Operation methods (sessions, batches, activities, observations, etc.) are
    auto-delegated to focused modules. Only connection management, schema init,
    and cross-cutting logic with real SQL live here as explicit methods.
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
        # Team outbox: when enabled, data writes enqueue sync events atomically
        self.team_outbox_enabled: bool = False
        self._team_policy_accessor: Callable[[], DataCollectionPolicy] | None = None
        self._ensure_schema()

    # ==========================================================================
    # Auto-delegation via __getattr__
    # ==========================================================================

    def __getattr__(self, name: str) -> Any:
        """Auto-delegate to operation modules via the registry.

        Looks up *name* in ``_DELEGATION_REGISTRY``.  If found, creates a
        bound partial (``module.func(self, ...)``), caches it on the instance
        so subsequent calls bypass ``__getattr__``, and returns it.
        """
        entry = _DELEGATION_REGISTRY.get(name)
        if entry is None:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        module, func_name = entry
        func = getattr(module, func_name)
        bound = functools.partial(func, self)
        # Cache on instance so __getattr__ is not called again for this name
        object.__setattr__(self, name, bound)
        return bound

    # ==========================================================================
    # Connection management
    # ==========================================================================

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

    def close(self) -> None:
        """Close database connections (read-write and read-only)."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
        if hasattr(self._local, "ro_conn") and self._local.ro_conn:
            self._local.ro_conn.close()
            self._local.ro_conn = None

    # ==========================================================================
    # Schema management
    # ==========================================================================

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

    def get_team_policy(self) -> "DataCollectionPolicy | None":
        """Get current team data collection policy, or None if not configured."""
        if self._team_policy_accessor is not None:
            return self._team_policy_accessor()
        return None

    # ==========================================================================
    # Database maintenance
    # ==========================================================================

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

    # ==========================================================================
    # Explicit typed delegations (kept for mypy — these methods are called in
    # functions that return their result directly, so the return type must be
    # concrete rather than Any from __getattr__).
    # ==========================================================================

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        return sessions.get_session(self, session_id)

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

    def get_due_schedules(self) -> list[dict[str, Any]]:
        """Get schedules that are due to run."""
        return schedules.get_due_schedules(self)
