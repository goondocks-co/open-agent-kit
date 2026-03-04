"""Team members commands: status and members."""

from http import HTTPStatus
from pathlib import Path

import typer
from rich.table import Table

from open_agent_kit.features.team.constants import (
    CI_EXIT_CODE_FAILURE,
    HTTP_TIMEOUT_QUICK,
)
from open_agent_kit.features.team.constants.team import (
    TEAM_API_PATH_MEMBERS,
    TEAM_API_PATH_STATUS,
    TEAM_CLI_API_URL_TEMPLATE,
    TEAM_MESSAGE_DAEMON_NOT_RUNNING,
    TEAM_MESSAGE_NO_MEMBERS,
    TEAM_MESSAGE_NOT_CONFIGURED,
    TEAM_MESSAGE_REQUEST_TIMED_OUT,
)
from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    console,
    get_daemon_manager,
)

members_app = typer.Typer(name="members", help="Team member management.", no_args_is_help=True)


def _daemon_api_url(port: int, path: str) -> str:
    """Build daemon API URL."""
    return TEAM_CLI_API_URL_TEMPLATE.format(port=port, path=path)


def _get_daemon_port(project_root: Path) -> int:
    """Get the daemon port, raising if daemon is not running."""
    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    status = manager.get_status()
    port: int = status["port"]
    return port


@members_app.command("status")
def members_status() -> None:
    """Show team sync status."""
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    print_header("Team Sync Status")

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
                if not data.get("configured"):
                    print_info(TEAM_MESSAGE_NOT_CONFIGURED)
                    return
                connected = data.get("connected", False)
                print_info(f"  Connected: {'yes' if connected else 'no'}")
                relay = data.get("relay")
                if relay and relay.get("worker_url"):
                    print_info(f"  Relay: {relay['worker_url']}")
                online = data.get("online_nodes", [])
                print_info(f"  Online nodes: {len(online)}")
    except (httpx.ConnectError, httpx.TimeoutException):
        print_warning("  Could not reach daemon for live status")


@members_app.command("list")
def members_list() -> None:
    """List team members."""
    import httpx

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

            data = response.json()
            members = data.get("online_nodes", [])
            if not members:
                print_info(TEAM_MESSAGE_NO_MEMBERS)
                return

            table = Table(title="Team Members")
            table.add_column("Name", style="cyan")
            table.add_column("Machine ID", style="dim")
            table.add_column("Last Seen")

            for member in members:
                table.add_row(
                    member.get("display_name", member.get("name", "")),
                    member.get("machine_id", ""),
                    member.get("last_seen", ""),
                )

            console.print(table)

    except httpx.ConnectError:
        print_error(TEAM_MESSAGE_DAEMON_NOT_RUNNING)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
    except httpx.TimeoutException:
        print_error(TEAM_MESSAGE_REQUEST_TIMED_OUT)
        raise typer.Exit(code=CI_EXIT_CODE_FAILURE)
