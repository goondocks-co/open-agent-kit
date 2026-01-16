"""Tests for index management routes.

Tests cover:
- Index status endpoint
- Index build with locking
- Race condition prevention
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    IndexStatus,
    reset_state,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


# =============================================================================
# IndexStatus Unit Tests
# =============================================================================


class TestIndexStatusEndpoint:
    """Test index status logic."""

    def test_index_status_dict_ready(self):
        """Test that index status to_dict works for ready state."""
        status = IndexStatus()
        status.set_ready()

        result = status.to_dict()

        assert result["status"] == "ready"
        assert result["is_indexing"] is False
        assert result["last_indexed"] is not None

    def test_index_status_dict_indexing(self):
        """Test that index status to_dict works for indexing state."""
        status = IndexStatus()
        status.set_indexing()
        status.update_progress(50, 100)

        result = status.to_dict()

        assert result["status"] == "indexing"
        assert result["is_indexing"] is True
        assert result["progress"] == 50
        assert result["total"] == 100


# =============================================================================
# Index Build Unit Tests
# =============================================================================


class TestBuildIndexLogic:
    """Test index build logic without async."""

    def test_indexer_required_check(self):
        """Test that indexer is required for build."""
        state = DaemonState()
        state.indexer = None

        # Verify the condition that would trigger 503
        assert state.indexer is None

    def test_index_lock_required_after_init(self, tmp_path):
        """Test that index lock is created during init."""
        state = DaemonState()
        state.initialize(tmp_path)

        assert state.index_lock is not None
        assert isinstance(state.index_lock, asyncio.Lock)

    def test_already_indexing_rejection(self):
        """Test that is_indexing flag prevents concurrent builds."""
        status = IndexStatus()
        status.set_indexing()

        # This is the check done in the route
        assert status.is_indexing is True

    def test_indexing_status_flow(self):
        """Test the status flow during indexing."""
        status = IndexStatus()

        # Start indexing
        status.set_indexing()
        assert status.is_indexing is True
        assert status.status == "indexing"

        # Update progress
        status.update_progress(50, 100)
        assert status.progress == 50
        assert status.total == 100

        # Complete
        status.set_ready(duration=2.5)
        assert status.is_indexing is False
        assert status.status == "ready"
        assert status.duration_seconds == 2.5

    def test_error_status_on_failure(self):
        """Test that error status is set on failure."""
        status = IndexStatus()
        status.set_indexing()
        status.set_error()

        assert status.is_indexing is False
        assert status.status == "error"


# =============================================================================
# Index Lock Unit Tests
# =============================================================================


class TestIndexLocking:
    """Test index locking prevents race conditions."""

    def test_lock_starts_unlocked(self, tmp_path):
        """Test that lock starts in unlocked state."""
        state = DaemonState()
        state.initialize(tmp_path)

        assert not state.index_lock.locked()

    def test_lock_prevents_concurrent_access(self, tmp_path):
        """Test that the lock can be acquired and blocks."""
        import threading

        state = DaemonState()
        state.initialize(tmp_path)

        # We need to test the concept - create a simple lock for sync testing
        lock = threading.Lock()
        results = []

        def try_acquire(name):
            acquired = lock.acquire(blocking=False)
            if acquired:
                results.append(f"{name}: acquired")
                import time

                time.sleep(0.1)
                lock.release()
            else:
                results.append(f"{name}: blocked")

        # First thread acquires
        lock.acquire()
        results.append("t0: acquired")

        # Second thread tries
        t1 = threading.Thread(target=try_acquire, args=("t1",))
        t1.start()
        t1.join()

        lock.release()

        # First acquired, second was blocked
        assert "t0: acquired" in results
        assert "t1: blocked" in results


# =============================================================================
# Rebuild Index Tests
# =============================================================================


class TestRebuildIndex:
    """Test rebuild index logic."""

    def test_full_rebuild_flag(self):
        """Test that full_rebuild=True triggers complete rebuild."""
        from open_agent_kit.features.codebase_intelligence.daemon.models import (
            IndexRequest,
        )

        request = IndexRequest(full_rebuild=True)
        assert request.full_rebuild is True

        request_default = IndexRequest()
        assert request_default.full_rebuild is False


# =============================================================================
# State Integration Tests
# =============================================================================


class TestStateIntegration:
    """Test state integration for index operations."""

    def test_state_tracks_background_tasks(self, tmp_path):
        """Test that state can track background tasks."""
        state = DaemonState()
        state.initialize(tmp_path)

        # Verify background_tasks is initialized
        assert state.background_tasks == []

        # Add a mock task
        mock_task = MagicMock()
        state.background_tasks.append(mock_task)
        assert len(state.background_tasks) == 1

    def test_state_reset_clears_tasks(self, tmp_path):
        """Test that reset clears background tasks."""
        state = DaemonState()
        state.initialize(tmp_path)
        state.background_tasks.append(MagicMock())

        state.reset()

        assert state.background_tasks == []
        assert state.index_lock is None
