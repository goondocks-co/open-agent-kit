"""Governance audit operations for activity store.

Functions for querying governance audit events and summaries.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def query_governance_audit_events(
    store: ActivityStore,
    *,
    since: int | None = None,
    action: str | None = None,
    agent: str | None = None,
    tool: str | None = None,
    rule_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
    """Query governance audit events with filtering and pagination.

    Args:
        store: The ActivityStore instance.
        since: Epoch timestamp lower bound filter.
        action: Filter by governance action (allow, deny, warn, observe).
        agent: Filter by agent name.
        tool: Filter by tool name.
        rule_id: Filter by rule ID.
        limit: Maximum events to return.
        offset: Pagination offset.

    Returns:
        Tuple of (total_count, events_list) where each event is a dict.
    """
    conn = store._get_connection()

    # Build query with filters
    conditions: list[str] = []
    params: list[Any] = []

    if since is not None:
        conditions.append("g.created_at_epoch >= ?")
        params.append(since)
    if action:
        conditions.append("g.action = ?")
        params.append(action)
    if agent:
        conditions.append("g.agent = ?")
        params.append(agent)
    if tool:
        conditions.append("g.tool_name = ?")
        params.append(tool)
    if rule_id:
        conditions.append("g.rule_id = ?")
        params.append(rule_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM governance_audit_events g WHERE {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Get events with session title from sessions table
    query_sql = (
        f"SELECT g.*, s.title AS session_title "
        f"FROM governance_audit_events g "
        f"LEFT JOIN sessions s ON g.session_id = s.id "
        f"WHERE {where_clause} "
        f"ORDER BY g.created_at_epoch DESC LIMIT ? OFFSET ?"
    )
    cursor = conn.execute(query_sql, params + [limit, offset])
    columns = [desc[0] for desc in cursor.description or []]
    rows = cursor.fetchall()

    events = [dict(zip(columns, row, strict=False)) for row in rows]

    return total, events


def get_governance_audit_summary(
    store: ActivityStore,
    since_epoch: int,
) -> dict[str, Any]:
    """Get aggregate audit stats for dashboard.

    Args:
        store: The ActivityStore instance.
        since_epoch: Epoch timestamp lower bound for the summary window.

    Returns:
        Dict with keys: total, by_action, by_tool, by_rule.
    """
    conn = store._get_connection()

    # Total events
    total = conn.execute(
        "SELECT COUNT(*) FROM governance_audit_events WHERE created_at_epoch >= ?",
        (since_epoch,),
    ).fetchone()[0]

    # By action
    by_action: dict[str, int] = {}
    for row in conn.execute(
        "SELECT action, COUNT(*) FROM governance_audit_events "
        "WHERE created_at_epoch >= ? GROUP BY action",
        (since_epoch,),
    ).fetchall():
        by_action[row[0]] = row[1]

    # By tool (top 10)
    by_tool: dict[str, int] = {}
    for row in conn.execute(
        "SELECT tool_name, COUNT(*) FROM governance_audit_events "
        "WHERE created_at_epoch >= ? GROUP BY tool_name ORDER BY COUNT(*) DESC LIMIT 10",
        (since_epoch,),
    ).fetchall():
        by_tool[row[0]] = row[1]

    # By rule (top 10)
    by_rule: dict[str, int] = {}
    for row in conn.execute(
        "SELECT rule_id, COUNT(*) FROM governance_audit_events "
        "WHERE created_at_epoch >= ? AND rule_id IS NOT NULL "
        "GROUP BY rule_id ORDER BY COUNT(*) DESC LIMIT 10",
        (since_epoch,),
    ).fetchall():
        by_rule[row[0]] = row[1]

    return {
        "total": total,
        "by_action": by_action,
        "by_tool": by_tool,
        "by_rule": by_rule,
    }
