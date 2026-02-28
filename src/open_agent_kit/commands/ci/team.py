"""CI team commands: join, leave, status, members, serve, and key management."""

import os
from http import HTTPStatus
from pathlib import Path

import httpx
import typer
from rich.table import Table

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_EXIT_CODE_FAILURE,
    HTTP_TIMEOUT_QUICK,
)
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_JOIN,
    TEAM_API_PATH_KEYS,
    TEAM_API_PATH_LEAVE,
    TEAM_API_PATH_MEMBERS,
    TEAM_API_PATH_STATUS,
    TEAM_CLI_API_URL_TEMPLATE,
    TEAM_DEFAULT_BIND_HOST,
    TEAM_DEFAULT_BIND_PORT,
    TEAM_MESSAGE_AUTO_SYNC,
    TEAM_MESSAGE_DAEMON_NOT_RUNNING,
    TEAM_MESSAGE_INVALID_URL,
    TEAM_MESSAGE_JOIN_PENDING,
    TEAM_MESSAGE_JOIN_PENDING_POLL,
    TEAM_MESSAGE_JOIN_SUCCESS,
    TEAM_MESSAGE_KEY_CREATED,
    TEAM_MESSAGE_KEY_NOT_FOUND,
    TEAM_MESSAGE_KEY_REVOKED,
    TEAM_MESSAGE_KEY_SAVE_WARNING,
    TEAM_MESSAGE_LEAVE_SUCCESS,
    TEAM_MESSAGE_NO_KEYS,
    TEAM_MESSAGE_NO_MEMBERS,
    TEAM_MESSAGE_NOT_CONFIGURED,
    TEAM_MESSAGE_REQUEST_TIMED_OUT,
    TEAM_MESSAGE_SERVE_STARTING,
    TEAM_MESSAGE_SERVER_URL,
    TEAM_MESSAGE_SYNC_DISABLED,
    TEAM_MESSAGE_SYNC_ENABLED,
    TEAM_SERVER_MODE_ENV_VAR,
)
from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    console,
    get_daemon_manager,
)

team_app = typer.Typer(name="team", help="Team sync management.", no_args_is_help=True)


def _daemon_api_url(port: int, path: str) -> str:
    """Build daemon API URL.

    Args:
        port: Daemon port.
        path: API path (e.g. "/api/team/status").

    Returns:
        Full URL string.
    """
    return TEAM_CLI_API_URL_TEMPLATE.format(port=port, path=path)


def _get_daemon_port(project_root: Path) -> int:
    """Get the daemon port, raising if daemon is not running.

    Args:
        project_root: Project root directory.

    Returns:
        The daemon port number.

    Raises:
        typer.Exit: If daemon is not running.
    """
    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    status = manager.get_status()
    port: int = status["port"]
    return port


