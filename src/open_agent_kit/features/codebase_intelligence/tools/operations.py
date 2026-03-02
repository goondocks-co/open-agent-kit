"""Core tool operations for CI tools.

This module contains the actual implementation logic for CI tools.
Both MCP handlers and SDK tool wrappers delegate to these operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    ARCHIVE_FILTER_BOTH,
    CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT,
    CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS,
    CLOUD_RELAY_REMOTE_TOOL_BRIDGE_TIMEOUT_SECONDS,
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
    VALID_ARCHIVE_FILTERS,
    VALID_OBSERVATION_STATUSES,
)
from open_agent_kit.features.codebase_intelligence.tools.formatting import (
    extract_text_from_mcp_result,
    format_activity_results,
    format_context_results,
    format_federated_tool_results,
    format_memory_results,
    format_network_search_results,
    format_node_results,
    format_search_results,
    format_session_results,
    format_stats_results,
)
from open_agent_kit.features.codebase_intelligence.tools.schemas import (
    ActivityInput,
    ArchiveInput,
    ContextInput,
    MemoriesInput,
    QueryInput,
    RememberInput,
    ResolveInput,
    SearchInput,
    SessionsInput,
    StatsInput,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.cloud_relay.base import RelayClient
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
        relay_client: RelayClient | None = None,
    ) -> None:
        """Initialize operations.

        Args:
            retrieval_engine: RetrievalEngine for search operations.
            activity_store: ActivityStore for session data (optional).
            vector_store: VectorStore for stats (optional).
            relay_client: RelayClient for network search (optional).
        """
        self.engine = retrieval_engine
        self.activity_store = activity_store
        self.vector_store = vector_store
        self.relay_client = relay_client

    # ------------------------------------------------------------------
    # Shared federation helpers
    # ------------------------------------------------------------------

    def _run_relay_coro(self, coro: Coroutine[Any, Any, Any], timeout: float) -> Any:
        """Run an async relay coroutine from synchronous tool code.

        Uses the running event loop when available (daemon context),
        otherwise falls back to ``loop.run_until_complete``.

        Args:
            coro: Awaitable to execute.
            timeout: Maximum seconds to wait for the result.

        Returns:
            The coroutine's return value.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=timeout)
        return loop.run_until_complete(coro)

    def list_nodes(self, args: dict[str, Any] | None = None) -> str:
        """List connected relay nodes.

        Returns:
            Formatted node list as markdown string.
        """
        if self.relay_client is None:
            return "Cloud relay not connected. No team nodes available."

        nodes = self.relay_client.online_nodes
        if not nodes:
            return "Cloud relay connected but no peer nodes online."

        return format_node_results(nodes)

    def _federate_if_requested(
        self, tool_name: str, args: dict[str, Any], local_result: str
    ) -> str:
        """Append federated results from peer nodes if include_network is set."""
        if not args.get("include_network") or self.relay_client is None:
            return local_result
        try:
            # Strip include_network to prevent recursion on peer nodes
            remote_args = {k: v for k, v in args.items() if k != "include_network"}
            coro = self.relay_client.federate_tool_call(tool_name, remote_args)
            network_result = self._run_relay_coro(
                coro, timeout=CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS
            )
            remote_results = network_result.get("results", [])
            if remote_results:
                # Tag local section with home node machine_id for provenance
                local_mid = self.relay_client.machine_id
                if local_mid:
                    local_result = f"## Local Results [{local_mid}]\n\n{local_result}"
                local_result += "\n\n## Network Results\n\n"
                local_result += format_federated_tool_results(remote_results)
        except Exception:
            logger.warning("Federated tool call failed", exc_info=True)
        return local_result

    def _route_to_node(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """If node_id in args, proxy to remote node. Returns None for local execution."""
        node_id = args.get("node_id")
        if not node_id:
            return None
        if self.relay_client is None:
            return "Error: Cloud relay not connected."
        try:
            # Build args without node_id (avoid mutating caller's dict)
            remote_args = {k: v for k, v in args.items() if k != "node_id"}
            coro = self.relay_client.call_remote_tool(tool_name, remote_args, node_id)
            result = self._run_relay_coro(
                coro, timeout=CLOUD_RELAY_REMOTE_TOOL_BRIDGE_TIMEOUT_SECONDS
            )

            if result.get("error"):
                return f"## Error from {node_id}\n\n{result['error']}"

            text = extract_text_from_mcp_result(result.get("result"))
            return f"## Results from {node_id}\n\n{text}"
        except Exception:
            logger.warning("Remote tool call to %s failed", node_id, exc_info=True)
            return f"Error: Failed to reach node {node_id}."

    # ------------------------------------------------------------------
    # Tool operations
    # ------------------------------------------------------------------

    def search(self, args: dict[str, Any]) -> str:
        """Execute search operation.

        Args:
            args: Search arguments (query, search_type, limit, include_network).

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

        output = format_search_results(result, query=input_data.query)

        # Append network results when requested and relay is available
        if (
            input_data.include_network
            and self.relay_client is not None
            and search_type != SEARCH_TYPE_CODE
        ):
            try:
                coro = self.relay_client.search_network(
                    query=input_data.query,
                    search_type=search_type,
                    limit=input_data.limit,
                )
                network_result = self._run_relay_coro(
                    coro, timeout=CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS
                )
                network_items = network_result.get("results", [])
                if network_items:
                    local_mid = self.relay_client.machine_id
                    if local_mid:
                        output = f"## Local Results [{local_mid}]\n\n{output}"
                    output += "\n\n## Network Results\n\n"
                    output += format_network_search_results(network_items)
            except Exception:
                logger.warning("Network search failed", exc_info=True)

        return output

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
            args: Context arguments (task, current_files, max_tokens, include_network).

        Returns:
            Formatted context as markdown string.
        """
        input_data = ContextInput(**args)

        result = self.engine.get_task_context(
            task=input_data.task,
            current_files=input_data.current_files,
            max_tokens=input_data.max_tokens,
        )

        output = format_context_results(
            code=result.code,
            memories=result.memories,
        )

        # Federate memories only (code stays local — branch/worktree differences).
        if input_data.include_network and self.relay_client is not None:
            try:
                coro = self.relay_client.search_network(
                    query=input_data.task,
                    search_type=SEARCH_TYPE_MEMORY,
                    limit=CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT,
                )
                network_result = self._run_relay_coro(
                    coro, timeout=CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS
                )
                network_items = network_result.get("results", [])
                if network_items:
                    local_mid = self.relay_client.machine_id
                    if local_mid:
                        output = f"## Local Results [{local_mid}]\n\n{output}"
                    output += "\n\n## Network Memories\n\n"
                    output += format_network_search_results(network_items)
            except Exception:
                logger.warning("Network context fetch failed", exc_info=True)

        return output

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
            output = "No memories found."
        else:
            output = format_memory_results(memories)
            output += f"\n(Showing {len(memories)} of {total} total memories)"

        return self._federate_if_requested("oak_memories", args, output)

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

        return self._federate_if_requested("oak_sessions", args, output)

    def resolve_memory(self, args: dict[str, Any]) -> str:
        """Resolve a memory observation.

        Delegates to engine.resolve_memory() which handles the two-phase
        write (SQLite + ChromaDB) as a single operation.

        Args:
            args: Dict with 'id' (required), 'status' (default 'resolved'), 'node_id' (optional).

        Returns:
            Confirmation message string.

        Raises:
            ValueError: If ID is missing or status is invalid.
        """
        # Node-targeted routing
        remote = self._route_to_node("oak_resolve_memory", args)
        if remote is not None:
            return remote

        input_data = ResolveInput(**args)

        if input_data.status not in VALID_OBSERVATION_STATUSES:
            raise ValueError(
                f"Invalid status '{input_data.status}'. Must be one of: "
                f"{', '.join(VALID_OBSERVATION_STATUSES)}"
            )

        success = self.engine.resolve_memory(input_data.id, input_data.status)
        if success:
            return f"Memory {input_data.id} marked as {input_data.status}."
        return f"Memory {input_data.id} not found or could not be updated."

    def get_stats(self, args: dict[str, Any] | None = None) -> str:
        """Execute project stats operation.

        Args:
            args: Optional stats arguments (include_network).

        Returns:
            Formatted stats as markdown string.
        """
        if args is None:
            args = {}

        StatsInput(**args)  # validate input

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

        output = format_stats_results(
            code_chunks=code_chunks,
            unique_files=unique_files,
            memory_count=memory_count,
            observation_count=observation_count,
            status_breakdown=status_breakdown,
        )

        return self._federate_if_requested("oak_stats", args, output)

    def list_activities(self, args: dict[str, Any]) -> str:
        """Execute activity listing operation.

        Args:
            args: Activity arguments (session_id, tool_name, limit, node_id).

        Returns:
            Formatted activity list as markdown string.

        Raises:
            ValueError: If activity store is not available.
        """
        # Node-targeted routing
        remote = self._route_to_node("oak_activity", args)
        if remote is not None:
            return remote

        if not self.activity_store:
            raise ValueError("Activity history not available.")

        input_data = ActivityInput(**args)

        activities = self.activity_store.get_session_activities(
            session_id=input_data.session_id,
            tool_name=input_data.tool_name,
            limit=input_data.limit,
        )

        if not activities:
            return "No activities found."

        # Convert Activity dataclasses to dicts for formatting
        activity_dicts = [
            {
                "tool_name": a.tool_name,
                "success": a.success,
                "file_path": a.file_path,
                "timestamp": str(a.timestamp) if a.timestamp else "",
                "error_message": a.error_message,
                "tool_output_summary": a.tool_output_summary,
            }
            for a in activities
        ]

        output = format_activity_results(activity_dicts)
        output += f"\n(Showing {len(activities)} activities for session {input_data.session_id})"
        return output

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

    def archive_memories(self, args: dict[str, Any]) -> str:
        """Archive observations from ChromaDB search index (keeps them in SQLite).

        Supports archiving by specific IDs or by status filter + age.
        Archived observations stop appearing in vector search results
        but remain in SQLite for historical queries.

        Args:
            args: Archive arguments (ids, status_filter, older_than_days, dry_run, node_id).

        Returns:
            Formatted summary of archival results.

        Raises:
            ValueError: If neither ids nor status_filter is provided,
                or if required stores are unavailable.
        """
        # Node-targeted routing
        remote = self._route_to_node("oak_archive_memories", args)
        if remote is not None:
            return remote

        if not self.vector_store:
            raise ValueError("Vector store not available for archiving.")

        # Defensive: LLMs may send ids as a JSON-encoded string instead of a list
        raw_ids = args.get("ids")
        if isinstance(raw_ids, str):
            import json

            try:
                parsed = json.loads(raw_ids)
                if isinstance(parsed, list):
                    args = {**args, "ids": parsed}
            except (json.JSONDecodeError, TypeError):
                pass

        input_data = ArchiveInput(**args)

        # Must provide either specific IDs or a filter
        if not input_data.ids and not input_data.status_filter:
            raise ValueError(
                "Provide either 'ids' (specific observations) or "
                "'status_filter' + optional 'older_than_days' to select observations."
            )

        ids_to_archive: list[str] = []

        if input_data.ids:
            ids_to_archive = input_data.ids
        elif input_data.status_filter and self.activity_store:
            # Validate status_filter
            if input_data.status_filter not in VALID_ARCHIVE_FILTERS:
                raise ValueError(
                    f"Invalid status_filter '{input_data.status_filter}'. "
                    f"Must be one of: {', '.join(VALID_ARCHIVE_FILTERS)}"
                )

            # Calculate cutoff date if older_than_days is set
            end_date: str | None = None
            if input_data.older_than_days:
                from datetime import datetime, timedelta

                cutoff = datetime.now() - timedelta(days=input_data.older_than_days)
                end_date = cutoff.strftime("%Y-%m-%d")

            # Query for each status in the filter
            statuses = (
                [OBSERVATION_STATUS_RESOLVED, OBSERVATION_STATUS_SUPERSEDED]
                if input_data.status_filter == ARCHIVE_FILTER_BOTH
                else [input_data.status_filter]
            )

            for status in statuses:
                obs_list, _ = self.activity_store.list_observations(
                    limit=10000,
                    status=status,
                    end_date=end_date,
                )
                ids_to_archive.extend(obs["id"] for obs in obs_list if obs.get("id"))
        elif input_data.status_filter and not self.activity_store:
            raise ValueError(
                "Activity store not available — cannot filter by status. "
                "Provide specific 'ids' instead."
            )

        if not ids_to_archive:
            return "No observations matched the criteria. Nothing to archive."

        if input_data.dry_run:
            return (
                f"**Dry run**: {len(ids_to_archive)} observation(s) would be archived.\n"
                f"IDs: {', '.join(ids_to_archive[:20])}"
                + (f"\n... and {len(ids_to_archive) - 20} more" if len(ids_to_archive) > 20 else "")
            )

        # Perform archival via VectorStore
        archived_count = self.vector_store.bulk_archive_memories(ids_to_archive)

        return (
            f"Archived {archived_count} of {len(ids_to_archive)} observation(s) "
            f"from the search index.\n"
            f"These observations remain in SQLite for historical queries "
            f"but will no longer appear in vector search results."
        )
