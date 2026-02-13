"""Index management routes for the CI daemon."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_INDEXING_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    IndexRequest,
    IndexResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["index"])


@router.get("/api/index/status")
async def index_status() -> dict:
    """Get index status."""
    state = get_state()

    stats = {}
    if state.vector_store:
        try:
            stats = state.vector_store.get_stats()
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Error getting vector store stats: {e}")
            # Return status even if stats retrieval fails

    return {
        "status": state.index_status.status,
        "is_indexing": state.index_status.is_indexing,
        "progress": state.index_status.progress,
        "total": state.index_status.total,
        "total_chunks": stats.get("code_chunks", 0),
        "memory_observations": stats.get("memory_observations", 0),
        "last_indexed": state.index_status.last_indexed,
    }


@router.post("/api/index/rebuild", response_model=IndexResponse)
async def rebuild_index() -> IndexResponse:
    """Trigger full index rebuild (UI endpoint)."""
    request = IndexRequest(full_rebuild=True)
    result: IndexResponse = await build_index(request)
    return result


@router.post("/api/index/build", response_model=IndexResponse)
async def build_index(request: IndexRequest) -> IndexResponse:
    """Trigger index build."""
    state = get_state()

    if not state.indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")

    # Use lock to prevent race condition between concurrent requests
    if state.index_lock is None:
        raise HTTPException(status_code=503, detail="Daemon not fully initialized")

    async with state.index_lock:
        if state.index_status.is_indexing:
            raise HTTPException(status_code=409, detail="Indexing already in progress")

        logger.info(f"Index build request: full_rebuild={request.full_rebuild}")

    try:
        loop = asyncio.get_event_loop()

        # Run unified index build in executor with timeout
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: state.run_index_build(full_rebuild=request.full_rebuild),
            ),
            timeout=DEFAULT_INDEXING_TIMEOUT_SECONDS,
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Index build failed")

        return IndexResponse(
            status="completed",
            chunks_indexed=result.chunks_indexed,
            files_processed=result.files_processed,
            duration_seconds=result.duration_seconds,
        )

    except TimeoutError:
        logger.error(f"Index build timed out after {DEFAULT_INDEXING_TIMEOUT_SECONDS}s")
        state.index_status.set_error()
        raise HTTPException(
            status_code=504,
            detail=f"Indexing timed out after {DEFAULT_INDEXING_TIMEOUT_SECONDS}s",
        ) from None

    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Index build failed: {e}")
        state.index_status.set_error()
        raise HTTPException(status_code=500, detail=str(e)) from e
