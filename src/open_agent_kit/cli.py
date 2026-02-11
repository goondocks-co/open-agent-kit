"""Main CLI entry point for open-agent-kit."""

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from open_agent_kit.commands.ci_cmd import ci_app
from open_agent_kit.commands.init_cmd import init_command
from open_agent_kit.commands.languages_cmd import languages_app
from open_agent_kit.commands.remove_cmd import remove_command
from open_agent_kit.commands.rfc_cmd import rfc_app
from open_agent_kit.commands.rules_cmd import rules_app
from open_agent_kit.commands.skill_cmd import skill_app
from open_agent_kit.commands.upgrade_cmd import upgrade_command
from open_agent_kit.config.messages import HELP_TEXT, PROJECT_TAGLINE, PROJECT_URL
from open_agent_kit.constants import VERSION
from open_agent_kit.utils import print_banner, print_error, print_panel

# Load .env file from current directory if it exists
load_dotenv(Path.cwd() / ".env", verbose=False)

# Create main Typer app
app = typer.Typer(
    name="oak",
    help=PROJECT_TAGLINE,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

# Add command groups
app.add_typer(rules_app, name="rules")
app.add_typer(rfc_app, name="rfc")
app.add_typer(languages_app, name="languages")
app.add_typer(skill_app, name="skill")
app.add_typer(ci_app, name="ci")

# Create console for output
console = Console()


@app.command("init")
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-initialization even if .oak directory exists",
    ),
    agent: list[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Agent(s) to use (can specify multiple times). Options: claude, copilot, codex, cursor, gemini, windsurf",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Skip interactive prompts and use defaults",
    ),
) -> None:
    """Initialize open-agent-kit in the current project.

    Creates the .oak directory structure with templates, configuration,
    and agent-specific command directories.
    """
    init_command(
        force=force,
        agent=agent,
        no_interactive=no_interactive,
    )


@app.command("upgrade")
def upgrade(
    commands: bool = typer.Option(
        False,
        "--commands",
        "-c",
        help="Upgrade only agent command templates",
    ),
    templates: bool = typer.Option(
        False,
        "--templates",
        "-t",
        help="Upgrade only RFC templates",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Preview changes without applying them",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts",
    ),
) -> None:
    """Upgrade open-agent-kit templates and agent commands.

    Upgrades agent command templates and command helper templates to the latest versions.
    Agent commands are always safe to upgrade. command helper templates will warn if customized.
    """
    upgrade_command(
        commands=commands,
        templates=templates,
        dry_run=dry_run,
        force=force,
    )


@app.command("remove")
def remove(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation and bypass initialization check (for orphaned cleanup)",
    ),
) -> None:
    """Remove open-agent-kit from the current project.

    Removes all oak-managed assets including configuration, agent directories,
    and agent instruction files. User content in the oak/ directory (constitution,
    RFCs, plans) is preserved.

    Use --force to clean up orphaned settings files when oak is not initialized.
    """
    remove_command(force=force)


@app.command("version")
def version() -> None:
    """Show version information."""
    print_panel(
        f"[bold cyan]open-agent-kit[/bold cyan] version [green]{VERSION}[/green]\n\n"
        f"{PROJECT_TAGLINE}\n\n"
        f"[dim]{PROJECT_URL}[/dim]",
        title="Version",
        style="cyan",
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version_flag: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version information",
        is_eager=True,
    ),
    help_flag: bool | None = typer.Option(
        None,
        "--help",
        "-h",
        help="Show this help message",
        is_eager=True,
    ),
) -> None:
    """open-agent-kit - AI-powered development workflows.

    A CLI tool for managing RFCs, project workflows, and team conventions
    with AI assistance from Claude, Copilot, Codex, or Cursor.

    Get started:
        oak init              # Initialize project
        oak rfc create "..."  # Create an RFC
        oak rfc list          # List all RFCs

    For more information, visit: https://oak.goondocks.co
    """
    _stamp_cli_version()
    _check_daemon_version_hint()

    # Handle version flag
    if version_flag:
        version()
        raise typer.Exit()

    # Handle help flag or no command
    if help_flag or ctx.invoked_subcommand is None:
        # Show banner and help
        print_banner()
        console.print(HELP_TEXT)
        raise typer.Exit()


def _stamp_cli_version() -> None:
    """Write current CLI version to .oak/ci/cli_version for daemon version detection."""
    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_CLI_VERSION_FILE,
        CI_DATA_DIR,
    )

    stamp = Path.cwd() / OAK_DIR / CI_DATA_DIR / CI_CLI_VERSION_FILE
    if stamp.parent.is_dir():
        try:
            if not stamp.exists() or stamp.read_text().strip() != VERSION:
                stamp.write_text(VERSION)
        except OSError:
            pass


def _check_daemon_version_hint() -> None:
    """Print a hint if the running daemon version differs from the installed CLI."""
    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_CLI_HINT_TIMEOUT,
        CI_CLI_HINT_VERSION_MISMATCH,
        CI_DATA_DIR,
        CI_PID_FILE,
    )

    pid_file = Path.cwd() / OAK_DIR / CI_DATA_DIR / CI_PID_FILE
    if not pid_file.exists():
        return

    try:
        import httpx

        from open_agent_kit.features.codebase_intelligence.cli_command import (
            resolve_ci_cli_command,
        )
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            get_project_port,
        )

        project_root = Path.cwd()
        ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        port = get_project_port(project_root, ci_data_dir)
        resp = httpx.get(
            f"http://127.0.0.1:{port}/api/health",
            timeout=CI_CLI_HINT_TIMEOUT,
        )
        data = resp.json()
        running_version = data.get("oak_version")
        if running_version and running_version != VERSION:
            cli_command = resolve_ci_cli_command(project_root)
            console.print(
                f"[yellow]{CI_CLI_HINT_VERSION_MISMATCH.format(running=running_version, installed=VERSION, cli_command=cli_command)}[/yellow]"
            )
    except Exception:
        pass


def cli_main() -> None:
    """Main entry point for the CLI.

    This is the function that gets called when running 'oak' command.
    It handles exceptions and provides user-friendly error messages.
    """
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        # Check if it's a typer.Exit with code
        if isinstance(e, typer.Exit):
            sys.exit(e.exit_code)

        # Handle other exceptions
        from open_agent_kit.config.messages import ERROR_MESSAGES

        print_error(ERROR_MESSAGES["generic_error"].format(error=str(e)))

        # Show traceback in debug mode
        if "--debug" in sys.argv or "-d" in sys.argv:
            import traceback

            console.print("\n[dim]Traceback:[/dim]")
            traceback.print_exc()

        sys.exit(1)


# For backwards compatibility and testing
if __name__ == "__main__":
    cli_main()
