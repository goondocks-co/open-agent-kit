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
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.config import CIConfig
    from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain
    from open_agent_kit.features.codebase_intelligence.indexing.indexer import (
        CodebaseIndexer,
        IndexStats,
    )
    from open_agent_kit.features.codebase_intelligence.indexing.watcher import FileWatcher
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine


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
class ToolExecution:
    """Record of a single tool execution for session accumulation."""

    tool_name: str
    file_path: str | None  # For file operations
    summary: str  # Brief description of what happened
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionInfo:
    """Information about an active session.

    Tracks session activity for claude-mem inspired auto-capture.
    Accumulates tool executions for end-of-session summarization.

    Sessions contain one or more prompt batches. A prompt batch is created
    when a user sends a prompt and ended when the agent finishes responding.
    """

    session_id: str
    agent: str
    started_at: datetime
    observations: list[str] = field(default_factory=list)
    tool_calls: int = 0
    last_activity: datetime | None = None
    # Current prompt batch ID for activity linking
    current_prompt_batch_id: int | None = None
    # Last prompt identifiers for deduplication
    last_prompt_hash: str | None = None
    last_generation_id: str | None = None
    # Accumulated tool executions for LLM summarization
    tool_executions: list[ToolExecution] = field(default_factory=list)
    files_modified: set[str] = field(default_factory=set)
    files_created: set[str] = field(default_factory=set)
    files_read: set[str] = field(default_factory=set)
    commands_run: list[str] = field(default_factory=list)
    memory_injection_batch_id: int | None = None
    memory_injection_files: set[str] = field(default_factory=set)

    def record_tool_call(self) -> None:
        """Record a tool call in this session."""
        self.tool_calls += 1
        self.last_activity = datetime.now()

    def record_tool_execution(
        self,
        tool_name: str,
        file_path: str | None = None,
        summary: str = "",
    ) -> None:
        """Record a tool execution with details for summarization.

        Args:
            tool_name: Name of the tool (Read, Edit, Write, Bash, etc.)
            file_path: File path if applicable
            summary: Brief description of what the tool did
        """
        self.tool_calls += 1
        self.last_activity = datetime.now()

        # Track file operations
        if file_path:
            if tool_name == "Read":
                self.files_read.add(file_path)
            elif tool_name == "Edit":
                self.files_modified.add(file_path)
            elif tool_name == "Write":
                self.files_created.add(file_path)

        # Track commands
        if tool_name == "Bash" and summary:
            # Keep only last 20 commands to avoid memory bloat
            self.commands_run.append(summary[:200])
            if len(self.commands_run) > 20:
                self.commands_run = self.commands_run[-20:]

        # Store execution record (limit to last 50)
        self.tool_executions.append(
            ToolExecution(
                tool_name=tool_name,
                file_path=file_path,
                summary=summary[:300] if summary else "",
            )
        )
        if len(self.tool_executions) > 50:
            self.tool_executions = self.tool_executions[-50:]

    def should_inject_file_memory(self, prompt_batch_id: int | None, file_path: str) -> bool:
        """Check if file memory should be injected for current prompt batch."""
        if prompt_batch_id != self.memory_injection_batch_id:
            self.memory_injection_batch_id = prompt_batch_id
            self.memory_injection_files = set()

        if file_path in self.memory_injection_files:
            return False

        self.memory_injection_files.add(file_path)
        return True

    def add_observation(self, observation_id: str) -> None:
        """Add an observation ID to this session.

        Args:
            observation_id: ID of the stored observation.
        """
        self.observations.append(observation_id)
        self.last_activity = datetime.now()

    def count_search_tool_uses(self) -> int:
        """Count how many times search-type tools (Grep, Glob) have been used.

        Returns:
            Number of Grep/Glob tool uses in this session.
        """
        return sum(1 for t in self.tool_executions if t.tool_name in ("Grep", "Glob"))

    def has_used_oak_ci(self) -> bool:
        """Check if oak ci commands have been used in this session.

        Returns:
            True if any oak ci commands were run via Bash.
        """
        for t in self.tool_executions:
            if t.tool_name == "Bash" and t.summary:
                if "oak ci" in t.summary or "oak ci" in (t.file_path or ""):
                    return True
        return False

    def get_session_summary_context(self) -> str:
        """Generate context string for LLM summarization.

        Returns:
            Formatted string describing session activity for LLM processing.
        """
        parts = []

        duration = (datetime.now() - self.started_at).total_seconds() / 60
        parts.append(f"Session duration: {duration:.1f} minutes")
        parts.append(f"Tool calls: {self.tool_calls}")

        if self.files_created:
            parts.append(f"Files created: {', '.join(sorted(self.files_created)[:10])}")
        if self.files_modified:
            parts.append(f"Files modified: {', '.join(sorted(self.files_modified)[:10])}")
        if self.files_read:
            # Only show most relevant reads (last 5)
            recent_reads = list(self.files_read)[-5:]
            parts.append(f"Files explored: {', '.join(recent_reads)}")

        if self.commands_run:
            parts.append(f"Commands run: {len(self.commands_run)}")
            # Show unique command prefixes
            unique_cmds = {cmd.split()[0] if cmd else "" for cmd in self.commands_run}
            parts.append(f"Command types: {', '.join(sorted(unique_cmds)[:5])}")

        return "\n".join(parts)


