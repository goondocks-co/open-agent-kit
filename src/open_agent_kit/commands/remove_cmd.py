"""Remove command for uninstalling open-agent-kit from a project."""

from pathlib import Path

import typer

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.executor import build_remove_pipeline
from open_agent_kit.services.skill_service import SkillService
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    StepTracker,
    print_error,
    print_header,
    print_info,
    print_panel,
)


def remove_command(force: bool = False) -> None:
    """Remove open-agent-kit managed assets from the project.

    Uses state tracking to intelligently remove only what oak created:
    - Files we created (hash matches) -> remove with confirmation
    - Files we modified (existed before) -> inform user to manually clean up
    - Directories we created -> remove if empty after file cleanup

    Preserves:
    - oak/ directory (user-generated content: constitution, RFCs, plans)
    - Files modified by user after oak created them

    Args:
        force: Skip confirmation prompt and bypass initialization check
    """
    project_root = Path.cwd()
    oak_dir = project_root / OAK_DIR
    is_initialized = oak_dir.exists()

    # Check if oak is initialized (unless force mode)
    if not is_initialized and not force:
        print_error("open-agent-kit is not initialized in this project.")
        print_info("Nothing to remove.")
        print_info("\nUse --force to clean up orphaned settings files.")
        raise typer.Exit(code=1)

    if is_initialized:
        print_header("Remove open-agent-kit")
    else:
        print_header("Cleanup Orphaned Settings")

    # Gather information for preview (before pipeline runs)
    preview_data = _gather_preview_data(project_root, cleanup_only=not is_initialized)

    # Display preview of what will be removed
    _display_removal_preview(preview_data, project_root, cleanup_only=not is_initialized)

    # Confirm removal
    if not force:
        print_info("")
        confirm = typer.confirm("Are you sure you want to remove open-agent-kit?")
        if not confirm:
            print_info("\nRemoval cancelled.")
            raise typer.Exit(code=0)

    # Build pipeline context
    context = PipelineContext(
        project_root=project_root,
        flow_type=FlowType.REMOVE,
        options={"cleanup_only": not is_initialized},
    )

    # Build and execute pipeline
    pipeline = build_remove_pipeline().build()
    step_count = pipeline.get_stage_count(context)
    tracker = StepTracker(step_count)

    print_info("")  # Blank line before execution

    result = pipeline.execute(context, tracker)

    # Display results
    if result.success:
        _display_removal_summary(context, preview_data)
    else:
        for stage_name, error in result.stages_failed:
            print_error(f"Stage '{stage_name}' failed: {error}")
        raise typer.Exit(code=1)


def _gather_preview_data(project_root: Path, cleanup_only: bool = False) -> dict:
    """Gather data needed for preview display.

    Args:
        project_root: Project root directory
        cleanup_only: If True, only gather settings cleanup data

    Returns:
        Dictionary with preview data
    """
    from open_agent_kit.services.agent_service import AgentService
    from open_agent_kit.services.agent_settings_service import AgentSettingsService

    # Categorize files
    files_to_remove: list[tuple[str, str]] = []
    files_modified_by_user: list[tuple[str, str]] = []
    files_to_inform_user: list[tuple[str, str]] = []
    settings_to_clean: list[tuple[str, str]] = []

    # Only gather full state data if not in cleanup_only mode
    if not cleanup_only:
        state_service = StateService(project_root)
        managed_assets = state_service.get_managed_assets()

        # Process created files
        for created_file in managed_assets.created_files:
            file_path = project_root / created_file.path
            if file_path.exists():
                if state_service.is_file_unchanged(file_path):
                    files_to_remove.append((created_file.path, "Created by oak (unchanged)"))
                else:
                    files_modified_by_user.append(
                        (created_file.path, "File was modified after oak created it")
                    )

        # Process modified files
        for modified_file in managed_assets.modified_files:
            file_path = project_root / modified_file.path
            if file_path.exists():
                files_to_inform_user.append((modified_file.path, modified_file.marker))

    # Gather settings files that may need cleanup
    agent_service = AgentService(project_root)
    settings_service = AgentSettingsService(project_root)
    try:
        available_agents = agent_service.list_available_agents()
        for agent in available_agents:
            settings_path = settings_service.get_settings_path(agent)
            if settings_path and settings_path.exists():
                rel_path = (
                    str(settings_path.relative_to(project_root))
                    if settings_path.is_relative_to(project_root)
                    else str(settings_path)
                )
                settings_to_clean.append((rel_path, agent))
    except Exception:
        pass

    # User content
    user_content_dir = project_root / "oak"
    has_user_content = user_content_dir.exists() and any(user_content_dir.iterdir())

    # Installed skills
    installed_skills: list[str] = []
    if not cleanup_only:
        try:
            skill_service = SkillService(project_root)
            installed_skills = skill_service.list_installed_skills()
        except Exception:
            pass

    return {
        "files_to_remove": files_to_remove,
        "files_modified_by_user": files_modified_by_user,
        "files_to_inform_user": files_to_inform_user,
        "settings_to_clean": settings_to_clean,
        "installed_skills": installed_skills,
        "has_user_content": has_user_content,
        "cleanup_only": cleanup_only,
    }


