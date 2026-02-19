"""Type-safe daemon state management.

This module provides a thread-safe, type-safe state container for the
CI daemon, replacing the previous module-level dictionary approach.

Benefits of this design:
1. Type safety - IDE autocomplete and static analysis support
2. Testability - State can be easily mocked/reset in tests
3. Single responsibility - State management separated from routing
4. Encapsulation - Controlled access to state via properties
"""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    INDEX_STATUS_IDLE,
    POWER_STATE_ACTIVE,
    POWER_STATE_DEEP_SLEEP,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.agents.scheduler import AgentScheduler
    from open_agent_kit.features.codebase_intelligence.cloud_relay.base import RelayClient
    from open_agent_kit.features.codebase_intelligence.config import CIConfig
    from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain
    from open_agent_kit.features.codebase_intelligence.governance.engine import GovernanceEngine
    from open_agent_kit.features.codebase_intelligence.indexing.indexer import (
        CodebaseIndexer,
        IndexStats,
    )
    from open_agent_kit.features.codebase_intelligence.indexing.watcher import FileWatcher
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine
    from open_agent_kit.features.codebase_intelligence.tunnel.base import TunnelProvider


@dataclass
class IndexStatus:
    """Status of the code index.

    Tracks indexing progress and statistics for monitoring.
    Thread-safe for concurrent access from HTTP handlers.
    """

    status: str = INDEX_STATUS_IDLE
    progress: int = 0
    total: int = 0
    last_indexed: str | None = None
    is_indexing: bool = False
    duration_seconds: float = 0.0
    file_count: int = 0
    ast_stats: dict[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def set_indexing(self) -> None:
        """Mark index as currently indexing."""
        with self._lock:
            self.status = "indexing"
            self.is_indexing = True
            self.progress = 0
            self.total = 0

    def set_ready(self, duration: float | None = None) -> None:
        """Mark index as ready.

        Args:
            duration: Optional duration of indexing in seconds.
        """
        with self._lock:
            self.status = "ready"
            self.is_indexing = False
            self.last_indexed = datetime.now().isoformat()
            if duration is not None:
                self.duration_seconds = duration

    def set_error(self) -> None:
        """Mark index as in error state."""
        with self._lock:
            self.status = "error"
            self.is_indexing = False

    def set_updating(self) -> None:
        """Mark index as updating (incremental)."""
        with self._lock:
            self.status = "updating"
            self.is_indexing = True

    def update_progress(self, current: int, total: int) -> None:
        """Update indexing progress.

        Args:
            current: Current number of files processed.
            total: Total number of files to process.
        """
        with self._lock:
            self.progress = current
            self.total = total

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses (thread-safe)."""
        with self._lock:
            return {
                "status": self.status,
                "progress": self.progress,
                "total": self.total,
                "last_indexed": self.last_indexed,
                "is_indexing": self.is_indexing,
                "duration_seconds": self.duration_seconds,
                "file_count": self.file_count,
                "ast_stats": dict(self.ast_stats),
            }


@dataclass
class DaemonState:
    """Type-safe state container for the CI daemon.

    This class encapsulates all daemon state in a type-safe manner,
    replacing the previous module-level `_state` dictionary.

    Note: Session tracking is handled entirely by SQLite (ActivityStore).
    There is no in-memory session state - this ensures consistency across
    daemon restarts and eliminates a class of state synchronization bugs.

    Attributes:
        start_time: Daemon start timestamp (epoch seconds).
        project_root: Root directory of the project being indexed.
        embedding_chain: Chain of embedding providers with fallback.
        vector_store: ChromaDB-backed vector store.
        indexer: Code indexer instance.
        file_watcher: File system watcher for incremental updates.
        config: Loaded CI configuration.
        ci_config: Full CI configuration (lazy-loaded property, cached after first access).
        log_level: Effective log level.
        index_status: Current indexing status.
        machine_id: Deterministic machine identifier (computed once at startup).
        activity_store: SQLite store for activity logging and session tracking.
        activity_processor: Background processor for observation extraction.
        background_tasks: Tracked asyncio tasks for proper cleanup.
        index_lock: Lock for serializing index operations.
    """

    start_time: float | None = None
    project_root: Path | None = None
    embedding_chain: "EmbeddingProviderChain | None" = None
    vector_store: "VectorStore | None" = None
    indexer: "CodebaseIndexer | None" = None
    file_watcher: "FileWatcher | None" = None
    config: dict[str, Any] = field(default_factory=dict)
    _ci_config: "CIConfig | None" = field(default=None, init=False, repr=False)
    _ci_config_mtime: float = field(default=0.0, init=False, repr=False)
    log_level: str = "INFO"
    index_status: IndexStatus = field(default_factory=IndexStatus)
    machine_id: str | None = None
    activity_store: "ActivityStore | None" = None
    activity_processor: "ActivityProcessor | None" = None
    # Background task tracking for proper shutdown
    background_tasks: list["asyncio.Task[Any]"] = field(default_factory=list)
    # Lock for serializing index operations (prevents race conditions)
    index_lock: "asyncio.Lock | None" = None
    # Cached retrieval engine instance
    _retrieval_engine: "RetrievalEngine | None" = field(default=None, init=False, repr=False)
    # Cached governance engine instance (recreated when config changes)
    _governance_engine: "GovernanceEngine | None" = field(default=None, init=False, repr=False)
    _governance_config_id: int = field(default=0, init=False, repr=False)
    # Hook deduplication cache (key -> None, insertion ordered)
    hook_event_cache: "OrderedDict[str, None]" = field(default_factory=OrderedDict)
    _hook_event_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    # Agent subsystem
    agent_registry: "AgentRegistry | None" = None
    agent_executor: "AgentExecutor | None" = None
    agent_scheduler: "AgentScheduler | None" = None
    # Periodic auto-backup tracking
    last_auto_backup: float | None = None
    # Authentication token for API security (set from OAK_CI_TOKEN env var)
    auth_token: str | None = None
    # Tunnel sharing
    tunnel_provider: "TunnelProvider | None" = None
    # Cloud MCP Relay
    cloud_relay_client: "RelayClient | None" = None
    cf_account_name: str | None = None
    _dynamic_cors_origins: set[str] = field(default_factory=set, init=False, repr=False)
    _cors_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    # Version detection
    installed_version: str | None = None
    update_available: bool = False
    # Power state lifecycle
    last_hook_activity: float | None = None  # epoch of last hook event
    power_state: str = POWER_STATE_ACTIVE  # current power state
    _power_state_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def initialize(self, project_root: Path) -> None:
        """Initialize daemon state for startup.

        Args:
            project_root: Project root directory.
        """
        import time

        self.start_time = time.time()
        self.project_root = project_root
        self.index_status = IndexStatus()
        self.background_tasks = []
        self.index_lock = asyncio.Lock()

    @property
    def uptime_seconds(self) -> float:
        """Get daemon uptime in seconds."""
        if self.start_time is None:
            return 0.0
        import time

        return time.time() - self.start_time

    @property
    def is_ready(self) -> bool:
        """Check if daemon is fully initialized and ready."""
        return (
            self.project_root is not None
            and self.embedding_chain is not None
            and self.vector_store is not None
        )

    @property
    def retrieval_engine(self) -> "RetrievalEngine | None":
        """Get the retrieval engine instance.

        Lazily creates the engine when first accessed if vector_store is available.

        Returns:
            RetrievalEngine instance, or None if vector_store not available.
        """
        if self._retrieval_engine is not None:
            return self._retrieval_engine

        if self.vector_store is None:
            return None

        from open_agent_kit.features.codebase_intelligence.retrieval.engine import (
            RetrievalEngine,
        )

        self._retrieval_engine = RetrievalEngine(
            vector_store=self.vector_store,
            activity_store=self.activity_store,
        )
        return self._retrieval_engine

    @property
    def governance_engine(self) -> "GovernanceEngine | None":
        """Get the governance engine, lazily created from config.

        Returns None if governance is disabled. Automatically recreates
        the engine when the GovernanceConfig changes (detected via
        config object identity).

        Returns:
            GovernanceEngine instance, or None if governance is disabled.
        """
        config = self.ci_config
        if config is None:
            return None

        gov_config = config.governance
        if not gov_config.enabled:
            self._governance_engine = None
            return None

        # Recreate engine if config object changed (identity check)
        config_id = id(gov_config)
        if self._governance_engine is not None and self._governance_config_id == config_id:
            return self._governance_engine

        from open_agent_kit.features.codebase_intelligence.governance.engine import (
            GovernanceEngine,
        )

        self._governance_engine = GovernanceEngine(gov_config)
        self._governance_config_id = config_id
        return self._governance_engine

    @property
    def ci_config(self) -> "CIConfig | None":
        """Get CI configuration, lazy-loading from disk if needed.

        Returns cached config if available. Automatically reloads when
        config files change on disk (detected via mtime), so CLI changes
        like ``oak ci debug`` are picked up without a daemon restart.

        Returns:
            CIConfig instance, or None if project_root not set.
        """
        if self.project_root is None:
            return None

        # Check if config files changed since last load
        if self._ci_config is not None:
            current_mtime = self._get_config_mtime()
            if current_mtime == self._ci_config_mtime:
                return self._ci_config
            # Files changed on disk — invalidate and reload

        from open_agent_kit.features.codebase_intelligence.config import load_ci_config

        self._ci_config = load_ci_config(self.project_root)
        self._ci_config_mtime = self._get_config_mtime()
        return self._ci_config

    @ci_config.setter
    def ci_config(self, value: "CIConfig | None") -> None:
        """Set or invalidate the cached CI configuration."""
        self._ci_config = value
        if value is not None and self.project_root is not None:
            self._ci_config_mtime = self._get_config_mtime()

    def _get_config_mtime(self) -> float:
        """Get max mtime of config files (project + user overlay).

        Returns 0.0 if no config files exist. Uses stat() which is
        a cheap syscall (microseconds), safe to call on every access.
        """
        from open_agent_kit.config.paths import OAK_DIR

        if self.project_root is None:
            return 0.0

        mtime = 0.0
        config_path = self.project_root / OAK_DIR / "config.yaml"
        try:
            if config_path.exists():
                mtime = config_path.stat().st_mtime
        except OSError:
            pass

        # Also check user overlay
        try:
            from open_agent_kit.features.codebase_intelligence.config import (
                _user_config_path,
            )

            user_path = _user_config_path(self.project_root)
            if user_path.exists():
                user_mtime = user_path.stat().st_mtime
                if user_mtime > mtime:
                    mtime = user_mtime
        except OSError:
            pass

        return mtime

    def invalidate_retrieval_engine(self) -> None:
        """Invalidate cached retrieval engine.

        Call this when vector_store changes.
        """
        self._retrieval_engine = None

    def should_dedupe_hook_event(self, key: str, max_entries: int) -> bool:
        """Check and update hook dedupe cache for a key.

        Args:
            key: Deduplication key for the event.
            max_entries: Maximum number of keys to keep.

        Returns:
            True if a duplicate event should be skipped.
        """
        with self._hook_event_lock:
            if key in self.hook_event_cache:
                return True

            self.hook_event_cache[key] = None
            while len(self.hook_event_cache) > max_entries:
                self.hook_event_cache.popitem(last=False)
        return False

    def add_cors_origin(self, origin: str) -> None:
        """Add a dynamic CORS origin (e.g. tunnel URL).

        Args:
            origin: Origin URL to allow (e.g. "https://xxx.trycloudflare.com").
        """
        with self._cors_lock:
            self._dynamic_cors_origins.add(origin)

    def remove_cors_origin(self, origin: str) -> None:
        """Remove a dynamic CORS origin.

        Args:
            origin: Origin URL to remove.
        """
        with self._cors_lock:
            self._dynamic_cors_origins.discard(origin)

    def get_dynamic_cors_origins(self) -> set[str]:
        """Get current dynamic CORS origins (thread-safe copy).

        Returns:
            Copy of the dynamic CORS origins set.
        """
        with self._cors_lock:
            return set(self._dynamic_cors_origins)

    def run_index_build(
        self,
        full_rebuild: bool = True,
        timeout_seconds: float | None = None,
        _status_preset: bool = False,
    ) -> "IndexStats | None":
        """Run index build with proper status management.

        This is the single, canonical way to run an index build. All code paths
        (daemon startup, API endpoints, devtools) should use this method to ensure
        consistent status tracking and error handling.

        Args:
            full_rebuild: If True, clear existing index first.
            timeout_seconds: Optional timeout (uses default if None).
            _status_preset: Internal flag. If True, caller has already set
                is_indexing=True to eliminate UI timing gaps. Skips the
                concurrent-build check since we know we set the flag.

        Returns:
            IndexStats on success, None on failure.

        Note:
            This is a synchronous method. For async contexts, run it in an executor.
        """
        if not self.indexer:
            import logging

            logging.getLogger(__name__).error("Cannot run index build: indexer not initialized")
            return None

        # Check if already indexing (skip if caller preset the status)
        if not _status_preset and self.index_status.is_indexing:
            import logging

            logging.getLogger(__name__).warning("Index build already in progress, skipping")
            return None

        import logging

        logger = logging.getLogger(__name__)

        try:
            # Set status to indexing (skip if caller already set it)
            if not _status_preset:
                self.index_status.set_indexing()
            logger.info(f"Index build started (full_rebuild={full_rebuild})")

            # Progress callback updates status
            def progress_callback(current: int, total: int) -> None:
                self.index_status.update_progress(current, total)

            # Run the actual build
            stats: IndexStats = self.indexer.build_index(
                full_rebuild=full_rebuild,
                progress_callback=progress_callback,
            )

            # Update status with results
            self.index_status.file_count = stats.files_processed
            self.index_status.ast_stats = {
                "ast_success": stats.ast_success,
                "ast_fallback": stats.ast_fallback,
                "line_based": stats.line_based,
            }
            self.index_status.set_ready(duration=stats.duration_seconds)

            logger.info(
                f"Index build complete: {stats.chunks_indexed} chunks "
                f"from {stats.files_processed} files in {stats.duration_seconds:.1f}s"
            )

            return stats

        except TimeoutError:
            logger.error("Index build timed out")
            self.index_status.set_error()
            raise
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            logger.exception(f"Index build failed: {e}")
            self.index_status.set_error()
            return None

    def record_hook_activity(self) -> None:
        """Record that a hook event occurred. Thread-safe."""
        import time

        self.last_hook_activity = time.time()
        if self.power_state == POWER_STATE_DEEP_SLEEP:
            self._wake_from_deep_sleep()

    def _wake_from_deep_sleep(self) -> None:
        """Restart background cycle when activity resumes after deep sleep."""
        import logging

        logger = logging.getLogger(__name__)

        with self._power_state_lock:
            if self.power_state != POWER_STATE_DEEP_SLEEP:
                return
            self.power_state = POWER_STATE_ACTIVE
        logger.info("Power state: deep_sleep -> active (hook activity detected)")
        if self.file_watcher:
            self.file_watcher.start()
        if self.activity_processor:
            self.activity_processor.schedule_background_processing(
                state_accessor=lambda: self,
            )

    def reset(self) -> None:
        """Reset state for testing or restart."""
        self.start_time = None
        self.project_root = None
        self.embedding_chain = None
        self.vector_store = None
        self.indexer = None
        self.file_watcher = None
        self.config = {}
        self._ci_config = None
        self._ci_config_mtime = 0.0
        self.log_level = "INFO"
        self.index_status = IndexStatus()
        self.machine_id = None
        self.activity_store = None
        self.activity_processor = None
        self.background_tasks = []
        self.index_lock = None
        self._retrieval_engine = None
        self._governance_engine = None
        self._governance_config_id = 0
        self.hook_event_cache = OrderedDict()
        self.agent_registry = None
        self.agent_executor = None
        self.agent_scheduler = None
        self.last_auto_backup = None
        self.auth_token = None
        self.tunnel_provider = None
        self.cloud_relay_client = None
        self.cf_account_name = None
        self._dynamic_cors_origins = set()
        self.installed_version = None
        self.update_available = False
        self.last_hook_activity = None
        self.power_state = POWER_STATE_ACTIVE


# Global daemon state instance
# This is accessed by the server routes
daemon_state = DaemonState()


def get_state() -> DaemonState:
    """Get the global daemon state.

    Returns:
        The global DaemonState instance.
    """
    return daemon_state


def reset_state() -> None:
    """Reset the global daemon state.

    Useful for testing.
    """
    daemon_state.reset()
