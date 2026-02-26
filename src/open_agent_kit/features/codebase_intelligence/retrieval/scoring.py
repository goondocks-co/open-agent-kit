"""Confidence scoring for search results.

Stateless functions for model-agnostic confidence scoring based on
relative positioning within a result set, not absolute similarity scores.

Also provides combined scoring (confidence + importance) and doc-type weighting.
"""

import logging
from enum import Enum
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    CONFIDENCE_GAP_BOOST_THRESHOLD,
    CONFIDENCE_HIGH,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_MEDIUM_THRESHOLD,
    CONFIDENCE_MIN_MEANINGFUL_RANGE,
    CONFIDENCE_SCORE_HIGH,
    CONFIDENCE_SCORE_LOW,
    CONFIDENCE_SCORE_MEDIUM,
    IMPORTANCE_HIGH_THRESHOLD,
    IMPORTANCE_MEDIUM_THRESHOLD,
    RETRIEVAL_CONFIDENCE_WEIGHT,
    RETRIEVAL_IMPORTANCE_WEIGHT,
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    DOC_TYPE_CODE,
    DOC_TYPE_CONFIG,
    DOC_TYPE_DOCS,
    DOC_TYPE_I18N,
    DOC_TYPE_TEST,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Confidence Levels
# =============================================================================


class Confidence(str, Enum):
    """Confidence levels for search results.

    These are model-agnostic and based on relative positioning within
    a result set, not absolute similarity scores. Values imported from
    feature-level constants for consistency across the codebase.
    """

    HIGH = CONFIDENCE_HIGH
    MEDIUM = CONFIDENCE_MEDIUM
    LOW = CONFIDENCE_LOW


# =============================================================================
# Document Type Scoring Weights
# =============================================================================

# Downweight factors for different document types
# These multiply the relevance score to deprioritize less-relevant file types
DOC_TYPE_WEIGHTS: dict[str, float] = {
    DOC_TYPE_CODE: 1.0,  # Full weight for code files
    DOC_TYPE_TEST: 0.9,  # Slightly lower for tests
    DOC_TYPE_CONFIG: 0.7,  # Config files often match but aren't usually what's wanted
    DOC_TYPE_DOCS: 0.8,  # Documentation is useful but not primary
    DOC_TYPE_I18N: 0.3,  # Heavily downweight i18n - rarely the target
}


# =============================================================================
# Confidence Calculation (model-agnostic)
# =============================================================================


def calculate_confidence(
    scores: list[float],
    index: int,
) -> Confidence:
    """Calculate confidence level for a result based on its position in the result set.

    This is model-agnostic - it compares results within the same query rather
    than using absolute thresholds that vary by embedding model.

    Args:
        scores: List of relevance scores, sorted descending (best first).
        index: Index of the result to calculate confidence for.

    Returns:
        Confidence level (HIGH, MEDIUM, or LOW).
    """
    if not scores or index >= len(scores):
        return Confidence.MEDIUM

    # Single result is considered high confidence (it's the best we have)
    if len(scores) == 1:
        return Confidence.HIGH

    score = scores[index]
    max_score = scores[0]
    min_score = scores[-1]
    score_range = max_score - min_score

    # If all scores are essentially the same, model is uncertain
    if score_range < CONFIDENCE_MIN_MEANINGFUL_RANGE:
        # Fall back to position-based: first few are medium, rest are low
        if index == 0:
            return Confidence.HIGH
        elif index <= len(scores) // 3:
            return Confidence.MEDIUM
        return Confidence.LOW

    # Calculate normalized position (0.0 = min, 1.0 = max)
    normalized = (score - min_score) / score_range

    # Calculate gap to next result (for first result boost)
    gap_ratio = 0.0
    if index < len(scores) - 1:
        gap = score - scores[index + 1]
        gap_ratio = gap / score_range

    # Determine confidence level
    # HIGH: Top 30% of range AND (first result OR clear gap to next)
    if normalized >= CONFIDENCE_HIGH_THRESHOLD:
        if index == 0 or gap_ratio >= CONFIDENCE_GAP_BOOST_THRESHOLD:
            return Confidence.HIGH
        return Confidence.MEDIUM

    # MEDIUM: Top 60% of range
    if normalized >= CONFIDENCE_MEDIUM_THRESHOLD:
        return Confidence.MEDIUM

    # LOW: Bottom 40% of range
    return Confidence.LOW


def calculate_confidence_batch(scores: list[float]) -> list[Confidence]:
    """Calculate confidence levels for all results in a batch.

    Args:
        scores: List of relevance scores, sorted descending.

    Returns:
        List of Confidence levels, one per score.
    """
    return [calculate_confidence(scores, i) for i in range(len(scores))]