def _display_removal_preview(
    preview_data: dict, project_root: Path, cleanup_only: bool = False
) -> None:
    """Display preview of what will be removed.

    Args:
        preview_data: Data gathered for preview
        project_root: Project root directory
        cleanup_only: If True, only show settings cleanup preview
    """
    files_to_remove = preview_data["files_to_remove"]
    files_modified_by_user = preview_data["files_modified_by_user"]
    files_to_inform_user = preview_data["files_to_inform_user"]
    settings_to_clean = preview_data.get("settings_to_clean", [])
    installed_skills = preview_data["installed_skills"]
    has_user_content = preview_data["has_user_content"]

    if cleanup_only:
        # Only show settings cleanup preview
        if settings_to_clean:
            print_info("\n[bold]Settings files to clean:[/bold]\n")
            for path, agent in settings_to_clean:
                print_info(f"  [cyan]•[/cyan] {path} ({agent})")
        else:
            print_info("\nNo orphaned settings files found.")
        return

    # Full removal preview
    # Display files to remove
    if files_to_remove:
        print_info("\n[bold]Files to remove:[/bold]\n")
        for path, description in files_to_remove:
            print_info(f"  [red]-[/red] {path} ({description})")

    # Display files modified by user (won't remove)
    if files_modified_by_user:
        print_info("\n[yellow]Files modified by user (will NOT remove):[/yellow]\n")
        for path, reason in files_modified_by_user:
            print_info(f"  [yellow]![/yellow] {path}")
            print_info(f"      {reason}")

    # Display files user needs to manually clean up
    if files_to_inform_user:
        print_info("\n[cyan]Files with oak modifications (manual cleanup needed):[/cyan]\n")
        for path, marker in files_to_inform_user:
            print_info(f"  [cyan]i[/cyan] {path}")
            print_info(f"      Look for section: '{marker}'")

    # Settings files to clean
    if settings_to_clean:
        print_info("\n[bold]Agent settings to clean:[/bold]\n")
        for path, agent in settings_to_clean:
            print_info(f"  [cyan]•[/cyan] {path} ({agent})")

    # Always remove .oak directory
    print_info("\n[bold]Configuration to remove:[/bold]\n")
    print_info(f"  [red]-[/red] {OAK_DIR}/ (oak configuration)")

    # Display installed skills that will be removed
    if installed_skills:
        print_info("\n[bold]Skills to remove:[/bold]\n")
        for skill_name in installed_skills:
            print_info(f"  [red]-[/red] {skill_name}")

    # Show what will be preserved
    if has_user_content:
        print_info("\n[green]Preserved (user content):[/green]\n")
        print_info("  [green]+[/green] oak/ (constitution, RFCs, plans)")


def _display_removal_summary(context: PipelineContext, preview_data: dict) -> None:
    """Display summary after removal.

    Args:
        context: Pipeline context with results
        preview_data: Original preview data
    """
    files_modified_by_user = preview_data["files_modified_by_user"]
    files_to_inform_user = preview_data["files_to_inform_user"]
    has_user_content = preview_data["has_user_content"]

    # Gather counts from stage results
    files_result = context.get_result("remove_created_files", {})
    files_removed = files_result.get("removed_count", 0)

    skills_result = context.get_result("remove_skills", {})
    skills_removed = skills_result.get("skills_removed", 0)

    oak_result = context.get_result("remove_oak_dir", {})
    oak_removed = 1 if oak_result.get("removed") else 0

    total_removed = files_removed + skills_removed + oak_removed

    message_parts = [f"[bold green]Removed {total_removed} open-agent-kit asset(s)[/bold green]\n"]

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
