"""End-to-end smoke tests for federated MCP tool architecture.

Exercises every federation path through the full MCPToolHandler dispatch,
verifying that the simplify refactors (constants, _run_relay_coro,
extract_text_from_mcp_result, non-mutation, ResolveInput wiring) all
work together correctly.

Unlike test_federation.py which tests individual methods in isolation,
these tests call MCPToolHandler.handle_tool_call() -- the same entry
point used by the daemon when a real agent makes an MCP request.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS,
    CLOUD_RELAY_REMOTE_TOOL_BRIDGE_TIMEOUT_SECONDS,
    SEARCH_TYPE_MEMORY,
)
from open_agent_kit.features.codebase_intelligence.daemon.mcp_tools import MCPToolHandler
from open_agent_kit.features.codebase_intelligence.tools.formatting import (
    extract_text_from_mcp_result,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def activity_store(tmp_path: Path) -> ActivityStore:
    db_path = tmp_path / "smoke_activities.db"
    return ActivityStore(db_path=db_path, machine_id="smoke_machine")


@pytest.fixture
def seeded_store(activity_store: ActivityStore) -> ActivityStore:
    conn = activity_store._get_connection()
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, "
        "started_at, summary, title) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "smoke-session-1",
            "claude",
            "completed",
            1700000000,
            "/test/project",
            "2023-11-14T20:00:00",
            "Smoke test session",
            "Smoke session",
        ),
    )
    conn.execute(
        "INSERT INTO activities (session_id, tool_name, file_path, success, "
        "tool_output_summary, timestamp, timestamp_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "smoke-session-1",
            "Edit",
            "/test/smoke.py",
            1,
            "Edited smoke file",
            "2023-11-14T20:00:00",
            1700000000,
        ),
    )
    conn.commit()
    return activity_store


@pytest.fixture
def mock_engine() -> MagicMock:
    engine = MagicMock()
    engine.activity_store = None
    engine.store = None
    engine.search.return_value = MagicMock(code=[], memory=[], plans=[], sessions=[])
    engine.remember.return_value = "smoke-obs-id"
    engine.get_task_context.return_value = MagicMock(code=[], memories=[])
    engine.list_memories.return_value = ([], 0)
    engine.resolve_memory.return_value = True
    return engine


@pytest.fixture
def mock_vector_store() -> MagicMock:
    vs = MagicMock()
    vs.get_stats.return_value = {
        "code_chunks": 42,
        "unique_files": 10,
        "memory_count": 5,
    }
    return vs


@pytest.fixture
def mock_relay_client() -> MagicMock:
    client = MagicMock()
    client.machine_id = "smoke-local"
    client.online_nodes = [
        {
            "machine_id": "smoke-node-1",
            "online": True,
            "oak_version": "0.10.0",
            "capabilities": ["obs_sync_v1", "federated_tools_v1"],
        },
        {
            "machine_id": "smoke-node-2",
            "online": True,
            "oak_version": "0.10.0",
            "capabilities": ["obs_sync_v1", "federated_tools_v1"],
        },
    ]
    client.federate_tool_call = AsyncMock(
        return_value={
            "results": [
                {
                    "from_machine_id": "smoke-node-1",
                    "result": {
                        "content": [{"type": "text", "text": "Peer data from node-1"}],
                    },
                },
                {
                    "from_machine_id": "smoke-node-2",
                    "result": {
                        "content": [{"type": "text", "text": "Peer data from node-2"}],
                    },
                },
            ],
        }
    )
    client.call_remote_tool = AsyncMock(
        return_value={
            "result": {
                "content": [{"type": "text", "text": "Remote tool output"}],
            },
        }
    )
    client.search_network = AsyncMock(
        return_value={
            "results": [
                {"observation": "Network memory X", "machine_id": "smoke-node-1"},
                {"observation": "Network memory Y", "machine_id": "smoke-node-2"},
            ]
        }
    )
    return client


@pytest.fixture
def handler(
    mock_engine: MagicMock,
    seeded_store: ActivityStore,
    mock_vector_store: MagicMock,
    mock_relay_client: MagicMock,
) -> MCPToolHandler:
    """MCPToolHandler wired with all stores and relay -- the full production path.

    MCPToolHandler extracts stores from the engine via getattr, so we set
    them as attributes on the mock engine.
    """
    mock_engine.activity_store = seeded_store
    mock_engine.store = mock_vector_store
    return MCPToolHandler(mock_engine, relay_client=mock_relay_client)


def _text(result: dict) -> str:
    """Extract text from MCP result dict."""
    assert not result.get("isError"), f"Tool returned error: {result}"
    return result["content"][0]["text"]


# =============================================================================
# 1. oak_nodes -- discovery tool
# =============================================================================


class TestOakNodesSmoke:
    def test_returns_both_nodes(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_nodes", {})
        text = _text(result)
        assert "smoke-node-1" in text
        assert "smoke-node-2" in text
        assert "2 node(s)" in text

    def test_empty_args_accepted(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_nodes", {})
        assert not result.get("isError")


# =============================================================================
# 2. Federated tools (include_network=true fan-out)
# =============================================================================


class TestFederatedFanOutSmoke:
    """Every federable tool through MCPToolHandler with include_network=true."""

    def _patch_loop(self, relay_return: dict):
        """Context manager that patches asyncio loop for _run_relay_coro."""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = relay_return
        return patch("asyncio.get_event_loop", return_value=mock_loop)

    def test_oak_sessions_federates(self, handler: MCPToolHandler) -> None:
        federated_return = {
            "results": [
                {
                    "from_machine_id": "smoke-node-1",
                    "result": {"content": [{"type": "text", "text": "Remote sessions"}]},
                }
            ]
        }
        with self._patch_loop(federated_return):
            result = handler.handle_tool_call("oak_sessions", {"limit": 5, "include_network": True})
        text = _text(result)
        assert "sessions" in text.lower()
        assert "Local Results [smoke-local]" in text
        assert "Network Results" in text

    def test_oak_memories_federates(self, handler: MCPToolHandler) -> None:
        federated_return = {
            "results": [
                {
                    "from_machine_id": "smoke-node-1",
                    "result": {"content": [{"type": "text", "text": "Remote memories"}]},
                }
            ]
        }
        with self._patch_loop(federated_return):
            result = handler.handle_tool_call("oak_memories", {"include_network": True})
        text = _text(result)
        assert "Local Results [smoke-local]" in text
        assert "Network Results" in text

    def test_oak_stats_federates(self, handler: MCPToolHandler) -> None:
        federated_return = {
            "results": [
                {
                    "from_machine_id": "smoke-node-1",
                    "result": {"content": [{"type": "text", "text": "Remote stats"}]},
                }
            ]
        }
        with self._patch_loop(federated_return):
            result = handler.handle_tool_call("oak_stats", {"include_network": True})
        text = _text(result)
        assert "Project Statistics" in text
        assert "Local Results [smoke-local]" in text
        assert "Network Results" in text

    def test_oak_search_federates(
        self, handler: MCPToolHandler, mock_relay_client: MagicMock
    ) -> None:
        network_return = {
            "results": [{"observation": "Found on network", "machine_id": "smoke-node-1"}]
        }
        with self._patch_loop(network_return):
            result = handler.handle_tool_call(
                "oak_search", {"query": "authentication", "include_network": True}
            )
        text = _text(result)
        assert "Local Results [smoke-local]" in text
        assert "Network Results" in text

    def test_oak_context_federates_memories_only(
        self, handler: MCPToolHandler, mock_relay_client: MagicMock
    ) -> None:
        network_return = {
            "results": [{"observation": "Network memory", "machine_id": "smoke-node-1"}]
        }
        with self._patch_loop(network_return):
            result = handler.handle_tool_call(
                "oak_context", {"task": "implement auth", "include_network": True}
            )
        text = _text(result)
        assert "Local Results [smoke-local]" in text
        assert "Network Memories" in text

    def test_include_network_false_skips_federation(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_sessions", {"limit": 5, "include_network": False})
        text = _text(result)
        assert "Network Results" not in text
        assert "Local Results" not in text

    def test_include_network_missing_skips_federation(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_stats", {})
        text = _text(result)
        assert "Network Results" not in text
        assert "Local Results" not in text


# =============================================================================
# 3. Node-targeted tools (node_id routing)
# =============================================================================


class TestNodeTargetedSmoke:
    """Every node-targeted tool through MCPToolHandler with node_id."""

    def _patch_loop(self, relay_return: dict):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = relay_return
        return patch("asyncio.get_event_loop", return_value=mock_loop)

    def test_oak_activity_routes_to_node(self, handler: MCPToolHandler) -> None:
        remote_return = {"result": {"content": [{"type": "text", "text": "Activities from node"}]}}
        with self._patch_loop(remote_return):
            result = handler.handle_tool_call(
                "oak_activity", {"session_id": "s1", "node_id": "smoke-node-1"}
            )
        text = _text(result)
        assert "smoke-node-1" in text
        assert "Activities from node" in text

    def test_oak_resolve_memory_routes_to_node(self, handler: MCPToolHandler) -> None:
        remote_return = {"result": {"content": [{"type": "text", "text": "Resolved on remote"}]}}
        with self._patch_loop(remote_return):
            result = handler.handle_tool_call(
                "oak_resolve_memory", {"id": "obs-1", "node_id": "smoke-node-1"}
            )
        text = _text(result)
        assert "smoke-node-1" in text
        assert "Resolved on remote" in text

    def test_oak_archive_memories_routes_to_node(self, handler: MCPToolHandler) -> None:
        remote_return = {"result": {"content": [{"type": "text", "text": "Archived on remote"}]}}
        with self._patch_loop(remote_return):
            result = handler.handle_tool_call(
                "oak_archive_memories", {"ids": ["obs-1"], "node_id": "smoke-node-1"}
            )
        text = _text(result)
        assert "smoke-node-1" in text
        assert "Archived on remote" in text

    def test_oak_activity_local_when_no_node_id(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_activity", {"session_id": "smoke-session-1"})
        text = _text(result)
        assert "activities" in text.lower()
        assert "smoke-session-1" in text

    def test_node_id_does_not_mutate_caller_args(self, handler: MCPToolHandler) -> None:
        remote_return = {"result": {"content": [{"type": "text", "text": "ok"}]}}
        args = {"session_id": "s1", "node_id": "smoke-node-1"}
        with self._patch_loop(remote_return):
            handler.handle_tool_call("oak_activity", args)
        assert "node_id" in args
        assert args["node_id"] == "smoke-node-1"

    def test_remote_error_surfaces_in_result(self, handler: MCPToolHandler) -> None:
        error_return = {"error": "Node offline"}
        with self._patch_loop(error_return):
            result = handler.handle_tool_call(
                "oak_activity", {"session_id": "s1", "node_id": "smoke-node-1"}
            )
        text = _text(result)
        assert "Error" in text
        assert "Node offline" in text


# =============================================================================
# 4. extract_text_from_mcp_result
# =============================================================================


class TestExtractTextSmoke:
    def test_standard_mcp_content(self) -> None:
        result = {"content": [{"type": "text", "text": "Hello"}]}
        assert extract_text_from_mcp_result(result) == "Hello"

    def test_multi_text_joined(self) -> None:
        result = {
            "content": [
                {"type": "text", "text": "Line 1"},
                {"type": "text", "text": "Line 2"},
            ]
        }
        assert extract_text_from_mcp_result(result) == "Line 1\nLine 2"

    def test_non_text_items_skipped(self) -> None:
        result = {
            "content": [
                {"type": "image", "data": "..."},
                {"type": "text", "text": "Only this"},
            ]
        }
        assert extract_text_from_mcp_result(result) == "Only this"

    def test_plain_string_passthrough(self) -> None:
        assert extract_text_from_mcp_result("plain") == "plain"

    def test_none_returns_empty(self) -> None:
        assert extract_text_from_mcp_result(None) == ""

    def test_dict_without_content_key(self) -> None:
        result = {"data": "something"}
        assert "data" in extract_text_from_mcp_result(result)

    def test_empty_content_list(self) -> None:
        result = {"content": []}
        text = extract_text_from_mcp_result(result)
        assert isinstance(text, str)


# =============================================================================
# 5. Constants validation
# =============================================================================


class TestConstantsSmoke:
    def test_federation_bridge_timeout_is_positive(self) -> None:
        assert CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS > 0

    def test_remote_tool_bridge_timeout_is_positive(self) -> None:
        assert CLOUD_RELAY_REMOTE_TOOL_BRIDGE_TIMEOUT_SECONDS > 0

    def test_remote_timeout_greater_than_federation(self) -> None:
        assert (
            CLOUD_RELAY_REMOTE_TOOL_BRIDGE_TIMEOUT_SECONDS
            >= CLOUD_RELAY_FEDERATION_BRIDGE_TIMEOUT_SECONDS
        )

    def test_search_type_memory_constant(self) -> None:
        assert SEARCH_TYPE_MEMORY == "memory"


# =============================================================================
# 6. _run_relay_coro helper
# =============================================================================


class TestRunRelayCoroSmoke:
    def test_running_loop_uses_run_coroutine_threadsafe(
        self,
        handler: MCPToolHandler,
    ) -> None:
        ops = handler.ops
        mock_coro = AsyncMock(return_value={"results": []})()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_future = MagicMock()
            mock_future.result.return_value = {"results": []}
            mock_get_loop.return_value = mock_loop

            with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future) as mock_rcts:
                result = ops._run_relay_coro(mock_coro, timeout=5.0)

            mock_rcts.assert_called_once_with(mock_coro, mock_loop)
            mock_future.result.assert_called_once_with(timeout=5.0)
            assert result == {"results": []}

    def test_stopped_loop_uses_run_until_complete(
        self,
        handler: MCPToolHandler,
    ) -> None:
        ops = handler.ops
        mock_coro = AsyncMock(return_value={"data": "ok"})()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = False
            mock_loop.run_until_complete.return_value = {"data": "ok"}
            mock_get_loop.return_value = mock_loop

            result = ops._run_relay_coro(mock_coro, timeout=5.0)

        mock_loop.run_until_complete.assert_called_once_with(mock_coro)
        assert result == {"data": "ok"}


# =============================================================================
# 7. ResolveInput wiring
# =============================================================================


class TestResolveInputWiringSmoke:
    def test_resolve_validates_via_schema(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call("oak_resolve_memory", {})
        assert result.get("isError")
        assert "error" in result["content"][0]["text"].lower()

    def test_resolve_invalid_status_rejected(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call(
            "oak_resolve_memory", {"id": "obs-1", "status": "invalid_status"}
        )
        assert result.get("isError")
        assert "invalid" in result["content"][0]["text"].lower()

    def test_resolve_valid_call(self, handler: MCPToolHandler) -> None:
        result = handler.handle_tool_call(
            "oak_resolve_memory", {"id": "any-obs-id", "status": "resolved"}
        )
        text = _text(result)
        assert "resolved" in text.lower()


# =============================================================================
# 8. Online nodes property on base class
# =============================================================================


class TestOnlineNodesPropertySmoke:
    def test_relay_client_has_online_nodes(self, mock_relay_client: MagicMock) -> None:
        assert hasattr(mock_relay_client, "online_nodes")
        assert len(mock_relay_client.online_nodes) == 2

    def test_base_class_default(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.base import (
            RelayClient,
        )

        assert hasattr(RelayClient, "online_nodes")


# =============================================================================
# 9. Full round-trip: multi-node federation through handler
# =============================================================================


class TestFullRoundTripSmoke:
    """Simulate a cloud agent calling multiple tools in sequence."""

    def _patch_loop(self, relay_return: dict):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = relay_return
        return patch("asyncio.get_event_loop", return_value=mock_loop)

    def test_discovery_then_federated_then_targeted(self, handler: MCPToolHandler) -> None:
        """Agent workflow: discover nodes -> federated search -> targeted activity."""
        # Step 1: Discover nodes
        nodes_result = handler.handle_tool_call("oak_nodes", {})
        nodes_text = _text(nodes_result)
        assert "smoke-node-1" in nodes_text
        assert "smoke-node-2" in nodes_text

        # Step 2: Federated search
        search_return = {
            "results": [{"observation": "Found something", "machine_id": "smoke-node-1"}]
        }
        with self._patch_loop(search_return):
            search_result = handler.handle_tool_call(
                "oak_search", {"query": "auth bug", "include_network": True}
            )
        search_text = _text(search_result)
        assert "Local Results [smoke-local]" in search_text
        assert "Network Results" in search_text

        # Step 3: Target a specific node for activity
        activity_return = {
            "result": {"content": [{"type": "text", "text": "Node-1 activities: Edit auth.py"}]}
        }
        with self._patch_loop(activity_return):
            activity_result = handler.handle_tool_call(
                "oak_activity", {"session_id": "s1", "node_id": "smoke-node-1"}
            )
        activity_text = _text(activity_result)
        assert "smoke-node-1" in activity_text
        assert "Edit auth.py" in activity_text

    def test_all_10_tools_callable(self, handler: MCPToolHandler) -> None:
        """Every registered tool can be called without crashing."""
        tool_args = {
            "oak_search": {"query": "test"},
            "oak_remember": {"observation": "test memory"},
            "oak_context": {"task": "test task"},
            "oak_resolve_memory": {"id": "any-obs-id"},
            "oak_sessions": {"limit": 5},
            "oak_memories": {},
            "oak_stats": {},
            "oak_activity": {"session_id": "smoke-session-1"},
            "oak_archive_memories": {"ids": ["any-obs-id"], "dry_run": True},
            "oak_nodes": {},
        }
        for tool_name, args in tool_args.items():
            result = handler.handle_tool_call(tool_name, args)
            assert not result.get("isError"), f"{tool_name} returned error: {result}"
            assert result["content"][0]["type"] == "text"
            assert len(result["content"][0]["text"]) > 0, f"{tool_name} returned empty text"


# =============================================================================
# 10. Federation policy enforcement through MCPToolHandler
# =============================================================================


class TestFederationPolicySmoke:
    """Full MCPToolHandler dispatch with federated_tools policy toggling.

    Verifies that when the policy accessor returns federated_tools=False,
    tools with include_network=True silently return local-only results
    (no relay calls made). When policy allows federation, relay calls proceed.
    """

    @pytest.fixture
    def disabled_policy_handler(
        self,
        mock_engine: MagicMock,
        seeded_store: ActivityStore,
        mock_vector_store: MagicMock,
        mock_relay_client: MagicMock,
    ) -> MCPToolHandler:
        """MCPToolHandler with federated_tools=False policy."""
        from open_agent_kit.features.codebase_intelligence.config.governance import (
            DataCollectionPolicy,
        )

        mock_engine.activity_store = seeded_store
        mock_engine.store = mock_vector_store
        policy = DataCollectionPolicy(federated_tools=False)
        return MCPToolHandler(
            mock_engine,
            relay_client=mock_relay_client,
            policy_accessor=lambda: policy,
        )

    @pytest.fixture
    def enabled_policy_handler(
        self,
        mock_engine: MagicMock,
        seeded_store: ActivityStore,
        mock_vector_store: MagicMock,
        mock_relay_client: MagicMock,
    ) -> MCPToolHandler:
        """MCPToolHandler with federated_tools=True policy."""
        from open_agent_kit.features.codebase_intelligence.config.governance import (
            DataCollectionPolicy,
        )

        mock_engine.activity_store = seeded_store
        mock_engine.store = mock_vector_store
        policy = DataCollectionPolicy(federated_tools=True)
        return MCPToolHandler(
            mock_engine,
            relay_client=mock_relay_client,
            policy_accessor=lambda: policy,
        )

    def _patch_loop(self, relay_return: dict):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = relay_return
        return patch("asyncio.get_event_loop", return_value=mock_loop)

    # -- Policy disabled: federation silently skipped -------------------------

    def test_search_skips_network_when_disabled(
        self, disabled_policy_handler: MCPToolHandler
    ) -> None:
        result = disabled_policy_handler.handle_tool_call(
            "oak_search", {"query": "auth", "include_network": True}
        )
        text = _text(result)
        assert "Network Results" not in text
        assert "Network Memories" not in text

    def test_sessions_skips_network_when_disabled(
        self, disabled_policy_handler: MCPToolHandler
    ) -> None:
        result = disabled_policy_handler.handle_tool_call(
            "oak_sessions", {"limit": 5, "include_network": True}
        )
        text = _text(result)
        assert "Network Results" not in text

    def test_memories_skips_network_when_disabled(
        self, disabled_policy_handler: MCPToolHandler
    ) -> None:
        result = disabled_policy_handler.handle_tool_call("oak_memories", {"include_network": True})
        text = _text(result)
        assert "Network Results" not in text

    def test_context_skips_network_when_disabled(
        self, disabled_policy_handler: MCPToolHandler
    ) -> None:
        result = disabled_policy_handler.handle_tool_call(
            "oak_context", {"task": "implement auth", "include_network": True}
        )
        text = _text(result)
        assert "Network Memories" not in text

    def test_stats_skips_network_when_disabled(
        self, disabled_policy_handler: MCPToolHandler
    ) -> None:
        result = disabled_policy_handler.handle_tool_call("oak_stats", {"include_network": True})
        text = _text(result)
        assert "Network Results" not in text

    # -- Policy enabled: federation proceeds ----------------------------------

    def test_search_includes_network_when_enabled(
        self,
        enabled_policy_handler: MCPToolHandler,
        mock_relay_client: MagicMock,
    ) -> None:
        network_return = {"results": [{"observation": "Network hit", "machine_id": "smoke-node-1"}]}
        with self._patch_loop(network_return):
            result = enabled_policy_handler.handle_tool_call(
                "oak_search", {"query": "auth", "include_network": True}
            )
        text = _text(result)
        assert "Network Results" in text

    def test_sessions_includes_network_when_enabled(
        self, enabled_policy_handler: MCPToolHandler
    ) -> None:
        federated_return = {
            "results": [
                {
                    "from_machine_id": "smoke-node-1",
                    "result": {"content": [{"type": "text", "text": "Remote sessions"}]},
                }
            ]
        }
        with self._patch_loop(federated_return):
            result = enabled_policy_handler.handle_tool_call(
                "oak_sessions", {"limit": 5, "include_network": True}
            )
        text = _text(result)
        assert "Network Results" in text

    # -- No relay calls made when policy disabled -----------------------------

    def test_relay_not_called_when_policy_disabled(
        self,
        disabled_policy_handler: MCPToolHandler,
        mock_relay_client: MagicMock,
    ) -> None:
        """Relay methods should never be invoked when policy disables federation."""
        disabled_policy_handler.handle_tool_call(
            "oak_search", {"query": "auth", "include_network": True}
        )
        disabled_policy_handler.handle_tool_call(
            "oak_sessions", {"limit": 5, "include_network": True}
        )
        disabled_policy_handler.handle_tool_call(
            "oak_context", {"task": "test", "include_network": True}
        )
        mock_relay_client.search_network.assert_not_called()
        mock_relay_client.federate_tool_call.assert_not_called()
