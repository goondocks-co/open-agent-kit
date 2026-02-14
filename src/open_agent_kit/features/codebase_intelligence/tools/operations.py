"""Core tool operations for CI tools.

This module contains the actual implementation logic for CI tools.
Both MCP handlers and SDK tool wrappers delegate to these operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
    VALID_OBSERVATION_STATUSES,
)
from open_agent_kit.features.codebase_intelligence.tools.formatting import (
    format_context_results,
    format_memory_results,
    format_search_results,
    format_session_results,
    format_stats_results,
)
from open_agent_kit.features.codebase_intelligence.tools.schemas import (
    ContextInput,
    MemoriesInput,
    QueryInput,
    RememberInput,
    SearchInput,
    SessionsInput,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


class ToolOperations:
    """Core operations for CI tools.

    Provides the actual implementation logic that both MCP handlers
    and SDK tool wrappers can use. Returns plain strings formatted
    for LLM consumption.
    """

    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        activity_store: ActivityStore | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        """Initialize operations.

        Args:
            retrieval_engine: RetrievalEngine for search operations.
            activity_store: ActivityStore for session data (optional).
            vector_store: VectorStore for stats (optional).
        """
        self.engine = retrieval_engine
        self.activity_store = activity_store
        self.vector_store = vector_store

    def search(self, args: dict[str, Any]) -> str:
        """Execute search operation.

        Args:
            args: Search arguments (query, search_type, limit).

        Returns:
            Formatted search results as markdown string.

        Raises:
            ValueError: If query is missing.
        """
        input_data = SearchInput(**args)

        if not input_data.query:
            raise ValueError("query is required")

        # Validate search type
        valid_types = (
            SEARCH_TYPE_ALL,
            SEARCH_TYPE_CODE,
            SEARCH_TYPE_MEMORY,
            SEARCH_TYPE_PLANS,
            SEARCH_TYPE_SESSIONS,
        )
        search_type = input_data.search_type
        if search_type not in valid_types:
            search_type = SEARCH_TYPE_ALL

        result = self.engine.search(
            query=input_data.query,
            search_type=search_type,
            limit=input_data.limit,
            include_resolved=input_data.include_resolved,
        )

        return format_search_results(result, query=input_data.query)

    def remember(self, args: dict[str, Any]) -> str:
        """Execute remember operation.

        Args:
            args: Remember arguments (observation, memory_type, context).

        Returns:
            Confirmation message with observation ID.
        """
        input_data = RememberInput(**args)

        observation_id = self.engine.remember(
            observation=input_data.observation,
            memory_type=input_data.memory_type,
            context=input_data.context,
        )

        return (
            f"Observation stored successfully.\n"
            f"- Type: {input_data.memory_type}\n"
            f"- ID: {observation_id}\n"
            f"This will be surfaced in future searches when relevant."
        )

    def get_context(self, args: dict[str, Any]) -> str:
        """Execute context retrieval operation.

        Args:
            args: Context arguments (task, current_files, max_tokens).

        Returns:
            Formatted context as markdown string.
        """
        input_data = ContextInput(**args)

        result = self.engine.get_task_context(
            task=input_data.task,
            current_files=input_data.current_files,
            max_tokens=input_data.max_tokens,
        )

        return format_context_results(
            code=result.code,
            memories=result.memories,
        )

    def list_memories(self, args: dict[str, Any]) -> str:
        """Execute memories listing operation.

        Args:
            args: Memories arguments (memory_type, limit).

        Returns:
            Formatted memories list as markdown string.
        """
        input_data = MemoriesInput(**args)

        memory_types = [input_data.memory_type] if input_data.memory_type else None
        memories, total = self.engine.list_memories(
            limit=input_data.limit,
            memory_types=memory_types,
            status=input_data.status,
            include_resolved=input_data.include_resolved,
        )

        if not memories:
            return "No memories found."

        output = format_memory_results(memories)
        output += f"\n(Showing {len(memories)} of {total} total memories)"
        return output

    def list_sessions(self, args: dict[str, Any]) -> str:
        """Execute sessions listing operation.

        Args:
            args: Sessions arguments (limit, include_summary).

        Returns:
            Formatted sessions list as markdown string.

        Raises:
            ValueError: If activity store is not available.
        """
        if not self.activity_store:
            raise ValueError("Session history not available.")

        input_data = SessionsInput(**args)

        sessions = self.activity_store.get_recent_sessions(
            limit=input_data.limit,
            offset=0,
        )

        if not sessions:
            return "No sessions found."

        # Convert Session objects to dicts for formatting
        session_dicts = [
            {
                "id": s.id,
                "title": s.title,
                "status": s.status or "unknown",
                "started_at": str(s.started_at) if s.started_at else "",
                "summary": s.summary or "" if input_data.include_summary else "",
            }
            for s in sessions
        ]

        output = format_session_results(session_dicts)
        output += f"\n(Showing {len(sessions)} sessions)"
        return output

    def resolve_memory(self, args: dict[str, Any]) -> str:
        """Resolve a memory observation via the retrieval engine.

        Args:
            args: Dict with 'id' (required), 'status' (default 'resolved').

        Returns:
            Confirmation message string.

        Raises:
            ValueError: If ID is missing or status is invalid.
        """
        memory_id = args.get("id")
        if not memory_id:
            raise ValueError("Memory ID is required")

        status = args.get("status", "resolved")
        if status not in VALID_OBSERVATION_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: "
                f"{', '.join(VALID_OBSERVATION_STATUSES)}"
            )

        success = self.engine.resolve_memory(memory_id, status)
        if success:
            return f"Memory {memory_id} marked as {status}."
        return f"Memory {memory_id} not found or could not be updated."

    def get_stats(self, args: dict[str, Any] | None = None) -> str:
        """Execute project stats operation.

        Args:
            args: Optional stats arguments (currently unused).

        Returns:
            Formatted stats as markdown string.
        """
        code_chunks = 0
        unique_files = 0
        memory_count = 0
        observation_count = 0
        status_breakdown: dict[str, int] = {}

        if self.vector_store:
            vs_stats = self.vector_store.get_stats()
            code_chunks = vs_stats.get("code_chunks", 0)
            unique_files = vs_stats.get("unique_files", 0)
            memory_count = vs_stats.get("memory_count", 0)

        if self.activity_store:
            observation_count = self.activity_store.count_observations()
            status_breakdown = self.activity_store.count_observations_by_status()

        return format_stats_results(
            code_chunks=code_chunks,
            unique_files=unique_files,
            memory_count=memory_count,
            observation_count=observation_count,
            status_breakdown=status_breakdown,
        )

    def execute_query(self, args: dict[str, Any]) -> str:
        """Execute a read-only SQL query against the activities database.

        Args:
            args: Query arguments (sql, limit).

        Returns:
            Formatted query results as a markdown table string.

        Raises:
            ValueError: If activity store is not available or SQL is invalid.
        """
        if not self.activity_store:
            raise ValueError("Activity store not available for SQL queries.")

        input_data = QueryInput(**args)

        columns, rows = self.activity_store.execute_readonly_query(
            sql=input_data.sql,
            limit=input_data.limit,
        )

        if not columns:
            return "Query returned no results."

        if not rows:
            return f"Query returned 0 rows.\n\nColumns: {', '.join(columns)}"

        # Format as markdown table
        lines: list[str] = []
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            formatted_cells = []
            for cell in row:
                cell_str = str(cell) if cell is not None else ""
                # Truncate long cell values for readability
                if len(cell_str) > 200:
                    cell_str = cell_str[:197] + "..."
                # Escape pipe characters in cell content
                cell_str = cell_str.replace("|", "\\|")
                formatted_cells.append(cell_str)
            lines.append("| " + " | ".join(formatted_cells) + " |")

        result = "\n".join(lines)
        result += f"\n\n({len(rows)} row{'s' if len(rows) != 1 else ''})"

        # Add hint about epoch timestamps
        epoch_cols = [c for c in columns if "epoch" in c.lower() or "at_epoch" in c.lower()]
        if epoch_cols:
            result += (
                "\n\n**Tip**: Epoch columns can be formatted with "
                "`datetime(col, 'unixepoch', 'localtime')` in your SQL."
            )

        return result
