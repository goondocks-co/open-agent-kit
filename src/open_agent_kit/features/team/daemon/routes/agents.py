"""Agent catalog routes for the CI daemon.

These routes provide the HTTP interface for the agent catalog:
- List available templates and tasks
- Get agent details
- Reload agent definitions
- Create tasks from templates
- Copy tasks
- Run tasks and agents (legacy)

IMPORTANT: Route order matters in FastAPI. Specific paths (like /runs/, /reload)
must be defined BEFORE wildcard paths (like /{agent_name}) to avoid the wildcard
catching everything. The agent_runs and agent_settings routers share the same
prefix and are registered BEFORE this router in server.py, so their specific
paths take priority over the wildcards defined here.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from open_agent_kit.features.agent_runtime.models import (
    AgentDetailResponse,
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
    CreateTaskRequest,
    TaskRunRequest,
)
from open_agent_kit.features.agent_runtime.routes.agents import (
    build_agent_list_response,
    reload_registry,
    start_task_run,
)
from open_agent_kit.features.agent_runtime.routes.common import (
    get_agent_components,
)
from open_agent_kit.features.team.constants import (
    AGENT_PROJECT_CONFIG_DIR,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# =============================================================================
# List Routes (no path parameters)
# =============================================================================


@router.get("", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """List all available templates and tasks."""
    registry, _executor, _state = get_agent_components(get_state())
    return build_agent_list_response(registry, tasks_dir=AGENT_PROJECT_CONFIG_DIR)


# =============================================================================
# Reload Route (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/reload")
async def reload_agents() -> dict:
    """Reload agent definitions from disk."""
    registry, _executor, _state = get_agent_components(get_state())
    return reload_registry(registry)


# =============================================================================
# Task Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/tasks/{task_name}/run", response_model=AgentRunResponse)
async def run_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    request: TaskRunRequest | None = None,
) -> AgentRunResponse:
    """Run a task using its configured default_task."""
    registry, executor, _state = get_agent_components(get_state())
    return start_task_run(
        registry,
        executor,
        task_name,
        request.additional_prompt if request else None,
        background_tasks,
    )


# =============================================================================
# Template Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/templates/{template_name}/create-task")
async def create_task(
    template_name: str,
    request: CreateTaskRequest,
) -> dict:
    """Create a new task from a template.

    Generates a task YAML file in the project's agent tasks directory
    with scaffolding for common configuration options.

    Args:
        template_name: Name of the template to use.
        request: Task creation request.

    Returns:
        Created task details.
    """
    registry, _executor, _state = get_agent_components(get_state())

    try:
        task = registry.create_task(
            name=request.name,
            template_name=template_name,
            display_name=request.display_name,
            description=request.description,
            default_task=request.default_task,
        )

        return {
            "success": True,
            "message": f"Created task '{task.name}'",
            "task": {
                "name": task.name,
                "display_name": task.display_name,
                "agent_type": task.agent_type,
                "description": task.description,
                "task_path": task.task_path,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write task file: {e}") from e


@router.post("/tasks/{task_name}/copy")
async def copy_task(
    task_name: str,
    new_name: str | None = Query(default=None, description="New name for the copy"),
) -> dict:
    """Copy a task to the user's tasks directory.

    Useful for customizing built-in tasks. The copy becomes a user-owned
    task that can be freely modified.

    Args:
        task_name: Name of the task to copy.
        new_name: Optional new name for the copy.

    Returns:
        Copied task details.
    """
    registry, _executor, _state = get_agent_components(get_state())

    try:
        task = registry.copy_task(task_name, new_name)

        return {
            "success": True,
            "message": f"Copied task '{task_name}' to '{task.name}'",
            "task": {
                "name": task.name,
                "display_name": task.display_name,
                "agent_type": task.agent_type,
                "description": task.description,
                "task_path": task.task_path,
                "is_builtin": task.is_builtin,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy task: {e}") from e


# =============================================================================
# Wildcard Routes (MUST come LAST to avoid catching specific paths)
# =============================================================================


@router.get("/{agent_name}", response_model=AgentDetailResponse)
async def get_agent(agent_name: str) -> AgentDetailResponse:
    """Get detailed information about a specific agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        Agent definition and recent run history.
    """
    registry, executor, _state = get_agent_components(get_state())

    agent = registry.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Get recent runs for this agent
    runs, _total = executor.list_runs(limit=10, agent_name=agent_name)

    return AgentDetailResponse(agent=agent, recent_runs=runs)


@router.post("/{agent_name}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_name: str,
    request: AgentRunRequest,
    background_tasks: BackgroundTasks,
) -> AgentRunResponse:
    """Trigger an agent run (legacy - prefer /tasks/{name}/run).

    Starts the agent in the background and returns immediately with a run ID
    that can be used to monitor progress.

    Args:
        agent_name: Name of the agent to run.
        request: Run request with task description.

    Returns:
        Run ID and initial status.
    """
    registry, executor, _state = get_agent_components(get_state())

    agent = registry.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Create run record
    run = executor.create_run(agent, request.task)

    logger.info(f"Starting agent run: {run.id} for {agent_name}")

    # Execute in background
    async def _execute_agent() -> None:
        try:
            await executor.execute(agent, request.task, run)
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Agent run {run.id} failed: {e}")
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            # Persist failure state to database
            executor.persist_completion(run)

    # Schedule background execution
    background_tasks.add_task(_execute_agent)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Agent '{agent_name}' started with task: {request.task[:100]}...",
    )
