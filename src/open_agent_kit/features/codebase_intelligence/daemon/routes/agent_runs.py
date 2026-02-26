"""Agent run lifecycle routes for the CI daemon.

These routes provide the HTTP interface for monitoring and managing agent runs:
- List runs with filtering, sorting, and pagination
- Get run details
- Cancel running agents
- Delete individual or bulk runs

IMPORTANT: Route order matters in FastAPI. This router uses prefix /api/agents
so specific paths (/runs/) must be defined BEFORE wildcard paths (/{agent_name}).
The main agents.py module includes this router to maintain correct ordering.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunStatus,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._agents_common import (
    get_agent_components,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agent-runs"])


@router.get("/runs", response_model=AgentRunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    status: str | None = Query(default=None, description="Filter by status"),
    created_after: datetime | None = Query(
        default=None, description="Filter runs created after this time"
    ),
    created_before: datetime | None = Query(
        default=None, description="Filter runs created before this time"
    ),
    sort_by: str = Query(
        default="created_at", description="Sort field: created_at, duration, cost"
    ),
    sort_order: str = Query(default="desc", description="Sort order: asc, desc"),
) -> AgentRunListResponse:
    """List agent runs with optional filtering and sorting.

    Args:
        limit: Maximum runs to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        status: Filter by run status.
        created_after: Filter runs created after this time.
        created_before: Filter runs created before this time.
        sort_by: Sort field (created_at, duration, cost).
        sort_order: Sort order (asc, desc).

    Returns:
        List of runs with pagination info.
    """
    _registry, executor, _state = get_agent_components()

    # Validate sort_by
    valid_sort_fields = {"created_at", "duration", "cost"}
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by: {sort_by}. Valid values: {list(valid_sort_fields)}",
        )

    # Validate sort_order
    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_order: {sort_order}. Valid values: ['asc', 'desc']",
        )

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = AgentRunStatus(status)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in AgentRunStatus]}",
            ) from e

    runs, total = executor.list_runs(
        limit=limit,
        offset=offset,
        agent_name=agent_name,
        status=status_filter,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return AgentRunListResponse(
        runs=runs,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_run(run_id: str) -> AgentRunDetailResponse:
    """Get detailed information about a specific run.

    Args:
        run_id: Run identifier.

    Returns:
        Full run details including results.
    """
    _registry, executor, _state = get_agent_components()

    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return AgentRunDetailResponse(run=run)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict:
    """Cancel a running agent.

    Args:
        run_id: Run identifier to cancel.

    Returns:
        Cancellation result.
    """
    _registry, executor, _state = get_agent_components()

    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    if run.is_terminal():
        raise HTTPException(
            status_code=400,
            detail=f"Run is already in terminal state: {run.status.value}",
        )

    success = await executor.cancel(run_id)

    if success:
        return {"success": True, "message": f"Run {run_id} cancelled"}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel run")


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict:
    """Delete an agent run record.

    Only terminal runs (completed, failed, cancelled, timeout) can be deleted.
    Running or pending runs must be cancelled first.

    Args:
        run_id: Run identifier to delete.

    Returns:
        Deletion result.
    """
    _registry, executor, state = get_agent_components()

    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    if not run.is_terminal():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete run in '{run.status.value}' state. Cancel it first.",
        )

    # Use existing store method to delete
    if state.activity_store:
        deleted = state.activity_store.delete_agent_run(run_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete run from database")

    return {"success": True, "message": f"Run {run_id} deleted", "deleted": run_id}


@router.delete("/runs")
async def bulk_delete_runs(
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    status: str | None = Query(default=None, description="Filter by status (must be terminal)"),
    before: datetime | None = Query(
        default=None, description="Delete runs created before this date"
    ),
    keep_recent: int = Query(
        default=10, ge=0, le=100, description="Keep N most recent runs per agent"
    ),
) -> dict:
    """Bulk delete agent runs with retention policy.

    Only deletes runs in terminal states (completed, failed, cancelled, timeout).
    Always keeps the most recent N runs per agent to maintain history.

    Args:
        agent_name: Filter by agent name (optional).
        status: Filter by status (optional, must be terminal).
        before: Delete runs created before this date (optional).
        keep_recent: Keep this many most recent runs per agent (default 10).

    Returns:
        Number of runs deleted.
    """
    _registry, _executor, state = get_agent_components()

    # Validate status if provided
    terminal_statuses = {"completed", "failed", "cancelled", "timeout"}
    if status and status not in terminal_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete runs with non-terminal status: {status}. "
            f"Valid values: {list(terminal_statuses)}",
        )

    # Convert before datetime to epoch
    before_epoch = int(before.timestamp()) if before else None

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    deleted_count = state.activity_store.bulk_delete_agent_runs(
        agent_name=agent_name,
        status=status,
        before_epoch=before_epoch,
        keep_recent=keep_recent,
    )

    return {
        "success": True,
        "message": f"Deleted {deleted_count} runs",
        "deleted_count": deleted_count,
        "filters": {
            "agent_name": agent_name,
            "status": status,
            "before": before.isoformat() if before else None,
            "keep_recent": keep_recent,
        },
    }
