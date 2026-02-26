"""Activity processing routes (reprocess memories, promote batches).

This module provides API endpoints for:
- Reprocessing prompt batches to regenerate memories
- Promoting agent batches to extract memories via LLM

Split from ``activity.py`` to keep route files under 500 lines.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


@router.post("/api/activity/reprocess-memories")
@handle_route_errors("reprocess memories")
async def reprocess_memories(
    batch_ids: list[int] | None = None,
    recover_stuck: bool = True,
    process_immediately: bool = False,
) -> dict:
    """Reprocess prompt batches to regenerate memories.

    This is a comprehensive reprocessing endpoint that handles all batch states:
    1. Recovers stuck batches (still in 'active' status)
    2. Resets 'processed' flag on completed batches
    3. Optionally triggers immediate processing instead of waiting for background cycle

    Args:
        batch_ids: Optional list of specific batch IDs to reprocess.
                  If not provided, all batches are eligible for reprocessing.
        recover_stuck: If True, also marks stuck 'active' batches as 'completed'.
        process_immediately: If True, triggers processing now instead of waiting.

    Returns:
        Dictionary with counts of batches recovered and queued for reprocessing.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    # Use typed local variables to avoid mypy issues with dict value types
    batches_recovered = 0
    batches_queued = 0
    batches_processed = 0
    observations_created = 0
    message = ""

    # Steps 1-2: Recover stuck batches and queue for reprocessing
    batches_recovered, batches_queued = state.activity_store.queue_batches_for_reprocessing(
        batch_ids=batch_ids,
        recover_stuck=recover_stuck,
    )

    # Step 3: Optionally trigger immediate processing
    if process_immediately and state.activity_processor:
        logger.info("Triggering immediate processing...")
        process_results = state.activity_processor.process_pending_batches(max_batches=100)
        batches_processed = len(process_results)
        observations_created = sum(r.observations_extracted for r in process_results)
        logger.info(
            f"Immediate processing: {batches_processed} batches → "
            f"{observations_created} observations"
        )

    # Build message
    parts = []
    if batches_recovered > 0:
        parts.append(f"recovered {batches_recovered} stuck batches")
    if batches_queued > 0:
        parts.append(f"queued {batches_queued} batches")
    if batches_processed > 0:
        parts.append(f"processed {batches_processed} batches → {observations_created} observations")

    if parts:
        message = f"Reprocessing: {', '.join(parts)}."
    else:
        message = "No batches needed reprocessing."

    if not process_immediately and batches_queued > 0:
        message += f" Memories will be regenerated in the next processing cycle ({DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS}s)."

    return {
        "success": True,
        "batches_recovered": batches_recovered,
        "batches_queued": batches_queued,
        "batches_processed": batches_processed,
        "observations_created": observations_created,
        "message": message,
    }


@router.post("/api/activity/prompt-batches/{batch_id}/promote")
@handle_route_errors("promote batch")
async def promote_batch_to_memory(batch_id: int) -> dict:
    """Promote an agent batch to extract memories using LLM.

    This endpoint allows manual promotion of background agent findings to the
    memory store. Agent batches (source_type='agent_notification') are normally
    skipped during memory extraction to prevent pollution. This endpoint forces
    user-style LLM extraction on those batches.

    Use this when a background agent discovered something valuable that should
    be preserved in the memory store for future sessions.

    Args:
        batch_id: The prompt batch ID to promote.

    Returns:
        Dictionary with promotion results including observation count.

    Raises:
        HTTPException: If batch not found, not promotable, or processing fails.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor import (
        promote_agent_batch_async,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized - LLM extraction unavailable",
        )

    logger.info(f"Promoting agent batch to memory: {batch_id}")

    # Check batch exists
    batch = state.activity_store.get_prompt_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Prompt batch not found")

    # Promote using async wrapper
    result = await promote_agent_batch_async(state.activity_processor, batch_id)

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or "Failed to promote batch",
        )

    return {
        "success": True,
        "batch_id": batch_id,
        "observations_extracted": result.observations_extracted,
        "activities_processed": result.activities_processed,
        "classification": result.classification,
        "duration_ms": result.duration_ms,
        "message": f"Promoted batch {batch_id}: {result.observations_extracted} observations extracted",
    }
