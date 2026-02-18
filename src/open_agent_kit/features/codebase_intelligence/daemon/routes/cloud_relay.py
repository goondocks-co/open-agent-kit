"""Cloud MCP Relay routes for the CI daemon.

Provides API endpoints for connecting, disconnecting, and checking the
status of the WebSocket-based cloud relay to a Cloudflare Worker.

The ``/api/cloud/start`` endpoint orchestrates the full deployment pipeline
(scaffold, npm install, auth check, deploy, connect) in a single call.
"""

import asyncio
import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLOUD_RELAY_API_PATH_CONNECT,
    CI_CLOUD_RELAY_API_PATH_DISCONNECT,
    CI_CLOUD_RELAY_API_PATH_PREFLIGHT,
    CI_CLOUD_RELAY_API_PATH_SETTINGS,
    CI_CLOUD_RELAY_API_PATH_START,
    CI_CLOUD_RELAY_API_PATH_STATUS,
    CI_CLOUD_RELAY_API_PATH_STOP,
    CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED,
    CI_CLOUD_RELAY_ERROR_CONNECT_FAILED,
    CI_CLOUD_RELAY_ERROR_DAEMON_NOT_INITIALIZED,
    CI_CLOUD_RELAY_ERROR_DISCONNECT_FAILED,
    CI_CLOUD_RELAY_ERROR_NO_TOKEN,
    CI_CLOUD_RELAY_ERROR_NO_WORKER_URL,
    CI_CLOUD_RELAY_LOG_CONNECTING,
    CI_CLOUD_RELAY_LOG_DISCONNECTED,
    CI_CLOUD_RELAY_LOG_PHASE_AUTH_CHECK,
    CI_CLOUD_RELAY_LOG_PHASE_DEPLOY,
    CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL,
    CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL_SKIP,
    CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD,
    CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD_SKIP,
    CI_CLOUD_RELAY_ROUTE_TAG,
    CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED,
    CLOUD_RELAY_API_STATUS_CONNECTED,
    CLOUD_RELAY_API_STATUS_DISCONNECTED,
    CLOUD_RELAY_API_STATUS_ERROR,
    CLOUD_RELAY_API_STATUS_NOT_CONNECTED,
    CLOUD_RELAY_DEPLOY_NPM_NOT_FOUND,
    CLOUD_RELAY_ERROR_CONNECTION_FAILED,
    CLOUD_RELAY_ERROR_DEPLOY_FAILED,
    CLOUD_RELAY_ERROR_NO_DEPLOY_URL,
    CLOUD_RELAY_ERROR_NOT_AUTHENTICATED,
    CLOUD_RELAY_ERROR_NPM_INSTALL_FAILED,
    CLOUD_RELAY_MCP_ENDPOINT_SUFFIX,
    CLOUD_RELAY_PHASE_AUTH_CHECK,
    CLOUD_RELAY_PHASE_COMPLETE,
    CLOUD_RELAY_PHASE_CONNECT,
    CLOUD_RELAY_PHASE_DEPLOY,
    CLOUD_RELAY_PHASE_NPM_INSTALL,
    CLOUD_RELAY_PHASE_SCAFFOLD,
    CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_ID,
    CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_NAME,
    CLOUD_RELAY_PREFLIGHT_KEY_DEPLOYED,
    CLOUD_RELAY_PREFLIGHT_KEY_INSTALLED,
    CLOUD_RELAY_PREFLIGHT_KEY_NPM_AVAILABLE,
    CLOUD_RELAY_PREFLIGHT_KEY_SCAFFOLDED,
    CLOUD_RELAY_PREFLIGHT_KEY_WORKER_URL,
    CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AUTHENTICATED,
    CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AVAILABLE,
    CLOUD_RELAY_REQUEST_KEY_AGENT_TOKEN,
    CLOUD_RELAY_REQUEST_KEY_FORCE,
    CLOUD_RELAY_REQUEST_KEY_TOKEN,
    CLOUD_RELAY_REQUEST_KEY_WORKER_URL,
    CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN,
    CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT,
    CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN,
    CLOUD_RELAY_RESPONSE_KEY_DETAIL,
    CLOUD_RELAY_RESPONSE_KEY_ERROR,
    CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT,
    CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT,
    CLOUD_RELAY_RESPONSE_KEY_PHASE,
    CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS,
    CLOUD_RELAY_RESPONSE_KEY_STATUS,
    CLOUD_RELAY_RESPONSE_KEY_SUGGESTION,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL,
    CLOUD_RELAY_SCAFFOLD_NODE_MODULES_DIR,
    CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR,
    CLOUD_RELAY_START_STATUS_ERROR,
    CLOUD_RELAY_START_STATUS_OK,
    CLOUD_RELAY_SUGGESTION_DEPLOY_FAILED,
    CLOUD_RELAY_SUGGESTION_INSTALL_NPM,
    CLOUD_RELAY_SUGGESTION_NPM_INSTALL_FAILED,
    CLOUD_RELAY_SUGGESTION_WRANGLER_LOGIN,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_CLOUD_RELAY_ROUTE_TAG])


