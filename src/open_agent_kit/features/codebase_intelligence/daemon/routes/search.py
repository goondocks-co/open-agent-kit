"""Search, fetch, remember, and context routes for the CI daemon."""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.codebase_intelligence.constants import (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ChunkType,
    CodeResult,
    ContextCodeResult,
    ContextMemoryResult,
    ContextRequest,
    ContextResponse,
    FetchRequest,
    FetchResponse,
    FetchResult,
    MemoriesListResponse,
    MemoryListItem,
    MemoryResult,
    MemoryType,
    RememberRequest,
    RememberResponse,
    SearchRequest,
    SearchResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.get("/api/search", response_model=SearchResponse)
async def search_get(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    search_type: str = Query(default="all", pattern="^(all|code|memory)$"),
    relevance_threshold: float = Query(default=0.3, ge=0.0, le=1.0),
) -> SearchResponse:
    """Perform semantic search (GET endpoint for UI)."""
    request = SearchRequest(
        query=query,
        limit=limit,
        search_type=search_type,
        relevance_threshold=relevance_threshold,
    )
    result: SearchResponse = await search_post(request)
    return result


@router.post("/api/search", response_model=SearchResponse)
async def search_post(request: SearchRequest) -> SearchResponse:
    """Perform semantic search."""
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    if not state.embedding_chain or not state.embedding_chain.is_available:
        raise HTTPException(
            status_code=503,
            detail="No embedding providers available. Is Ollama running?",
        )

    logger.info(f"Search request: {request.query}")

    code_results = []
    memory_results = []
    total_tokens = 0

    # Search code
    if request.search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_CODE):
        results = state.vector_store.search_code(
            query=request.query,
            limit=request.limit,
            relevance_threshold=request.relevance_threshold,
        )
        for r in results:
            code_results.append(
                CodeResult(
                    id=r["id"],
                    chunk_type=ChunkType(r.get("chunk_type", "unknown")),
                    name=r.get("name"),
                    filepath=r.get("filepath", ""),
                    start_line=r.get("start_line", 0),
                    end_line=r.get("end_line", 0),
                    tokens=r.get("token_estimate", 0),
                    relevance=r["relevance"],
                    preview=r.get("content", "")[:200] if r.get("content") else None,
                )
            )
            total_tokens += r.get("token_estimate", 0)

    # Search memory
    if request.search_type in (SEARCH_TYPE_ALL, SEARCH_TYPE_MEMORY):
        results = state.vector_store.search_memory(
            query=request.query,
            limit=request.limit,
            relevance_threshold=request.relevance_threshold,
        )
        for r in results:
            memory_results.append(
                MemoryResult(
                    id=r["id"],
                    memory_type=MemoryType(r.get("memory_type", "discovery")),
                    summary=r.get("observation", ""),
                    tokens=r.get("token_estimate", 0),
                    relevance=r["relevance"],
                )
            )
            total_tokens += r.get("token_estimate", 0)

    return SearchResponse(
        query=request.query,
        code=code_results,
        memory=memory_results,
        total_tokens_available=total_tokens,
    )


@router.post("/api/fetch", response_model=FetchResponse)
async def fetch_content(request: FetchRequest) -> FetchResponse:
    """Fetch full content for chunk IDs."""
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.info(f"Fetch request: {request.ids}")

    results = []
    total_tokens = 0

    # Try fetching from code collection
    code_items = state.vector_store.get_by_ids(request.ids, collection="code")
    for item in code_items:
        content = item.get("content", "")
        tokens = len(content) // 4
        results.append(
            FetchResult(
                id=item["id"],
                content=content,
                tokens=tokens,
            )
        )
        total_tokens += tokens

    # Try fetching from memory collection
    memory_items = state.vector_store.get_by_ids(request.ids, collection="memory")
    for item in memory_items:
        content = item.get("content", "")
        tokens = len(content) // 4
        results.append(
            FetchResult(
                id=item["id"],
                content=content,
                tokens=tokens,
            )
        )
        total_tokens += tokens

    return FetchResponse(
        results=results,
        total_tokens=total_tokens,
    )


@router.post("/api/remember", response_model=RememberResponse)
async def remember(request: RememberRequest) -> RememberResponse:
    """Store an observation."""
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.info(f"Remember request: {request.observation[:50]}...")

    from open_agent_kit.features.codebase_intelligence.memory.store import MemoryObservation

    observation = MemoryObservation(
        id=str(uuid4()),
        observation=request.observation,
        memory_type=request.memory_type.value,
        context=request.context,
        tags=request.tags,
        created_at=datetime.now(),
    )

    observation_id = state.vector_store.add_memory(observation)

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
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    # Build filter parameters
    memory_types = [memory_type] if memory_type else None
    exclude_types = ["session_summary"] if exclude_sessions else None

    memories, total = state.vector_store.list_memories(
        limit=limit,
        offset=offset,
        memory_types=memory_types,
        exclude_types=exclude_types,
    )

    # Convert to response model
    items = []
    for mem in memories:
        items.append(
            MemoryListItem(
                id=mem["id"],
                memory_type=MemoryType(mem.get("memory_type", "discovery")),
                observation=mem.get("observation", ""),
                context=mem.get("context"),
                tags=mem.get("tags", []),
                created_at=mem.get("created_at"),
            )
        )

    return MemoriesListResponse(
        memories=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/api/context", response_model=ContextResponse)
async def get_context(request: ContextRequest) -> ContextResponse:
    """Get relevant context for a task.

    Combines code search and memory search to provide curated context
    for the given task description.
    """
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    if not state.embedding_chain or not state.embedding_chain.is_available:
        raise HTTPException(
            status_code=503,
            detail="No embedding providers available. Is Ollama running?",
        )

    logger.info(f"Context request: {request.task[:50]}...")

    code_results = []
    memory_results = []
    guidelines = []
    total_tokens = 0

    # Build search query from task + current files
    search_query = request.task
    if request.current_files:
        file_names = [f.split("/")[-1] for f in request.current_files]
        search_query = f"{search_query} {' '.join(file_names)}"

    # Search for relevant code
    code_search = state.vector_store.search_code(
        query=search_query,
        limit=10,
        relevance_threshold=0.3,
    )

    for r in code_search:
        tokens = r.get("token_estimate", 0)
        if total_tokens + tokens > request.max_tokens:
            break
        code_results.append(
            ContextCodeResult(
                file_path=r.get("filepath", ""),
                chunk_type=r.get("chunk_type", "unknown"),
                name=r.get("name"),
                start_line=r.get("start_line", 0),
                relevance=r["relevance"],
            )
        )
        total_tokens += tokens

    # Search for relevant memories
    memory_search = state.vector_store.search_memory(
        query=search_query,
        limit=5,
        relevance_threshold=0.3,
    )

    for r in memory_search:
        tokens = r.get("token_estimate", 0)
        if total_tokens + tokens > request.max_tokens:
            break
        memory_results.append(
            ContextMemoryResult(
                memory_type=r.get("memory_type", "discovery"),
                observation=r.get("observation", ""),
                relevance=r["relevance"],
            )
        )
        total_tokens += tokens

    # Add project guidelines if constitution exists
    if state.project_root:
        constitution_path = state.project_root / ".constitution.md"
        if constitution_path.exists():
            guidelines.append("Follow project standards in .constitution.md")

    return ContextResponse(
        task=request.task,
        code=code_results,
        memories=memory_results,
        guidelines=guidelines,
        total_tokens=total_tokens,
    )
