"""Codebase Intelligence commands for open-agent-kit."""

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from rich.console import Console

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import SKIP_DIRECTORIES
from open_agent_kit.utils import (
    dir_exists,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    prompt,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.manager import DaemonManager

console = Console()

ci_app = typer.Typer(
    name="ci",
    help="Manage Codebase Intelligence daemon and index",
    no_args_is_help=True,
)


def _check_oak_initialized(project_root: Path) -> None:
    """Check if OAK is initialized in the project."""
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)


def _check_ci_enabled(project_root: Path) -> None:
    """Check if Codebase Intelligence feature is enabled."""
    ci_dir = project_root / OAK_DIR / "ci"
    if not dir_exists(ci_dir):
        print_error(
            "Codebase Intelligence is not enabled. "
            "Run 'oak feature add codebase-intelligence' first."
        )
        raise typer.Exit(code=1)


def _get_daemon_manager(project_root: Path) -> "DaemonManager":
    """Get daemon manager instance with per-project port."""
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        DaemonManager,
        get_project_port,
    )

    ci_data_dir = project_root / OAK_DIR / "ci"
    port = get_project_port(project_root, ci_data_dir)
    return DaemonManager(project_root=project_root, port=port, ci_data_dir=ci_data_dir)


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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
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

            with httpx.Client(timeout=5.0) as client:
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
    max_files = 1000  # Limit scan for speed

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
        ci_dir = oak_dir / "ci"
        if not oak_dir.exists() or not ci_dir.exists():
            return  # Silently exit if not configured

    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)

    if manager.is_running():
        if not quiet:
            print_info("Daemon is already running.")
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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)

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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)

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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    ci_data_dir = project_root / OAK_DIR / "ci"
    chroma_dir = ci_data_dir / "chroma"

    if not force:
        confirm = prompt(
            "This will delete all indexed data. The index will be rebuilt on next start. Continue? [y/N]"
        )
        if confirm.lower() not in ("y", "yes"):
            print_info("Cancelled.")
            return

    manager = _get_daemon_manager(project_root)

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
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show Codebase Intelligence daemon logs."""
    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)

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


@ci_app.command("index")
def ci_index(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force full reindex (clear existing data first)"
    ),
) -> None:
    """Trigger codebase indexing.

    Tells the daemon to index (or re-index) the project.
    """
    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)

    if not manager.is_running():
        print_error("Daemon is not running. Start it first with 'oak ci start'.")
        raise typer.Exit(code=1)

    print_info("Triggering codebase indexing...")

    try:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/index/build",
                json={"full_rebuild": force},
            )

            if response.status_code == 200:
                result = response.json()
                print_success(
                    f"Indexing complete: {result.get('files_processed', 0)} files processed"
                )
                if result.get("chunks_indexed"):
                    print_info(f"  Chunks indexed: {result['chunks_indexed']}")
            else:
                print_error(f"Indexing failed: {response.text}")
                raise typer.Exit(code=1)

    except httpx.TimeoutException:
        print_warning("Indexing request timed out. The daemon may still be processing.")
        print_info("Check status with 'oak ci status'.")
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        logger.error(f"Failed to trigger indexing: {e}")
        print_error(f"Failed to trigger indexing: {e}")
        raise typer.Exit(code=1)


@ci_app.command("install-parsers")
def ci_install_parsers(
    all_languages: bool = typer.Option(
        False, "--all", "-a", help="Install parsers for all supported languages"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would be installed without installing"
    ),
) -> None:
    """Install tree-sitter language parsers for better code understanding.

    By default, scans your project and installs only the parsers needed
    for languages detected in your codebase.

    Examples:
        oak ci install-parsers           # Auto-detect and install
        oak ci install-parsers --all     # Install all supported parsers
        oak ci install-parsers --dry-run # Preview what would be installed
    """
    import subprocess
    import sys

    from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
        LANGUAGE_MAP,
        TREE_SITTER_PACKAGES,
        CodeChunker,
    )

    project_root = Path.cwd()

    # Get currently installed parsers
    chunker = CodeChunker()
    installed = chunker._available_languages

    if all_languages:
        # Install all supported parsers
        languages_to_install = set(TREE_SITTER_PACKAGES.keys()) - installed
        print_info("Installing all supported language parsers...")
    else:
        # Detect languages in project
        print_info("Scanning project for languages...")
        detected_languages: set[str] = set()

        for filepath in project_root.rglob("*"):
            if not filepath.is_file():
                continue
            # Skip common non-code directories
            path_str = str(filepath)
            if any(skip in path_str for skip in SKIP_DIRECTORIES):
                continue

            suffix = filepath.suffix.lower()
            if suffix in LANGUAGE_MAP:
                lang = LANGUAGE_MAP[suffix]
                if lang in TREE_SITTER_PACKAGES:
                    detected_languages.add(lang)

        if not detected_languages:
            print_info("No supported languages detected in project.")
            return

        print_info(f"Detected languages: {', '.join(sorted(detected_languages))}")
        languages_to_install = detected_languages - installed

    if not languages_to_install:
        print_success("All needed parsers are already installed!")
        return

    # Map languages to pip packages
    packages_to_install = []
    for lang in languages_to_install:
        pkg = TREE_SITTER_PACKAGES.get(lang)
        if pkg:
            # Convert module name to pip package name (tree_sitter_python -> tree-sitter-python)
            pip_pkg = pkg.replace("_", "-")
            packages_to_install.append(pip_pkg)

    if dry_run:
        print_header("Would install:")
        for pkg in sorted(packages_to_install):
            console.print(f"  {pkg}")
        return

    print_info(f"Installing {len(packages_to_install)} parser(s)...")

    # Try uv first, fall back to pip
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        install_cmd = ["uv", "pip", "install"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        install_cmd = [sys.executable, "-m", "pip", "install"]

    try:
        cmd = install_cmd + packages_to_install
        console.print(f"  Running: {' '.join(cmd)}", style="dim")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print_success(f"Installed {len(packages_to_install)} parser(s) successfully!")

        # Show what was installed
        for pkg in sorted(packages_to_install):
            console.print(f"  [green]✓[/green] {pkg}")

        console.print()
        print_info("Restart the daemon to use new parsers:")
        print_info("  oak ci restart")

    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install parsers: {e.stderr}")
        raise typer.Exit(code=1)


@ci_app.command("languages")
def ci_languages() -> None:
    """Show supported programming languages and AST parsing status.

    Displays which languages have tree-sitter parsers installed for
    better semantic chunking vs line-based fallback.
    """
    from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
        LANGUAGE_MAP,
        CodeChunker,
    )

    print_header("Supported Languages")

    chunker = CodeChunker()
    available_ast = chunker._available_languages

    # Group by AST support
    ast_supported = []
    line_based = []

    for ext, lang in sorted(LANGUAGE_MAP.items(), key=lambda x: x[1]):
        if lang in available_ast:
            ast_supported.append((ext, lang))
        else:
            line_based.append((ext, lang))

    if ast_supported:
        print_success("AST-based chunking (semantic):")
        current_lang = None
        for ext, lang in ast_supported:
            if lang != current_lang:
                if current_lang:
                    console.print()
                current_lang = lang
                console.print(f"  {lang}", style="bold")
            console.print(f"    {ext}", style="dim")

    console.print()

    if line_based:
        print_info("Line-based chunking (no AST parser installed):")
        current_lang = None
        for _ext, lang in line_based:
            if lang != current_lang:
                current_lang = lang
                console.print(f"  {lang}", style="dim")

    console.print()
    print_info("Install tree-sitter parsers for better code understanding:")
    print_info("  pip install tree-sitter-python tree-sitter-javascript tree-sitter-c-sharp")


@ci_app.command("config")
def ci_config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Embedding provider (ollama, openai, fastembed)"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Embedding model name"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    list_models: bool = typer.Option(
        False, "--list-models", "-l", help="List known embedding models"
    ),
    debug: bool | None = typer.Option(
        None, "--debug", "-d", help="Enable debug logging (true/false)"
    ),
    log_level: str | None = typer.Option(
        None, "--log-level", help="Set log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    # Summarization options
    summarization: bool | None = typer.Option(
        None, "--summarization/--no-summarization", help="Enable/disable LLM summarization"
    ),
    summarization_provider: str | None = typer.Option(
        None, "--sum-provider", help="Summarization provider (ollama, openai)"
    ),
    summarization_model: str | None = typer.Option(
        None, "--sum-model", help="Summarization model name (e.g., qwen2.5:3b, phi4)"
    ),
    summarization_url: str | None = typer.Option(
        None, "--sum-url", help="Summarization API base URL"
    ),
    list_summarization_models: bool = typer.Option(
        False, "--list-sum-models", help="List available summarization models from provider"
    ),
    summarization_context: str | None = typer.Option(
        None,
        "--sum-context",
        help="Context window size: number (e.g., 32768), 'auto' to discover, or 'show' to display current",
    ),
) -> None:
    """Configure embedding, summarization, and logging settings.

    Examples:
        oak ci config --show                    # Show current config
        oak ci config --list-models             # List known embedding models
        oak ci config -p ollama -m nomic-embed-code  # Use code embedding model
        oak ci config -p openai -u http://localhost:1234/v1  # Use LMStudio
        oak ci config --debug                   # Enable debug logging
        oak ci config --log-level INFO          # Set log level

    Summarization examples:
        oak ci config --list-sum-models         # List available LLM models
        oak ci config --sum-model phi4          # Use phi4 for summarization
        oak ci config --sum-context auto        # Auto-discover context window from API
        oak ci config --sum-context 32768       # Manually set context window
        oak ci config --no-summarization        # Disable LLM summarization

    Environment variables (override config file):
        OAK_CI_DEBUG=1          # Enable debug logging
        OAK_CI_LOG_LEVEL=DEBUG  # Set log level
    """
    project_root = Path.cwd()

    if list_models:
        from open_agent_kit.features.codebase_intelligence.config import load_ci_config

        config = load_ci_config(project_root)
        emb_config = config.embedding

        print_header("Available Embedding Models")
        print_info(f"Provider: {emb_config.provider}")
        print_info(f"URL: {emb_config.base_url}")
        console.print()
        print_info("Querying provider for embedding models...")

        # Query the provider for available embedding models
        import httpx

        try:
            with httpx.Client(timeout=5.0) as client:
                url = emb_config.base_url.rstrip("/")
                if emb_config.provider == "ollama":
                    response = client.get(f"{url}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        models = data.get("models", [])
                        embedding_models = []
                        for m in models:
                            name = m.get("name", "")
                            details = m.get("details", {})
                            has_embed = details.get("embedding_length") or "embed" in name.lower()
                            if has_embed:
                                dims = details.get("embedding_length", "?")
                                size = m.get("size", 0)
                                size_str = (
                                    f"{size / 1e9:.1f}GB" if size > 1e9 else f"{size / 1e6:.0f}MB"
                                )
                                embedding_models.append((name.split(":")[0], dims, size_str))
                        if embedding_models:
                            for name, dims, size in embedding_models:
                                console.print(f"  {name}")
                                console.print(f"    Dimensions: {dims}, Size: {size}", style="dim")
                        else:
                            print_warning("No embedding models found.")
                            print_info("  Pull one: ollama pull bge-m3")
                    else:
                        print_warning(f"Failed to query Ollama: {response.status_code}")
                else:
                    response = client.get(f"{url}/v1/models")
                    if response.status_code == 200:
                        data = response.json()
                        models = [
                            m["id"] for m in data.get("data", []) if "embed" in m["id"].lower()
                        ]
                        for name in models:
                            console.print(f"  {name}")
                    else:
                        print_warning(f"Failed to query provider: {response.status_code}")
        except httpx.ConnectError:
            print_warning(f"Cannot connect to {emb_config.provider} at {emb_config.base_url}")
            print_info("  Make sure the provider is running")
        except Exception as e:
            print_warning(f"Error: {e}")

        console.print()
        print_info("Set model: oak ci config --model <model>")
        print_info("Discover context: Use the web UI or oak ci config --context auto")
        return

    if list_summarization_models:
        from open_agent_kit.features.codebase_intelligence.config import load_ci_config
        from open_agent_kit.features.codebase_intelligence.summarization import (
            list_available_models,
        )

        config = load_ci_config(project_root)
        sum_config = config.summarization

        print_header("Available Summarization Models")
        print_info(f"Provider: {sum_config.provider}")
        print_info(f"URL: {sum_config.base_url}")
        console.print()

        available_models = list_available_models(
            base_url=sum_config.base_url,
            provider=sum_config.provider,
        )

        if not available_models:
            print_warning("No models available. Is the provider running?")
            print_info("  For Ollama: ollama serve")
            return

        for model_info in available_models:
            ctx = f" (context: {model_info.context_window})" if model_info.context_window else ""
            console.print(f"  {model_info.id}{ctx}")

        console.print()
        print_info("Set summarization model: oak ci config --sum-model <model>")
        return

    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    config = load_ci_config(project_root)

    # Handle --sum-context show/auto separately
    if summarization_context == "show":
        config = load_ci_config(project_root)
        summ = config.summarization
        print_header("Summarization Context Configuration")
        print_info(f"Model: {summ.model}")
        print_info(f"Provider: {summ.provider}")
        context_tokens = summ.context_tokens
        if context_tokens:
            print_success(f"Context tokens: {context_tokens:,}")
        else:
            print_warning(f"Context tokens: not set (using default: {summ.get_context_tokens():,})")
            print_info("  Set with: oak ci config --sum-context <tokens>")
            print_info("  Or discover: oak ci config --sum-context auto")
        return

    if summarization_context == "auto":
        from open_agent_kit.features.codebase_intelligence.summarization import (
            discover_model_context,
        )

        config = load_ci_config(project_root)
        summ = config.summarization
        print_info(f"Discovering context window for {summ.model}...")

        discovered = discover_model_context(
            model=summ.model,
            base_url=summ.base_url,
            provider=summ.provider,
            api_key=summ.api_key,
        )

        if discovered:
            config.summarization.context_tokens = discovered
            save_ci_config(project_root, config)
            print_success(f"Context tokens discovered and saved: {discovered:,}")
            print_info("Restart the daemon to apply: oak ci restart")
        else:
            print_warning("Could not discover context window from API.")
            print_info(
                f"  Provider {summ.provider} at {summ.base_url} may not report context info."
            )
            print_info("  Set manually: oak ci config --sum-context <tokens>")
            print_info("  Example: oak ci config --sum-context 32768")
        return

    # Check if this is just a show request (no changes)
    no_changes = (
        provider is None
        and model is None
        and base_url is None
        and debug is None
        and log_level is None
        and summarization is None
        and summarization_provider is None
        and summarization_model is None
        and summarization_url is None
        and summarization_context is None
    )

    if show or no_changes:
        print_header("Codebase Intelligence Configuration")

        # Embedding config
        console.print("[bold]Embedding:[/bold]")
        emb = config.embedding
        print_info(f"  Provider: {emb.provider}")
        print_info(f"  Model: {emb.model}")
        print_info(f"  Base URL: {emb.base_url}")
        print_info(f"  Max Chunk Chars: {emb.get_max_chunk_chars()}")
        dims = emb.get_dimensions()
        print_info(f"  Dimensions: {dims or 'auto-detect'}")
        print_info(f"  Fallback Enabled: {emb.fallback_enabled}")
        print_info(f"  Context Tokens: {emb.get_context_tokens()}")

        # Summarization config
        console.print()
        console.print("[bold]Summarization (LLM):[/bold]")
        summ = config.summarization
        status = "[green]enabled[/green]" if summ.enabled else "[dim]disabled[/dim]"
        console.print(f"  Enabled: {status}")
        print_info(f"  Provider: {summ.provider}")
        print_info(f"  Model: {summ.model}")
        print_info(f"  Base URL: {summ.base_url}")
        print_info(f"  Timeout: {summ.timeout}s")
        sum_context = summ.context_tokens
        if sum_context:
            print_info(f"  Context Tokens: {sum_context:,}")
        else:
            print_info(f"  Context Tokens: {summ.get_context_tokens():,} (default)")
            console.print("    [dim]Discover: oak ci config --sum-context auto[/dim]")

        # Show logging config
        console.print()
        console.print("[bold]Logging:[/bold]")
        print_info(f"  Log Level: {config.log_level}")
        effective = config.get_effective_log_level()
        if effective != config.log_level:
            print_info(f"    (effective: {effective} from environment)")
        return

    # Update configuration
    changed = False
    embedding_changed = False

    if provider:
        config.embedding.provider = provider
        changed = True
        embedding_changed = True
    if model:
        config.embedding.model = model
        # Reset dimensions and chunk chars to auto-detect from new model
        config.embedding.dimensions = None
        config.embedding.max_chunk_chars = None
        changed = True
        embedding_changed = True
    if base_url:
        config.embedding.base_url = base_url
        changed = True
        embedding_changed = True

    # Handle debug/log level settings
    if debug is not None:
        config.log_level = "DEBUG" if debug else "INFO"
        changed = True
    if log_level:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if log_level.upper() in valid_levels:
            config.log_level = log_level.upper()
            changed = True
        else:
            print_error(
                f"Invalid log level '{log_level}'. Must be one of: {', '.join(valid_levels)}"
            )
            raise typer.Exit(code=1)

    # Handle summarization settings
    summarization_changed = False
    if summarization is not None:
        config.summarization.enabled = summarization
        changed = True
        summarization_changed = True
    if summarization_provider:
        config.summarization.provider = summarization_provider
        changed = True
        summarization_changed = True
    if summarization_model:
        config.summarization.model = summarization_model
        # Reset context_tokens when model changes (user should re-discover)
        config.summarization.context_tokens = None
        changed = True
        summarization_changed = True
    if summarization_url:
        config.summarization.base_url = summarization_url
        changed = True
        summarization_changed = True
    if summarization_context and summarization_context not in ("show", "auto"):
        # Numeric value provided
        try:
            ctx_tokens = int(summarization_context)
            if ctx_tokens < 1024:
                print_warning(
                    f"Context tokens {ctx_tokens} seems very low. Typical values: 4096-131072"
                )
            config.summarization.context_tokens = ctx_tokens
            changed = True
            summarization_changed = True
        except ValueError:
            print_error(
                f"Invalid context value '{summarization_context}'. Use a number, 'auto', or 'show'."
            )
            raise typer.Exit(code=1)

    if changed:
        save_ci_config(project_root, config)
        print_success("Configuration updated.")

        if embedding_changed:
            print_info(f"  Provider: {config.embedding.provider}")
            print_info(f"  Model: {config.embedding.model}")
            print_info(f"  Base URL: {config.embedding.base_url}")
            print_info(f"  Max Chunk Chars: {config.embedding.get_max_chunk_chars()}")

        if summarization_changed:
            status = "enabled" if config.summarization.enabled else "disabled"
            print_info(f"  Summarization: {status}")
            print_info(f"  Summarization Provider: {config.summarization.provider}")
            print_info(f"  Summarization Model: {config.summarization.model}")

        if debug is not None or log_level:
            print_info(f"  Log Level: {config.log_level}")

        console.print()
        if embedding_changed:
            print_warning("Restart the daemon and rebuild the index to apply embedding changes:")
            print_info("  oak ci restart && oak ci reset -f")
        elif summarization_changed or debug is not None or log_level:
            print_info("Restart the daemon to apply changes:")
            print_info("  oak ci restart")


@ci_app.command("exclude")
def ci_exclude(
    add: list[str] = typer.Option(
        None,
        "--add",
        "-a",
        help="Add pattern(s) to exclude (glob format, e.g., 'vendor/**', 'aiounifi')",
    ),
    remove: list[str] = typer.Option(
        None, "--remove", "-r", help="Remove pattern(s) from exclude list"
    ),
    show: bool = typer.Option(False, "--show", "-s", help="Show all active exclude patterns"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default exclude patterns"),
) -> None:
    """Manage directory/file exclusions from indexing.

    Exclude directories or files from being indexed by the CI daemon.
    Patterns use glob format (fnmatch style).

    Examples:
        oak ci exclude --show                  # List all exclude patterns
        oak ci exclude -a aiounifi             # Exclude 'aiounifi' directory
        oak ci exclude -a "vendor/**"          # Exclude vendor and subdirs
        oak ci exclude -a lib -a tmp           # Exclude multiple directories
        oak ci exclude -r aiounifi             # Remove from exclusions
        oak ci exclude --reset                 # Reset to defaults

    Pattern Format:
        - 'dirname' matches directory name anywhere
        - 'dirname/**' matches directory and all contents
        - '**/*.log' matches .log files in any directory
        - '*.min.js' matches minified JS files

    After changing excludes, restart the daemon and rebuild the index:
        oak ci restart && oak ci reset -f
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        DEFAULT_EXCLUDE_PATTERNS,
        load_ci_config,
        save_ci_config,
    )

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    config = load_ci_config(project_root)

    # Reset to defaults
    if reset:
        config.exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.copy()
        save_ci_config(project_root, config)
        print_success("Exclude patterns reset to defaults.")
        print_info("Restart daemon and rebuild index: oak ci restart && oak ci reset -f")
        return

    # Add patterns
    changed = False
    if add:
        for pattern in add:
            if pattern not in config.exclude_patterns:
                config.exclude_patterns.append(pattern)
                print_success(f"Added: {pattern}")
                changed = True
            else:
                print_warning(f"Already excluded: {pattern}")

    # Remove patterns
    if remove:
        for pattern in remove:
            if pattern in config.exclude_patterns:
                config.exclude_patterns.remove(pattern)
                print_success(f"Removed: {pattern}")
                changed = True
            else:
                print_warning(f"Not in exclude list: {pattern}")

    # Save if changed
    if changed:
        save_ci_config(project_root, config)
        console.print()
        print_info("Restart daemon and rebuild index to apply changes:")
        print_info("  oak ci restart && oak ci reset -f")
        return

    # Show patterns (default behavior if no changes)
    if show or (not add and not remove):
        print_header("Exclude Patterns")

        # Show user-configured patterns (from config.yaml)
        user_patterns = config.get_user_exclude_patterns()
        if user_patterns:
            print_info("User-configured exclusions:")
            for pattern in user_patterns:
                console.print(f"  [green]•[/green] {pattern}")
        else:
            print_info("No user-configured exclusions.")

        console.print()
        print_info("Built-in default exclusions:")
        for pattern in sorted(DEFAULT_EXCLUDE_PATTERNS):
            console.print(f"  [dim]•[/dim] {pattern}", style="dim")

        console.print()
        print_info("Add exclusions: oak ci exclude -a <pattern>")
        print_info("Edit directly: .oak/ci/config.yaml (exclude_patterns list)")


