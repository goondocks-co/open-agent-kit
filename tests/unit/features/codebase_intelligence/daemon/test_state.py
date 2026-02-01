"""Tests for daemon state management.

Tests cover:
- IndexStatus state transitions
- DaemonState initialization and properties
- State reset for testing
"""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    INDEX_STATUS_ERROR,
    INDEX_STATUS_IDLE,
    INDEX_STATUS_INDEXING,
    INDEX_STATUS_READY,
    INDEX_STATUS_UPDATING,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    IndexStatus,
    daemon_state,
    get_state,
    reset_state,
)

# =============================================================================
# IndexStatus Tests
# =============================================================================


class TestIndexStatusInit:
    """Test IndexStatus initialization."""

    def test_default_initialization(self, empty_index_status: IndexStatus):
        """Test default index status values.

        Args:
            empty_index_status: Empty IndexStatus fixture.
        """
        assert empty_index_status.status == INDEX_STATUS_IDLE
        assert empty_index_status.progress == 0
        assert empty_index_status.total == 0
        assert empty_index_status.last_indexed is None
        assert empty_index_status.is_indexing is False
        assert empty_index_status.duration_seconds == 0.0
        assert empty_index_status.ast_stats == {}


class TestIndexStatusTransitions:
    """Test index status state transitions."""

    def test_set_indexing_transition(self):
        """Test transition to indexing state."""
        status = IndexStatus()
        status.set_indexing()

        assert status.status == INDEX_STATUS_INDEXING
        assert status.is_indexing is True
        assert status.progress == 0
        assert status.total == 0

    def test_set_ready_transition(self):
        """Test transition to ready state."""
        status = IndexStatus()
        status.set_ready()

        assert status.status == INDEX_STATUS_READY
        assert status.is_indexing is False
        assert status.last_indexed is not None

    def test_set_ready_with_duration(self):
        """Test transition to ready state with duration."""
        status = IndexStatus()
        status.set_ready(duration=5.5)

        assert status.status == INDEX_STATUS_READY
        assert status.duration_seconds == 5.5

    def test_set_error_transition(self):
        """Test transition to error state."""
        status = IndexStatus()
        status.set_error()

        assert status.status == INDEX_STATUS_ERROR
        assert status.is_indexing is False

    def test_set_updating_transition(self):
        """Test transition to updating state."""
        status = IndexStatus()
        status.set_updating()

        assert status.status == INDEX_STATUS_UPDATING
        assert status.is_indexing is True

    def test_multiple_state_transitions(self):
        """Test multiple consecutive state transitions."""
        status = IndexStatus()

        # Start indexing
        status.set_indexing()
        assert status.is_indexing is True

        # Mark as ready
        status.set_ready(duration=2.0)
        assert status.is_indexing is False
        assert status.status == INDEX_STATUS_READY

        # Update files
        status.set_updating()
        assert status.is_indexing is True
        assert status.status == INDEX_STATUS_UPDATING


class TestIndexStatusProgress:
    """Test progress tracking."""

    def test_update_progress(self):
        """Test updating progress."""
        status = IndexStatus()
        status.update_progress(current=10, total=100)

        assert status.progress == 10
        assert status.total == 100

    def test_update_progress_multiple_times(self):
        """Test updating progress multiple times."""
        status = IndexStatus()

        status.update_progress(25, 100)
        assert status.progress == 25

        status.update_progress(50, 100)
        assert status.progress == 50

        status.update_progress(100, 100)
        assert status.progress == 100

    def test_progress_during_indexing(self):
        """Test that progress can be updated during indexing."""
        status = IndexStatus()
        status.set_indexing()

        assert status.progress == 0
        status.update_progress(1, 10)
        assert status.progress == 1


