"""Cloud MCP Relay commands: cloud-init, cloud-connect, cloud-disconnect, cloud-status, cloud-url."""

from http import HTTPStatus
from pathlib import Path

import httpx
import typer

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLOUD_RELAY_API_PATH_CONNECT,
    CI_CLOUD_RELAY_API_PATH_DISCONNECT,
    CI_CLOUD_RELAY_API_PATH_START,
    CI_CLOUD_RELAY_API_PATH_STATUS,
    CI_CLOUD_RELAY_API_URL_TEMPLATE,
    CI_CLOUD_RELAY_ERROR_UNKNOWN,
    CI_CLOUD_RELAY_MESSAGE_AGENT_TOKEN,
    CI_CLOUD_RELAY_MESSAGE_ALREADY_CONNECTED,
    CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR,
    CI_CLOUD_RELAY_MESSAGE_CONNECTED,
    CI_CLOUD_RELAY_MESSAGE_CONNECTED_AT,
    CI_CLOUD_RELAY_MESSAGE_CONNECTING_RELAY,
    CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING,
    CI_CLOUD_RELAY_MESSAGE_DEPLOY_DETAIL,
    CI_CLOUD_RELAY_MESSAGE_DISCONNECTED,
    CI_CLOUD_RELAY_MESSAGE_FAILED_CONNECT,
    CI_CLOUD_RELAY_MESSAGE_FAILED_DISCONNECT,
    CI_CLOUD_RELAY_MESSAGE_FAILED_START,
    CI_CLOUD_RELAY_MESSAGE_FAILED_STATUS,
    CI_CLOUD_RELAY_MESSAGE_LAST_ERROR,
    CI_CLOUD_RELAY_MESSAGE_LAST_HEARTBEAT,
    CI_CLOUD_RELAY_MESSAGE_MCP_ENDPOINT,
    CI_CLOUD_RELAY_MESSAGE_NOT_CONNECTED,
    CI_CLOUD_RELAY_MESSAGE_RECONNECT_ATTEMPTS,
    CI_CLOUD_RELAY_MESSAGE_SAVE_TOKEN,
    CI_CLOUD_RELAY_MESSAGE_STARTING,
    CI_CLOUD_RELAY_MESSAGE_SUGGESTION,
    CI_CLOUD_RELAY_MESSAGE_TIMEOUT,
    CI_CLOUD_RELAY_MESSAGE_TIMEOUT_CONNECT,
    CI_CLOUD_RELAY_MESSAGE_WORKER_URL,
    CI_CORS_HOST_LOCALHOST,
    CI_CORS_SCHEME_HTTP,
    CI_DAEMON_STATUS_KEY_PORT,
    CI_EXIT_CODE_FAILURE,
    CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED,
    CLOUD_RELAY_API_STATUS_NOT_CONNECTED,
    CLOUD_RELAY_REQUEST_KEY_FORCE,
    CLOUD_RELAY_REQUEST_KEY_WORKER_URL,
    CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT,
    CLOUD_RELAY_RESPONSE_KEY_DETAIL,
    CLOUD_RELAY_RESPONSE_KEY_ERROR,
    CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT,
    CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT,
    CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS,
    CLOUD_RELAY_RESPONSE_KEY_STATUS,
    CLOUD_RELAY_RESPONSE_KEY_SUGGESTION,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL,
    CLOUD_RELAY_START_STATUS_OK,
    HTTP_TIMEOUT_LONG,
    HTTP_TIMEOUT_QUICK,
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
        path: API path (e.g. "/api/cloud/connect").

    Returns:
        Full URL string.
    """
    return CI_CLOUD_RELAY_API_URL_TEMPLATE.format(
        scheme=CI_CORS_SCHEME_HTTP,
        host=CI_CORS_HOST_LOCALHOST,
        port=port,
        path=path,
    )


@ci_app.command("cloud-init")
def cloud_init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite scaffold if it already exists.",
    ),
) -> None:
    """Deploy a Cloudflare Worker for cloud relay (one command).

    Scaffolds the Worker project, installs dependencies, checks Cloudflare
    auth, deploys via wrangler, and connects the daemon — all in one step.
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status[CI_DAEMON_STATUS_KEY_PORT]

    print_info(CI_CLOUD_RELAY_MESSAGE_STARTING)

    body: dict = {}
    if force:
        body[CLOUD_RELAY_REQUEST_KEY_FORCE] = True

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_LONG) as client:
            response = client.post(
                _daemon_api_url(port, CI_CLOUD_RELAY_API_PATH_START),
                json=body,
            )
            if response.status_code != HTTPStatus.OK:
                print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_START.format(error=response.text))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            data = response.json()

            if data.get(CLOUD_RELAY_RESPONSE_KEY_STATUS) != CLOUD_RELAY_START_STATUS_OK:
                error = data.get(CLOUD_RELAY_RESPONSE_KEY_ERROR, CI_CLOUD_RELAY_ERROR_UNKNOWN)
                print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_START.format(error=error))
                suggestion = data.get(CLOUD_RELAY_RESPONSE_KEY_SUGGESTION)
                if suggestion:
                    print_info(CI_CLOUD_RELAY_MESSAGE_SUGGESTION.format(suggestion=suggestion))
                detail = data.get(CLOUD_RELAY_RESPONSE_KEY_DETAIL)
                if detail:
                    print_info(CI_CLOUD_RELAY_MESSAGE_DEPLOY_DETAIL.format(detail=detail))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            # Success
            worker_url = data.get(CLOUD_RELAY_RESPONSE_KEY_WORKER_URL)
            mcp_endpoint = data.get(CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT)
            agent_token = data.get(CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN)

            print_success(CI_CLOUD_RELAY_MESSAGE_CONNECTED.format(worker_url=worker_url))
            if worker_url:
                print_info(CI_CLOUD_RELAY_MESSAGE_WORKER_URL.format(worker_url=worker_url))
            if mcp_endpoint:
                print_info(CI_CLOUD_RELAY_MESSAGE_MCP_ENDPOINT.format(mcp_endpoint=mcp_endpoint))
            if agent_token:
                print_info(CI_CLOUD_RELAY_MESSAGE_AGENT_TOKEN.format(agent_token=agent_token))
                print_info(CI_CLOUD_RELAY_MESSAGE_SAVE_TOKEN)

    except httpx.ConnectError:
        print_error(CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_CLOUD_RELAY_MESSAGE_TIMEOUT_CONNECT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("cloud-connect")
def cloud_connect(
    url: str | None = typer.Argument(  # noqa: UP007
        None,
        help="Worker URL (optional if already in config).",
    ),
) -> None:
    """Connect the daemon to a deployed Cloudflare Worker relay."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status[CI_DAEMON_STATUS_KEY_PORT]

    body: dict[str, str] = {}
    if url:
        body[CLOUD_RELAY_REQUEST_KEY_WORKER_URL] = url

    print_info(CI_CLOUD_RELAY_MESSAGE_CONNECTING_RELAY)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(
                _daemon_api_url(port, CI_CLOUD_RELAY_API_PATH_CONNECT),
                json=body,
            )
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if (
                    data.get(CLOUD_RELAY_RESPONSE_KEY_STATUS)
                    == CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED
                ):
                    print_info(
                        CI_CLOUD_RELAY_MESSAGE_ALREADY_CONNECTED.format(
                            worker_url=data.get(CLOUD_RELAY_RESPONSE_KEY_WORKER_URL)
                        )
                    )
                elif data.get(CLOUD_RELAY_RESPONSE_KEY_CONNECTED):
                    print_success(
                        CI_CLOUD_RELAY_MESSAGE_CONNECTED.format(
                            worker_url=data.get(CLOUD_RELAY_RESPONSE_KEY_WORKER_URL)
                        )
                    )
                else:
                    error = data.get(CLOUD_RELAY_RESPONSE_KEY_ERROR, CI_CLOUD_RELAY_ERROR_UNKNOWN)
                    print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_CONNECT.format(detail=error))
                    raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
            else:
                detail = response.json().get("detail", response.text)
                print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_CONNECT.format(detail=detail))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_CLOUD_RELAY_MESSAGE_TIMEOUT_CONNECT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("cloud-disconnect")
def cloud_disconnect() -> None:
    """Disconnect from the cloud relay."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status[CI_DAEMON_STATUS_KEY_PORT]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(
                _daemon_api_url(port, CI_CLOUD_RELAY_API_PATH_DISCONNECT),
            )
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if (
                    data.get(CLOUD_RELAY_RESPONSE_KEY_STATUS)
                    == CLOUD_RELAY_API_STATUS_NOT_CONNECTED
                ):
                    print_info(CI_CLOUD_RELAY_MESSAGE_NOT_CONNECTED)
                else:
                    print_success(CI_CLOUD_RELAY_MESSAGE_DISCONNECTED)
            else:
                print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_DISCONNECT.format(detail=response.text))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_CLOUD_RELAY_MESSAGE_TIMEOUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("cloud-status")
