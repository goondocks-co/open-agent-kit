"""SQLite-to-ChromaDB consistency checks and background rebuild tasks.

Extracted from ``server.py`` -- handles detection of mismatches between
SQLite (source of truth) and ChromaDB (search index) and schedules
background rebuilds without blocking daemon startup.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def _run_chromadb_rebuild_sync(
    activity_processor: "ActivityProcessor",
    rebuild_type: str,
    count: int,
) -> None:
    """Run ChromaDB rebuild synchronously (for use in background thread).

    Args:
        activity_processor: The activity processor instance.
        rebuild_type: Either "full" or "pending" to indicate rebuild type.
        count: Number of observations to process (for logging).
    """
    try:
        if rebuild_type == "full":
            logger.info(f"Background ChromaDB rebuild started ({count} observations)...")
            stats = activity_processor.rebuild_chromadb_from_sqlite()
            logger.info(
                f"Background ChromaDB rebuild complete: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )
        else:
            logger.info(f"Background embedding started ({count} observations)...")
            stats = activity_processor.embed_pending_observations()
            logger.info(
                f"Background embedding complete: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Background ChromaDB operation failed: {e}")


def _run_session_summary_rebuild_sync(state: "DaemonState") -> None:
    """Rebuild session summary embeddings from SQLite (for use in background thread)."""
    from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
        reembed_session_summaries,
    )

    if not state.activity_store or not state.vector_store:
        return
    try:
        processed, embedded = reembed_session_summaries(
            state.activity_store,
            state.vector_store,
        )
        logger.info(
            f"Background session summary rebuild complete: " f"{embedded}/{processed} embedded"
        )
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Background session summary rebuild failed: {e}")


def _run_plan_index_rebuild_sync(state: "DaemonState") -> None:
    """Rebuild plan index from SQLite (for use in background thread)."""
    from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
        rebuild_plan_index,
    )

    if not state.activity_store or not state.vector_store:
        return
    try:
        stats = rebuild_plan_index(
            state.activity_store,
            state.vector_store,
            batch_size=50,
        )
        logger.info(
            f"Background plan index rebuild complete: " f"{stats.get('indexed', 0)} indexed"
        )
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Background plan index rebuild failed: {e}")


async def check_and_rebuild_chromadb(state: "DaemonState") -> None:
    """Check for SQLite/ChromaDB mismatch and schedule rebuild if needed.

    SQLite is the source of truth for memory observations. If ChromaDB
    is empty or was wiped but SQLite has observations, this schedules
    a background rebuild to restore the search index.

    IMPORTANT: This function does NOT block startup. Rebuilds run in
    a background thread so the daemon can start accepting requests
    immediately. The health endpoint reports rebuild status.

    This handles the case where:
    - ChromaDB was deleted/corrupted
    - Embedding dimensions changed requiring full re-index
    - Fresh ChromaDB but existing SQLite data

    Args:
        state: Daemon state with activity_store, vector_store, and activity_processor.
    """
    if not state.activity_store or not state.vector_store or not state.activity_processor:
        return

    try:
        # Count observations in SQLite (source of truth)
        sqlite_count = state.activity_store.count_observations()

        # Count memories in ChromaDB
        try:
            chromadb_count = state.vector_store.count_memories()
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Could not count ChromaDB memories: {e}")
            chromadb_count = 0

        # Check for mismatch
        unembedded_count = state.activity_store.count_unembedded_observations()

        logger.info(
            f"Memory sync check: SQLite={sqlite_count}, ChromaDB={chromadb_count}, "
            f"unembedded={unembedded_count}"
        )

        loop = asyncio.get_event_loop()

        # If ChromaDB is empty but SQLite has data, schedule background rebuild
        if chromadb_count == 0 and sqlite_count > 0:
            logger.warning(
                f"ChromaDB is empty but SQLite has {sqlite_count} observations. "
                "Scheduling background rebuild (startup will continue)..."
            )
            loop.run_in_executor(
                None,
                _run_chromadb_rebuild_sync,
                state.activity_processor,
                "full",
                sqlite_count,
            )
        # If there are unembedded observations, schedule background embedding
        elif unembedded_count > 0:
            logger.info(
                f"Found {unembedded_count} unembedded observations. "
                "Scheduling background embedding (startup will continue)..."
            )
            loop.run_in_executor(
                None,
                _run_chromadb_rebuild_sync,
                state.activity_processor,
                "pending",
                unembedded_count,
            )

        # --- Session summaries rebuild ---
        # If SQLite has session summaries but ChromaDB doesn't, rebuild them.
        try:
            sqlite_sessions_with_summaries = state.activity_store.count_sessions_with_summaries()
            chromadb_session_count = state.vector_store.count_session_summaries()

            if sqlite_sessions_with_summaries > 0 and chromadb_session_count == 0:
                logger.warning(
                    f"ChromaDB has no session summaries but SQLite has "
                    f"{sqlite_sessions_with_summaries}. Scheduling background rebuild..."
                )
                loop.run_in_executor(None, _run_session_summary_rebuild_sync, state)
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Session summary sync check failed: {e}")

        # --- Plans rebuild ---
        # Cross-reference actual ChromaDB plan count vs SQLite to detect
        # mismatches caused by collection recreation (e.g. dimension mismatch)
        # that doesn't reset SQLite plan_embedded flags.
        try:
            sqlite_embedded_plans = state.activity_store.count_embedded_plans()
            chromadb_plan_count = state.vector_store.count_plans()

            if sqlite_embedded_plans > 0 and chromadb_plan_count == 0:
                # SQLite thinks plans are embedded but ChromaDB has none
                logger.warning(
                    f"SQLite has {sqlite_embedded_plans} plans marked embedded "
                    "but ChromaDB has 0. Scheduling plan rebuild..."
                )
                loop.run_in_executor(None, _run_plan_index_rebuild_sync, state)
            elif sqlite_embedded_plans > 0 and chromadb_plan_count < sqlite_embedded_plans // 2:
                # ChromaDB has significantly fewer plans than SQLite claims --
                # likely a partial collection loss (e.g. recreated mid-session)
                logger.warning(
                    f"Plan count mismatch: SQLite has {sqlite_embedded_plans} embedded "
                    f"but ChromaDB only has {chromadb_plan_count}. Scheduling plan rebuild..."
                )
                loop.run_in_executor(None, _run_plan_index_rebuild_sync, state)
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Plan sync check failed: {e}")

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Error during ChromaDB sync check: {e}")
