"""Agent API routes for the CI daemon.

These routes provide the HTTP interface for the agent subsystem:
- List available templates and tasks
- Run tasks (not templates)
- Create tasks from templates
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
    AgentListItem,
    AgentListResponse,
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
    AgentTaskListItem,
    AgentTemplateListItem,
    CreateTaskRequest,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_PROJECT_CONFIG_DIR,
    DEFAULT_BASE_URL,
)
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
    """List all available templates and tasks.

    Templates define capabilities but cannot be run directly.
    Tasks are runnable - they have a configured default_task.
    """
    registry, _executor, _state = _get_agent_components()

    templates = registry.list_templates()
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
        tasks=task_items,
        tasks_dir=AGENT_PROJECT_CONFIG_DIR,
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
    _registry, executor, _state = _get_agent_components()

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
    _registry, executor, state = _get_agent_components()

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
    _registry, _executor, state = _get_agent_components()

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
# Task Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.post("/tasks/{task_name}/run", response_model=AgentRunResponse)
async def run_task(
    task_name: str,
    background_tasks: BackgroundTasks,
) -> AgentRunResponse:
    """Run a task using its configured default_task.

    Tasks are the preferred way to run agents - they have a pre-configured
    task so no task input is required.

    Args:
        task_name: Name of the task to run.

    Returns:
        Run ID and initial status.
    """
    registry, executor, _state = _get_agent_components()

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

    # Create run record with task
    run = executor.create_run(template, task.default_task, task)

    logger.info(f"Starting task run: {run.id} for {task_name}")

    # Execute in background
    async def _execute_task() -> None:
        try:
            await executor.execute(template, task.default_task, run, task)
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
    registry, _executor, _state = _get_agent_components()

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
    registry, _executor, _state = _get_agent_components()

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
# Schedule Routes (MUST come before /{agent_name} wildcard)
# =============================================================================


@router.get("/schedules")
async def list_schedules(
    enabled_only: bool = Query(default=False, description="Only return enabled schedules"),
) -> dict:
    """List all agent schedules with their runtime state.

    Returns schedules for tasks that have a cron schedule configured,
    including their enabled status, last run time, and next run time.

    Args:
        enabled_only: If True, only return enabled schedules.

    Returns:
        List of schedule records with task metadata.
    """
    registry, _executor, state = _get_agent_components()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    # Get runtime state from database
    db_schedules = state.activity_store.list_schedules(enabled_only=enabled_only)

    # Enrich with task metadata
    schedules = []
    for sched in db_schedules:
        task = registry.get_task(sched["task_name"])
        # Schedule definitions now live in database, not in task model
        schedule_info = {
            **sched,
            "display_name": task.display_name if task else None,
            "cron": sched.get("cron_expression"),
            "schedule_description": sched.get("description"),
        }
        schedules.append(schedule_info)

    return {
        "schedules": schedules,
        "total": len(schedules),
    }


@router.put("/schedules/{task_name}")
async def update_schedule(
    task_name: str,
    enabled: bool = Query(..., description="Enable or disable the schedule"),
) -> dict:
    """Enable or disable a task's schedule.

    Args:
        task_name: Name of the task.
        enabled: Whether to enable or disable the schedule.

    Returns:
        Updated schedule state.
    """
    registry, _executor, state = _get_agent_components()

    # Verify task exists
    task = registry.get_task(task_name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    # Check if schedule exists in database (schedules are now DB-only)
    existing_schedule = state.activity_store.get_schedule(task_name)
    if not existing_schedule:
        raise HTTPException(
            status_code=400,
            detail=f"Task '{task_name}' has no schedule configured",
        )

    # Update the schedule
    state.activity_store.update_schedule(task_name=task_name, enabled=enabled)

    # Get updated state
    updated = state.activity_store.get_schedule(task_name)

    return {
        "success": True,
        "message": f"Schedule {'enabled' if enabled else 'disabled'} for '{task_name}'",
        "schedule": updated,
    }


# =============================================================================
# Settings Routes (Provider Configuration)
# =============================================================================


@router.get("/settings")
async def get_agent_settings() -> dict:
    """Get agent settings including provider configuration.

    Returns current agent configuration from CI config file.
    """
    from open_agent_kit.features.codebase_intelligence.agents.models import AgentProvider

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    agents_config = config.agents

    # Create provider instance to get computed properties
    provider = AgentProvider(
        type=agents_config.provider_type,
        base_url=agents_config.provider_base_url,
        model=agents_config.provider_model,
    )

    return {
        "enabled": agents_config.enabled,
        "max_turns": agents_config.max_turns,
        "timeout_seconds": agents_config.timeout_seconds,
        "provider": {
            "type": agents_config.provider_type,
            "base_url": agents_config.provider_base_url or provider.default_base_url,
            "model": agents_config.provider_model,
            "api_format": provider.api_format,
            "recommended_models": provider.recommended_models,
        },
    }


@router.put("/settings")
async def update_agent_settings(request: dict) -> dict:
    """Update agent settings including provider configuration.

    Accepts JSON with optional fields:
    - enabled: bool
    - max_turns: int
    - timeout_seconds: int
    - provider: { type, base_url, model }
    """
    from open_agent_kit.features.codebase_intelligence.config import save_ci_config

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    changed = False

    # Update basic settings
    if "enabled" in request:
        config.agents.enabled = request["enabled"]
        changed = True
    if "max_turns" in request:
        config.agents.max_turns = request["max_turns"]
        changed = True
    if "timeout_seconds" in request:
        config.agents.timeout_seconds = request["timeout_seconds"]
        changed = True

    # Update provider settings
    if "provider" in request and isinstance(request["provider"], dict):
        provider_data = request["provider"]
        if "type" in provider_data:
            config.agents.provider_type = provider_data["type"]
            changed = True
        if "base_url" in provider_data:
            config.agents.provider_base_url = provider_data["base_url"]
            changed = True
        if "model" in provider_data:
            config.agents.provider_model = provider_data["model"]
            changed = True

    if changed:
        save_ci_config(state.project_root, config)
        state.ci_config = config

    return {
        "success": True,
        "message": "Agent settings updated" if changed else "No changes made",
        "settings": {
            "enabled": config.agents.enabled,
            "max_turns": config.agents.max_turns,
            "timeout_seconds": config.agents.timeout_seconds,
            "provider_type": config.agents.provider_type,
            "provider_base_url": config.agents.provider_base_url,
            "provider_model": config.agents.provider_model,
        },
    }


@router.get("/provider-models")
async def list_agent_provider_models(
    provider: str = Query(default="ollama", description="Provider type"),
    base_url: str = Query(default=DEFAULT_BASE_URL, description="Provider base URL"),
) -> dict:
    """List LLM models available from a provider for agent execution.

    Queries the provider's API to get available chat/completion models.
    Filters out embedding-only models.

    Note: Only localhost URLs are allowed for security (prevents SSRF).
    """
    from urllib.parse import urlparse

    import httpx

    # Security: Validate URL is localhost-only
    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname
        if not hostname or hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
            return {
                "success": False,
                "error": "Only localhost URLs are allowed for security",
                "models": [],
            }
    except (ValueError, AttributeError):
        return {"success": False, "error": "Invalid URL format", "models": []}

    # Patterns to filter out embedding models
    embedding_patterns = [
        "embed",
        "embedding",
        "bge-",
        "bge:",
        "gte-",
        "e5-",
        "nomic-embed",
        "arctic-embed",
        "mxbai-embed",
    ]

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "ollama":
                # Query Ollama native API
                response = await client.get(f"{url}/api/tags")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Ollama returned status {response.status_code}",
                        "models": [],
                    }

                data = response.json()
                all_models = data.get("models", [])

                # Filter for LLM models (exclude embedding models)
                llm_models = []
                for model in all_models:
                    name = model.get("name", "")
                    name_lower = name.lower()

                    # Skip embedding models
                    if any(pattern in name_lower for pattern in embedding_patterns):
                        continue

                    # Get size for display
                    size = model.get("size", 0)
                    size_str = f"{size / 1e9:.1f}GB" if size > 1e9 else f"{size / 1e6:.0f}MB"

                    llm_models.append(
                        {
                            "id": name,
                            "name": name,
                            "size": size_str,
                            "provider": "ollama",
                        }
                    )

                return {"success": True, "models": llm_models}

            else:
                # Use OpenAI-compatible /v1/models endpoint
                api_url = url if url.endswith("/v1") else f"{url}/v1"
                response = await client.get(f"{api_url}/models")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status_code}",
                        "models": [],
                    }

                data = response.json()
                all_models = data.get("data", [])

                # Filter for LLM models
                llm_models = []
                for model in all_models:
                    model_id = model.get("id", "")
                    model_lower = model_id.lower()

                    # Skip embedding models
                    if any(pattern in model_lower for pattern in embedding_patterns):
                        continue

                    llm_models.append(
                        {
                            "id": model_id,
                            "name": model_id,
                            "context_window": model.get("context_window"),
                            "provider": provider,
                        }
                    )

                return {"success": True, "models": llm_models}

    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "models": [],
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        logger.debug(f"Failed to query provider models: {e}")
        return {"success": False, "error": str(e), "models": []}


@router.post("/test-provider")
async def test_agent_provider(request: dict) -> dict:
    """Test agent provider connection.

    Tests that the provider is accessible and can list models.
    This is a lightweight check that doesn't run a full agent.

    Accepts JSON with:
    - provider: Provider type (ollama, lmstudio, etc.)
    - base_url: Provider base URL
    - model: Optional model to check for
    """
    from urllib.parse import urlparse

    import httpx

    provider = request.get("provider", "ollama")
    base_url = request.get("base_url", DEFAULT_BASE_URL)
    model = request.get("model")

    # Security: Validate URL is localhost-only
    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname
        if not hostname or hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
            return {
                "success": False,
                "error": "Only localhost URLs are allowed for security",
                "suggestion": "Use localhost or 127.0.0.1",
            }
    except (ValueError, AttributeError):
        return {"success": False, "error": "Invalid URL format"}

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "ollama":
                # Test Ollama connection
                response = await client.get(f"{url}/api/tags")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Ollama returned status {response.status_code}",
                        "suggestion": "Make sure Ollama is running: ollama serve",
                    }

                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]

                # Check if specific model is available
                if model and model not in models:
                    # Check partial match (model without tag)
                    base_model = model.split(":")[0]
                    if not any(m.startswith(base_model) for m in models):
                        return {
                            "success": False,
                            "error": f"Model '{model}' not found",
                            "suggestion": f"Pull the model: ollama pull {model}",
                            "available_models": models[:10],
                        }

                return {
                    "success": True,
                    "provider": provider,
                    "message": f"Connected to Ollama with {len(models)} models available",
                    "model_available": model in models if model else None,
                }

            else:
                # Test OpenAI-compatible endpoint
                api_url = url if url.endswith("/v1") else f"{url}/v1"
                response = await client.get(f"{api_url}/models")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status_code}",
                        "suggestion": f"Make sure {provider} is running at {base_url}",
                    }

                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]

                return {
                    "success": True,
                    "provider": provider,
                    "message": f"Connected with {len(models)} models available",
                    "model_available": model in models if model else None,
                }

    except httpx.ConnectError:
        suggestions = {
            "ollama": "Make sure Ollama is running: ollama serve",
            "lmstudio": "Make sure LM Studio is running with the server enabled",
        }
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "suggestion": suggestions.get(provider, f"Check that {provider} is running"),
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        return {"success": False, "error": f"Connection test failed: {e}"}


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
    """Trigger an agent run (legacy - prefer /tasks/{name}/run).

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
