"""Data models for activity store.

Dataclasses representing sessions, prompt batches, activities, and observations.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    source_machine_id: str | None = None  # Machine that originated this record (v13)

    def _compute_content_hash(self) -> str:
        """Compute content hash for deduplication."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            compute_activity_hash,
        )

        return compute_activity_hash(
            self.session_id, int(self.timestamp.timestamp()), self.tool_name
        )

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
            "source_machine_id": self.source_machine_id,
            "content_hash": self._compute_content_hash(),
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
            source_machine_id=(
                row["source_machine_id"] if "source_machine_id" in row.keys() else None
            ),
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
    - derived_plan: Plan synthesized from TaskCreate activities
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
    source_type: str = "user"  # user, agent_notification, plan, system, derived_plan
    plan_file_path: str | None = None  # Path to plan file (for source_type='plan')
    plan_content: str | None = None  # Full plan content (stored for self-contained CI)
    plan_embedded: bool = False  # Has plan been indexed in ChromaDB?
    source_plan_batch_id: int | None = None  # Link to plan batch being implemented (v12)
    source_machine_id: str | None = None  # Machine that originated this record (v13)

    # Maximum prompt length to store (10K chars should capture most prompts)
    MAX_PROMPT_LENGTH = 10000
    # Maximum plan content length (100K chars for large plans)
    MAX_PLAN_CONTENT_LENGTH = 100000

    def _compute_content_hash(self) -> str:
        """Compute content hash for deduplication."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            compute_prompt_batch_hash,
        )

        return compute_prompt_batch_hash(self.session_id, self.prompt_number)

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
            "source_plan_batch_id": self.source_plan_batch_id,
            "source_machine_id": self.source_machine_id,
            "content_hash": self._compute_content_hash(),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PromptBatch":
        """Create from database row."""
        # Handle migration: older rows may not have source_type, plan_file_path, plan_content,
        # plan_embedded, or source_plan_batch_id
        source_type = "user"
        plan_file_path = None
        plan_content = None
        plan_embedded = False
        source_plan_batch_id = None
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
        try:
            source_plan_batch_id = row["source_plan_batch_id"]
        except (KeyError, IndexError):
            pass

        source_machine_id = None
        try:
            source_machine_id = row["source_machine_id"]
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
            source_plan_batch_id=source_plan_batch_id,
            source_machine_id=source_machine_id,
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
    parent_session_id: str | None = None  # Session this was derived from (v12)
    parent_session_reason: str | None = None  # Why linked: 'clear', 'compact', 'inferred' (v12)
    source_machine_id: str | None = None  # Machine that originated this record (v13)

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
            "parent_session_id": self.parent_session_id,
            "parent_session_reason": self.parent_session_reason,
            "source_machine_id": self.source_machine_id,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Session":
        """Create from database row."""
        # Handle columns which may not exist in older databases
        row_keys = row.keys()
        title = row["title"] if "title" in row_keys else None
        parent_session_id = row["parent_session_id"] if "parent_session_id" in row_keys else None
        parent_session_reason = (
            row["parent_session_reason"] if "parent_session_reason" in row_keys else None
        )
        source_machine_id = row["source_machine_id"] if "source_machine_id" in row_keys else None
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
            parent_session_id=parent_session_id,
            parent_session_reason=parent_session_reason,
            source_machine_id=source_machine_id,
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
    source_machine_id: str | None = None  # Machine that originated this record (v13)

    def _compute_content_hash(self) -> str:
        """Compute content hash for deduplication."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            compute_observation_hash,
        )

        return compute_observation_hash(self.observation, self.memory_type, self.context)

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
            "source_machine_id": self.source_machine_id,
            "content_hash": self._compute_content_hash(),
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
            source_machine_id=(
                row["source_machine_id"] if "source_machine_id" in row.keys() else None
            ),
        )
