"""Governance API routes for config management and audit queries."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Query, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CONFIG_KEY_GOVERNANCE,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])


@router.get("/config")
@handle_route_errors("governance config get")
async def get_governance_config() -> dict[str, Any]:
    """Get current governance configuration."""
    state = get_state()
    config = state.ci_config
    if config is None:
        return {"enabled": False, "enforcement_mode": "observe", "log_allowed": False, "rules": []}
    return config.governance.to_dict()


@router.put("/config")
@handle_route_errors("governance config save")
async def save_governance_config(request: Request) -> dict[str, Any]:
    """Save updated governance configuration."""
    state = get_state()
    if state.project_root is None:
        return {"error": "Project root not set"}

    body = await request.json()

    from open_agent_kit.features.codebase_intelligence.config import (
        CIConfig,
        GovernanceConfig,
        load_ci_config,
        save_ci_config,
    )

    # Validate the new config
    gov_config = GovernanceConfig.from_dict(body)

    # Load current full config, update governance section, save
    full_config = load_ci_config(state.project_root)
    full_dict = full_config.to_dict()
    full_dict[CI_CONFIG_KEY_GOVERNANCE] = gov_config.to_dict()

    updated = CIConfig.from_dict(full_dict)
    save_ci_config(state.project_root, updated)

    # Invalidate cached config so DaemonState picks up changes
    state.ci_config = None

    return {"status": "saved", "config": gov_config.to_dict()}


@router.get("/audit")
@handle_route_errors("governance audit query")
async def get_audit_events(
    since: int | None = Query(None, description="Epoch timestamp filter"),
    action: str | None = Query(None, description="Filter by action"),
    agent: str | None = Query(None, description="Filter by agent"),
    tool: str | None = Query(None, description="Filter by tool name"),
    rule_id: str | None = Query(None, description="Filter by rule ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query governance audit events."""
    state = get_state()
    if not state.activity_store:
        return {"events": [], "total": 0}

    conn = state.activity_store._get_connection()

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

    return {"events": events, "total": total, "limit": limit, "offset": offset}


@router.get("/audit/summary")
@handle_route_errors("governance audit summary")
async def get_audit_summary(
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Get aggregate audit stats for dashboard."""
    state = get_state()
    if not state.activity_store:
        return {"total": 0, "by_action": {}, "by_tool": {}, "by_rule": {}}

    since_epoch = int(time.time()) - (days * 86400)
    conn = state.activity_store._get_connection()

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
        "days": days,
    }


@router.post("/audit/prune")
@handle_route_errors("governance audit prune")
async def prune_audit_events() -> dict[str, Any]:
    """Manually trigger audit event retention pruning."""
    state = get_state()
    if not state.activity_store:
        return {"deleted": 0, "error": "Activity store not available"}

    config = state.ci_config
    retention_days = 30  # fallback default
    if config and config.governance:
        retention_days = config.governance.retention_days

    from open_agent_kit.features.codebase_intelligence.governance.audit import (
        prune_old_events,
    )

    deleted = prune_old_events(state.activity_store, retention_days)
    return {"deleted": deleted, "retention_days": retention_days}


@router.post("/test")
@handle_route_errors("governance test")
async def test_governance_rule(request: Request) -> dict[str, Any]:
    """Test a hypothetical tool call against policy."""
    state = get_state()
    engine = state.governance_engine
    if engine is None:
        return {"error": "Governance is not enabled"}

    body = await request.json()
    tool_name = body.get("tool_name", "")
    tool_input = body.get("tool_input", {})

    decision = engine.evaluate(tool_name, tool_input)
    return {
        "action": decision.action,
        "rule_id": decision.rule_id,
        "reason": decision.reason,
        "matched_pattern": decision.matched_pattern,
        "tool_category": decision.tool_category,
    }
