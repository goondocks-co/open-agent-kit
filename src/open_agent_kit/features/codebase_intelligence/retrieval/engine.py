"""Retrieval engine for semantic search.

This is the central abstraction for all retrieval operations in CI.
All search functionality (daemon routes, MCP tools, hooks) should use this engine.

Provides:
- Unified search interface for code and memories
- Token-aware context assembly
- Model-agnostic confidence scoring (delegated to retrieval.scoring)
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

from open_agent_kit.features.codebase_intelligence.constants import (
    CHARS_PER_TOKEN_ESTIMATE,
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_CONTEXT_MEMORY_LIMIT,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MEMORY_LIST_LIMIT,
    DEFAULT_PREVIEW_LENGTH,
    DEFAULT_SEARCH_LIMIT,
    MEMORY_TYPE_PLAN,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    DOC_TYPE_CODE,
    MemoryObservation,
    VectorStore,
)
from open_agent_kit.features.codebase_intelligence.retrieval.scoring import (
    Confidence,
    apply_doc_type_weights,
    calculate_combined_score,
    calculate_confidence,
    calculate_confidence_batch,
    filter_by_combined_score,
    filter_by_confidence,
    get_importance_level,
)

logger = logging.getLogger(__name__)


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


def _build_code_item(raw: dict, confidence: Confidence) -> dict[str, Any]:
    """Build a normalized code search result dict."""
    return {
        "id": raw["id"],
        "chunk_type": raw.get("chunk_type", "unknown"),
        "name": raw.get("name"),
        "filepath": raw.get("filepath", ""),
        "start_line": raw.get("start_line", 0),
        "end_line": raw.get("end_line", 0),
        "tokens": raw.get("token_estimate", 0),
        "relevance": raw["weighted_relevance"],
        "raw_relevance": raw["relevance"],
        "doc_type": raw.get("doc_type", DOC_TYPE_CODE),
        "confidence": confidence.value,
        "content": raw.get("content", ""),
    }


def _build_memory_item(raw: dict, confidence: Confidence) -> dict[str, Any]:
    """Build a normalized memory search result dict."""
    return {
        "id": raw["id"],
        "memory_type": raw.get("memory_type", "discovery"),
        "observation": raw.get("observation", ""),
        "tokens": raw.get("token_estimate", 0),
        "relevance": raw["relevance"],
        "confidence": confidence.value,
        "status": raw.get("status", "active"),
    }


def _build_plan_item(raw: dict, confidence: Confidence) -> dict[str, Any]:
    """Build a normalized plan search result dict."""
    observation = raw.get("observation", "")
    preview = (
        observation[:DEFAULT_PREVIEW_LENGTH] + "..."
        if len(observation) > DEFAULT_PREVIEW_LENGTH
        else observation
    )
    return {
        "id": raw["id"],
        "relevance": raw["relevance"],
        "confidence": confidence.value,
        "title": raw.get("title", "Untitled Plan"),
        "preview": preview,
        "session_id": raw.get("session_id"),
        "created_at": raw.get("created_at"),
        "tokens": raw.get("token_estimate", 0),
    }


def _build_session_item(raw: dict, confidence: Confidence) -> dict[str, Any]:
    """Build a normalized session search result dict."""
    document = raw.get("document", "")
    preview = (
        document[:DEFAULT_PREVIEW_LENGTH] + "..."
        if len(document) > DEFAULT_PREVIEW_LENGTH
        else document
    )
    return {
        "id": raw["id"],
        "relevance": raw["relevance"],
        "confidence": confidence.value,
        "title": raw.get("title") or None,
        "preview": preview,
        "created_at_epoch": raw.get("created_at_epoch", 0),
    }


class RetrievalEngine:
    """Engine for semantic retrieval.

    This is the central abstraction for all search/retrieval operations.
    It provides:
    - Unified search interface for code and memories
    - Token-aware context assembly
    - Model-agnostic confidence scoring (via retrieval.scoring)
    - Two-phase memory status writes (SQLite + ChromaDB)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        config: RetrievalConfig | None = None,
        activity_store: "ActivityStore | None" = None,
    ):
        self.store = vector_store
        self.config = config or RetrievalConfig()
        self.activity_store = activity_store

    # Backward-compatible static method delegations to scoring module
    calculate_confidence = staticmethod(calculate_confidence)
    calculate_confidence_batch = staticmethod(calculate_confidence_batch)
    filter_by_confidence = staticmethod(filter_by_confidence)
    calculate_combined_score = staticmethod(calculate_combined_score)
    get_importance_level = staticmethod(get_importance_level)
    filter_by_combined_score = staticmethod(filter_by_combined_score)
    _apply_doc_type_weights = staticmethod(apply_doc_type_weights)

    def search(
        self,
        query: str,
        search_type: str = SEARCH_TYPE_ALL,
        limit: int | None = None,
        apply_doc_type_weights: bool = True,
        include_resolved: bool = False,
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
            self._search_code(query, limit, apply_doc_type_weights, result)

        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_MEMORY):
            self._search_memory(query, limit, include_resolved, result)

        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_PLANS):
            self._search_plans(query, limit, result)

        if search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_SESSIONS):
            self._search_sessions(query, limit, result)

        return result

    def _search_code(
        self,
        query: str,
        limit: int,
        weight: bool,
        result: SearchResult,
    ) -> None:
        """Search code collection and append results."""
        code_results = self.store.search_code(query=query, limit=limit)
        self._apply_doc_type_weights(code_results, weight)

        scores = [r["weighted_relevance"] for r in code_results]
        confidences = calculate_confidence_batch(scores)

        for i, r in enumerate(code_results):
            result.code.append(_build_code_item(r, confidences[i]))
            result.total_tokens_available += r.get("token_estimate", 0)

    def _search_memory(
        self,
        query: str,
        limit: int,
        include_resolved: bool,
        result: SearchResult,
    ) -> None:
        """Search memory collection and append results (excluding plans)."""
        memory_filters = None if include_resolved else {"status": "active"}
        memory_results = self.store.search_memory(
            query=query,
            limit=limit,
            metadata_filters=memory_filters,
        )
        memory_results = [r for r in memory_results if r.get("memory_type") != MEMORY_TYPE_PLAN]

        scores = [r["relevance"] for r in memory_results]
        confidences = calculate_confidence_batch(scores)

        for i, r in enumerate(memory_results):
            result.memory.append(_build_memory_item(r, confidences[i]))
            result.total_tokens_available += r.get("token_estimate", 0)

    def _search_plans(
        self,
        query: str,
        limit: int,
        result: SearchResult,
    ) -> None:
        """Search plans (memory collection with type filter) and append results."""
        plan_results = self.store.search_memory(
            query=query,
            limit=limit,
            memory_types=[MEMORY_TYPE_PLAN],
        )

        scores = [r["relevance"] for r in plan_results]
        confidences = calculate_confidence_batch(scores)

        for i, r in enumerate(plan_results):
            result.plans.append(_build_plan_item(r, confidences[i]))
            result.total_tokens_available += r.get("token_estimate", 0)

    def _search_sessions(
        self,
        query: str,
        limit: int,
        result: SearchResult,
    ) -> None:
        """Search session summaries and append results with lineage enrichment."""
        session_results = self.store.search_session_summaries(query=query, limit=limit)

        scores = [r["relevance"] for r in session_results]
        confidences = calculate_confidence_batch(scores)

        for i, r in enumerate(session_results):
            result.sessions.append(_build_session_item(r, confidences[i]))

        # Enrich with lineage metadata from SQLite via ActivityStore
        if self.activity_store and result.sessions:
            self.activity_store.enrich_sessions_with_lineage(result.sessions)

    def fetch(self, ids: list[str]) -> FetchResult:
        """Fetch full content for chunk IDs (used by /api/fetch)."""
        result = FetchResult()

        for collection in ("code", "memory"):
            items = self.store.get_by_ids(ids, collection=collection)
            for item in items:
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
        """Get curated context for a task (used by /api/context)."""
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

        # Search for relevant memories (always filter to active)
        memory_results = self.store.search_memory(
            query=search_query,
            limit=DEFAULT_CONTEXT_MEMORY_LIMIT,
            metadata_filters={"status": "active"},
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
            constitution_path = project_root / "oak" / "constitution.md"
            if constitution_path.exists():
                result.guidelines.append("Follow project standards in oak/constitution.md")

        return result

    def remember(
        self,
        observation: str,
        memory_type: str = "discovery",
        context: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Store an observation in memory (two-phase: ChromaDB + SQLite)."""
        obs_id = str(uuid4())
        now = datetime.now()

        mem_observation = MemoryObservation(
            id=obs_id,
            observation=observation,
            memory_type=memory_type,
            context=context,
            tags=tags,
            created_at=now,
        )

        # Phase 1: ChromaDB (search index)
        self.store.add_memory(mem_observation)

        # Phase 2: SQLite (source of truth)
        if self.activity_store:
            from open_agent_kit.features.codebase_intelligence.activity.store.models import (
                StoredObservation,
            )

            # Resolve session ID: use provided, or find most recent active session
            resolved_session_id = session_id
            if not resolved_session_id:
                try:
                    recent = self.activity_store.get_recent_sessions(limit=1, status="active")
                    if recent:
                        resolved_session_id = recent[0].id
                except Exception:
                    logger.debug("Could not resolve active session for remember()")

            if resolved_session_id:
                from open_agent_kit.features.codebase_intelligence.constants import (
                    ORIGIN_TYPE_AGENT_CREATED,
                )

                stored_obs = StoredObservation(
                    id=obs_id,
                    session_id=resolved_session_id,
                    observation=observation,
                    memory_type=memory_type,
                    context=context,
                    tags=tags,
                    importance=5,
                    created_at=now,
                    embedded=True,  # Already in ChromaDB from phase 1
                    origin_type=ORIGIN_TYPE_AGENT_CREATED,
                )
                self.activity_store.store_observation(stored_obs)
            else:
                logger.warning("No active session found — observation stored in ChromaDB only")

        return obs_id

    def archive_memory(self, memory_id: str, archived: bool = True) -> bool:
        """Archive or unarchive a memory."""
        return self.store.archive_memory(memory_id, archived)

    def resolve_memory(
        self,
        memory_id: str,
        status: str = "resolved",
        resolved_by_session_id: str | None = None,
        superseded_by: str | None = None,
    ) -> bool:
        """Update lifecycle status of a memory (two-phase: SQLite + ChromaDB)."""
        resolved_at = datetime.now(UTC).isoformat() if status != "active" else None

        # Phase 1: Update SQLite (source of truth)
        if self.activity_store:
            self.activity_store.update_observation_status(
                observation_id=memory_id,
                status=status,
                resolved_by_session_id=resolved_by_session_id,
                resolved_at=resolved_at,
                superseded_by=superseded_by,
            )

        # Phase 2: Update ChromaDB (search index)
        result = self.store.update_memory_status(memory_id, status)

        # Phase 3: Emit resolution event for cross-machine propagation
        if status != "active" and self.activity_store:
            try:
                self.activity_store.store_resolution_event(
                    observation_id=memory_id,
                    action=status,
                    resolved_by_session_id=resolved_by_session_id,
                    superseded_by=superseded_by,
                )
            except Exception:
                logger.debug(f"Failed to emit resolution event for {memory_id}", exc_info=True)

        return result

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
        status: str | None = "active",
        include_resolved: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List stored memories with pagination (SQLite preferred, ChromaDB fallback)."""
        if self.activity_store:
            return self.activity_store.list_observations(
                limit=limit,
                offset=offset,
                memory_types=memory_types,
                exclude_types=exclude_types,
                tag=tag,
                start_date=start_date,
                end_date=end_date,
                include_archived=include_archived,
                status=status,
                include_resolved=include_resolved,
            )

        # Fallback to ChromaDB if no activity store (shouldn't happen in practice)
        return self.store.list_memories(
            limit=limit,
            offset=offset,
            memory_types=memory_types,
            exclude_types=exclude_types,
            tag=tag,
            start_date=start_date,
            end_date=end_date,
            include_archived=include_archived,
            status=status,
            include_resolved=include_resolved,
        )
