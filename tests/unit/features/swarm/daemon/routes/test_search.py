"""Tests for the swarm search route helpers.

Tests cover:
- _normalize_match() field mapping without mutating the input
- _group_results_by_project() grouping flat results by project_slug
- _group_results_by_project() passthrough for already-grouped data
"""

from open_agent_kit.features.swarm.constants import (
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_RESPONSE_KEY_RESULTS,
)
from open_agent_kit.features.swarm.daemon.routes.search import (
    _group_results_by_project,
    _normalize_match,
)

# =========================================================================
# _normalize_match() tests
# =========================================================================


class TestNormalizeMatch:
    """Test flat search result normalization."""

    def test_maps_memory_fields(self) -> None:
        """Memory results use 'summary' as content source."""
        item = {
            "id": "m1",
            "_result_type": "memory",
            "summary": "Auth middleware pattern",
            "relevance": 0.95,
            "memory_type": "discovery",
        }
        result = _normalize_match(item)
        assert result["id"] == "m1"
        assert result["type"] == "memory"
        assert result["content"] == "Auth middleware pattern"
        assert result["score"] == 0.95
        assert result["doc_type"] == "discovery"

    def test_maps_code_fields(self) -> None:
        """Code results use 'content' and 'file_path'."""
        item = {
            "id": "c1",
            "type": "code",
            "content": "def hello(): pass",
            "score": 0.8,
            "file_path": "src/main.py",
        }
        result = _normalize_match(item)
        assert result["type"] == "code"
        assert result["content"] == "def hello(): pass"
        assert result["file_path"] == "src/main.py"

    def test_does_not_mutate_input(self) -> None:
        """Ensure _normalize_match does not modify the original dict."""
        item = {
            "id": "x1",
            "_result_type": "memory",
            "summary": "test",
            "relevance": 0.5,
            "machine_id": "abc",
        }
        original_keys = set(item.keys())
        _normalize_match(item)
        assert set(item.keys()) == original_keys
        assert item["_result_type"] == "memory"

    def test_falls_back_to_type_when_no_result_type(self) -> None:
        """Uses 'type' field when '_result_type' is absent."""
        item = {"id": "t1", "type": "plan", "preview": "Sprint plan", "score": 0.7}
        result = _normalize_match(item)
        assert result["type"] == "plan"
        assert result["content"] == "Sprint plan"

    def test_falls_back_to_unknown_type(self) -> None:
        """Returns 'unknown' when neither '_result_type' nor 'type' is present."""
        item = {"id": "u1", "content": "something"}
        result = _normalize_match(item)
        assert result["type"] == "unknown"

    def test_filepath_alias(self) -> None:
        """Handles 'filepath' (no underscore) as fallback for file_path."""
        item = {"id": "f1", "type": "code", "content": "x", "filepath": "lib/util.py"}
        result = _normalize_match(item)
        assert result["file_path"] == "lib/util.py"


# =========================================================================
# _group_results_by_project() tests
# =========================================================================


class TestGroupResultsByProject:
    """Test grouping flat results into per-project groups."""

    def test_groups_by_project_slug(self) -> None:
        """Flat results are grouped into project-keyed groups."""
        raw = {
            SWARM_RESPONSE_KEY_RESULTS: [
                {"id": "a", "project_slug": "proj-a", "type": "code", "content": "x", "score": 0.9},
                {"id": "b", "project_slug": "proj-b", "type": "code", "content": "y", "score": 0.8},
                {"id": "c", "project_slug": "proj-a", "type": "code", "content": "z", "score": 0.7},
            ]
        }
        grouped = _group_results_by_project(raw)
        results = grouped[SWARM_RESPONSE_KEY_RESULTS]
        slugs = {r["project_slug"] for r in results}
        assert slugs == {"proj-a", "proj-b"}

        proj_a = next(r for r in results if r["project_slug"] == "proj-a")
        assert len(proj_a["matches"]) == 2

    def test_passthrough_already_grouped(self) -> None:
        """Already-grouped data (with 'matches' key) passes through unchanged."""
        raw = {
            SWARM_RESPONSE_KEY_RESULTS: [
                {"project_slug": "proj-a", "matches": [{"id": "a", "type": "code"}]}
            ]
        }
        grouped = _group_results_by_project(raw)
        assert grouped is raw

    def test_empty_results(self) -> None:
        """Empty results array passes through."""
        raw = {SWARM_RESPONSE_KEY_RESULTS: []}
        grouped = _group_results_by_project(raw)
        assert grouped is raw

    def test_preserves_errors(self) -> None:
        """Error keys from the swarm worker are preserved."""
        raw = {
            SWARM_RESPONSE_KEY_RESULTS: [
                {"id": "a", "project_slug": "p1", "type": "code", "content": "x"},
            ],
            "errors": [{"project_slug": "p2", "error": "timeout"}],
            SWARM_RESPONSE_KEY_ERROR: "partial failure",
        }
        grouped = _group_results_by_project(raw)
        assert grouped["errors"] == [{"project_slug": "p2", "error": "timeout"}]
        assert grouped[SWARM_RESPONSE_KEY_ERROR] == "partial failure"

    def test_does_not_mutate_input(self) -> None:
        """Ensure the original flat items are not mutated."""
        item = {"id": "a", "project_slug": "proj-a", "type": "code", "content": "x"}
        raw = {SWARM_RESPONSE_KEY_RESULTS: [item]}
        _group_results_by_project(raw)
        assert "project_slug" in item