@team_app.command("join")
def team_join(
    server_url: str = typer.Option(..., help="Team server URL"),
) -> None:
    """Join a team server.

    Sends a join request through the daemon, which auto-generates an API
    key and submits only its SHA-256 hash to the server.  The server
    admin must approve the request before sync begins.
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    # Validate server_url
    if not server_url.startswith(("http://", "https://")):
        print_error(TEAM_MESSAGE_INVALID_URL)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    port = _get_daemon_port(project_root)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(
                _daemon_api_url(port, TEAM_API_PATH_JOIN),
                json={"server_url": server_url},
            )

            if response.status_code != HTTPStatus.OK:
                detail = response.json().get("detail", response.text) if response.text else ""
                print_error(f"Join failed: {detail}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            data = response.json()

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    status = data.get("status", "")
    if status == "pending_approval":
        print_warning(TEAM_MESSAGE_JOIN_PENDING.format(server_url=server_url))
        print_info(TEAM_MESSAGE_JOIN_PENDING_POLL)
    else:
        print_success(TEAM_MESSAGE_JOIN_SUCCESS.format(server_url=server_url))


@team_app.command("leave")
def team_leave() -> None:
    """Disconnect from team server and disable sync."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if manager.is_running():
        # Daemon running — go through API so it also stops sync workers
        status = manager.get_status()
        port: int = status["port"]
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
                response = client.post(_daemon_api_url(port, TEAM_API_PATH_LEAVE))
                if response.status_code == HTTPStatus.OK:
                    print_success(TEAM_MESSAGE_LEAVE_SUCCESS)
                    return
                print_error(f"Leave failed: {response.text}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
        except httpx.ConnectError:
            pass  # Fall through to direct config write
        except httpx.TimeoutException:
            pass

    # Daemon not running — write config directly
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    config = load_ci_config(project_root)
    if not config.team.server_url:
        print_info(TEAM_MESSAGE_NOT_CONFIGURED)
        return

    config.team.server_url = None
    config.team.api_key = None
    config.team.auto_sync = False
    save_ci_config(project_root, config)

    print_success(TEAM_MESSAGE_LEAVE_SUCCESS)


@team_app.command("status")
def team_status() -> None:
    """Show team sync status."""
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    config = load_ci_config(project_root)

    print_header("Team Sync Status")

    if not config.team.server_url:
        print_info(TEAM_MESSAGE_NOT_CONFIGURED)
        print_info("  Join a team: oak ci team join --server-url <url>")
        return

    print_info(TEAM_MESSAGE_SERVER_URL.format(server_url=config.team.server_url))
    sync_label = TEAM_MESSAGE_SYNC_ENABLED if config.team.auto_sync else TEAM_MESSAGE_SYNC_DISABLED
    print_info(TEAM_MESSAGE_AUTO_SYNC.format(auto_sync=sync_label))

    # Try to get live status from daemon
    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_warning(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        return

    status = manager.get_status()
    port = status["port"]

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(_daemon_api_url(port, TEAM_API_PATH_STATUS))
            if response.status_code == HTTPStatus.OK:
                data = response.json()
                if data.get("server_mode"):
                    print_info("  Mode: server")
                if data.get("status"):
                    print_info(f"  Server Status: {data['status']}")
    except (httpx.ConnectError, httpx.TimeoutException):
        print_warning("  Could not reach daemon for live status")


@team_app.command("members")
def team_members() -> None:
    """List team members."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    port = _get_daemon_port(project_root)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(_daemon_api_url(port, TEAM_API_PATH_MEMBERS))
            if response.status_code != HTTPStatus.OK:
                print_error(f"Failed to list members: HTTP {response.status_code}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            members = response.json()
            if not members:
                print_info(TEAM_MESSAGE_NO_MEMBERS)
                return

            table = Table(title="Team Members")
            table.add_column("Name", style="cyan")
            table.add_column("Machine ID", style="dim")
            table.add_column("Last Seen")
            table.add_column("Events", justify="right")

            for member in members:
                table.add_row(
                    member.get("display_name", ""),
                    member.get("machine_id", ""),
                    member.get("last_seen", ""),
                    str(member.get("event_count", 0)),
                )

            console.print(table)

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@team_app.command("serve")
def team_serve(
    port: int = typer.Option(TEAM_DEFAULT_BIND_PORT, help="Port to listen on"),
    host: str = typer.Option(TEAM_DEFAULT_BIND_HOST, help="Host to bind to"),
) -> None:
    """Start daemon in team server mode."""
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    # Update config for server mode
    config = load_ci_config(project_root)
    config.team.server_mode = True
    config.team.bind_host = host
    config.team.bind_port = port
    save_ci_config(project_root, config)

    # Set env var and start daemon
    os.environ[TEAM_SERVER_MODE_ENV_VAR] = "1"
    print_info(TEAM_MESSAGE_SERVE_STARTING.format(host=host, port=port))

    manager = get_daemon_manager(project_root)
    if manager.is_running():
        print_info("Restarting daemon in server mode...")
        manager.stop()
        import time

        time.sleep(0.5)

    if manager.start():
        print_success("Daemon started in team server mode")
        print_info("Teammates can join via: oak ci team join --server-url <url>")
    else:
        print_error("Failed to start daemon")
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


# --- Key management subcommands ---

key_app = typer.Typer(
    name="key", help="API key management (server mode only).", no_args_is_help=True
)
team_app.add_typer(key_app)


@key_app.command("create")
def key_create(
    name: str = typer.Option(..., help="Human-readable key name"),
) -> None:
    """Create a new API key (prints plaintext once)."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    port = _get_daemon_port(project_root)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.post(
                _daemon_api_url(port, TEAM_API_PATH_KEYS),
                json={"name": name},
            )
            if response.status_code != HTTPStatus.OK:
                print_error(f"Failed to create key: {response.text}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            data = response.json()
            print_success(TEAM_MESSAGE_KEY_CREATED.format(name=name))
            console.print()
            print_warning(TEAM_MESSAGE_KEY_SAVE_WARNING)
            console.print(f"  {data.get('key', '')}")

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@key_app.command("list")
def key_list() -> None:
    """List all API keys."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    port = _get_daemon_port(project_root)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.get(_daemon_api_url(port, TEAM_API_PATH_KEYS))
            if response.status_code != HTTPStatus.OK:
                print_error(f"Failed to list keys: {response.text}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

            keys = response.json()
            if not keys:
                print_info(TEAM_MESSAGE_NO_KEYS)
                return

            table = Table(title="API Keys")
            table.add_column("ID", style="cyan")
            table.add_column("Name")
            table.add_column("Machine ID", style="dim")
            table.add_column("Created")
            table.add_column("Last Used")
            table.add_column("Status")

            for key in keys:
                status = "[red]revoked[/red]" if key.get("revoked_at") else "[green]active[/green]"
                table.add_row(
                    key.get("id", ""),
                    key.get("name", ""),
                    key.get("machine_id", "") or "",
                    key.get("created_at", ""),
                    key.get("last_used_at", "") or "",
                    status,
                )

            console.print(table)

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)


@key_app.command("revoke")
def key_revoke(
    key_id: str = typer.Argument(help="Key ID to revoke"),
) -> None:
    """Revoke an API key."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    port = _get_daemon_port(project_root)

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            response = client.delete(
                _daemon_api_url(port, f"{TEAM_API_PATH_KEYS}/{key_id}"),
            )
            if response.status_code == HTTPStatus.OK:
                print_success(TEAM_MESSAGE_KEY_REVOKED.format(key_id=key_id))
            elif response.status_code == HTTPStatus.NOT_FOUND:
                print_error(TEAM_MESSAGE_KEY_NOT_FOUND.format(key_id=key_id))
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
            else:
                print_error(f"Failed to revoke key: {response.text}")
                raise typer.Exit(code=CI_EXIT_CODE_FAILURE)

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
