"""CI development commands: dev, port."""

import os
from pathlib import Path

import typer

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
    ci_app,
    console,
    get_daemon_manager,
    logger,
)


@ci_app.command("port")
def ci_port() -> None:
    """Show the port assigned to this project.

    Each project gets a unique port derived from its path, allowing
    multiple CI daemons to run simultaneously on different projects.
    """
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    port = get_project_port(project_root)
    manager = get_daemon_manager(project_root)

    print_header("Codebase Intelligence Port")
    print_info(f"Project: {project_root}")
    print_info(f"Port: {port}")
    print_info(f"Dashboard: http://localhost:{port}/ui")

    if manager.is_running():
        print_success("Daemon is running.")
    else:
        print_warning("Daemon is not running. Start with: oak ci start")


@ci_app.command("dev")
def ci_dev(
    port: int = typer.Option(None, "--port", "-p", help="Port to run on (default: auto-assigned)"),
    reload_dir: str = typer.Option(
        None,
        "--reload-dir",
        "-r",
        help="Directory to watch for code changes (for OAK development)",
    ),
) -> None:
    """Run the daemon in development mode with hot reload.

    Runs the daemon in the foreground with auto-reload on code changes.
    Useful for development and debugging. Press Ctrl+C to stop.

    For OAK developers testing in external projects with an editable install,
    use --reload-dir to watch the OAK source directory:

    Examples:
        oak ci dev                              # Basic hot reload
        oak ci dev -p 37801                     # Custom port
        oak ci dev -r ~/Repos/open-agent-kit/src  # Watch OAK source (for OAK devs)
    """
    import subprocess
    import sys

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    run_port = port or manager.port

    # Check if port is in use
    if manager._is_port_in_use():
        print_warning(f"Port {run_port} is already in use.")
        if manager.is_running():
            print_info("Stopping existing daemon...")
            manager.stop()
        else:
            print_error(f"Another process is using port {run_port}.")
            raise typer.Exit(code=1)

    print_header("Codebase Intelligence Development Server")
    print_info(f"Project: {project_root}")
    print_info(f"Port: {run_port}")
    print_info(f"Dashboard: http://localhost:{run_port}/ui")

    # Determine reload directory
    if reload_dir:
        watch_dir = Path(reload_dir).expanduser().resolve()
        if not watch_dir.exists():
            print_error(f"Reload directory does not exist: {watch_dir}")
            raise typer.Exit(code=1)
        print_info(f"Watching: {watch_dir}")
    else:
        # Try to find OAK source from editable install
        try:
            import open_agent_kit

            oak_path = Path(open_agent_kit.__file__).parent
            # Check if this looks like an editable install (src layout)
            if "site-packages" not in str(oak_path):
                watch_dir = oak_path.parent  # src/ directory
                print_info(f"Watching: {watch_dir} (detected editable install)")
            else:
                watch_dir = oak_path
                print_info(f"Watching: {watch_dir}")
        except (ImportError, AttributeError, TypeError) as e:
            logger.warning(f"Could not detect OAK installation path: {e}")
            watch_dir = Path.cwd() / "src"
            print_info(f"Watching: {watch_dir}")

    console.print()
    print_info("Running with hot reload - code changes will auto-restart the server.")
    print_info("Press Ctrl+C to stop.\n")

    # Run uvicorn with reload
    env = os.environ.copy()
    env["OAK_CI_PROJECT_ROOT"] = str(project_root)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "open_agent_kit.features.codebase_intelligence.daemon.server:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(run_port),
        "--reload",
        "--reload-dir",
        str(watch_dir),
    ]

    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print_info("\nDevelopment server stopped.")
    except subprocess.CalledProcessError as e:
        print_error(f"Server exited with error: {e.returncode}")
        raise typer.Exit(code=1)
