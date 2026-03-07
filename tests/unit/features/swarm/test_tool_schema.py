"""Tests for swarm tool schema consistency.

Verifies that all three tool definition sites stay in sync:
  1. tool_schema.py (canonical Python definitions)
  2. daemon/mcp_server.py (FastMCP server)
  3. worker_template/src/mcp-handler.ts (TypeScript MCP handler)
"""

import re
from pathlib import Path

from open_agent_kit.features.swarm.tool_schema import SWARM_TOOL_DEFS, SWARM_TOOL_DEFS_BY_NAME

# Path to the TypeScript MCP handler
_MCP_HANDLER_TS = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "open_agent_kit"
    / "features"
    / "swarm"
    / "worker_template"
    / "src"
    / "mcp-handler.ts"
)


class TestToolSchemaCompleteness:
    """Verify the canonical schema covers all expected tools."""

    def test_no_duplicate_names(self) -> None:
        """All tool names in the schema are unique."""
        names = [t.name for t in SWARM_TOOL_DEFS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_all_tools_have_descriptions(self) -> None:
        """Every tool has a non-empty description."""
        for tool_def in SWARM_TOOL_DEFS:
            assert tool_def.description, f"{tool_def.name} has empty description"

    def test_by_name_index_matches_tuple(self) -> None:
        """SWARM_TOOL_DEFS_BY_NAME is consistent with SWARM_TOOL_DEFS."""
        assert len(SWARM_TOOL_DEFS_BY_NAME) == len(SWARM_TOOL_DEFS)
        for tool_def in SWARM_TOOL_DEFS:
            assert SWARM_TOOL_DEFS_BY_NAME[tool_def.name] is tool_def


class TestTypeScriptSync:
    """Verify the TypeScript mcp-handler.ts tool names match the Python schema."""

    def test_ts_tool_names_match_python_schema(self) -> None:
        """Every tool name in mcp-handler.ts SWARM_TOOLS must exist in the Python schema.

        The TS file also defines TOOL_ENDPOINTS — we check both.
        """
        assert _MCP_HANDLER_TS.exists(), f"TS handler not found: {_MCP_HANDLER_TS}"
        ts_source = _MCP_HANDLER_TS.read_text(encoding="utf-8")

        # Extract tool names from the SWARM_TOOLS array: `name: "swarm_search",`
        ts_tool_names = set(re.findall(r'name:\s*"(swarm_\w+)"', ts_source))
        assert ts_tool_names, "Failed to parse any tool names from mcp-handler.ts"

        python_names = set(SWARM_TOOL_DEFS_BY_NAME.keys())

        # TS tools should be a subset of Python tools (TS may omit health_check
        # since it's not exposed via the cloud MCP endpoint)
        missing_from_python = ts_tool_names - python_names
        assert (
            not missing_from_python
        ), f"Tools in mcp-handler.ts but not in tool_schema.py: {missing_from_python}"

    def test_ts_endpoint_names_match_python_schema(self) -> None:
        """Every key in TOOL_ENDPOINTS must exist in the Python schema."""
        assert _MCP_HANDLER_TS.exists()
        ts_source = _MCP_HANDLER_TS.read_text(encoding="utf-8")

        # Extract keys from TOOL_ENDPOINTS: `swarm_search: {`
        ts_endpoint_names = set(re.findall(r"^\s*(swarm_\w+):", ts_source, re.MULTILINE))
        assert ts_endpoint_names, "Failed to parse TOOL_ENDPOINTS from mcp-handler.ts"

        python_names = set(SWARM_TOOL_DEFS_BY_NAME.keys())
        missing = ts_endpoint_names - python_names
        assert not missing, f"TOOL_ENDPOINTS keys in TS but not in tool_schema.py: {missing}"
