"""Remove command for uninstalling open-agent-kit from a project."""

import shutil
from pathlib import Path

import typer

from open_agent_kit.config.paths import (
    CURSOR_SETTINGS_FILE,
    OAK_DIR,
    VSCODE_SETTINGS_FILE,
)
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_panel,
    print_warning,
)


def remove_command(
    force: bool = False,
    keep_ide_settings: bool = False,
) -> None:
    """Remove open-agent-kit managed assets from the project.

    Uses state tracking to intelligently remove only what oak created:
    - Files we created (hash matches) -> remove with confirmation
    - Files we modified (existed before) -> inform user to manually clean up
    - Directories we created -> remove if empty after file cleanup

    Preserves:
    - oak/ directory (user-generated content: constitution, RFCs, plans)
    - Files modified by user after oak created them

    Args:
        force: Skip confirmation prompt
        keep_ide_settings: Keep IDE settings files (.vscode/settings.json, etc.)
    """
    project_root = Path.cwd()
    oak_dir = project_root / OAK_DIR

    # Check if oak is initialized
    if not oak_dir.exists():
        print_error("open-agent-kit is not initialized in this project.")
        print_info("Nothing to remove.")
        raise typer.Exit(code=1)

    print_header("Remove open-agent-kit")

    state_service = StateService(project_root)
    managed_assets = state_service.get_managed_assets()

    # Categorize files for removal
    files_to_remove: list[tuple[Path, str]] = []  # (path, description)
    files_modified_by_user: list[tuple[Path, str]] = []  # (path, reason)
    files_to_inform_user: list[tuple[Path, str]] = []  # (path, marker)
    directories_to_check: list[Path] = []

    # Process created files - check if unchanged
    for created_file in managed_assets.created_files:
        file_path = project_root / created_file.path
        if file_path.exists():
            if state_service.is_file_unchanged(file_path):
                files_to_remove.append((file_path, "Created by oak (unchanged)"))
            else:
                files_modified_by_user.append((file_path, "File was modified after oak created it"))

    # Process modified files - inform user to manually clean up
    for modified_file in managed_assets.modified_files:
        file_path = project_root / modified_file.path
        if file_path.exists():
            files_to_inform_user.append((file_path, modified_file.marker))

    # Collect directories for potential cleanup
    for dir_path_str in managed_assets.directories:
        dir_path = project_root / dir_path_str
        if dir_path.exists():
            directories_to_check.append(dir_path)

    # IDE settings (unless keeping them)
    if not keep_ide_settings:
        vscode_settings = project_root / VSCODE_SETTINGS_FILE
        cursor_settings = project_root / CURSOR_SETTINGS_FILE

        if vscode_settings.exists():
            files_to_remove.append((vscode_settings, "IDE settings"))
        if cursor_settings.exists():
            files_to_remove.append((cursor_settings, "IDE settings"))

    # Check for user content
    user_content_dir = project_root / "oak"
    has_user_content = user_content_dir.exists() and any(user_content_dir.iterdir())

    # Display what will be removed
    if files_to_remove:
        print_info("\n[bold]Files to remove:[/bold]\n")
        for path, description in files_to_remove:
            relative_path = _get_relative_path(path, project_root)
            print_info(f"  [red]-[/red] {relative_path} ({description})")

    # Display files modified by user (won't remove)
    if files_modified_by_user:
        print_info("\n[yellow]Files modified by user (will NOT remove):[/yellow]\n")
        for path, reason in files_modified_by_user:
            relative_path = _get_relative_path(path, project_root)
            print_info(f"  [yellow]![/yellow] {relative_path}")
            print_info(f"      {reason}")

    # Display files user needs to manually clean up
    if files_to_inform_user:
        print_info("\n[cyan]Files with oak modifications (manual cleanup needed):[/cyan]\n")
        for path, marker in files_to_inform_user:
            relative_path = _get_relative_path(path, project_root)
            print_info(f"  [cyan]i[/cyan] {relative_path}")
            print_info(f"      Look for section: '{marker}'")

    # Always remove .oak directory
    print_info("\n[bold]Configuration to remove:[/bold]\n")
    print_info(f"  [red]-[/red] {OAK_DIR}/ (oak configuration)")

    # Show what will be preserved
    if has_user_content:
        print_info("\n[green]Preserved (user content):[/green]\n")
        print_info("  [green]+[/green] oak/ (constitution, RFCs, plans)")

    if keep_ide_settings:
        print_info("\n[cyan]Preserved (--keep-ide-settings):[/cyan]")
        if (project_root / VSCODE_SETTINGS_FILE).exists():
            print_info(f"  [cyan]+[/cyan] {VSCODE_SETTINGS_FILE}")
        if (project_root / CURSOR_SETTINGS_FILE).exists():
            print_info(f"  [cyan]+[/cyan] {CURSOR_SETTINGS_FILE}")

    # Confirm removal
    if not force:
        print_info("")
        confirm = typer.confirm("Are you sure you want to remove open-agent-kit?")
        if not confirm:
            print_info("\nRemoval cancelled.")
            raise typer.Exit(code=0)

    # Perform removal
    removed_count = 0
    failed_count = 0

    # Remove created files
    for path, _ in files_to_remove:
        try:
            if path.exists():
                path.unlink()
                removed_count += 1
        except PermissionError:
            print_warning(f"Permission denied: {path}")
            failed_count += 1
        except Exception as e:
            print_warning(f"Failed to remove {path}: {e}")
            failed_count += 1

    # Clean up empty directories (in reverse order for proper nesting)
    directories_to_check.sort(key=lambda p: len(p.parts), reverse=True)
    for dir_path in directories_to_check:
        _remove_if_empty(dir_path)

    # Clean up parent directories of removed files if empty
    _cleanup_empty_ide_directories(project_root)

    # Remove .oak directory
    try:
        if oak_dir.exists():
            shutil.rmtree(oak_dir)
            removed_count += 1
    except Exception as e:
        print_warning(f"Failed to remove {OAK_DIR}/: {e}")
        failed_count += 1

    # Final summary
    if failed_count == 0:
        _display_removal_summary(
            removed_count,
            has_user_content,
            files_modified_by_user,
            files_to_inform_user,
        )
    else:
        print_warning(f"\nRemoved {removed_count} items, {failed_count} failed.")
        raise typer.Exit(code=1)


