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
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 3

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

    # Maximum prompt length to store (10K chars should capture most prompts)
    MAX_PROMPT_LENGTH = 10000

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
            "created_at_epoch": int(self.started_at.timestamp()),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PromptBatch":
        """Create from database row."""
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
            "created_at_epoch": int(self.started_at.timestamp()),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Session":
        """Create from database row."""
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
        """Create database schema if needed."""
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
                # Apply schema
                conn.executescript(SCHEMA_SQL)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
                logger.info(f"Activity store schema initialized (v{SCHEMA_VERSION})")

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
    ) -> PromptBatch:
        """Create a new prompt batch (when user submits a prompt).

        Args:
            session_id: Parent session ID.
            user_prompt: Full user prompt text (up to 10K chars).

        Returns:
            Created PromptBatch with assigned ID.
        """
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
        )

        with self._transaction() as conn:
            row_data = batch.to_row()
            cursor = conn.execute(
                """
                INSERT INTO prompt_batches (session_id, prompt_number, user_prompt,
                                           started_at, status, activity_count, processed,
                                           classification, created_at_epoch)
                VALUES (:session_id, :prompt_number, :user_prompt,
                        :started_at, :status, :activity_count, :processed,
                        :classification, :created_at_epoch)
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
            f"Created prompt batch {batch.id} (prompt #{prompt_number}) for session {session_id}"
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
            return cursor.lastrowid or 0

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

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Get statistics for a session.

        Args:
            session_id: Session to query.

        Returns:
            Dictionary with session statistics.
        """
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

        return {
            "tool_counts": tool_counts,
            "activity_count": activity_count,
            "prompt_batch_count": prompt_batch_count,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
        }

    def get_recent_sessions(self, limit: int = 10) -> list[Session]:
        """Get recent sessions.

        Args:
            limit: Maximum sessions to return.

        Returns:
            List of recent Session objects.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY created_at_epoch DESC
            LIMIT ?
            """,
            (limit,),
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

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
