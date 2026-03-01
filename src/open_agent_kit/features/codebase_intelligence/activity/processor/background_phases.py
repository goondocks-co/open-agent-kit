"""Background processing phases for the ActivityProcessor.

Each phase has its own error boundary so a failure in one phase does not
skip subsequent phases.  This decomposition also makes each phase
independently testable.

All functions take the processor instance as their first argument to
access stores, config, and helper methods.
"""

import logging
import sqlite3
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    INJECTION_MAX_SESSION_SUMMARIES,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
        ActivityProcessor,
    )

logger = logging.getLogger(__name__)

# Exception types caught by background processing phases.
# Each phase has its own error boundary so failures are isolated --
# a bug in one phase must not crash the entire processor loop.
# TypeError/KeyError/AttributeError are intentionally included:
# while they often indicate programming errors, in this context
# phase isolation is more important than fail-fast behavior.
# All caught exceptions are logged with exc_info=True for debugging.
_BG_EXCEPTIONS = (
    OSError,
    sqlite3.OperationalError,
    sqlite3.IntegrityError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


def bg_cleanup_pollution(processor: "ActivityProcessor") -> None:
    """Phase 0: One-time cross-machine pollution cleanup.

    Runs only on the first background cycle. Removes observations that
    were created by the local processor but reference sessions from
    another machine (a violation of the machine isolation invariant).
    """
    if processor._pollution_cleanup_done:
        return

    try:
        counts = processor.activity_store.cleanup_cross_machine_pollution(
            vector_store=processor.vector_store,
        )
        if counts["observations_deleted"] > 0:
            logger.info(
                "Cross-machine pollution cleanup: %d observations removed",
                counts["observations_deleted"],
            )
    except _BG_EXCEPTIONS as e:
        logger.error(f"Cross-machine pollution cleanup error: {e}", exc_info=True)
    finally:
        processor._pollution_cleanup_done = True


def bg_recover_stuck_data(processor: "ActivityProcessor") -> None:
    """Phase 1: Recover stuck batches, stale runs, and orphaned activities."""
    try:
        from open_agent_kit.features.codebase_intelligence.constants import (
            BATCH_ACTIVE_TIMEOUT_SECONDS,
        )

        # Auto-end batches stuck in 'active' too long
        stuck_count = processor.activity_store.recover_stuck_batches(
            timeout_seconds=BATCH_ACTIVE_TIMEOUT_SECONDS,
            project_root=processor.project_root,
        )
        if stuck_count:
            logger.info(f"Recovered {stuck_count} stuck batches")

        # Mark stale agent runs as failed
        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_RUN_RECOVERY_BUFFER_SECONDS,
            DEFAULT_AGENT_TIMEOUT_SECONDS,
        )

        stale_run_ids = processor.activity_store.recover_stale_runs(
            buffer_seconds=AGENT_RUN_RECOVERY_BUFFER_SECONDS,
            default_timeout_seconds=DEFAULT_AGENT_TIMEOUT_SECONDS,
        )
        if stale_run_ids:
            logger.info(
                f"Recovered {len(stale_run_ids)} stale agent runs: "
                f"{[r[:8] for r in stale_run_ids]}"
            )

        # Associate orphaned activities with batches
        orphan_count = processor.activity_store.recover_orphaned_activities()
        if orphan_count:
            logger.info(f"Recovered {orphan_count} orphaned activities")
    except _BG_EXCEPTIONS as e:
        logger.error(f"Background recovery error: {e}", exc_info=True)


def bg_recover_stale_sessions(processor: "ActivityProcessor") -> None:
    """Phase 2: End/delete stale sessions and summarize recovered ones."""
    try:
        recovered_ids, deleted_ids = processor.activity_store.recover_stale_sessions(
            timeout_seconds=processor.stale_timeout_seconds,
            min_activities=processor.min_session_activities,
            vector_store=processor.vector_store,
        )
        if deleted_ids:
            logger.info(
                f"Deleted {len(deleted_ids)} empty stale sessions: "
                f"{[s[:8] for s in deleted_ids]}"
            )
        if recovered_ids:
            logger.info(f"Recovered {len(recovered_ids)} stale sessions")
            for session_id in recovered_ids:
                try:
                    summary, _title = processor.process_session_summary_with_title(session_id)
                    if summary:
                        logger.info(
                            f"Generated summary for recovered session "
                            f"{session_id[:8]}: {summary[:50]}..."
                        )
                except (OSError, ValueError, TypeError, RuntimeError) as e:
                    logger.warning(f"Failed to summarize recovered session {session_id[:8]}: {e}")
    except _BG_EXCEPTIONS as e:
        logger.error(f"Background stale-session recovery error: {e}", exc_info=True)


def bg_cleanup_and_summarize(processor: "ActivityProcessor") -> None:
    """Phase 3: Clean up low-quality sessions and generate missing summaries.

    Cleanup runs first to avoid wasting LLM calls on sessions that
    will be deleted.
    """
    try:
        cleanup_ids = processor.activity_store.cleanup_low_quality_sessions(
            vector_store=processor.vector_store,
            min_activities=processor.min_session_activities,
        )
        if cleanup_ids:
            logger.info(
                f"Cleaned up {len(cleanup_ids)} low-quality completed sessions: "
                f"{[s[:8] for s in cleanup_ids]}"
            )

        if processor.summarizer:
            missing = processor.activity_store.get_sessions_missing_summaries(
                limit=INJECTION_MAX_SESSION_SUMMARIES,
                min_activities=processor.min_session_activities,
            )
            for session in missing:
                try:
                    summary, _title = processor.process_session_summary_with_title(session.id)
                    if summary:
                        logger.info(
                            f"Generated summary for session {session.id[:8]}: " f"{summary[:50]}..."
                        )
                except (OSError, ValueError, TypeError, RuntimeError) as e:
                    logger.warning(f"Failed to summarize session {session.id[:8]}: {e}")
    except _BG_EXCEPTIONS as e:
        logger.error(f"Background cleanup/summarize error: {e}", exc_info=True)


def bg_process_pending(processor: "ActivityProcessor") -> None:
    """Phase 4: Process pending batches and fallback sessions."""
    try:
        batch_results = processor.process_pending_batches()
        if batch_results:
            logger.info(f"Background processed {len(batch_results)} prompt batches")

        processor.process_pending()
    except _BG_EXCEPTIONS as e:
        logger.error(f"Background batch processing error: {e}", exc_info=True)


def bg_index_and_title(processor: "ActivityProcessor") -> None:
    """Phase 5: Index pending plans, embed pending observations, and generate missing titles."""
    try:
        plan_stats = processor.index_pending_plans()
        if plan_stats.get("indexed", 0) > 0:
            logger.info(f"Background indexed {plan_stats['indexed']} plans")

        # Embed observations not yet in ChromaDB (e.g. from remote sync)
        obs_stats = processor.embed_pending_observations()
        obs_embedded = obs_stats.get("embedded", 0)
        if obs_embedded > 0:
            logger.info(f"Background embedded {obs_embedded} pending observations")

        title_count = processor.generate_pending_titles()
        if title_count > 0:
            logger.info(f"Background generated {title_count} session titles")
    except _BG_EXCEPTIONS as e:
        logger.error(f"Background indexing/title error: {e}", exc_info=True)
