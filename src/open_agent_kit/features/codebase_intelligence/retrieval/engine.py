"""Retrieval engine implementing progressive disclosure.

The engine uses a 3-layer pattern to manage context efficiently:
1. INDEX layer: Summaries with IDs (~50-100 tokens/result)
2. CONTEXT layer: Related chunks for selected items
3. FETCH layer: Full content for specific IDs

This is the central abstraction for all retrieval operations in CI.
All search functionality (daemon routes, MCP tools, hooks) should use this engine.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from open_agent_kit.features.codebase_intelligence.constants import (
    CONFIDENCE_GAP_BOOST_THRESHOLD,
    CONFIDENCE_HIGH,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_MEDIUM_THRESHOLD,
    CONFIDENCE_MIN_MEANINGFUL_RANGE,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
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

    default_limit: int = 20
    max_context_tokens: int = 2000
    preview_length: int = 200


@dataclass
class SearchResult:
    """Result from a search operation."""

    query: str
    code: list[dict[str, Any]] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
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
    """Engine for semantic retrieval with progressive disclosure.

    This is the central abstraction for all search/retrieval operations.
    It provides:
    - Unified search interface for code and memories
    - Token-aware context assembly
    - Progressive disclosure (index → context → full)

    Implements a 3-layer retrieval pattern:
    - Layer 1 (INDEX): Return summaries to let agent select relevant items
    - Layer 2 (CONTEXT): Return related items for selected chunks
    - Layer 3 (FETCH): Return full content for specific IDs
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
    def get_confidence_stats(scores: list[float]) -> dict[str, Any]:
        """Get statistics about confidence distribution for a result set.

        Useful for debugging and UI display.

        Args:
            scores: List of relevance scores, sorted descending.

        Returns:
            Dictionary with confidence statistics.
        """
        if not scores:
            return {
                "count": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "score_range": 0.0,
                "mean_score": 0.0,
                "std_score": 0.0,
            }

        confidences = RetrievalEngine.calculate_confidence_batch(scores)

        return {
            "count": len(scores),
            "high": sum(1 for c in confidences if c == Confidence.HIGH),
            "medium": sum(1 for c in confidences if c == Confidence.MEDIUM),
            "low": sum(1 for c in confidences if c == Confidence.LOW),
            "score_range": max(scores) - min(scores),
            "mean_score": statistics.mean(scores),
            "std_score": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        }

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

        return [r for r in results if r.get("confidence", "low") in allowed]

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
            if apply_doc_type_weights:
                for r in code_results:
                    doc_type = r.get("doc_type", DOC_TYPE_CODE)
                    weight = DOC_TYPE_WEIGHTS.get(doc_type, 1.0)
                    r["weighted_relevance"] = r["relevance"] * weight

                # Re-sort by weighted relevance
                code_results.sort(key=lambda x: x["weighted_relevance"], reverse=True)
            else:
                # No weighting - use raw relevance
                for r in code_results:
                    r["weighted_relevance"] = r["relevance"]

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
            memory_results = self.store.search_memory(
                query=query,
                limit=limit,
            )

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
            tokens = len(content) // 4
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
            tokens = len(content) // 4
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
            limit=10,
        )

        # Apply doc_type weighting if enabled
        if apply_doc_type_weights:
            for r in code_results:
                doc_type = r.get("doc_type", DOC_TYPE_CODE)
                weight = DOC_TYPE_WEIGHTS.get(doc_type, 1.0)
                r["weighted_relevance"] = r["relevance"] * weight
            code_results.sort(key=lambda x: x["weighted_relevance"], reverse=True)
        else:
            for r in code_results:
                r["weighted_relevance"] = r["relevance"]

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
            limit=5,
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

    def list_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        memory_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List stored memories with pagination.

        This is used by the /api/memories endpoint.

        Args:
            limit: Maximum memories to return.
            offset: Pagination offset.
            memory_types: Filter to specific types.
            exclude_types: Types to exclude.

        Returns:
            Tuple of (memories list, total count).
        """
        return self.store.list_memories(
            limit=limit,
            offset=offset,
            memory_types=memory_types,
            exclude_types=exclude_types,
        )

    # =========================================================================
    # Progressive Disclosure Methods (Layer 1-3)
    # =========================================================================

    def search_index(
        self,
        query: str,
        search_type: str = "all",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Layer 1: Search and return index-level summaries.

        Returns compact summaries (~50-100 tokens each) that let the
        agent decide which items are relevant for deeper exploration.

        Args:
            query: Natural language search query.
            search_type: 'all', 'code', or 'memory'.
            limit: Maximum results per category.

        Returns:
            Dictionary with code and memory results at index level.
        """
        limit = limit or self.config.default_limit

        result: dict[str, Any] = {
            "query": query,
            "code": [],
            "memory": [],
            "total_tokens_available": 0,
        }

        if search_type in ("all", "code"):
            code_results = self.store.search_code(
                query=query,
                limit=limit,
            )
            for r in code_results:
                result["code"].append(
                    {
                        "id": r["id"],
                        "type": r.get("chunk_type", "unknown"),
                        "name": r.get("name", ""),
                        "filepath": r.get("filepath", ""),
                        "lines": f"{r.get('start_line', 0)}-{r.get('end_line', 0)}",
                        "tokens": r.get("token_estimate", 0),
                        "relevance": round(r["relevance"], 2),
                    }
                )
                result["total_tokens_available"] += r.get("token_estimate", 0)

        if search_type in ("all", "memory"):
            memory_results = self.store.search_memory(
                query=query,
                limit=limit,
            )
            for r in memory_results:
                result["memory"].append(
                    {
                        "id": r["id"],
                        "type": r.get("memory_type", "unknown"),
                        "summary": (
                            r["observation"][:100] + "..."
                            if len(r["observation"]) > 100
                            else r["observation"]
                        ),
                        "tokens": r.get("token_estimate", 0),
                        "relevance": round(r["relevance"], 2),
                    }
                )
                result["total_tokens_available"] += r.get("token_estimate", 0)

        return result

    def get_chunk_context(self, chunk_ids: list[str]) -> dict[str, Any]:
        """Layer 2: Get context for selected chunks.

        Returns the selected chunks plus related items that might
        be helpful for understanding them.

        Args:
            chunk_ids: List of chunk IDs to get context for.

        Returns:
            Dictionary with selected chunks and related context.
        """
        result: dict[str, Any] = {
            "chunks": [],
            "related": [],
            "total_tokens": 0,
        }

        # Fetch the requested chunks
        code_chunks = self.store.get_by_ids(chunk_ids, collection="code")
        memory_chunks = self.store.get_by_ids(chunk_ids, collection="memory")

        for chunk in code_chunks:
            preview = chunk.get("content", "")
            if len(preview) > self.config.preview_length:
                preview = preview[: self.config.preview_length] + "..."

            result["chunks"].append(
                {
                    "id": chunk["id"],
                    "type": "code",
                    "name": chunk.get("name", ""),
                    "filepath": chunk.get("filepath", ""),
                    "preview": preview,
                    "tokens": len(chunk.get("content", "")) // 4,
                }
            )
            result["total_tokens"] += len(chunk.get("content", "")) // 4

        for chunk in memory_chunks:
            result["chunks"].append(
                {
                    "id": chunk["id"],
                    "type": "memory",
                    "memory_type": chunk.get("memory_type", ""),
                    "observation": chunk.get("content", ""),
                    "tokens": len(chunk.get("content", "")) // 4,
                }
            )
            result["total_tokens"] += len(chunk.get("content", "")) // 4

        # Find related chunks by searching with first chunk's content
        if code_chunks:
            first_content = code_chunks[0].get("content", "")
            if first_content:
                related = self.store.search_code(
                    query=first_content[:500],
                    limit=5,
                )
                for r in related:
                    if r["id"] not in chunk_ids:
                        result["related"].append(
                            {
                                "id": r["id"],
                                "type": r.get("chunk_type", ""),
                                "name": r.get("name", ""),
                                "filepath": r.get("filepath", ""),
                                "relevance": round(r["relevance"], 2),
                            }
                        )

        return result

    def fetch_full(self, ids: list[str]) -> dict[str, Any]:
        """Layer 3: Fetch full content for specific IDs.

        Returns complete content for the specified items.

        Args:
            ids: List of IDs to fetch.

        Returns:
            Dictionary with full content for each ID.
        """
        result: dict[str, Any] = {
            "items": [],
            "total_tokens": 0,
        }

        # Try both collections
        code_items = self.store.get_by_ids(ids, collection="code")
        memory_items = self.store.get_by_ids(ids, collection="memory")

        for item in code_items:
            content = item.get("content", "")
            result["items"].append(
                {
                    "id": item["id"],
                    "type": "code",
                    "filepath": item.get("filepath", ""),
                    "name": item.get("name", ""),
                    "start_line": item.get("start_line", 0),
                    "end_line": item.get("end_line", 0),
                    "language": item.get("language", ""),
                    "content": content,
                    "tokens": len(content) // 4,
                }
            )
            result["total_tokens"] += len(content) // 4

        for item in memory_items:
            observation = item.get("content", "")
            result["items"].append(
                {
                    "id": item["id"],
                    "type": "memory",
                    "memory_type": item.get("memory_type", ""),
                    "observation": observation,
                    "context": item.get("context", ""),
                    "tokens": len(observation) // 4,
                }
            )
            result["total_tokens"] += len(observation) // 4

        return result
