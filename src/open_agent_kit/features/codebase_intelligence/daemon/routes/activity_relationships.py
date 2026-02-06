"""Activity relationship routes for many-to-many session links.

This module provides API endpoints for managing semantic relationships
between sessions (complementing the parent-child lineage model):
- List related sessions
- Add/remove related session relationships
- Get suggested related sessions via vector similarity
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
    ERROR_MSG_SESSION_NOT_FOUND,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    AddRelatedRequest,
    AddRelatedResponse,
    RelatedSessionItem,
    RelatedSessionsResponse,
    RemoveRelatedResponse,
    SuggestedRelatedItem,
    SuggestedRelatedResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


@router.get(
    "/api/activity/sessions/{session_id}/related",
    response_model=RelatedSessionsResponse,
)
@handle_route_errors("get related sessions")
async def get_related_sessions(session_id: str) -> RelatedSessionsResponse:
    """Get sessions related to a given session.

    Returns sessions with many-to-many semantic relationships, which
    complement the parent-child model designed for temporal continuity.
    Related sessions can span any time gap.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.relationships import (
        get_related_sessions as store_get_related,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Getting related sessions for: {session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Get related sessions
    related = store_get_related(state.activity_store, session_id)

    # Get session details for each related session
    related_session_ids = [rel_id for rel_id, _ in related]
    first_prompts_map = state.activity_store.get_bulk_first_prompts(related_session_ids)
    stats_map = state.activity_store.get_bulk_session_stats(related_session_ids)

    related_items: list[RelatedSessionItem] = []
    for related_session_id, relationship in related:
        related_session = state.activity_store.get_session(related_session_id)
        if not related_session:
            continue

        related_items.append(
            RelatedSessionItem(
                id=related_session.id,
                title=related_session.title,
                first_prompt_preview=first_prompts_map.get(related_session_id),
                started_at=related_session.started_at,
                ended_at=related_session.ended_at,
                status=related_session.status,
                prompt_batch_count=stats_map.get(related_session_id, {}).get(
                    "prompt_batch_count", 0
                ),
                relationship_id=relationship.id,
                similarity_score=relationship.similarity_score,
                created_by=relationship.created_by,
                related_at=relationship.created_at,
            )
        )

    return RelatedSessionsResponse(
        session_id=session_id,
        related=related_items,
    )


@router.post(
    "/api/activity/sessions/{session_id}/related",
    response_model=AddRelatedResponse,
)
@handle_route_errors("add related session")
async def add_related_session(session_id: str, request: AddRelatedRequest) -> AddRelatedResponse:
    """Add a related session relationship.

    Creates a many-to-many semantic relationship between two sessions.
    Relationships are bidirectional: if A is related to B, B is related to A.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.relationships import (
        add_relationship,
    )
    from open_agent_kit.features.codebase_intelligence.constants import (
        RELATIONSHIP_CREATED_BY_MANUAL,
        RELATIONSHIP_CREATED_BY_SUGGESTION,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Adding related session: {session_id} <-> {request.related_session_id}")

    # Verify both sessions exist
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    related_session = state.activity_store.get_session(request.related_session_id)
    if not related_session:
        raise HTTPException(status_code=404, detail="Related session not found")

    # Determine created_by based on whether similarity_score is provided
    created_by = (
        RELATIONSHIP_CREATED_BY_SUGGESTION
        if request.similarity_score is not None
        else RELATIONSHIP_CREATED_BY_MANUAL
    )

    # Add the relationship
    relationship = add_relationship(
        store=state.activity_store,
        session_a_id=session_id,
        session_b_id=request.related_session_id,
        similarity_score=request.similarity_score,
        created_by=created_by,
    )

    if relationship:
        return AddRelatedResponse(
            success=True,
            session_id=session_id,
            related_session_id=request.related_session_id,
            relationship_id=relationship.id,
            message="Related session added successfully",
        )
    else:
        return AddRelatedResponse(
            success=False,
            session_id=session_id,
            related_session_id=request.related_session_id,
            message="Failed to add relationship (may already exist)",
        )


@router.delete(
    "/api/activity/sessions/{session_id}/related/{related_session_id}",
    response_model=RemoveRelatedResponse,
)
@handle_route_errors("remove related session")
async def remove_related_session(session_id: str, related_session_id: str) -> RemoveRelatedResponse:
    """Remove a related session relationship.

    Removes the many-to-many relationship between two sessions.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.relationships import (
        remove_relationship,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Removing related session: {session_id} <-> {related_session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Remove the relationship
    removed = remove_relationship(
        store=state.activity_store,
        session_a_id=session_id,
        session_b_id=related_session_id,
    )

    if removed:
        return RemoveRelatedResponse(
            success=True,
            session_id=session_id,
            related_session_id=related_session_id,
            message="Related session removed successfully",
        )
    else:
        return RemoveRelatedResponse(
            success=False,
            session_id=session_id,
            related_session_id=related_session_id,
            message="Relationship not found",
        )


@router.get(
    "/api/activity/sessions/{session_id}/suggested-related",
    response_model=SuggestedRelatedResponse,
)
@handle_route_errors("get suggested related sessions")
async def get_suggested_related(session_id: str) -> SuggestedRelatedResponse:
    """Get suggested related sessions based on semantic similarity.

    Uses vector similarity search with an extended age limit (365 days)
    to find sessions that worked on similar topics, regardless of time gap.
    Excludes sessions already in the parent-child lineage and existing
    related sessions.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.suggestions import (
        compute_related_sessions,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.debug(f"Getting suggested related sessions for: {session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Compute suggestions
    suggestions = compute_related_sessions(
        activity_store=state.activity_store,
        vector_store=state.vector_store,
        session_id=session_id,
        limit=5,
        exclude_lineage=True,
        exclude_existing_related=True,
    )

    # Get session details for suggestions
    suggestion_ids = [s.session_id for s in suggestions]
    first_prompts_map = state.activity_store.get_bulk_first_prompts(suggestion_ids)
    stats_map = state.activity_store.get_bulk_session_stats(suggestion_ids)

    suggestion_items: list[SuggestedRelatedItem] = []
    for suggestion in suggestions:
        suggested_session = state.activity_store.get_session(suggestion.session_id)
        if not suggested_session:
            continue

        suggestion_items.append(
            SuggestedRelatedItem(
                id=suggested_session.id,
                title=suggested_session.title,
                first_prompt_preview=first_prompts_map.get(suggestion.session_id),
                started_at=suggested_session.started_at,
                ended_at=suggested_session.ended_at,
                status=suggested_session.status,
                prompt_batch_count=stats_map.get(suggestion.session_id, {}).get(
                    "prompt_batch_count", 0
                ),
                confidence=suggestion.confidence,
                confidence_score=suggestion.confidence_score,
                reason=suggestion.reason,
            )
        )

    return SuggestedRelatedResponse(
        session_id=session_id,
        suggestions=suggestion_items,
    )