def _get_relative_path(path: Path, project_root: Path) -> str:
    """Get relative path string from project root."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _remove_if_empty(dir_path: Path) -> bool:
    """Remove directory if empty.

    Args:
        dir_path: Directory to check and remove

    Returns:
        True if directory was removed
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return False

    # Check if directory is empty
    if not any(dir_path.iterdir()):
        try:
            dir_path.rmdir()
            return True
        except Exception:
            pass
    return False


def _cleanup_empty_ide_directories(project_root: Path) -> None:
    """Remove empty IDE directories after settings removal.

    Args:
        project_root: Project root directory
    """
    for dir_name in [".vscode", ".cursor"]:
        dir_path = project_root / dir_name
        _remove_if_empty(dir_path)


def _display_removal_summary(
    removed_count: int,
    has_user_content: bool,
    files_modified_by_user: list[tuple[Path, str]],
    files_to_inform_user: list[tuple[Path, str]],
) -> None:
    """Display summary after removal.

    Args:
        removed_count: Number of items removed
        has_user_content: Whether user content directory exists
        files_modified_by_user: Files that were modified by user (not removed)
        files_to_inform_user: Files that need manual cleanup
    """
    message_parts = [f"[bold green]Removed {removed_count} open-agent-kit asset(s)[/bold green]\n"]

    if has_user_content:
        message_parts.append(
            "\n[cyan]Your user content in oak/ has been preserved:[/cyan]\n"
            "  - Constitution and amendments\n"
            "  - RFCs and documentation\n"
            "  - Plans and research\n"
            "\nYou can safely delete the oak/ directory manually if desired."
        )

    if files_modified_by_user:
        message_parts.append(
            f"\n\n[yellow]Note:[/yellow] {len(files_modified_by_user)} file(s) were not "
            "removed because you modified them after oak created them.\n"
            "Review and delete manually if no longer needed."
        )

    if files_to_inform_user:
        message_parts.append(
            f"\n\n[cyan]Manual cleanup needed:[/cyan] {len(files_to_inform_user)} file(s) "
            "existed before oak and were modified.\n"
            "Look for the '## Project Constitution' section and remove it manually."
        )

    message_parts.append("\n\n[dim]To reinstall, run: oak init[/dim]")

    print_panel(
        "\n".join(message_parts),
        title="Removal Complete",
        style="green",
    )
