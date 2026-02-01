"""Schedule API routes for the CI daemon.

These routes provide the HTTP interface for agent scheduling:
- List all schedules with their status
- Get schedule details for a specific instance
- Enable/disable schedules
- Manually trigger scheduled runs
- Force sync schedules from YAML
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

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

    instance_name: str
    has_definition: bool = Field(description="Whether YAML defines a schedule")
    has_db_record: bool = Field(description="Whether database has runtime state")
    cron: str | None = Field(default=None, description="Cron expression from YAML")
    description: str | None = Field(default=None, description="Schedule description")
    enabled: bool | None = Field(default=None, description="Whether schedule is enabled")
    last_run_at: str | None = Field(default=None, description="Last execution time")
    last_run_id: str | None = Field(default=None, description="ID of last run")
    next_run_at: str | None = Field(default=None, description="Next scheduled time")


class ScheduleListResponse(BaseModel):
    """Response model for schedule list."""

    schedules: list[ScheduleStatusResponse]
    total: int
    scheduler_running: bool


class ScheduleUpdateRequest(BaseModel):
    """Request model for updating schedule state."""

    enabled: bool | None = Field(default=None, description="Enable or disable the schedule")


class ScheduleSyncResponse(BaseModel):
    """Response model for schedule sync."""

    created: int
    updated: int
    removed: int
    total: int


class ScheduleRunResponse(BaseModel):
    """Response model for manual run trigger."""

    instance_name: str
    run_id: str | None = None
    status: str | None = None
    error: str | None = None
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

    Returns combined information from YAML definitions and database runtime state.
    """
    scheduler, _state = _get_scheduler()

    statuses = scheduler.list_schedule_statuses()

    schedule_responses = [
        ScheduleStatusResponse(
            instance_name=s["instance_name"],
            has_definition=s.get("has_definition", False),
            has_db_record=s.get("has_db_record", False),
            cron=s.get("cron"),
            description=s.get("description"),
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


@router.get("/{instance_name}", response_model=ScheduleStatusResponse)
async def get_schedule(instance_name: str) -> ScheduleStatusResponse:
    """Get schedule details for a specific instance.

    Args:
        instance_name: Name of the agent instance.
    """
    scheduler, _state = _get_scheduler()

    status = scheduler.get_schedule_status(instance_name)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for instance '{instance_name}'",
        )

    return ScheduleStatusResponse(
        instance_name=status["instance_name"],
        has_definition=status.get("has_definition", False),
        has_db_record=status.get("has_db_record", False),
        cron=status.get("cron"),
        description=status.get("description"),
        enabled=status.get("enabled"),
        last_run_at=status.get("last_run_at"),
        last_run_id=status.get("last_run_id"),
        next_run_at=status.get("next_run_at"),
    )


@router.patch("/{instance_name}", response_model=ScheduleStatusResponse)
async def update_schedule(
    instance_name: str, request: ScheduleUpdateRequest
) -> ScheduleStatusResponse:
    """Update schedule state (enable/disable).

    Args:
        instance_name: Name of the agent instance.
        request: Update request with enabled field.
    """
    scheduler, state = _get_scheduler()

    # Check schedule exists
    existing = scheduler.get_schedule_status(instance_name)
    if existing is None or not existing.get("has_db_record"):
        raise HTTPException(
            status_code=404,
            detail=f"No schedule record found for instance '{instance_name}'",
        )

    # Update if enabled field provided
    if request.enabled is not None and state.activity_store:
        state.activity_store.update_schedule(instance_name, enabled=request.enabled)
        logger.info(f"Schedule '{instance_name}' enabled={request.enabled}")

    # Return updated status
    status = scheduler.get_schedule_status(instance_name)
    if status is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated schedule")

    return ScheduleStatusResponse(
        instance_name=status["instance_name"],
        has_definition=status.get("has_definition", False),
        has_db_record=status.get("has_db_record", False),
        cron=status.get("cron"),
        description=status.get("description"),
        enabled=status.get("enabled"),
        last_run_at=status.get("last_run_at"),
        last_run_id=status.get("last_run_id"),
        next_run_at=status.get("next_run_at"),
    )


@router.post("/{instance_name}/run", response_model=ScheduleRunResponse)
async def run_schedule(
    instance_name: str, background_tasks: BackgroundTasks
) -> ScheduleRunResponse:
    """Manually trigger a scheduled agent run.

    This runs the agent immediately, bypassing the cron schedule.
    The schedule's last_run and next_run are updated as if it ran normally.

    Args:
        instance_name: Name of the agent instance to run.
    """
    scheduler, state = _get_scheduler()

    # Check schedule exists
    status = scheduler.get_schedule_status(instance_name)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for instance '{instance_name}'",
        )

    # Get database schedule record
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not available")

    schedule = state.activity_store.get_schedule(instance_name)
    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule record found for instance '{instance_name}'",
        )

    # Run in background
    async def _run_agent() -> dict[str, Any]:
        return await scheduler.run_scheduled_agent(schedule)

    # For manual runs, we run synchronously to return the result
    result = await scheduler.run_scheduled_agent(schedule)

    if result.get("error"):
        return ScheduleRunResponse(
            instance_name=instance_name,
            run_id=result.get("run_id"),
            status=result.get("status"),
            error=result.get("error"),
            message=f"Run completed with error: {result.get('error')}",
        )

    return ScheduleRunResponse(
        instance_name=instance_name,
        run_id=result.get("run_id"),
        status=result.get("status"),
        message="Run completed successfully",
    )


@router.post("/sync", response_model=ScheduleSyncResponse)
async def sync_schedules() -> ScheduleSyncResponse:
    """Force sync schedules from YAML definitions to database.

    This re-reads all instance YAML files and updates the database:
    - Creates records for new schedules
    - Removes orphaned records (YAML definition removed)
    - Updates next_run times if missing
    """
    scheduler, _state = _get_scheduler()

    result = scheduler.sync_schedules()

    return ScheduleSyncResponse(
        created=result["created"],
        updated=result["updated"],
        removed=result["removed"],
        total=result["total"],
    )
