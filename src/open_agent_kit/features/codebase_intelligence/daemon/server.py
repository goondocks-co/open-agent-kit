"""FastAPI server for Codebase Intelligence daemon.

This module creates the FastAPI application. Lifecycle management
(startup, shutdown, logging, version checks, etc.) lives in the
``daemon/lifecycle/`` package. Background indexing and file-watching
live in ``daemon/background.py``.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CORS_ALLOWED_HEADERS,
    CI_CORS_ALLOWED_METHODS,
    CI_CORS_HOST_LOCALHOST,
    CI_CORS_HOST_LOOPBACK,
    CI_CORS_ORIGIN_TEMPLATE,
    CI_CORS_SCHEME_HTTP,
    CI_DATA_DIR,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)


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
    from open_agent_kit.features.codebase_intelligence.daemon.lifecycle.startup import (
        lifespan,
    )

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

    # Read auth token from environment (set by DaemonManager.start())
    from open_agent_kit.features.codebase_intelligence.constants import CI_AUTH_ENV_VAR

    state.auth_token = os.environ.get(CI_AUTH_ENV_VAR)

    # --- Middleware stack ---
    # Add order determines nesting: first added = innermost.
    # Request flow: CORS -> RequestSizeLimit -> TokenAuth -> ActivityTracking -> app
    # (CORS outermost handles preflight before any auth checks)
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.middleware import (
        ActivityTrackingMiddleware,
        DynamicCORSMiddleware,
        RequestSizeLimitMiddleware,
        TokenAuthMiddleware,
    )

    # 1. ActivityTracking (innermost -- added first, runs after auth)
    app.add_middleware(ActivityTrackingMiddleware)

    # 2. TokenAuth
    app.add_middleware(TokenAuthMiddleware)

    # 3. RequestSizeLimit
    app.add_middleware(RequestSizeLimitMiddleware)

    # 4. CORS (outermost -- added last, runs first on requests)
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
        acp,
        acp_sessions,
        activity,
        activity_management,
        activity_plans,
        activity_processing,
        activity_relationships,
        activity_sessions,
        agent_runs,
        agent_settings,
        agents,
        backup,
        cloud_relay,
        config_exclusions,
        config_providers,
        config_test,
        devtools,
        devtools_processing,
        governance,
        health,
        hooks,
        index,
        mcp,
        notifications,
        otel,
        restart,
        schedules,
        search,
        search_network,
        ui,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.routes import (
        config as config_routes,
    )

    # Routes already include full paths (e.g., /api/health, /api/search)
    # so no prefix is needed
    app.include_router(health.router)
    app.include_router(config_routes.router)
    app.include_router(config_providers.router)
    app.include_router(config_test.router)
    app.include_router(config_exclusions.router)
    app.include_router(index.router)
    app.include_router(search.router)
    app.include_router(search_network.router)
    app.include_router(activity.router)
    app.include_router(activity_plans.router)
    app.include_router(activity_processing.router)
    app.include_router(activity_sessions.router)
    app.include_router(activity_relationships.router)
    app.include_router(activity_management.router)
    app.include_router(notifications.router)
    app.include_router(hooks.router)
    app.include_router(otel.router)
    app.include_router(mcp.router)
    # agent_runs and agent_settings share /api/agents prefix — register BEFORE
    # agents.router so their specific paths take priority over wildcards.
    app.include_router(agent_runs.router)
    app.include_router(agent_settings.router)
    app.include_router(agents.router)
    app.include_router(schedules.router)
    app.include_router(devtools.router)
    app.include_router(devtools_processing.router)
    app.include_router(backup.router)
    app.include_router(cloud_relay.router)
    app.include_router(restart.router)
    app.include_router(governance.router)
    app.include_router(acp.router)
    app.include_router(acp_sessions.router)

    # Release channel routes
    from open_agent_kit.features.codebase_intelligence.daemon.routes import (
        release_channel,
    )

    app.include_router(release_channel.router)

    # Team UI routes (always available -- both client and server mode)
    from open_agent_kit.features.codebase_intelligence.daemon.routes.team import (
        router as team_ui_router,
    )

    app.include_router(team_ui_router)

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
