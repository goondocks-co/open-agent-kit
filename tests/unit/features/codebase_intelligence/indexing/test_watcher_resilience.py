"""Tests for watcher exception safety.

The file watcher's _do_reindex() method runs in a threading.Timer thread.
If an unhandled exception propagates out, the thread dies silently and the
watcher permanently stops processing file changes.

These tests verify that transient errors (ChromaDB lock, SQLite readonly,
etc.) are caught and logged without killing the thread.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.indexing.watcher import FileWatcher

# Module path for patching
_WATCHER_MODULE = "open_agent_kit.features.codebase_intelligence.indexing.watcher"


@pytest.fixture
def mock_indexer():
    """Create a mock CodebaseIndexer."""
    indexer = MagicMock()
    indexer._should_ignore.return_value = False
    indexer.remove_file.return_value = 0
    indexer.index_single_file.return_value = 1
    return indexer


@pytest.fixture
def watcher(mock_indexer, tmp_path: Path) -> FileWatcher:
    """Create a FileWatcher with mocked indexer."""
    return FileWatcher(
        project_root=tmp_path,
        indexer=mock_indexer,
    )


class TestDoReindexResilience:
    """Test that _do_reindex() survives unexpected exceptions."""

    def test_survives_remove_file_runtime_error(
        self, watcher: FileWatcher, mock_indexer, tmp_path: Path
    ) -> None:
        """_do_reindex() does not raise when remove_file throws RuntimeError."""
        mock_indexer.remove_file.side_effect = RuntimeError("readonly database")

        gone_file = tmp_path / "gone.py"
        watcher._deleted_files.add(gone_file)
        watcher._last_reindex_time = 0.0

        with patch(f"{_WATCHER_MODULE}.get_state") as mock_get_state:
            mock_get_state.return_value.vector_store = None
            watcher._do_reindex()  # Should NOT raise

    def test_survives_index_single_file_exception(
        self, watcher: FileWatcher, mock_indexer, tmp_path: Path
    ) -> None:
        """_do_reindex() does not raise when index_single_file throws Exception."""
        mock_indexer.index_single_file.side_effect = RuntimeError("ChromaDB lock")

        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        watcher._pending_files.add(test_file)
        watcher._last_reindex_time = 0.0

        with patch(f"{_WATCHER_MODULE}.get_state") as mock_get_state:
            mock_get_state.return_value.vector_store = None
            watcher._do_reindex()  # Should NOT raise

    def test_logs_error_on_unexpected_exception(
        self, watcher: FileWatcher, mock_indexer, tmp_path: Path, caplog
    ) -> None:
        """_do_reindex() logs the error when an unexpected exception occurs."""
        mock_indexer.remove_file.side_effect = RuntimeError("database is locked")

        gone_file = tmp_path / "gone.py"
        watcher._deleted_files.add(gone_file)
        watcher._last_reindex_time = 0.0

        with (
            patch(f"{_WATCHER_MODULE}.get_state") as mock_get_state,
            caplog.at_level(logging.ERROR),
        ):
            mock_get_state.return_value.vector_store = None
            watcher._do_reindex()

        assert "Watcher reindex failed unexpectedly" in caplog.text

    def test_survives_vector_store_exception(
        self, watcher: FileWatcher, mock_indexer, tmp_path: Path
    ) -> None:
        """_do_reindex() survives when vector_store.count_unique_files() fails."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        watcher._pending_files.add(test_file)
        watcher._last_reindex_time = 0.0

        mock_vs = MagicMock()
        mock_vs.count_unique_files.side_effect = RuntimeError("ChromaDB internal error")

        with patch(f"{_WATCHER_MODULE}.get_state") as mock_get_state:
            mock_get_state.return_value.vector_store = mock_vs
            watcher._do_reindex()  # Should NOT raise

    def test_empty_queues_return_early(self, watcher: FileWatcher) -> None:
        """_do_reindex() returns immediately when there are no pending changes."""
        # No files queued — should return without error
        watcher._do_reindex()
