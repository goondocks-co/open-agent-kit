"""FastAPI server for Codebase Intelligence daemon.

This module creates the FastAPI application and manages the daemon lifecycle.
Route handlers are organized in separate modules under daemon/routes/.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_CHROMA_DIR,
    CI_CORS_ALLOWED_HEADERS,
    CI_CORS_ALLOWED_METHODS,
    CI_CORS_HOST_LOCALHOST,
    CI_CORS_HOST_LOOPBACK,
    CI_CORS_ORIGIN_TEMPLATE,
    CI_CORS_SCHEME_HTTP,
    CI_DATA_DIR,
    CI_HOOKS_LOG_FILE,
    CI_LOG_FILE,
    CI_TUNNEL_ERROR_START_UNKNOWN,
    CI_TUNNEL_LOG_ACTIVE,
    CI_TUNNEL_LOG_AUTO_START,
    CI_TUNNEL_LOG_AUTO_START_FAILED,
    CI_TUNNEL_LOG_AUTO_START_UNAVAILABLE,
    DEFAULT_INDEXING_TIMEOUT_SECONDS,
    SHUTDOWN_TASK_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.config import (
        CIConfig,
        LogRotationConfig,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState
    from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


async def _background_index() -> None:
    """Run initial indexing in background."""
    state = get_state()

    if not state.indexer or not state.vector_store:
        logger.warning("Cannot start background indexing - components not initialized")
        return

    # Check if index already has data
    stats = state.vector_store.get_stats()
    if stats.get("code_chunks", 0) > 0:
        logger.info(f"Index already has {stats['code_chunks']} chunks, skipping initial index")
        state.index_status.set_ready()
        state.index_status.file_count = state.vector_store.count_unique_files()
        # Still start file watcher for incremental updates
        await _start_file_watcher()
        return

    logger.info("Starting background indexing...")

    # Set indexing status BEFORE running in executor to eliminate race condition
    # where UI polls between task scheduling and executor start
    state.index_status.set_indexing()

    try:
        # Run unified index build in executor with timeout
        # Pass _status_preset=True since we already set is_indexing above
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: state.run_index_build(full_rebuild=True, _status_preset=True),
            ),
            timeout=DEFAULT_INDEXING_TIMEOUT_SECONDS,
        )

        if result is not None:
            # Start file watcher for incremental updates
            await _start_file_watcher()

    except TimeoutError:
        logger.error(f"Background indexing timed out after {DEFAULT_INDEXING_TIMEOUT_SECONDS}s")
        state.index_status.set_error()
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Background indexing failed: {e}")
        state.index_status.set_error()
    finally:
        # Only update file count from DB if it wasn't set by successful indexing
        # This prevents overwriting the accurate count from run_index_build() result
        if state.index_status.file_count == 0 and state.vector_store:
            try:
                state.index_status.file_count = state.vector_store.count_unique_files()
            except (OSError, AttributeError, RuntimeError) as e:
                logger.warning(f"Failed to update file count: {e}")


async def _start_file_watcher() -> None:
    """Start file watcher for real-time incremental updates."""
    state = get_state()

    if state.file_watcher is not None:
        return  # Already running

    if not state.indexer or not state.project_root:
        logger.warning("Cannot start file watcher - indexer not initialized")
        return

    try:
        from open_agent_kit.features.codebase_intelligence.indexing.watcher import (
            FileWatcher,
        )

        def on_index_start() -> None:
            state.index_status.set_updating()

        def on_index_complete(chunks: int) -> None:
            state.index_status.set_ready()

        watcher = FileWatcher(
            project_root=state.project_root,
            indexer=state.indexer,
            on_index_start=on_index_start,
            on_index_complete=on_index_complete,
        )

        # Start in thread pool
        loop = asyncio.get_event_loop()
        started = await loop.run_in_executor(None, watcher.start)

        if started:
            state.file_watcher = watcher
            logger.info("File watcher started for real-time index updates")
        else:
            logger.warning("File watcher could not be started (watchdog not installed?)")

    except (OSError, ImportError, RuntimeError) as e:
        logger.warning(f"Failed to start file watcher: {e}")


def _run_chromadb_rebuild_sync(
    activity_processor: "ActivityProcessor",
    rebuild_type: str,
    count: int,
) -> None:
    """Run ChromaDB rebuild synchronously (for use in background thread).

    Args:
        activity_processor: The activity processor instance.
        rebuild_type: Either "full" or "pending" to indicate rebuild type.
        count: Number of observations to process (for logging).
    """
    try:
        if rebuild_type == "full":
            logger.info(f"Background ChromaDB rebuild started ({count} observations)...")
            stats = activity_processor.rebuild_chromadb_from_sqlite()
            logger.info(
                f"Background ChromaDB rebuild complete: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )
        else:
            logger.info(f"Background embedding started ({count} observations)...")
            stats = activity_processor.embed_pending_observations()
            logger.info(
                f"Background embedding complete: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Background ChromaDB operation failed: {e}")


async def _check_and_rebuild_chromadb(state: "DaemonState") -> None:
    """Check for SQLite/ChromaDB mismatch and schedule rebuild if needed.

    SQLite is the source of truth for memory observations. If ChromaDB
    is empty or was wiped but SQLite has observations, this schedules
    a background rebuild to restore the search index.

    IMPORTANT: This function does NOT block startup. Rebuilds run in
    a background thread so the daemon can start accepting requests
    immediately. The health endpoint reports rebuild status.

    This handles the case where:
    - ChromaDB was deleted/corrupted
    - Embedding dimensions changed requiring full re-index
    - Fresh ChromaDB but existing SQLite data

    Args:
        state: Daemon state with activity_store, vector_store, and activity_processor.
    """
    if not state.activity_store or not state.vector_store or not state.activity_processor:
        return

    try:
        # Count observations in SQLite (source of truth)
        sqlite_count = state.activity_store.count_observations()
        if sqlite_count == 0:
            logger.debug("No observations in SQLite - nothing to rebuild")
            return

        # Count memories in ChromaDB
        try:
            chromadb_count = state.vector_store.count_memories()
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Could not count ChromaDB memories: {e}")
            chromadb_count = 0

        # Check for mismatch
        unembedded_count = state.activity_store.count_unembedded_observations()

        logger.info(
            f"Memory sync check: SQLite={sqlite_count}, ChromaDB={chromadb_count}, "
            f"unembedded={unembedded_count}"
        )

        # If ChromaDB is empty but SQLite has data, schedule background rebuild
        if chromadb_count == 0 and sqlite_count > 0:
            logger.warning(
                f"ChromaDB is empty but SQLite has {sqlite_count} observations. "
                "Scheduling background rebuild (startup will continue)..."
            )
            # Run rebuild in background thread - don't await, let startup continue
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                _run_chromadb_rebuild_sync,
                state.activity_processor,
                "full",
                sqlite_count,
            )
        # If there are unembedded observations, schedule background embedding
        elif unembedded_count > 0:
            logger.info(
                f"Found {unembedded_count} unembedded observations. "
                "Scheduling background embedding (startup will continue)..."
            )
            # Run embedding in background thread - don't await, let startup continue
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                _run_chromadb_rebuild_sync,
                state.activity_processor,
                "pending",
                unembedded_count,
            )

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Error during ChromaDB sync check: {e}")


def _configure_logging(
    log_level: str,
    log_file: Path | None = None,
    log_rotation: "LogRotationConfig | None" = None,
) -> None:
    """Configure logging for the daemon.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional log file path.
        log_rotation: Optional log rotation configuration.
    """
    from logging.handlers import RotatingFileHandler

    from open_agent_kit.features.codebase_intelligence.config import LogRotationConfig

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure the CI logger (our application logger)
    ci_logger = logging.getLogger("open_agent_kit.features.codebase_intelligence")
    ci_logger.setLevel(level)

    # CRITICAL: Prevent propagation to root logger to avoid duplicates
    # Uvicorn sets up handlers on the root logger before lifespan runs
    ci_logger.propagate = False

    # Clear any existing handlers to avoid duplicates on restart/reconfigure
    ci_logger.handlers.clear()

    # Suppress uvicorn's loggers - we handle our own logging
    # Set to WARNING so only actual errors come through
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # In debug mode, we might want to see uvicorn errors
    if level == logging.DEBUG:
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Configure the dedicated hooks logger (separate file for hook lifecycle events)
    # This logger is always INFO level for complete hook visibility
    hooks_logger = logging.getLogger("oak.ci.hooks")
    hooks_logger.setLevel(logging.INFO)  # Always INFO for hooks.log
    hooks_logger.propagate = False  # Don't duplicate to daemon.log
    hooks_logger.handlers.clear()  # Clear existing handlers on restart

    # Create formatter
    if level == logging.DEBUG:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    # Add file handler if log file specified (daemon mode)
    # When file logging is enabled, skip stream handler to avoid duplicates
    # (stdout is redirected to /dev/null by the daemon manager)
    if log_file:
        try:
            rotation = log_rotation or LogRotationConfig()

            # Declare with base Handler type to satisfy mypy for both branches
            file_handler: logging.Handler
            if rotation.enabled:
                # Use RotatingFileHandler to prevent unbounded log growth
                file_handler = RotatingFileHandler(
                    log_file,
                    mode="a",
                    maxBytes=rotation.get_max_bytes(),
                    backupCount=rotation.backup_count,
                    encoding="utf-8",
                )
            else:
                # Rotation disabled - use standard FileHandler
                file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")

            file_handler.setFormatter(formatter)
            ci_logger.addHandler(file_handler)

            # IMPORTANT: Add our handler to uvicorn's error logger
            # This captures uvicorn tracebacks through rotation instead of raw stderr
            # Since subprocess stdout/stderr now goes to /dev/null, this ensures
            # uvicorn errors are still captured in the rotated log file
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.addHandler(file_handler)

            # Set up hooks logger file handler (separate file for hook lifecycle events)
            hooks_log_file = log_file.parent / CI_HOOKS_LOG_FILE
            hooks_handler: logging.Handler
            if rotation.enabled:
                hooks_handler = RotatingFileHandler(
                    hooks_log_file,
                    mode="a",
                    maxBytes=rotation.get_max_bytes(),
                    backupCount=rotation.backup_count,
                    encoding="utf-8",
                )
            else:
                hooks_handler = logging.FileHandler(hooks_log_file, mode="a", encoding="utf-8")
            hooks_handler.setFormatter(formatter)
            hooks_logger.addHandler(hooks_handler)

        except OSError as e:
            ci_logger.warning(f"Could not set up file logging to {log_file}: {e}")
    else:
        # Only add stream handler when NOT running as daemon
        # (avoids duplicates since daemon stdout goes to log file)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        ci_logger.addHandler(stream_handler)


def _init_tunnel(state: "DaemonState", project_root: Path) -> None:
    """Auto-start tunnel if configured.

    Non-critical: failures are logged but do not prevent startup.
    """
    ci_config = state.ci_config
    if not ci_config or not ci_config.tunnel.auto_start:
        return

    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )
    from open_agent_kit.features.codebase_intelligence.tunnel.factory import (
        create_tunnel_provider,
    )

    logger.info(CI_TUNNEL_LOG_AUTO_START)
    try:
        provider = create_tunnel_provider(
            provider=ci_config.tunnel.provider,
            cloudflared_path=ci_config.tunnel.cloudflared_path,
            ngrok_path=ci_config.tunnel.ngrok_path,
        )
        if not provider.is_available:
            logger.warning(CI_TUNNEL_LOG_AUTO_START_UNAVAILABLE.format(provider=provider.name))
            return

        ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        port = get_project_port(project_root, ci_data_dir)
        status = provider.start(port)
        if status.active and status.public_url:
            state.tunnel_provider = provider
            state.add_cors_origin(status.public_url)
            logger.info(CI_TUNNEL_LOG_ACTIVE.format(public_url=status.public_url))
        else:
            error_detail = status.error or CI_TUNNEL_ERROR_START_UNKNOWN
            logger.warning(CI_TUNNEL_LOG_AUTO_START_FAILED.format(error=error_detail))
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(CI_TUNNEL_LOG_AUTO_START_FAILED.format(error=e))


def _init_embedding(state: "DaemonState", project_root: Path) -> bool:
    """Create and verify the embedding provider.

    Returns True if the provider is available for immediate use.
    """
    from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
        create_provider_from_config,
    )

    ci_config = state.ci_config
    if ci_config is None:
        state.embedding_chain = None
        return False

    try:
        primary_provider = create_provider_from_config(ci_config.embedding)
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to create embedding provider: {e}")
        logger.info("Configure your provider in the Settings tab to start indexing.")
        state.embedding_chain = None
        return False

    if not primary_provider.is_available:
        logger.warning(
            f"Embedding provider {primary_provider.name} not available. "
            "Make sure Ollama is running or configure an OpenAI-compatible provider."
        )
        logger.info("Configure your provider in the Settings tab to start indexing.")
        state.embedding_chain = EmbeddingProviderChain(providers=[primary_provider])
        return False

    state.embedding_chain = EmbeddingProviderChain(providers=[primary_provider])

    # Verify dimensions on startup - detect actual model output dimensions
    _verify_embedding_dimensions(primary_provider, ci_config, project_root)

    logger.info(
        f"Created embedding provider: {primary_provider.name} "
        f"(dims={ci_config.embedding.get_dimensions()}, "
        f"max_chunk={ci_config.embedding.get_max_chunk_chars()})"
    )
    return True


def _verify_embedding_dimensions(
    primary_provider: "EmbeddingProvider", ci_config: "CIConfig", project_root: Path
) -> None:
    """Detect actual model dimensions and update config if needed."""
    try:
        test_result = primary_provider.embed(["dimension test"])
        if not (test_result.embeddings and len(test_result.embeddings) > 0):
            return

        detected_dims = len(test_result.embeddings[0])
        config_dims = ci_config.embedding.dimensions

        if config_dims is None:
            from open_agent_kit.features.codebase_intelligence.config import save_ci_config

            ci_config.embedding.dimensions = detected_dims
            save_ci_config(project_root, ci_config)
            logger.info(f"Auto-detected and saved embedding dimensions: {detected_dims}")
        elif config_dims != detected_dims:
            from open_agent_kit.features.codebase_intelligence.config import save_ci_config

            logger.warning(
                f"Config dimensions ({config_dims}) don't match actual model "
                f"output ({detected_dims}). This model doesn't support dimension "
                f"truncation - updating config to {detected_dims}."
            )
            ci_config.embedding.dimensions = detected_dims
            save_ci_config(project_root, ci_config)
    except (OSError, RuntimeError, ValueError) as e:
        logger.warning(f"Could not verify dimensions: {e}")


def _init_vector_store_and_indexer(
    state: "DaemonState", project_root: Path, provider_available: bool
) -> None:
    """Initialize vector store and code indexer.

    Requires ``state.embedding_chain`` to be set. If the embedding chain is
    ``None`` the vector store and indexer are left as ``None``.
    """
    if state.embedding_chain is None:
        logger.warning("Skipping vector store initialization - no embedding provider")
        state.vector_store = None
        state.indexer = None
        return

    ci_config = state.ci_config
    if ci_config is None:
        return

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR / CI_CHROMA_DIR

    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

    state.vector_store = VectorStore(
        persist_directory=ci_data_dir,
        embedding_provider=state.embedding_chain,
    )
    logger.info(f"Vector store initialized at {ci_data_dir}")

    # Initialize indexer with configured chunk size
    from open_agent_kit.features.codebase_intelligence.indexing.chunker import ChunkerConfig
    from open_agent_kit.features.codebase_intelligence.indexing.indexer import (
        CodebaseIndexer,
        IndexerConfig,
    )

    chunker_config = ChunkerConfig(
        max_chunk_chars=ci_config.embedding.get_max_chunk_chars(),
    )

    # Get combined exclusion patterns from config (defaults + user patterns)
    combined_patterns = ci_config.get_combined_exclude_patterns()
    user_patterns = ci_config.get_user_exclude_patterns()
    if user_patterns:
        logger.debug(f"User exclude patterns: {user_patterns}")

    indexer_config = IndexerConfig(ignore_patterns=combined_patterns)

    state.indexer = CodebaseIndexer(
        project_root=project_root,
        vector_store=state.vector_store,
        config=indexer_config,
        chunker_config=chunker_config,
    )

    # Start background indexing only if provider is available
    if provider_available:
        task = asyncio.create_task(_background_index(), name="background_index")
        state.background_tasks.append(task)
    else:
        logger.info(
            "Skipping auto-index - provider not available. Save settings to start indexing."
        )


async def _init_activity(state: "DaemonState", project_root: Path) -> None:
    """Initialize the activity store and processor.

    Requires ``state.vector_store`` to be set for full processor init.
    """
    ci_config = state.ci_config
    if ci_config is None:
        return

    from open_agent_kit.features.codebase_intelligence.activity import (
        ActivityProcessor,
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )
    from open_agent_kit.features.codebase_intelligence.summarization import (
        create_summarizer_from_config,
    )

    activity_db_path = project_root / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
    state.machine_id = get_machine_identifier(project_root)
    state.activity_store = ActivityStore(activity_db_path, machine_id=state.machine_id)
    logger.info(f"Activity store initialized at {activity_db_path}")

    # Create processor with summarizer if configured
    summarizer = None
    if ci_config.summarization.enabled:
        summarizer = create_summarizer_from_config(ci_config.summarization)

    if state.vector_store:
        state.activity_processor = ActivityProcessor(
            activity_store=state.activity_store,
            vector_store=state.vector_store,
            summarizer=summarizer,
            project_root=str(project_root),
            context_tokens=ci_config.summarization.get_context_tokens(),
            session_quality_config=ci_config.session_quality,
        )

        # Check for SQLite/ChromaDB mismatch on startup
        await _check_and_rebuild_chromadb(state)

        # Schedule background processing using config interval
        bg_interval = ci_config.agents.background_processing_interval_seconds
        state.activity_processor.schedule_background_processing(interval_seconds=bg_interval)
        logger.info(
            f"Activity processor initialized with background scheduling "
            f"(interval={bg_interval}s)"
        )


def _init_agents(state: "DaemonState", project_root: Path) -> None:
    """Initialize the agent subsystem (registry, executor, scheduler).

    Non-critical: failures are logged but do not prevent startup.
    """
    ci_config = state.ci_config
    if ci_config is None:
        return

    if not ci_config.agents.enabled:
        logger.info("Agent subsystem disabled in config")
        return

    from open_agent_kit.features.codebase_intelligence.agents import (
        AgentExecutor,
        AgentRegistry,
    )

    state.agent_registry = AgentRegistry(project_root=project_root)
    agent_count = state.agent_registry.load_all()
    logger.info(f"Agent registry loaded {agent_count} agents")

    state.agent_executor = AgentExecutor(
        project_root=project_root,
        agent_config=ci_config.agents,
        retrieval_engine=state.retrieval_engine,
        activity_store=state.activity_store,
        vector_store=state.vector_store,
    )
    logger.info(f"Agent executor initialized (cache_size={ci_config.agents.executor_cache_size})")

    # Initialize scheduler if activity_store is available
    if state.activity_store:
        from open_agent_kit.features.codebase_intelligence.agents.scheduler import (
            AgentScheduler,
        )

        state.agent_scheduler = AgentScheduler(
            activity_store=state.activity_store,
            agent_registry=state.agent_registry,
            agent_executor=state.agent_executor,
            agent_config=ci_config.agents,
        )
        # Sync schedules from YAML definitions to database
        sync_result = state.agent_scheduler.sync_schedules()
        logger.info(
            f"Agent scheduler initialized: {sync_result['total']} schedules "
            f"({sync_result['created']} created, {sync_result['updated']} updated)"
        )
        # Start the background scheduling loop (uses config interval)
        state.agent_scheduler.start()


async def _shutdown(state: "DaemonState") -> None:
    """Graceful shutdown sequence for all subsystems."""
    logger.info("Initiating graceful shutdown...")

    # 1. Cancel background tasks and wait for them with timeout
    for task in state.background_tasks:
        if not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=SHUTDOWN_TASK_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                logger.warning(
                    f"Task {task.get_name()} did not cancel within {SHUTDOWN_TASK_TIMEOUT_SECONDS}s"
                )
            except (RuntimeError, OSError) as e:
                logger.warning(f"Error cancelling task {task.get_name()}: {e}")
    state.background_tasks.clear()

    # 2. Activity processor uses daemon timers that auto-terminate on shutdown
    # No explicit stop needed - daemon threads exit with the process
    if state.activity_processor:
        logger.info("Activity processor will terminate with daemon shutdown")

    # 3. Stop agent scheduler
    if state.agent_scheduler:
        logger.info("Stopping agent scheduler...")
        try:
            state.agent_scheduler.stop()
        except (RuntimeError, OSError) as e:
            logger.warning(f"Error stopping agent scheduler: {e}")
        finally:
            state.agent_scheduler = None

    # 4. Stop tunnel if active
    if state.tunnel_provider:
        logger.info("Stopping tunnel...")
        try:
            status = state.tunnel_provider.get_status()
            if status.public_url:
                state.remove_cors_origin(status.public_url)
            state.tunnel_provider.stop()
        except (RuntimeError, OSError) as e:
            logger.warning(f"Error stopping tunnel: {e}")
        finally:
            state.tunnel_provider = None

    # 5. Stop file watcher and wait for thread cleanup
    if state.file_watcher:
        logger.info("Stopping file watcher...")
        try:
            state.file_watcher.stop()
            # Give watcher thread time to exit cleanly
            await asyncio.sleep(0.5)
        except (RuntimeError, OSError, AttributeError) as e:
            logger.warning(f"Error stopping file watcher: {e}")
        finally:
            state.file_watcher = None

    logger.info("Codebase Intelligence daemon shutdown complete")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage daemon lifecycle.

    Initialization order matters: embedding → vector store → activity → agents.
    Each helper is self-contained and logs its own errors so failures in one
    subsystem do not block the rest of startup.
    """
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config

    state = get_state()

    # Get project root from state (set by create_app)
    project_root = state.project_root or Path.cwd()
    state.initialize(project_root)

    # Load configuration
    ci_config = load_ci_config(project_root)
    state.ci_config = ci_config
    state.config = ci_config.to_dict()

    # Configure logging
    effective_log_level = ci_config.get_effective_log_level()
    log_file = project_root / OAK_DIR / CI_DATA_DIR / CI_LOG_FILE
    _configure_logging(effective_log_level, log_file=log_file, log_rotation=ci_config.log_rotation)
    state.log_level = effective_log_level

    logger.info(f"Codebase Intelligence daemon starting up (log_level={effective_log_level})")
    if effective_log_level == "DEBUG":
        logger.debug("Debug logging enabled - verbose output active")

    # Initialize secrets redaction patterns (before any activity storage)
    from open_agent_kit.features.codebase_intelligence.utils.redact import (
        initialize as initialize_redaction,
    )

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    initialize_redaction(ci_data_dir)

    # --- Subsystem init (order matters: embedding → vector store → activity → agents) ---
    _init_tunnel(state, project_root)

    provider_available = _init_embedding(state, project_root)

    try:
        _init_vector_store_and_indexer(state, project_root, provider_available)

        try:
            await _init_activity(state, project_root)
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize activity store: {e}")
            state.activity_store = None
            state.activity_processor = None

        try:
            _init_agents(state, project_root)
        except ImportError as e:
            logger.warning(f"Agent subsystem unavailable (SDK not installed): {e}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize agent subsystem: {e}")
            state.agent_registry = None
            state.agent_executor = None
            state.agent_scheduler = None

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to initialize: {e}")
        state.vector_store = None
        state.indexer = None

    yield

    await _shutdown(state)