class TestIndexStatusSerialization:
    """Test serialization of index status."""

    def test_to_dict_default_status(self, empty_index_status: IndexStatus):
        """Test converting default status to dict.

        Args:
            empty_index_status: Empty IndexStatus fixture.
        """
        result = empty_index_status.to_dict()

        assert result["status"] == INDEX_STATUS_IDLE
        assert result["progress"] == 0
        assert result["total"] == 0
        assert result["is_indexing"] is False
        assert result["duration_seconds"] == 0.0
        assert isinstance(result["ast_stats"], dict)

    def test_to_dict_ready_status(self, ready_status: IndexStatus):
        """Test converting ready status to dict.

        Args:
            ready_status: Ready IndexStatus fixture.
        """
        result = ready_status.to_dict()

        assert result["status"] == INDEX_STATUS_READY
        assert result["is_indexing"] is False
        assert result["last_indexed"] is not None
        assert result["duration_seconds"] == 2.5

    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all fields."""
        status = IndexStatus()
        status.set_indexing()
        status.update_progress(5, 20)
        status.ast_stats = {"functions": 42, "classes": 8}

        result = status.to_dict()

        assert set(result.keys()) == {
            "status",
            "progress",
            "total",
            "file_count",
            "last_indexed",
            "is_indexing",
            "duration_seconds",
            "ast_stats",
        }


# =============================================================================
# DaemonState Tests
# =============================================================================


class TestDaemonStateInit:
    """Test DaemonState initialization."""

    def test_default_initialization(self, daemon_state: DaemonState):
        """Test default DaemonState values.

        Args:
            daemon_state: DaemonState fixture.
        """
        assert daemon_state.start_time is None
        assert daemon_state.project_root is None
        assert daemon_state.embedding_chain is None
        assert daemon_state.vector_store is None
        assert daemon_state.indexer is None
        assert daemon_state.file_watcher is None
        assert daemon_state.config == {}
        assert daemon_state.ci_config is None
        assert daemon_state.log_level == "INFO"
        assert isinstance(daemon_state.index_status, IndexStatus)

    def test_initialize_method(self, daemon_state: DaemonState, tmp_path: Path):
        """Test the initialize method sets expected values.

        Args:
            daemon_state: DaemonState fixture.
            tmp_path: Temporary directory from pytest.
        """
        daemon_state.initialize(tmp_path)

        assert daemon_state.project_root == tmp_path
        assert daemon_state.start_time is not None
        assert isinstance(daemon_state.start_time, float)

    def test_uptime_calculation(self, initialized_daemon_state: DaemonState):
        """Test uptime calculation.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
        """
        uptime = initialized_daemon_state.uptime_seconds
        assert isinstance(uptime, float)
        assert uptime >= 0

    def test_uptime_uninitialized_returns_zero(self, daemon_state: DaemonState):
        """Test that uptime returns 0 before initialization.

        Args:
            daemon_state: DaemonState fixture.
        """
        assert daemon_state.uptime_seconds == 0.0


class TestDaemonStateReadiness:
    """Test readiness checking."""

    def test_is_ready_false_initially(self, daemon_state: DaemonState):
        """Test that daemon is not ready initially.

        Args:
            daemon_state: DaemonState fixture.
        """
        assert daemon_state.is_ready is False

    def test_is_ready_true_when_fully_initialized(self, initialized_daemon_state: DaemonState):
        """Test that daemon is not ready without all components.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
        """
        # Not yet ready - still missing embedding chain and vector store
        assert initialized_daemon_state.is_ready is False

    def test_is_ready_requires_project_root(self, daemon_state: DaemonState, tmp_path: Path):
        """Test that is_ready requires project_root to be set.

        Args:
            daemon_state: DaemonState fixture.
            tmp_path: Temporary directory from pytest.
        """
        daemon_state.project_root = tmp_path
        assert daemon_state.is_ready is False

    def test_is_ready_requires_embedding_chain(
        self, initialized_daemon_state: DaemonState, mock_embedding_chain
    ):
        """Test that is_ready requires embedding_chain.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
            mock_embedding_chain: Mock embedding chain fixture.
        """
        initialized_daemon_state.embedding_chain = mock_embedding_chain
        assert initialized_daemon_state.is_ready is False  # Still missing vector_store

    def test_is_ready_requires_vector_store(
        self,
        initialized_daemon_state: DaemonState,
        mock_embedding_chain,
        mock_vector_store,
    ):
        """Test that is_ready requires vector_store.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
            mock_embedding_chain: Mock embedding chain fixture.
            mock_vector_store: Mock vector store fixture.
        """
        initialized_daemon_state.embedding_chain = mock_embedding_chain
        initialized_daemon_state.vector_store = mock_vector_store
        assert initialized_daemon_state.is_ready is True


class TestDaemonStateReset:
    """Test state reset functionality."""

    def test_reset_clears_all_state(self, initialized_daemon_state: DaemonState):
        """Test that reset clears all state.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
        """
        initialized_daemon_state.reset()

        assert initialized_daemon_state.start_time is None
        assert initialized_daemon_state.project_root is None
        assert initialized_daemon_state.embedding_chain is None
        assert initialized_daemon_state.config == {}

    def test_reset_reinitializes_collections(self, daemon_state: DaemonState):
        """Test that reset reinitializes collections.

        Args:
            daemon_state: DaemonState fixture.
        """
        # Add some data
        daemon_state.config["test"] = "value"

        # Reset
        daemon_state.reset()

        # Collections should be fresh
        assert isinstance(daemon_state.index_status, IndexStatus)
        assert daemon_state.config == {}

    def test_reset_restores_defaults(self, daemon_state: DaemonState):
        """Test that reset restores default values.

        Args:
            daemon_state: DaemonState fixture.
        """
        daemon_state.log_level = "DEBUG"
        daemon_state.reset()

        assert daemon_state.log_level == "INFO"


# =============================================================================
# Module-level State Tests
# =============================================================================


class TestModuleLevelState:
    """Test module-level state functions."""

    def test_get_state_returns_daemon_state(self):
        """Test that get_state returns the global daemon_state instance."""
        state = get_state()
        assert state is daemon_state

    def test_reset_state_function(self):
        """Test the reset_state module function."""
        # Modify state
        daemon_state.log_level = "DEBUG"
        daemon_state.config = {"test": "value"}

        # Reset
        reset_state()

        # Should be restored
        assert daemon_state.log_level == "INFO"
        assert daemon_state.config == {}

    def test_daemon_state_is_singleton(self):
        """Test that daemon_state is a singleton."""
        state1 = get_state()
        state2 = get_state()
        assert state1 is state2
        assert state1 is daemon_state


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestIndexStatusThreadSafety:
    """Test thread-safe operations on IndexStatus."""

    def test_index_status_has_lock(self):
        """Test that IndexStatus has internal RLock."""
        status = IndexStatus()
        assert hasattr(status, "_lock")

    def test_concurrent_status_updates(self):
        """Test that concurrent status updates don't cause data races."""
        import threading

        status = IndexStatus()
        errors = []

        def set_indexing():
            try:
                for _ in range(100):
                    status.set_indexing()
            except Exception as e:
                errors.append(e)

        def set_ready():
            try:
                for _ in range(100):
                    status.set_ready(duration=1.0)
            except Exception as e:
                errors.append(e)

        def update_progress():
            try:
                for i in range(100):
                    status.update_progress(i, 100)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=set_indexing),
            threading.Thread(target=set_ready),
            threading.Thread(target=update_progress),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0

    def test_to_dict_returns_consistent_snapshot(self):
        """Test that to_dict returns a consistent snapshot."""
        status = IndexStatus()
        status.set_indexing()
        status.update_progress(50, 100)

        # Get snapshot
        snapshot = status.to_dict()

        # Verify consistency
        assert snapshot["is_indexing"] is True
        assert snapshot["progress"] == 50
        assert snapshot["total"] == 100

    def test_to_dict_copies_ast_stats(self):
        """Test that to_dict returns a copy of ast_stats."""
        status = IndexStatus()
        status.ast_stats = {"test": 42}

        snapshot = status.to_dict()

        # Modifying the returned dict shouldn't affect original
        snapshot["ast_stats"]["test"] = 999
        assert status.ast_stats["test"] == 42


