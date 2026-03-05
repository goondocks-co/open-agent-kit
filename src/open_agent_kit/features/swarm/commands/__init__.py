"""Swarm commands: create, deploy, destroy, start, stop, status."""

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

swarm_app = typer.Typer(name="swarm", help="Swarm management.", no_args_is_help=True)


def _get_swarm_daemon_manager(name: str, port: int | None = None) -> "SwarmDaemonManager":
    """Get swarm daemon manager instance."""
    from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

    return SwarmDaemonManager(swarm_id=name, port=port)


@swarm_app.command("create")
def swarm_create(
    name: str = typer.Option(..., "--name", "-n", help="Name for the swarm"),
) -> None:
    """Create a new swarm configuration and token."""
    from open_agent_kit.features.swarm.config import save_swarm_config
    from open_agent_kit.features.swarm.constants import (
        CI_CONFIG_SWARM_KEY_SWARM_ID,
        CI_CONFIG_SWARM_KEY_TOKEN,
        CI_CONFIG_SWARM_KEY_WORKER_NAME,
        SWARM_MESSAGE_CREATED,
        SWARM_MESSAGE_CREATING,
        SWARM_MESSAGE_SAVE_TOKEN,
        SWARM_MESSAGE_START_HINT,
        SWARM_MESSAGE_SWARM_TOKEN,
    )
    from open_agent_kit.features.swarm.scaffold import generate_token, make_worker_name
    from open_agent_kit.utils import print_info, print_warning

    print_info(SWARM_MESSAGE_CREATING.format(name=name))

    swarm_token = generate_token()
    worker_name = make_worker_name(name)

    # save_swarm_config creates the directory via mkdir(parents=True)
    save_swarm_config(
        name,
        {
            CI_CONFIG_SWARM_KEY_SWARM_ID: name,
            CI_CONFIG_SWARM_KEY_TOKEN: swarm_token,
            CI_CONFIG_SWARM_KEY_WORKER_NAME: worker_name,
        },
    )

    print_info(SWARM_MESSAGE_CREATED)
    print_info(SWARM_MESSAGE_SWARM_TOKEN.format(swarm_token=swarm_token))
    print_warning(SWARM_MESSAGE_SAVE_TOKEN)
    print_info(SWARM_MESSAGE_START_HINT.format(name=name))


@swarm_app.command("deploy")
def swarm_deploy(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm to deploy"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing scaffold"),
) -> None:
    """Deploy the Swarm Worker to Cloudflare."""
    from open_agent_kit.features.swarm.config import (
        get_swarm_config_dir,
        load_swarm_config,
        save_swarm_config,
    )
    from open_agent_kit.features.swarm.constants import (
        CI_CONFIG_SWARM_KEY_AGENT_TOKEN,
        CI_CONFIG_SWARM_KEY_TOKEN,
        CI_CONFIG_SWARM_KEY_URL,
        CI_CONFIG_SWARM_KEY_WORKER_NAME,
        SWARM_MESSAGE_DEPLOY_FAILED,
        SWARM_MESSAGE_DEPLOY_STARTING,
        SWARM_MESSAGE_DEPLOY_SUCCESS,
        SWARM_MESSAGE_NO_SWARM_CONFIG,
        SWARM_MESSAGE_NPM_INSTALL_FAILED,
        SWARM_MESSAGE_SWARM_URL,
        SWARM_MESSAGE_WRANGLER_NOT_AVAILABLE,
        SWARM_SCAFFOLD_WORKER_SUBDIR,
    )
    from open_agent_kit.features.swarm.deploy import (
        check_wrangler_available,
        run_npm_install,
        run_wrangler_deploy,
    )
    from open_agent_kit.features.swarm.scaffold import generate_token, render_worker_template
    from open_agent_kit.utils import print_error, print_info

    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    print_info(SWARM_MESSAGE_DEPLOY_STARTING)

    if not check_wrangler_available():
        print_error(SWARM_MESSAGE_WRANGLER_NOT_AVAILABLE)
        raise typer.Exit(code=1)

    swarm_token = config[CI_CONFIG_SWARM_KEY_TOKEN]
    worker_name = config[CI_CONFIG_SWARM_KEY_WORKER_NAME]

    # Generate agent token for MCP endpoint
    agent_token = config.get(CI_CONFIG_SWARM_KEY_AGENT_TOKEN)
    if not agent_token:
        agent_token = generate_token()
        config[CI_CONFIG_SWARM_KEY_AGENT_TOKEN] = agent_token
        save_swarm_config(name, config)

    swarm_dir = get_swarm_config_dir(name)
    scaffold_dir = swarm_dir / SWARM_SCAFFOLD_WORKER_SUBDIR

    render_worker_template(
        output_dir=scaffold_dir,
        swarm_token=swarm_token,
        worker_name=worker_name,
        agent_token=agent_token,
        force=force,
    )

    # npm install
    success, output = run_npm_install(scaffold_dir)
    if not success:
        print_error(SWARM_MESSAGE_NPM_INSTALL_FAILED.format(output=output))
        raise typer.Exit(code=1)

    # Deploy
    success, swarm_url, output = run_wrangler_deploy(scaffold_dir)
    if not success:
        print_error(SWARM_MESSAGE_DEPLOY_FAILED.format(output=output))
        raise typer.Exit(code=1)

    # Update config with deployed URL
    config[CI_CONFIG_SWARM_KEY_URL] = swarm_url
    save_swarm_config(name, config)

    print_info(SWARM_MESSAGE_DEPLOY_SUCCESS)
    if swarm_url:
        print_info(SWARM_MESSAGE_SWARM_URL.format(swarm_url=swarm_url))


