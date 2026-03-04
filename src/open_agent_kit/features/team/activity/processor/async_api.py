"""Async wrappers for ActivityProcessor methods.

Used by FastAPI routes to run synchronous processor methods in a thread pool
without blocking the event loop.
"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.team.activity.processor.models import (
        ProcessingResult,
    )


async def process_session_async(
    processor: "ActivityProcessor",
    session_id: str,
) -> "ProcessingResult":
    """Process a session asynchronously.

    Args:
        processor: Activity processor instance.
        session_id: Session to process.

    Returns:
        ProcessingResult.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.process_session, session_id)


async def process_prompt_batch_async(
    processor: "ActivityProcessor",
    batch_id: int,
) -> "ProcessingResult":
    """Process a prompt batch asynchronously.

    This is the preferred processing method - processes activities from a
    single user prompt as one coherent unit.

    Args:
        processor: Activity processor instance.
        batch_id: Prompt batch ID to process.

    Returns:
        ProcessingResult.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.process_prompt_batch, batch_id)


async def promote_agent_batch_async(
    processor: "ActivityProcessor",
    batch_id: int,
) -> "ProcessingResult":
    """Promote an agent batch to extract memories asynchronously.

    This forces user-style LLM extraction on batches that were previously
    skipped (agent_notification, system). Useful for promoting valuable
    findings from background agent work.

    Args:
        processor: Activity processor instance.
        batch_id: Prompt batch ID to promote.

    Returns:
        ProcessingResult with extracted observations.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.promote_agent_batch, batch_id)
