"""Swarm daemon FastAPI server."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_agent_kit.features.agent_runtime.executor import AgentExecutor
from open_agent_kit.features.agent_runtime.registry import AgentRegistry
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_SWARM_KEY_LOG_LEVEL,
    CI_CONFIG_SWARM_KEY_LOG_ROTATION,
    SWARM_AGENTS_DEFINITIONS_DIR,
    SWARM_AUTH_ENV_VAR,
    SWARM_DAEMON_DEFAULT_LOG_LEVEL,
    SWARM_ENV_VAR_CUSTOM_DOMAIN,
    SWARM_ENV_VAR_ID,
    SWARM_ENV_VAR_TOKEN,
    SWARM_ENV_VAR_URL,
    SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT,
    SWARM_LOG_ROTATION_DEFAULT_ENABLED,
    SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB,
)
from open_agent_kit.features.swarm.daemon.middleware import TokenAuthMiddleware
from open_agent_kit.features.swarm.daemon.routes import (
    agents,
    config,
    deploy,
    fetch,
    health,
    logs,
    nodes,
    release_channel,
    restart,
    search,
    status,
    tools,
    ui,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)
from open_agent_kit.features.team.config.agents import AgentConfig

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle."""
    # Initialize SwarmWorkerClient from env vars set by SwarmDaemonManager
    state = get_swarm_state()
    swarm_url = os.environ.get(SWARM_ENV_VAR_URL, "")
    swarm_token = os.environ.get(SWARM_ENV_VAR_TOKEN, "")
    swarm_id = os.environ.get(SWARM_ENV_VAR_ID, "")

    # Read persisted log level from config (set via PUT /api/config)
    from open_agent_kit.features.swarm.config import load_swarm_config
    from open_agent_kit.features.swarm.daemon.logging_setup import configure_swarm_logging

    swarm_config = load_swarm_config(swarm_id) or {} if swarm_id else {}
    log_level = swarm_config.get(CI_CONFIG_SWARM_KEY_LOG_LEVEL, SWARM_DAEMON_DEFAULT_LOG_LEVEL)

    # Read log rotation settings from config
    rotation = swarm_config.get(CI_CONFIG_SWARM_KEY_LOG_ROTATION, {})
    rotation_enabled = rotation.get("enabled", SWARM_LOG_ROTATION_DEFAULT_ENABLED)
    rotation_max_size_mb = rotation.get("max_size_mb", SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB)
    rotation_backup_count = rotation.get("backup_count", SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT)

    # Configure structured logging BEFORE any log calls so all output
    # goes through the file handler with [INFO]/[DEBUG]/etc. tags.
    configure_swarm_logging(
        swarm_id,
        log_level=log_level,
        max_size_mb=rotation_max_size_mb,
        backup_count=rotation_backup_count,
        rotation_enabled=rotation_enabled,
    )
    logger.info("Swarm daemon starting (log_level=%s)", log_level)
    logger.debug(
        "Environment: OAK_SWARM_ID=%s OAK_SWARM_URL=%s",
        swarm_id,
        swarm_url[:50] if swarm_url else "<unset>",
    )
    custom_domain = os.environ.get(SWARM_ENV_VAR_CUSTOM_DOMAIN, "")

    # When a custom domain is configured, derive the effective URL so the UI
    # and credentials display the custom domain instead of the workers.dev URL.
    effective_url = swarm_url
    if custom_domain and swarm_id and swarm_url:
        from open_agent_kit.features.swarm.scaffold import make_worker_name

        worker_name = make_worker_name(swarm_id)
        effective_url = f"https://{worker_name}.{custom_domain}"

    state.swarm_url = effective_url
    state.swarm_token = swarm_token
    state.swarm_id = swarm_id
    state.custom_domain = custom_domain
    state.auth_token = os.environ.get(SWARM_AUTH_ENV_VAR)

    if swarm_url and swarm_token:
        from open_agent_kit.features.swarm.daemon.client import (
            SwarmWorkerClient,
        )

        state.http_client = SwarmWorkerClient(effective_url, swarm_token)
        logger.info("Connected to swarm worker at %s", effective_url)
    else:
        logger.warning(
            "OAK_SWARM_URL or OAK_SWARM_TOKEN not set; swarm daemon running without worker connection"
        )

    # Initialize agent runtime
    try:
        # Definitions live inside the swarm feature package
        definitions_dir = Path(__file__).parent.parent / SWARM_AGENTS_DEFINITIONS_DIR

        registry = AgentRegistry(
            definitions_dir=definitions_dir,
            project_root=None,
        )
        registry.load_all()
        logger.debug("Agent definitions dir: %s", definitions_dir)
        logger.debug("Loaded templates: %s", [t.name for t in registry.templates.values()])

        agent_config = AgentConfig(enabled=True)
        executor = AgentExecutor(
            project_root=Path.cwd(),
            agent_config=agent_config,
        )

        state.agent_registry = registry
        state.agent_executor = executor

        # Inject swarm MCP server so agents can use swarm tools
        if state.http_client:
            try:
                from open_agent_kit.features.swarm.agents.tools import (
                    create_swarm_mcp_server,
                )

                swarm_mcp = create_swarm_mcp_server(state.http_client)
                if swarm_mcp:
                    executor.add_mcp_server("oak-swarm", swarm_mcp)
                    logger.info("Swarm MCP server injected into agent executor")
            except Exception as mcp_exc:
                logger.warning("Failed to inject swarm MCP server: %s", mcp_exc)

        logger.info("Agent runtime initialized with %d templates", len(registry.templates))
    except Exception as exc:
        logger.warning("Failed to initialize agent runtime: %s", exc)

    yield

    # Cleanup
    if state.http_client:
        await state.http_client.close()
    logger.info("Swarm daemon stopped")


def create_app() -> FastAPI:
    """Create the swarm daemon FastAPI application.

    Returns:
        Configured FastAPI application with swarm routes.
    """
    app = FastAPI(title="Oak Swarm Daemon", lifespan=lifespan)

    # Middleware: TokenAuth protects /api/* routes (health exempt)
    app.add_middleware(TokenAuthMiddleware)

    # API routes
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(fetch.router)
    app.include_router(nodes.router)
    app.include_router(status.router)
    app.include_router(agents.router)
    app.include_router(restart.router)
    app.include_router(config.router)
    app.include_router(logs.router)
    app.include_router(deploy.router)
    app.include_router(tools.router)
    app.include_router(release_channel.router)

    # Static files for UI
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # UI routes (catch-all, must be last)
    app.include_router(ui.router)

    return app
