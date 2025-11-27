"""Language management commands for open-agent-kit.

Commands for managing language parsers for code intelligence.
"""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import LANGUAGE_DISPLAY_NAMES, SUPPORTED_LANGUAGES
from open_agent_kit.services.language_service import LanguageService
from open_agent_kit.utils import dir_exists, print_error, print_info

logger = logging.getLogger(__name__)

console = Console()


languages_app = typer.Typer(
    name="languages",
    help="Manage language parsers for code intelligence",
    no_args_is_help=True,
)


@languages_app.command("list")
def languages_list() -> None:
    """List all available languages and their installation status."""
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    language_service = LanguageService(project_root)
    all_languages = language_service.list_all()

    # Create table
    table = Table(title="Language Parsers")
    table.add_column("Language", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Package")

    for _lang_id, info in all_languages.items():
        status = "[green]✓ Installed[/green]" if info["installed"] else "[dim]Not installed[/dim]"
        table.add_row(
            info["display"],
            status,
            info["package"],
        )

    console.print(table)

    # Summary
    installed_count = sum(1 for info in all_languages.values() if info["installed"])
    print_info(f"\nInstalled: {installed_count}/{len(all_languages)}")


def _get_available_languages_help() -> str:
    """Build help text showing available languages."""
    langs = sorted(SUPPORTED_LANGUAGES.keys())
    return ", ".join(langs)


@languages_app.command("add")
def languages_add(
    languages: list[str] = typer.Argument(
        None, help="Languages to add (e.g., python javascript typescript)"
    ),
    all_languages: bool = typer.Option(
        False, "--all", "-a", help="Install all available language parsers"
    ),
) -> None:
    """Add language parser support for code intelligence.

    Installs tree-sitter parsers for the specified languages, enabling
    semantic code understanding in CI.

    Available languages:
        python, javascript, typescript, java, csharp, go, rust, c, cpp,
        ruby, php, kotlin, scala

    Examples:
        oak languages add python javascript typescript
        oak languages add --all
        oak languages add ruby go rust
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    # Determine languages to add
    if all_languages:
        languages_to_add = list(SUPPORTED_LANGUAGES.keys())
        print_info(f"Installing all {len(languages_to_add)} language parsers...")
    elif languages:
        languages_to_add = [lang.lower() for lang in languages]
    else:
        # No languages specified and no --all flag
        print_error("No languages specified. Use --all for all languages or specify languages:")
        print_info(f"  Available: {_get_available_languages_help()}")
        raise typer.Exit(code=1)

    # Validate languages
    invalid = [lang for lang in languages_to_add if lang not in SUPPORTED_LANGUAGES]
    if invalid:
        print_error(f"Unknown language(s): {', '.join(invalid)}")
        print_info(f"  Available: {_get_available_languages_help()}")
        raise typer.Exit(code=1)

    language_service = LanguageService(project_root)
    result = language_service.add_languages(languages_to_add)

    if not result.get("success"):
        raise typer.Exit(code=1)


@languages_app.command("remove")
def languages_remove(
    languages: list[str] = typer.Argument(
        None, help="Languages to remove (e.g., python javascript)"
    ),
    all_languages: bool = typer.Option(
        False, "--all", "-a", help="Remove all installed language parsers"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
) -> None:
    """Remove language parser support.

    Uninstalls tree-sitter parsers for the specified languages.

    Examples:
        oak languages remove ruby php
        oak languages remove --all
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    language_service = LanguageService(project_root)

    # Determine languages to remove
    if all_languages:
        installed = language_service.list_installed()
        if not installed:
            print_info("No language parsers are installed.")
            return
        languages_to_remove = installed
    elif languages:
        languages_to_remove = [lang.lower() for lang in languages]
    else:
        # No languages specified
        print_error("No languages specified. Use --all for all installed, or specify languages.")
        installed = language_service.list_installed()
        if installed:
            print_info(f"  Installed: {', '.join(installed)}")
        raise typer.Exit(code=1)

    # Validate languages
    invalid = [lang for lang in languages_to_remove if lang not in SUPPORTED_LANGUAGES]
    if invalid:
        print_error(f"Unknown language(s): {', '.join(invalid)}")
        print_info(f"  Available: {_get_available_languages_help()}")
        raise typer.Exit(code=1)

    # Confirm removal
    if not force:
        display_names = [
            LANGUAGE_DISPLAY_NAMES.get(lang, lang)
            for lang in languages_to_remove
            if lang in SUPPORTED_LANGUAGES
        ]
        if display_names:
            confirm = typer.confirm(f"Remove language parsers: {', '.join(display_names)}?")
            if not confirm:
                print_info("Cancelled.")
                return

    result = language_service.remove_languages(languages_to_remove)

    if not result.get("success"):
        raise typer.Exit(code=1)
