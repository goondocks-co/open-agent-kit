"""Daemon lifespan context manager and subsystem init helpers.

Extracted from ``server.py`` -- this is the core startup/shutdown
orchestrator. Init order is load-bearing:
    embedding -> vector store -> activity -> agents
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_CHROMA_DIR,
    CI_CLOUD_RELAY_ERROR_CONNECT_FAILED,
    CI_CLOUD_RELAY_LOG_AUTO_CONNECT,
    CI_CLOUD_RELAY_LOG_AUTO_CONNECT_FAILED,
    CI_CLOUD_RELAY_LOG_CONNECTED,
    CI_DATA_DIR,
    CI_LOG_FILE,
    CI_TUNNEL_ERROR_START_UNKNOWN,
    CI_TUNNEL_LOG_ACTIVE,
    CI_TUNNEL_LOG_AUTO_START,
    CI_TUNNEL_LOG_AUTO_START_FAILED,
    CI_TUNNEL_LOG_AUTO_START_UNAVAILABLE,
    SHUTDOWN_TASK_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.config import CIConfig
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState
    from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


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


async def _init_cloud_relay(state: "DaemonState", project_root: Path) -> None:
    """Auto-connect cloud relay if configured.

    Non-critical: failures are logged but do not prevent startup.
    """
    ci_config = state.ci_config
    if not ci_config or not ci_config.cloud_relay.auto_connect:
        return

    relay_config = ci_config.cloud_relay
    if not relay_config.worker_url:
        logger.debug("Cloud relay auto-connect skipped: no worker_url configured")
        return
    if not relay_config.token:
        logger.debug("Cloud relay auto-connect skipped: no token configured")
        return

    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )

    logger.info(CI_CLOUD_RELAY_LOG_AUTO_CONNECT)
    try:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.client import (
            CloudRelayClient,
        )

        ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        port = get_project_port(project_root, ci_data_dir)

        client = CloudRelayClient(
            tool_timeout_seconds=relay_config.tool_timeout_seconds,
            reconnect_max_seconds=relay_config.reconnect_max_seconds,
        )
        relay_status = await client.connect(relay_config.worker_url, relay_config.token, port)
        state.cloud_relay_client = client

        if relay_status.connected:
            logger.info(CI_CLOUD_RELAY_LOG_CONNECTED.format(worker_url=relay_config.worker_url))
        else:
            error_detail = relay_status.error or CI_CLOUD_RELAY_ERROR_CONNECT_FAILED.format(
                error="unknown"
            )
            logger.warning(CI_CLOUD_RELAY_LOG_AUTO_CONNECT_FAILED.format(error=error_detail))
    except (OSError, ValueError, RuntimeError, ConnectionError) as e:
        logger.warning(CI_CLOUD_RELAY_LOG_AUTO_CONNECT_FAILED.format(error=e))


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
    from open_agent_kit.features.codebase_intelligence.daemon.background import (
        _background_index,
    )

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
    from open_agent_kit.features.codebase_intelligence.daemon.lifecycle.sync_check import (
        check_and_rebuild_chromadb,
    )

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

    activity_db_path = project_root / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
    state.machine_id = get_machine_identifier(project_root)
    state.activity_store = ActivityStore(activity_db_path, machine_id=state.machine_id)
    logger.info(f"Activity store initialized at {activity_db_path}")

    # Create processor with config accessor so summarizer/context_budget/
    # session_quality read live config (no stale snapshots after UI changes).
    config_accessor = lambda: state.ci_config  # noqa: E731

    if state.vector_store:
        state.activity_processor = ActivityProcessor(
            activity_store=state.activity_store,
            vector_store=state.vector_store,
            project_root=str(project_root),
            config_accessor=config_accessor,
        )

        # Check for SQLite/ChromaDB mismatch on startup
        await check_and_rebuild_chromadb(state)

        # Schedule background processing using config interval
        bg_interval = ci_config.agents.background_processing_interval_seconds
        state.activity_processor.schedule_background_processing(
            interval_seconds=bg_interval,
            state_accessor=lambda: state,
        )
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

    config_accessor = lambda: state.ci_config  # noqa: E731
    state.agent_executor = AgentExecutor(
        project_root=project_root,
        agent_config=ci_config.agents,
        retrieval_engine=state.retrieval_engine,
        activity_store=state.activity_store,
        vector_store=state.vector_store,
        config_accessor=config_accessor,
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
            config_accessor=config_accessor,
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

    # 3. Close any active interactive sessions
    if state.interactive_session_manager:
        state.interactive_session_manager = None

    # 4. Stop agent scheduler
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

    # 4b. Disconnect cloud relay if connected
    if state.cloud_relay_client:
        logger.info("Disconnecting cloud relay...")
        try:
            await state.cloud_relay_client.disconnect()
        except (RuntimeError, OSError) as e:
            logger.warning(f"Error disconnecting cloud relay: {e}")
        finally:
            state.cloud_relay_client = None

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

    Initialization order matters: embedding -> vector store -> activity -> agents.
    Each helper is self-contained and logs its own errors so failures in one
    subsystem do not block the rest of startup.
    """
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config
    from open_agent_kit.features.codebase_intelligence.daemon.lifecycle.logging_setup import (
        configure_logging,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.lifecycle.maintenance import (
        run_governance_prune,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.lifecycle.version_check import (
        check_upgrade_needed,
        check_version,
        periodic_version_check,
    )

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
    configure_logging(effective_log_level, log_file=log_file, log_rotation=ci_config.log_rotation)
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

    # --- Subsystem init (order matters: embedding -> vector store -> activity -> agents) ---
    _init_tunnel(state, project_root)
    await _init_cloud_relay(state, project_root)

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

        # Initialize interactive session manager for ACP
        try:
            from open_agent_kit.features.codebase_intelligence.agents.interactive import (
                InteractiveSessionManager,
            )

            if state.activity_store is None:
                logger.warning("Interactive session manager unavailable (no activity store)")
                return
            state.interactive_session_manager = InteractiveSessionManager(
                project_root=project_root,
                activity_store=state.activity_store,
                retrieval_engine=state.retrieval_engine,
                vector_store=state.vector_store,
                agent_registry=state.agent_registry,
                activity_processor=state.activity_processor,
            )
            logger.info("Interactive session manager initialized for ACP")
        except ImportError as e:
            logger.warning(f"Interactive session manager unavailable (SDK not installed): {e}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize interactive session manager: {e}")

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to initialize: {e}")
        state.vector_store = None
        state.indexer = None

    # Run one immediate version + upgrade check, then launch periodic loop
    check_version(state)
    check_upgrade_needed(state)
    version_check_task = asyncio.create_task(periodic_version_check(), name="version_check")
    state.background_tasks.append(version_check_task)

    # Run one immediate governance audit prune (ongoing pruning is power-aware via ActivityProcessor)
    run_governance_prune(state)

    yield

    await _shutdown(state)
