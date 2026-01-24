"""SQLite-based activity store for tool execution logging.

Captures raw tool executions during sessions for background LLM processing.
Inspired by claude-mem's approach: capture liberally, process asynchronously.

Schema:
- sessions: Session metadata and state
- activities: Raw tool execution events
- activities_fts: FTS5 virtual table for full-text search
"""

import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Schema version for migrations
# v4: Added source_type to prompt_batches (user, agent_notification, plan, system)
# v5: Added plan_file_path to prompt_batches (for plan source type)
# v6: Added plan_content to prompt_batches (store actual plan content in DB)
# v7: Added plan_embedded to prompt_batches (track ChromaDB indexing status for plans)
# v8: Added composite indexes for common query patterns (performance optimization)
# v9: Added title column to sessions (LLM-generated short session title)
SCHEMA_VERSION = 9

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Memory observations table (source of truth for extracted memories)
-- ChromaDB is just a search index over this data
CREATE TABLE IF NOT EXISTS memory_observations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    prompt_batch_id INTEGER,
    observation TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    context TEXT,
    tags TEXT,  -- Comma-separated tags
    importance INTEGER DEFAULT 5,
    file_path TEXT,
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL,
    embedded BOOLEAN DEFAULT FALSE,  -- Has this been added to ChromaDB?
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (prompt_batch_id) REFERENCES prompt_batches(id)
);

-- Index for finding unembedded observations (for rebuilding ChromaDB)
CREATE INDEX IF NOT EXISTS idx_memory_observations_embedded ON memory_observations(embedded);
CREATE INDEX IF NOT EXISTS idx_memory_observations_session ON memory_observations(session_id);

-- Sessions table (Claude Code session - from launch to exit)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    project_root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',  -- active, completed, abandoned
    prompt_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,  -- Has background processor handled this?
    summary TEXT,  -- LLM-generated session summary
    title TEXT,  -- LLM-generated short session title (10-20 words)
    created_at_epoch INTEGER NOT NULL
);

