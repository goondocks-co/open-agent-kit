"""Tests for federated MCP tool operations.

Tests cover:
- list_nodes with various relay states
- _federate_if_requested helper with mock relay client
- _route_to_node helper with mock relay client
- Federation wiring in list_sessions, list_memories, get_stats
- Node-targeted routing in list_activities, resolve_memory, archive_memories
- oak_nodes handler dispatch
- MCP tool definitions: include_network and node_id params
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent_kit.features.team.activity.store.core import ActivityStore
from open_agent_kit.features.team.constants import (
    MCP_TOOL_ACTIVITY,
    MCP_TOOL_ARCHIVE_MEMORIES,
    MCP_TOOL_CONTEXT,
    MCP_TOOL_MEMORIES,
    MCP_TOOL_NODES,
    MCP_TOOL_REMEMBER,
    MCP_TOOL_RESOLVE_MEMORY,
    MCP_TOOL_SEARCH,
    MCP_TOOL_SESSIONS,
    MCP_TOOL_STATS,
)
from open_agent_kit.features.team.daemon.mcp_tools import (
    MCP_TOOLS,
    MCPToolHandler,
)
from open_agent_kit.features.team.tools.formatting import (
    format_federated_tool_results,
    format_node_results,
)
from open_agent_kit.features.team.tools.operations import ToolOperations

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def activity_store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real SQLite database."""
    db_path = tmp_path / "test_activities.db"
    return ActivityStore(db_path=db_path, machine_id="test_machine")


@pytest.fixture
def seeded_store(activity_store: ActivityStore) -> ActivityStore:
    """ActivityStore with test data pre-inserted."""
    conn = activity_store._get_connection()
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, started_at, summary, title) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "session-1",
            "claude",
            "completed",
            1700000000,
            "/test/project",
            "2023-11-14T20:00:00",
            "Worked on authentication",
            "Auth feature",
        ),
    )
    for i in range(2):
        epoch = 1700000000 + i
        conn.execute(
            "INSERT INTO activities (session_id, tool_name, file_path, success, "
            "tool_output_summary, timestamp, timestamp_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "session-1",
                "Edit",
                f"/test/file_{i}.py",
                1,
                f"Edited file {i}",
                "2023-11-14T20:00:00",
                epoch,
            ),
        )
    conn.commit()
    return activity_store


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create a mock RetrievalEngine."""
    engine = MagicMock()
    engine.activity_store = None
    engine.store = None
    engine.search.return_value = MagicMock(code=[], memory=[], plans=[], sessions=[])
    engine.remember.return_value = "test-obs-id"
    engine.get_task_context.return_value = MagicMock(code=[], memories=[])
    engine.list_memories.return_value = ([], 0)
    engine.resolve_memory.return_value = True
    return engine


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Create a mock VectorStore."""
    vs = MagicMock()
    vs.get_stats.return_value = {
        "code_chunks": 100,
        "unique_files": 20,
        "memory_count": 50,
    }
    return vs


@pytest.fixture
def mock_relay_client() -> MagicMock:
    """Create a mock RelayClient with federation support."""
    client = MagicMock()
    client.machine_id = "test-local"
    client.online_nodes = [
        {
            "machine_id": "node-abc",
            "online": True,
            "oak_version": "0.10.0",
            "capabilities": ["obs_sync_v1", "federated_tools_v1"],
        },
        {
            "machine_id": "node-def",
            "online": True,
            "oak_version": "0.9.5",
            "capabilities": ["obs_sync_v1"],
        },
    ]
    client.federate_tool_call = AsyncMock(
        return_value={
            "results": [
                {
                    "from_machine_id": "node-abc",
                    "result": {
                        "content": [{"type": "text", "text": "Remote sessions data"}],
                    },
                },
            ],
        }
    )
    client.call_remote_tool = AsyncMock(
        return_value={
            "result": {
                "content": [{"type": "text", "text": "Remote activity data"}],
            },
        }
    )
    client.search_network = AsyncMock(
        return_value={"results": [{"observation": "Network memory", "machine_id": "node-abc"}]}
    )
    return client


@pytest.fixture
def ops_with_relay(
    mock_engine: MagicMock,
    seeded_store: ActivityStore,
    mock_vector_store: MagicMock,
    mock_relay_client: MagicMock,
) -> ToolOperations:
    """Create ToolOperations with relay client."""
    return ToolOperations(
        retrieval_engine=mock_engine,
        activity_store=seeded_store,
        vector_store=mock_vector_store,
        relay_client=mock_relay_client,
    )


@pytest.fixture
def ops_no_relay(
    mock_engine: MagicMock,
    seeded_store: ActivityStore,
    mock_vector_store: MagicMock,
) -> ToolOperations:
    """Create ToolOperations without relay client."""
    return ToolOperations(
        retrieval_engine=mock_engine,
        activity_store=seeded_store,
        vector_store=mock_vector_store,
        relay_client=None,
    )


# =============================================================================
# list_nodes tests
# =============================================================================


