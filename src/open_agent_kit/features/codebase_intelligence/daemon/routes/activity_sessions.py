"""Activity session routes for lineage, linking, and session lifecycle.

This module provides API endpoints for:
- Session lineage (ancestors and children)
- Linking/unlinking sessions (parent-child relationships)
- Suggested parent sessions
- Session completion and summary regeneration
- Re-embedding session summaries
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
    ERROR_MSG_SESSION_NOT_FOUND,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    CompleteSessionResponse,
    DismissSuggestionResponse,
    LinkSessionRequest,
    LinkSessionResponse,
    ReembedSessionsResponse,
    RegenerateSummaryResponse,
    SessionLineageResponse,
    SuggestedParentResponse,
    UnlinkSessionResponse,
    UpdateSessionTitleRequest,
    UpdateSessionTitleResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
    session_to_lineage_item,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


@router.get(
    "/api/activity/sessions/{session_id}/lineage",
    response_model=SessionLineageResponse,
)
@handle_route_errors("get session lineage")
async def get_session_lineage(session_id: str) -> SessionLineageResponse:
    """Get the lineage (ancestors and children) of a session.

    Returns the ancestry chain (parent, grandparent, etc.) and direct children
    of the specified session. Useful for understanding session relationships
    created through clear/compact cycles or manual linking.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_child_sessions,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_session_lineage as store_get_lineage,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Getting lineage for session: {session_id}")

    # Get the session first to verify it exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Get ancestors (returns [self, parent, grandparent, ...])
    lineage = store_get_lineage(state.activity_store, session_id)

    # Get children
    children = get_child_sessions(state.activity_store, session_id)

    # Get first prompts for all sessions in lineage and children
    all_session_ids = [s.id for s in lineage] + [c.id for c in children]
    first_prompts_map = state.activity_store.get_bulk_first_prompts(all_session_ids)
    stats_map = state.activity_store.get_bulk_session_stats(all_session_ids)

    # Convert ancestors (skip self - first item)
    ancestor_items = []
    for ancestor in lineage[1:]:  # Skip self
        ancestor_items.append(
            session_to_lineage_item(
                ancestor,
                first_prompt_preview=first_prompts_map.get(ancestor.id),
                prompt_batch_count=stats_map.get(ancestor.id, {}).get("prompt_batch_count", 0),
            )
        )

    # Convert children
    child_items = [
        session_to_lineage_item(
            child,
            first_prompt_preview=first_prompts_map.get(child.id),
            prompt_batch_count=stats_map.get(child.id, {}).get("prompt_batch_count", 0),
        )
        for child in children
    ]

    return SessionLineageResponse(
        session_id=session_id,
        ancestors=ancestor_items,
        children=child_items,
    )


@router.post(
    "/api/activity/sessions/{session_id}/link",
    response_model=LinkSessionResponse,
)
@handle_route_errors("link session")
async def link_session(session_id: str, request: LinkSessionRequest) -> LinkSessionResponse:
    """Link a session to a parent session.

    Creates a parent-child relationship between sessions. This is useful for
    manually connecting related sessions that weren't automatically linked
    during clear/compact operations.

    Validates that:
    - Both sessions exist
    - The link would not create a cycle
    - The session doesn't already have this parent
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        update_session_parent,
        would_create_cycle,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Linking session {session_id} to parent {request.parent_session_id}")

    # Verify child session exists
    child_session = state.activity_store.get_session(session_id)
    if not child_session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Verify parent session exists
    parent_session = state.activity_store.get_session(request.parent_session_id)
    if not parent_session:
        raise HTTPException(status_code=404, detail="Parent session not found")

    # Check if already linked to this parent
    if child_session.parent_session_id == request.parent_session_id:
        return LinkSessionResponse(
            success=True,
            session_id=session_id,
            parent_session_id=request.parent_session_id,
            reason=request.reason,
            message="Session already linked to this parent",
        )

    # Check for cycles
    if would_create_cycle(state.activity_store, session_id, request.parent_session_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot link: would create a cycle in the session lineage",
        )

    # Create the link
    update_session_parent(
        state.activity_store,
        session_id,
        request.parent_session_id,
        request.reason,
    )

    return LinkSessionResponse(
        success=True,
        session_id=session_id,
        parent_session_id=request.parent_session_id,
        reason=request.reason,
        message="Session linked to parent successfully",
    )


@router.delete(
    "/api/activity/sessions/{session_id}/link",
    response_model=UnlinkSessionResponse,
)
@handle_route_errors("unlink session")
async def unlink_session(session_id: str) -> UnlinkSessionResponse:
    """Remove the parent link from a session.

    Clears the parent_session_id and parent_session_reason fields,
    making this session a root session in its lineage.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        clear_session_parent,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Unlinking session {session_id} from parent")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Check if already unlinked
    if not session.parent_session_id:
        return UnlinkSessionResponse(
            success=True,
            session_id=session_id,
            previous_parent_id=None,
            message="Session has no parent link to remove",
        )

    # Clear the link
    previous_parent = clear_session_parent(state.activity_store, session_id)

    return UnlinkSessionResponse(
        success=True,
        session_id=session_id,
        previous_parent_id=previous_parent,
        message="Session unlinked from parent successfully",
    )


