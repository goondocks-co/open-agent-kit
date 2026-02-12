"""File watcher for real-time incremental index updates.

Monitors the codebase for file changes and triggers incremental
re-indexing to keep the vector store up to date.
"""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.indexing.indexer import (
    INDEXABLE_EXTENSIONS,
    CodebaseIndexer,
)

logger = logging.getLogger(__name__)

# Debounce delay to batch rapid changes
DEBOUNCE_DELAY_SECONDS = 1.0

# Minimum time between full reindex attempts
MIN_REINDEX_INTERVAL_SECONDS = 30.0


class FileWatcher:
    """Watch for file changes and trigger incremental indexing.

    Uses watchdog library for efficient file system monitoring.
    Debounces rapid changes to avoid excessive re-indexing.
    """

    def __init__(
        self,
        project_root: Path,
        indexer: CodebaseIndexer,
        on_index_start: Callable[[], None] | None = None,
        on_index_complete: Callable[[int], None] | None = None,
    ):
        """Initialize file watcher.

        Args:
            project_root: Root directory to watch.
            indexer: CodebaseIndexer instance for re-indexing.
            on_index_start: Callback when indexing starts.
            on_index_complete: Callback when indexing completes (receives chunk count).
        """
        self.project_root = project_root
        self.indexer = indexer
        self.on_index_start = on_index_start
        self.on_index_complete = on_index_complete

        self._observer: Any = None  # Lazy-loaded watchdog Observer
        self._pending_files: set[Path] = set()
        self._deleted_files: set[Path] = set()
        self._debounce_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._running = False
        self._last_reindex_time = 0.0

    def _should_watch_file(self, filepath: Path) -> bool:
        """Check if a file should trigger re-indexing.

        Uses the indexer's ignore patterns for consistency.

        Args:
            filepath: Path to check.

        Returns:
            True if file changes should trigger indexing.
        """
        # Check extension
        if filepath.suffix.lower() not in INDEXABLE_EXTENSIONS:
            return False

        # Use indexer's ignore check for consistency with indexing
        try:
            relative = filepath.relative_to(self.project_root)
            if self.indexer._should_ignore(relative):
                return False
        except ValueError:
            # Path is not relative to project root
            return False

        return True

    def _schedule_reindex(self) -> None:
        """Schedule a debounced re-index operation."""
        with self._lock:
            # Cancel existing timer
            if self._debounce_timer:
                self._debounce_timer.cancel()

            # Schedule new timer
            self._debounce_timer = threading.Timer(
                DEBOUNCE_DELAY_SECONDS,
                self._do_reindex,
            )
            self._debounce_timer.start()

    def _do_reindex(self) -> None:
        """Perform the actual re-indexing."""
        with self._lock:
            if not self._pending_files and not self._deleted_files:
                return

            # Check minimum interval
            now = time.time()
            if now - self._last_reindex_time < MIN_REINDEX_INTERVAL_SECONDS:
                # Reschedule for later
                remaining = MIN_REINDEX_INTERVAL_SECONDS - (now - self._last_reindex_time)
                self._debounce_timer = threading.Timer(remaining, self._do_reindex)
                self._debounce_timer.start()
                return

            pending = self._pending_files.copy()
            deleted = self._deleted_files.copy()
            self._pending_files.clear()
            self._deleted_files.clear()
            self._last_reindex_time = now

        logger.info(f"Processing file changes: {len(pending)} modified, {len(deleted)} deleted")

        try:
            if self.on_index_start:
                self.on_index_start()

            total_chunks = 0

            # Handle deleted files
            for filepath in deleted:
                try:
                    removed = self.indexer.remove_file(filepath)
                    logger.debug(f"Removed {removed} chunks for deleted file: {filepath}")
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to remove {filepath} from index: {e}")

            # Handle modified/created files
            for filepath in pending:
                if not filepath.exists():
                    # File was deleted after being queued
                    continue

                try:
                    chunks = self.indexer.index_single_file(filepath)
                    total_chunks += chunks
                    logger.debug(f"Re-indexed {filepath}: {chunks} chunks")
                except (OSError, ValueError, TypeError) as e:
                    logger.warning(f"Failed to re-index {filepath}: {e}")

            if self.on_index_complete:
                self.on_index_complete(total_chunks)

            # Update file count in state
            state = get_state()
            if state.vector_store:
                state.index_status.file_count = state.vector_store.count_unique_files()

            logger.info(f"Incremental indexing complete: {total_chunks} chunks updated")
        except Exception:
            logger.error("Watcher reindex failed unexpectedly", exc_info=True)

    def _on_file_created(self, filepath: Path) -> None:
        """Handle file creation event."""
        if not self._should_watch_file(filepath):
            return

        with self._lock:
            self._pending_files.add(filepath)

        logger.debug(f"File created: {filepath}")
        self._schedule_reindex()

    def _on_file_modified(self, filepath: Path) -> None:
        """Handle file modification event."""
        if not self._should_watch_file(filepath):
            return

        with self._lock:
            self._pending_files.add(filepath)

        logger.debug(f"File modified: {filepath}")
        self._schedule_reindex()

    def _on_file_deleted(self, filepath: Path) -> None:
        """Handle file deletion event."""
        if not self._should_watch_file(filepath):
            return

        with self._lock:
            self._deleted_files.add(filepath)
            # Remove from pending if it was there
            self._pending_files.discard(filepath)

        logger.debug(f"File deleted: {filepath}")
        self._schedule_reindex()

    def _on_file_moved(self, src_path: Path, dest_path: Path) -> None:
        """Handle file move event."""
        # Treat as delete + create
        self._on_file_deleted(src_path)
        self._on_file_created(dest_path)

    def start(self) -> bool:
        """Start watching for file changes.

        Returns:
            True if watcher started successfully.
        """
        if self._running:
            logger.info("File watcher already running")
            return True

        try:
            from watchdog.events import FileSystemEventHandler  # type: ignore[import-not-found]
            from watchdog.observers import Observer  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "watchdog library not installed, file watching disabled. "
                "Install with: pip install watchdog"
            )
            return False

        class EventHandler(FileSystemEventHandler):
            def __init__(handler_self, watcher: "FileWatcher") -> None:
                handler_self.watcher = watcher

            def on_created(handler_self, event: Any) -> None:
                if not event.is_directory:
                    handler_self.watcher._on_file_created(Path(event.src_path))

            def on_modified(handler_self, event: Any) -> None:
                if not event.is_directory:
                    handler_self.watcher._on_file_modified(Path(event.src_path))

            def on_deleted(handler_self, event: Any) -> None:
                if not event.is_directory:
                    handler_self.watcher._on_file_deleted(Path(event.src_path))

            def on_moved(handler_self, event: Any) -> None:
                if not event.is_directory:
                    handler_self.watcher._on_file_moved(
                        Path(event.src_path),
                        Path(event.dest_path),
                    )

        self._observer = Observer()
        self._observer.schedule(
            EventHandler(self),
            str(self.project_root),
            recursive=True,
        )
        self._observer.start()
        self._running = True

        logger.info(f"File watcher started for {self.project_root}")
        return True

    def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._running:
            return

        # Cancel pending timer
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        # Stop observer
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        self._running = False
        logger.info("File watcher stopped")

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    def get_pending_count(self) -> int:
        """Get number of pending file changes."""
        with self._lock:
            return len(self._pending_files) + len(self._deleted_files)


async def create_async_watcher(
    project_root: Path,
    indexer: CodebaseIndexer,
    on_index_start: Callable[[], None] | None = None,
    on_index_complete: Callable[[int], None] | None = None,
) -> FileWatcher:
    """Create and start a file watcher asynchronously.

    Args:
        project_root: Root directory to watch.
        indexer: CodebaseIndexer instance.
        on_index_start: Optional callback when indexing starts.
        on_index_complete: Optional callback when indexing completes.

    Returns:
        Started FileWatcher instance.
    """
    watcher = FileWatcher(
        project_root=project_root,
        indexer=indexer,
        on_index_start=on_index_start,
        on_index_complete=on_index_complete,
    )

    # Start in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, watcher.start)

    return watcher
