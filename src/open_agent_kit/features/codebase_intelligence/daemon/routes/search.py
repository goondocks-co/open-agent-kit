"""Search, fetch, remember, and context routes for the CI daemon.

These routes are thin wrappers around RetrievalEngine, handling:
- HTTP request/response transformation
- Error handling and status codes
- Logging

All retrieval logic is centralized in RetrievalEngine for consistency.
"""

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ChunkType,
    CodeResult,
    ContextCodeResult,
    ContextMemoryResult,
    ContextRequest,
    ContextResponse,
    DeleteMemoryResponse,
    DocType,
    FetchRequest,
    FetchResponse,
    FetchResult,
    MemoriesListResponse,
    MemoryListItem,
    MemoryResult,
    MemoryType,
    PlanResult,
    RememberRequest,
    RememberResponse,
    SearchRequest,
    SearchResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.retrieval.engine import Confidence

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


def _get_retrieval_engine() -> tuple["RetrievalEngine", "DaemonState"]:
    """Get retrieval engine or raise appropriate HTTP error."""
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    if not state.embedding_chain or not state.embedding_chain.is_available:
        raise HTTPException(
            status_code=503,
            detail="No embedding providers available. Is Ollama running?",
        )

    engine = state.retrieval_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Retrieval engine not initialized")

    return engine, state


@router.get("/api/search", response_model=SearchResponse)
async def search_get(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    search_type: str = Query(default="all", pattern="^(all|code|memory|plans)$"),
    apply_doc_type_weights: bool = Query(
        default=True, description="Apply doc_type weighting. Disable for translation searches."
    ),
) -> SearchResponse:
    """Perform semantic search (GET endpoint for UI)."""
    request = SearchRequest(
        query=query,
        limit=limit,
        search_type=search_type,
        apply_doc_type_weights=apply_doc_type_weights,
    )
    return await search_post(request)


@router.post("/api/search", response_model=SearchResponse)
async def search_post(request: SearchRequest) -> SearchResponse:
    """Perform semantic search using RetrievalEngine."""
    engine, _state = _get_retrieval_engine()

    logger.info(f"Search request: {request.query}")

    # Use engine for search
    result = engine.search(
        query=request.query,
        search_type=request.search_type,
        limit=request.limit,
        apply_doc_type_weights=request.apply_doc_type_weights,
    )

    # Map engine result to API response models
    code_results = [
        CodeResult(
            id=r["id"],
            chunk_type=ChunkType(r.get("chunk_type", "unknown")),
            name=r.get("name"),
            filepath=r.get("filepath", ""),
            start_line=r.get("start_line", 0),
            end_line=r.get("end_line", 0),
            tokens=r.get("tokens", 0),
            relevance=r["relevance"],
            confidence=Confidence(r.get("confidence", "medium")),
            doc_type=DocType(r.get("doc_type", "code")),
            preview=r.get("content", "")[:200] if r.get("content") else None,
        )
        for r in result.code
    ]

    memory_results = [
        MemoryResult(
            id=r["id"],
            memory_type=MemoryType(r.get("memory_type", "discovery")),
            summary=r.get("observation", ""),
            tokens=r.get("tokens", 0),
            relevance=r["relevance"],
            confidence=Confidence(r.get("confidence", "medium")),
        )
        for r in result.memory
    ]

    plan_results = [
        PlanResult(
            id=r["id"],
            relevance=r["relevance"],
            confidence=Confidence(r.get("confidence", "medium")),
            title=r.get("title", "Untitled Plan"),
            preview=r.get("preview", ""),
            session_id=r.get("session_id"),
            created_at=r.get("created_at"),
            tokens=r.get("tokens", 0),
        )
        for r in result.plans
    ]

    return SearchResponse(
        query=result.query,
        code=code_results,
        memory=memory_results,
        plans=plan_results,
        total_tokens_available=result.total_tokens_available,
    )


@router.post("/api/fetch", response_model=FetchResponse)
async def fetch_content(request: FetchRequest) -> FetchResponse:
    """Fetch full content for chunk IDs using RetrievalEngine."""
    engine, _state = _get_retrieval_engine()

    logger.info(f"Fetch request: {request.ids}")

    # Use engine for fetch
    result = engine.fetch(request.ids)

    # Map to response model
    results = [
        FetchResult(
            id=r["id"],
            content=r["content"],
            tokens=r["tokens"],
        )
        for r in result.results
    ]

    return FetchResponse(
        results=results,
        total_tokens=result.total_tokens,
    )


