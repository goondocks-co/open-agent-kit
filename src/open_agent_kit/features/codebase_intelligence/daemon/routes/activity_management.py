"""Activity management routes for delete operations.

This module provides API endpoints for deleting:
- Sessions (cascade: batches, activities, observations)
- Prompt batches (cascade: activities, observations)
- Individual activities
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
    ERROR_MSG_SESSION_NOT_FOUND,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    DeleteActivityResponse,
    DeleteBatchResponse,
    DeleteSessionResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


@router.delete("/api/activity/sessions/{session_id}", response_model=DeleteSessionResponse)
@handle_route_errors("delete session")
async def delete_session(session_id: str) -> DeleteSessionResponse:
    """Delete a session and all related data (cascade delete).

    Deletes:
    - The session record
    - All prompt batches for this session
    - All activities for this session
    - All memory observations for this session (SQLite + ChromaDB)
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting session: {session_id}")

    # Check session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Get observation IDs for ChromaDB cleanup before deleting from SQLite
    observation_ids = state.activity_store.get_session_observation_ids(session_id)

    # Delete from SQLite (cascade)
    result = state.activity_store.delete_session(session_id)

    # Delete from ChromaDB
    memories_deleted = 0
    if observation_ids and state.vector_store:
        memories_deleted = state.vector_store.delete_memories(observation_ids)

    logger.info(
        f"Deleted session {session_id}: "
        f"{result['batches_deleted']} batches, "
        f"{result['activities_deleted']} activities, "
        f"{result['observations_deleted']} SQLite observations, "
        f"{memories_deleted} ChromaDB memories"
    )

    return DeleteSessionResponse(
        success=True,
        deleted_count=1,
        message=f"Session {session_id[:8]}... deleted successfully",
        batches_deleted=result["batches_deleted"],
        activities_deleted=result["activities_deleted"],
        memories_deleted=result["observations_deleted"],
    )


@router.delete(
    "/api/activity/prompt-batches/{batch_id}",
    response_model=DeleteBatchResponse,
)
@handle_route_errors("delete prompt batch")
async def delete_prompt_batch(batch_id: int) -> DeleteBatchResponse:
    """Delete a prompt batch and all related data (cascade delete).

    Deletes:
    - The prompt batch record
    - All activities for this batch
    - All memory observations for this batch (SQLite + ChromaDB)
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting prompt batch: {batch_id}")

    # Check batch exists
    batch = state.activity_store.get_prompt_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Prompt batch not found")

    # Get observation IDs for ChromaDB cleanup before deleting from SQLite
    observation_ids = state.activity_store.get_batch_observation_ids(batch_id)

    # Delete from SQLite (cascade)
    result = state.activity_store.delete_prompt_batch(batch_id)

    # Delete from ChromaDB
    memories_deleted = 0
    if observation_ids and state.vector_store:
        memories_deleted = state.vector_store.delete_memories(observation_ids)

    logger.info(
        f"Deleted prompt batch {batch_id}: "
        f"{result['activities_deleted']} activities, "
        f"{result['observations_deleted']} SQLite observations, "
        f"{memories_deleted} ChromaDB memories"
    )

    return DeleteBatchResponse(
        success=True,
        deleted_count=1,
        message=f"Prompt batch {batch_id} deleted successfully",
        activities_deleted=result["activities_deleted"],
        memories_deleted=result["observations_deleted"],
    )


@router.delete(
    "/api/activity/activities/{activity_id}",
    response_model=DeleteActivityResponse,
)
@handle_route_errors("delete activity")
async def delete_activity(activity_id: int) -> DeleteActivityResponse:
    """Delete a single activity.

    If the activity has a linked observation, also deletes it from SQLite and ChromaDB.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting activity: {activity_id}")

    # Delete activity and get linked observation_id (if any)
    observation_id = state.activity_store.delete_activity(activity_id)

    if observation_id is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    # If there was a linked observation, delete it too
    memory_deleted = False
    if observation_id:
        state.activity_store.delete_observation(observation_id)
        if state.vector_store:
            state.vector_store.delete_memories([observation_id])
        memory_deleted = True
        logger.info(f"Also deleted linked observation: {observation_id}")

    return DeleteActivityResponse(
        success=True,
        deleted_count=1,
        message=f"Activity {activity_id} deleted successfully",
        memory_deleted=memory_deleted,
    )