@ci_app.command("debug")
def ci_debug(
    enable: bool = typer.Argument(
        None,
        help="Enable (true) or disable (false) debug logging. Omit to toggle.",
    ),
    restart: bool = typer.Option(
        True, "--restart/--no-restart", "-r/-R", help="Restart daemon after change"
    ),
) -> None:
    """Toggle debug logging for detailed chunking output.

    Quick shortcut for 'oak ci config --debug' with automatic restart.

    Example:
        oak ci debug              # Toggle debug mode
        oak ci debug true         # Enable debug mode
        oak ci debug false        # Disable debug mode
        oak ci debug --no-restart # Change without restart
    """
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config, save_ci_config

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    config = load_ci_config(project_root)
    current_level = config.log_level.upper()

    # Determine new state
    if enable is None:
        # Toggle
        new_level = "INFO" if current_level == "DEBUG" else "DEBUG"
    else:
        new_level = "DEBUG" if enable else "INFO"

    if new_level == current_level:
        print_info(f"Debug logging already {'enabled' if new_level == 'DEBUG' else 'disabled'}")
        return

    config.log_level = new_level
    save_ci_config(project_root, config)

    if new_level == "DEBUG":
        print_success("Debug logging enabled")
        print_info("  Per-file chunking will show: AST package, language, chunk counts")
        print_info("  Summary will show: extracted node types per language")
    else:
        print_info("Debug logging disabled (INFO level)")

    if restart:
        manager = _get_daemon_manager(project_root)
        if manager.is_running():
            print_info("Restarting daemon to apply changes...")
            manager.stop()
            import time

            time.sleep(1)
            manager.start()
            print_success("Daemon restarted with new log level")
        else:
            print_info("Daemon not running. Start with: oak ci start")


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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    port = get_project_port(project_root)
    manager = _get_daemon_manager(project_root)

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
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
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