def _get_daemon_port() -> int:
    """Get the port the daemon is listening on.

    Returns:
        The daemon port number.

    Raises:
        HTTPException: If port cannot be determined.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_CLOUD_RELAY_ERROR_DAEMON_NOT_INITIALIZED,
        )

    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    return get_project_port(state.project_root, ci_data_dir)


def _make_error_response(
    phase: str,
    error: str,
    suggestion: str | None = None,
    detail: str | None = None,
) -> dict:
    """Build a structured error response for the start endpoint.

    Always returns HTTP 200 with ``status: "error"`` so the CLI can
    display a user-friendly message without parsing HTTP status codes.
    """
    resp: dict = {
        CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_START_STATUS_ERROR,
        CLOUD_RELAY_RESPONSE_KEY_CONNECTED: False,
        CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: None,
        CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT: None,
        CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN: None,
        CLOUD_RELAY_RESPONSE_KEY_PHASE: phase,
        CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME: None,
        CLOUD_RELAY_RESPONSE_KEY_ERROR: error,
    }
    if suggestion:
        resp[CLOUD_RELAY_RESPONSE_KEY_SUGGESTION] = suggestion
    if detail:
        resp[CLOUD_RELAY_RESPONSE_KEY_DETAIL] = detail
    return resp


def _mcp_endpoint(
    worker_url: str,
    custom_domain: str | None = None,
    worker_name: str | None = None,
) -> str:
    """Derive the public MCP endpoint URL.

    Prefers the custom domain when both ``custom_domain`` and
    ``worker_name`` are available (e.g. ``oak-relay-foo.example.com``).
    Falls back to the workers.dev *worker_url* otherwise.
    """
    if custom_domain and worker_name:
        return f"https://{worker_name}.{custom_domain}" + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
    return worker_url + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX


# =========================================================================
# POST /api/cloud/start  — all-in-one orchestration
# =========================================================================


@router.post(CI_CLOUD_RELAY_API_PATH_START)
async def start_cloud_relay(body: dict | None = None) -> dict:
    """Orchestrate full cloud relay deployment.

    Phases (skips completed phases automatically):
    1. scaffold — generate Worker project if not already scaffolded
    2. npm_install — install dependencies if node_modules missing
    3. auth_check — verify ``npx wrangler whoami`` succeeds
    4. deploy — run ``npx wrangler deploy``, extract Worker URL
    5. connect — connect the daemon's WebSocket relay client

    Returns:
        Structured JSON with status, worker_url, mcp_endpoint, agent_token,
        phase, cf_account_name, and optional error/suggestion/detail.
    """
    state = get_state()
    body = body or {}

    if not state.project_root:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_SCAFFOLD,
            error=CI_CLOUD_RELAY_ERROR_DAEMON_NOT_INITIALIZED,
        )

    if not state.ci_config:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_SCAFFOLD,
            error=CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED,
        )

    from open_agent_kit.features.codebase_intelligence.cloud_relay.deploy import (
        check_wrangler_auth,
        run_npm_install,
        run_wrangler_deploy,
    )
    from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
        generate_token,
        is_scaffolded,
        make_worker_name,
        render_worker_template,
        render_wrangler_config,
    )
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    project_root = state.project_root
    scaffold_dir = project_root / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR
    relay_config = state.ci_config.cloud_relay

    # ------------------------------------------------------------------
    # Phase 1: Scaffold
    # ------------------------------------------------------------------
    if not is_scaffolded(project_root):
        logger.info(CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD)
        relay_token = relay_config.token or generate_token()
        agent_token = body.get(CLOUD_RELAY_REQUEST_KEY_AGENT_TOKEN) or generate_token()
        worker_name = relay_config.worker_name or make_worker_name(project_root.name)

        # Auto-force if dir exists but is incomplete (e.g. wrangler.toml deleted)
        force = scaffold_dir.exists() or body.get(CLOUD_RELAY_REQUEST_KEY_FORCE, False)

        try:
            render_worker_template(
                scaffold_dir,
                relay_token=relay_token,
                agent_token=agent_token,
                worker_name=worker_name,
                custom_domain=relay_config.custom_domain,
                force=force,
            )
        except (FileExistsError, FileNotFoundError) as exc:
            return _make_error_response(
                phase=CLOUD_RELAY_PHASE_SCAFFOLD,
                error=str(exc),
            )

        # Persist tokens and worker name to config; clear stale worker_url
        # so deploy phase runs with the (possibly new) worker name.
        ci_config = load_ci_config(project_root)
        ci_config.cloud_relay.token = relay_token
        ci_config.cloud_relay.agent_token = agent_token
        ci_config.cloud_relay.worker_name = worker_name
        ci_config.cloud_relay.worker_url = None
        save_ci_config(project_root, ci_config)
        # Invalidate cached config so subsequent reads pick up the new tokens
        state.ci_config = None
    else:
        logger.info(CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD_SKIP)

    # Re-read config (may have been updated by scaffold phase)
    ci_config = load_ci_config(project_root)
    relay_config = ci_config.cloud_relay

    # Always sync wrangler.toml with current config (handles custom_domain
    # changes without requiring a full re-scaffold).
    render_wrangler_config(
        scaffold_dir=scaffold_dir,
        relay_token=relay_config.token or "",
        agent_token=relay_config.agent_token or "",
        worker_name=relay_config.worker_name or make_worker_name(project_root.name),
        custom_domain=relay_config.custom_domain,
    )

    # ------------------------------------------------------------------
    # Phase 2: npm install (skip if node_modules exists)
    # ------------------------------------------------------------------
    node_modules = scaffold_dir / CLOUD_RELAY_SCAFFOLD_NODE_MODULES_DIR
    if not node_modules.is_dir():
        logger.info(CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL)
        loop = asyncio.get_running_loop()
        success, npm_output = await loop.run_in_executor(None, run_npm_install, scaffold_dir)
        if not success:
            return _make_error_response(
                phase=CLOUD_RELAY_PHASE_NPM_INSTALL,
                error=CLOUD_RELAY_ERROR_NPM_INSTALL_FAILED,
                suggestion=(
                    CLOUD_RELAY_SUGGESTION_NPM_INSTALL_FAILED
                    if CLOUD_RELAY_DEPLOY_NPM_NOT_FOUND not in npm_output
                    else CLOUD_RELAY_SUGGESTION_INSTALL_NPM
                ),
                detail=npm_output,
            )
    else:
        logger.info(CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL_SKIP)

    # ------------------------------------------------------------------
    # Phase 3: Auth check
    # ------------------------------------------------------------------
    logger.info(CI_CLOUD_RELAY_LOG_PHASE_AUTH_CHECK)
    loop = asyncio.get_running_loop()
    auth_info = await loop.run_in_executor(None, check_wrangler_auth, scaffold_dir)

    if auth_info is None or not auth_info.authenticated:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_AUTH_CHECK,
            error=CLOUD_RELAY_ERROR_NOT_AUTHENTICATED,
            suggestion=CLOUD_RELAY_SUGGESTION_WRANGLER_LOGIN,
        )

    # Store account name for status display
    state.cf_account_name = auth_info.account_name

    # ------------------------------------------------------------------
    # Phase 4: Deploy (always — idempotent, ensures config changes
    # like custom_domain routes are applied)
    # ------------------------------------------------------------------
    logger.info(CI_CLOUD_RELAY_LOG_PHASE_DEPLOY)
    success, deployed_url, deploy_output = await loop.run_in_executor(
        None, run_wrangler_deploy, scaffold_dir
    )
    if not success:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_DEPLOY,
            error=CLOUD_RELAY_ERROR_DEPLOY_FAILED,
            suggestion=CLOUD_RELAY_SUGGESTION_DEPLOY_FAILED,
            detail=deploy_output,
        )
    if not deployed_url:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_DEPLOY,
            error=CLOUD_RELAY_ERROR_NO_DEPLOY_URL,
            detail=deploy_output,
        )

    worker_url = deployed_url

    # Save worker_url to config
    ci_config_fresh = load_ci_config(project_root)
    ci_config_fresh.cloud_relay.worker_url = worker_url
    save_ci_config(project_root, ci_config_fresh)
    state.ci_config = None

    # ------------------------------------------------------------------
    # Phase 5: Connect
    # ------------------------------------------------------------------
    # Re-read config for latest token
    ci_config_final = load_ci_config(project_root)
    relay_config_final = ci_config_final.cloud_relay
    token = relay_config_final.token

    if not token:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_CONNECT,
            error=CI_CLOUD_RELAY_ERROR_NO_TOKEN,
        )

    # Resolve effective worker name for response and endpoint derivation
    effective_worker_name = relay_config_final.worker_name or make_worker_name(project_root.name)

    # If already connected to the same URL, skip
    if state.cloud_relay_client is not None:
        client_status = state.cloud_relay_client.get_status()
        if client_status.connected and client_status.worker_url == worker_url:
            mcp_endpoint = _mcp_endpoint(
                worker_url, relay_config_final.custom_domain, effective_worker_name
            )
            return {
                CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_START_STATUS_OK,
                CLOUD_RELAY_RESPONSE_KEY_CONNECTED: True,
                CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: worker_url,
                CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT: mcp_endpoint,
                CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN: relay_config_final.agent_token,
                CLOUD_RELAY_RESPONSE_KEY_PHASE: CLOUD_RELAY_PHASE_COMPLETE,
                CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME: state.cf_account_name,
                CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN: relay_config_final.custom_domain,
                CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME: effective_worker_name,
            }

    port = _get_daemon_port()
    logger.info(CI_CLOUD_RELAY_LOG_CONNECTING.format(worker_url=worker_url))

    from open_agent_kit.features.codebase_intelligence.cloud_relay.client import (
        CloudRelayClient,
    )

    client = CloudRelayClient(
        tool_timeout_seconds=relay_config_final.tool_timeout_seconds,
        reconnect_max_seconds=relay_config_final.reconnect_max_seconds,
    )

    try:
        relay_status = await client.connect(worker_url, token, port)
        state.cloud_relay_client = client
    except Exception as exc:
        error_msg = CI_CLOUD_RELAY_ERROR_CONNECT_FAILED.format(error=str(exc))
        logger.error(error_msg)
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_CONNECT,
            error=str(exc),
        )

    if not relay_status.connected:
        return _make_error_response(
            phase=CLOUD_RELAY_PHASE_CONNECT,
            error=relay_status.error or CLOUD_RELAY_ERROR_CONNECTION_FAILED,
        )

    mcp_endpoint = _mcp_endpoint(
        worker_url, relay_config_final.custom_domain, effective_worker_name
    )

    return {
        CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_START_STATUS_OK,
        CLOUD_RELAY_RESPONSE_KEY_CONNECTED: True,
        CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: worker_url,
        CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT: mcp_endpoint,
        CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN: relay_config_final.agent_token,
        CLOUD_RELAY_RESPONSE_KEY_PHASE: CLOUD_RELAY_PHASE_COMPLETE,
        CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME: state.cf_account_name,
        CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN: relay_config_final.custom_domain,
        CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME: effective_worker_name,
    }


# =========================================================================
# POST /api/cloud/stop  — clean disconnect
# =========================================================================


@router.post(CI_CLOUD_RELAY_API_PATH_STOP)
async def stop_cloud_relay() -> dict:
    """Stop the cloud relay (disconnect WebSocket).

    Returns:
        Status confirmation.
    """
    state = get_state()

    if state.cloud_relay_client is None:
        return {
            CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_NOT_CONNECTED,
        }

    try:
        await state.cloud_relay_client.disconnect()
    except Exception as exc:
        logger.warning(CI_CLOUD_RELAY_ERROR_DISCONNECT_FAILED.format(error=str(exc)))
    finally:
        state.cloud_relay_client = None
        state.cf_account_name = None

    logger.info(CI_CLOUD_RELAY_LOG_DISCONNECTED)
    return {
        CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_DISCONNECTED,
    }


# =========================================================================
# GET /api/cloud/preflight  — prerequisite check
# =========================================================================


@router.get(CI_CLOUD_RELAY_API_PATH_PREFLIGHT)
async def preflight_cloud_relay() -> dict:
    """Check prerequisites for cloud relay deployment.

    Returns:
        Dict with boolean flags for each prerequisite.
    """
    state = get_state()

    from open_agent_kit.features.codebase_intelligence.cloud_relay.deploy import (
        check_wrangler_auth,
        check_wrangler_available,
    )
    from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
        is_scaffolded,
    )

    project_root = state.project_root
    if not project_root:
        return {
            CLOUD_RELAY_PREFLIGHT_KEY_NPM_AVAILABLE: False,
            CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AVAILABLE: False,
            CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AUTHENTICATED: False,
            CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_NAME: None,
            CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_ID: None,
            CLOUD_RELAY_PREFLIGHT_KEY_SCAFFOLDED: False,
            CLOUD_RELAY_PREFLIGHT_KEY_INSTALLED: False,
            CLOUD_RELAY_PREFLIGHT_KEY_DEPLOYED: False,
            CLOUD_RELAY_PREFLIGHT_KEY_WORKER_URL: None,
        }

    scaffold_dir = project_root / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR
    scaffolded = is_scaffolded(project_root)
    installed = scaffolded and (scaffold_dir / CLOUD_RELAY_SCAFFOLD_NODE_MODULES_DIR).is_dir()

    # Check npm availability
    import shutil

    npm_available = shutil.which("npm") is not None

    # Check wrangler — works from any cwd, scaffold dir not required
    loop = asyncio.get_running_loop()
    wrangler_available = await loop.run_in_executor(None, check_wrangler_available, project_root)

    # Check wrangler auth — run whoami to get live account info
    wrangler_authenticated = False
    cf_account_name: str | None = None
    cf_account_id: str | None = None
    if wrangler_available:
        auth_info = await loop.run_in_executor(None, check_wrangler_auth, project_root)
        if auth_info:
            wrangler_authenticated = auth_info.authenticated
            cf_account_name = auth_info.account_name
            cf_account_id = auth_info.account_id

    # Check deployed status from config
    worker_url: str | None = None
    if state.ci_config and state.ci_config.cloud_relay.worker_url:
        worker_url = state.ci_config.cloud_relay.worker_url

    return {
        CLOUD_RELAY_PREFLIGHT_KEY_NPM_AVAILABLE: npm_available,
        CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AVAILABLE: wrangler_available,
        CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AUTHENTICATED: wrangler_authenticated,
        CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_NAME: cf_account_name,
        CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_ID: cf_account_id,
        CLOUD_RELAY_PREFLIGHT_KEY_SCAFFOLDED: scaffolded,
        CLOUD_RELAY_PREFLIGHT_KEY_INSTALLED: installed,
        CLOUD_RELAY_PREFLIGHT_KEY_DEPLOYED: worker_url is not None,
        CLOUD_RELAY_PREFLIGHT_KEY_WORKER_URL: worker_url,
    }


# =========================================================================
# PUT /api/cloud/settings  — update cloud relay settings
# =========================================================================


@router.put(CI_CLOUD_RELAY_API_PATH_SETTINGS)
async def update_cloud_relay_settings(body: dict) -> dict:
    """Update cloud relay settings (currently: custom_domain).

    Request body:
        - custom_domain: hostname string, or null to clear.

    Returns:
        Updated cloud relay status (same shape as GET /api/cloud/status).
    """
    state = get_state()

    if not state.ci_config or not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_CLOUD_RELAY_ERROR_DAEMON_NOT_INITIALIZED,
        )

    from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
        is_scaffolded,
        make_worker_name,
        render_wrangler_config,
    )
    from open_agent_kit.features.codebase_intelligence.config import (
        CloudRelayConfig,
        load_ci_config,
        save_ci_config,
    )

    # Validate: accept string or None
    raw_domain = body.get("custom_domain")
    if raw_domain is not None and not isinstance(raw_domain, str):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="custom_domain must be a string or null",
        )

    # Let CloudRelayConfig._validate() handle normalization and validation
    # by constructing a temporary instance to test the value.
    try:
        test_config = CloudRelayConfig(custom_domain=raw_domain)
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Load → mutate → save → invalidate (established config save pattern)
    ci_config = load_ci_config(state.project_root)
    ci_config.cloud_relay.custom_domain = test_config.custom_domain
    save_ci_config(state.project_root, ci_config)
    state.ci_config = None

    # Re-render wrangler.toml so next deploy picks up the domain change
    if is_scaffolded(state.project_root):
        render_wrangler_config(
            scaffold_dir=state.project_root / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR,
            relay_token=ci_config.cloud_relay.token or "",
            agent_token=ci_config.cloud_relay.agent_token or "",
            worker_name=ci_config.cloud_relay.worker_name
            or make_worker_name(state.project_root.name),
            custom_domain=test_config.custom_domain,
        )

    return await get_cloud_relay_status()


# =========================================================================
# Backward-compatible routes (connect/disconnect/status)
# =========================================================================


@router.post(CI_CLOUD_RELAY_API_PATH_CONNECT)
async def connect_cloud_relay(body: dict | None = None) -> dict:
    """Connect to the cloud relay worker.

    Request body (all optional, falls back to config):
        - worker_url: Cloudflare Worker URL
        - token: Shared authentication token

    Returns:
        Relay status including connection state and worker URL.
    """
    state = get_state()
    body = body or {}

    # Check if already connected
    if state.cloud_relay_client is not None:
        status = state.cloud_relay_client.get_status()
        if status.connected:
            return {
                CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED,
                **status.to_dict(),
            }

    # Get config
    if not state.ci_config:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED,
        )

    relay_config = state.ci_config.cloud_relay

    # Resolve worker_url and token (request body overrides config)
    worker_url = body.get(CLOUD_RELAY_REQUEST_KEY_WORKER_URL) or relay_config.worker_url
    token = body.get(CLOUD_RELAY_REQUEST_KEY_TOKEN) or relay_config.token

    if not worker_url:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=CI_CLOUD_RELAY_ERROR_NO_WORKER_URL,
        )

    if not token:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=CI_CLOUD_RELAY_ERROR_NO_TOKEN,
        )

    port = _get_daemon_port()

    logger.info(CI_CLOUD_RELAY_LOG_CONNECTING.format(worker_url=worker_url))

    # Create client and connect
    from open_agent_kit.features.codebase_intelligence.cloud_relay.client import (
        CloudRelayClient,
    )

    client = CloudRelayClient(
        tool_timeout_seconds=relay_config.tool_timeout_seconds,
        reconnect_max_seconds=relay_config.reconnect_max_seconds,
    )

    try:
        relay_status = await client.connect(worker_url, token, port)
        state.cloud_relay_client = client

        if relay_status.connected:
            return {
                CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_CONNECTED,
                **relay_status.to_dict(),
            }

        return {
            CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_ERROR,
            **relay_status.to_dict(),
        }

    except Exception as exc:
        error_msg = CI_CLOUD_RELAY_ERROR_CONNECT_FAILED.format(error=str(exc))
        logger.error(error_msg)
        return {
            CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_ERROR,
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED: False,
            CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: worker_url,
            CLOUD_RELAY_RESPONSE_KEY_ERROR: str(exc),
        }


@router.post(CI_CLOUD_RELAY_API_PATH_DISCONNECT)
async def disconnect_cloud_relay() -> dict:
    """Disconnect from the cloud relay.

    Returns:
        Status confirmation.
    """
    state = get_state()

    if state.cloud_relay_client is None:
        return {CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_NOT_CONNECTED}

    try:
        await state.cloud_relay_client.disconnect()
    except Exception as exc:
        logger.warning(CI_CLOUD_RELAY_ERROR_DISCONNECT_FAILED.format(error=str(exc)))
    finally:
        state.cloud_relay_client = None

    logger.info(CI_CLOUD_RELAY_LOG_DISCONNECTED)
    return {CLOUD_RELAY_RESPONSE_KEY_STATUS: CLOUD_RELAY_API_STATUS_DISCONNECTED}


@router.get(CI_CLOUD_RELAY_API_PATH_STATUS)
async def get_cloud_relay_status() -> dict:
    """Get current cloud relay status.

    Returns:
        Relay status including connection state, worker URL, heartbeat info,
        agent_token, mcp_endpoint, and cf_account_name.
    """
    state = get_state()

    # Reload config if invalidated (e.g. after settings save set it to None)
    if state.ci_config is None and state.project_root:
        from open_agent_kit.features.codebase_intelligence.config import (
            load_ci_config,
        )

        state.ci_config = load_ci_config(state.project_root)

    # Resolve worker_name and custom_domain from config
    worker_name: str | None = None
    custom_domain: str | None = None
    if state.ci_config:
        if state.ci_config.cloud_relay.worker_name:
            worker_name = state.ci_config.cloud_relay.worker_name
        custom_domain = state.ci_config.cloud_relay.custom_domain
    if worker_name is None and state.project_root:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        worker_name = make_worker_name(state.project_root.name)

    if state.cloud_relay_client is None:
        return {
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED: False,
            CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: None,
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT: None,
            CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT: None,
            CLOUD_RELAY_RESPONSE_KEY_ERROR: None,
            CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS: 0,
            CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN: None,
            CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT: None,
            CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME: None,
            CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN: custom_domain,
            CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME: worker_name,
        }

    status_dict = state.cloud_relay_client.get_status().to_dict()

    # Enrich with agent_token, mcp_endpoint, custom_domain, cf_account_name
    agent_token = None
    mcp_endpoint = None
    if state.ci_config:
        agent_token = state.ci_config.cloud_relay.agent_token
    worker_url = status_dict.get(CLOUD_RELAY_RESPONSE_KEY_WORKER_URL)
    if worker_url:
        mcp_endpoint = _mcp_endpoint(worker_url, custom_domain, worker_name)

    status_dict[CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN] = agent_token
    status_dict[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT] = mcp_endpoint
    status_dict[CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME] = state.cf_account_name
    status_dict[CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN] = custom_domain
    status_dict[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] = worker_name

    return status_dict