@dataclass
class DaemonState:
    """Type-safe state container for the CI daemon.

    This class encapsulates all daemon state in a type-safe manner,
    replacing the previous module-level `_state` dictionary.

    Attributes:
        start_time: Daemon start timestamp (epoch seconds).
        project_root: Root directory of the project being indexed.
        embedding_chain: Chain of embedding providers with fallback.
        vector_store: ChromaDB-backed vector store.
        indexer: Code indexer instance.
        file_watcher: File system watcher for incremental updates.
        config: Loaded CI configuration.
        ci_config: Full CI configuration object.
        log_level: Effective log level.
        index_status: Current indexing status.
        sessions: Active sessions by ID.
        activity_store: SQLite store for activity logging.
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
    ci_config: "CIConfig | None" = None
    log_level: str = "INFO"
    index_status: IndexStatus = field(default_factory=IndexStatus)
    sessions: dict[str, SessionInfo] = field(default_factory=dict)
    activity_store: "ActivityStore | None" = None
    activity_processor: "ActivityProcessor | None" = None
    # Background task tracking for proper shutdown
    background_tasks: list["asyncio.Task[Any]"] = field(default_factory=list)
    # Lock for serializing index operations (prevents race conditions)
    index_lock: "asyncio.Lock | None" = None
    # Cached retrieval engine instance
    _retrieval_engine: "RetrievalEngine | None" = field(default=None, init=False, repr=False)
    # Hook deduplication cache (key -> None, insertion ordered)
    hook_event_cache: "OrderedDict[str, None]" = field(default_factory=OrderedDict)
    _hook_event_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    # Agent subsystem
    agent_registry: "AgentRegistry | None" = None
    agent_executor: "AgentExecutor | None" = None

    def initialize(self, project_root: Path) -> None:
        """Initialize daemon state for startup.

        Args:
            project_root: Project root directory.
        """
        import time

        self.start_time = time.time()
        self.project_root = project_root
        self.index_status = IndexStatus()
        self.sessions = {}
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
        )
        return self._retrieval_engine

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
        except Exception as e:
            logger.exception(f"Index build failed: {e}")
            self.index_status.set_error()
            return None

    def get_session(self, session_id: str) -> SessionInfo | None:
        """Get session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            SessionInfo if found, None otherwise.
        """
        return self.sessions.get(session_id)

    def create_session(self, session_id: str, agent: str) -> SessionInfo:
        """Create a new session.

        Args:
            session_id: Unique session identifier.
            agent: Agent name (claude, cursor, etc.).

        Returns:
            The created SessionInfo.
        """
        session = SessionInfo(
            session_id=session_id,
            agent=agent,
            started_at=datetime.now(),
            last_activity=datetime.now(),
        )
        self.sessions[session_id] = session
        return session

    def end_session(self, session_id: str) -> SessionInfo | None:
        """End a session and return its info.

        Args:
            session_id: The session to end.

        Returns:
            The ended SessionInfo, or None if not found.
        """
        return self.sessions.pop(session_id, None)

    def reset(self) -> None:
        """Reset state for testing or restart."""
        self.start_time = None
        self.project_root = None
        self.embedding_chain = None
        self.vector_store = None
        self.indexer = None
        self.file_watcher = None
        self.config = {}
        self.ci_config = None
        self.log_level = "INFO"
        self.index_status = IndexStatus()
        self.sessions = {}
        self.activity_store = None
        self.activity_processor = None
        self.background_tasks = []
        self.index_lock = None
        self._retrieval_engine = None
        self.hook_event_cache = OrderedDict()
        self.agent_registry = None
        self.agent_executor = None


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
