"""Session summary embedding and similarity search.

Provides functions for embedding session summaries to ChromaDB and finding
similar sessions for the user-driven session linking system.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def embed_session_summary(
    vector_store: "VectorStore",
    session_id: str,
    title: str | None,
    summary: str,
    agent: str,
    project_root: str,
    created_at_epoch: int,
) -> bool:
    """Embed session summary to ChromaDB for similarity search.

    Called after generating a session summary to enable vector-based
    similarity search for parent session suggestions.

    Args:
        vector_store: VectorStore instance.
        session_id: Unique session identifier.
        title: Session title (can be None).
        summary: Session summary text.
        agent: Agent name (claude, cursor, etc.).
        project_root: Project root directory.
        created_at_epoch: Creation timestamp as Unix epoch.

    Returns:
        True if embedding succeeded, False otherwise.
    """
    if not summary or not summary.strip():
        logger.debug(f"Skipping session summary embedding for {session_id}: empty summary")
        return False

    try:
        vector_store.add_session_summary(
            session_id=session_id,
            title=title or "",
            summary=summary,
            agent=agent,
            project_root=project_root,
            created_at_epoch=created_at_epoch,
        )
        logger.debug(f"Embedded session summary for {session_id}")
        return True
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.warning(f"Failed to embed session summary for {session_id}: {e}")
        return False


def find_similar_sessions(
    vector_store: "VectorStore",
    query_text: str,
    project_root: str,
    exclude_session_id: str | None = None,
    limit: int = 5,
    max_age_days: int = 7,
) -> list[tuple[str, float]]:
    """Find sessions with similar summaries using vector search.

    Fast candidate selection for parent session suggestions. Results should
    be refined with LLM scoring for final ranking.

    Args:
        vector_store: VectorStore instance.
        query_text: Text to search for (session summary/title).
        project_root: Filter to same project.
        exclude_session_id: Session to exclude from results.
        limit: Maximum number of results.
        max_age_days: Only include sessions within this age.

    Returns:
        List of (session_id, similarity_score) tuples, highest similarity first.
    """
    if not query_text or not query_text.strip():
        return []

    try:
        return vector_store.find_similar_sessions(
            query_text=query_text,
            project_root=project_root,
            exclude_session_id=exclude_session_id,
            limit=limit,
            max_age_days=max_age_days,
        )
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.warning(f"Failed to find similar sessions: {e}")
        return []


def reembed_session_summaries(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    clear_first: bool = True,
) -> tuple[int, int]:
    """Re-embed all session summaries from SQLite to ChromaDB.

    Used after backup restore or when the embedding model changes.
    Reads session data from SQLite and embeds summaries that exist.

    Args:
        activity_store: ActivityStore for reading session data.
        vector_store: VectorStore for storing embeddings.
        clear_first: If True, clear existing summaries before re-embedding.

    Returns:
        Tuple of (sessions_processed, sessions_embedded).
    """
    if clear_first:
        cleared = vector_store.clear_session_summaries()
        logger.info(f"Cleared {cleared} existing session summary embeddings")

    # Get all completed sessions with summaries
    # We need to query sessions that have summary observations
    conn = activity_store._get_connection()
    cursor = conn.execute("""
        SELECT s.id, s.title, s.agent, s.project_root, s.created_at_epoch,
               m.observation as summary
        FROM sessions s
        INNER JOIN memory_observations m ON m.session_id = s.id
        WHERE m.memory_type = 'session_summary'
        ORDER BY s.created_at_epoch DESC
        """)

    sessions_processed = 0
    sessions_embedded = 0

    for row in cursor.fetchall():
        session_id = row[0]
        title = row[1]
        agent = row[2]
        project_root = row[3]
        created_at_epoch = row[4]
        summary = row[5]

        sessions_processed += 1

        if summary:
            success = embed_session_summary(
                vector_store=vector_store,
                session_id=session_id,
                title=title,
                summary=summary,
                agent=agent,
                project_root=project_root,
                created_at_epoch=created_at_epoch,
            )
            if success:
                sessions_embedded += 1

    logger.info(f"Re-embedded session summaries: {sessions_embedded}/{sessions_processed} sessions")
    return sessions_processed, sessions_embedded


def backfill_session_summaries(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
) -> tuple[int, int]:
    """Backfill session summary embeddings for sessions missing from ChromaDB.

    Non-destructive: only embeds sessions not already in the vector store.
    Used during daemon startup to catch up on any missing embeddings.

    Args:
        activity_store: ActivityStore for reading session data.
        vector_store: VectorStore for storing embeddings.

    Returns:
        Tuple of (sessions_checked, sessions_embedded).
    """
    # Get current count in ChromaDB
    existing_count = vector_store.count_session_summaries()
    logger.debug(f"Session summaries in ChromaDB: {existing_count}")

    # Get all sessions with summaries from SQLite
    conn = activity_store._get_connection()
    cursor = conn.execute("""
        SELECT s.id, s.title, s.agent, s.project_root, s.created_at_epoch,
               m.observation as summary
        FROM sessions s
        INNER JOIN memory_observations m ON m.session_id = s.id
        WHERE m.memory_type = 'session_summary'
        ORDER BY s.created_at_epoch DESC
        """)

    sessions_checked = 0
    sessions_embedded = 0

    for row in cursor.fetchall():
        session_id = row[0]
        title = row[1]
        agent = row[2]
        project_root = row[3]
        created_at_epoch = row[4]
        summary = row[5]

        sessions_checked += 1

        # Embed (upsert handles duplicates gracefully)
        if summary:
            success = embed_session_summary(
                vector_store=vector_store,
                session_id=session_id,
                title=title,
                summary=summary,
                agent=agent,
                project_root=project_root,
                created_at_epoch=created_at_epoch,
            )
            if success:
                sessions_embedded += 1

    if sessions_embedded > 0:
        logger.info(f"Backfilled {sessions_embedded} session summary embeddings")

    return sessions_checked, sessions_embedded