@ci_app.command("mcp")
def ci_mcp(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type: 'stdio' (for Claude Code) or 'streamable-http' (for web)",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port for HTTP transport (only used with streamable-http)",
    ),
    project: str = typer.Option(
        None,
        "--project",
        help="Project root directory (defaults to current directory or OAK_CI_PROJECT_ROOT env)",
    ),
) -> None:
    """Run the MCP protocol server for native tool discovery.

    This starts an MCP server that exposes CI tools (oak_search, oak_remember,
    oak_context, oak_status) via the Model Context Protocol.

    For Claude Code, add to your MCP config:
    {
      "mcpServers": {
        "codebase-intelligence": {
          "command": "oak",
          "args": ["ci", "mcp", "--project", "/path/to/your/project"]
        }
      }
    }

    The MCP server requires the CI daemon to be running (oak ci start).
    """
    # Determine project root: --project flag > OAK_CI_PROJECT_ROOT env > cwd
    if project:
        project_root = Path(project)
    elif os.environ.get("OAK_CI_PROJECT_ROOT"):
        project_root = Path(os.environ["OAK_CI_PROJECT_ROOT"])
    else:
        project_root = Path.cwd()

    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    # Check if daemon is running
    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_warning("CI daemon is not running. Starting it now...")
        if not manager.start():
            print_error("Failed to start daemon. Run 'oak ci start' manually and check logs.")
            raise typer.Exit(code=1)
        print_success(f"Daemon started at http://localhost:{manager.port}")

    try:
        from open_agent_kit.features.codebase_intelligence.daemon.mcp_server import run_mcp_server
    except ImportError as e:
        print_error(f"MCP server not available: {e}")
        print_info("Install the mcp package: pip install mcp")
        raise typer.Exit(code=1)

    if transport == "streamable-http":
        print_info(f"Starting MCP server on http://localhost:{port}/mcp")
        print_info("Press Ctrl+C to stop.")
        # Set port via environment for streamable-http
        os.environ["FASTMCP_PORT"] = str(port)

    # Run the MCP server (blocks)
    from open_agent_kit.features.codebase_intelligence.daemon.mcp_server import MCPTransport

    # Validate transport before cast
    valid_transports = {"stdio", "sse", "streamable-http"}
    if transport not in valid_transports:
        print_error(
            f"Invalid transport: {transport}. Must be one of: {', '.join(sorted(valid_transports))}"
        )
        raise typer.Exit(code=1)
    run_mcp_server(project_root, transport=cast(MCPTransport, transport))


