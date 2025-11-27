"""Retrieval engine for semantic search.

This is the central abstraction for all retrieval operations in CI.
All search functionality (daemon routes, MCP tools, hooks) should use this engine.

Provides:
- Unified search interface for code and memories
- Token-aware context assembly
- Model-agnostic confidence scoring
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from open_agent_kit.features.codebase_intelligence.constants import (
    CHARS_PER_TOKEN_ESTIMATE,
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
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_CONTEXT_MEMORY_LIMIT,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MEMORY_LIST_LIMIT,
    DEFAULT_PREVIEW_LENGTH,
    DEFAULT_SEARCH_LIMIT,
    IMPORTANCE_HIGH_THRESHOLD,
    IMPORTANCE_MEDIUM_THRESHOLD,
    MEMORY_TYPE_PLAN,
    RETRIEVAL_CONFIDENCE_WEIGHT,
    RETRIEVAL_IMPORTANCE_WEIGHT,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    DOC_TYPE_CODE,
    DOC_TYPE_CONFIG,
    DOC_TYPE_DOCS,
    DOC_TYPE_I18N,
    DOC_TYPE_TEST,
    MemoryObservation,
    VectorStore,
)

logger = logging.getLogger(__name__)


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
# Confidence Scoring
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


@dataclass
class RetrievalConfig:
    """Configuration for retrieval operations."""

    default_limit: int = DEFAULT_SEARCH_LIMIT
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    preview_length: int = DEFAULT_PREVIEW_LENGTH


@dataclass
class SearchResult:
    """Result from a search operation."""

    query: str
    code: list[dict[str, Any]] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
    plans: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    total_tokens_available: int = 0


@dataclass
class FetchResult:
    """Result from a fetch operation."""

    results: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0


@dataclass
class ContextResult:
    """Result from a context retrieval operation."""

    task: str
    code: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    guidelines: list[str] = field(default_factory=list)
    total_tokens: int = 0


class RetrievalEngine:
    """Engine for semantic retrieval.

    This is the central abstraction for all search/retrieval operations.
    It provides:
    - Unified search interface for code and memories
    - Token-aware context assembly
    - Model-agnostic confidence scoring
    """

    def __init__(self, vector_store: VectorStore, config: RetrievalConfig | None = None):
        """Initialize retrieval engine.

        Args:
            vector_store: VectorStore instance for searching.
            config: Retrieval configuration.
        """
        self.store = vector_store
        self.config = config or RetrievalConfig()

    # =========================================================================
    # Confidence Calculation (model-agnostic)
    # =========================================================================

    @staticmethod
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

    @staticmethod
    def calculate_confidence_batch(scores: list[float]) -> list[Confidence]:
        """Calculate confidence levels for all results in a batch.

        Args:
            scores: List of relevance scores, sorted descending.

        Returns:
            List of Confidence levels, one per score.
        """
        return [RetrievalEngine.calculate_confidence(scores, i) for i in range(len(scores))]

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

            combined_score = RetrievalEngine.calculate_combined_score(confidence, importance)

            if combined_score >= threshold:
                # Add combined_score to result for debugging/transparency
                r["combined_score"] = round(combined_score, 3)
                kept.append(r)

        # Debug logging for filtering decisions
        dropped = len(results) - len(kept)
        if dropped > 0:
            logger.debug(
                f"[FILTER:combined] Dropped {dropped}/{len(results)} results below "
                f"{min_combined} threshold ({threshold})"
            )

        return kept

    # =========================================================================
    # Document Type Weighting
    # =========================================================================

    @staticmethod
    def _apply_doc_type_weights(
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

    # =========================================================================
    # Primary Search Methods (used by daemon routes)
    # =========================================================================

    def search(
        self,
        query: str,
        search_type: str = SEARCH_TYPE_ALL,
        limit: int | None = None,
        apply_doc_type_weights: bool = True,
    ) -> SearchResult:
        """Search code and/or memories.

        This is the primary search method used by the /api/search endpoint.
        Results include model-agnostic confidence levels (high/medium/low)
        based on relative positioning within the result set.

        Args:
            query: Natural language search query.
            search_type: 'all', 'code', or 'memory'.
            limit: Maximum results per category.
            apply_doc_type_weights: Whether to apply doc_type weighting (default True).
                Set to False when searching for specific file types like translations,
                or in skills/hooks where the weighting isn't appropriate.

        Returns:
            SearchResult with code and memory results, each including confidence.
        """
        limit = limit or self.config.default_limit

        result = SearchResult(query=query)

        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_CODE):
            code_results = self.store.search_code(
                query=query,
                limit=limit,
            )

            # Apply doc_type weighting to scores (if enabled)
            self._apply_doc_type_weights(code_results, apply_doc_type_weights)

            # Calculate confidence based on (potentially weighted) scores
            code_scores = [r["weighted_relevance"] for r in code_results]
            code_confidences = self.calculate_confidence_batch(code_scores)

            for i, r in enumerate(code_results):
                result.code.append(
                    {
                        "id": r["id"],
                        "chunk_type": r.get("chunk_type", "unknown"),
                        "name": r.get("name"),
                        "filepath": r.get("filepath", ""),
                        "start_line": r.get("start_line", 0),
                        "end_line": r.get("end_line", 0),
                        "tokens": r.get("token_estimate", 0),
                        "relevance": r["weighted_relevance"],  # Use (potentially) weighted score
                        "raw_relevance": r["relevance"],  # Keep raw for debugging
                        "doc_type": r.get("doc_type", DOC_TYPE_CODE),
                        "confidence": code_confidences[i].value if code_confidences else "medium",
                        "content": r.get("content", ""),
                    }
                )
                result.total_tokens_available += r.get("token_estimate", 0)

        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_MEMORY):
            # Search memories, excluding plans (they have their own category)
            memory_results = self.store.search_memory(
                query=query,
                limit=limit,
            )
            # Filter out plans from memory results (they go in the plans category)
            memory_results = [r for r in memory_results if r.get("memory_type") != MEMORY_TYPE_PLAN]

            # Calculate confidence for memory results
            memory_scores = [r["relevance"] for r in memory_results]
            memory_confidences = self.calculate_confidence_batch(memory_scores)

            for i, r in enumerate(memory_results):
                result.memory.append(
                    {
                        "id": r["id"],
                        "memory_type": r.get("memory_type", "discovery"),
                        "observation": r.get("observation", ""),
                        "tokens": r.get("token_estimate", 0),
                        "relevance": r["relevance"],
                        "confidence": (
                            memory_confidences[i].value if memory_confidences else "medium"
                        ),
                    }
                )
                result.total_tokens_available += r.get("token_estimate", 0)

        # Plans search (uses memory collection with type filter)
        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_PLANS):
            plan_results = self.store.search_memory(
                query=query,
                limit=limit,
                memory_types=[MEMORY_TYPE_PLAN],  # Filter to plans only
            )

            # Calculate confidence for plan results
            plan_scores = [r["relevance"] for r in plan_results]
            plan_confidences = self.calculate_confidence_batch(plan_scores)

            for i, r in enumerate(plan_results):
                # Get preview from observation (plan content)
                observation = r.get("observation", "")
                preview = (
                    observation[:DEFAULT_PREVIEW_LENGTH] + "..."
                    if len(observation) > DEFAULT_PREVIEW_LENGTH
                    else observation
                )

                result.plans.append(
                    {
                        "id": r["id"],
                        "relevance": r["relevance"],
                        "confidence": (plan_confidences[i].value if plan_confidences else "medium"),
                        "title": r.get("title", "Untitled Plan"),
                        "preview": preview,
                        "session_id": r.get("session_id"),
                        "created_at": r.get("created_at"),
                        "tokens": r.get("token_estimate", 0),
                    }
                )
                result.total_tokens_available += r.get("token_estimate", 0)

        # Sessions search (uses session_summaries collection in ChromaDB)
        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_SESSIONS):
            session_results = self.store.search_session_summaries(
                query=query,
                limit=limit,
            )

            # Calculate confidence for session results
            session_scores = [r["relevance"] for r in session_results]
            session_confidences = self.calculate_confidence_batch(session_scores)

            for i, r in enumerate(session_results):
                # Get preview from document (the embedded title + summary text)
                document = r.get("document", "")
                preview = (
                    document[:DEFAULT_PREVIEW_LENGTH] + "..."
                    if len(document) > DEFAULT_PREVIEW_LENGTH
                    else document
                )

                result.sessions.append(
                    {
                        "id": r["id"],
                        "relevance": r["relevance"],
                        "confidence": (
                            session_confidences[i].value if session_confidences else "medium"
                        ),
                        "title": r.get("title") or None,
                        "preview": preview,
                        "created_at_epoch": r.get("created_at_epoch", 0),
                    }
                )

        return result

    def fetch(self, ids: list[str]) -> FetchResult:
        """Fetch full content for chunk IDs.

        This is used by the /api/fetch endpoint.

        Args:
            ids: List of chunk IDs to fetch.

        Returns:
            FetchResult with full content for each ID.
        """
        result = FetchResult()

        # Try fetching from code collection
        code_items = self.store.get_by_ids(ids, collection="code")
        for item in code_items:
            content = item.get("content", "")
            tokens = len(content) // CHARS_PER_TOKEN_ESTIMATE
            result.results.append(
                {
                    "id": item["id"],
                    "content": content,
                    "tokens": tokens,
                }
            )
            result.total_tokens += tokens

        # Try fetching from memory collection
        memory_items = self.store.get_by_ids(ids, collection="memory")
        for item in memory_items:
            content = item.get("content", "")
            tokens = len(content) // CHARS_PER_TOKEN_ESTIMATE
            result.results.append(
                {
                    "id": item["id"],
                    "content": content,
                    "tokens": tokens,
                }
            )
            result.total_tokens += tokens

        return result

    def get_task_context(
        self,
        task: str,
        current_files: list[str] | None = None,
        max_tokens: int | None = None,
        project_root: Any | None = None,
        apply_doc_type_weights: bool = True,
    ) -> ContextResult:
        """Get curated context for a task.

        This is used by the /api/context endpoint.

        Combines search results and automatic selection to provide
        optimal context for a given task within token limits.

        Args:
            task: Description of the task.
            current_files: Files currently being worked on.
            max_tokens: Maximum tokens to return.
            project_root: Project root path for guidelines check.
            apply_doc_type_weights: Whether to apply doc_type weighting (default True).
                Set to False when working with specific file types like translations.

        Returns:
            ContextResult with code, memories, and guidelines.
        """
        max_tokens = max_tokens or self.config.max_context_tokens

        result = ContextResult(task=task)

        # Build search query from task + current files
        search_query = task
        if current_files:
            file_names = [f.split("/")[-1] for f in current_files]
            search_query = f"{task} {' '.join(file_names)}"

        # Search for relevant code
        code_results = self.store.search_code(
            query=search_query,
            limit=DEFAULT_CONTEXT_LIMIT,
        )

        # Apply doc_type weighting if enabled
        self._apply_doc_type_weights(code_results, apply_doc_type_weights)

        for r in code_results:
            tokens = r.get("token_estimate", 0)
            if result.total_tokens + tokens > max_tokens:
                break
            result.code.append(
                {
                    "file_path": r.get("filepath", ""),
                    "chunk_type": r.get("chunk_type", "unknown"),
                    "name": r.get("name"),
                    "start_line": r.get("start_line", 0),
                    "relevance": r["weighted_relevance"],
                }
            )
            result.total_tokens += tokens

        # Search for relevant memories
        memory_results = self.store.search_memory(
            query=search_query,
            limit=DEFAULT_CONTEXT_MEMORY_LIMIT,
        )

        for r in memory_results:
            tokens = r.get("token_estimate", 0)
            if result.total_tokens + tokens > max_tokens:
                break
            result.memories.append(
                {
                    "memory_type": r.get("memory_type", "discovery"),
                    "observation": r.get("observation", ""),
                    "relevance": r["relevance"],
                }
            )
            result.total_tokens += tokens

        # Add project guidelines if constitution exists
        if project_root:
            constitution_path = project_root / ".constitution.md"
            if constitution_path.exists():
                result.guidelines.append("Follow project standards in .constitution.md")

        return result

    # =========================================================================
    # Memory Storage (complements retrieval)
    # =========================================================================

    def remember(
        self,
        observation: str,
        memory_type: str = "discovery",
        context: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Store an observation in memory.

        This is used by the /api/remember endpoint.

        Args:
            observation: The observation text to store.
            memory_type: Type of memory (gotcha, bug_fix, decision, discovery, trade_off).
            context: Optional context (e.g., related file path).
            tags: Optional tags for categorization.

        Returns:
            The ID of the stored observation.
        """
        mem_observation = MemoryObservation(
            id=str(uuid4()),
            observation=observation,
            memory_type=memory_type,
            context=context,
            tags=tags,
            created_at=datetime.now(),
        )

        return self.store.add_memory(mem_observation)

    def archive_memory(self, memory_id: str, archived: bool = True) -> bool:
        """Archive or unarchive a memory.

        Args:
            memory_id: ID of the memory to archive/unarchive.
            archived: True to archive, False to unarchive.

        Returns:
            True if the memory was found and updated.
        """
        return self.store.archive_memory(memory_id, archived)

    def list_memories(
        self,
        limit: int = DEFAULT_MEMORY_LIST_LIMIT,
        offset: int = 0,
        memory_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        tag: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_archived: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List stored memories with pagination.

        This is used by the /api/memories endpoint.

        Args:
            limit: Maximum memories to return.
            offset: Pagination offset.
            memory_types: Filter to specific types.
            exclude_types: Types to exclude.
            tag: Filter to memories containing this tag.
            start_date: Filter to memories created on or after this date (ISO format).
            end_date: Filter to memories created on or before this date (ISO format).
            include_archived: If True, include archived memories. Default False.

        Returns:
            Tuple of (memories list, total count).
        """
        return self.store.list_memories(
            limit=limit,
            offset=offset,
            memory_types=memory_types,
            exclude_types=exclude_types,
            tag=tag,
            start_date=start_date,
            end_date=end_date,
            include_archived=include_archived,
        )
