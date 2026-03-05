"""Plan-related activity routes.

This module provides API endpoints for:
- Listing plans (design documents from plan mode)
- Refreshing plan content from source files on disk

Split from ``activity.py`` to keep route files under 500 lines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.team.constants import (
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
    PAGINATION_DEFAULT_LIMIT,
    PAGINATION_DEFAULT_OFFSET,
    PAGINATION_MIN_LIMIT,
    PAGINATION_SESSIONS_MAX,
)
from open_agent_kit.features.team.daemon.models import (
    PlanListItem,
    PlansListResponse,
    RefreshPlanResponse,
)
from open_agent_kit.features.team.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.team.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store import (
        PromptBatch,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


def _extract_plan_title(batch: PromptBatch) -> str:
    """Extract a title from a plan batch.

    Tries in order:
    1. First markdown heading (# Title) from plan_content
    2. Filename from plan_file_path
    3. Fallback to "Plan #{batch_id}"
    """
    import re

    # Try to extract first heading from plan_content
    if batch.plan_content:
        # Match first markdown heading (# or ##)
        heading_match = re.search(r"^#+ +(.+)$", batch.plan_content, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

    # Try filename from plan_file_path
    if batch.plan_file_path:
        from pathlib import Path

        filename = Path(batch.plan_file_path).stem
        # Convert kebab-case or snake_case to title case
        title = filename.replace("-", " ").replace("_", " ").title()
        return title

    # Fallback
    return f"Plan #{batch.id}" if batch.id else "Untitled Plan"


def _plan_to_item(batch: PromptBatch) -> PlanListItem:
    """Convert a plan PromptBatch to PlanListItem."""
    # Get preview from plan_content (first 200 chars, skip heading)
    preview = ""
    if batch.plan_content:
        import re

        # Remove first heading line and get next 200 chars
        content = re.sub(r"^#+ +.+\n*", "", batch.plan_content, count=1).strip()
        preview = content[:200]
        if len(content) > 200:
            preview += "..."

    return PlanListItem(
        id=batch.id if batch.id is not None else 0,
        title=_extract_plan_title(batch),
        session_id=batch.session_id,
        created_at=batch.started_at,
        file_path=batch.plan_file_path,
        preview=preview,
        plan_embedded=batch.plan_embedded,
    )


@router.get("/api/activity/plans", response_model=PlansListResponse)
@handle_route_errors("list plans")
async def list_plans(
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_SESSIONS_MAX
    ),
    offset: int = Query(default=PAGINATION_DEFAULT_OFFSET, ge=0),
    session_id: str | None = Query(default=None, description="Filter by session"),
    sort: str = Query(
        default="created",
        description="Sort order: created (newest first, default) or created_asc (oldest first)",
    ),
) -> PlansListResponse:
    """List plans from prompt_batches (direct SQLite, not ChromaDB).

    Plans are prompt batches with source_type='plan' that contain design documents
    created during plan mode sessions.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(
        f"Listing plans: limit={limit}, offset={offset}, session_id={session_id}, sort={sort}"
    )

    plans, total = state.activity_store.get_plans(
        limit=limit,
        offset=offset,
        session_id=session_id,
        sort=sort,
    )

    items = [_plan_to_item(batch) for batch in plans]

    return PlansListResponse(
        plans=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/api/activity/plans/{batch_id}/refresh", response_model=RefreshPlanResponse)
@handle_route_errors("refresh plan")
async def refresh_plan_from_source(
    batch_id: int,
    graceful: bool = Query(default=False),
) -> RefreshPlanResponse:
    """Re-read plan content from source file on disk.

    This is useful when a plan file has been edited outside of the normal
    plan mode workflow (e.g., manual edits) and you want to update the
    stored content in the CI database.

    Also marks the plan as unembedded so it will be re-indexed.

    Args:
        batch_id: The prompt batch ID containing the plan.
        graceful: When True, return success=False instead of HTTP errors for
            expected conditions (file not found, no file path). Useful for
            automatic background refreshes where the plan file may not exist
            on the current machine.

    Returns:
        RefreshPlanResponse with updated content length.

    Raises:
        HTTPException: If batch not found, has no plan file, or file not found
            (only when graceful=False).
    """
    from pathlib import Path

    from open_agent_kit.features.team.constants import PROMPT_SOURCE_PLAN

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Refreshing plan from disk: batch_id={batch_id} graceful={graceful}")

    # Get the batch
    batch = state.activity_store.get_prompt_batch(batch_id)
    if not batch:
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message="Plan batch not found",
            )
        raise HTTPException(status_code=404, detail="Plan batch not found")

    # Verify it's a plan with a file path
    if batch.source_type != "plan":
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message=f"Batch {batch_id} is not a plan (source_type={batch.source_type})",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Batch {batch_id} is not a plan (source_type={batch.source_type})",
        )

    if not batch.plan_file_path:
        # Discover plan file using centralized resolver.
        # Tries: candidate paths -> transcript -> filesystem scan.
        from open_agent_kit.features.team.plan_detector import (
            resolve_plan_content,
        )

        # Gather candidate paths from batch activities
        candidate_paths: list[str] = []
        try:
            activities = state.activity_store.get_prompt_batch_activities(batch_id, limit=50)
            for act in activities:
                if act.tool_name in ("Read", "Edit", "Write") and act.file_path:
                    candidate_paths.append(act.file_path)
        except Exception as e:
            logger.warning(f"Failed to gather candidate paths from activities: {e}")

        # Resolve transcript_path via transcript resolver
        transcript_path: str | None = None
        if batch.session_id:
            try:
                from open_agent_kit.features.team.transcript_resolver import (
                    get_transcript_resolver,
                )

                session = state.activity_store.get_session(batch.session_id)
                if session and session.project_root:
                    resolver = get_transcript_resolver(Path(session.project_root))
                    transcript_result = resolver.resolve(
                        session_id=batch.session_id,
                        agent_type=(session.agent if session.agent != "unknown" else None),
                        project_root=session.project_root,
                    )
                    if transcript_result.path:
                        transcript_path = str(transcript_result.path)
            except Exception as e:
                logger.warning(f"Failed to resolve transcript_path: {e}")

        resolution = resolve_plan_content(
            candidate_paths=candidate_paths or None,
            transcript_path=transcript_path,
            max_age_seconds=86400,  # Generous window for retroactive refresh
            project_root=state.project_root,
        )

        if resolution:
            state.activity_store.update_prompt_batch_source_type(
                batch_id,
                PROMPT_SOURCE_PLAN,
                plan_file_path=resolution.file_path,
                plan_content=resolution.content,
            )
            state.activity_store.mark_plan_unembedded(batch_id)

            logger.info(
                f"Discovered plan via {resolution.strategy}: "
                f"{resolution.file_path} -> batch {batch_id} "
                f"({len(resolution.content)} chars)"
            )

            return RefreshPlanResponse(
                success=True,
                batch_id=batch_id,
                plan_file_path=resolution.file_path,
                content_length=len(resolution.content),
                message=(
                    f"Discovered plan via {resolution.strategy} "
                    f"and refreshed ({len(resolution.content)} chars)"
                ),
            )

        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message="No file path - content may be embedded in prompt",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Plan batch {batch_id} has no file path - content may be embedded in prompt",
        )

    # Resolve the file path
    plan_path = Path(batch.plan_file_path)
    if not plan_path.is_absolute() and state.project_root:
        plan_path = state.project_root / plan_path

    if not plan_path.exists():
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                plan_file_path=batch.plan_file_path,
                message=f"Plan file not found on disk: {batch.plan_file_path}",
            )
        raise HTTPException(
            status_code=404,
            detail=f"Plan file not found: {batch.plan_file_path}",
        )

    # Read fresh content from disk
    final_content = plan_path.read_text(encoding="utf-8")

    # Update the batch with fresh content
    state.activity_store.update_prompt_batch_source_type(
        batch_id,
        PROMPT_SOURCE_PLAN,
        plan_file_path=batch.plan_file_path,
        plan_content=final_content,
    )

    # Mark as unembedded for re-indexing
    state.activity_store.mark_plan_unembedded(batch_id)

    logger.info(
        f"Refreshed plan batch {batch_id} from {batch.plan_file_path} ({len(final_content)} chars)"
    )

    return RefreshPlanResponse(
        success=True,
        batch_id=batch_id,
        plan_file_path=batch.plan_file_path,
        content_length=len(final_content),
        message=f"Plan refreshed from disk ({len(final_content)} chars)",
    )
