"""Schedule API routes for the CI daemon.

These routes provide the HTTP interface for agent scheduling:
- List all schedules with their status
- Get schedule details for a specific task
- Create new schedules
- Update schedule definitions (cron, description, enabled)
- Delete schedules
- Manually trigger scheduled runs
- Sync (clean up orphaned) schedules

The database is the sole source of truth for schedules. YAML schedule support
has been deprecated.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.constants import (
    SCHEDULE_TRIGGER_CRON,
    VALID_SCHEDULE_TRIGGER_TYPES,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.agents.scheduler import AgentScheduler
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ScheduleStatusResponse(BaseModel):
    """Response model for schedule status."""

    task_name: str
    has_definition: bool = Field(description="Whether schedule has a cron expression")
    has_db_record: bool = Field(description="Whether schedule exists in database")
    has_task: bool = Field(default=True, description="Whether agent task exists")
    cron: str | None = Field(default=None, description="Cron expression")
    description: str | None = Field(default=None, description="Schedule description")
    trigger_type: str = Field(
        default=SCHEDULE_TRIGGER_CRON, description="Trigger type: cron or manual"
    )
    additional_prompt: str | None = Field(
        default=None, max_length=10000, description="Persistent assignment for each run"
    )
    enabled: bool | None = Field(default=None, description="Whether schedule is enabled")
    last_run_at: str | None = Field(default=None, description="Last execution time")
    last_run_id: str | None = Field(default=None, description="ID of last run")
    next_run_at: str | None = Field(default=None, description="Next scheduled time")


class ScheduleListResponse(BaseModel):
    """Response model for schedule list."""

    schedules: list[ScheduleStatusResponse]
    total: int
    scheduler_running: bool


class ScheduleCreateRequest(BaseModel):
    """Request model for creating a new schedule."""

    task_name: str = Field(..., min_length=1, description="Name of agent task")
    cron_expression: str | None = Field(
        default=None,
        description="Cron expression (e.g., '0 0 * * MON' for weekly Monday)",
    )
    description: str = Field(default="", description="Human-readable description")
    trigger_type: str = Field(
        default=SCHEDULE_TRIGGER_CRON,
        description="Trigger type: 'cron' or 'manual'",
    )
    additional_prompt: str | None = Field(
        default=None, max_length=10000, description="Persistent assignment for each run"
    )


class ScheduleUpdateRequest(BaseModel):
    """Request model for updating schedule definition."""

    enabled: bool | None = Field(default=None, description="Enable or disable the schedule")
    cron_expression: str | None = Field(default=None, description="Cron expression to set")
    description: str | None = Field(default=None, description="Description to set")
    trigger_type: str | None = Field(default=None, description="Trigger type to set")
    additional_prompt: str | None = Field(
        default=None, max_length=10000, description="Persistent assignment for each run"
    )


class ScheduleSyncResponse(BaseModel):
    """Response model for schedule sync (orphan cleanup)."""

    created: int = Field(default=0, description="Always 0 (no auto-creation)")
    updated: int = Field(default=0, description="Always 0 (no auto-updates)")
    removed: int = Field(description="Number of orphaned schedules removed")
    total: int = Field(description="Total schedules remaining")


class ScheduleRunResponse(BaseModel):
    """Response model for manual run trigger."""

    task_name: str
    run_id: str | None = None
    status: str | None = None
    error: str | None = None
    skipped: bool = Field(default=False, description="True if run was skipped (already running)")
    message: str


class ScheduleDeleteResponse(BaseModel):
    """Response model for schedule deletion."""

    task_name: str
    deleted: bool
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def _get_scheduler() -> tuple["AgentScheduler", "DaemonState"]:
    """Get agent scheduler or raise HTTP error."""
    state = get_state()

    if not state.agent_scheduler:
        raise HTTPException(
            status_code=503,
            detail="Agent scheduler not initialized. Agents or activity store may be disabled.",
        )

    return state.agent_scheduler, state


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=ScheduleListResponse)
async def list_schedules() -> ScheduleListResponse:
    """List all schedules with their status.

    Returns all schedule records from the database with their runtime state.
    """
    scheduler, _state = _get_scheduler()

    statuses = scheduler.list_schedule_statuses()

    schedule_responses = [
        ScheduleStatusResponse(
            task_name=s["task_name"],
            has_definition=s.get("has_definition", False),
            has_db_record=s.get("has_db_record", False),
            has_task=s.get("has_task", True),
            cron=s.get("cron"),
            description=s.get("description"),
            trigger_type=s.get("trigger_type", SCHEDULE_TRIGGER_CRON),
            additional_prompt=s.get("additional_prompt"),
            enabled=s.get("enabled"),
            last_run_at=s.get("last_run_at"),
            last_run_id=s.get("last_run_id"),
            next_run_at=s.get("next_run_at"),
        )
        for s in statuses
    ]

    return ScheduleListResponse(
        schedules=schedule_responses,
        total=len(schedule_responses),
        scheduler_running=scheduler.is_running,
    )


@router.get("/{task_name}", response_model=ScheduleStatusResponse)
async def get_schedule(task_name: str) -> ScheduleStatusResponse:
    """Get schedule details for a specific task.

    Args:
        task_name: Name of the agent task.
    """
    scheduler, _state = _get_scheduler()

    status = scheduler.get_schedule_status(task_name)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for task '{task_name}'",
        )

    return ScheduleStatusResponse(
        task_name=status["task_name"],
        has_definition=status.get("has_definition", False),
        has_db_record=status.get("has_db_record", False),
        has_task=status.get("has_task", True),
        cron=status.get("cron"),
        description=status.get("description"),
        trigger_type=status.get("trigger_type", SCHEDULE_TRIGGER_CRON),
        additional_prompt=status.get("additional_prompt"),
        enabled=status.get("enabled"),
        last_run_at=status.get("last_run_at"),
        last_run_id=status.get("last_run_id"),
        next_run_at=status.get("next_run_at"),
    )


@router.post("", response_model=ScheduleStatusResponse, status_code=201)
async def create_schedule(request: ScheduleCreateRequest) -> ScheduleStatusResponse:
    """Create a new schedule for an agent task.

    Args:
        request: Schedule creation request with task_name, cron, etc.
    """
    scheduler, state = _get_scheduler()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    # Validate task exists
    if state.agent_registry:
        task = state.agent_registry.get_task(request.task_name)
        if task is None:
            raise HTTPException(
                status_code=400,
                detail=f"Agent task '{request.task_name}' not found",
            )

    # Check schedule doesn't already exist
    existing = state.activity_store.get_schedule(request.task_name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Schedule already exists for task '{request.task_name}'",
        )

    # Validate trigger_type
    if request.trigger_type not in VALID_SCHEDULE_TRIGGER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type '{request.trigger_type}'. Must be one of: {VALID_SCHEDULE_TRIGGER_TYPES}",
        )

    # Validate cron expression if provided
    next_run_at = None
    if request.cron_expression:
        if not scheduler.validate_cron(request.cron_expression):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: '{request.cron_expression}'",
            )
        # Compute next run time for cron schedules
        if request.trigger_type == SCHEDULE_TRIGGER_CRON:
            next_run_at = scheduler.compute_next_run(request.cron_expression)

    # Create schedule
    state.activity_store.create_schedule(
        task_name=request.task_name,
        cron_expression=request.cron_expression,
        description=request.description,
        trigger_type=request.trigger_type,
        next_run_at=next_run_at,
        additional_prompt=request.additional_prompt,
    )

    logger.info(f"Created schedule for '{request.task_name}': cron={request.cron_expression}")

    # Return created schedule
    status = scheduler.get_schedule_status(request.task_name)
    if status is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created schedule")

    return ScheduleStatusResponse(
        task_name=status["task_name"],
        has_definition=status.get("has_definition", False),
        has_db_record=status.get("has_db_record", False),
        has_task=status.get("has_task", True),
        cron=status.get("cron"),
        description=status.get("description"),
        trigger_type=status.get("trigger_type", SCHEDULE_TRIGGER_CRON),
        additional_prompt=status.get("additional_prompt"),
        enabled=status.get("enabled"),
        last_run_at=status.get("last_run_at"),
        last_run_id=status.get("last_run_id"),
        next_run_at=status.get("next_run_at"),
    )


@router.patch("/{task_name}", response_model=ScheduleStatusResponse)
@router.put("/{task_name}", response_model=ScheduleStatusResponse)
async def update_schedule(task_name: str, request: ScheduleUpdateRequest) -> ScheduleStatusResponse:
    """Update schedule definition (cron, description, enabled, trigger_type).

    Args:
        task_name: Name of the agent task.
        request: Update request with fields to change.
    """
    scheduler, state = _get_scheduler()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    # Check schedule exists
    existing = scheduler.get_schedule_status(task_name)
    if existing is None or not existing.get("has_db_record"):
        raise HTTPException(
            status_code=404,
            detail=f"No schedule record found for task '{task_name}'",
        )

    # Validate trigger_type if provided
    if (
        request.trigger_type is not None
        and request.trigger_type not in VALID_SCHEDULE_TRIGGER_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type '{request.trigger_type}'. Must be one of: {VALID_SCHEDULE_TRIGGER_TYPES}",
        )

    # Validate cron expression if provided
    next_run_at = None
    if request.cron_expression is not None:
        if request.cron_expression and not scheduler.validate_cron(request.cron_expression):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: '{request.cron_expression}'",
            )
        # Compute next run time if setting a cron expression
        if request.cron_expression:
            trigger = request.trigger_type or existing.get("trigger_type", SCHEDULE_TRIGGER_CRON)
            if trigger == SCHEDULE_TRIGGER_CRON:
                next_run_at = scheduler.compute_next_run(request.cron_expression)

    # Build update kwargs
    update_kwargs: dict[str, Any] = {}
    if request.enabled is not None:
        update_kwargs["enabled"] = request.enabled
    if request.cron_expression is not None:
        update_kwargs["cron_expression"] = request.cron_expression
    if request.description is not None:
        update_kwargs["description"] = request.description
    if request.trigger_type is not None:
        update_kwargs["trigger_type"] = request.trigger_type
    if request.additional_prompt is not None:
        update_kwargs["additional_prompt"] = request.additional_prompt
    if next_run_at is not None:
        update_kwargs["next_run_at"] = next_run_at

    if update_kwargs:
        state.activity_store.update_schedule(task_name, **update_kwargs)
        logger.info(f"Updated schedule '{task_name}': {update_kwargs}")

    # Return updated status
    status = scheduler.get_schedule_status(task_name)
    if status is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated schedule")

    return ScheduleStatusResponse(
        task_name=status["task_name"],
        has_definition=status.get("has_definition", False),
        has_db_record=status.get("has_db_record", False),
        has_task=status.get("has_task", True),
        cron=status.get("cron"),
        description=status.get("description"),
        trigger_type=status.get("trigger_type", SCHEDULE_TRIGGER_CRON),
        additional_prompt=status.get("additional_prompt"),
        enabled=status.get("enabled"),
        last_run_at=status.get("last_run_at"),
        last_run_id=status.get("last_run_id"),
        next_run_at=status.get("next_run_at"),
    )


@router.delete("/{task_name}", response_model=ScheduleDeleteResponse)
async def delete_schedule(task_name: str) -> ScheduleDeleteResponse:
    """Delete a schedule.

    Args:
        task_name: Name of the agent task.
    """
    scheduler, state = _get_scheduler()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    # Check schedule exists
    existing = scheduler.get_schedule_status(task_name)
    if existing is None or not existing.get("has_db_record"):
        raise HTTPException(
            status_code=404,
            detail=f"No schedule record found for task '{task_name}'",
        )

    # Delete the schedule
    deleted = state.activity_store.delete_schedule(task_name)

    if deleted:
        logger.info(f"Deleted schedule for '{task_name}'")
        return ScheduleDeleteResponse(
            task_name=task_name,
            deleted=True,
            message=f"Schedule for '{task_name}' deleted successfully",
        )
    else:
        return ScheduleDeleteResponse(
            task_name=task_name,
            deleted=False,
            message=f"Schedule for '{task_name}' was not found or already deleted",
        )


@router.post("/{task_name}/run", response_model=ScheduleRunResponse)
async def run_schedule(task_name: str, background_tasks: BackgroundTasks) -> ScheduleRunResponse:
    """Manually trigger a scheduled agent run.

    This runs the agent immediately, bypassing the cron schedule.
    The schedule's last_run and next_run are updated as if it ran normally.

    Args:
        task_name: Name of the agent task to run.
    """
    scheduler, state = _get_scheduler()

    # Check schedule exists
    status = scheduler.get_schedule_status(task_name)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for task '{task_name}'",
        )

    # Get database schedule record
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    schedule = state.activity_store.get_schedule(task_name)
    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule record found for task '{task_name}'",
        )

    # For manual runs, we run synchronously to return the result
    result = await scheduler.run_scheduled_agent(schedule)

    # Handle skipped runs (agent already running)
    if result.get("skipped"):
        return ScheduleRunResponse(
            task_name=task_name,
            skipped=True,
            message=f"Run skipped: {result.get('reason', 'unknown')}",
        )

    if result.get("error"):
        return ScheduleRunResponse(
            task_name=task_name,
            run_id=result.get("run_id"),
            status=result.get("status"),
            error=result.get("error"),
            message=f"Run completed with error: {result.get('error')}",
        )

    return ScheduleRunResponse(
        task_name=task_name,
        run_id=result.get("run_id"),
        status=result.get("status"),
        message="Run completed successfully",
    )


@router.post("/sync", response_model=ScheduleSyncResponse)
async def sync_schedules() -> ScheduleSyncResponse:
    """Clean up orphaned schedules.

    This removes schedules for agent tasks that no longer exist in the registry.
    YAML schedule sync is deprecated - use POST/PUT/DELETE endpoints instead.
    """
    scheduler, _state = _get_scheduler()

    result = scheduler.sync_schedules()

    return ScheduleSyncResponse(
        created=result["created"],
        updated=result["updated"],
        removed=result["removed"],
        total=result["total"],
    )
