"""Swarm commands: create, destroy, start, stop, status."""

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

from open_agent_kit.features.swarm.config import (
    get_swarm_config_dir,
    load_swarm_config,
    save_swarm_config,
)
from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_DEFAULT_PORT,
    SWARM_MESSAGE_ALREADY_RUNNING,
    SWARM_MESSAGE_CREATED,
    SWARM_MESSAGE_CREATING,
    SWARM_MESSAGE_DESTROYED,
    SWARM_MESSAGE_DESTROYING,
    SWARM_MESSAGE_NO_SWARM_CONFIG,
    SWARM_MESSAGE_NOT_RUNNING,
    SWARM_MESSAGE_SAVE_TOKEN,
    SWARM_MESSAGE_STARTED,
    SWARM_MESSAGE_STARTING,
    SWARM_MESSAGE_STOPPED,
    SWARM_MESSAGE_STOPPING,
    SWARM_MESSAGE_SWARM_TOKEN,
    SWARM_MESSAGE_SWARM_URL,
    SWARM_SCAFFOLD_WORKER_SUBDIR,
)
from open_agent_kit.utils import print_error, print_info, print_warning

swarm_app = typer.Typer(name="swarm", help="Swarm management.", no_args_is_help=True)


def _get_swarm_daemon_manager(name: str, port: int | None = None) -> "SwarmDaemonManager":
    """Get swarm daemon manager instance."""
    from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

    return SwarmDaemonManager(swarm_id=name, port=port)


@swarm_app.command("create")
def swarm_create(
    name: str = typer.Option(..., "--name", "-n", help="Name for the swarm"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing scaffold"),
) -> None:
    """Create a new swarm and deploy the Swarm Worker."""
    from open_agent_kit.features.swarm.deploy import (
        check_wrangler_available,
        run_npm_install,
        run_wrangler_deploy,
    )
    from open_agent_kit.features.swarm.scaffold import (
        generate_token,
        make_worker_name,
        render_worker_template,
    )

    print_info(SWARM_MESSAGE_CREATING.format(name=name))

    # Check wrangler is available before proceeding
    if not check_wrangler_available():
        print_error(
            "npx wrangler is not available. Install wrangler first: npm install -g wrangler"
        )
        raise typer.Exit(code=1)

    # Generate token and scaffold
    swarm_token = generate_token()
    worker_name = make_worker_name(name)

    swarm_dir = get_swarm_config_dir(name)
    scaffold_dir = swarm_dir / SWARM_SCAFFOLD_WORKER_SUBDIR

    render_worker_template(
        output_dir=scaffold_dir,
        swarm_token=swarm_token,
        worker_name=worker_name,
        force=force,
    )

    # npm install
    success, output = run_npm_install(scaffold_dir)
    if not success:
        print_error(f"npm install failed: {output}")
        raise typer.Exit(code=1)

    # Deploy
    success, swarm_url, output = run_wrangler_deploy(scaffold_dir)
    if not success:
        print_error(f"Deploy failed: {output}")
        raise typer.Exit(code=1)

    # Save config
    save_swarm_config(
        name,
        {
            "swarm_id": name,
            "swarm_url": swarm_url,
            "swarm_token": swarm_token,
            "worker_name": worker_name,
        },
    )

    print_info(SWARM_MESSAGE_CREATED)
    if swarm_url:
        print_info(SWARM_MESSAGE_SWARM_URL.format(swarm_url=swarm_url))
    print_info(SWARM_MESSAGE_SWARM_TOKEN.format(swarm_token=swarm_token))
    print_warning(SWARM_MESSAGE_SAVE_TOKEN)


@swarm_app.command("destroy")
def swarm_destroy(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm to destroy"),
) -> None:
    """Destroy a swarm and clean up."""
    import shutil

    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    print_info(SWARM_MESSAGE_DESTROYING.format(name=name))

    # Stop daemon if running
    manager = _get_swarm_daemon_manager(name)
    manager.stop()

    # Remove swarm directory
    swarm_dir = get_swarm_config_dir(name)
    if swarm_dir.is_dir():
        shutil.rmtree(swarm_dir)

    print_info(SWARM_MESSAGE_DESTROYED)


@swarm_app.command("start")
def swarm_start(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
    port: int = typer.Option(SWARM_DAEMON_DEFAULT_PORT, "--port", "-p", help="Daemon port"),
) -> None:
    """Start the swarm daemon."""
    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    manager = _get_swarm_daemon_manager(name, port=port)

    if manager.is_running():
        print_warning(SWARM_MESSAGE_ALREADY_RUNNING.format(port=port))
        return

    print_info(SWARM_MESSAGE_STARTING)

    if manager.start():
        print_info(SWARM_MESSAGE_STARTED.format(port=port))
    else:
        print_error("Swarm daemon failed to start. Check logs for details.")
        raise typer.Exit(code=1)


@swarm_app.command("stop")
def swarm_stop(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
) -> None:
    """Stop the swarm daemon."""
    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    manager = _get_swarm_daemon_manager(name)

    if not manager.is_running():
        print_info(SWARM_MESSAGE_NOT_RUNNING)
        return

    print_info(SWARM_MESSAGE_STOPPING)
    manager.stop()
    print_info(SWARM_MESSAGE_STOPPED)


@swarm_app.command("status")
def swarm_status(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
) -> None:
    """Show swarm status."""
    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    manager = _get_swarm_daemon_manager(name)
    status = manager.get_status()

    print_info(f"Swarm: {config.get('swarm_id', name)}")
    if config.get("swarm_url"):
        print_info(f"  URL: {config['swarm_url']}")
    print_info(f"  Worker: {config.get('worker_name', 'unknown')}")
    print_info(f"  Daemon: {'running' if status['running'] else 'stopped'}")
    if status["running"] and status.get("port"):
        print_info(f"  Port: {status['port']}")
    if status["running"] and status.get("pid"):
        print_info(f"  PID: {status['pid']}")
