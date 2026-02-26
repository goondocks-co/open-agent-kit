"""Plan embedding operations for semantic search.

Track which plans have been embedded in ChromaDB for vector search.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    PromptBatch,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def get_unembedded_plans(store: ActivityStore, limit: int = 50) -> list[PromptBatch]:
    """Get plan batches that haven't been embedded in ChromaDB yet.

    Returns batches where:
    - source_type = 'plan'
    - plan_content is not empty
    - plan_embedded = FALSE

    Args:
        store: The ActivityStore instance.
        limit: Maximum batches to return.

    Returns:
        List of PromptBatch objects needing embedding.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND (plan_embedded IS NULL OR plan_embedded = 0)
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (limit,),
    )
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


def mark_plan_embedded(store: ActivityStore, batch_id: int) -> None:
    """Mark a plan batch as embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_id: The prompt batch ID to mark.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE prompt_batches SET plan_embedded = 1 WHERE id = ?",
            (batch_id,),
        )
    logger.debug(f"Marked plan batch {batch_id} as embedded")


def mark_plan_unembedded(store: ActivityStore, batch_id: int) -> None:
    """Mark a plan batch as not embedded in ChromaDB.

    Used when a plan is deleted from ChromaDB to allow re-indexing.

    Args:
        store: The ActivityStore instance.
        batch_id: The prompt batch ID to mark.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE prompt_batches SET plan_embedded = 0 WHERE id = ?",
            (batch_id,),
        )
    logger.debug(f"Marked plan batch {batch_id} as unembedded")


def count_unembedded_plans(store: ActivityStore) -> int:
    """Count plan batches not yet in ChromaDB.

    Args:
        store: The ActivityStore instance.

    Returns:
        Unembedded plan count.
    """
    conn = store._get_connection()
    cursor = conn.execute("""
        SELECT COUNT(*) FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND (plan_embedded IS NULL OR plan_embedded = 0)
        """)
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def count_embedded_plans(store: ActivityStore) -> int:
    """Count plan batches that are embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.

    Returns:
        Embedded plan count.
    """
    conn = store._get_connection()
    cursor = conn.execute("""
        SELECT COUNT(*) FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND plan_embedded = 1
        """)
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def get_embedded_plan_chromadb_ids(store: ActivityStore) -> list[str]:
    """Get ChromaDB IDs for all embedded plans.

    Plan IDs in ChromaDB use the format 'plan-{batch_id}'.
    Used by orphan cleanup to diff against ChromaDB IDs.

    Args:
        store: The ActivityStore instance.

    Returns:
        List of ChromaDB-format plan IDs (e.g. 'plan-42').
    """
    conn = store._get_connection()
    cursor = conn.execute("""
        SELECT id FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND plan_embedded = 1
        """)
    return [f"plan-{row[0]}" for row in cursor.fetchall()]


def mark_all_plans_unembedded(store: ActivityStore) -> int:
    """Mark all plans as not embedded (for full ChromaDB rebuild).

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of plans marked.
    """
    with store._transaction() as conn:
        cursor = conn.execute("UPDATE prompt_batches SET plan_embedded = 0 WHERE plan_embedded = 1")
        count = cursor.rowcount

    logger.info(f"Marked {count} plans as unembedded for rebuild")
    return count
