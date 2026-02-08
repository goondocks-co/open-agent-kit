"""CI configuration commands: config, exclude, debug."""

from pathlib import Path

import typer

from open_agent_kit.features.codebase_intelligence.constants import (
    DAEMON_RESTART_DELAY_SECONDS,
    HTTP_TIMEOUT_QUICK,
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
    ci_app,
    console,
    get_daemon_manager,
)


@ci_app.command("config")
def ci_config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Embedding provider (ollama, lmstudio, openai)"
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
    project_flag: bool = typer.Option(
        False,
        "--project",
        help="Write all settings to project config (team-shared baseline)",
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
            with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
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
        save_ci_config(project_root, config, force_project=project_flag)
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
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

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
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

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
        manager = get_daemon_manager(project_root)
        if manager.is_running():
            print_info("Restarting daemon to apply changes...")
            manager.stop()
            import time

            time.sleep(DAEMON_RESTART_DELAY_SECONDS)
            manager.start()
            print_success("Daemon restarted with new log level")
        else:
            print_info("Daemon not running. Start with: oak ci start")
