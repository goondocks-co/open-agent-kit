"""Shared agent route handler functions.

Pure functions that accept (registry, executor, ...) and return response
models.  Each daemon's route files remain thin wrappers that call these.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import BackgroundTasks, HTTPException

from open_agent_kit.features.agent_runtime.models import (
    AgentListItem,
    AgentListResponse,
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunStatus,
    AgentTaskListItem,
    AgentTemplateListItem,
)

if TYPE_CHECKING:
    from open_agent_kit.features.agent_runtime.executor import AgentExecutor
    from open_agent_kit.features.agent_runtime.registry import AgentRegistry

logger = logging.getLogger(__name__)


def build_agent_list_response(
    registry: AgentRegistry,
    tasks_dir: str = "",
) -> AgentListResponse:
    """Build the standard agent list response from a registry.

    Args:
        registry: Agent registry to query.
        tasks_dir: Directory where task YAML files are stored.

    Returns:
        AgentListResponse with templates, tasks, and legacy agents.
    """
    templates = [t for t in registry.list_templates() if not t.internal]
    tasks = registry.list_tasks()

    # Build template and legacy items in a single pass
    template_items = []
    legacy_items = []
    for t in templates:
        template_items.append(
            AgentTemplateListItem(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                max_turns=t.execution.max_turns,
                timeout_seconds=t.execution.timeout_seconds,
            )
        )
        legacy_items.append(
            AgentListItem(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                max_turns=t.execution.max_turns,
                timeout_seconds=t.execution.timeout_seconds,
                project_config=t.project_config,
            )
        )

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

    return AgentListResponse(
        templates=template_items,
        tasks=task_items,
        tasks_dir=tasks_dir,
        agents=legacy_items,
        total=len(templates),
    )


def reload_registry(registry: AgentRegistry) -> dict:
    """Reload agent definitions and return result dict.

    Args:
        registry: Agent registry to reload.

    Returns:
        Dict with success, message, and agent names.
    """
    count = registry.reload()
    return {
        "success": True,
        "message": f"Reloaded {count} agents",
        "agents": registry.list_names(),
    }


def start_task_run(
    registry: AgentRegistry,
    executor: AgentExecutor,
    task_name: str,
    additional_prompt: str | None,
    background_tasks: BackgroundTasks,
) -> AgentRunResponse:
    """Look up a task, compose prompt, and start a background run.

    Args:
        registry: Agent registry.
        executor: Agent executor.
        task_name: Name of the task to run.
        additional_prompt: Optional runtime direction.
        background_tasks: FastAPI BackgroundTasks for async execution.

    Returns:
        AgentRunResponse with run_id and status.

    Raises:
        HTTPException: 404 if task not found, 500 if template missing.
    """
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
    if additional_prompt:
        task_prompt = f"## Assignment\n{additional_prompt}\n\n---\n\n{task.default_task}"

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
            executor.persist_completion(run)

    background_tasks.add_task(_execute_task)

    return AgentRunResponse(
        run_id=run.id,
        status=run.status,
        message=f"Task '{task_name}' started",
    )


def list_runs(
    executor: AgentExecutor,
    limit: int = 20,
    offset: int = 0,
    agent_name: str | None = None,
    status_filter: AgentRunStatus | None = None,
) -> AgentRunListResponse:
    """List agent runs with basic filtering.

    Args:
        executor: Agent executor.
        limit: Maximum runs to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        status_filter: Filter by run status.

    Returns:
        AgentRunListResponse with runs and pagination info.
    """
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


def get_run_detail(
    executor: AgentExecutor,
    run_id: str,
) -> AgentRunDetailResponse:
    """Get detailed information about a specific run.

    Args:
        executor: Agent executor.
        run_id: Run identifier.

    Returns:
        AgentRunDetailResponse with full run details.

    Raises:
        HTTPException: 404 if run not found.
    """
    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return AgentRunDetailResponse(run=run)
