"""Agent routes for the swarm daemon.

Provides the HTTP interface for the swarm agent catalog:
- List available templates and tasks
- Reload agent definitions
- Run tasks
- List and inspect runs
"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from open_agent_kit.features.agent_runtime.models import (
    AgentListResponse,
    AgentListItem,
    AgentRunListResponse,
    AgentRunDetailResponse,
    AgentRunResponse,
    AgentRunStatus,
    AgentTaskListItem,
    AgentTemplateListItem,
)
from open_agent_kit.features.swarm.constants import (
    SWARM_AGENTS_ROUTE_TAG,
    SWARM_DAEMON_API_PATH_AGENTS,
)
from open_agent_kit.features.swarm.daemon.state import (
    SwarmDaemonState,
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=[SWARM_AGENTS_ROUTE_TAG])


def _get_agent_components():
    """Get agent registry and executor from swarm state, or raise HTTP 503."""
    state = get_swarm_state()

    if not state.agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized.",
        )

    if not state.agent_executor:
        raise HTTPException(
            status_code=503,
            detail="Agent executor not initialized.",
        )

    return state.agent_registry, state.agent_executor, state


# =============================================================================
# List Routes
# =============================================================================


@router.get("", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """List all available templates and tasks."""
    registry, _executor, _state = _get_agent_components()

    templates = [t for t in registry.list_templates() if not t.internal]
    tasks = registry.list_tasks()

    template_items = [
        AgentTemplateListItem(
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            max_turns=t.execution.max_turns,
            timeout_seconds=t.execution.timeout_seconds,
        )
        for t in templates
    ]

    task_items = []
    for task in tasks:
        template = registry.get_template(task.agent_type)
        if template:
            has_override = task.execution is not None
            if has_override and task.execution:
                effective_max_turns = task.execution.max_turns or template.execution.max_turns
                effective_timeout = (
                    task.execution.timeout_seconds or template.execution.timeout_seconds
                )
            else:
                effective_max_turns = template.execution.max_turns
                effective_timeout = template.execution.timeout_seconds

            task_items.append(
                AgentTaskListItem(
                    name=task.name,
                    display_name=task.display_name,
                    agent_type=task.agent_type,
                    description=task.description,
                    default_task=task.default_task,
                    max_turns=effective_max_turns,
                    timeout_seconds=effective_timeout,
                    has_execution_override=has_override,
                    is_builtin=task.is_builtin,
                )
            )

    legacy_items = [
        AgentListItem(
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            max_turns=t.execution.max_turns,
            timeout_seconds=t.execution.timeout_seconds,
            project_config=t.project_config,
        )
        for t in templates
    ]

    return AgentListResponse(
        templates=template_items,
        tasks=task_items,
        agents=legacy_items,
        total=len(templates),
    )


# =============================================================================
# Reload Route
# =============================================================================


@router.post("/reload")
async def reload_agents() -> dict:
    """Reload agent definitions from disk."""
    registry, _executor, _state = _get_agent_components()

    count = registry.reload()

    return {
        "success": True,
        "message": f"Reloaded {count} agents",
        "agents": registry.list_names(),
    }


# =============================================================================
# Task Run Route
# =============================================================================


class TaskRunRequest(BaseModel):
    """Request body for running a task with optional runtime direction."""

    additional_prompt: str | None = Field(
        default=None,
        max_length=10000,
        description="Optional runtime direction for the task",
    )


@router.post("/tasks/{task_name}/run", response_model=AgentRunResponse)
async def run_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    request: TaskRunRequest | None = None,
) -> AgentRunResponse:
    """Run a task using its configured default_task."""
    registry, executor, _state = _get_agent_components()

    task = registry.get_task(task_name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    template = registry.get_template(task.agent_type)
    if not template:
        raise HTTPException(
            status_code=500,
            detail=f"Template '{task.agent_type}' not found for task '{task_name}'",
        )

    task_prompt = task.default_task
    if request and request.additional_prompt:
        task_prompt = f"## Assignment\n{request.additional_prompt}\n\n---\n\n{task.default_task}"

    run = executor.create_run(template, task_prompt, task)

    logger.info("Starting task run: %s for %s", run.id, task_name)

    async def _execute_task() -> None:
        try:
            await executor.execute(template, task_prompt, run, task)
        except (OSError, RuntimeError, ValueError) as e:
            logger.error("Task run %s failed: %s", run.id, e)
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            executor._persist_run_completion(run)

    background_tasks.add_task(_execute_task)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Task '{task_name}' started",
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
    _registry, executor, _state = _get_agent_components()

    status_filter = None
    if status:
        try:
            status_filter = AgentRunStatus(status)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid: {[s.value for s in AgentRunStatus]}",
            ) from e

    runs, total = executor.list_runs(
        limit=limit,
        offset=offset,
        agent_name=agent_name,
        status=status_filter,
    )

    return AgentRunListResponse(
        runs=runs,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_run(run_id: str) -> AgentRunDetailResponse:
    """Get detailed information about a specific run."""
    _registry, executor, _state = _get_agent_components()

    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return AgentRunDetailResponse(run=run)
