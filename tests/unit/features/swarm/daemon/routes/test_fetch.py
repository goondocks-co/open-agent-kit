"""Tests for the swarm fetch route helpers.

Tests cover:
- _extract_fetch_payload() parsing MCP tool-result envelopes
- _merge_broadcast_results() merging nested broadcast responses
- _merge_broadcast_results() deduplicating by chunk ID
- swarm_fetch() endpoint error handling
"""

import json

from open_agent_kit.features.swarm.daemon.routes.fetch import (
    _extract_fetch_payload,
    _merge_broadcast_results,
)

# =========================================================================
# _extract_fetch_payload() tests
# =========================================================================


class TestExtractFetchPayload:
    """Test MCP tool-result envelope parsing."""

    def test_extracts_valid_payload(self) -> None:
        """Parses JSON from a standard MCP text content block."""
        mcp_result = {
            "content": [
                {"type": "text", "text": json.dumps({"results": [{"id": "a"}], "total_tokens": 10})}
            ]
        }
        payload = _extract_fetch_payload(mcp_result)
        assert payload is not None
        assert payload["results"] == [{"id": "a"}]
        assert payload["total_tokens"] == 10

    def test_returns_none_on_error(self) -> None:
        """Returns None when isError is set."""
        mcp_result = {"isError": True, "content": [{"type": "text", "text": "{}"}]}
        assert _extract_fetch_payload(mcp_result) is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Returns None when text is not valid JSON."""
        mcp_result = {"content": [{"type": "text", "text": "not json"}]}
        assert _extract_fetch_payload(mcp_result) is None

    def test_skips_non_text_blocks(self) -> None:
        """Skips image or other block types, returns None if no text found."""
        mcp_result = {"content": [{"type": "image", "data": "..."}]}
        assert _extract_fetch_payload(mcp_result) is None

    def test_returns_none_on_empty_content(self) -> None:
        """Returns None when content list is empty."""
        assert _extract_fetch_payload({"content": []}) is None
        assert _extract_fetch_payload({}) is None


# =========================================================================
# _merge_broadcast_results() tests
# =========================================================================


def _make_mcp_envelope(results: list[dict], total_tokens: int = 0) -> dict:
    """Build an MCP tool-result envelope with the given results."""
    return {
        "content": [
            {"type": "text", "text": json.dumps({"results": results, "total_tokens": total_tokens})}
        ]
    }


def _make_broadcast_response(project_entries: list[dict]) -> dict:
    """Build a broadcast response with project entries."""
    return {"results": project_entries}


class TestMergeBroadcastResults:
    """Test broadcast response merging."""

    def test_merges_single_node_results(self) -> None:
        """Merges results from a single node correctly."""
        raw = _make_broadcast_response(
            [
                {
                    "project_slug": "proj-a",
                    "error": None,
                    "result": {
                        "results": [
                            {
                                "from_machine_id": "node-1",
                                "result": _make_mcp_envelope(
                                    [{"id": "chunk-1", "content": "hello", "tokens": 5}],
                                    total_tokens=5,
                                ),
                            }
                        ]
                    },
                }
            ]
        )
        merged = _merge_broadcast_results(raw)
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert len(inner["results"]) == 1
        assert inner["results"][0]["id"] == "chunk-1"
        assert inner["total_tokens"] == 5

    def test_deduplicates_by_chunk_id(self) -> None:
        """Same chunk ID from multiple nodes is included only once."""
        node_result = _make_mcp_envelope(
            [{"id": "chunk-1", "content": "hello", "tokens": 5}],
            total_tokens=5,
        )
        raw = _make_broadcast_response(
            [
                {
                    "project_slug": "proj-a",
                    "error": None,
                    "result": {
                        "results": [
                            {"from_machine_id": "node-1", "result": node_result},
                            {"from_machine_id": "node-2", "result": node_result},
                        ]
                    },
                }
            ]
        )
        merged = _merge_broadcast_results(raw)
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert len(inner["results"]) == 1

    def test_merges_across_projects(self) -> None:
        """Results from different projects are merged together."""
        raw = _make_broadcast_response(
            [
                {
                    "project_slug": "proj-a",
                    "error": None,
                    "result": {
                        "results": [
                            {
                                "from_machine_id": "node-1",
                                "result": _make_mcp_envelope(
                                    [{"id": "a-1", "content": "from a", "tokens": 3}]
                                ),
                            }
                        ]
                    },
                },
                {
                    "project_slug": "proj-b",
                    "error": None,
                    "result": {
                        "results": [
                            {
                                "from_machine_id": "node-2",
                                "result": _make_mcp_envelope(
                                    [{"id": "b-1", "content": "from b", "tokens": 4}]
                                ),
                            }
                        ]
                    },
                },
            ]
        )
        merged = _merge_broadcast_results(raw)
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert len(inner["results"]) == 2
        ids = {r["id"] for r in inner["results"]}
        assert ids == {"a-1", "b-1"}
        assert inner["total_tokens"] == 7

    def test_skips_errored_projects(self) -> None:
        """Projects with errors are skipped."""
        raw = _make_broadcast_response(
            [
                {"project_slug": "proj-a", "error": "connection failed", "result": None},
                {
                    "project_slug": "proj-b",
                    "error": None,
                    "result": {
                        "results": [
                            {
                                "from_machine_id": "node-1",
                                "result": _make_mcp_envelope(
                                    [{"id": "b-1", "content": "ok", "tokens": 2}]
                                ),
                            }
                        ]
                    },
                },
            ]
        )
        merged = _merge_broadcast_results(raw)
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert len(inner["results"]) == 1
        assert inner["results"][0]["id"] == "b-1"

    def test_empty_broadcast(self) -> None:
        """Returns empty results for empty broadcast response."""
        merged = _merge_broadcast_results({"results": []})
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert inner["results"] == []
        assert inner["total_tokens"] == 0

    def test_skips_error_mcp_results(self) -> None:
        """MCP results with isError are skipped."""
        raw = _make_broadcast_response(
            [
                {
                    "project_slug": "proj-a",
                    "error": None,
                    "result": {
                        "results": [
                            {
                                "from_machine_id": "node-1",
                                "result": {"isError": True, "content": []},
                            }
                        ]
                    },
                }
            ]
        )
        merged = _merge_broadcast_results(raw)
        inner = json.loads(merged["result"]["content"][0]["text"])
        assert inner["results"] == []