@router.get(
    "/api/activity/sessions/{session_id}/suggested-parent",
    response_model=SuggestedParentResponse,
)
@handle_route_errors("get suggested parent")
async def get_suggested_parent(session_id: str) -> SuggestedParentResponse:
    """Get the suggested parent session for an unlinked session.

    Uses vector similarity search and optional LLM refinement to find
    the most likely parent session for manual linking.

    Returns suggestion info if found, or has_suggestion=False if:
    - Session already has a parent
    - Session has no summary for similarity search
    - No suitable candidate sessions found
    - Suggestion was previously dismissed
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.suggestions import (
        compute_suggested_parent,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.debug(f"Getting suggested parent for session: {session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Check if suggestion was dismissed
    dismissed = state.activity_store.is_suggestion_dismissed(session_id)

    if dismissed:
        return SuggestedParentResponse(
            session_id=session_id,
            has_suggestion=False,
            dismissed=True,
        )

    # Compute suggestion using vector similarity search
    # Note: LLM refinement is available but disabled for now - the cost/benefit
    # ratio isn't clear (5 LLM calls per suggestion). Can be re-enabled once
    # we have a smarter approach (e.g., single comparison call, background processing).
    suggestion = compute_suggested_parent(
        activity_store=state.activity_store,
        vector_store=state.vector_store,
        session_id=session_id,
        call_llm=None,  # Disabled - use vector-only scoring
    )

    if not suggestion:
        return SuggestedParentResponse(
            session_id=session_id,
            has_suggestion=False,
            dismissed=False,
        )

    # Get suggested parent session details
    suggested_session = state.activity_store.get_session(suggestion.session_id)
    if not suggested_session:
        return SuggestedParentResponse(
            session_id=session_id,
            has_suggestion=False,
            dismissed=False,
        )

    # Get first prompt preview for the suggested session
    first_prompts_map = state.activity_store.get_bulk_first_prompts([suggestion.session_id])
    stats_map = state.activity_store.get_bulk_session_stats([suggestion.session_id])

    suggested_item = session_to_lineage_item(
        suggested_session,
        first_prompt_preview=first_prompts_map.get(suggestion.session_id),
        prompt_batch_count=stats_map.get(suggestion.session_id, {}).get("prompt_batch_count", 0),
    )

    return SuggestedParentResponse(
        session_id=session_id,
        has_suggestion=True,
        suggested_parent=suggested_item,
        confidence=suggestion.confidence,
        confidence_score=suggestion.confidence_score,
        reason=suggestion.reason,
        dismissed=False,
    )


@router.post(
    "/api/activity/sessions/{session_id}/dismiss-suggestion",
    response_model=DismissSuggestionResponse,
)
@handle_route_errors("dismiss suggestion")
async def dismiss_suggestion(session_id: str) -> DismissSuggestionResponse:
    """Dismiss the suggestion for a session.

    Marks the session so that no suggestion will be shown until the user
    manually links or the dismissal is reset.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.suggestions import (
        dismiss_suggestion as store_dismiss_suggestion,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Dismissing suggestion for session: {session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    success = store_dismiss_suggestion(state.activity_store, session_id)

    if success:
        return DismissSuggestionResponse(
            success=True,
            session_id=session_id,
            message="Suggestion dismissed successfully",
        )
    else:
        return DismissSuggestionResponse(
            success=False,
            session_id=session_id,
            message="Failed to dismiss suggestion",
        )


@router.post(
    "/api/activity/reembed-sessions",
    response_model=ReembedSessionsResponse,
)
@handle_route_errors("reembed sessions")
async def reembed_sessions(
    background_tasks: BackgroundTasks,
) -> ReembedSessionsResponse:
    """Re-embed all session summaries to ChromaDB.

    Useful after:
    - Backup restore (sessions exist in SQLite but not in ChromaDB)
    - Embedding model changes
    - Index corruption

    Clears existing session summary embeddings and re-embeds from SQLite.
    Runs in background to avoid blocking the UI.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
        reembed_session_summaries,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    # Capture stores for the closure (already validated non-None above)
    activity_store = state.activity_store
    vector_store = state.vector_store

    # Count sessions to re-embed for the response
    total_sessions = activity_store.count_sessions_with_summaries()

    def _run_reembed() -> None:
        """Background task to re-embed session summaries."""
        try:
            sessions_processed, sessions_embedded = reembed_session_summaries(
                activity_store=activity_store,
                vector_store=vector_store,
                clear_first=True,
            )
            logger.info(
                f"Session summary re-embedding complete: "
                f"{sessions_embedded}/{sessions_processed} embedded"
            )
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Session summary re-embedding failed: {e}")

    logger.info(f"Starting session summary re-embedding in background ({total_sessions} sessions)")
    background_tasks.add_task(_run_reembed)

    return ReembedSessionsResponse(
        success=True,
        sessions_processed=total_sessions,
        sessions_embedded=0,  # Will be updated when complete
        message=f"Re-embedding {total_sessions} session summaries in background",
    )


@router.post(
    "/api/activity/sessions/{session_id}/complete",
    response_model=CompleteSessionResponse,
)
@handle_route_errors("complete session")
async def complete_session(session_id: str) -> CompleteSessionResponse:
    """Manually complete an active session.

    Triggers the same processing chain as the background auto-completion:
    1. Mark session as 'completed'
    2. Generate summary (if summarizer configured)
    3. Generate title (if missing)

    The session must be 'active' to be completed.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized",
        )

    logger.info(f"Manually completing session: {session_id}")

    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    previous_status = session.status

    try:
        summary, title = state.activity_processor.complete_session(session_id)
    except ValueError as e:
        return CompleteSessionResponse(
            success=False,
            session_id=session_id,
            previous_status=previous_status,
            message=str(e),
        )

    return CompleteSessionResponse(
        success=True,
        session_id=session_id,
        previous_status=previous_status,
        summary=summary,
        title=title,
        message="Session completed successfully",
    )


@router.post(
    "/api/activity/sessions/{session_id}/regenerate-summary",
    response_model=RegenerateSummaryResponse,
)
@handle_route_errors("regenerate session summary")
async def regenerate_session_summary(session_id: str) -> RegenerateSummaryResponse:
    """Regenerate the summary and title for a specific session.

    Triggers LLM-based summary generation for the session. The session must:
    - Exist
    - Have at least some activity (tool calls)

    Note: This will overwrite any existing summary and title for the session.
    The title is regenerated from the summary for better accuracy.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized - LLM summarization unavailable",
        )

    from open_agent_kit.features.codebase_intelligence.constants import (
        MIN_SESSION_ACTIVITIES,
    )

    logger.info(f"Regenerating summary and title for session: {session_id}")

    # Verify session exists
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Get session stats to check if it has enough data
    stats = state.activity_store.get_session_stats(session_id)
    activity_count = stats.get("activity_count", 0)

    if activity_count < MIN_SESSION_ACTIVITIES:
        return RegenerateSummaryResponse(
            success=False,
            session_id=session_id,
            summary=None,
            title=None,
            message=f"Insufficient data: session has only {activity_count} activities (minimum {MIN_SESSION_ACTIVITIES} required)",
        )

    # Generate the summary and title (force regenerate both)
    summary, title = state.activity_processor.process_session_summary_with_title(
        session_id, regenerate_title=True
    )

    if summary:
        logger.info(f"Regenerated summary and title for session {session_id[:8]}")
        return RegenerateSummaryResponse(
            success=True,
            session_id=session_id,
            summary=summary,
            title=title,
            message="Summary and title regenerated successfully",
        )
    else:
        return RegenerateSummaryResponse(
            success=False,
            session_id=session_id,
            summary=None,
            title=None,
            message="Failed to generate summary - check logs for details",
        )


@router.patch(
    "/api/activity/sessions/{session_id}/title",
    response_model=UpdateSessionTitleResponse,
)
@handle_route_errors("update session title")
async def update_session_title(
    session_id: str, request: UpdateSessionTitleRequest
) -> UpdateSessionTitleResponse:
    """Update a session's title and mark it as manually edited.

    Manually edited titles are protected from being overwritten by
    LLM-generated titles during background processing.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    title = request.title.strip()
    state.activity_store.update_session_title(session_id, title, manually_edited=True)

    logger.info(f"Manually updated title for session {session_id[:8]}: {title[:50]}")

    return UpdateSessionTitleResponse(
        success=True,
        session_id=session_id,
        title=title,
        message="Title updated successfully",
    )