def create_app(
    project_root: Path | None = None,
    config: dict | None = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        project_root: Root directory of the project.
        config: Optional configuration overrides.

    Returns:
        Configured FastAPI application.
    """
    import os

    state = get_state()

    # Get project root from parameter, environment, or current directory
    if project_root:
        state.project_root = project_root
    elif os.environ.get("OAK_CI_PROJECT_ROOT"):
        state.project_root = Path(os.environ["OAK_CI_PROJECT_ROOT"])
    else:
        state.project_root = Path.cwd()

    state.config = config or {}

    app = FastAPI(
        title="OAK Codebase Intelligence",
        description="Semantic search and persistent memory for AI assistants",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add dynamic CORS middleware - localhost origins are static,
    # tunnel URLs are added/removed at runtime
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.middleware import (
        DynamicCORSMiddleware,
    )

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(state.project_root, ci_data_dir)
    allowed_origins = [
        CI_CORS_ORIGIN_TEMPLATE.format(
            scheme=CI_CORS_SCHEME_HTTP,
            host=CI_CORS_HOST_LOCALHOST,
            port=port,
        ),
        CI_CORS_ORIGIN_TEMPLATE.format(
            scheme=CI_CORS_SCHEME_HTTP,
            host=CI_CORS_HOST_LOOPBACK,
            port=port,
        ),
    ]
    app.add_middleware(
        DynamicCORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=list(CI_CORS_ALLOWED_METHODS),
        allow_headers=list(CI_CORS_ALLOWED_HEADERS),
    )

    # Include routers
    from open_agent_kit.features.codebase_intelligence.daemon.routes import (
        activity,
        activity_management,
        activity_relationships,
        activity_sessions,
        agents,
        backup,
        devtools,
        health,
        hooks,
        index,
        mcp,
        notifications,
        otel,
        schedules,
        search,
        tunnel,
        ui,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.routes import (
        config as config_routes,
    )

    # Routes already include full paths (e.g., /api/health, /api/search)
    # so no prefix is needed
    app.include_router(health.router)
    app.include_router(config_routes.router)
    app.include_router(index.router)
    app.include_router(search.router)
    app.include_router(activity.router)
    app.include_router(activity_sessions.router)
    app.include_router(activity_relationships.router)
    app.include_router(activity_management.router)
    app.include_router(notifications.router)
    app.include_router(hooks.router)
    app.include_router(otel.router)
    app.include_router(mcp.router)
    app.include_router(agents.router)
    app.include_router(schedules.router)
    app.include_router(devtools.router)
    app.include_router(backup.router)
    app.include_router(tunnel.router)

    # UI router must be last to catch fallback routes
    app.include_router(ui.router)

    # Mount static files
    # Use strict=False to allow serving files on windows if needed, but mainly ensure verify directory exists
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    else:
        logger.warning(f"Static directory not found at {static_dir}")

    return app
