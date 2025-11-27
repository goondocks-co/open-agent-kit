"""Parent session suggestion computation.

Computes suggested parent sessions using vector search + LLM refinement.
Part of the user-driven session linking system.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    CONFIDENCE_GAP_BOOST_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    CONFIDENCE_MIN_MEANINGFUL_RANGE,
    RELATED_SUGGESTION_MAX_AGE_DAYS,
    SUGGESTION_CONFIDENCE_HIGH,
    SUGGESTION_CONFIDENCE_LOW,
    SUGGESTION_CONFIDENCE_MEDIUM,
    SUGGESTION_LLM_WEIGHT,
    SUGGESTION_MAX_AGE_DAYS,
    SUGGESTION_MAX_CANDIDATES,
    SUGGESTION_TIME_BONUS_1H_SECONDS,
    SUGGESTION_TIME_BONUS_1H_VALUE,
    SUGGESTION_TIME_BONUS_6H_SECONDS,
    SUGGESTION_TIME_BONUS_6H_VALUE,
    SUGGESTION_VECTOR_WEIGHT,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class SuggestionCandidate:
    """A candidate parent session with similarity scores."""

    session_id: str
    title: str | None
    summary: str | None
    vector_similarity: float
    llm_score: float | None = None
    time_gap_seconds: float | None = None
    final_score: float = 0.0


@dataclass
class RelatedSuggestion:
    """Result of related session suggestion computation."""

    session_id: str
    title: str | None
    confidence: str  # high, medium, low
    confidence_score: float
    reason: str


@dataclass
class SuggestedParent:
    """Result of suggestion computation."""

    session_id: str
    title: str | None
    confidence: str  # high, medium, low
    confidence_score: float
    reason: str


def compute_suggested_parent(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    session_id: str,
    call_llm: Callable[[str], dict[str, Any]] | None = None,
) -> SuggestedParent | None:
    """Compute suggested parent for an unlinked session.

    Uses a multi-step approach:
    1. Get current session's summary/title
    2. Vector search for top N similar sessions
    3. (Optional) LLM refine scoring for top candidates
    4. Apply time bonus
    5. Return best match above threshold

    Args:
        activity_store: ActivityStore for session data.
        vector_store: VectorStore for similarity search.
        session_id: Session to find parent suggestion for.
        call_llm: Optional LLM function for refinement scoring.
                  If None, uses vector similarity only.

    Returns:
        SuggestedParent if a good match is found, None otherwise.
    """
    # Get the session
    session = activity_store.get_session(session_id)
    if not session:
        logger.debug(f"Session {session_id} not found for suggestion")
        return None

    # Don't suggest for sessions that already have a parent
    if session.parent_session_id:
        logger.debug(f"Session {session_id} already has parent, skipping suggestion")
        return None

    # Check if suggestion was dismissed
    conn = activity_store._get_connection()
    cursor = conn.execute(
        "SELECT suggested_parent_dismissed FROM sessions WHERE id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    if row and row[0]:
        logger.debug(f"Session {session_id} suggestion was dismissed")
        return None

    # Get session's summary for similarity search
    summary_obs = activity_store.get_latest_session_summary(session_id)
    if not summary_obs:
        logger.debug(f"Session {session_id} has no summary, cannot compute suggestion")
        return None

    query_text = f"{session.title or ''}\n\n{summary_obs.observation}"

    # Get already-related sessions to exclude from suggestions
    from open_agent_kit.features.codebase_intelligence.activity.store.relationships import (
        get_related_session_ids,
    )

    related_ids = get_related_session_ids(activity_store, session_id)

    # Vector search for similar sessions
    similar_sessions = vector_store.find_similar_sessions(
        query_text=query_text,
        project_root=session.project_root,
        exclude_session_id=session_id,
        limit=SUGGESTION_MAX_CANDIDATES,
        max_age_days=SUGGESTION_MAX_AGE_DAYS,
    )

    if not similar_sessions:
        logger.debug(f"No similar sessions found for {session_id}")
        return None

    # Build candidates with metadata
    candidates: list[SuggestionCandidate] = []
    for candidate_id, vector_similarity in similar_sessions:
        candidate_session = activity_store.get_session(candidate_id)
        if not candidate_session:
            continue

        # Skip sessions that are already linked to this one (avoid reverse links)
        if candidate_session.parent_session_id == session_id:
            continue

        # Skip sessions that are already related
        if candidate_id in related_ids:
            continue

        # Get candidate's summary
        candidate_summary_obs = activity_store.get_latest_session_summary(candidate_id)
        candidate_summary = candidate_summary_obs.observation if candidate_summary_obs else None

        # Calculate time gap
        time_gap_seconds: float | None = None
        if session.started_at and candidate_session.ended_at:
            time_gap_seconds = (session.started_at - candidate_session.ended_at).total_seconds()
        elif session.started_at and candidate_session.started_at:
            time_gap_seconds = (session.started_at - candidate_session.started_at).total_seconds()

        candidates.append(
            SuggestionCandidate(
                session_id=candidate_id,
                title=candidate_session.title,
                summary=candidate_summary,
                vector_similarity=vector_similarity,
                time_gap_seconds=time_gap_seconds,
            )
        )

    if not candidates:
        logger.debug(f"No valid candidates after filtering for {session_id}")
        return None

    # LLM refinement if available
    if call_llm:
        _compute_llm_scores(
            current_summary=summary_obs.observation,
            candidates=candidates,
            call_llm=call_llm,
        )

    # Compute final scores (combines vector similarity, optional LLM, and time bonus)
    for candidate in candidates:
        _compute_final_score(candidate, has_llm_scores=call_llm is not None)

    # Sort by final score (descending - best first)
    candidates.sort(key=lambda c: c.final_score, reverse=True)

    # Get best candidate
    best = candidates[0]

    # Use relative confidence scoring (model-agnostic)
    # This compares results within this result set, not against absolute thresholds
    # which vary significantly across different embedding models
    scores = [c.final_score for c in candidates]
    confidence = _calculate_relative_confidence(scores, index=0)

    # Only show suggestions with high or medium relative confidence
    # Low confidence means the best result isn't significantly better than others
    if confidence == SUGGESTION_CONFIDENCE_LOW:
        logger.debug(
            f"Best candidate for {session_id} has low relative confidence "
            f"(score={best.final_score:.2f}), not suggesting"
        )
        return None

    # Build reason string
    reason = _build_reason(best, has_llm=call_llm is not None)

    logger.info(
        f"Suggested parent for {session_id[:8]}: {best.session_id[:8]} "
        f"(score={best.final_score:.2f}, confidence={confidence})"
    )

    return SuggestedParent(
        session_id=best.session_id,
        title=best.title,
        confidence=confidence,
        confidence_score=best.final_score,
        reason=reason,
    )


def _compute_llm_scores(
    current_summary: str,
    candidates: list[SuggestionCandidate],
    call_llm: Callable[[str], dict[str, Any]],
) -> None:
    """Compute LLM similarity scores for candidates.

    Updates candidates in-place with llm_score.
    """
    for candidate in candidates:
        if not candidate.summary:
            candidate.llm_score = 0.0
            continue

        score = compute_llm_similarity(
            session_a_summary=current_summary,
            session_b_summary=candidate.summary,
            call_llm=call_llm,
        )
        candidate.llm_score = score


def compute_llm_similarity(
    session_a_summary: str,
    session_b_summary: str,
    call_llm: Callable[[str], dict[str, Any]],
) -> float:
    """Use LLM to compute similarity between two session summaries.

    Args:
        session_a_summary: First session's summary.
        session_b_summary: Second session's summary.
        call_llm: Function to call LLM with a prompt.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    prompt = f"""Rate how related these two coding sessions are on a scale of 0.0 to 1.0.

Session A:
{session_a_summary[:1500]}

Session B:
{session_b_summary[:1500]}

Consider:
- Are they working on the same feature/bug?
- Do they reference the same files or components?
- Is one a continuation of the other?

Respond with ONLY a number between 0.0 and 1.0."""

    try:
        result = call_llm(prompt)
        if not result.get("success"):
            logger.debug(f"LLM similarity call failed: {result.get('error')}")
            return 0.0

        raw_response = result.get("raw_response", "")
        if not raw_response:
            return 0.0

        # Parse the response - expect just a number
        response_text = str(raw_response).strip()
        # Handle common LLM response variations
        for prefix in ["Score:", "Rating:", "Similarity:"]:
            if response_text.startswith(prefix):
                response_text = response_text[len(prefix) :].strip()

        score = float(response_text)
        return max(0.0, min(1.0, score))

    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse LLM similarity score: {e}")
        return 0.0
    except (OSError, RuntimeError) as e:
        logger.warning(f"LLM similarity call error: {e}")
        return 0.0


