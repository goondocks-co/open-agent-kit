"""Tunnel sharing routes for the CI daemon.

Provides API endpoints for starting, stopping, and checking the status
of tunnel providers (cloudflared, ngrok) that expose the daemon UI
via a public URL for team sharing.
"""

import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_TUNNEL_API_PATH_START,
    CI_TUNNEL_API_PATH_STATUS,
    CI_TUNNEL_API_PATH_STOP,
    CI_TUNNEL_ERROR_CONFIG_NOT_LOADED,
    CI_TUNNEL_ERROR_CREATE_PROVIDER,
    CI_TUNNEL_ERROR_DAEMON_NOT_INITIALIZED,
    CI_TUNNEL_ERROR_PROVIDER_UNAVAILABLE,
    CI_TUNNEL_ERROR_START_UNKNOWN,
    CI_TUNNEL_ERROR_STOP,
    CI_TUNNEL_INSTALL_HINT_CLOUDFLARED,
    CI_TUNNEL_INSTALL_HINT_DEFAULT,
    CI_TUNNEL_INSTALL_HINT_NGROK,
    CI_TUNNEL_LOG_ACTIVE,
    CI_TUNNEL_LOG_FAILED_START,
    CI_TUNNEL_LOG_START,
    CI_TUNNEL_LOG_STOPPED,
    CI_TUNNEL_ROUTE_TAG,
    TUNNEL_API_STATUS_ALREADY_ACTIVE,
    TUNNEL_API_STATUS_ERROR,
    TUNNEL_API_STATUS_NOT_ACTIVE,
    TUNNEL_API_STATUS_STARTED,
    TUNNEL_API_STATUS_STOPPED,
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_PROVIDER_NGROK,
    TUNNEL_RESPONSE_KEY_STATUS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.tunnel.factory import (
    create_tunnel_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_TUNNEL_ROUTE_TAG])


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
            detail=CI_TUNNEL_ERROR_DAEMON_NOT_INITIALIZED,
        )

    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    return get_project_port(state.project_root, ci_data_dir)


@router.post(CI_TUNNEL_API_PATH_START)
async def start_tunnel() -> dict:
    """Start a tunnel to expose the daemon via a public URL.

    Creates a tunnel provider from configuration and starts it.
    The tunnel URL is added to the dynamic CORS origins.

    Returns:
        Tunnel status including the public URL.
    """
    state = get_state()

    # Check if tunnel is already active
    if state.tunnel_provider is not None:
        status = state.tunnel_provider.get_status()
        if status.active:
            return {
                TUNNEL_RESPONSE_KEY_STATUS: TUNNEL_API_STATUS_ALREADY_ACTIVE,
                **status.to_dict(),
            }

    # Get tunnel config
    if not state.ci_config:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_TUNNEL_ERROR_CONFIG_NOT_LOADED,
        )

    tunnel_config = state.ci_config.tunnel
    port = _get_daemon_port()

    # Create and start the provider
    try:
        provider = create_tunnel_provider(
            provider=tunnel_config.provider,
            cloudflared_path=tunnel_config.cloudflared_path,
            ngrok_path=tunnel_config.ngrok_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=CI_TUNNEL_ERROR_CREATE_PROVIDER.format(error=e),
        ) from e

    if not provider.is_available:
        install_hint = {
            TUNNEL_PROVIDER_NGROK: CI_TUNNEL_INSTALL_HINT_NGROK,
            TUNNEL_PROVIDER_CLOUDFLARED: CI_TUNNEL_INSTALL_HINT_CLOUDFLARED,
        }.get(provider.name, CI_TUNNEL_INSTALL_HINT_DEFAULT)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=CI_TUNNEL_ERROR_PROVIDER_UNAVAILABLE.format(
                provider=provider.name,
                install_hint=install_hint,
            ),
        )

    logger.info(CI_TUNNEL_LOG_START.format(provider=provider.name, port=port))
    status = provider.start(port)

    if status.active and status.public_url:
        state.tunnel_provider = provider
        # Add tunnel URL to dynamic CORS origins
        state.add_cors_origin(status.public_url)
        logger.info(CI_TUNNEL_LOG_ACTIVE.format(public_url=status.public_url))
        return {TUNNEL_RESPONSE_KEY_STATUS: TUNNEL_API_STATUS_STARTED, **status.to_dict()}

    # Start failed
    error_detail = status.error or CI_TUNNEL_ERROR_START_UNKNOWN
    logger.error(CI_TUNNEL_LOG_FAILED_START.format(error=error_detail))
    return {
        TUNNEL_RESPONSE_KEY_STATUS: TUNNEL_API_STATUS_ERROR,
        **status.to_dict(),
    }


@router.post(CI_TUNNEL_API_PATH_STOP)
async def stop_tunnel() -> dict:
    """Stop the active tunnel.

    Removes the tunnel URL from dynamic CORS origins and stops the provider.

    Returns:
        Status confirmation.
    """
    state = get_state()

    if state.tunnel_provider is None:
        return {TUNNEL_RESPONSE_KEY_STATUS: TUNNEL_API_STATUS_NOT_ACTIVE}

    # Get the URL before stopping (for CORS cleanup)
    status = state.tunnel_provider.get_status()
    if status.public_url:
        state.remove_cors_origin(status.public_url)

    # Stop the tunnel
    try:
        state.tunnel_provider.stop()
    except Exception as e:
        logger.warning(CI_TUNNEL_ERROR_STOP.format(error=e))
    finally:
        state.tunnel_provider = None

    logger.info(CI_TUNNEL_LOG_STOPPED)
    return {TUNNEL_RESPONSE_KEY_STATUS: TUNNEL_API_STATUS_STOPPED}


@router.get(CI_TUNNEL_API_PATH_STATUS)
async def get_tunnel_status() -> dict:
    """Get current tunnel status.

    Returns:
        Tunnel status including active state, URL, and provider info.
    """
    state = get_state()

    if state.tunnel_provider is None:
        return {
            "active": False,
            "public_url": None,
            "provider": None,
            "started_at": None,
            "error": None,
        }

    status = state.tunnel_provider.get_status()

    # If the tunnel died unexpectedly, clean up
    if not status.active and state.tunnel_provider is not None:
        if status.public_url:
            state.remove_cors_origin(status.public_url)
        state.tunnel_provider = None

    return status.to_dict()