def filter_by_confidence(
    results: list[dict[str, Any]],
    min_confidence: str = "high",
) -> list[dict[str, Any]]:
    """Filter results by minimum confidence level.

    This is the primary method hooks should use to filter results.

    Args:
        results: List of result dicts with 'confidence' key.
        min_confidence: Minimum confidence to include:
            - 'high': Only high confidence results
            - 'medium': High and medium confidence
            - 'low' or 'all': All results (no filtering)

    Returns:
        Filtered list of results meeting the confidence threshold.
    """
    if min_confidence == "low" or min_confidence == "all":
        return results

    allowed = {Confidence.HIGH.value}
    if min_confidence == "medium":
        allowed.add(Confidence.MEDIUM.value)

    kept = [r for r in results if r.get("confidence", "low") in allowed]

    # Debug logging for filtering decisions (trace mode)
    dropped = len(results) - len(kept)
    if dropped > 0:
        logger.debug(
            f"[FILTER] Dropped {dropped}/{len(results)} results below "
            f"{min_confidence} confidence"
        )

    return kept


def calculate_combined_score(
    confidence: str,
    importance: int,
) -> float:
    """Calculate combined score from confidence level and importance.

    Uses a weighted combination of semantic relevance (confidence) and
    inherent value (importance) to produce a single score for ranking.

    Formula: (0.7 * confidence_score) + (0.3 * importance_normalized)

    Args:
        confidence: Confidence level string ("high", "medium", or "low").
        importance: Importance value on 1-10 scale.

    Returns:
        Combined score between 0.0 and 1.0.
    """
    # Map confidence level to numeric score
    confidence_scores = {
        CONFIDENCE_HIGH: CONFIDENCE_SCORE_HIGH,
        CONFIDENCE_MEDIUM: CONFIDENCE_SCORE_MEDIUM,
        CONFIDENCE_LOW: CONFIDENCE_SCORE_LOW,
    }
    confidence_score = confidence_scores.get(confidence, CONFIDENCE_SCORE_MEDIUM)

    # Normalize importance to 0-1 range (1-10 scale -> 0.1-1.0)
    importance_normalized = max(1, min(10, importance)) / 10.0

    # Weighted combination
    combined = (
        RETRIEVAL_CONFIDENCE_WEIGHT * confidence_score
        + RETRIEVAL_IMPORTANCE_WEIGHT * importance_normalized
    )

    return combined


def get_importance_level(importance: int) -> str:
    """Get importance level string from numeric value.

    Args:
        importance: Importance value on 1-10 scale.

    Returns:
        Importance level string ("high", "medium", or "low").
    """
    if importance >= IMPORTANCE_HIGH_THRESHOLD:
        return "high"
    elif importance >= IMPORTANCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def filter_by_combined_score(
    results: list[dict[str, Any]],
    min_combined: str = "high",
) -> list[dict[str, Any]]:
    """Filter results by minimum combined score threshold.

    Combines semantic relevance (confidence) with inherent value (importance)
    to determine which results to include. This method is preferred over
    filter_by_confidence when importance metadata is available.

    Args:
        results: List of result dicts with 'confidence' and optionally 'importance' keys.
        min_combined: Minimum threshold level:
            - 'high': Only results with combined score >= 0.7
            - 'medium': Results with combined score >= 0.5
            - 'low' or 'all': All results (no filtering)

    Returns:
        Filtered list of results meeting the combined score threshold.
    """
    if min_combined == "low" or min_combined == "all":
        return results

    # Define thresholds for combined score (based on weighted formula)
    # high: requires either high confidence OR high importance + medium confidence
    # medium: allows medium confidence + medium importance
    thresholds = {
        "high": 0.7,  # ~high confidence alone, or medium conf + high importance
        "medium": 0.5,  # ~medium confidence alone
    }
    threshold = thresholds.get(min_combined, 0.5)

    kept = []
    for r in results:
        confidence = r.get("confidence", "medium")
        # Get importance from result, default to 5 (medium) if not present
        importance = r.get("importance", 5)
        if isinstance(importance, str):
            # Handle string importance values from older data
            importance_map = {"low": 3, "medium": 5, "high": 8}
            importance = importance_map.get(importance, 5)

        combined = calculate_combined_score(confidence, importance)

        if combined >= threshold:
            # Add combined_score to result for debugging/transparency
            r["combined_score"] = round(combined, 3)
            kept.append(r)

    # Debug logging for filtering decisions
    dropped = len(results) - len(kept)
    if dropped > 0:
        logger.debug(
            f"[FILTER:combined] Dropped {dropped}/{len(results)} results below "
            f"{min_combined} threshold ({threshold})"
        )

    return kept


def apply_doc_type_weights(
    code_results: list[dict],
    apply_weights: bool = True,
) -> None:
    """Apply doc_type weighting to code search results (in-place).

    When enabled, multiplies each result's relevance score by a
    doc-type-specific weight and re-sorts by weighted relevance.
    When disabled, copies raw relevance to weighted_relevance.

    Args:
        code_results: List of code search result dicts (must have 'relevance' key).
        apply_weights: Whether to apply weighting (False = use raw relevance).
    """
    if apply_weights:
        for r in code_results:
            doc_type = r.get("doc_type", DOC_TYPE_CODE)
            weight = DOC_TYPE_WEIGHTS.get(doc_type, 1.0)
            r["weighted_relevance"] = r["relevance"] * weight
        code_results.sort(key=lambda x: x["weighted_relevance"], reverse=True)
    else:
        for r in code_results:
            r["weighted_relevance"] = r["relevance"]
