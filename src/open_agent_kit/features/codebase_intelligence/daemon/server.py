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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_INDEXING_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.config import CIConfig
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState
    from open_agent_kit.features.codebase_intelligence.embeddings.base import (
        EmbeddingProvider,
    )

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
    state.index_status.set_indexing()

    # Capture indexer to satisfy type narrowing in lambda
    indexer = state.indexer

    try:

        def progress_callback(current: int, total: int) -> None:
            state.index_status.update_progress(current, total)

        # Run indexing in thread pool to not block event loop
        # Add timeout protection to prevent runaway indexing
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: indexer.build_index(
                    full_rebuild=True,
                    progress_callback=progress_callback,
                ),
            ),
            timeout=DEFAULT_INDEXING_TIMEOUT_SECONDS,
        )

        state.index_status.set_ready(duration=result.duration_seconds)
        state.index_status.file_count = result.files_processed
        logger.info(
            f"Background indexing complete: {result.chunks_indexed} chunks "
            f"from {result.files_processed} files"
        )

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
        # This prevents overwriting the accurate count from build_index() result
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


async def _detect_and_persist_dimensions(
    provider: "EmbeddingProvider",
    ci_config: "CIConfig",
    project_root: Path,
) -> int | None:
    """Detect embedding dimensions and persist to config file.

    This ensures dimensions are always saved in config.yaml so they remain
    consistent across daemon restarts, preventing spurious dimension mismatches.

    Args:
        provider: The embedding provider to test.
        ci_config: Current CI configuration.
        project_root: Project root directory.

    Returns:
        Detected dimensions, or None if detection failed.
    """
    from open_agent_kit.features.codebase_intelligence.config import save_ci_config
    from open_agent_kit.features.codebase_intelligence.embeddings.base import (
        EmbeddingProvider,
    )

    # Type hint for the provider parameter
    embedding_provider: EmbeddingProvider = provider

    try:
        # Make a test embedding to detect dimensions
        result = embedding_provider.embed(["test"])
        if result.embeddings and len(result.embeddings) > 0:
            detected_dims = len(result.embeddings[0])

            # Update config and save
            ci_config.embedding.dimensions = detected_dims
            save_ci_config(project_root, ci_config)

            return detected_dims
    except (OSError, RuntimeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to detect embedding dimensions: {e}")

    return None


async def _check_and_rebuild_chromadb(state: "DaemonState") -> None:
    """Check for SQLite/ChromaDB mismatch and rebuild if needed.

    SQLite is the source of truth for memory observations. If ChromaDB
    is empty or was wiped but SQLite has observations, this triggers
    a rebuild to restore the search index.

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

        # If ChromaDB is empty but SQLite has data, rebuild
        if chromadb_count == 0 and sqlite_count > 0:
            logger.warning(
                f"ChromaDB is empty but SQLite has {sqlite_count} observations. "
                "Triggering rebuild from SQLite (source of truth)..."
            )
            # Run rebuild in thread pool to not block startup
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None,
                state.activity_processor.rebuild_chromadb_from_sqlite,
            )
            logger.info(
                f"ChromaDB rebuild complete: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )
        # If there are unembedded observations, process them
        elif unembedded_count > 0:
            logger.info(
                f"Found {unembedded_count} unembedded observations. "
                "Scheduling embedding in background..."
            )
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None,
                state.activity_processor.embed_pending_observations,
            )
            logger.info(
                f"Pending observations embedded: {stats['embedded']} embedded, "
                f"{stats['failed']} failed"
            )

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Error during ChromaDB sync check: {e}")


def _configure_logging(log_level: str, log_file: Path | None = None) -> None:
    """Configure logging for the daemon.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional log file path.
    """
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
    # (stdout is redirected to the log file by the daemon manager)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setFormatter(formatter)
            ci_logger.addHandler(file_handler)
        except OSError as e:
            ci_logger.warning(f"Could not set up file logging to {log_file}: {e}")
    else:
        # Only add stream handler when NOT running as daemon
        # (avoids duplicates since daemon stdout goes to log file)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        ci_logger.addHandler(stream_handler)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage daemon lifecycle."""
    state = get_state()

    # Get project root from state (set by create_app)
    project_root = state.project_root or Path.cwd()
    state.initialize(project_root)

    # Load configuration from project
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config
    from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
        create_provider_from_config,
    )

    ci_config = load_ci_config(project_root)
    state.ci_config = ci_config
    state.config = ci_config.to_dict()

    # Configure logging based on config and environment
    effective_log_level = ci_config.get_effective_log_level()
    log_file = project_root / ".oak" / "ci" / "daemon.log"
    _configure_logging(effective_log_level, log_file=log_file)
    state.log_level = effective_log_level

    logger.info(f"Codebase Intelligence daemon starting up (log_level={effective_log_level})")
    if effective_log_level == "DEBUG":
        logger.debug("Debug logging enabled - verbose output active")

    # Create embedding provider from config
    # Note: We require Ollama or OpenAI-compatible provider - no built-in fallback
    provider_available = False
    try:
        primary_provider = create_provider_from_config(ci_config.embedding)
        if primary_provider.is_available:
            state.embedding_chain = EmbeddingProviderChain(providers=[primary_provider])
            provider_available = True

            # Auto-detect and persist dimensions if not set in config
            # This ensures dimensions are always saved for consistent behavior across restarts
            if ci_config.embedding.dimensions is None:
                try:
                    detected_dims = await _detect_and_persist_dimensions(
                        primary_provider, ci_config, project_root
                    )
                    if detected_dims:
                        logger.info(
                            f"Auto-detected and saved embedding dimensions: {detected_dims}"
                        )
                except (OSError, RuntimeError, ValueError) as e:
                    logger.warning(f"Could not auto-detect dimensions: {e}")

            logger.info(
                f"Created embedding provider: {primary_provider.name} "
                f"(dims={ci_config.embedding.get_dimensions()}, "
                f"max_chunk={ci_config.embedding.get_max_chunk_chars()})"
            )
        else:
            # Provider created but not available (e.g., Ollama not running)
            logger.warning(
                f"Embedding provider {primary_provider.name} not available. "
                "Make sure Ollama is running or configure an OpenAI-compatible provider."
            )
            logger.info("Configure your provider in the Settings tab to start indexing.")
            # Still create the chain - it will be checked on first use
            state.embedding_chain = EmbeddingProviderChain(providers=[primary_provider])
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to create embedding provider: {e}")
        logger.info("Configure your provider in the Settings tab to start indexing.")
        state.embedding_chain = None

    # Initialize vector store (requires embedding provider)
    ci_data_dir = project_root / ".oak" / "ci" / "chroma"

    if state.embedding_chain is None:
        logger.warning("Skipping vector store initialization - no embedding provider")
        state.vector_store = None
        state.indexer = None
    else:
        try:
            from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

            state.vector_store = VectorStore(
                persist_directory=ci_data_dir,
                embedding_provider=state.embedding_chain,
            )
            logger.info(f"Vector store initialized at {ci_data_dir}")

            # Initialize indexer with configured chunk size
            from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
                ChunkerConfig,
            )
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
                    "Skipping auto-index - provider not available. "
                    "Save settings to start indexing."
                )

            # Initialize activity store and processor
            try:
                from open_agent_kit.features.codebase_intelligence.activity import (
                    ActivityProcessor,
                    ActivityStore,
                )
                from open_agent_kit.features.codebase_intelligence.summarization import (
                    create_summarizer_from_config,
                )

                activity_db_path = project_root / ".oak" / "ci" / "activities.db"
                state.activity_store = ActivityStore(activity_db_path)
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
                    )

                    # Check for SQLite/ChromaDB mismatch on startup
                    # SQLite is source of truth - if it has data but ChromaDB doesn't,
                    # we need to rebuild ChromaDB from SQLite
                    await _check_and_rebuild_chromadb(state)

                    # Schedule background processing every 60 seconds
                    state.activity_processor.schedule_background_processing(interval_seconds=60)
                    logger.info("Activity processor initialized with background scheduling")

            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(f"Failed to initialize activity store: {e}")
                state.activity_store = None
                state.activity_processor = None

        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize: {e}")
            state.vector_store = None
            state.indexer = None

    yield

    # Graceful shutdown sequence
    logger.info("Initiating graceful shutdown...")

    # 1. Cancel background tasks and wait for them
    for task in state.background_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except (RuntimeError, OSError) as e:
                logger.warning(f"Error cancelling task {task.get_name()}: {e}")
    state.background_tasks.clear()

    # 2. Activity processor uses daemon timers that auto-terminate on shutdown
    # No explicit stop needed - daemon threads exit with the process
    if state.activity_processor:
        logger.info("Activity processor will terminate with daemon shutdown")

    # 3. Stop file watcher and wait for thread cleanup
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

    # Add CORS middleware - restrict to localhost only for security
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://localhost",
            "http://127.0.0.1",
        ],
        allow_credentials=False,  # Disabled unless specifically needed
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Include routers
    from open_agent_kit.features.codebase_intelligence.daemon.routes import (
        activity,
        devtools,
        health,
        hooks,
        index,
        mcp,
        search,
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
    app.include_router(hooks.router)
    app.include_router(mcp.router)
    app.include_router(devtools.router)

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