-- Prompt batches table (activities between user prompts - the unit of processing)
CREATE TABLE IF NOT EXISTS prompt_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    prompt_number INTEGER NOT NULL,  -- Sequence number within session
    user_prompt TEXT,  -- Full user prompt (up to 10K chars) for context
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',  -- active, completed
    activity_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,  -- Has background processor handled this?
    classification TEXT,  -- LLM classification: exploration, implementation, debugging, refactoring
    source_type TEXT DEFAULT 'user',  -- user, agent_notification, plan, system
    plan_file_path TEXT,  -- Path to plan file (for source_type='plan')
    plan_content TEXT,  -- Full plan content (stored for self-contained CI)
    created_at_epoch INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Activities table (raw tool executions)
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    prompt_batch_id INTEGER,  -- Links to the prompt batch (for prompt-level processing)
    tool_name TEXT NOT NULL,
    tool_input TEXT,  -- JSON of input params (sanitized)
    tool_output_summary TEXT,  -- Brief summary, not full output
    file_path TEXT,  -- Primary file affected (if any)
    files_affected TEXT,  -- JSON array of all files
    duration_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    timestamp TEXT NOT NULL,
    timestamp_epoch INTEGER NOT NULL,
    processed BOOLEAN DEFAULT FALSE,  -- Has this activity been processed?
    observation_id TEXT,  -- Link to extracted observation (if any)
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (prompt_batch_id) REFERENCES prompt_batches(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_activities_session ON activities(session_id);
CREATE INDEX IF NOT EXISTS idx_activities_prompt_batch ON activities(prompt_batch_id);
CREATE INDEX IF NOT EXISTS idx_activities_tool ON activities(tool_name);
CREATE INDEX IF NOT EXISTS idx_activities_processed ON activities(processed);
CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON activities(timestamp_epoch);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_processed ON sessions(processed);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_session ON prompt_batches(session_id);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_processed ON prompt_batches(processed);

-- FTS5 virtual table for full-text search across activities
CREATE VIRTUAL TABLE IF NOT EXISTS activities_fts USING fts5(
    tool_name,
    tool_input,
    tool_output_summary,
    file_path,
    error_message,
    content='activities',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS activities_ai AFTER INSERT ON activities BEGIN
    INSERT INTO activities_fts(rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES (new.id, new.tool_name, new.tool_input, new.tool_output_summary, new.file_path, new.error_message);
END;

CREATE TRIGGER IF NOT EXISTS activities_ad AFTER DELETE ON activities BEGIN
    INSERT INTO activities_fts(activities_fts, rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES ('delete', old.id, old.tool_name, old.tool_input, old.tool_output_summary, old.file_path, old.error_message);
END;

CREATE TRIGGER IF NOT EXISTS activities_au AFTER UPDATE ON activities BEGIN
    INSERT INTO activities_fts(activities_fts, rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES ('delete', old.id, old.tool_name, old.tool_input, old.tool_output_summary, old.file_path, old.error_message);
    INSERT INTO activities_fts(rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES (new.id, new.tool_name, new.tool_input, new.tool_output_summary, new.file_path, new.error_message);
END;
"""


@dataclass
class Activity:
    """A single tool execution event."""

    id: int | None = None
    session_id: str = ""
    prompt_batch_id: int | None = None  # Links to the prompt batch
    tool_name: str = ""
    tool_input: dict[str, Any] | None = None
    tool_output_summary: str = ""
    file_path: str | None = None
    files_affected: list[str] = field(default_factory=list)
    duration_ms: int | None = None
    success: bool = True
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    processed: bool = False
    observation_id: str | None = None

    def to_row(self) -> dict[str, Any]:
        """Convert to database row."""
        return {
            "session_id": self.session_id,
            "prompt_batch_id": self.prompt_batch_id,
            "tool_name": self.tool_name,
            "tool_input": json.dumps(self.tool_input) if self.tool_input else None,
            "tool_output_summary": (
                self.tool_output_summary[:2000] if self.tool_output_summary else None
            ),
            "file_path": self.file_path,
            "files_affected": json.dumps(self.files_affected) if self.files_affected else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message[:1000] if self.error_message else None,
            "timestamp": self.timestamp.isoformat(),
            "timestamp_epoch": int(self.timestamp.timestamp()),
            "processed": self.processed,
            "observation_id": self.observation_id,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Activity":
        """Create from database row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            prompt_batch_id=row["prompt_batch_id"],
            tool_name=row["tool_name"],
            tool_input=json.loads(row["tool_input"]) if row["tool_input"] else None,
            tool_output_summary=row["tool_output_summary"] or "",
            file_path=row["file_path"],
            files_affected=json.loads(row["files_affected"]) if row["files_affected"] else [],
            duration_ms=row["duration_ms"],
            success=bool(row["success"]),
            error_message=row["error_message"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            processed=bool(row["processed"]),
            observation_id=row["observation_id"],
        )


@dataclass
class PromptBatch:
    """A batch of activities from a single user prompt.

    This is the unit of processing - activities between user prompts.

    Source types:
    - user: User-initiated prompts (extract memories normally)
    - agent_notification: Background agent completions (preserve but skip memory extraction)
    - plan: Plan mode activities (extract plan as decision memory)
    - system: System messages (skip memory extraction)
    """

    id: int | None = None
    session_id: str = ""
    prompt_number: int = 1
    user_prompt: str | None = None  # Full user prompt for context
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    status: str = "active"
    activity_count: int = 0
    processed: bool = False
    classification: str | None = None  # exploration, implementation, debugging, refactoring
    source_type: str = "user"  # user, agent_notification, plan, system
    plan_file_path: str | None = None  # Path to plan file (for source_type='plan')
    plan_content: str | None = None  # Full plan content (stored for self-contained CI)
    plan_embedded: bool = False  # Has plan been indexed in ChromaDB?

    # Maximum prompt length to store (10K chars should capture most prompts)
    MAX_PROMPT_LENGTH = 10000
    # Maximum plan content length (100K chars for large plans)
    MAX_PLAN_CONTENT_LENGTH = 100000

    def to_row(self) -> dict[str, Any]:
        """Convert to database row."""
        return {
            "session_id": self.session_id,
            "prompt_number": self.prompt_number,
            "user_prompt": self.user_prompt[: self.MAX_PROMPT_LENGTH] if self.user_prompt else None,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "activity_count": self.activity_count,
            "processed": self.processed,
            "classification": self.classification,
            "source_type": self.source_type,
            "plan_file_path": self.plan_file_path,
            "plan_content": (
                self.plan_content[: self.MAX_PLAN_CONTENT_LENGTH] if self.plan_content else None
            ),
            "created_at_epoch": int(self.started_at.timestamp()),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PromptBatch":
        """Create from database row."""
        # Handle migration: older rows may not have source_type, plan_file_path, plan_content,
        # or plan_embedded
        source_type = "user"
        plan_file_path = None
        plan_content = None
        plan_embedded = False
        try:
            source_type = row["source_type"] or "user"
        except (KeyError, IndexError):
            pass
        try:
            plan_file_path = row["plan_file_path"]
        except (KeyError, IndexError):
            pass
        try:
            plan_content = row["plan_content"]
        except (KeyError, IndexError):
            pass
        try:
            plan_embedded = bool(row["plan_embedded"])
        except (KeyError, IndexError):
            pass

        return cls(
            id=row["id"],
            session_id=row["session_id"],
            prompt_number=row["prompt_number"],
            user_prompt=row["user_prompt"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            status=row["status"],
            activity_count=row["activity_count"],
            processed=bool(row["processed"]),
            classification=row["classification"],
            source_type=source_type,
            plan_file_path=plan_file_path,
            plan_content=plan_content,
            plan_embedded=plan_embedded,
        )


@dataclass
class Session:
    """A session record."""

    id: str
    agent: str
    project_root: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "active"
    prompt_count: int = 0
    tool_count: int = 0
    processed: bool = False
    summary: str | None = None
    title: str | None = None

    def to_row(self) -> dict[str, Any]:
        """Convert to database row."""
        return {
            "id": self.id,
            "agent": self.agent,
            "project_root": self.project_root,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "prompt_count": self.prompt_count,
            "tool_count": self.tool_count,
            "processed": self.processed,
            "summary": self.summary,
            "title": self.title,
            "created_at_epoch": int(self.started_at.timestamp()),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Session":
        """Create from database row."""
        # Handle title column which may not exist in older databases
        title = row["title"] if "title" in row.keys() else None
        return cls(
            id=row["id"],
            agent=row["agent"],
            project_root=row["project_root"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            status=row["status"],
            prompt_count=row["prompt_count"],
            tool_count=row["tool_count"],
            processed=bool(row["processed"]),
            summary=row["summary"],
            title=title,
        )


@dataclass
class StoredObservation:
    """A memory observation stored in SQLite (source of truth).

    This is the authoritative storage for observations. ChromaDB is a
    search index that can be rebuilt from this data.
    """

    id: str
    session_id: str
    prompt_batch_id: int | None = None
    observation: str = ""
    memory_type: str = ""
    context: str | None = None
    tags: list[str] | None = None
    importance: int = 5
    file_path: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    embedded: bool = False  # Has this been added to ChromaDB?

    def to_row(self) -> dict[str, Any]:
        """Convert to database row."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "prompt_batch_id": self.prompt_batch_id,
            "observation": self.observation,
            "memory_type": self.memory_type,
            "context": self.context,
            "tags": ",".join(self.tags) if self.tags else None,
            "importance": self.importance,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat(),
            "created_at_epoch": int(self.created_at.timestamp()),
            "embedded": self.embedded,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "StoredObservation":
        """Create from database row."""
        tags_str = row["tags"]
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            prompt_batch_id=row["prompt_batch_id"],
            observation=row["observation"],
            memory_type=row["memory_type"],
            context=row["context"],
            tags=tags_str.split(",") if tags_str else None,
            importance=row["importance"] or 5,
            file_path=row["file_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            embedded=bool(row["embedded"]),
        )


class ActivityStore:
    """SQLite-based store for session activities.

    Thread-safe activity logging with FTS5 full-text search.
    Designed for high-volume append operations during sessions.
    """

    def __init__(self, db_path: Path):
        """Initialize the activity store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
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
                timeout=30.0,
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
                cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
                row = cursor.fetchone()
                current_version = row["version"] if row else 0
            except sqlite3.OperationalError:
                current_version = 0

            if current_version < SCHEMA_VERSION:
                if current_version == 0:
                    # Fresh database - apply full schema
                    conn.executescript(SCHEMA_SQL)
                else:
                    # Existing database - apply migrations
                    self._apply_migrations(conn, current_version)

                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
                logger.info(f"Activity store schema initialized (v{SCHEMA_VERSION})")

    def _apply_migrations(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Apply schema migrations from current version to latest.

        Args:
            conn: Database connection (within transaction).
            from_version: Current schema version.
        """
        if from_version < 4:
            self._migrate_v3_to_v4(conn)
        if from_version < 5:
            self._migrate_v4_to_v5(conn)
        if from_version < 6:
            self._migrate_v5_to_v6(conn)
        if from_version < 7:
            self._migrate_v6_to_v7(conn)
        if from_version < 8:
            self._migrate_v7_to_v8(conn)
        if from_version < 9:
            self._migrate_v8_to_v9(conn)

    def _migrate_v3_to_v4(self, conn: sqlite3.Connection) -> None:
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
        cursor = conn.execute(
            """
            UPDATE prompt_batches
            SET source_type = 'agent_notification'
            WHERE user_prompt LIKE '<task-notification>%'
        """
        )
        agent_count = cursor.rowcount

        # Backfill plan batches using PlanDetector for dynamic pattern matching
        plan_count = 0
        try:
            from open_agent_kit.features.codebase_intelligence.plan_detector import PlanDetector

            detector = PlanDetector()

            # Get all activities with Write to potential plan paths
            cursor = conn.execute(
                """
                SELECT DISTINCT prompt_batch_id, file_path
                FROM activities
                WHERE tool_name = 'Write' AND file_path IS NOT NULL AND prompt_batch_id IS NOT NULL
            """
            )

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

    def _migrate_v4_to_v5(self, conn: sqlite3.Connection) -> None:
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
            cursor = conn.execute(
                """
                SELECT id, user_prompt FROM prompt_batches
                WHERE source_type != 'plan' AND user_prompt IS NOT NULL
                """
            )
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

    def _migrate_v5_to_v6(self, conn: sqlite3.Connection) -> None:
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
            cursor = conn.execute(
                """
                SELECT id, plan_file_path FROM prompt_batches
                WHERE source_type = 'plan'
                  AND plan_file_path IS NOT NULL
                  AND (plan_content IS NULL OR plan_content = '')
                """
            )
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

    def _migrate_v6_to_v7(self, conn: sqlite3.Connection) -> None:
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

    def _migrate_v7_to_v8(self, conn: sqlite3.Connection) -> None:
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

    def _migrate_v8_to_v9(self, conn: sqlite3.Connection) -> None:
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

    def optimize_database(self) -> None:
        """Run database optimization (VACUUM + ANALYZE + FTS optimize).

        This should be called periodically (weekly/monthly) or after large deletions
        to maintain performance and reclaim space.

        Note: VACUUM can be slow for large databases. Consider running in background.
        """
        logger.info("Starting database optimization (VACUUM + ANALYZE + FTS optimize)...")

        conn = self._get_connection()

        try:
            # Analyze to update query planner statistics
            conn.execute("ANALYZE")
            logger.debug("Database optimization: ANALYZE complete")

            # Optimize FTS index
            conn.execute("INSERT INTO activities_fts(activities_fts) VALUES('optimize')")
            logger.debug("Database optimization: FTS optimize complete")

            # Vacuum to reclaim space and defragment
            # Note: VACUUM requires exclusive lock, can be slow
            conn.execute("VACUUM")
            logger.info("Database optimization complete (VACUUM + ANALYZE + FTS optimize)")
        except sqlite3.Error as e:
            logger.error(f"Database optimization error: {e}", exc_info=True)
            raise

    # Session operations

    def create_session(self, session_id: str, agent: str, project_root: str) -> Session:
        """Create a new session record.

        Args:
            session_id: Unique session identifier.
            agent: Agent name (claude, cursor, etc.).
            project_root: Project root directory.

        Returns:
            Created Session object.
        """
        session = Session(
            id=session_id,
            agent=agent,
            project_root=project_root,
            started_at=datetime.now(),
        )

        with self._transaction() as conn:
            row = session.to_row()
            conn.execute(
                """
                INSERT INTO sessions (id, agent, project_root, started_at, status,
                                      prompt_count, tool_count, processed, summary, created_at_epoch)
                VALUES (:id, :agent, :project_root, :started_at, :status,
                        :prompt_count, :tool_count, :processed, :summary, :created_at_epoch)
                """,
                row,
            )

        logger.debug(f"Created session {session_id} for agent {agent}")
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return Session.from_row(row) if row else None

    def get_or_create_session(
        self, session_id: str, agent: str, project_root: str
    ) -> tuple[Session, bool]:
        """Get existing session or create new one.

        Handles session resumption gracefully - if session exists, returns it.
        If it was previously ended, reactivates it.
        Idempotent: handles duplicate hook calls and race conditions safely.

        Args:
            session_id: Unique session identifier.
            agent: Agent name (claude, cursor, etc.).
            project_root: Project root directory.

        Returns:
            Tuple of (Session, created) where created is True if new session.
        """
        existing = self.get_session(session_id)
        if existing:
            # Reactivate if previously ended
            if existing.status == "completed":
                with self._transaction() as conn:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET status = 'active', ended_at = NULL
                        WHERE id = ?
                        """,
                        (session_id,),
                    )
                existing.status = "active"
                existing.ended_at = None
                logger.debug(f"Reactivated session {session_id}")
            return existing, False

        # Create new session - handle race condition if another hook created it concurrently
        try:
            session = self.create_session(session_id, agent, project_root)
            return session, True
        except sqlite3.IntegrityError:
            # Race condition: another hook created the session between our check and insert
            # This is safe - just return the existing session
            logger.debug(
                f"Race condition detected: session {session_id} was created concurrently. "
                "Returning existing session."
            )
            existing = self.get_session(session_id)
            if existing:
                return existing, False
            # If we still can't find it, something went wrong - re-raise
            raise

    def end_session(self, session_id: str, summary: str | None = None) -> None:
        """Mark session as completed.

        Args:
            session_id: Session to end.
            summary: Optional session summary.
        """
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = ?, status = 'completed', summary = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), summary, session_id),
            )
        logger.debug(f"Ended session {session_id}")

    def update_session_title(self, session_id: str, title: str) -> None:
        """Update the session title.

        Args:
            session_id: Session to update.
            title: LLM-generated short title for the session.
        """
        with self._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?",
                (title, session_id),
            )
        logger.debug(f"Updated session {session_id} title: {title[:50]}...")

    def reactivate_session_if_needed(self, session_id: str) -> bool:
        """Reactivate a session if it's currently completed.

        Called when new activity arrives for a session that may have been
        auto-closed by stale session recovery. This enables sessions to
        seamlessly resume when Claude Code sends new prompts after a gap.

        This is performant: the UPDATE only affects completed sessions and
        uses the primary key index. For active sessions, it's a no-op.

        Args:
            session_id: Session to potentially reactivate.

        Returns:
            True if session was reactivated, False if already active or not found.
        """
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                SET status = 'active', ended_at = NULL
                WHERE id = ? AND status = 'completed'
                """,
                (session_id,),
            )
            reactivated = cursor.rowcount > 0

        if reactivated:
            logger.info(f"Reactivated completed session {session_id} for new activity")

        return reactivated

    def increment_prompt_count(self, session_id: str) -> None:
        """Increment the prompt count for a session."""
        with self._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET prompt_count = prompt_count + 1 WHERE id = ?",
                (session_id,),
            )

    def get_unprocessed_sessions(self, limit: int = 10) -> list[Session]:
        """Get sessions that haven't been processed yet.

        Args:
            limit: Maximum sessions to return.

        Returns:
            List of unprocessed Session objects.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM sessions
            WHERE processed = FALSE AND status = 'completed'
            ORDER BY created_at_epoch DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [Session.from_row(row) for row in cursor.fetchall()]

    def mark_session_processed(self, session_id: str) -> None:
        """Mark session as processed by background worker."""
        with self._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET processed = TRUE WHERE id = ?",
                (session_id,),
            )

    # Prompt batch operations

    def create_prompt_batch(
        self,
        session_id: str,
        user_prompt: str | None = None,
        source_type: str = "user",
        plan_file_path: str | None = None,
        plan_content: str | None = None,
    ) -> PromptBatch:
        """Create a new prompt batch (when user submits a prompt).

        Args:
            session_id: Parent session ID.
            user_prompt: Full user prompt text (up to 10K chars).
            source_type: Source type (user, agent_notification, plan, system).
            plan_file_path: Path to plan file (for source_type='plan').
            plan_content: Plan content (extracted from prompt or written to file).

        Returns:
            Created PromptBatch with assigned ID.
        """
        # Reactivate session if it was completed (e.g., by stale session recovery).
        # This ensures sessions seamlessly resume when new prompts arrive after a gap.
        # Performant: single UPDATE that only affects completed sessions (no-op if active).
        self.reactivate_session_if_needed(session_id)

        # Get current prompt count for this session
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        prompt_number = (row["count"] or 0) + 1

        batch = PromptBatch(
            session_id=session_id,
            prompt_number=prompt_number,
            user_prompt=user_prompt,
            started_at=datetime.now(),
            source_type=source_type,
            plan_file_path=plan_file_path,
            plan_content=plan_content,
        )

        with self._transaction() as conn:
            row_data = batch.to_row()
            cursor = conn.execute(
                """
                INSERT INTO prompt_batches (session_id, prompt_number, user_prompt,
                                           started_at, status, activity_count, processed,
                                           classification, source_type, plan_file_path,
                                           plan_content, created_at_epoch)
                VALUES (:session_id, :prompt_number, :user_prompt,
                        :started_at, :status, :activity_count, :processed,
                        :classification, :source_type, :plan_file_path,
                        :plan_content, :created_at_epoch)
                """,
                row_data,
            )
            batch.id = cursor.lastrowid

            # Update session prompt count
            conn.execute(
                "UPDATE sessions SET prompt_count = prompt_count + 1 WHERE id = ?",
                (session_id,),
            )

        logger.debug(
            f"Created prompt batch {batch.id} (prompt #{prompt_number}, source={source_type}) "
            f"for session {session_id}"
        )
        return batch

    def get_prompt_batch(self, batch_id: int) -> PromptBatch | None:
        """Get prompt batch by ID."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM prompt_batches WHERE id = ?", (batch_id,))
        row = cursor.fetchone()
        return PromptBatch.from_row(row) if row else None

    def get_active_prompt_batch(self, session_id: str) -> PromptBatch | None:
        """Get the current active prompt batch for a session.

        Args:
            session_id: Session to query.

        Returns:
            Active PromptBatch if one exists, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE session_id = ? AND status = 'active'
            ORDER BY prompt_number DESC
            LIMIT 1
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        return PromptBatch.from_row(row) if row else None

    def end_prompt_batch(self, batch_id: int) -> None:
        """Mark a prompt batch as completed (when agent stops responding).

        Args:
            batch_id: Prompt batch to end.
        """
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE prompt_batches
                SET ended_at = ?, status = 'completed'
                WHERE id = ?
                """,
                (datetime.now().isoformat(), batch_id),
            )
        logger.debug(f"Ended prompt batch {batch_id}")

    def get_unprocessed_prompt_batches(self, limit: int = 10) -> list[PromptBatch]:
        """Get prompt batches that haven't been processed yet.

        Args:
            limit: Maximum batches to return.

        Returns:
            List of unprocessed PromptBatch objects (completed but not processed).
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE processed = FALSE AND status = 'completed'
            ORDER BY created_at_epoch ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [PromptBatch.from_row(row) for row in cursor.fetchall()]

    def mark_prompt_batch_processed(
        self,
        batch_id: int,
        classification: str | None = None,
    ) -> None:
        """Mark prompt batch as processed.

        Args:
            batch_id: Batch to mark.
            classification: LLM classification result.
        """
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE prompt_batches
                SET processed = TRUE, classification = ?
                WHERE id = ?
                """,
                (classification, batch_id),
            )

    def update_prompt_batch_source_type(
        self,
        batch_id: int,
        source_type: str,
        plan_file_path: str | None = None,
        plan_content: str | None = None,
    ) -> None:
        """Update the source type for a prompt batch.

        Used when plan mode is detected mid-batch (e.g., Write to plans directory).

        Args:
            batch_id: Batch to update.
            source_type: New source type (user, agent_notification, plan, system).
            plan_file_path: Path to plan file (for source_type='plan').
            plan_content: Full plan content (for source_type='plan').
        """
        # Truncate plan content to max length
        if plan_content and len(plan_content) > PromptBatch.MAX_PLAN_CONTENT_LENGTH:
            plan_content = plan_content[: PromptBatch.MAX_PLAN_CONTENT_LENGTH]

        with self._transaction() as conn:
            if plan_file_path or plan_content:
                conn.execute(
                    """
                    UPDATE prompt_batches
                    SET source_type = ?, plan_file_path = ?, plan_content = ?
                    WHERE id = ?
                    """,
                    (source_type, plan_file_path, plan_content, batch_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE prompt_batches
                    SET source_type = ?
                    WHERE id = ?
                    """,
                    (source_type, batch_id),
                )
        logger.debug(f"Updated prompt batch {batch_id} source_type to {source_type}")

    def get_session_prompt_batches(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[PromptBatch]:
        """Get all prompt batches for a session.

        Args:
            session_id: Session to query.
            limit: Maximum batches to return.

        Returns:
            List of PromptBatch objects in chronological order.
        """
        conn = self._get_connection()

        query = """
            SELECT * FROM prompt_batches
            WHERE session_id = ?
            ORDER BY prompt_number ASC
        """
        params: list[Any] = [session_id]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [PromptBatch.from_row(row) for row in cursor.fetchall()]

    def recover_stuck_batches(self, timeout_seconds: int = 1800) -> int:
        """Auto-end batches stuck in 'active' status for too long.

        This handles cases where the session ended unexpectedly (crash, network
        disconnect) without calling the stop hook.

        Args:
            timeout_seconds: Batches active longer than this are auto-ended.

        Returns:
            Number of batches recovered.
        """
        import time

        cutoff_epoch = time.time() - timeout_seconds

        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE prompt_batches
                SET status = 'completed'
                WHERE status = 'active' AND created_at_epoch < ?
                RETURNING id
                """,
                (cutoff_epoch,),
            )
            recovered_ids = [row[0] for row in cursor.fetchall()]

        if recovered_ids:
            logger.info(
                f"Recovered {len(recovered_ids)} stuck batches "
                f"(active > {timeout_seconds}s): {recovered_ids}"
            )

        return len(recovered_ids)

    def recover_stale_sessions(self, timeout_seconds: int = 3600) -> list[str]:
        """Auto-end sessions that have been inactive for too long.

        This handles cases where the SessionEnd hook didn't fire (crash, network
        disconnect, user closed terminal without proper exit).

        A session is considered stale if:
        - It has activities and the most recent activity is older than timeout_seconds
        - It has NO activities and was created more than timeout_seconds ago

        Args:
            timeout_seconds: Sessions inactive longer than this are auto-ended.

        Returns:
            List of recovered session IDs (for state synchronization).
        """
        import time

        cutoff_epoch = time.time() - timeout_seconds

        # Find active sessions with no recent activity
        # IMPORTANT: For sessions with no activities, check created_at_epoch
        # to avoid marking brand new sessions as stale
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT s.id, MAX(a.timestamp_epoch) as last_activity, s.created_at_epoch
            FROM sessions s
            LEFT JOIN activities a ON s.id = a.session_id
            WHERE s.status = 'active'
            GROUP BY s.id
            HAVING (last_activity IS NOT NULL AND last_activity < ?)
                OR (last_activity IS NULL AND s.created_at_epoch < ?)
            """,
            (cutoff_epoch, cutoff_epoch),
        )
        stale_sessions = [(row[0], row[1], row[2]) for row in cursor.fetchall()]

        if not stale_sessions:
            return []

        recovered_ids = []
        with self._transaction() as conn:
            for session_id, _last_activity, _created_at in stale_sessions:
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'completed', ended_at = ?
                    WHERE id = ? AND status = 'active'
                    """,
                    (datetime.now().isoformat(), session_id),
                )
                recovered_ids.append(session_id)

        logger.info(
            f"Recovered {len(recovered_ids)} stale sessions "
            f"(inactive > {timeout_seconds}s): {[s[:8] for s in recovered_ids]}"
        )

        return recovered_ids

    def recover_orphaned_activities(self) -> int:
        """Associate orphaned activities (NULL batch) with appropriate batches.

        For each orphaned activity, finds the most recent batch for that session
        and associates the activity with it. If no batch exists, creates a
        recovery batch.

        Returns:
            Number of activities recovered.
        """
        conn = self._get_connection()

        # Find sessions with orphaned activities
        cursor = conn.execute(
            """
            SELECT DISTINCT session_id, COUNT(*) as orphan_count
            FROM activities
            WHERE prompt_batch_id IS NULL
            GROUP BY session_id
            """
        )
        orphan_sessions = cursor.fetchall()

        if not orphan_sessions:
            return 0

        total_recovered = 0

        for session_id, orphan_count in orphan_sessions:
            # Find the most recent batch for this session
            cursor = conn.execute(
                """
                SELECT id FROM prompt_batches
                WHERE session_id = ?
                ORDER BY created_at_epoch DESC
                LIMIT 1
                """,
                (session_id,),
            )
            batch_row = cursor.fetchone()

            if batch_row:
                batch_id = batch_row[0]
            else:
                # Create a recovery batch for this session
                import time

                with self._transaction() as tx_conn:
                    tx_conn.execute(
                        """
                        INSERT INTO prompt_batches
                        (session_id, prompt_number, user_prompt, created_at_epoch, status)
                        VALUES (?, 0, '[Recovery batch for orphaned activities]', ?, 'completed')
                        """,
                        (session_id, time.time()),
                    )
                    cursor = tx_conn.execute("SELECT last_insert_rowid()")
                    batch_id = cursor.fetchone()[0]
                    logger.info(f"Created recovery batch {batch_id} for session {session_id}")

            # Associate orphaned activities with the batch
            with self._transaction() as tx_conn:
                tx_conn.execute(
                    """
                    UPDATE activities
                    SET prompt_batch_id = ?
                    WHERE session_id = ? AND prompt_batch_id IS NULL
                    """,
                    (batch_id, session_id),
                )

            logger.info(
                f"Recovered {orphan_count} orphaned activities for session "
                f"{session_id[:8]}... -> batch {batch_id}"
            )
            total_recovered += orphan_count

        return total_recovered

    def get_prompt_batch_activities(
        self,
        batch_id: int,
        limit: int | None = None,
    ) -> list[Activity]:
        """Get all activities for a prompt batch.

        Args:
            batch_id: Prompt batch ID.
            limit: Maximum activities to return.

        Returns:
            List of Activity objects in chronological order.
        """
        conn = self._get_connection()

        query = "SELECT * FROM activities WHERE prompt_batch_id = ? ORDER BY timestamp_epoch ASC"
        params: list[Any] = [batch_id]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [Activity.from_row(row) for row in cursor.fetchall()]

    def get_prompt_batch_stats(self, batch_id: int) -> dict[str, Any]:
        """Get statistics for a prompt batch.

        Args:
            batch_id: Prompt batch to query.

        Returns:
            Dictionary with batch statistics.
        """
        conn = self._get_connection()

        # Tool counts by name
        cursor = conn.execute(
            """
            SELECT tool_name, COUNT(*) as count
            FROM activities
            WHERE prompt_batch_id = ?
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (batch_id,),
        )
        tool_counts = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

        # File and error counts
        cursor = conn.execute(
            """
            SELECT
                COUNT(DISTINCT file_path) as files_touched,
                SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
                SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
                SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
                SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
            FROM activities
            WHERE prompt_batch_id = ?
            """,
            (batch_id,),
        )
        row = cursor.fetchone()

        return {
            "tool_counts": tool_counts,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
        }

    # Activity operations

    def add_activity(self, activity: Activity) -> int:
        """Add a tool execution activity.

        Args:
            activity: Activity to store.

        Returns:
            ID of inserted activity.
        """
        with self._transaction() as conn:
            row = activity.to_row()
            cursor = conn.execute(
                """
                INSERT INTO activities (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                                       file_path, files_affected, duration_ms, success,
                                       error_message, timestamp, timestamp_epoch, processed, observation_id)
                VALUES (:session_id, :prompt_batch_id, :tool_name, :tool_input, :tool_output_summary,
                        :file_path, :files_affected, :duration_ms, :success,
                        :error_message, :timestamp, :timestamp_epoch, :processed, :observation_id)
                """,
                row,
            )
            # Update session tool count
            conn.execute(
                "UPDATE sessions SET tool_count = tool_count + 1 WHERE id = ?",
                (activity.session_id,),
            )
            # Update prompt batch activity count if linked
            if activity.prompt_batch_id:
                conn.execute(
                    "UPDATE prompt_batches SET activity_count = activity_count + 1 WHERE id = ?",
                    (activity.prompt_batch_id,),
                )
            # Invalidate cache for this session
            self._invalidate_stats_cache(activity.session_id)
            return cursor.lastrowid or 0

    def flush_activity_buffer(self) -> list[int]:
        """Flush any buffered activities to the database.

        Returns:
            List of inserted activity IDs.
        """
        with self._buffer_lock:
            if not self._activity_buffer:
                return []
            activities = self._activity_buffer[:]
            self._activity_buffer.clear()

        if activities:
            count = len(activities)
            ids = self.add_activities(activities)
            logger.debug(f"Flushed {count} buffered activities (bulk insert)")
            return ids
        return []

    def add_activity_buffered(self, activity: Activity, force_flush: bool = False) -> int | None:
        """Add an activity with automatic batching.

        Activities are buffered and flushed when the buffer reaches _buffer_size.
        This provides better performance for rapid tool execution while maintaining
        low latency for debugging.

        Args:
            activity: Activity to add.
            force_flush: If True, flush buffer immediately after adding.

        Returns:
            Activity ID if flushed immediately, None if buffered.
        """
        with self._buffer_lock:
            self._activity_buffer.append(activity)
            should_flush = len(self._activity_buffer) >= self._buffer_size or force_flush

            if should_flush:
                activities = self._activity_buffer[:]
                self._activity_buffer.clear()
            else:
                activities = None

        if activities:
            count = len(activities)
            ids = self.add_activities(activities)
            logger.debug(f"Bulk inserted {count} activities (buffer auto-flush)")
            # Return the ID of the activity we just added (last in batch)
            return ids[-1] if ids else None
        return None

    def add_activities(self, activities: list[Activity]) -> list[int]:
        """Add multiple activities in a single transaction (bulk insert).

        This method is more efficient than calling add_activity() multiple times
        as it uses a single transaction and batches count updates.

        Args:
            activities: List of activities to insert.

        Returns:
            List of inserted activity IDs.
        """
        if not activities:
            return []

        count = len(activities)
        ids: list[int] = []
        session_updates: dict[str, int] = {}  # session_id -> count delta
        batch_updates: dict[int, int] = {}  # batch_id -> count delta
        affected_sessions: set[str] = set()

        logger.debug(f"Bulk inserting {count} activities in single transaction")

        with self._transaction() as conn:
            for activity in activities:
                row = activity.to_row()
                cursor = conn.execute(
                    """
                    INSERT INTO activities (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                                           file_path, files_affected, duration_ms, success,
                                           error_message, timestamp, timestamp_epoch, processed, observation_id)
                    VALUES (:session_id, :prompt_batch_id, :tool_name, :tool_input, :tool_output_summary,
                            :file_path, :files_affected, :duration_ms, :success,
                            :error_message, :timestamp, :timestamp_epoch, :processed, :observation_id)
                    """,
                    row,
                )
                ids.append(cursor.lastrowid or 0)

                # Track updates needed
                session_updates[activity.session_id] = (
                    session_updates.get(activity.session_id, 0) + 1
                )
                affected_sessions.add(activity.session_id)
                if activity.prompt_batch_id:
                    batch_updates[activity.prompt_batch_id] = (
                        batch_updates.get(activity.prompt_batch_id, 0) + 1
                    )

            # Bulk update session counts
            for session_id, delta in session_updates.items():
                conn.execute(
                    "UPDATE sessions SET tool_count = tool_count + ? WHERE id = ?",
                    (delta, session_id),
                )

            # Bulk update batch counts
            for batch_id, delta in batch_updates.items():
                conn.execute(
                    "UPDATE prompt_batches SET activity_count = activity_count + ? WHERE id = ?",
                    (delta, batch_id),
                )

        # Invalidate cache for all affected sessions
        for session_id in affected_sessions:
            self._invalidate_stats_cache(session_id)

        logger.debug(
            f"Bulk insert complete: {len(ids)} activities inserted for {len(affected_sessions)} sessions"
        )
        return ids

    def get_session_activities(
        self,
        session_id: str,
        tool_name: str | None = None,
        limit: int | None = None,
    ) -> list[Activity]:
        """Get activities for a session.

        Args:
            session_id: Session to query.
            tool_name: Optional filter by tool name.
            limit: Maximum activities to return.

        Returns:
            List of Activity objects.
        """
        conn = self._get_connection()

        query = "SELECT * FROM activities WHERE session_id = ?"
        params: list[Any] = [session_id]

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)

        query += " ORDER BY timestamp_epoch ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [Activity.from_row(row) for row in cursor.fetchall()]

    def get_unprocessed_activities(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[Activity]:
        """Get activities that haven't been processed yet.

        Args:
            session_id: Optional session filter.
            limit: Maximum activities to return.

        Returns:
            List of unprocessed Activity objects.
        """
        conn = self._get_connection()

        if session_id:
            cursor = conn.execute(
                """
                SELECT * FROM activities
                WHERE processed = FALSE AND session_id = ?
                ORDER BY timestamp_epoch ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM activities
                WHERE processed = FALSE
                ORDER BY timestamp_epoch ASC
                LIMIT ?
                """,
                (limit,),
            )

        return [Activity.from_row(row) for row in cursor.fetchall()]

    def mark_activities_processed(
        self,
        activity_ids: list[int],
        observation_id: str | None = None,
    ) -> None:
        """Mark activities as processed.

        Args:
            activity_ids: Activities to mark.
            observation_id: Optional observation ID to link.
        """
        if not activity_ids:
            return

        with self._transaction() as conn:
            placeholders = ",".join("?" * len(activity_ids))
            params: list[str | int | None] = [observation_id, *activity_ids]
            conn.execute(
                f"""
                UPDATE activities
                SET processed = TRUE, observation_id = ?
                WHERE id IN ({placeholders})
                """,
                params,
            )

    # Search operations

    def search_activities(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[Activity]:
        """Full-text search across activities.

        Args:
            query: Search query (FTS5 syntax).
            session_id: Optional session filter.
            limit: Maximum results.

        Returns:
            List of matching Activity objects.
        """
        conn = self._get_connection()

        if session_id:
            cursor = conn.execute(
                """
                SELECT a.* FROM activities a
                JOIN activities_fts fts ON a.id = fts.rowid
                WHERE activities_fts MATCH ? AND a.session_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, session_id, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT a.* FROM activities a
                JOIN activities_fts fts ON a.id = fts.rowid
                WHERE activities_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )

        return [Activity.from_row(row) for row in cursor.fetchall()]

    # Statistics

    def _invalidate_stats_cache(self, session_id: str | None = None) -> None:
        """Invalidate stats cache for a specific session or all sessions.

        Args:
            session_id: Session ID to invalidate, or None to clear all cache.
        """
        with self._cache_lock:
            if session_id:
                # Remove specific session from cache
                keys_to_remove = [
                    k for k in self._stats_cache.keys() if k.startswith(f"stats:{session_id}")
                ]
                for key in keys_to_remove:
                    self._stats_cache.pop(key, None)
            else:
                # Clear all cache
                self._stats_cache.clear()

    def _get_cached_stats(self, cache_key: str) -> dict[str, Any] | None:
        """Get cached stats if still valid.

        Args:
            cache_key: Cache key (e.g., "stats:session-id").

        Returns:
            Cached stats dict if valid, None otherwise.
        """
        with self._cache_lock:
            if cache_key in self._stats_cache:
                cached_data, cached_time = self._stats_cache[cache_key]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_data
                # Expired, remove it
                self._stats_cache.pop(cache_key, None)
        return None

    def _set_cached_stats(self, cache_key: str, data: dict[str, Any]) -> None:
        """Cache stats data.

        Args:
            cache_key: Cache key (e.g., "stats:session-id").
            data: Stats data to cache.
        """
        with self._cache_lock:
            # Clean up old entries periodically (keep cache size reasonable)
            if len(self._stats_cache) > 1000:
                now = time.time()
                self._stats_cache = {
                    k: v for k, v in self._stats_cache.items() if now - v[1] < self._cache_ttl
                }
            self._stats_cache[cache_key] = (data, time.time())

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get statistics for a session (with low TTL caching for debugging).

        Args:
            session_id: Session to query.

        Returns:
            Dictionary with session statistics.
        """
        # Check cache first (low TTL for near real-time debugging)
        cache_key = f"stats:{session_id}"
        cached = self._get_cached_stats(cache_key)
        if cached is not None:
            logger.debug(f"Session stats cache hit: {session_id}")
            return cached

        conn = self._get_connection()

        # Tool counts by name
        cursor = conn.execute(
            """
            SELECT tool_name, COUNT(*) as count
            FROM activities
            WHERE session_id = ?
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (session_id,),
        )
        tool_counts = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

        # File operation counts
        cursor = conn.execute(
            """
            SELECT
                COUNT(DISTINCT file_path) as files_touched,
                SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
                SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
                SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
                SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
            FROM activities
            WHERE session_id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()

        # Get total activity count
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM activities WHERE session_id = ?",
            (session_id,),
        )
        activity_count = cursor.fetchone()["count"]

        # Get prompt batch count
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
            (session_id,),
        )
        prompt_batch_count = cursor.fetchone()["count"]

        stats = {
            "tool_counts": tool_counts,
            "activity_count": activity_count,
            "prompt_batch_count": prompt_batch_count,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
        }

        # Cache the result
        self._set_cached_stats(cache_key, stats)
        logger.debug(f"Session stats cached: {session_id} (TTL: {self._cache_ttl}s)")
        return stats

    def get_bulk_session_stats(self, session_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get statistics for multiple sessions in a single query.

        This method eliminates the N+1 query pattern by fetching stats for
        all sessions in a single aggregated query.

        Args:
            session_ids: List of session IDs to query.

        Returns:
            Dictionary mapping session_id -> stats dict with keys:
            - tool_counts: dict[str, int] - Tool name -> count
            - activity_count: int
            - prompt_batch_count: int
            - files_touched: int
            - reads: int
            - edits: int
            - writes: int
            - errors: int
        """
        if not session_ids:
            return {}

        conn = self._get_connection()

        # Build placeholders for IN clause
        placeholders = ",".join("?" * len(session_ids))

        # Single aggregated query for all sessions
        cursor = conn.execute(
            f"""
            SELECT
                a.session_id,
                COUNT(DISTINCT a.id) as activity_count,
                COUNT(DISTINCT a.file_path) as files_touched,
                SUM(CASE WHEN a.tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
                SUM(CASE WHEN a.tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
                SUM(CASE WHEN a.tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
                SUM(CASE WHEN a.success = FALSE THEN 1 ELSE 0 END) as errors,
                COUNT(DISTINCT pb.id) as prompt_batch_count
            FROM activities a
            LEFT JOIN prompt_batches pb ON a.session_id = pb.session_id
            WHERE a.session_id IN ({placeholders})
            GROUP BY a.session_id
            """,
            session_ids,
        )

        # Build result dict with aggregated stats
        stats_map: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            session_id = row["session_id"]

            # Get tool counts for this session (still need separate query for tool breakdown)
            tool_cursor = conn.execute(
                """
                SELECT tool_name, COUNT(*) as count
                FROM activities
                WHERE session_id = ?
                GROUP BY tool_name
                ORDER BY count DESC
                """,
                (session_id,),
            )
            tool_counts = {r["tool_name"]: r["count"] for r in tool_cursor.fetchall()}

            stats_map[session_id] = {
                "tool_counts": tool_counts,
                "activity_count": row["activity_count"] or 0,
                "prompt_batch_count": row["prompt_batch_count"] or 0,
                "files_touched": row["files_touched"] or 0,
                "reads": row["reads"] or 0,
                "edits": row["edits"] or 0,
                "writes": row["writes"] or 0,
                "errors": row["errors"] or 0,
            }

        # Fill in missing sessions (sessions with no activities)
        for session_id in session_ids:
            if session_id not in stats_map:
                # Still need prompt_batch_count even if no activities
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
                    (session_id,),
                )
                prompt_batch_count = cursor.fetchone()["count"]

                stats_map[session_id] = {
                    "tool_counts": {},
                    "activity_count": 0,
                    "prompt_batch_count": prompt_batch_count or 0,
                    "files_touched": 0,
                    "reads": 0,
                    "edits": 0,
                    "writes": 0,
                    "errors": 0,
                }

        return stats_map

    def get_bulk_first_prompts(
        self, session_ids: list[str], max_length: int = 100
    ) -> dict[str, str | None]:
        """Get the first user prompt preview for multiple sessions efficiently.

        This method fetches the first prompt batch's user_prompt for each session
        in a single query, avoiding N+1 patterns.

        Args:
            session_ids: List of session IDs to query.
            max_length: Maximum length of the prompt preview (truncated with ...).

        Returns:
            Dictionary mapping session_id -> first prompt preview (or None).
        """
        if not session_ids:
            return {}

        conn = self._get_connection()
        placeholders = ",".join("?" * len(session_ids))

        # Get first prompt batch for each session (by prompt_number=1)
        cursor = conn.execute(
            f"""
            SELECT session_id, user_prompt
            FROM prompt_batches
            WHERE session_id IN ({placeholders})
              AND prompt_number = 1
              AND user_prompt IS NOT NULL
              AND user_prompt != ''
            """,
            session_ids,
        )

        result: dict[str, str | None] = {}
        for row in cursor.fetchall():
            session_id = row["session_id"]
            user_prompt = row["user_prompt"]

            if user_prompt:
                # Clean up the prompt: take first line or truncate
                preview = user_prompt.strip()
                # If it starts with a plan prefix, remove it for cleaner display
                if preview.startswith("Implement the following plan:"):
                    preview = preview[len("Implement the following plan:") :].strip()
                # Take first meaningful line (skip empty lines)
                lines = [line.strip() for line in preview.split("\n") if line.strip()]
                if lines:
                    preview = lines[0]
                # Truncate if needed
                if len(preview) > max_length:
                    preview = preview[:max_length].rstrip() + "..."
                result[session_id] = preview
            else:
                result[session_id] = None

        # Fill in missing sessions
        for session_id in session_ids:
            if session_id not in result:
                result[session_id] = None

        return result

    def get_recent_sessions(
        self,
        limit: int = 10,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Session]:
        """Get recent sessions with pagination support.

        Args:
            limit: Maximum sessions to return.
            offset: Number of sessions to skip (for pagination).
            status: Optional status filter (e.g., 'active', 'completed').

        Returns:
            List of recent Session objects.
        """
        conn = self._get_connection()

        query = "SELECT * FROM sessions"
        params: list[Any] = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at_epoch DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [Session.from_row(row) for row in cursor.fetchall()]

    def get_sessions_needing_titles(self, limit: int = 10) -> list[Session]:
        """Get sessions that need titles generated.

        Returns sessions that:
        - Don't have a title yet
        - Have at least one prompt batch (so we can generate a title)
        - Are either completed or have been active for at least 5 minutes

        Args:
            limit: Maximum sessions to return.

        Returns:
            List of Session objects needing titles.
        """
        conn = self._get_connection()

        # Get sessions without titles that have prompt batches
        # Only process sessions that are either completed OR have been active 5+ minutes
        five_minutes_ago = int(time.time()) - 300
        cursor = conn.execute(
            """
            SELECT s.* FROM sessions s
            WHERE s.title IS NULL
            AND EXISTS (SELECT 1 FROM prompt_batches pb WHERE pb.session_id = s.id)
            AND (s.status = 'completed' OR s.created_at_epoch < ?)
            ORDER BY s.created_at_epoch DESC
            LIMIT ?
            """,
            (five_minutes_ago, limit),
        )
        return [Session.from_row(row) for row in cursor.fetchall()]

    # Memory observation operations (source of truth for memories)

    def store_observation(self, observation: StoredObservation) -> str:
        """Store a memory observation in SQLite.

        This is the source of truth. ChromaDB embedding happens separately.

        Args:
            observation: The observation to store.

        Returns:
            The observation ID.
        """
        with self._transaction() as conn:
            row = observation.to_row()
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_observations
                (id, session_id, prompt_batch_id, observation, memory_type,
                 context, tags, importance, file_path, created_at, created_at_epoch, embedded)
                VALUES (:id, :session_id, :prompt_batch_id, :observation, :memory_type,
                        :context, :tags, :importance, :file_path, :created_at,
                        :created_at_epoch, :embedded)
                """,
                row,
            )

        logger.debug(f"Stored observation {observation.id} for session {observation.session_id}")
        return observation.id

    def get_observation(self, observation_id: str) -> StoredObservation | None:
        """Get an observation by ID.

        Args:
            observation_id: The observation ID.

        Returns:
            The observation or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM memory_observations WHERE id = ?",
            (observation_id,),
        )
        row = cursor.fetchone()
        return StoredObservation.from_row(row) if row else None

    def get_latest_session_summary(self, session_id: str) -> StoredObservation | None:
        """Get the most recent session_summary observation for a session.

        Used to check if a session has already been summarized, and when,
        so we can avoid duplicate summaries on session resume.

        Args:
            session_id: The session ID.

        Returns:
            The most recent session_summary observation or None if none exists.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM memory_observations
            WHERE session_id = ? AND memory_type = 'session_summary'
            ORDER BY created_at_epoch DESC
            LIMIT 1
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        return StoredObservation.from_row(row) if row else None

    def get_unembedded_observations(self, limit: int = 100) -> list[StoredObservation]:
        """Get observations that haven't been added to ChromaDB.

        Used for rebuilding the ChromaDB index from SQLite.

        Args:
            limit: Maximum observations to return.

        Returns:
            List of unembedded observations.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM memory_observations
            WHERE embedded = FALSE
            ORDER BY created_at_epoch
            LIMIT ?
            """,
            (limit,),
        )
        return [StoredObservation.from_row(row) for row in cursor.fetchall()]

    def mark_observation_embedded(self, observation_id: str) -> None:
        """Mark an observation as embedded in ChromaDB.

        Args:
            observation_id: The observation ID.
        """
        with self._transaction() as conn:
            conn.execute(
                "UPDATE memory_observations SET embedded = TRUE WHERE id = ?",
                (observation_id,),
            )

    def mark_observations_embedded(self, observation_ids: list[str]) -> None:
        """Mark multiple observations as embedded in ChromaDB.

        Args:
            observation_ids: List of observation IDs.
        """
        if not observation_ids:
            return

        with self._transaction() as conn:
            placeholders = ",".join("?" * len(observation_ids))
            conn.execute(
                f"UPDATE memory_observations SET embedded = TRUE WHERE id IN ({placeholders})",
                observation_ids,
            )

    def mark_all_observations_unembedded(self) -> int:
        """Mark all observations as not embedded (for full ChromaDB rebuild).

        Returns:
            Number of observations marked.
        """
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE memory_observations SET embedded = FALSE WHERE embedded = TRUE"
            )
            count = cursor.rowcount

        logger.info(f"Marked {count} observations as unembedded for rebuild")
        return count

    def count_observations(self) -> int:
        """Count total observations in SQLite.

        Returns:
            Total observation count.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM memory_observations")
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    def count_embedded_observations(self) -> int:
        """Count observations that are in ChromaDB.

        Returns:
            Embedded observation count.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM memory_observations WHERE embedded = TRUE")
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    def count_unembedded_observations(self) -> int:
        """Count observations not yet in ChromaDB.

        Returns:
            Unembedded observation count.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM memory_observations WHERE embedded = FALSE")
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    # ==========================================================================
    # Plan Embedding Operations (for semantic search of plans)
    # ==========================================================================

    def get_unembedded_plans(self, limit: int = 50) -> list[PromptBatch]:
        """Get plan batches that haven't been embedded in ChromaDB yet.

        Returns batches where:
        - source_type = 'plan'
        - plan_content is not empty
        - plan_embedded = FALSE

        Args:
            limit: Maximum batches to return.

        Returns:
            List of PromptBatch objects needing embedding.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE source_type = 'plan'
              AND plan_content IS NOT NULL
              AND plan_content != ''
              AND (plan_embedded IS NULL OR plan_embedded = 0)
            ORDER BY created_at_epoch ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [PromptBatch.from_row(row) for row in cursor.fetchall()]

    def mark_plan_embedded(self, batch_id: int) -> None:
        """Mark a plan batch as embedded in ChromaDB.

        Args:
            batch_id: The prompt batch ID to mark.
        """
        with self._transaction() as conn:
            conn.execute(
                "UPDATE prompt_batches SET plan_embedded = 1 WHERE id = ?",
                (batch_id,),
            )
        logger.debug(f"Marked plan batch {batch_id} as embedded")

    def count_unembedded_plans(self) -> int:
        """Count plan batches not yet in ChromaDB.

        Returns:
            Unembedded plan count.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM prompt_batches
            WHERE source_type = 'plan'
              AND plan_content IS NOT NULL
              AND plan_content != ''
              AND (plan_embedded IS NULL OR plan_embedded = 0)
            """
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    def mark_all_plans_unembedded(self) -> int:
        """Mark all plans as not embedded (for full ChromaDB rebuild).

        Returns:
            Number of plans marked.
        """
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE prompt_batches SET plan_embedded = 0 WHERE plan_embedded = 1"
            )
            count = cursor.rowcount

        logger.info(f"Marked {count} plans as unembedded for rebuild")
        return count

    # ==========================================================================
    # Backup and Restore Operations
    # ==========================================================================

    def export_to_sql(self, output_path: Path, include_activities: bool = False) -> int:
        """Export valuable tables to SQL dump file.

        Exports sessions, prompt_batches, and memory_observations to a SQL file
        that can be used to restore data after feature removal/reinstall.
        The file is text-based and can be committed to git.

        Args:
            output_path: Path to write SQL dump file.
            include_activities: If True, include activities table (can be large).

        Returns:
            Number of records exported.
        """
        logger.info(
            f"Exporting database: include_activities={include_activities}, path={output_path}"
        )

        conn = self._get_connection()
        total_count = 0

        # Tables to export (order matters for foreign keys)
        tables = ["sessions", "prompt_batches", "memory_observations"]
        if include_activities:
            tables.append("activities")

        # Generate INSERT statements
        lines: list[str] = []
        lines.append("-- OAK Codebase Intelligence History Backup")
        lines.append(f"-- Exported: {datetime.now().isoformat()}")
        lines.append(f"-- Schema version: {SCHEMA_VERSION}")
        lines.append("")

        for table in tables:
            cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608 - trusted table names
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            if rows:
                lines.append(f"-- {table} ({len(rows)} records)")
                for row in rows:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, bool):
                            values.append("1" if val else "0")
                        else:
                            # Escape single quotes for SQL
                            escaped = str(val).replace("'", "''")
                            values.append(f"'{escaped}'")

                    cols_str = ", ".join(columns)
                    vals_str = ", ".join(values)
                    lines.append(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});")

                total_count += len(rows)
                lines.append("")

            logger.debug(f"Exported {len(rows)} records from {table}")

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")

        logger.info(f"Export complete: {total_count} records to {output_path}")
        return total_count

    def import_from_sql(self, backup_path: Path) -> int:
        """Import data from SQL backup into existing database.

        The database should already have the current schema (via _ensure_schema).
        This method imports data only, not schema. All imported observations
        are marked as unembedded to trigger ChromaDB rebuild.

        Args:
            backup_path: Path to SQL backup file.

        Returns:
            Number of records imported.
        """
        logger.info(f"Importing from backup: {backup_path}")

        content = backup_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Extract INSERT statements
        insert_statements: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("INSERT INTO"):
                insert_statements.append(stripped)

        logger.debug(f"Found {len(insert_statements)} INSERT statements")

        total_imported = 0
        failed_count = 0

        with self._transaction() as conn:
            for stmt in insert_statements:
                try:
                    # For memory_observations, mark as unembedded
                    if "INSERT INTO memory_observations" in stmt:
                        # Replace embedded value to FALSE for rebuild
                        # The embedded column is typically the last one
                        stmt = stmt.replace(", 1);", ", 0);")
                        stmt = stmt.replace(", TRUE);", ", FALSE);")

                    # For prompt_batches, reset plan_embedded for re-indexing
                    if "INSERT INTO prompt_batches" in stmt:
                        # Reset plan_embedded to 0 so plans get re-indexed
                        stmt = re.sub(r"plan_embedded\s*=\s*1", "plan_embedded = 0", stmt)
                        # Also handle column-value format in INSERT
                        stmt = stmt.replace(", 1)", ", 0)")  # Only if plan_embedded is last

                    conn.execute(stmt)
                    total_imported += 1
                except sqlite3.Error as e:
                    # Log but continue - some records may conflict
                    logger.debug(f"Skipping duplicate or invalid record: {e}")
                    failed_count += 1

        if failed_count > 0:
            logger.warning(f"Skipped {failed_count} records during import (duplicates/conflicts)")

        logger.info(f"Import complete: {total_imported} records restored from {backup_path}")
        return total_imported

    # ==========================================================================
    # Delete Operations (cascade)
    # ==========================================================================

    def get_session_observation_ids(self, session_id: str) -> list[str]:
        """Get all observation IDs for a session (for ChromaDB cleanup).

        Args:
            session_id: Session to query.

        Returns:
            List of observation IDs linked to this session.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id FROM memory_observations WHERE session_id = ?",
            (session_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_batch_observation_ids(self, batch_id: int) -> list[str]:
        """Get all observation IDs for a prompt batch (for ChromaDB cleanup).

        Args:
            batch_id: Prompt batch ID to query.

        Returns:
            List of observation IDs linked to this batch.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id FROM memory_observations WHERE prompt_batch_id = ?",
            (batch_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation from SQLite.

        Args:
            observation_id: The observation ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_observations WHERE id = ?",
                (observation_id,),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted observation {observation_id}")
        return deleted

    def delete_activity(self, activity_id: int) -> str | None:
        """Delete a single activity.

        Args:
            activity_id: The activity ID to delete.

        Returns:
            The linked observation_id if any (for ChromaDB cleanup), None otherwise.
        """
        conn = self._get_connection()

        # Get the observation_id before deleting (if any)
        cursor = conn.execute(
            "SELECT observation_id FROM activities WHERE id = ?",
            (activity_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        observation_id: str | None = row[0]

        with self._transaction() as conn:
            conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))

        logger.info(f"Deleted activity {activity_id}")
        return observation_id

    def delete_prompt_batch(self, batch_id: int) -> dict[str, int]:
        """Delete a prompt batch and all related data.

        Cascade deletes:
        - Activities linked to this batch
        - Memory observations linked to this batch

        Args:
            batch_id: The prompt batch ID to delete.

        Returns:
            Dictionary with counts: activities_deleted, observations_deleted
        """
        result = {"activities_deleted": 0, "observations_deleted": 0}

        with self._transaction() as conn:
            # Delete activities for this batch
            cursor = conn.execute(
                "DELETE FROM activities WHERE prompt_batch_id = ?",
                (batch_id,),
            )
            result["activities_deleted"] = cursor.rowcount

            # Delete observations for this batch
            cursor = conn.execute(
                "DELETE FROM memory_observations WHERE prompt_batch_id = ?",
                (batch_id,),
            )
            result["observations_deleted"] = cursor.rowcount

            # Delete the batch itself
            conn.execute("DELETE FROM prompt_batches WHERE id = ?", (batch_id,))

        logger.info(
            f"Deleted prompt batch {batch_id}: "
            f"{result['activities_deleted']} activities, "
            f"{result['observations_deleted']} observations"
        )
        return result

    def delete_session(self, session_id: str) -> dict[str, int]:
        """Delete a session and all related data.

        Cascade deletes:
        - All prompt batches for this session
        - All activities for this session
        - All memory observations for this session

        Args:
            session_id: The session ID to delete.

        Returns:
            Dictionary with counts: batches_deleted, activities_deleted, observations_deleted
        """
        result = {"batches_deleted": 0, "activities_deleted": 0, "observations_deleted": 0}

        with self._transaction() as conn:
            # Delete activities for this session
            cursor = conn.execute(
                "DELETE FROM activities WHERE session_id = ?",
                (session_id,),
            )
            result["activities_deleted"] = cursor.rowcount

            # Delete observations for this session
            cursor = conn.execute(
                "DELETE FROM memory_observations WHERE session_id = ?",
                (session_id,),
            )
            result["observations_deleted"] = cursor.rowcount

            # Delete prompt batches for this session
            cursor = conn.execute(
                "DELETE FROM prompt_batches WHERE session_id = ?",
                (session_id,),
            )
            result["batches_deleted"] = cursor.rowcount

            # Delete the session itself
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        logger.info(
            f"Deleted session {session_id}: "
            f"{result['batches_deleted']} batches, "
            f"{result['activities_deleted']} activities, "
            f"{result['observations_deleted']} observations"
        )
        return result

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