def cloud_status() -> None:
    """Show cloud relay connection status."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status[CI_DAEMON_STATUS_KEY_PORT]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(
                _daemon_api_url(port, CI_CLOUD_RELAY_API_PATH_STATUS),
            )
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(CLOUD_RELAY_RESPONSE_KEY_CONNECTED):
                    print_success(
                        CI_CLOUD_RELAY_MESSAGE_CONNECTED.format(
                            worker_url=data.get(CLOUD_RELAY_RESPONSE_KEY_WORKER_URL)
                        )
                    )
                    if data.get(CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT):
                        print_info(
                            CI_CLOUD_RELAY_MESSAGE_CONNECTED_AT.format(
                                connected_at=data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT]
                            )
                        )
                    if data.get(CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT):
                        print_info(
                            CI_CLOUD_RELAY_MESSAGE_LAST_HEARTBEAT.format(
                                last_heartbeat=data[CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT]
                            )
                        )
                    reconnects = data.get(CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS, 0)
                    if reconnects > 0:
                        print_warning(
                            CI_CLOUD_RELAY_MESSAGE_RECONNECT_ATTEMPTS.format(
                                reconnect_attempts=reconnects
                            )
                        )
                else:
                    print_info(CI_CLOUD_RELAY_MESSAGE_NOT_CONNECTED)
                    if data.get(CLOUD_RELAY_RESPONSE_KEY_ERROR):
                        print_warning(
                            CI_CLOUD_RELAY_MESSAGE_LAST_ERROR.format(
                                error=data[CLOUD_RELAY_RESPONSE_KEY_ERROR]
                            )
                        )
            else:
                print_error(CI_CLOUD_RELAY_MESSAGE_FAILED_STATUS.format(detail=response.text))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.ConnectError:
        print_error(CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(CI_CLOUD_RELAY_MESSAGE_TIMEOUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@ci_app.command("cloud-url")
def cloud_url() -> None:
    """Print the cloud relay Worker URL (for scripting).

    Outputs only the URL with no formatting, suitable for use in scripts:
        oak ci cloud-url | pbcopy
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = manager.get_status()
    port = status[CI_DAEMON_STATUS_KEY_PORT]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(
                _daemon_api_url(port, CI_CLOUD_RELAY_API_PATH_STATUS),
            )
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get(CLOUD_RELAY_RESPONSE_KEY_CONNECTED) and data.get(
                    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL
                ):
                    # Raw output for scripting — no Rich formatting
                    print(data[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL])
                else:
                    raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
            else:
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except (httpx.ConnectError, httpx.TimeoutException):
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