@swarm_app.command("destroy")
def swarm_destroy(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm to destroy"),
) -> None:
    """Destroy a swarm and clean up."""
    import shutil

    from open_agent_kit.features.swarm.config import (
        get_swarm_config_dir,
        load_swarm_config,
    )
    from open_agent_kit.features.swarm.constants import (
        SWARM_MESSAGE_DESTROYED,
        SWARM_MESSAGE_DESTROYING,
        SWARM_MESSAGE_NO_SWARM_CONFIG,
    )
    from open_agent_kit.utils import print_error, print_info

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
    port: int = typer.Option(None, "--port", "-p", help="Daemon port"),
) -> None:
    """Start the swarm daemon."""
    from open_agent_kit.features.swarm.config import load_swarm_config
    from open_agent_kit.features.swarm.constants import (
        SWARM_DAEMON_DEFAULT_PORT,
        SWARM_MESSAGE_ALREADY_RUNNING,
        SWARM_MESSAGE_DAEMON_START_FAILED,
        SWARM_MESSAGE_NO_SWARM_CONFIG,
        SWARM_MESSAGE_STARTED,
        SWARM_MESSAGE_STARTING,
    )
    from open_agent_kit.utils import print_error, print_info, print_warning

    if port is None:
        port = SWARM_DAEMON_DEFAULT_PORT

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
        print_info(f"  http://localhost:{port}")
    else:
        print_error(SWARM_MESSAGE_DAEMON_START_FAILED)
        raise typer.Exit(code=1)


@swarm_app.command("stop")
def swarm_stop(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
) -> None:
    """Stop the swarm daemon."""
    from open_agent_kit.features.swarm.config import load_swarm_config
    from open_agent_kit.features.swarm.constants import (
        SWARM_MESSAGE_NO_SWARM_CONFIG,
        SWARM_MESSAGE_NOT_RUNNING,
        SWARM_MESSAGE_STOPPED,
        SWARM_MESSAGE_STOPPING,
    )
    from open_agent_kit.utils import print_error, print_info

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


@swarm_app.command("restart")
def swarm_restart(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
) -> None:
    """Restart the swarm daemon."""
    from open_agent_kit.features.swarm.config import load_swarm_config
    from open_agent_kit.features.swarm.constants import (
        SWARM_MESSAGE_NO_SWARM_CONFIG,
        SWARM_MESSAGE_RESTART_FAILED,
        SWARM_MESSAGE_RESTARTED,
        SWARM_MESSAGE_RESTARTING,
    )
    from open_agent_kit.utils import print_error, print_info, print_success

    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    manager = _get_swarm_daemon_manager(name)

    print_info(SWARM_MESSAGE_RESTARTING)
    if manager.restart():
        print_success(SWARM_MESSAGE_RESTARTED.format(port=manager.port))
    else:
        print_error(SWARM_MESSAGE_RESTART_FAILED.format(log_file=manager.log_file))
        raise typer.Exit(code=1)


@swarm_app.command("status")
def swarm_status(
    name: str = typer.Option(..., "--name", "-n", help="Name of the swarm"),
) -> None:
    """Show swarm status."""
    from open_agent_kit.features.swarm.config import load_swarm_config
    from open_agent_kit.features.swarm.constants import (
        CI_CONFIG_SWARM_KEY_SWARM_ID,
        CI_CONFIG_SWARM_KEY_URL,
        CI_CONFIG_SWARM_KEY_WORKER_NAME,
        SWARM_MESSAGE_NO_SWARM_CONFIG,
    )
    from open_agent_kit.utils import print_error, print_info

    config = load_swarm_config(name)
    if not config:
        print_error(SWARM_MESSAGE_NO_SWARM_CONFIG)
        raise typer.Exit(code=1)

    manager = _get_swarm_daemon_manager(name)
    status = manager.get_status()

    print_info(f"Swarm: {config.get(CI_CONFIG_SWARM_KEY_SWARM_ID, name)}")
    if config.get(CI_CONFIG_SWARM_KEY_URL):
        print_info(f"  URL: {config[CI_CONFIG_SWARM_KEY_URL]}")
    print_info(f"  Worker: {config.get(CI_CONFIG_SWARM_KEY_WORKER_NAME, 'unknown')}")
    print_info(f"  Daemon: {'running' if status['running'] else 'stopped'}")
    if status["running"] and status.get("port"):
        print_info(f"  Port: {status['port']}")
    if status["running"] and status.get("pid"):
        print_info(f"  PID: {status['pid']}")


@swarm_app.command("mcp")
def swarm_mcp(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type.",
    ),
) -> None:
    """Run the swarm MCP server."""
    from open_agent_kit.features.swarm.commands.mcp import mcp_command

    mcp_command(transport=transport)
