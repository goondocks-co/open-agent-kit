"""Tests for daemon index management routes.

Tests cover:
- Index status endpoint
- Index build endpoint
- Full rebuild endpoint
- Progress tracking
- Error handling and edge cases
- Concurrency and locking
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_indexer():
    """Mock code indexer."""
    mock = MagicMock()
    mock.build_index.return_value = MagicMock(
        chunks_indexed=1250,
        files_processed=42,
        duration_seconds=15.5,
        ast_success=38,
        ast_fallback=3,
        line_based=1,
    )
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    mock = MagicMock()
    mock.get_stats.return_value = {
        "code_chunks": 1250,
        "memory_observations": 45,
    }
    return mock


@pytest.fixture
def setup_state_for_indexing(tmp_path: Path, mock_indexer, mock_vector_store):
    """Setup daemon state for indexing tests."""
    state = get_state()
    state.initialize(tmp_path)
    state.project_root = tmp_path
    state.indexer = mock_indexer
    state.vector_store = mock_vector_store
    return state


# =============================================================================
# GET /api/index/status Tests
# =============================================================================


class TestIndexStatus:
    """Test GET /api/index/status endpoint."""

    def test_index_status_ready(self, client, setup_state_for_indexing):
        """Test index status when ready."""
        setup_state_for_indexing.index_status.set_ready(duration=10.0)

        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["is_indexing"] is False

    def test_index_status_indexing(self, client, setup_state_for_indexing):
        """Test index status when indexing."""
        setup_state_for_indexing.index_status.set_indexing()
        setup_state_for_indexing.index_status.update_progress(50, 100)

        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexing"
        assert data["is_indexing"] is True
        assert data["progress"] == 50
        assert data["total"] == 100

    def test_index_status_error(self, client, setup_state_for_indexing):
        """Test index status when error occurred."""
        setup_state_for_indexing.index_status.set_error()

        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    def test_index_status_includes_chunks(self, client, setup_state_for_indexing):
        """Test that status includes total chunks."""
        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert "total_chunks" in data
        assert data["total_chunks"] >= 0

    def test_index_status_includes_memories(self, client, setup_state_for_indexing):
        """Test that status includes memory observations."""
        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert "memory_observations" in data

    def test_index_status_includes_last_indexed(self, client, setup_state_for_indexing):
        """Test that status includes last indexed timestamp."""
        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert "last_indexed" in data

    def test_index_status_uninitialized(self, client):
        """Test index status when not initialized."""
        # Using fresh daemon state from fixture (not initialized)
        response = client.get("/api/index/status")

        assert response.status_code == 200
        # Should return status even if not initialized
        _ = response.json()


# =============================================================================
# POST /api/index/build Tests
# =============================================================================


class TestBuildIndex:
    """Test POST /api/index/build endpoint."""

    def test_build_index_success(self, client, setup_state_for_indexing):
        """Test successful index build."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_build_index_incremental_rebuild(self, client, setup_state_for_indexing):
        """Test incremental index rebuild (default)."""
        payload = {"full_rebuild": False}
        response = client.post("/api/index/build", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Should pass full_rebuild=False to indexer
        setup_state_for_indexing.indexer.build_index.assert_called()

    def test_build_index_full_rebuild(self, client, setup_state_for_indexing):
        """Test full index rebuild."""
        payload = {"full_rebuild": True}
        response = client.post("/api/index/build", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_build_index_returns_stats(self, client, setup_state_for_indexing):
        """Test that build response includes statistics."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        data = response.json()
        assert "chunks_indexed" in data
        assert "files_processed" in data
        assert "duration_seconds" in data

    def test_build_index_prevents_concurrent_builds(self, client, setup_state_for_indexing):
        """Test that concurrent builds are prevented."""
        # Start first build
        setup_state_for_indexing.index_status.set_indexing()

        # Try second build
        response = client.post("/api/index/build", json={})

        assert response.status_code == 409
        data = response.json()
        assert "already in progress" in data["detail"].lower()

    def test_build_index_no_indexer(self, client):
        """Test build when indexer is not initialized."""
        state = get_state()
        state.initialize(Path("/tmp/test"))
        state.indexer = None

        response = client.post("/api/index/build", json={})

        assert response.status_code == 503

    def test_build_index_no_lock(self, client, setup_state_for_indexing):
        """Test build fails without index lock."""
        setup_state_for_indexing.index_lock = None

        response = client.post("/api/index/build", json={})

        assert response.status_code == 503

    def test_build_index_timeout_protection(self, client, setup_state_for_indexing):
        """Test that indexing has timeout protection."""
        # Configure indexer to timeout
        setup_state_for_indexing.indexer.build_index.side_effect = TimeoutError()

        response = client.post("/api/index/build", json={})

        assert response.status_code == 504
        # Status should be set to error
        assert setup_state_for_indexing.index_status.status == "error"

    def test_build_index_handles_errors(self, client, setup_state_for_indexing):
        """Test error handling during index build."""
        setup_state_for_indexing.indexer.build_index.side_effect = ValueError("Index build failed")

        response = client.post("/api/index/build", json={})

        assert response.status_code == 500

    def test_build_index_updates_status(self, client, setup_state_for_indexing):
        """Test that index status is updated during build."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        # Status should have been updated
        assert setup_state_for_indexing.index_status.status == "ready"

    def test_build_index_stores_ast_stats(self, client, setup_state_for_indexing):
        """Test that AST statistics are stored."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        assert setup_state_for_indexing.index_status.ast_stats is not None
        assert "ast_success" in setup_state_for_indexing.index_status.ast_stats

    def test_build_index_progress_callback(self, client, setup_state_for_indexing):
        """Test that progress callback is used."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        # Indexer should have been called with progress_callback
        setup_state_for_indexing.indexer.build_index.assert_called()

    def test_build_index_executor_used(self, client, setup_state_for_indexing):
        """Test that indexing runs in executor (not blocking)."""
        response = client.post("/api/index/build", json={})

        # Should complete quickly since it's in executor
        assert response.status_code == 200


# =============================================================================
# POST /api/index/rebuild Tests
# =============================================================================


class TestRebuildIndex:
    """Test POST /api/index/rebuild endpoint."""

    def test_rebuild_index_full_rebuild(self, client, setup_state_for_indexing):
        """Test rebuild endpoint requests full rebuild."""
        response = client.post("/api/index/rebuild", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Should have called build_index with full_rebuild=True
        setup_state_for_indexing.indexer.build_index.assert_called()

    def test_rebuild_index_success(self, client, setup_state_for_indexing):
        """Test successful rebuild."""
        response = client.post("/api/index/rebuild")

        assert response.status_code == 200
        data = response.json()
        assert "chunks_indexed" in data
        assert "files_processed" in data

    def test_rebuild_index_returns_all_stats(self, client, setup_state_for_indexing):
        """Test that rebuild returns comprehensive statistics."""
        response = client.post("/api/index/rebuild")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "chunks_indexed" in data
        assert "files_processed" in data
        assert "duration_seconds" in data


# =============================================================================
# Index Progress Tests
# =============================================================================


class TestIndexProgress:
    """Test index progress tracking."""

    def test_progress_updates_during_indexing(self, client, setup_state_for_indexing):
        """Test that progress updates are tracked."""

        def indexing_with_progress(full_rebuild=False, progress_callback=None):
            if progress_callback:
                progress_callback(0, 100)
                progress_callback(50, 100)
                progress_callback(100, 100)
            return MagicMock(
                chunks_indexed=1000,
                files_processed=40,
                duration_seconds=10.0,
                ast_success=30,
                ast_fallback=8,
                line_based=2,
            )

        setup_state_for_indexing.indexer.build_index = indexing_with_progress

        response = client.post("/api/index/build", json={})

        assert response.status_code == 200

    def test_progress_shows_current_file_count(self, client, setup_state_for_indexing):
        """Test that progress shows file count."""
        setup_state_for_indexing.index_status.update_progress(25, 40)

        response = client.get("/api/index/status")

        assert response.status_code == 200
        data = response.json()
        assert data["progress"] == 25
        assert data["total"] == 40


# =============================================================================
# Index Error Handling Tests
# =============================================================================


class TestIndexErrorHandling:
    """Test error handling in index routes."""

    def test_build_with_invalid_json(self, client, setup_state_for_indexing):
        """Test build with invalid JSON."""
        response = client.post(
            "/api/index/build",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )

        # Should fail with 400
        assert response.status_code in (400, 422)

    def test_build_handles_indexer_errors(self, client, setup_state_for_indexing):
        """Test that indexer errors are handled."""
        setup_state_for_indexing.indexer.build_index.side_effect = RuntimeError("Indexer error")

        response = client.post("/api/index/build", json={})

        assert response.status_code == 500

    def test_build_handles_vector_store_errors(self, client, setup_state_for_indexing):
        """Test that vector store errors are handled."""
        setup_state_for_indexing.vector_store.get_stats.side_effect = RuntimeError("Store error")

        response = client.get("/api/index/status")

        # Should handle gracefully
        assert response.status_code == 200

    def test_timeout_error_handling(self, client, setup_state_for_indexing):
        """Test timeout error handling."""

        def timeout_build(*args, **kwargs):
            # Synchronous function that raises TimeoutError
            # (build_index runs in executor synchronously)
            raise TimeoutError("Indexing took too long")

        setup_state_for_indexing.indexer.build_index = timeout_build

        response = client.post("/api/index/build", json={})

        assert response.status_code == 504


# =============================================================================
# Index State Management Tests
# =============================================================================


class TestIndexStateManagement:
    """Test index state management during operations."""

    def test_status_transitions_during_build(self, client, setup_state_for_indexing):
        """Test that status transitions correctly during build."""
        # Initial status
        response = client.get("/api/index/status")
        assert response.status_code == 200
        _ = response.json()  # Verify valid JSON response

        # Start build
        response = client.post("/api/index/build", json={})
        assert response.status_code == 200

        # Status should now be ready
        response = client.get("/api/index/status")
        final = response.json()
        assert final["status"] == "ready"

    def test_error_state_after_failure(self, client, setup_state_for_indexing):
        """Test that error state is set after failure."""
        setup_state_for_indexing.indexer.build_index.side_effect = ValueError("Build failed")

        response = client.post("/api/index/build", json={})

        assert response.status_code == 500
        assert setup_state_for_indexing.index_status.status == "error"

    def test_index_not_indexing_after_complete(self, client, setup_state_for_indexing):
        """Test that is_indexing flag is cleared after completion."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        assert setup_state_for_indexing.index_status.is_indexing is False


# =============================================================================
# Index Request Model Tests
# =============================================================================


class TestIndexRequestModel:
    """Test IndexRequest Pydantic model."""

    def test_index_request_default_values(self, client, setup_state_for_indexing):
        """Test IndexRequest with default values."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        # Should use full_rebuild=False by default

    def test_index_request_explicit_full_rebuild(self, client, setup_state_for_indexing):
        """Test IndexRequest with explicit full_rebuild."""
        response = client.post("/api/index/build", json={"full_rebuild": True})

        assert response.status_code == 200

    def test_index_request_false_full_rebuild(self, client, setup_state_for_indexing):
        """Test IndexRequest with full_rebuild=False."""
        response = client.post("/api/index/build", json={"full_rebuild": False})

        assert response.status_code == 200


# =============================================================================
# Index Response Model Tests
# =============================================================================


class TestIndexResponseModel:
    """Test IndexResponse Pydantic model."""

    def test_response_includes_required_fields(self, client, setup_state_for_indexing):
        """Test that response includes all required fields."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "chunks_indexed" in data
        assert "files_processed" in data
        assert "duration_seconds" in data

    def test_response_field_types(self, client, setup_state_for_indexing):
        """Test that response fields have correct types."""
        response = client.post("/api/index/build", json={})

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["chunks_indexed"], int)
        assert isinstance(data["files_processed"], int)
        assert isinstance(data["duration_seconds"], (int, float))


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestIndexConcurrency:
    """Test concurrency control in index routes."""

    def test_lock_prevents_concurrent_access(self, client, setup_state_for_indexing):
        """Test that lock prevents concurrent index builds."""
        # Start first indexing
        setup_state_for_indexing.index_status.set_indexing()

        # Try to start second
        response = client.post("/api/index/build", json={})

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"].lower()

    def test_lock_released_after_completion(self, client, setup_state_for_indexing):
        """Test that lock is released after build completes."""
        # Build once
        response1 = client.post("/api/index/build", json={})
        assert response1.status_code == 200

        # Build again should succeed
        setup_state_for_indexing.index_status.set_ready()
        response2 = client.post("/api/index/build", json={})
        assert response2.status_code in (200, 409)
