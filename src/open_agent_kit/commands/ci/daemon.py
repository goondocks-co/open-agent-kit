"""CI daemon lifecycle commands: status, start, stop, restart, reset, logs."""

from pathlib import Path

import typer

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import SKIP_DIRECTORIES
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_DATA_DIR,
    DEFAULT_LOG_LINES,
    HTTP_TIMEOUT_QUICK,
    MAX_LANGUAGE_DETECTION_FILES,
)
from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    prompt,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    ci_app,
    console,
    get_daemon_manager,
    logger,
)


def _check_missing_parsers(project_root: Path) -> list[str]:
    """Check for missing language parsers based on project files.

    Returns:
        List of missing pip package names.
    """
    from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
        LANGUAGE_MAP,
        TREE_SITTER_PACKAGES,
        CodeChunker,
    )

    chunker = CodeChunker()
    installed = chunker._available_languages

    # Detect languages in project (quick scan)
    detected_languages: set[str] = set()
    file_count = 0
    max_files = MAX_LANGUAGE_DETECTION_FILES

    for filepath in project_root.rglob("*"):
        if file_count > max_files:
            break
        if not filepath.is_file():
            continue
        path_str = str(filepath)
        if any(skip in path_str for skip in SKIP_DIRECTORIES):
            continue

        suffix = filepath.suffix.lower()
        if suffix in LANGUAGE_MAP:
            lang = LANGUAGE_MAP[suffix]
            if lang in TREE_SITTER_PACKAGES:
                detected_languages.add(lang)
        file_count += 1

    # Find missing parsers
    missing = detected_languages - installed
    return [TREE_SITTER_PACKAGES[lang].replace("_", "-") for lang in missing]


@ci_app.command("status")
def ci_status() -> None:
    """Show Codebase Intelligence status.

    Displays daemon status, index statistics, and provider information.
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        DEFAULT_EXCLUDE_PATTERNS,
        load_ci_config,
    )

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    status = manager.get_status()

    print_header("Codebase Intelligence Status")

    # Daemon status
    if status["running"]:
        print_success(f"Daemon: Running on port {status['port']} (PID: {status['pid']})")
        if status.get("uptime_seconds"):
            uptime_mins = int(status["uptime_seconds"] // 60)
            print_info(f"  Uptime: {uptime_mins} minutes")
    else:
        print_warning("Daemon: Not running")
        print_info(f"  Log file: {status['log_file']}")

    # Try to get index stats from daemon
    if status["running"]:
        try:
            import httpx

            with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
                response = client.get(f"http://localhost:{status['port']}/api/index/status")
                if response.status_code == 200:
                    stats = response.json()
                    console.print()
                    print_info("Index Statistics:")
                    print_info(f"  Status: {stats.get('status', 'unknown')}")
                    print_info(f"  Total chunks: {stats.get('total_chunks', 0)}")
                    print_info(f"  Memory observations: {stats.get('memory_observations', 0)}")

                    if stats.get("is_indexing"):
                        print_info(
                            f"  Progress: {stats.get('progress', 0)}/{stats.get('total', 0)}"
                        )

                    if stats.get("last_indexed"):
                        print_info(f"  Last indexed: {stats['last_indexed']}")

                # Get config for log level
                config_response = client.get(f"http://localhost:{status['port']}/api/config")
                if config_response.status_code == 200:
                    config_data = config_response.json()
                    log_level = config_data.get("log_level", "INFO")
                    console.print()
                    print_info(f"Log Level: {log_level}")
                    if log_level != "DEBUG":
                        console.print(
                            "  [dim]Enable debug: oak ci config --debug && oak ci restart[/dim]"
                        )
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
            logger.debug(
                f"Daemon stats endpoint not available: {e}"
            )  # Daemon might not have stats endpoint yet

    # Show user-configured exclude patterns
    try:
        config = load_ci_config(project_root)
        user_excludes = [p for p in config.exclude_patterns if p not in DEFAULT_EXCLUDE_PATTERNS]
        if user_excludes:
            console.print()
            print_info(f"User Exclusions ({len(user_excludes)}):")
            for pattern in user_excludes:
                console.print(f"  • {pattern}")
            print_info("  Manage with: oak ci exclude --help")
    except (OSError, ValueError) as e:
        logger.debug(f"Config not accessible: {e}")  # Config might not be accessible


@ci_app.command("start")
def ci_start(
    auto_install: bool = typer.Option(
        False, "--auto-install", "-i", help="Automatically install missing language parsers"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output (for use in hooks)"),
    open_browser: bool = typer.Option(
        False, "--open", "-o", help="Open the dashboard in your browser after starting"
    ),
    settings: bool = typer.Option(
        False, "--settings", "-s", help="Open directly to the settings tab (implies --open)"
    ),
) -> None:
    """Start the Codebase Intelligence daemon."""
    import subprocess
    import sys

    project_root = Path.cwd()

    # In quiet mode, don't show errors for uninitialized projects
    if quiet:
        oak_dir = project_root / OAK_DIR
        ci_dir = oak_dir / CI_DATA_DIR
        if not oak_dir.exists() or not ci_dir.exists():
            return  # Silently exit if not configured

    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    # Reconcile hooks (ensures hook files exist locally after fresh clone)
    # Skip in quiet mode to avoid overhead when invoked from hooks themselves
    if not quiet:
        try:
            from open_agent_kit.features.codebase_intelligence.service import (
                CodebaseIntelligenceService,
            )
            from open_agent_kit.services.config_service import ConfigService

            config_service = ConfigService(project_root)
            config = config_service.load_config()
            if config.agents:
                ci_service = CodebaseIntelligenceService(project_root)
                ci_service.update_agent_hooks(config.agents)
        except Exception as e:
            logger.debug(f"Hook reconciliation skipped: {e}")

    manager = get_daemon_manager(project_root)

    if manager.is_running():
        if not quiet:
            print_info(f"Daemon is already running at http://localhost:{manager.port}")

        # Still open browser if requested
        if open_browser or settings:
            import webbrowser

            url = f"http://localhost:{manager.port}/ui"
            if settings:
                url += "?tab=settings"
            try:
                webbrowser.open(url)
            except OSError as e:
                logger.warning(f"Failed to open browser: {e}")
                if not quiet:
                    print_info(f"Could not open browser. Visit: {url}")
        return

    # Check for missing parsers (skip in quiet mode)
    if not quiet:
        missing_parsers = _check_missing_parsers(project_root)
        if missing_parsers:
            print_warning("Missing language parsers for better code understanding:")
            for pkg in sorted(missing_parsers):
                console.print(f"  {pkg}", style="dim")

            if auto_install:
                install = True
            else:
                install_prompt = prompt(f"Install {len(missing_parsers)} parser(s) now? [Y/n]")
                install = install_prompt.lower() not in ("n", "no")

            if install:
                print_info("Installing parsers...")
                try:
                    subprocess.run(["uv", "--version"], capture_output=True, check=True)
                    install_cmd = ["uv", "pip", "install"]
                except (subprocess.CalledProcessError, FileNotFoundError):
                    install_cmd = [sys.executable, "-m", "pip", "install"]

                try:
                    subprocess.run(install_cmd + missing_parsers, check=True)
                    print_success("Parsers installed!")
                except subprocess.CalledProcessError:
                    print_warning("Failed to install some parsers. Continuing anyway...")

    if not quiet:
        print_info("Starting Codebase Intelligence daemon...")

    if manager.start(wait=True):
        if not quiet:
            print_success(f"Daemon started at http://localhost:{manager.port}")
            print_info(f"  Dashboard: http://localhost:{manager.port}/ui")

        # Open browser if requested
        if open_browser or settings:
            import webbrowser

            url = f"http://localhost:{manager.port}/ui"
            if settings:
                url += "?tab=settings"
            try:
                webbrowser.open(url)
            except OSError as e:
                logger.warning(f"Failed to open browser: {e}")
                if not quiet:
                    print_info(f"Could not open browser. Visit: {url}")
    else:
        if not quiet:
            print_error(f"Failed to start daemon. Check logs: {manager.log_file}")
        raise typer.Exit(code=1)


@ci_app.command("stop")
def ci_stop() -> None:
    """Stop the Codebase Intelligence daemon."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)

    if not manager.is_running():
        print_info("Daemon is not running.")
        return

    print_info("Stopping Codebase Intelligence daemon...")
    if manager.stop():
        print_success("Daemon stopped.")
    else:
        print_error("Failed to stop daemon.")
        raise typer.Exit(code=1)


