"""Plan and memory indexing for semantic search.

Handles background indexing and rebuilding of ChromaDB from SQLite.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
        PromptBatch,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def index_pending_plans(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    batch_size: int = 10,
) -> dict[str, int]:
    """Index plans that haven't been embedded in ChromaDB yet.

    Plans are stored in prompt_batches (SQLite) with source_type='plan'
    and indexed in oak_memory (ChromaDB) with memory_type='plan'.
    This enables semantic search of plans alongside code and memories.

    Called during background processing cycle.

    Args:
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        batch_size: Number of plans to process per batch.

    Returns:
        Dictionary with indexing statistics:
        - indexed: Successfully indexed count
        - skipped: Plans with no content (marked as embedded)
        - failed: Failed indexing count
    """
    from open_agent_kit.features.codebase_intelligence.memory.store import (
        PlanObservation,
    )

    stats = {"indexed": 0, "skipped": 0, "failed": 0}

    unembedded = activity_store.get_unembedded_plans(limit=batch_size)

    if not unembedded:
        return stats

    logger.info(f"Indexing {len(unembedded)} pending plans for search")

    for batch in unembedded:
        if not batch.plan_content:
            # Mark as embedded (nothing to index)
            if batch.id is not None:
                activity_store.mark_plan_embedded(batch.id)
            stats["skipped"] += 1
            continue

        try:
            # Extract title from filename or content
            title = extract_plan_title(batch)

            plan = PlanObservation(
                id=f"plan-{batch.id}",
                session_id=batch.session_id,
                title=title,
                content=batch.plan_content,
                file_path=batch.plan_file_path,
                created_at=batch.started_at,
            )

            vector_store.add_plan(plan)
            if batch.id is not None:
                activity_store.mark_plan_embedded(batch.id)
            stats["indexed"] += 1

            logger.info(f"Indexed plan for search: {title} (batch_id={batch.id})")

        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to index plan {batch.id}: {e}")
            stats["failed"] += 1

    if stats["indexed"] > 0:
        logger.info(
            f"Plan indexing complete: {stats['indexed']} indexed, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )

    return stats


def extract_plan_title(batch: "PromptBatch") -> str:
    """Extract plan title from filename or first heading.

    Args:
        batch: PromptBatch with plan content.

    Returns:
        Title string for the plan.
    """
    # Try to extract from filename
    if batch.plan_file_path:
        filename = Path(batch.plan_file_path).stem
        # Convert kebab-case to title case
        title = filename.replace("-", " ").replace("_", " ").title()
        return title

    # Fallback: extract first markdown heading from content
    if batch.plan_content:
        for line in batch.plan_content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()

    # Final fallback
    return f"Plan #{batch.prompt_number}"


def rebuild_plan_index(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    batch_size: int = 50,
) -> dict[str, int]:
    """Rebuild ChromaDB plan index from SQLite source of truth.

    Marks all plans as unembedded and re-indexes them. Use this when
    ChromaDB is empty/wiped or when there's a dimension mismatch.

    Args:
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        batch_size: Number of plans to process per batch.

    Returns:
        Dictionary with rebuild statistics.
    """
    stats = {"total": 0, "indexed": 0, "skipped": 0, "failed": 0}

    # Mark all plans as unembedded
    total_reset = activity_store.mark_all_plans_unembedded()
    stats["total"] = total_reset

    if stats["total"] == 0:
        logger.info("No plans in SQLite to rebuild")
        return stats

    logger.info(f"Rebuilding plan index for {stats['total']} plans")

    # Process in batches
    while True:
        batch_stats = index_pending_plans(activity_store, vector_store, batch_size=batch_size)

        if batch_stats["indexed"] == 0 and batch_stats["skipped"] == 0:
            break

        stats["indexed"] += batch_stats["indexed"]
        stats["skipped"] += batch_stats["skipped"]
        stats["failed"] += batch_stats["failed"]

    logger.info(
        f"Plan index rebuild complete: {stats['indexed']} indexed, "
        f"{stats['skipped']} skipped, {stats['failed']} failed"
    )
    return stats


def rebuild_chromadb_from_sqlite(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    batch_size: int = 50,
    reset_embedded_flags: bool = True,
    clear_chromadb_first: bool = False,
) -> dict[str, int]:
    """Rebuild ChromaDB memory index from SQLite source of truth.

    Call this when ChromaDB is empty/wiped but SQLite has observations,
    or when there's a dimension mismatch requiring full re-indexing.

    Args:
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        batch_size: Number of observations to process per batch.
        reset_embedded_flags: If True, marks ALL observations as unembedded
            first (for full rebuild). If False, only processes observations
            already marked as unembedded.
        clear_chromadb_first: If True, clears the ChromaDB memory collection
            before rebuilding. Use this after restore operations to remove
            orphaned entries that were deleted from SQLite but still exist
            in ChromaDB.

    Returns:
        Dictionary with rebuild statistics:
        - total: Total observations in SQLite
        - embedded: Successfully embedded count
        - failed: Failed embedding count
        - skipped: Already embedded (if reset_embedded_flags=False)
        - cleared: Items cleared from ChromaDB (if clear_chromadb_first=True)
    """
    from open_agent_kit.features.codebase_intelligence.memory.store import (
        MemoryObservation,
    )

    stats = {"total": 0, "embedded": 0, "failed": 0, "skipped": 0, "cleared": 0}

    # Get total count
    stats["total"] = activity_store.count_observations()

    if stats["total"] == 0:
        logger.info("No observations in SQLite to rebuild")
        return stats

    # Step 0: Clear ChromaDB memory collection if requested (removes orphans)
    if clear_chromadb_first:
        cleared_count = vector_store.clear_memory_collection()
        stats["cleared"] = cleared_count
        logger.info(f"Cleared {cleared_count} items from ChromaDB memory collection")

    # Step 1: Reset embedded flags if doing full rebuild
    if reset_embedded_flags:
        already_embedded = activity_store.count_embedded_observations()
        if already_embedded > 0:
            logger.info(f"Resetting {already_embedded} embedded flags for full rebuild")
            activity_store.mark_all_observations_unembedded()

    # Step 2: Process unembedded observations in batches
    processed = 0
    while True:
        observations = activity_store.get_unembedded_observations(limit=batch_size)

        if not observations:
            break

        logger.info(
            f"Rebuilding ChromaDB: processing batch of {len(observations)} "
            f"({processed}/{stats['total']} done)"
        )

        for stored_obs in observations:
            try:
                # Create MemoryObservation for ChromaDB
                memory = MemoryObservation(
                    id=stored_obs.id,
                    observation=stored_obs.observation,
                    memory_type=stored_obs.memory_type,
                    context=stored_obs.context,
                    tags=stored_obs.tags or [],
                    created_at=stored_obs.created_at,
                )

                # Embed and store
                vector_store.add_memory(memory)
                activity_store.mark_observation_embedded(stored_obs.id)
                stats["embedded"] += 1

            except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
                logger.warning(f"Failed to embed observation {stored_obs.id}: {e}")
                stats["failed"] += 1

        processed += len(observations)

    logger.info(
        f"ChromaDB rebuild complete: {stats['embedded']} embedded, "
        f"{stats['failed']} failed, {stats['total']} total"
    )

    # Step 3: Also rebuild plans if we cleared ChromaDB (plans were wiped too)
    if clear_chromadb_first:
        logger.info("Rebuilding plan index (cleared with ChromaDB)")
        plan_stats = rebuild_plan_index(activity_store, vector_store, batch_size)
        stats["plans_indexed"] = plan_stats.get("indexed", 0)
        stats["plans_failed"] = plan_stats.get("failed", 0)
        logger.info(
            f"Plan rebuild complete: {stats['plans_indexed']} indexed, "
            f"{stats['plans_failed']} failed"
        )

    return stats


def embed_pending_observations(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    batch_size: int = 50,
) -> dict[str, int]:
    """Embed observations that are in SQLite but not yet in ChromaDB.

    This is the incremental version - only processes observations with
    embedded=FALSE. Use rebuild_chromadb_from_sqlite for full rebuilds.

    Args:
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        batch_size: Number of observations to process per batch.

    Returns:
        Dictionary with processing statistics.
    """
    return rebuild_chromadb_from_sqlite(
        activity_store=activity_store,
        vector_store=vector_store,
        batch_size=batch_size,
        reset_embedded_flags=False,
    )


def compact_all_chromadb(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    clear_code_index: bool = True,
    hard_reset: bool = True,
) -> dict[str, int]:
    """Compact all ChromaDB collections by rebuilding from SQLite source of truth.

    This is the ONLY way to reclaim disk space after deletions - ChromaDB has no
    built-in vacuum/compaction. Use after large refactors, deletions, embedding
    model changes, or periodically to maintain optimal storage size.

    When hard_reset=True (default), this deletes the entire ChromaDB directory
    and rebuilds from scratch. This is the ONLY way to actually reclaim disk
    space since ChromaDB's delete_collection() doesn't release file space.

    Operations performed:
    1. Hard reset ChromaDB (delete directory, reclaim space)
    2. Re-embed session summaries from SQLite
    3. Re-embed memories from SQLite
    4. Code index cleared - caller must trigger re-indexing

    This function is synchronous and may take a while for large datasets.
    Callers should run it in a background task/thread.

    Args:
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        clear_code_index: Whether to clear the code index. Caller is responsible
            for triggering re-indexing afterward (e.g., via background indexer).
        hard_reset: If True, delete ChromaDB directory to reclaim disk space.
            If False, use delete_collection which doesn't release space.

    Returns:
        Dictionary with compaction statistics:
        - bytes_freed: Disk space reclaimed (only if hard_reset=True)
        - code_cleared: Whether code index was cleared
        - sessions_processed: Total sessions processed
        - sessions_embedded: Successfully embedded sessions
        - memories_embedded: Successfully embedded memories
        - memories_cleared: Orphaned memory entries removed
        - memories_failed: Failed memory embeddings
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
        reembed_session_summaries,
    )

    stats: dict[str, int] = {
        "bytes_freed": 0,
        "code_cleared": 0,
        "sessions_processed": 0,
        "sessions_embedded": 0,
        "memories_embedded": 0,
        "memories_cleared": 0,
        "memories_failed": 0,
        "plans_indexed": 0,
        "plans_failed": 0,
    }

    # 1. Hard reset to reclaim disk space (or soft clear if hard_reset=False)
    if hard_reset:
        bytes_freed = vector_store.hard_reset()
        stats["bytes_freed"] = bytes_freed
        stats["code_cleared"] = 1
        logger.info(f"Hard reset complete: freed {bytes_freed / 1024 / 1024:.1f} MB")
    elif clear_code_index:
        vector_store.clear_code_index()
        stats["code_cleared"] = 1
        logger.info("Cleared ChromaDB code index (soft clear, no space reclaimed)")

    # 2. Re-embed session summaries from SQLite
    try:
        sessions_processed, sessions_embedded = reembed_session_summaries(
            activity_store,
            vector_store,
        )
        stats["sessions_processed"] = sessions_processed
        stats["sessions_embedded"] = sessions_embedded
        logger.info(f"Re-embedded {sessions_embedded}/{sessions_processed} session summaries")
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Session summary re-embedding failed: {e}")

    # 3. Re-embed memories from SQLite
    try:
        # Mark all as unembedded and rebuild (ChromaDB is already empty from hard reset)
        memory_stats = rebuild_chromadb_from_sqlite(
            activity_store=activity_store,
            vector_store=vector_store,
            batch_size=50,
            reset_embedded_flags=True,
            clear_chromadb_first=False,  # Already cleared by hard_reset
        )
        stats["memories_embedded"] = memory_stats.get("embedded", 0)
        stats["memories_cleared"] = memory_stats.get("cleared", 0)
        stats["memories_failed"] = memory_stats.get("failed", 0)
        logger.info(f"Re-embedded {stats['memories_embedded']} memories")
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Memory re-embedding failed: {e}")

    # 4. Re-index plans (stored in prompt_batches, indexed to memory collection)
    try:
        plan_stats = rebuild_plan_index(activity_store, vector_store, batch_size=50)
        stats["plans_indexed"] = plan_stats.get("indexed", 0)
        stats["plans_failed"] = plan_stats.get("failed", 0)
        logger.info(f"Re-indexed {stats['plans_indexed']} plans")
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Plan re-indexing failed: {e}")

    logger.info("ChromaDB compaction complete")
    return stats