def _compute_final_score(candidate: SuggestionCandidate, has_llm_scores: bool) -> None:
    """Compute final score for a candidate.

    Combines vector similarity, LLM score (if available), and time bonus.
    Updates candidate.final_score in place.
    """
    if has_llm_scores and candidate.llm_score is not None:
        # Combined scoring: vector + LLM
        base_score = (
            SUGGESTION_VECTOR_WEIGHT * candidate.vector_similarity
            + SUGGESTION_LLM_WEIGHT * candidate.llm_score
        )
    else:
        # Vector only
        base_score = candidate.vector_similarity

    # Time bonus for recent sessions
    time_bonus = 0.0
    if candidate.time_gap_seconds is not None and candidate.time_gap_seconds >= 0:
        if candidate.time_gap_seconds < SUGGESTION_TIME_BONUS_1H_SECONDS:
            time_bonus = SUGGESTION_TIME_BONUS_1H_VALUE
        elif candidate.time_gap_seconds < SUGGESTION_TIME_BONUS_6H_SECONDS:
            time_bonus = SUGGESTION_TIME_BONUS_6H_VALUE

    candidate.final_score = min(1.0, base_score + time_bonus)


def _calculate_relative_confidence(scores: list[float], index: int) -> str:
    """Calculate confidence level based on relative position in result set.

    This is model-agnostic - it compares results within the same query rather
    than using absolute thresholds that vary by embedding model.

    Adapted from RetrievalEngine.calculate_confidence() for consistency.

    Args:
        scores: List of relevance scores, sorted descending (best first).
        index: Index of the result to calculate confidence for.

    Returns:
        Confidence level string: "high", "medium", or "low".
    """
    if not scores or index >= len(scores):
        return SUGGESTION_CONFIDENCE_MEDIUM

    # Single result - can't determine relative confidence, be conservative
    if len(scores) == 1:
        # With only one candidate, we can't compare. Default to medium.
        return SUGGESTION_CONFIDENCE_MEDIUM

    score = scores[index]
    max_score = scores[0]
    min_score = scores[-1]
    score_range = max_score - min_score

    # If all scores are essentially the same, model is uncertain
    if score_range < CONFIDENCE_MIN_MEANINGFUL_RANGE:
        # Fall back to position-based: first is medium (can't be sure), rest are low
        if index == 0:
            return SUGGESTION_CONFIDENCE_MEDIUM
        return SUGGESTION_CONFIDENCE_LOW

    # Calculate normalized position (0.0 = min, 1.0 = max)
    normalized = (score - min_score) / score_range

    # Calculate gap to next result (for confidence boost)
    gap_ratio = 0.0
    if index < len(scores) - 1:
        gap = score - scores[index + 1]
        gap_ratio = gap / score_range

    # HIGH: Top 30% of range AND (first result OR clear gap to next)
    if normalized >= CONFIDENCE_HIGH_THRESHOLD:
        if index == 0 or gap_ratio >= CONFIDENCE_GAP_BOOST_THRESHOLD:
            return SUGGESTION_CONFIDENCE_HIGH
        return SUGGESTION_CONFIDENCE_MEDIUM

    # MEDIUM: Top 60% of range
    if normalized >= CONFIDENCE_MEDIUM_THRESHOLD:
        return SUGGESTION_CONFIDENCE_MEDIUM

    # LOW: Bottom 40% of range
    return SUGGESTION_CONFIDENCE_LOW


