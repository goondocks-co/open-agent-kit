"""Tunnel sharing commands: tunnel-start, tunnel-stop, tunnel-status, tunnel-url."""

from http import HTTPStatus
from pathlib import Path

import httpx
import typer

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CORS_HOST_LOCALHOST,
    CI_CORS_SCHEME_HTTP,
    CI_EXIT_CODE_FAILURE,
    CI_TUNNEL_API_PATH_START,
    CI_TUNNEL_API_PATH_STATUS,
    CI_TUNNEL_API_PATH_STOP,
    CI_TUNNEL_API_URL_TEMPLATE,
    CI_TUNNEL_ERROR_UNKNOWN,
    CI_TUNNEL_MESSAGE_ACTIVE,
    CI_TUNNEL_MESSAGE_ALREADY_ACTIVE,
    CI_TUNNEL_MESSAGE_CONNECT_ERROR,
    CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING,
    CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING_START,
    CI_TUNNEL_MESSAGE_FAILED_START,
    CI_TUNNEL_MESSAGE_FAILED_STATUS,
    CI_TUNNEL_MESSAGE_FAILED_STOP,
    CI_TUNNEL_MESSAGE_LAST_ERROR,
    CI_TUNNEL_MESSAGE_NO_TUNNEL,
    CI_TUNNEL_MESSAGE_PROVIDER,
    CI_TUNNEL_MESSAGE_STARTED,
    CI_TUNNEL_MESSAGE_STARTING,
    CI_TUNNEL_MESSAGE_STOPPED,
    CI_TUNNEL_MESSAGE_TIMEOUT,
    CI_TUNNEL_MESSAGE_TIMEOUT_START,
    CI_TUNNEL_PROVIDER_UNKNOWN,
    HTTP_TIMEOUT_QUICK,
    TUNNEL_API_STATUS_ALREADY_ACTIVE,
    TUNNEL_API_STATUS_NOT_ACTIVE,
    TUNNEL_RESPONSE_KEY_ACTIVE,
    TUNNEL_RESPONSE_KEY_ERROR,
    TUNNEL_RESPONSE_KEY_PROVIDER,
    TUNNEL_RESPONSE_KEY_PUBLIC_URL,
    TUNNEL_RESPONSE_KEY_STARTED_AT,
    TUNNEL_RESPONSE_KEY_STATUS,
)
from open_agent_kit.utils import (
    print_error,
    print_info,
    print_success,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    ci_app,
    get_daemon_manager,
)


def _daemon_api_url(port: int, path: str) -> str:
    """Build daemon API URL.

    Args:
        port: Daemon port.
        path: API path (e.g. "/api/tunnel/start").

    Returns:
        Full URL string.
    """
    return CI_TUNNEL_API_URL_TEMPLATE.format(
        scheme=CI_CORS_SCHEME_HTTP,
        host=CI_CORS_HOST_LOCALHOST,
        port=port,
        path=path,
    )


@ci_app.command("tunnel-start")
def tunnel_start() -> None:
    """Start a tunnel to share the daemon via a public URL."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING_START)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status["port"]

    print_info(CI_TUNNEL_MESSAGE_STARTING)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(_daemon_api_url(port, CI_TUNNEL_API_PATH_START))
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(TUNNEL_RESPONSE_KEY_PUBLIC_URL):
                    print_success(
                        CI_TUNNEL_MESSAGE_ACTIVE.format(
                            public_url=data[TUNNEL_RESPONSE_KEY_PUBLIC_URL]
                        )
                    )
                    print_info(
                        CI_TUNNEL_MESSAGE_PROVIDER.format(
                            provider=data.get(
                                TUNNEL_RESPONSE_KEY_PROVIDER, CI_TUNNEL_PROVIDER_UNKNOWN
                            )
                        )
                    )
                elif data.get(TUNNEL_RESPONSE_KEY_STATUS) == TUNNEL_API_STATUS_ALREADY_ACTIVE:
                    print_info(
                        CI_TUNNEL_MESSAGE_ALREADY_ACTIVE.format(
                            public_url=data.get(TUNNEL_RESPONSE_KEY_PUBLIC_URL)
                        )
                    )
                else:
                    error = data.get(TUNNEL_RESPONSE_KEY_ERROR, CI_TUNNEL_ERROR_UNKNOWN)
                    print_error(CI_TUNNEL_MESSAGE_FAILED_START.format(detail=error))
                    raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
            else:
                detail = response.json().get("detail", response.text)
                print_error(CI_TUNNEL_MESSAGE_FAILED_START.format(detail=detail))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_TUNNEL_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_TUNNEL_MESSAGE_TIMEOUT_START)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("tunnel-stop")
def tunnel_stop() -> None:
    """Stop the active tunnel."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status["port"]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(_daemon_api_url(port, CI_TUNNEL_API_PATH_STOP))
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(TUNNEL_RESPONSE_KEY_STATUS) == TUNNEL_API_STATUS_NOT_ACTIVE:
                    print_info(CI_TUNNEL_MESSAGE_NO_TUNNEL)
                else:
                    print_success(CI_TUNNEL_MESSAGE_STOPPED)
            else:
                print_error(CI_TUNNEL_MESSAGE_FAILED_STOP.format(detail=response.text))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_TUNNEL_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_TUNNEL_MESSAGE_TIMEOUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("tunnel-status")
def tunnel_status() -> None:
    """Show tunnel sharing status."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status["port"]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(_daemon_api_url(port, CI_TUNNEL_API_PATH_STATUS))
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(TUNNEL_RESPONSE_KEY_ACTIVE):
                    print_success(
                        CI_TUNNEL_MESSAGE_ACTIVE.format(
                            public_url=data[TUNNEL_RESPONSE_KEY_PUBLIC_URL]
                        )
                    )
                    print_info(
                        CI_TUNNEL_MESSAGE_PROVIDER.format(
                            provider=data.get(
                                TUNNEL_RESPONSE_KEY_PROVIDER, CI_TUNNEL_PROVIDER_UNKNOWN
                            )
                        )
                    )
                    if data.get(TUNNEL_RESPONSE_KEY_STARTED_AT):
                        print_info(
                            CI_TUNNEL_MESSAGE_STARTED.format(
                                started_at=data[TUNNEL_RESPONSE_KEY_STARTED_AT]
                            )
                        )
                else:
                    print_info(CI_TUNNEL_MESSAGE_NO_TUNNEL)
                    if data.get(TUNNEL_RESPONSE_KEY_ERROR):
                        print_warning(
                            CI_TUNNEL_MESSAGE_LAST_ERROR.format(
                                error=data[TUNNEL_RESPONSE_KEY_ERROR]
                            )
                        )
            else:
                print_error(CI_TUNNEL_MESSAGE_FAILED_STATUS.format(detail=response.text))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_TUNNEL_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_TUNNEL_MESSAGE_TIMEOUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("tunnel-url")
def tunnel_url() -> None:
    """Print the tunnel URL (for scripting).

    Outputs only the URL with no formatting, suitable for use in scripts:
        oak ci tunnel-url | pbcopy
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status["port"]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(_daemon_api_url(port, CI_TUNNEL_API_PATH_STATUS))
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(TUNNEL_RESPONSE_KEY_ACTIVE) and data.get(
                    TUNNEL_RESPONSE_KEY_PUBLIC_URL
                ):
                    # Raw output for scripting — no Rich formatting
                    print(data[TUNNEL_RESPONSE_KEY_PUBLIC_URL])
                else:
                    raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
            else:
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except (httpx.ConnectError, httpx.TimeoutException):
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