@router.post("/api/remember", response_model=RememberResponse)
async def remember(request: RememberRequest) -> RememberResponse:
    """Store an observation using RetrievalEngine."""
    engine, _state = _get_retrieval_engine()

    logger.info(f"Remember request: {request.observation[:50]}...")

    # Use engine for storage
    observation_id = engine.remember(
        observation=request.observation,
        memory_type=request.memory_type.value,
        context=request.context,
        tags=request.tags,
    )

    return RememberResponse(
        id=observation_id,
        stored=True,
        message="Observation stored successfully",
    )


@router.get("/api/memories", response_model=MemoriesListResponse)
async def list_memories(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    memory_type: str | None = Query(default=None, description="Filter by memory type"),
    exclude_sessions: bool = Query(default=False, description="Exclude session summaries"),
) -> MemoriesListResponse:
    """List stored memories with pagination and filtering.

    This endpoint provides browsing access to all stored memories,
    complementing the semantic search functionality.
    """
    engine, _state = _get_retrieval_engine()

    # Build filter parameters
    memory_types = [memory_type] if memory_type else None
    exclude_types = ["session_summary"] if exclude_sessions else None

    # Use engine for listing
    memories, total = engine.list_memories(
        limit=limit,
        offset=offset,
        memory_types=memory_types,
        exclude_types=exclude_types,
    )

    # Map to response model
    items = [
        MemoryListItem(
            id=mem["id"],
            memory_type=MemoryType(mem.get("memory_type", "discovery")),
            observation=mem.get("observation", ""),
            context=mem.get("context"),
            tags=mem.get("tags", []),
            created_at=mem.get("created_at"),
        )
        for mem in memories
    ]

    return MemoriesListResponse(
        memories=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/api/context", response_model=ContextResponse)
async def get_context(request: ContextRequest) -> ContextResponse:
    """Get relevant context for a task using RetrievalEngine.

    Combines code search and memory search to provide curated context
    for the given task description.
    """
    engine, state = _get_retrieval_engine()

    logger.info(f"Context request: {request.task[:50]}...")

    # Use engine for context retrieval
    result = engine.get_task_context(
        task=request.task,
        current_files=request.current_files,
        max_tokens=request.max_tokens,
        project_root=state.project_root,
        apply_doc_type_weights=request.apply_doc_type_weights,
    )

    # Map to response models
    code_results = [
        ContextCodeResult(
            file_path=r.get("file_path", ""),
            chunk_type=r.get("chunk_type", "unknown"),
            name=r.get("name"),
            start_line=r.get("start_line", 0),
            relevance=r["relevance"],
        )
        for r in result.code
    ]

    memory_results = [
        ContextMemoryResult(
            memory_type=r.get("memory_type", "discovery"),
            observation=r.get("observation", ""),
            relevance=r["relevance"],
        )
        for r in result.memories
    ]

    return ContextResponse(
        task=result.task,
        code=code_results,
        memories=memory_results,
        guidelines=result.guidelines,
        total_tokens=result.total_tokens,
    )


@router.delete("/api/memories/{memory_id}", response_model=DeleteMemoryResponse)
async def delete_memory(memory_id: str) -> DeleteMemoryResponse:
    """Delete a memory observation from both SQLite and ChromaDB.

    Args:
        memory_id: The UUID of the memory to delete.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.info(f"Deleting memory: {memory_id}")

    try:
        # Check if memory exists in SQLite
        observation = state.activity_store.get_observation(memory_id)
        if not observation:
            raise HTTPException(status_code=404, detail="Memory not found")

        # Delete from SQLite
        deleted = state.activity_store.delete_observation(memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")

        # Delete from ChromaDB
        if state.vector_store:
            state.vector_store.delete_memories([memory_id])

        logger.info(f"Deleted memory {memory_id} from SQLite and ChromaDB")

        return DeleteMemoryResponse(
            success=True,
            deleted_count=1,
            message="Memory deleted successfully",
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