def _build_reason(candidate: SuggestionCandidate, has_llm: bool) -> str:
    """Build human-readable reason for the suggestion."""
    parts = []

    # Vector similarity component
    parts.append(f"Vector similarity: {candidate.vector_similarity:.0%}")

    # LLM score if available
    if has_llm and candidate.llm_score is not None:
        parts.append(f"LLM score: {candidate.llm_score:.0%}")

    # Time proximity
    if candidate.time_gap_seconds is not None and candidate.time_gap_seconds >= 0:
        hours = candidate.time_gap_seconds / 3600
        if hours < 1:
            minutes = int(candidate.time_gap_seconds / 60)
            parts.append(f"Time gap: {minutes}m")
        elif hours < 24:
            parts.append(f"Time gap: {hours:.1f}h")
        else:
            days = hours / 24
            parts.append(f"Time gap: {days:.1f}d")

    return " | ".join(parts)


def dismiss_suggestion(
    activity_store: "ActivityStore",
    session_id: str,
) -> bool:
    """Mark a session's suggestion as dismissed.

    Args:
        activity_store: ActivityStore instance.
        session_id: Session to dismiss suggestion for.

    Returns:
        True if updated successfully, False otherwise.
    """
    try:
        with activity_store._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET suggested_parent_dismissed = 1 WHERE id = ?",
                (session_id,),
            )
        logger.debug(f"Dismissed suggestion for session {session_id}")
        return True
    except (OSError, ValueError) as e:
        logger.error(f"Failed to dismiss suggestion for {session_id}: {e}")
        return False


