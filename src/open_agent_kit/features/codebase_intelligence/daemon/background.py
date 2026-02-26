"""Background indexing and file-watching tasks.

Extracted from ``server.py`` so that ``routes/config.py`` can import
``_background_index`` and ``_start_file_watcher`` without creating a
circular dependency through the server module.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_INDEXING_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def _background_index() -> None:
    """Run initial indexing in background."""
    state = get_state()

    if not state.indexer or not state.vector_store:
        logger.warning("Cannot start background indexing - components not initialized")
        return

    # Check if index already has data
    stats = state.vector_store.get_stats()
    if stats.get("code_chunks", 0) > 0:
        logger.info(f"Index already has {stats['code_chunks']} chunks, skipping initial index")
        state.index_status.set_ready()
        state.index_status.file_count = state.vector_store.count_unique_files()
        # Still start file watcher for incremental updates
        await _start_file_watcher()
        return

    logger.info("Starting background indexing...")

    # Set indexing status BEFORE running in executor to eliminate race condition
    # where UI polls between task scheduling and executor start
    state.index_status.set_indexing()

    try:
        # Run unified index build in executor with timeout
        # Pass _status_preset=True since we already set is_indexing above
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: state.run_index_build(full_rebuild=True, _status_preset=True),
            ),
            timeout=DEFAULT_INDEXING_TIMEOUT_SECONDS,
        )

        if result is not None:
            # Start file watcher for incremental updates
            await _start_file_watcher()

    except TimeoutError:
        logger.error(f"Background indexing timed out after {DEFAULT_INDEXING_TIMEOUT_SECONDS}s")
        state.index_status.set_error()
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Background indexing failed: {e}")
        state.index_status.set_error()
    finally:
        # Only update file count from DB if it wasn't set by successful indexing
        # This prevents overwriting the accurate count from run_index_build() result
        if state.index_status.file_count == 0 and state.vector_store:
            try:
                state.index_status.file_count = state.vector_store.count_unique_files()
            except (OSError, AttributeError, RuntimeError) as e:
                logger.warning(f"Failed to update file count: {e}")


async def _start_file_watcher() -> None:
    """Start file watcher for real-time incremental updates."""
    state = get_state()

    if state.file_watcher is not None:
        return  # Already running

    if not state.indexer or not state.project_root:
        logger.warning("Cannot start file watcher - indexer not initialized")
        return

    try:
        from open_agent_kit.features.codebase_intelligence.indexing.watcher import (
            FileWatcher,
        )

        def on_index_start() -> None:
            state.index_status.set_updating()

        def on_index_complete(chunks: int) -> None:
            state.index_status.set_ready()

        watcher = FileWatcher(
            project_root=state.project_root,
            indexer=state.indexer,
            on_index_start=on_index_start,
            on_index_complete=on_index_complete,
        )

        # Start in thread pool
        loop = asyncio.get_event_loop()
        started = await loop.run_in_executor(None, watcher.start)

        if started:
            state.file_watcher = watcher
            logger.info("File watcher started for real-time index updates")
        else:
            logger.warning("File watcher could not be started (watchdog not installed?)")

    except (OSError, ImportError, RuntimeError) as e:
        logger.warning(f"Failed to start file watcher: {e}")
