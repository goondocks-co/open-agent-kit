"""Governance audit writer: persists evaluation decisions to SQLite.

Records every governance evaluation (allow, deny, warn, observe) to the
governance_audit_events table for compliance reporting and debugging.
Includes retention pruning to prevent unbounded table growth.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.governance.engine import (
        GovernanceDecision,
    )

logger = logging.getLogger(__name__)


def prune_old_events(activity_store: ActivityStore, retention_days: int) -> int:
    """Delete governance audit events older than retention_days.

    Args:
        activity_store: The activity store with a SQLite connection.
        retention_days: Number of days to retain. Events older than this are deleted.

    Returns:
        Number of rows deleted.
    """
    cutoff_epoch = int(time.time()) - (retention_days * 86400)
    try:
        conn = activity_store._get_connection()
        cursor = conn.execute(
            "DELETE FROM governance_audit_events WHERE created_at_epoch < ?",
            (cutoff_epoch,),
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            logger.info(
                "Governance audit retention: pruned %d events older than %d days",
                deleted,
                retention_days,
            )
        return deleted
    except sqlite3.Error as e:
        logger.warning("Failed to prune governance audit events: %s", e)
        return 0


class GovernanceAuditWriter:
    """Writes governance evaluation results to the audit events table."""

    def __init__(self, activity_store: ActivityStore) -> None:
        self._store = activity_store

    def record(
        self,
        session_id: str,
        agent: str,
        tool_name: str,
        tool_use_id: str | None,
        decision: GovernanceDecision,
        enforcement_mode: str,
        evaluation_ms: int | None = None,
        tool_input_summary: str | None = None,
    ) -> None:
        """Record a governance evaluation to the audit events table.

        Args:
            session_id: Current session ID.
            agent: Agent name (e.g., "claude", "cursor").
            tool_name: Name of the evaluated tool.
            tool_use_id: Unique tool use identifier (if available).
            decision: The governance evaluation result.
            enforcement_mode: Current enforcement mode ("observe" or "enforce").
            evaluation_ms: Time taken to evaluate rules (milliseconds).
            tool_input_summary: Truncated summary of tool input for audit.
        """
        now = datetime.now(UTC)
        created_at = now.isoformat()
        created_at_epoch = int(time.time())

        # Get machine_id from activity store if available
        source_machine_id = getattr(self._store, "machine_id", None)

        try:
            conn = self._store._get_connection()
            conn.execute(
                """
                INSERT INTO governance_audit_events (
                    session_id, agent, tool_name, tool_use_id,
                    tool_category, rule_id, rule_description,
                    action, reason, matched_pattern,
                    tool_input_summary, enforcement_mode,
                    created_at, created_at_epoch,
                    evaluation_ms, source_machine_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    agent,
                    tool_name,
                    tool_use_id,
                    decision.tool_category,
                    decision.rule_id or None,
                    decision.rule_description or None,
                    decision.action,
                    decision.reason or None,
                    decision.matched_pattern or None,
                    tool_input_summary,
                    enforcement_mode,
                    created_at,
                    created_at_epoch,
                    evaluation_ms,
                    source_machine_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warning("Failed to record governance audit event: %s", e)
