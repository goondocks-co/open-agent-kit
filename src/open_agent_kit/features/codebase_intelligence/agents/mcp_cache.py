"""Shared CI MCP server cache for agent subsystem.

Provides ``CiMcpServerCache`` which caches MCP server configs keyed by
the frozenset of enabled tool names.  Used by both ``AgentExecutor``
and ``InteractiveSessionManager``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.agents.tools import create_ci_mcp_server

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


class CiMcpServerCache:
    """Cache of CI MCP server configs keyed by enabled tool sets.

    Attributes:
        retrieval_engine: RetrievalEngine for tool creation.
        activity_store: ActivityStore for tool creation.
        vector_store: VectorStore for tool creation.
    """

    def __init__(
        self,
        retrieval_engine: RetrievalEngine | None,
        activity_store: ActivityStore | None,
        vector_store: VectorStore | None,
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._activity_store = activity_store
        self._vector_store = vector_store
        self._servers: dict[frozenset[str], Any] = {}

    def get(self, enabled_tools: set[str] | None = None) -> Any:
        """Get or create a CI MCP server for the given tool set.

        Caches servers by the set of enabled tools so agents with
        different ci_access flags get different tool sets.

        Args:
            enabled_tools: Set of tool names to include.

        Returns:
            McpSdkServerConfig instance, or None if unavailable.
        """
        cache_key = frozenset(enabled_tools) if enabled_tools else frozenset()

        if cache_key in self._servers:
            return self._servers[cache_key]

        if self._retrieval_engine is None:
            logger.warning("Cannot create CI MCP server - no retrieval engine")
            return None

        server = create_ci_mcp_server(
            retrieval_engine=self._retrieval_engine,
            activity_store=self._activity_store,
            vector_store=self._vector_store,
            enabled_tools=enabled_tools,
        )
        self._servers[cache_key] = server
        return server