@ci_app.command("restart")
def ci_restart() -> None:
    """Restart the Codebase Intelligence daemon."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)

    print_info("Restarting Codebase Intelligence daemon...")
    if manager.restart():
        print_success(f"Daemon restarted at http://localhost:{manager.port}")
    else:
        print_error(f"Failed to restart daemon. Check logs: {manager.log_file}")
        raise typer.Exit(code=1)


@ci_app.command("reset")
def ci_reset(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    keep_daemon: bool = typer.Option(
        False, "--keep-daemon", "-k", help="Keep daemon running (only clear data)"
    ),
) -> None:
    """Reset Codebase Intelligence data.

    Stops the daemon and clears all indexed data (code chunks and memories).
    The index will be rebuilt on next daemon start.
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    chroma_dir = ci_data_dir / "chroma"

    if not force:
        confirm = prompt(
            "This will delete all indexed data. The index will be rebuilt on next start. Continue? [y/N]"
        )
        if confirm.lower() not in ("y", "yes"):
            print_info("Cancelled.")
            return

    manager = get_daemon_manager(project_root)

    # Stop daemon first unless keeping it
    was_running = manager.is_running()
    if was_running and not keep_daemon:
        print_info("Stopping daemon...")
        manager.stop()

    # Clear ChromaDB data
    if chroma_dir.exists():
        import shutil

        print_info("Clearing index data...")
        shutil.rmtree(chroma_dir)
        print_success("Index data cleared.")
    else:
        print_info("No index data found.")

    # Restart daemon if it was running
    if was_running and not keep_daemon:
        print_info("Restarting daemon...")
        if manager.start(wait=True):
            print_success("Daemon restarted. Index will be rebuilt.")
        else:
            print_warning(f"Failed to restart daemon. Check logs: {manager.log_file}")


@ci_app.command("logs")
def ci_logs(
    lines: int = typer.Option(DEFAULT_LOG_LINES, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show Codebase Intelligence daemon logs."""
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)

    if follow:
        # Use tail -f for following
        import subprocess
        import sys

        if not manager.log_file.exists():
            print_error("No log file found.")
            raise typer.Exit(code=1)

        print_info(f"Following logs from {manager.log_file} (Ctrl+C to stop)...")
        try:
            subprocess.run(
                ["tail", "-f", "-n", str(lines), str(manager.log_file)],
                check=True,
            )
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        log_content = manager.tail_logs(lines=lines)
        if log_content == "No log file found":
            print_warning("No log file found. Daemon may not have been started yet.")
        else:
            console.print(log_content)
