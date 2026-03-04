"""Swarm daemon FastAPI server."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_agent_kit.features.swarm.constants import (
    SWARM_AGENTS_DEFINITIONS_DIR,
    SWARM_AUTH_ENV_VAR,
)
from open_agent_kit.features.swarm.daemon.middleware import TokenAuthMiddleware
from open_agent_kit.features.swarm.daemon.routes import (
    agents,
    deploy,
    health,
    logs,
    nodes,
    restart,
    search,
    status,
    tools,
    ui,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle."""
    logger.info("Swarm daemon starting")

    # Initialize SwarmWorkerClient from env vars set by SwarmDaemonManager
    state = get_swarm_state()
    swarm_url = os.environ.get("OAK_SWARM_URL", "")
    swarm_token = os.environ.get("OAK_SWARM_TOKEN", "")
    swarm_id = os.environ.get("OAK_SWARM_ID", "")

    state.swarm_url = swarm_url
    state.swarm_token = swarm_token
    state.swarm_id = swarm_id
    state.auth_token = os.environ.get(SWARM_AUTH_ENV_VAR)

    if swarm_url and swarm_token:
        from open_agent_kit.features.swarm.daemon.client import (
            SwarmWorkerClient,
        )

        state.http_client = SwarmWorkerClient(swarm_url, swarm_token)
        logger.info("Connected to swarm worker at %s", swarm_url)
    else:
        logger.warning(
            "OAK_SWARM_URL or OAK_SWARM_TOKEN not set; swarm daemon running without worker connection"
        )

    # Initialize agent runtime
    try:
        from open_agent_kit.features.agent_runtime.registry import AgentRegistry
        from open_agent_kit.features.agent_runtime.run_store import RunStore
        from open_agent_kit.features.agent_runtime.executor import AgentExecutor
        from open_agent_kit.features.team.config.agents import AgentConfig

        # Definitions live inside the swarm feature package
        definitions_dir = Path(__file__).parent.parent / SWARM_AGENTS_DEFINITIONS_DIR

        registry = AgentRegistry(
            definitions_dir=definitions_dir,
            project_root=None,
        )
        registry.load_all()

        run_store = RunStore(activity_store=None)

        agent_config = AgentConfig(enabled=True)
        executor = AgentExecutor(
            project_root=Path.cwd(),
            agent_config=agent_config,
        )

        state.agent_registry = registry
        state.agent_executor = executor
        state.run_store = run_store

        logger.info(
            "Agent runtime initialized with %d templates", len(registry.templates)
        )
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
    app.include_router(nodes.router)
    app.include_router(status.router)
    app.include_router(tools.router)
    app.include_router(agents.router)
    app.include_router(restart.router)
    app.include_router(logs.router)
    app.include_router(deploy.router)

    # Static files for UI
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # UI routes (catch-all, must be last)
    app.include_router(ui.router)

    return app
