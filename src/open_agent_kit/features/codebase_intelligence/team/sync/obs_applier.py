"""Remote observation applier -- dedup-safe INSERT for relay-received obs.

Uses direct SQL (not store_observation) to avoid triggering outbox hooks
on imported data, which would cause infinite sync loops.  Mirrors the
pattern from team/pull/applier.py::_apply_observation_upsert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)

_EPOCH = "1970-01-01T00:00:00+00:00"


@dataclass
class ApplyResult:
    """Result of applying a batch of remote observations."""

    applied: int = 0
    skipped: int = 0


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

        Args:
            observations: List of observation payloads from the relay.
            from_machine_id: Machine ID of the sender.

        Returns:
            ApplyResult with counts of applied and skipped observations.
        """
        result = ApplyResult()
        for obs in observations:
            try:
                applied = self._apply_one(obs, from_machine_id)
                if applied:
                    result.applied += 1
                else:
                    result.skipped += 1
            except Exception as exc:
                logger.warning(
                    "Failed to apply obs from %s: %s",
                    from_machine_id,
                    exc,
                )
                result.skipped += 1
        return result

    def _apply_one(self, obs: dict[str, Any], from_machine_id: str) -> bool:
        """Insert a single observation; return True if inserted, False if dup."""
        content_hash = obs.get("content_hash")
        if not content_hash:
            logger.debug("Skipping obs without content_hash from %s", from_machine_id)
            return False

        # Dedup check -- same guard used by store_observation and applier.py
        from open_agent_kit.features.codebase_intelligence.activity.store.observations import (
            has_observation_with_hash,
        )

        if has_observation_with_hash(self._store, content_hash):
            return False

        with self._store._transaction() as conn:
            self._ensure_session_exists(conn, obs)
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_observations
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
                    obs.get("importance", 5),
                    obs.get("file_path"),
                    obs.get("created_at"),
                    obs.get("created_at_epoch"),
                    False,  # embedded=False -- needs ChromaDB re-embedding
                    obs.get("source_machine_id") or from_machine_id,
                    content_hash,
                    obs.get("status", "active"),
                    obs.get("resolved_by_session_id"),
                    obs.get("resolved_at"),
                    obs.get("superseded_by"),
                    obs.get("session_origin_type"),
                    obs.get("origin_type", "auto_extracted"),
                ),
            )
        return True

    def _ensure_session_exists(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
        """Create a stub session row if the referenced session doesn't exist.

        Observations can arrive before their parent session event, so we
        insert a minimal placeholder that will be overwritten when the real
        session data arrives (INSERT OR IGNORE).
        """
        session_id = payload.get("session_id")
        if not session_id:
            return
        started_at = payload.get("started_at") or payload.get("created_at") or _EPOCH
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions
            (id, agent, project_root, started_at, status, prompt_count, tool_count,
             processed, created_at_epoch, source_machine_id, summary_embedded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.get("agent", "unknown"),
                payload.get("project_root", ""),
                started_at,
                "active",
                0,
                0,
                False,
                payload.get("created_at_epoch", 0),
                payload.get("source_machine_id"),
                0,
            ),
        )