# =============================================================================
# Agent-facing commands (search, remember, context)
# These are designed to be called by AI agents via skills/prompts
# =============================================================================


@ci_app.command("search")
def ci_search(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return"),
    search_type: str = typer.Option(
        "all", "--type", "-t", help="Search type: 'all', 'code', or 'memory'"
    ),
    format_output: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
    no_weight: bool = typer.Option(
        False,
        "--no-weight",
        "-w",
        help="Disable doc_type weighting (useful for translation searches)",
    ),
) -> None:
    """Search the codebase and memories using semantic similarity.

    Find relevant code implementations, past decisions, gotchas, and learnings.
    Results are ranked by relevance score. By default, i18n/config files are
    down-weighted; use --no-weight to disable this for translation searches.

    Examples:
        oak ci search "authentication middleware"
        oak ci search "error handling patterns" --type code
        oak ci search "database connection" -n 5 -f text
        oak ci search "translation strings" --no-weight
    """
    import json

    import httpx

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/search",
                json={
                    "query": query,
                    "search_type": search_type,
                    "limit": min(max(1, limit), 50),
                    "apply_doc_type_weights": not no_weight,
                },
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                code_results = result.get("code", [])
                memory_results = result.get("memory", [])

                if code_results:
                    print_header(f"Code Results ({len(code_results)})")
                    for item in code_results:
                        score = item.get("score", 0)
                        filepath = item.get("file_path", "?")
                        chunk_type = item.get("chunk_type", "?")
                        name = item.get("name", "")
                        lines = item.get("start_line", "?")
                        console.print(f"\n[bold]{filepath}:{lines}[/bold] ({chunk_type}: {name})")
                        console.print(f"  Score: {score:.1%}", style="dim")
                        preview = item.get("content", "")[:200]
                        if preview:
                            console.print(f"  {preview}...", style="dim")

                if memory_results:
                    console.print()
                    print_header(f"Memory Results ({len(memory_results)})")
                    for item in memory_results:
                        score = item.get("score", 0)
                        memory_type = item.get("memory_type", "?")
                        observation = item.get("observation", "")
                        console.print(f"\n[bold][{memory_type}][/bold] {observation[:100]}")
                        console.print(f"  Score: {score:.1%}", style="dim")

                if not code_results and not memory_results:
                    print_warning("No results found.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Search failed: {e}")
        raise typer.Exit(code=1)