def reset_suggestion_dismissal(
    activity_store: "ActivityStore",
    session_id: str,
) -> bool:
    """Reset a session's suggestion dismissal (allow new suggestions).

    Args:
        activity_store: ActivityStore instance.
        session_id: Session to reset.

    Returns:
        True if updated successfully, False otherwise.
    """
    try:
        with activity_store._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET suggested_parent_dismissed = 0 WHERE id = ?",
                (session_id,),
            )
        logger.debug(f"Reset suggestion dismissal for session {session_id}")
        return True
    except (OSError, ValueError) as e:
        logger.error(f"Failed to reset suggestion dismissal for {session_id}: {e}")
        return False


# =============================================================================
# Related Session Suggestions (many-to-many semantic relationships)
# =============================================================================


def compute_related_sessions(
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    session_id: str,
    limit: int = 5,
    exclude_lineage: bool = True,
    exclude_existing_related: bool = True,
) -> list[RelatedSuggestion]:
    """Compute suggested related sessions for semantic linking.

    Unlike parent suggestions (which are for temporal continuity after "clear"),
    related suggestions find semantically similar sessions regardless of time gap.
    This enables linking sessions that worked on the same topic months apart.

    Args:
        activity_store: ActivityStore for session data.
        vector_store: VectorStore for similarity search.
        session_id: Session to find related suggestions for.
        limit: Maximum number of suggestions to return.
        exclude_lineage: If True, exclude parent/child sessions from results.
        exclude_existing_related: If True, exclude already-related sessions.

    Returns:
        List of RelatedSuggestion objects, sorted by confidence (best first).
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.relationships import (
        get_related_session_ids,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_session_lineage,
    )

    # Get the session
    session = activity_store.get_session(session_id)
    if not session:
        logger.debug(f"Session {session_id} not found for related suggestions")
        return []

    # Get session's summary for similarity search
    summary_obs = activity_store.get_latest_session_summary(session_id)
    if not summary_obs:
        logger.debug(f"Session {session_id} has no summary, cannot compute related suggestions")
        return []

    query_text = f"{session.title or ''}\n\n{summary_obs.observation}"

    # Build exclusion set
    exclude_ids: set[str] = {session_id}

    # Exclude lineage (ancestors and children)
    if exclude_lineage:
        lineage = get_session_lineage(activity_store, session_id)
        for ancestor in lineage:
            exclude_ids.add(ancestor.id)

        # Also get children via parent_session_id
        conn = activity_store._get_connection()
        cursor = conn.execute(
            "SELECT id FROM sessions WHERE parent_session_id = ?",
            (session_id,),
        )
        for row in cursor.fetchall():
            exclude_ids.add(row[0])

    # Exclude already-related sessions
    if exclude_existing_related:
        existing_related = get_related_session_ids(activity_store, session_id)
        exclude_ids.update(existing_related)

    # Vector search for similar sessions with extended age limit
    # Request more than limit to account for filtering
    fetch_limit = limit + len(exclude_ids) + 5
    similar_sessions = vector_store.find_similar_sessions(
        query_text=query_text,
        project_root=session.project_root,
        exclude_session_id=session_id,
        limit=fetch_limit,
        max_age_days=RELATED_SUGGESTION_MAX_AGE_DAYS,
    )

    if not similar_sessions:
        logger.debug(f"No similar sessions found for {session_id}")
        return []

    # Filter out excluded sessions and build candidates
    candidates: list[SuggestionCandidate] = []
    for candidate_id, vector_similarity in similar_sessions:
        if candidate_id in exclude_ids:
            continue

        candidate_session = activity_store.get_session(candidate_id)
        if not candidate_session:
            continue

        # Get candidate's summary
        candidate_summary_obs = activity_store.get_latest_session_summary(candidate_id)
        candidate_summary = candidate_summary_obs.observation if candidate_summary_obs else None

        # Calculate time gap (for display, not scoring - related doesn't prioritize recent)
        time_gap_seconds: float | None = None
        if session.started_at and candidate_session.started_at:
            time_gap_seconds = abs(
                (session.started_at - candidate_session.started_at).total_seconds()
            )

        candidates.append(
            SuggestionCandidate(
                session_id=candidate_id,
                title=candidate_session.title,
                summary=candidate_summary,
                vector_similarity=vector_similarity,
                time_gap_seconds=time_gap_seconds,
                final_score=vector_similarity,  # Use raw similarity for related (no time bonus)
            )
        )

        if len(candidates) >= limit * 2:  # Get extra for confidence calculation
            break

    if not candidates:
        logger.debug(f"No valid candidates after filtering for {session_id}")
        return []

    # Sort by similarity (best first)
    candidates.sort(key=lambda c: c.final_score, reverse=True)

    # Calculate relative confidence for each candidate
    scores = [c.final_score for c in candidates]
    suggestions: list[RelatedSuggestion] = []

    for i, candidate in enumerate(candidates[:limit]):
        confidence = _calculate_relative_confidence(scores, index=i)

        # Filter out low confidence results (relative to this result set)
        # The min_confidence threshold filters by absolute score at search level,
        # but we also filter by relative confidence label here
        if confidence == SUGGESTION_CONFIDENCE_LOW:
            continue

        # Build reason string with time gap
        reason = f"Vector similarity: {candidate.vector_similarity:.0%}"
        if candidate.time_gap_seconds is not None:
            hours = candidate.time_gap_seconds / 3600
            if hours < 24:
                reason += f" | {hours:.1f}h apart"
            else:
                days = hours / 24
                reason += f" | {days:.0f}d apart"

        suggestions.append(
            RelatedSuggestion(
                session_id=candidate.session_id,
                title=candidate.title,
                confidence=confidence,
                confidence_score=candidate.final_score,
                reason=reason,
            )
        )

    logger.debug(f"Found {len(suggestions)} related session suggestions for {session_id[:8]}")
    return suggestions
