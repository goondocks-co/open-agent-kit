"""Prompt batch finalization helpers for Codebase Intelligence."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from open_agent_kit.features.codebase_intelligence.activity.processor import (
    ActivityProcessor,
    process_prompt_batch_async,
)
from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

logger = logging.getLogger(__name__)


def finalize_prompt_batch(
    activity_store: ActivityStore,
    activity_processor: ActivityProcessor | None,
    prompt_batch_id: int,
    response_summary: str | None = None,
) -> dict[str, Any]:
    """Finalize a prompt batch and optionally capture a response summary."""
    response_captured = False

    if response_summary:
        try:
            activity_store.update_prompt_batch_response(prompt_batch_id, response_summary)
            response_captured = True
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(
                "Failed to store response summary for batch %s: %s",
                prompt_batch_id,
                e,
            )

    try:
        activity_store.end_prompt_batch(prompt_batch_id)
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning("Failed to end prompt batch %s: %s", prompt_batch_id, e)

    stats = activity_store.get_prompt_batch_stats(prompt_batch_id)

    processing_scheduled = False
    if activity_processor:
        processor = activity_processor
        batch_id = prompt_batch_id

        async def _process_batch() -> None:
            logger.debug(f"[REALTIME] Starting async processing for batch {batch_id}")
            try:
                result = await process_prompt_batch_async(processor, batch_id)
                if result.success:
                    logger.info(
                        f"[REALTIME] Prompt batch {batch_id} processed: "
                        f"{result.observations_extracted} observations from "
                        f"{result.activities_processed} activities "
                        f"(type={result.classification})"
                    )
                else:
                    logger.warning(f"[REALTIME] Prompt batch processing failed: {result.error}")
            except (RuntimeError, OSError, ValueError) as e:
                logger.warning(f"[REALTIME] Prompt batch processing error: {e}")

        logger.debug(f"[REALTIME] Scheduling async task for batch {batch_id}")
        asyncio.create_task(_process_batch())
        processing_scheduled = True

    result: dict[str, Any] = {
        "prompt_batch_id": prompt_batch_id,
        "prompt_batch_stats": stats,
    }
    if response_captured:
        result["response_captured"] = True
    if processing_scheduled:
        result["processing_scheduled"] = True

    return result
