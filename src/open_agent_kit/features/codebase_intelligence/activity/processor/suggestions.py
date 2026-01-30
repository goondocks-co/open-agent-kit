"""Parent session suggestion computation.

Computes suggested parent sessions using vector search + LLM refinement.
Part of the user-driven session linking system.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    SUGGESTION_CONFIDENCE_HIGH,
    SUGGESTION_CONFIDENCE_LOW,
    SUGGESTION_CONFIDENCE_MEDIUM,
    SUGGESTION_HIGH_THRESHOLD,
    SUGGESTION_LLM_WEIGHT,
    SUGGESTION_LOW_THRESHOLD,
    SUGGESTION_MAX_AGE_DAYS,
    SUGGESTION_MAX_CANDIDATES,
    SUGGESTION_MEDIUM_THRESHOLD,
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

    # Compute final scores
    for candidate in candidates:
        _compute_final_score(candidate, has_llm_scores=call_llm is not None)

    # Sort by final score
    candidates.sort(key=lambda c: c.final_score, reverse=True)

    # Get best candidate
    best = candidates[0]

    # Check if score is above minimum threshold
    if best.final_score < SUGGESTION_LOW_THRESHOLD:
        logger.debug(
            f"Best candidate for {session_id} scored {best.final_score:.2f}, "
            f"below threshold {SUGGESTION_LOW_THRESHOLD}"
        )
        return None

    # Determine confidence level
    confidence = _get_confidence_level(best.final_score)

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


def _get_confidence_level(score: float) -> str:
    """Map score to confidence level."""
    if score >= SUGGESTION_HIGH_THRESHOLD:
        return SUGGESTION_CONFIDENCE_HIGH
    elif score >= SUGGESTION_MEDIUM_THRESHOLD:
        return SUGGESTION_CONFIDENCE_MEDIUM
    else:
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
