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
from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDetailResponse,
    AgentListItem,
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
    AgentTaskListItem,
    AgentTemplateListItem,
    CreateTaskRequest,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_PROJECT_CONFIG_DIR,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._agents_common import (
    get_agent_components,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# =============================================================================
# List Routes (no path parameters)
# =============================================================================


@router.get("", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """List all available templates and tasks.

    Templates define capabilities but cannot be run directly.
    Tasks are runnable - they have a configured default_task.
    """
    registry, _executor, _state = get_agent_components()

    templates = [t for t in registry.list_templates() if not t.internal]
    tasks = registry.list_tasks()

    # Build template list items
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

    # Build task list items (use effective execution settings - task override or template default)
    task_items = []
    for task in tasks:
        template = registry.get_template(task.agent_type)
        if template:
            # Compute effective execution config (task override takes precedence)
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

    # Legacy: also return agents list for backwards compatibility
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
        tasks_dir=AGENT_PROJECT_CONFIG_DIR,
        agents=legacy_items,
        total=len(templates),
    )


# =============================================================================
# Reload Route (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/reload")
async def reload_agents() -> dict:
    """Reload agent definitions from disk.

    Useful after adding or modifying agent YAML files.

    Returns:
        Number of agents loaded.
    """
    registry, _executor, _state = get_agent_components()

    count = registry.reload()

    return {
        "success": True,
        "message": f"Reloaded {count} agents",
        "agents": registry.list_names(),
    }


# =============================================================================
# Task Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


class TaskRunRequest(BaseModel):
    """Request body for running a task with optional runtime direction."""

    additional_prompt: str | None = Field(
        default=None,
        max_length=10000,
        description="Optional runtime direction for the task (what to work on)",
    )


@router.post("/tasks/{task_name}/run", response_model=AgentRunResponse)
async def run_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    request: TaskRunRequest | None = None,
) -> AgentRunResponse:
    """Run a task using its configured default_task.

    Tasks are the preferred way to run agents - they have a pre-configured
    task so no task input is required. Optionally accepts an additional_prompt
    to provide runtime direction (e.g., "Focus on the backup system").

    Args:
        task_name: Name of the task to run.
        request: Optional request body with additional_prompt.

    Returns:
        Run ID and initial status.
    """
    registry, executor, _state = get_agent_components()

    # Get task
    task = registry.get_task(task_name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Get template
    template = registry.get_template(task.agent_type)
    if not template:
        raise HTTPException(
            status_code=500,
            detail=f"Template '{task.agent_type}' not found for task '{task_name}'",
        )

    # Compose task prompt: prepend assignment if provided
    task_prompt = task.default_task
    if request and request.additional_prompt:
        task_prompt = f"## Assignment\n{request.additional_prompt}\n\n---\n\n{task.default_task}"

    # Create run record with task
    run = executor.create_run(template, task_prompt, task)

    logger.info(f"Starting task run: {run.id} for {task_name}")

    # Execute in background
    async def _execute_task() -> None:
        try:
            await executor.execute(template, task_prompt, run, task)
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Task run {run.id} failed: {e}")
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            # Persist failure state to database
            executor._persist_run_completion(run)

    # Schedule background execution
    background_tasks.add_task(_execute_task)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Task '{task_name}' started",
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
    registry, _executor, _state = get_agent_components()

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
    registry, _executor, _state = get_agent_components()

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
    registry, executor, _state = get_agent_components()

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
    registry, executor, _state = get_agent_components()

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
            executor._persist_run_completion(run)

    # Schedule background execution
    background_tasks.add_task(_execute_agent)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Agent '{agent_name}' started with task: {request.task[:100]}...",
    )
