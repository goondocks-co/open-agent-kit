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
    BulkAction,
    BulkMemoriesRequest,
    BulkMemoriesResponse,
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


@router.get("/api/memories/tags")
async def list_memory_tags() -> dict:
    """Get all unique tags used across memories.

    Returns:
        Dictionary with list of unique tags sorted alphabetically.
    """
    engine, _state = _get_retrieval_engine()

    # Fetch all memories to extract unique tags
    # This is not ideal for large collections but works for current scale
    memories, _total = engine.list_memories(limit=1000, offset=0)

    tags_set: set[str] = set()
    for mem in memories:
        tags_set.update(mem.get("tags", []))

    return {"tags": sorted(tags_set)}


@router.post("/api/memories/{memory_id}/archive")
async def archive_memory(memory_id: str) -> dict:
    """Archive a memory.

    Archived memories are hidden from the default list view but not deleted.
    """
    engine, _state = _get_retrieval_engine()
    success = engine.archive_memory(memory_id, archived=True)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"success": True, "message": "Memory archived"}


@router.post("/api/memories/{memory_id}/unarchive")
async def unarchive_memory(memory_id: str) -> dict:
    """Unarchive a memory.

    Restores a previously archived memory to the active list.
    """
    engine, _state = _get_retrieval_engine()
    success = engine.archive_memory(memory_id, archived=False)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"success": True, "message": "Memory unarchived"}


@router.get("/api/memories", response_model=MemoriesListResponse)
async def list_memories(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    memory_type: str | None = Query(default=None, description="Filter by memory type"),
    tag: str | None = Query(default=None, description="Filter by tag"),
    start_date: str | None = Query(default=None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="Filter by end date (YYYY-MM-DD)"),
    include_archived: bool = Query(default=False, description="Include archived memories"),
    exclude_sessions: bool = Query(default=False, description="Exclude session summaries"),
) -> MemoriesListResponse:
    """List stored memories with pagination and filtering.

    This endpoint provides browsing access to all stored memories,
    complementing the semantic search functionality.
    """
    engine, _state = _get_retrieval_engine()

    # Build filter parameters
    memory_types = [memory_type] if memory_type else None
    # Always exclude plans from memories view - they have their own dedicated tab
    exclude_types = ["plan"]
    if exclude_sessions:
        exclude_types.append("session_summary")

    # Use engine for listing
    memories, total = engine.list_memories(
        limit=limit,
        offset=offset,
        memory_types=memory_types,
        exclude_types=exclude_types,
        tag=tag,
        start_date=start_date,
        end_date=end_date,
        include_archived=include_archived,
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
            archived=mem.get("archived", False),
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

    Handles two types of memories:
    - Regular memories (UUID): Stored in SQLite memory_observations + ChromaDB
    - Plan memories (plan-{batch_id}): Stored only in ChromaDB, reset plan_embedded flag

    Args:
        memory_id: The UUID or plan ID of the memory to delete.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.info(f"Deleting memory: {memory_id}")

    try:
        # Check if this is a plan memory (indexed from prompt_batches)
        if memory_id.startswith("plan-"):
            # Plans are only stored in ChromaDB, not SQLite memory_observations
            if not state.vector_store:
                raise HTTPException(status_code=503, detail="Vector store not initialized")

            # Delete from ChromaDB
            state.vector_store.delete_memories([memory_id])

            # Reset the plan_embedded flag so it can be re-indexed if needed
            try:
                batch_id_str = memory_id.replace("plan-", "")
                batch_id = int(batch_id_str)
                state.activity_store.mark_plan_unembedded(batch_id)
            except (ValueError, AttributeError):
                # If batch_id extraction fails, just log and continue
                logger.warning(f"Could not reset plan_embedded flag for {memory_id}")

            logger.info(f"Deleted plan memory {memory_id} from ChromaDB")

            return DeleteMemoryResponse(
                success=True,
                deleted_count=1,
                message="Plan memory deleted successfully",
            )

        # Regular memory - check if it exists in SQLite
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


@router.post("/api/memories/bulk", response_model=BulkMemoriesResponse)
async def bulk_memory_operation(request: BulkMemoriesRequest) -> BulkMemoriesResponse:
    """Perform bulk operations on multiple memories.

    Supported actions:
    - delete: Delete selected memories
    - archive: Archive selected memories
    - unarchive: Unarchive selected memories
    - add_tag: Add a tag to selected memories (requires tag field)
    - remove_tag: Remove a tag from selected memories (requires tag field)
    """
    state = get_state()

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.info(f"Bulk operation: {request.action} on {len(request.memory_ids)} memories")

    try:
        affected_count = 0
        action_name = request.action.value

        if request.action == BulkAction.DELETE:
            # Separate plan IDs from regular memory IDs
            plan_ids = [mid for mid in request.memory_ids if mid.startswith("plan-")]
            regular_ids = [mid for mid in request.memory_ids if not mid.startswith("plan-")]

            # Delete regular memories from SQLite
            if state.activity_store and regular_ids:
                for memory_id in regular_ids:
                    if state.activity_store.delete_observation(memory_id):
                        affected_count += 1

            # Mark plans as unembedded in SQLite
            if state.activity_store and plan_ids:
                for plan_id in plan_ids:
                    try:
                        batch_id = int(plan_id.replace("plan-", ""))
                        state.activity_store.mark_plan_unembedded(batch_id)
                        affected_count += 1
                    except (ValueError, AttributeError):
                        logger.warning(f"Could not reset plan_embedded for {plan_id}")

            # Delete all from ChromaDB
            state.vector_store.delete_memories(request.memory_ids)

        elif request.action == BulkAction.ARCHIVE:
            affected_count = state.vector_store.bulk_archive_memories(
                request.memory_ids, archived=True
            )

        elif request.action == BulkAction.UNARCHIVE:
            affected_count = state.vector_store.bulk_archive_memories(
                request.memory_ids, archived=False
            )

        elif request.action == BulkAction.ADD_TAG:
            if not request.tag:
                raise HTTPException(status_code=400, detail="Tag is required for add_tag action")
            affected_count = state.vector_store.add_tag_to_memories(request.memory_ids, request.tag)

        elif request.action == BulkAction.REMOVE_TAG:
            if not request.tag:
                raise HTTPException(status_code=400, detail="Tag is required for remove_tag action")
            affected_count = state.vector_store.remove_tag_from_memories(
                request.memory_ids, request.tag
            )

        return BulkMemoriesResponse(
            success=True,
            affected_count=affected_count,
            message=f"Successfully {action_name}d {affected_count} memories",
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Bulk operation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
