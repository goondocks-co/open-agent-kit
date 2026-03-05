"""Agent routes for the swarm daemon.

Thin wrappers that delegate to shared agent route handlers in
``open_agent_kit.features.agent_runtime.routes.agents``.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from open_agent_kit.features.agent_runtime.models import (
    AgentListResponse,
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunStatus,
    TaskRunRequest,
)
from open_agent_kit.features.agent_runtime.routes.agents import (
    build_agent_list_response,
    get_run_detail,
    reload_registry,
    start_task_run,
)
from open_agent_kit.features.agent_runtime.routes.agents import (
    list_runs as shared_list_runs,
)
from open_agent_kit.features.agent_runtime.routes.common import (
    get_agent_components,
)
from open_agent_kit.features.swarm.constants import (
    SWARM_AGENTS_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=[SWARM_AGENTS_ROUTE_TAG])


# =============================================================================
# List Routes
# =============================================================================


@router.get("", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """List all available templates and tasks."""
    registry, _executor, _state = get_agent_components(get_swarm_state())
    return build_agent_list_response(registry)


# =============================================================================
# Reload Route
# =============================================================================


@router.post("/reload")
async def reload_agents() -> dict:
    """Reload agent definitions from disk."""
    registry, _executor, _state = get_agent_components(get_swarm_state())
    return reload_registry(registry)


# =============================================================================
# Task Run Route
# =============================================================================


@router.post("/tasks/{task_name}/run", response_model=AgentRunResponse)
async def run_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    request: TaskRunRequest | None = None,
) -> AgentRunResponse:
    """Run a task using its configured default_task."""
    registry, executor, _state = get_agent_components(get_swarm_state())
    return start_task_run(
        registry,
        executor,
        task_name,
        request.additional_prompt if request else None,
        background_tasks,
    )


# =============================================================================
# Run History Routes
# =============================================================================


@router.get("/runs", response_model=AgentRunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> AgentRunListResponse:
    """List agent runs with optional filtering."""
    _registry, executor, _state = get_agent_components(get_swarm_state())

    status_filter = None
    if status:
        try:
            status_filter = AgentRunStatus(status)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid: {[s.value for s in AgentRunStatus]}",
            ) from e

    return shared_list_runs(
        executor,
        limit=limit,
        offset=offset,
        agent_name=agent_name,
        status_filter=status_filter,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_run(run_id: str) -> AgentRunDetailResponse:
    """Get detailed information about a specific run."""
    _registry, executor, _state = get_agent_components(get_swarm_state())
    return get_run_detail(executor, run_id)
