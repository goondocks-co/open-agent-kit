"""Agent API routes for the CI daemon.

These routes provide the HTTP interface for the agent subsystem:
- List available templates and instances
- Run instances (not templates)
- Create instances from templates
- Monitor run status
- Cancel running agents

IMPORTANT: Route order matters in FastAPI. Specific paths (like /runs/, /reload)
must be defined BEFORE wildcard paths (like /{agent_name}) to avoid the wildcard
catching everything.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDetailResponse,
    AgentInstanceListItem,
    AgentListItem,
    AgentListResponse,
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
    AgentTemplateListItem,
    CreateInstanceRequest,
)
from open_agent_kit.features.codebase_intelligence.constants import AGENT_PROJECT_CONFIG_DIR
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _get_agent_components() -> tuple["AgentRegistry", "AgentExecutor", "DaemonState"]:
    """Get agent registry and executor or raise HTTP error."""
    state = get_state()

    if not state.agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Agents may be disabled in config.",
        )

    if not state.agent_executor:
        raise HTTPException(
            status_code=503,
            detail="Agent executor not initialized. Agents may be disabled in config.",
        )

    return state.agent_registry, state.agent_executor, state


# =============================================================================
# List Routes (no path parameters)
# =============================================================================


@router.get("", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """List all available templates and instances.

    Templates define capabilities but cannot be run directly.
    Instances are runnable - they have a configured default_task.
    """
    registry, _executor, _state = _get_agent_components()

    templates = registry.list_templates()
    instances = registry.list_instances()

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

    # Build instance list items (include template execution settings)
    instance_items = []
    for inst in instances:
        template = registry.get_template(inst.agent_type)
        if template:
            instance_items.append(
                AgentInstanceListItem(
                    name=inst.name,
                    display_name=inst.display_name,
                    agent_type=inst.agent_type,
                    description=inst.description,
                    default_task=inst.default_task,
                    max_turns=template.execution.max_turns,
                    timeout_seconds=template.execution.timeout_seconds,
                )
            )

    # Legacy: also return agents list for backwards compatibility
    legacy_items = [
        AgentListItem(
            name=a.name,
            display_name=a.display_name,
            description=a.description,
            max_turns=a.execution.max_turns,
            timeout_seconds=a.execution.timeout_seconds,
            project_config=a.project_config,
        )
        for a in templates
    ]

    return AgentListResponse(
        templates=template_items,
        instances=instance_items,
        instances_dir=AGENT_PROJECT_CONFIG_DIR,
        agents=legacy_items,
        total=len(templates),
    )


# =============================================================================
# Runs Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.get("/runs", response_model=AgentRunListResponse)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> AgentRunListResponse:
    """List agent runs with optional filtering.

    Args:
        limit: Maximum runs to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        status: Filter by run status.

    Returns:
        List of runs with pagination info.
    """
    _registry, executor, _state = _get_agent_components()

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
    _registry, executor, _state = _get_agent_components()

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
    _registry, executor, _state = _get_agent_components()

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
    registry, _executor, _state = _get_agent_components()

    count = registry.reload()

    return {
        "success": True,
        "message": f"Reloaded {count} agents",
        "agents": registry.list_names(),
    }


# =============================================================================
# Instance Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/instances/{instance_name}/run", response_model=AgentRunResponse)
async def run_instance(
    instance_name: str,
    background_tasks: BackgroundTasks,
) -> AgentRunResponse:
    """Run an instance using its configured default_task.

    Instances are the preferred way to run agents - they have a pre-configured
    task so no task input is required.

    Args:
        instance_name: Name of the instance to run.

    Returns:
        Run ID and initial status.
    """
    registry, executor, _state = _get_agent_components()

    # Get instance
    instance = registry.get_instance(instance_name)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_name}' not found")

    # Get template
    template = registry.get_template(instance.agent_type)
    if not template:
        raise HTTPException(
            status_code=500,
            detail=f"Template '{instance.agent_type}' not found for instance '{instance_name}'",
        )

    # Create run record with instance
    run = executor.create_run(template, instance.default_task, instance)

    logger.info(f"Starting instance run: {run.id} for {instance_name}")

    # Execute in background
    async def _execute_instance() -> None:
        try:
            await executor.execute(template, instance.default_task, run, instance)
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Instance run {run.id} failed: {e}")
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            # Persist failure state to database
            executor._persist_run_completion(run)

    # Schedule background execution
    background_tasks.add_task(_execute_instance)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Instance '{instance_name}' started",
    )


# =============================================================================
# Template Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/templates/{template_name}/create-instance")
async def create_instance(
    template_name: str,
    request: CreateInstanceRequest,
) -> dict:
    """Create a new instance from a template.

    Generates an instance YAML file in the project's agent instances directory
    with scaffolding for common configuration options.

    Args:
        template_name: Name of the template to use.
        request: Instance creation request.

    Returns:
        Created instance details.
    """
    registry, _executor, _state = _get_agent_components()

    try:
        instance = registry.create_instance(
            name=request.name,
            template_name=template_name,
            display_name=request.display_name,
            description=request.description,
            default_task=request.default_task,
        )

        return {
            "success": True,
            "message": f"Created instance '{instance.name}'",
            "instance": {
                "name": instance.name,
                "display_name": instance.display_name,
                "agent_type": instance.agent_type,
                "description": instance.description,
                "instance_path": instance.instance_path,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write instance file: {e}") from e


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
    registry, executor, _state = _get_agent_components()

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
    """Trigger an agent run (legacy - prefer /instances/{name}/run).

    Starts the agent in the background and returns immediately with a run ID
    that can be used to monitor progress.

    Args:
        agent_name: Name of the agent to run.
        request: Run request with task description.

    Returns:
        Run ID and initial status.
    """
    registry, executor, _state = _get_agent_components()

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
