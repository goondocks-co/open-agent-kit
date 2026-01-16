"""Retrieval engine implementing progressive disclosure.

The engine uses a 3-layer pattern to manage context efficiently:
1. INDEX layer: Summaries with IDs (~50-100 tokens/result)
2. CONTEXT layer: Related chunks for selected items
3. FETCH layer: Full content for specific IDs
"""

import logging
from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    """Configuration for retrieval operations."""

    default_limit: int = 20
    max_context_tokens: int = 2000
    relevance_threshold: float = 0.3
    preview_length: int = 200


class RetrievalEngine:
    """Engine for semantic retrieval with progressive disclosure.

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
                relevance_threshold=self.config.relevance_threshold,
            )
            for r in code_results:
                # Create index-level summary
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
                relevance_threshold=self.config.relevance_threshold,
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

    def get_context(self, chunk_ids: list[str]) -> dict[str, Any]:
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

    def get_task_context(
        self,
        task: str,
        current_files: list[str] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Get curated context for a task.

        Combines search results and automatic selection to provide
        optimal context for a given task within token limits.

        Args:
            task: Description of the task.
            current_files: Files currently being worked on.
            max_tokens: Maximum tokens to return.

        Returns:
            Curated context dictionary.
        """
        max_tokens = max_tokens or self.config.max_context_tokens

        result: dict[str, Any] = {
            "task": task,
            "code_context": [],
            "memory_context": [],
            "total_tokens": 0,
        }

        # Search for relevant code
        code_results = self.store.search_code(
            query=task,
            limit=10,
            relevance_threshold=self.config.relevance_threshold,
        )

        # Add code context within token budget
        for r in code_results:
            tokens = r.get("token_estimate", len(r.get("content", "")) // 4)
            if result["total_tokens"] + tokens > max_tokens * 0.7:  # Reserve 30% for memory
                break

            result["code_context"].append(
                {
                    "filepath": r.get("filepath", ""),
                    "name": r.get("name", ""),
                    "type": r.get("chunk_type", ""),
                    "lines": f"{r.get('start_line', 0)}-{r.get('end_line', 0)}",
                    "content": r.get("content", ""),
                    "relevance": round(r["relevance"], 2),
                }
            )
            result["total_tokens"] += tokens

        # Search for relevant memories
        memory_results = self.store.search_memory(
            query=task,
            limit=5,
            relevance_threshold=self.config.relevance_threshold,
        )

        # Add memory context
        for r in memory_results:
            tokens = r.get("token_estimate", len(r.get("observation", "")) // 4)
            if result["total_tokens"] + tokens > max_tokens:
                break

            result["memory_context"].append(
                {
                    "type": r.get("memory_type", ""),
                    "observation": r.get("observation", ""),
                    "context": r.get("context", ""),
                    "relevance": round(r["relevance"], 2),
                }
            )
            result["total_tokens"] += tokens

        return result