@ci_app.command("remember")
def ci_remember(
    observation: str = typer.Argument(..., help="The observation or learning to store"),
    memory_type: str = typer.Option(
        "discovery",
        "--type",
        "-t",
        help="Type: 'gotcha', 'bug_fix', 'decision', 'discovery', 'trade_off'",
    ),
    context: str = typer.Option(
        None, "--context", "-c", help="Related file path or additional context"
    ),
    format_output: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """Store an observation, decision, or learning for future sessions.

    Use this when you discover something important about the codebase that
    would help in future work. Memories persist across sessions.

    Memory Types:
        gotcha     - Non-obvious behavior or quirk that could trip someone up
        bug_fix    - Solution to a bug, including root cause
        decision   - Architectural or design decision with rationale
        discovery  - General insight or learning about the codebase
        trade_off  - Trade-off that was made and why

    Examples:
        oak ci remember "The auth module requires Redis for sessions" -t discovery
        oak ci remember "Always call cleanup() before disconnect" -t gotcha -c src/db.py
        oak ci remember "Chose SQLite over PostgreSQL for simplicity" -t decision
    """
    import json

    import httpx

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    valid_types = ["gotcha", "bug_fix", "decision", "discovery", "trade_off"]
    if memory_type not in valid_types:
        print_error(
            f"Invalid memory type '{memory_type}'. Must be one of: {', '.join(valid_types)}"
        )
        raise typer.Exit(code=1)

    try:
        data = {
            "observation": observation,
            "memory_type": memory_type,
        }
        if context:
            data["context"] = context

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/remember",
                json=data,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                if result.get("stored"):
                    print_success("Memory stored successfully.")
                    if result.get("id"):
                        print_info(f"  ID: {result['id']}")
                else:
                    print_warning("Memory was not stored.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to store memory: {e}")
        raise typer.Exit(code=1)


@ci_app.command("context")
def ci_context(
    task: str = typer.Argument(..., help="Description of the task you're working on"),
    files: list[str] = typer.Option(
        None, "--file", "-f", help="Files currently being viewed/edited (can specify multiple)"
    ),
    max_tokens: int = typer.Option(
        2000, "--max-tokens", "-m", help="Maximum tokens of context to return"
    ),
    format_output: str = typer.Option("json", "--format", help="Output format: 'json' or 'text'"),
    no_weight: bool = typer.Option(
        False, "--no-weight", "-w", help="Disable doc_type weighting (useful for non-code tasks)"
    ),
) -> None:
    """Get relevant context for your current task.

    Call this when starting work on something to retrieve related code,
    past decisions, and applicable project guidelines. By default,
    i18n/config files are down-weighted; use --no-weight to disable this.

    Examples:
        oak ci context "implementing user logout"
        oak ci context "fixing authentication bug" -f src/auth.py
        oak ci context "adding database migration" -f models.py -f db.py -m 4000
        oak ci context "updating translation strings" --no-weight
    """
    import json

    import httpx

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        data: dict[str, Any] = {
            "task": task,
            "max_tokens": max_tokens,
            "apply_doc_type_weights": not no_weight,
        }
        if files:
            data["current_files"] = list(files)

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/context",
                json=data,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                code_context = result.get("code", [])
                memory_context = result.get("memories", [])
                guidelines = result.get("guidelines", [])

                if guidelines:
                    print_header("Guidelines")
                    for g in guidelines:
                        console.print(f"  • {g}")

                if memory_context:
                    console.print()
                    print_header("Relevant Memories")
                    for mem in memory_context:
                        mem_type = mem.get("memory_type", "?")
                        obs = mem.get("observation", "")
                        console.print(f"  [{mem_type}] {obs}")

                if code_context:
                    console.print()
                    print_header("Related Code")
                    for code in code_context:
                        filepath = code.get("file_path", "?")
                        chunk_type = code.get("chunk_type", "?")
                        name = code.get("name", "")
                        console.print(f"  {filepath} ({chunk_type}: {name})")

                if not code_context and not memory_context and not guidelines:
                    print_info("No relevant context found for this task.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to get context: {e}")
        raise typer.Exit(code=1)


@ci_app.command("memories")
def ci_memories(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of memories to show"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    memory_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type: gotcha, bug_fix, decision, discovery, trade_off, session_summary",
    ),
    exclude_sessions: bool = typer.Option(
        False, "--exclude-sessions", "-x", help="Exclude session summaries"
    ),
    format_output: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """List stored memories and session summaries.

    Browse all observations, decisions, gotchas, and session summaries stored
    by CI. Unlike search, this lists memories without semantic matching.

    Examples:
        oak ci memories                    # List recent memories
        oak ci memories --type gotcha      # Filter by type
        oak ci memories -n 50              # Show more results
        oak ci memories --type session_summary  # List session summaries only
        oak ci memories -x                 # Exclude session summaries
        oak ci memories -f json            # JSON output for scripting
    """
    import json

    import httpx

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    # Validate memory type if provided
    valid_types = ["gotcha", "bug_fix", "decision", "discovery", "trade_off", "session_summary"]
    if memory_type and memory_type not in valid_types:
        print_error(
            f"Invalid memory type '{memory_type}'. Must be one of: {', '.join(valid_types)}"
        )
        raise typer.Exit(code=1)

    try:
        params: dict[str, str | int] = {
            "limit": min(max(1, limit), 100),
            "offset": max(0, offset),
        }
        if memory_type:
            params["memory_type"] = memory_type
        if exclude_sessions:
            params["exclude_sessions"] = "true"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"http://localhost:{manager.port}/api/memories",
                params=params,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                memories = result.get("memories", [])
                total = result.get("total", 0)

                if not memories:
                    print_info("No memories found.")
                    return

                # Memory type icons
                type_icons = {
                    "gotcha": "⚠️",
                    "bug_fix": "🐛",
                    "decision": "📐",
                    "discovery": "💡",
                    "trade_off": "⚖️",
                    "session_summary": "📋",
                }

                print_header(f"Memories ({len(memories)} of {total})")
                for mem in memories:
                    mem_type = mem.get("memory_type", "discovery")
                    icon = type_icons.get(mem_type, "•")
                    observation = mem.get("observation", "")
                    created = mem.get("created_at", "")

                    # Truncate long observations
                    if len(observation) > 100:
                        observation = observation[:97] + "..."

                    console.print(f"\n{icon} [bold][{mem_type}][/bold] {observation}")
                    if created:
                        # Format datetime if present
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            formatted = dt.strftime("%Y-%m-%d %H:%M")
                            console.print(f"  [dim]{formatted}[/dim]")
                        except (ValueError, AttributeError, TypeError) as e:
                            logger.debug(f"Failed to parse created timestamp: {e}")
                            console.print(f"  [dim]{created}[/dim]")

                    context = mem.get("context")
                    if context:
                        console.print(f"  Context: {context}", style="dim")

                    tags = mem.get("tags", [])
                    if tags:
                        console.print(f"  Tags: {', '.join(tags)}", style="dim")

                # Pagination info
                if total > len(memories):
                    next_offset = offset + limit
                    console.print()
                    print_info(f"Page {offset // limit + 1} of {(total + limit - 1) // limit}")
                    if next_offset < total:
                        print_info(f"  Next page: oak ci memories -n {limit} -o {next_offset}")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to list memories: {e}")
        raise typer.Exit(code=1)


@ci_app.command("sessions")
def ci_sessions(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show"),
    format_output: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """List recent session summaries.

    Shortcut for 'oak ci memories --type session_summary'.
    Shows LLM-generated summaries from past coding sessions.

    Examples:
        oak ci sessions          # List last 10 session summaries
        oak ci sessions -n 5     # Show fewer
        oak ci sessions -f json  # JSON output
    """
    import json

    import httpx

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    manager = _get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        query_params: dict[str, str | int] = {
            "limit": min(max(1, limit), 100),
            "memory_type": "session_summary",
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"http://localhost:{manager.port}/api/memories",
                params=query_params,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                memories = result.get("memories", [])
                total = result.get("total", 0)

                if not memories:
                    print_info("No session summaries found.")
                    print_info("Sessions are summarized when you end a coding session.")
                    return

                print_header(f"Session Summaries ({len(memories)} of {total})")
                for i, mem in enumerate(memories, 1):
                    observation = mem.get("observation", "")
                    created = mem.get("created_at", "")
                    tags = mem.get("tags", [])

                    # Format datetime
                    time_str = ""
                    if created:
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            time_str = dt.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, AttributeError, TypeError) as e:
                            logger.debug(f"Failed to parse session timestamp: {e}")
                            time_str = created

                    console.print(f"\n[bold]Session {i}[/bold] - {time_str}")

                    # Show agent if in tags
                    agent = next((t for t in tags if t not in ["session", "llm-summarized"]), None)
                    if agent:
                        console.print(f"  Agent: {agent}", style="dim")

                    # Show summary (may be multi-line)
                    console.print(f"  {observation}")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to list sessions: {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Testing and diagnostics
# =============================================================================


@ci_app.command("test")
def ci_test(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Test Codebase Intelligence integration.

    Runs a series of tests to verify hooks, search, and memory are working.
    """
    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    import httpx

    print_header("Codebase Intelligence Integration Test")

    manager = _get_daemon_manager(project_root)
    port = manager.port
    base_url = f"http://localhost:{port}"

    tests_passed = 0
    tests_failed = 0

    def test(name: str, func: Callable[[], Any]) -> bool:
        nonlocal tests_passed, tests_failed
        try:
            result = func()
            if result:
                print_success(f"✓ {name}")
                if verbose and isinstance(result, dict):
                    console.print(f"  {result}")
                tests_passed += 1
                return True
            else:
                print_error(f"✗ {name}: No result")
                tests_failed += 1
                return False
        except Exception as e:
            print_error(f"✗ {name}: {e}")
            tests_failed += 1
            return False

    # Test 1: Daemon health
    def test_health() -> bool:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base_url}/api/health")
            return r.status_code == 200

    test("Daemon health check", test_health)

    # Test 2: Index status
    def test_index() -> bool:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base_url}/api/index/status")
            data = r.json()
            return data.get("status") in ["ready", "indexing"]

    test("Index status", test_index)

    # Test 3: Session start hook
    def test_session_start() -> bool:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(f"{base_url}/api/hook/session-start", json={"agent": "test"})
            data = r.json()
            return data.get("status") == "ok" and "session_id" in data

    test("Session start hook", test_session_start)

    # Test 4: Search API
    def test_search() -> bool:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(f"{base_url}/api/search", json={"query": "main function", "limit": 3})
            data = r.json()
            return "code" in data or "memory" in data

    test("Semantic search", test_search)

    # Test 5: Remember API
    def test_remember() -> bool:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(
                f"{base_url}/api/remember",
                json={
                    "observation": "Test observation from CI test",
                    "memory_type": "discovery",
                    "context": "ci_test",
                },
            )
            data = r.json()
            return data.get("stored") is True

    test("Memory storage", test_remember)

    # Test 6: MCP tools listing
    def test_mcp_tools() -> bool:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base_url}/api/mcp/tools")
            data = r.json()
            tools = [t["name"] for t in data.get("tools", [])]
            return "oak_search" in tools and "oak_remember" in tools

    test("MCP tools available", test_mcp_tools)

    # Test 7: Auto-capture via post-tool-use hook
    def test_auto_capture() -> bool:
        import base64

        # Simulate an error output that should trigger auto-capture
        error_output = "Error: Failed to connect to database\nTraceback: connection refused"
        tool_input = {"command": "pytest tests/"}
        output_b64 = base64.b64encode(error_output.encode()).decode()

        with httpx.Client(timeout=5.0) as client:
            r = client.post(
                f"{base_url}/api/hook/post-tool-use",
                json={
                    "agent": "test",
                    "tool_name": "Bash",
                    "tool_input": tool_input,
                    "tool_output_b64": output_b64,
                },
            )
            data = r.json()
            # Should have captured at least one observation due to error keywords
            status_ok = data.get("status") == "ok"
            has_observations = int(data.get("observations_captured", 0)) > 0
            return status_ok and has_observations

    test("Auto-capture from tool output", test_auto_capture)

    # Test 8: Check hook files exist
    def test_hook_files() -> bool:
        claude_hooks = project_root / ".claude" / "settings.json"
        cursor_hooks = project_root / ".cursor" / "hooks.json"
        # At least one should exist
        return claude_hooks.exists() or cursor_hooks.exists()

    test("Agent hook files installed", test_hook_files)

    # Summary
    console.print()
    total = tests_passed + tests_failed
    if tests_failed == 0:
        print_success(f"All {total} tests passed!")
    else:
        print_warning(f"{tests_passed}/{total} tests passed, {tests_failed} failed")

    if tests_failed > 0:
        raise typer.Exit(code=1)


@ci_app.command("backup")
def ci_backup(
    include_activities: bool = typer.Option(
        False,
        "--include-activities",
        "-a",
        help="Include activities table (can be large)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: oak/data/ci_history.sql)",
    ),
) -> None:
    """Export CI database to SQL backup file.

    Exports sessions, prompts, and memory observations. Use --include-activities
    to also include the activities table (warning: can be large).

    The backup file is text-based, can be committed to git, and will be
    automatically restored when the feature is re-enabled.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_HISTORY_BACKUP_DIR,
        CI_HISTORY_BACKUP_FILE,
    )

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    db_path = project_root / OAK_DIR / "ci" / "activities.db"
    if not db_path.exists():
        print_error("No CI database found. Start the daemon first: oak ci start")
        raise typer.Exit(code=1)

    if output:
        backup_path = Path(output)
    else:
        backup_path = project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE

    backup_path.parent.mkdir(parents=True, exist_ok=True)

    print_info(f"Exporting CI database to {backup_path}...")
    if include_activities:
        print_info("  Including activities table (may be large)")

    store = ActivityStore(db_path)
    count = store.export_to_sql(backup_path, include_activities=include_activities)
    store.close()

    print_success(f"Exported {count} records to {backup_path}")
    print_info("  This file can be committed to git for version control")


@ci_app.command("restore")
def ci_restore(
    input_path: str | None = typer.Option(
        None,
        "--input",
        "-i",
        help="Input path (default: oak/data/ci_history.sql)",
    ),
) -> None:
    """Restore CI database from SQL backup file.

    Imports sessions, prompts, and memory observations from backup.
    ChromaDB will be rebuilt automatically on next daemon startup.

    This is automatically done when re-enabling the codebase-intelligence
    feature, but you can also restore manually.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_HISTORY_BACKUP_DIR,
        CI_HISTORY_BACKUP_FILE,
    )

    project_root = Path.cwd()
    _check_oak_initialized(project_root)
    _check_ci_enabled(project_root)

    db_path = project_root / OAK_DIR / "ci" / "activities.db"
    if not db_path.exists():
        print_error("No CI database found. Start the daemon first: oak ci start")
        raise typer.Exit(code=1)

    if input_path:
        backup_path = Path(input_path)
    else:
        backup_path = project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE

    if not backup_path.exists():
        print_error(f"Backup file not found: {backup_path}")
        raise typer.Exit(code=1)

    print_info(f"Restoring CI database from {backup_path}...")

    store = ActivityStore(db_path)
    count = store.import_from_sql(backup_path)
    store.close()

    print_success(f"Restored {count} records from {backup_path}")
    print_info("  ChromaDB will rebuild on next daemon startup")
    print_info("  Restart daemon to apply: oak ci restart")
