"""Remote observation applier -- dedup-safe INSERT for relay-received obs.

Uses direct SQL (not store_observation) to avoid triggering outbox hooks
on imported data, which would cause infinite sync loops.  Mirrors the
pattern from team/pull/applier.py::_apply_observation_upsert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from open_agent_kit.features.team.constants.session import (
    OBSERVATION_STATUS_ACTIVE,
    ORIGIN_TYPE_AUTO_EXTRACTED,
    SESSION_STATUS_ACTIVE,
)
from open_agent_kit.features.team.constants.team import (
    TEAM_REMOTE_OBS_DEFAULT_IMPORTANCE,
    TEAM_REMOTE_OBS_EPOCH,
    TEAM_REMOTE_OBS_UNKNOWN_AGENT,
)

if TYPE_CHECKING:
    import sqlite3

    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    """Result of applying a batch of remote observations."""

    applied: int = 0
    skipped: int = 0
    errored: int = 0


@runtime_checkable
class ObsApplierProtocol(Protocol):
    """Protocol for observation appliers used by the relay client."""

    def apply_batch(
        self,
        observations: list[dict[str, Any]],
        from_machine_id: str,
    ) -> ApplyResult: ...


class RemoteObsApplier:
    """Apply remote observations received via the cloud relay.

    Inserts observations with dedup by content_hash.
    No batch/activity/session replay -- observations only.
    """

    def __init__(self, store: ActivityStore) -> None:
        self._store = store

    def apply_batch(
        self,
        observations: list[dict[str, Any]],
        from_machine_id: str,
    ) -> ApplyResult:
        """Insert remote observations with dedup by content_hash.

        Wraps the entire batch in a single transaction for performance.
        Uses INSERT OR IGNORE for SQL-level dedup.

        Args:
            observations: List of observation payloads from the relay.
            from_machine_id: Machine ID of the sender.

        Returns:
            ApplyResult with counts of applied, skipped, and errored observations.
        """
        from open_agent_kit.features.team.activity.store.observations import (
            has_observation_with_hash,
        )

        result = ApplyResult()

        # Pre-filter: skip observations without content_hash or already present
        to_insert: list[dict[str, Any]] = []
        for obs in observations:
            content_hash = obs.get("content_hash")
            if not content_hash:
                logger.debug("Skipping obs without content_hash from %s", from_machine_id)
                result.skipped += 1
                continue
            if has_observation_with_hash(self._store, content_hash):
                result.skipped += 1
                continue
            to_insert.append(obs)

        if not to_insert:
            return result

        # Batch insert in a single transaction
        with self._store._transaction() as conn:
            for obs in to_insert:
                try:
                    self._ensure_session_exists(conn, obs)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO memory_observations
                        (id, session_id, prompt_batch_id, observation, memory_type,
                         context, tags, importance, file_path, created_at, created_at_epoch,
                         embedded, source_machine_id, content_hash, status,
                         resolved_by_session_id, resolved_at, superseded_by,
                         session_origin_type, origin_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            obs.get("id"),
                            obs.get("session_id"),
                            None,  # prompt_batch_id is a local integer FK
                            obs.get("observation"),
                            obs.get("memory_type"),
                            obs.get("context"),
                            obs.get("tags"),
                            obs.get("importance", TEAM_REMOTE_OBS_DEFAULT_IMPORTANCE),
                            obs.get("file_path"),
                            obs.get("created_at"),
                            obs.get("created_at_epoch"),
                            False,  # embedded=False -- needs ChromaDB re-embedding
                            obs.get("source_machine_id") or from_machine_id,
                            obs["content_hash"],
                            obs.get("status", OBSERVATION_STATUS_ACTIVE),
                            obs.get("resolved_by_session_id"),
                            obs.get("resolved_at"),
                            obs.get("superseded_by"),
                            obs.get("session_origin_type"),
                            obs.get("origin_type", ORIGIN_TYPE_AUTO_EXTRACTED),
                        ),
                    )
                    result.applied += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to apply obs from %s: %s",
                        from_machine_id,
                        exc,
                    )
                    result.errored += 1

        return result

    def _ensure_session_exists(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        """Create a stub session row if the referenced session doesn't exist.

        Observations can arrive before their parent session event, so we
        insert a minimal placeholder that will be overwritten when the real
        session data arrives (INSERT OR IGNORE).
        """
        session_id = payload.get("session_id")
        if not session_id:
            return
        started_at = payload.get("started_at") or payload.get("created_at") or TEAM_REMOTE_OBS_EPOCH
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions
            (id, agent, project_root, started_at, status, prompt_count, tool_count,
             processed, created_at_epoch, source_machine_id, summary_embedded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.get("agent", TEAM_REMOTE_OBS_UNKNOWN_AGENT),
                payload.get("project_root", ""),
                started_at,
                SESSION_STATUS_ACTIVE,
                0,
                0,
                False,
                payload.get("created_at_epoch", 0),
                payload.get("source_machine_id"),
                0,
            ),
        )
