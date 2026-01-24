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

    Returns:
        Dictionary with rebuild statistics:
        - total: Total observations in SQLite
        - embedded: Successfully embedded count
        - failed: Failed embedding count
        - skipped: Already embedded (if reset_embedded_flags=False)
    """
    from open_agent_kit.features.codebase_intelligence.memory.store import (
        MemoryObservation,
    )

    stats = {"total": 0, "embedded": 0, "failed": 0, "skipped": 0}

    # Get total count
    stats["total"] = activity_store.count_observations()

    if stats["total"] == 0:
        logger.info("No observations in SQLite to rebuild")
        return stats

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