class TestListNodes:
    """Tests for oak_nodes / list_nodes operation."""

    def test_no_relay_returns_not_connected(self, ops_no_relay: ToolOperations) -> None:
        result = ops_no_relay.list_nodes()
        assert "not connected" in result.lower()

    def test_relay_no_nodes(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        mock_relay_client.online_nodes = []
        result = ops_with_relay.list_nodes()
        assert "no peer nodes" in result.lower()

    def test_relay_with_nodes(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.list_nodes()
        assert "node-abc" in result
        assert "node-def" in result
        assert "2 node(s)" in result

    def test_handler_dispatch(self, mock_engine: MagicMock, mock_relay_client: MagicMock) -> None:
        mock_engine.activity_store = None
        mock_engine.store = None
        handler = MCPToolHandler(mock_engine, relay_client=mock_relay_client)
        result = handler.handle_tool_call(MCP_TOOL_NODES, {})
        assert not result.get("isError")
        text = result["content"][0]["text"]
        assert "node-abc" in text


# =============================================================================
# format_node_results tests
# =============================================================================


class TestFormatNodeResults:
    """Tests for format_node_results."""

    def test_empty_nodes(self) -> None:
        result = format_node_results([])
        assert "No nodes" in result

    def test_single_node(self) -> None:
        nodes = [
            {
                "machine_id": "test-node",
                "online": True,
                "oak_version": "1.0.0",
                "capabilities": ["obs_sync_v1"],
            }
        ]
        result = format_node_results(nodes)
        assert "test-node" in result
        assert "v1.0.0" in result
        assert "obs_sync_v1" in result
        assert "[+]" in result

    def test_offline_node(self) -> None:
        nodes = [{"machine_id": "offline-node", "online": False}]
        result = format_node_results(nodes)
        assert "[-]" in result


# =============================================================================
# format_federated_tool_results tests
# =============================================================================


class TestFormatFederatedToolResults:
    """Tests for format_federated_tool_results."""

    def test_empty_results(self) -> None:
        result = format_federated_tool_results([])
        assert "No results" in result

    def test_with_text_content(self) -> None:
        results = [
            {
                "from_machine_id": "node-abc",
                "result": {"content": [{"type": "text", "text": "Hello from peer"}]},
            }
        ]
        result = format_federated_tool_results(results)
        assert "[node-abc]" in result
        assert "Hello from peer" in result

    def test_with_error(self) -> None:
        results = [{"from_machine_id": "node-xyz", "error": "Connection timeout"}]
        result = format_federated_tool_results(results)
        assert "[node-xyz]" in result
        assert "Error" in result
        assert "Connection timeout" in result


# =============================================================================
# _federate_if_requested tests
# =============================================================================


class TestFederateIfRequested:
    """Tests for _federate_if_requested helper."""

    def test_no_include_network(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay._federate_if_requested(MCP_TOOL_SESSIONS, {}, "local data")
        assert result == "local data"

    def test_include_network_false(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay._federate_if_requested(
            MCP_TOOL_SESSIONS, {"include_network": False}, "local data"
        )
        assert result == "local data"

    def test_no_relay_client(self, ops_no_relay: ToolOperations) -> None:
        result = ops_no_relay._federate_if_requested(
            MCP_TOOL_SESSIONS, {"include_network": True}, "local data"
        )
        assert result == "local data"

    def test_federation_appends_network_results(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "results": [
                    {
                        "from_machine_id": "node-abc",
                        "result": {"content": [{"type": "text", "text": "Remote data"}]},
                    }
                ]
            }
            result = ops_with_relay._federate_if_requested(
                MCP_TOOL_SESSIONS, {"include_network": True}, "local data"
            )
            assert "local data" in result
            assert "Local Results [test-local]" in result
            assert "Network Results" in result

    def test_federation_strips_include_network_from_remote_args(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {"results": []}
            ops_with_relay._federate_if_requested(
                MCP_TOOL_SESSIONS, {"include_network": True, "limit": 5}, "local data"
            )
            call_args = mock_relay_client.federate_tool_call.call_args
            remote_args = call_args[0][1]
            assert "include_network" not in remote_args
            assert remote_args["limit"] == 5


# =============================================================================
# _route_to_node tests
# =============================================================================


class TestRouteToNode:
    """Tests for _route_to_node helper."""

    def test_no_node_id_returns_none(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay._route_to_node(MCP_TOOL_ACTIVITY, {"session_id": "s1"})
        assert result is None

    def test_no_relay_returns_error(self, ops_no_relay: ToolOperations) -> None:
        result = ops_no_relay._route_to_node(MCP_TOOL_ACTIVITY, {"node_id": "node-abc"})
        assert result is not None
        assert "not connected" in result.lower()

    def test_routes_to_remote_node(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "result": {
                    "content": [{"type": "text", "text": "Remote response"}],
                }
            }
            args = {"node_id": "node-abc", "session_id": "s1"}
            result = ops_with_relay._route_to_node(MCP_TOOL_ACTIVITY, args)
            assert result is not None
            assert "node-abc" in result
            assert "Remote response" in result
            # args must not be mutated
            assert args == {"node_id": "node-abc", "session_id": "s1"}

    def test_remote_error_returned(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {"error": "Node unreachable"}
            result = ops_with_relay._route_to_node(MCP_TOOL_ACTIVITY, {"node_id": "node-abc"})
            assert result is not None
            assert "Error" in result
            assert "Node unreachable" in result


# =============================================================================
# Federation wiring in tool operations
# =============================================================================


class TestFederationWiring:
    """Tests that include_network and node_id are properly wired into tool operations."""

    def test_list_sessions_without_network(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.list_sessions({"limit": 5})
        # Should work normally without network flag
        assert isinstance(result, str)

    def test_list_memories_without_network(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.list_memories({})
        assert isinstance(result, str)

    def test_get_stats_without_network(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.get_stats({})
        assert "Project Statistics" in result

    def test_get_stats_with_network(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "results": [
                    {
                        "from_machine_id": "node-abc",
                        "result": {"content": [{"type": "text", "text": "Remote stats"}]},
                    }
                ]
            }
            result = ops_with_relay.get_stats({"include_network": True})
            assert "Project Statistics" in result
            assert "Local Results [test-local]" in result
            assert "Network Results" in result

    def test_list_activities_with_node_id(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "result": {
                    "content": [{"type": "text", "text": "Remote activities"}],
                }
            }
            result = ops_with_relay.list_activities({"session_id": "s1", "node_id": "node-abc"})
            assert "node-abc" in result
            assert "Remote activities" in result

    def test_list_activities_local(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.list_activities({"session_id": "session-1"})
        assert "activities" in result.lower()

    def test_resolve_memory_with_node_id(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "result": {
                    "content": [{"type": "text", "text": "Memory resolved remotely"}],
                }
            }
            result = ops_with_relay.resolve_memory({"id": "obs-1", "node_id": "node-abc"})
            assert "node-abc" in result

    def test_resolve_memory_local(self, ops_with_relay: ToolOperations) -> None:
        result = ops_with_relay.resolve_memory({"id": "test-id"})
        assert "resolved" in result.lower() or "not found" in result.lower()

    def test_archive_memories_with_node_id(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "result": {
                    "content": [{"type": "text", "text": "Archived remotely"}],
                }
            }
            result = ops_with_relay.archive_memories({"ids": ["obs-1"], "node_id": "node-abc"})
            assert "node-abc" in result

    def test_get_context_with_network(
        self, ops_with_relay: ToolOperations, mock_relay_client: MagicMock
    ) -> None:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.return_value = {
                "results": [{"observation": "Network memory", "machine_id": "node-abc"}]
            }
            result = ops_with_relay.get_context({"task": "implement auth", "include_network": True})
            assert "Network Memories" in result


# =============================================================================
# MCP tool schema tests for new params
# =============================================================================


class TestMCPToolSchemaFederation:
    """Validates new include_network and node_id params in MCP tool definitions."""

    FEDERABLE_TOOLS = {
        MCP_TOOL_SEARCH,
        MCP_TOOL_SESSIONS,
        MCP_TOOL_MEMORIES,
        MCP_TOOL_CONTEXT,
        MCP_TOOL_STATS,
    }
    NODE_TARGETED_TOOLS = {MCP_TOOL_ACTIVITY, MCP_TOOL_RESOLVE_MEMORY, MCP_TOOL_ARCHIVE_MEMORIES}

    def _get_tool(self, name: str) -> dict:
        for tool in MCP_TOOLS:
            if tool["name"] == name:
                return tool
        raise AssertionError(f"Tool {name} not found in MCP_TOOLS")

    def test_federable_tools_have_include_network(self) -> None:
        for tool_name in self.FEDERABLE_TOOLS:
            tool = self._get_tool(tool_name)
            props = tool["inputSchema"].get("properties", {})
            assert "include_network" in props, f"{tool_name} should have include_network param"
            assert props["include_network"]["type"] == "boolean"

    def test_node_targeted_tools_have_node_id(self) -> None:
        for tool_name in self.NODE_TARGETED_TOOLS:
            tool = self._get_tool(tool_name)
            props = tool["inputSchema"].get("properties", {})
            assert "node_id" in props, f"{tool_name} should have node_id param"
            assert props["node_id"]["type"] == "string"

    def test_oak_nodes_tool_exists(self) -> None:
        tool = self._get_tool(MCP_TOOL_NODES)
        assert "description" in tool
        assert "nodes" in tool["description"].lower()

    def test_oak_nodes_has_empty_schema(self) -> None:
        tool = self._get_tool(MCP_TOOL_NODES)
        props = tool["inputSchema"].get("properties", {})
        assert len(props) == 0

    def test_non_federable_tools_no_include_network(self) -> None:
        non_federable = {
            MCP_TOOL_REMEMBER,
            MCP_TOOL_RESOLVE_MEMORY,
            MCP_TOOL_ACTIVITY,
            MCP_TOOL_ARCHIVE_MEMORIES,
            MCP_TOOL_NODES,
        }
        for tool_name in non_federable:
            tool = self._get_tool(tool_name)
            props = tool["inputSchema"].get("properties", {})
            assert (
                "include_network" not in props
            ), f"{tool_name} should NOT have include_network param"