# =============================================================================
# Background Task Tracking Tests
# =============================================================================


class TestDaemonStateBackgroundTasks:
    """Test background task tracking."""

    def test_default_background_tasks_empty(self, daemon_state: DaemonState):
        """Test that background_tasks is empty by default.

        Args:
            daemon_state: DaemonState fixture.
        """
        assert daemon_state.background_tasks == []

    def test_initialize_creates_empty_task_list(self, daemon_state: DaemonState, tmp_path: Path):
        """Test that initialize creates fresh task list.

        Args:
            daemon_state: DaemonState fixture.
            tmp_path: Temporary directory from pytest.
        """
        daemon_state.initialize(tmp_path)
        assert daemon_state.background_tasks == []

    def test_reset_clears_background_tasks(self, daemon_state: DaemonState):
        """Test that reset clears background tasks.

        Args:
            daemon_state: DaemonState fixture.
        """
        # Add a mock task
        from unittest.mock import MagicMock

        mock_task = MagicMock()
        daemon_state.background_tasks.append(mock_task)

        daemon_state.reset()
        assert daemon_state.background_tasks == []


# =============================================================================
# Index Lock Tests
# =============================================================================


class TestDaemonStateIndexLock:
    """Test index lock for race condition prevention."""

    def test_default_index_lock_is_none(self, daemon_state: DaemonState):
        """Test that index_lock is None by default.

        Args:
            daemon_state: DaemonState fixture.
        """
        assert daemon_state.index_lock is None

    def test_initialize_creates_index_lock(self, daemon_state: DaemonState, tmp_path: Path):
        """Test that initialize creates an asyncio.Lock.

        Args:
            daemon_state: DaemonState fixture.
            tmp_path: Temporary directory from pytest.
        """
        import asyncio

        daemon_state.initialize(tmp_path)
        assert isinstance(daemon_state.index_lock, asyncio.Lock)

    def test_reset_clears_index_lock(self, initialized_daemon_state: DaemonState):
        """Test that reset clears index lock.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
        """
        initialized_daemon_state.reset()
        assert initialized_daemon_state.index_lock is None

    def test_index_lock_is_not_locked_initially(self, initialized_daemon_state: DaemonState):
        """Test that index lock is not locked after initialization.

        Args:
            initialized_daemon_state: Initialized DaemonState fixture.
        """
        assert initialized_daemon_state.index_lock is not None
        assert not initialized_daemon_state.index_lock.locked()
