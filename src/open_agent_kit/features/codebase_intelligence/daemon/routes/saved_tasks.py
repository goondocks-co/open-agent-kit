"""Saved tasks API routes for the CI daemon.

These routes provide the HTTP interface for managing saved task templates:
- Create, read, update, delete saved tasks
- Run saved tasks on-demand
- List saved tasks with filtering
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saved-tasks", tags=["saved-tasks"])


# =============================================================================
# Request/Response Models
# =============================================================================


class SavedTaskCreate(BaseModel):
    """Request to create a saved task."""

    name: str = Field(..., description="Human-readable name for the task")
    agent_name: str = Field(..., description="Name of the agent to run")
    task: str = Field(..., description="The task description/prompt")
    description: str | None = Field(None, description="Optional description")
    schedule_cron: str | None = Field(None, description="Optional cron expression")


class SavedTaskUpdate(BaseModel):
    """Request to update a saved task."""

    name: str | None = None
    description: str | None = None
    task: str | None = None
    schedule_cron: str | None = None
    schedule_enabled: bool | None = None


class SavedTaskResponse(BaseModel):
    """Single saved task response."""

    id: str
    name: str
    description: str | None
    agent_name: str
    task: str
    schedule_cron: str | None
    schedule_enabled: bool
    last_run_at: str | None
    last_run_id: str | None
    total_runs: int
    created_at: str
    updated_at: str


class SavedTaskListResponse(BaseModel):
    """List of saved tasks response."""

    tasks: list[SavedTaskResponse]
    total: int
    limit: int
    offset: int


class RunSavedTaskResponse(BaseModel):
    """Response from running a saved task."""

    run_id: str
    status: str
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def _dict_to_response(data: dict[str, Any]) -> SavedTaskResponse:
    """Convert database dict to response model."""
    return SavedTaskResponse(
        id=data["id"],
        name=data["name"],
        description=data.get("description"),
        agent_name=data["agent_name"],
        task=data["task"],
        schedule_cron=data.get("schedule_cron"),
        schedule_enabled=data.get("schedule_enabled", False),
        last_run_at=data.get("last_run_at"),
        last_run_id=data.get("last_run_id"),
        total_runs=data.get("total_runs", 0),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=SavedTaskListResponse)
async def list_saved_tasks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    scheduled_only: bool = Query(default=False, description="Only return scheduled tasks"),
) -> SavedTaskListResponse:
    """List saved tasks with optional filtering."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    tasks, total = state.activity_store.list_saved_tasks(
        limit=limit,
        offset=offset,
        agent_name=agent_name,
        scheduled_only=scheduled_only,
    )

    return SavedTaskListResponse(
        tasks=[_dict_to_response(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=SavedTaskResponse)
async def create_saved_task(request: SavedTaskCreate) -> SavedTaskResponse:
    """Create a new saved task."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Verify agent exists
    if state.agent_registry:
        agent = state.agent_registry.get(request.agent_name)
        if not agent:
            raise HTTPException(
                status_code=400,
                detail=f"Agent '{request.agent_name}' not found",
            )

    task_id = state.activity_store.create_saved_task(
        name=request.name,
        agent_name=request.agent_name,
        task=request.task,
        description=request.description,
        schedule_cron=request.schedule_cron,
    )

    task_data = state.activity_store.get_saved_task(task_id)
    if not task_data:
        raise HTTPException(status_code=500, detail="Failed to create task")

    return _dict_to_response(task_data)


@router.get("/{task_id}", response_model=SavedTaskResponse)
async def get_saved_task(task_id: str) -> SavedTaskResponse:
    """Get a saved task by ID."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    task_data = state.activity_store.get_saved_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return _dict_to_response(task_data)


@router.patch("/{task_id}", response_model=SavedTaskResponse)
async def update_saved_task(task_id: str, request: SavedTaskUpdate) -> SavedTaskResponse:
    """Update a saved task."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Check task exists
    existing = state.activity_store.get_saved_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    state.activity_store.update_saved_task(
        task_id=task_id,
        name=request.name,
        description=request.description,
        task=request.task,
        schedule_cron=request.schedule_cron,
        schedule_enabled=request.schedule_enabled,
    )

    task_data = state.activity_store.get_saved_task(task_id)
    if not task_data:
        raise HTTPException(status_code=500, detail="Failed to update task")

    return _dict_to_response(task_data)


@router.delete("/{task_id}")
async def delete_saved_task(task_id: str) -> dict:
    """Delete a saved task."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    deleted = state.activity_store.delete_saved_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return {"success": True, "message": f"Task {task_id} deleted"}


@router.post("/{task_id}/run", response_model=RunSavedTaskResponse)
async def run_saved_task(task_id: str) -> RunSavedTaskResponse:
    """Run a saved task immediately.

    Creates a new agent run using the saved task's configuration.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    if not state.agent_registry or not state.agent_executor:
        raise HTTPException(status_code=503, detail="Agent system not initialized")

    # Get the saved task
    task_data = state.activity_store.get_saved_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Get the agent
    agent = state.agent_registry.get(task_data["agent_name"])
    if not agent:
        raise HTTPException(
            status_code=400,
            detail=f"Agent '{task_data['agent_name']}' not found",
        )

    # Create the run
    agent_executor = state.agent_executor
    run = agent_executor.create_run(agent, task_data["task"])

    # Update saved task with run info
    state.activity_store.update_saved_task(
        task_id=task_id,
        last_run_at=datetime.now(),
        last_run_id=run.id,
        increment_runs=True,
    )

    # Import here to avoid circular imports
    import asyncio

    from open_agent_kit.features.codebase_intelligence.agents.models import AgentRunStatus

    # Execute in background
    async def _execute_agent() -> None:
        try:
            await agent_executor.execute(agent, task_data["task"], run)
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Saved task run {run.id} failed: {e}")
            run.status = AgentRunStatus.FAILED
            run.error = str(e)

    asyncio.create_task(_execute_agent())

    return RunSavedTaskResponse(
        run_id=run.id,
        status=run.status.value,
        message=f"Started '{task_data['name']}' (run: {run.id})",
    )
