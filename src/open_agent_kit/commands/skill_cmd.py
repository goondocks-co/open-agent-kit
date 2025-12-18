"""Skill management commands for open-agent-kit."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.services.skill_service import SkillService
from open_agent_kit.utils import (
    StepTracker,
    confirm,
    dir_exists,
    print_error,
    print_header,
    print_info,
)

console = Console()

skill_app = typer.Typer(
    name="skill",
    help="Manage Claude Agent Skills",
    no_args_is_help=False,
)


@skill_app.callback(invoke_without_command=True)
def skill_interactive(ctx: typer.Context) -> None:
    """Manage Claude Agent Skills interactively.

    When invoked without a subcommand, defaults to listing skills.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Check if OAK is initialized
    project_root = Path.cwd()
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    # Default to list command
    skill_list()


@skill_app.command("list")
def skill_list() -> None:
    """List all available skills and their installation status."""
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    skill_service = SkillService(project_root)
    available = skill_service.list_available_skills()
    installed = set(skill_service.list_installed_skills())

    if not available:
        print_info("No skills available.")
        print_info("Skills will be added when you create them with 'oak skill create'")
        return

    # Create table
    table = Table(title="Claude Agent Skills")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Description")

    for manifest in available:
        status = (
            "[green]✓ Installed[/green]"
            if manifest.name in installed
            else "[dim]Not installed[/dim]"
        )
        desc = (
            manifest.description[:60] + "..."
            if len(manifest.description) > 60
            else manifest.description
        )
        table.add_row(manifest.name, status, desc)

    console.print(table)


@skill_app.command("install")
def skill_install(
    name: str = typer.Argument(..., help="Skill name to install"),
) -> None:
    """Install a Claude Agent Skill.

    Copies the skill to .oak/skills/ and .claude/skills/ directories.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    skill_service = SkillService(project_root)

    # Check if skill exists
    manifest = skill_service.get_skill_manifest(name)
    if not manifest:
        print_error(f"Skill '{name}' not found.")
        available = skill_service.list_available_skills()
        if available:
            print_info(f"Available skills: {', '.join(s.name for s in available)}")
        raise typer.Exit(code=1)

    # Check if already installed
    if skill_service.is_skill_installed(name):
        print_info(f"Skill '{name}' is already installed.")
        return

    # Install skill
    tracker = StepTracker(1)
    tracker.start_step(f"Installing {name}")

    try:
        result = skill_service.install_skill(name)
        if "error" in result:
            tracker.fail_step(f"Failed to install {name}", result["error"])
            raise typer.Exit(code=1)

        tracker.complete_step(f"Installed {name}")
        tracker.finish(f"Skill '{name}' installed successfully!")

        # Show where it was installed
        if result.get("installed_to"):
            print_info("\nInstalled to:")
            for path in result["installed_to"]:
                print_info(f"  - {path}")

    except Exception as e:
        tracker.fail_step(f"Failed to install {name}", str(e))
        raise typer.Exit(code=1)


@skill_app.command("remove")
def skill_remove(
    name: str = typer.Argument(..., help="Skill name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
) -> None:
    """Remove a Claude Agent Skill.

    Removes the skill from .oak/skills/ and .claude/skills/ directories.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    skill_service = SkillService(project_root)

    # Check if installed
    if not skill_service.is_skill_installed(name):
        print_info(f"Skill '{name}' is not installed.")
        return

    # Confirm removal
    if not force:
        if not confirm(f"Remove skill '{name}'?"):
            print_info("Cancelled.")
            return

    # Remove skill
    tracker = StepTracker(1)
    tracker.start_step(f"Removing {name}")

    try:
        result = skill_service.remove_skill(name)
        tracker.complete_step(f"Removed {name}")
        tracker.finish(f"Skill '{name}' removed successfully!")

        # Show where it was removed from
        if result.get("removed_from"):
            print_info("\nRemoved from:")
            for path in result["removed_from"]:
                print_info(f"  - {path}")

    except Exception as e:
        tracker.fail_step(f"Failed to remove {name}", str(e))
        raise typer.Exit(code=1)


@skill_app.command("refresh")
def skill_refresh() -> None:
    """Refresh all installed skills by re-copying from package.

    Use this after upgrading open-agent-kit to get the latest skill content.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    skill_service = SkillService(project_root)
    installed = skill_service.list_installed_skills()

    if not installed:
        print_info("No skills installed. Nothing to refresh.")
        return

    # Show what will be refreshed
    print_header("Refreshing Skills")
    print_info(f"Skills: {', '.join(installed)}\n")

    # Perform refresh
    tracker = StepTracker(len(installed))

    for skill_name in installed:
        tracker.start_step(f"Refreshing {skill_name}")

        try:
            skill_service.upgrade_skill(skill_name)
            tracker.complete_step(f"Refreshed {skill_name}")
        except Exception as e:
            tracker.fail_step(f"Failed to refresh {skill_name}", str(e))

    tracker.finish("Skills refreshed successfully!")


@skill_app.command("create")
def skill_create(
    name: str = typer.Argument(..., help="Name for the new skill (lowercase, hyphens)"),
    description: str = typer.Option(
        ...,
        "--description",
        "-d",
        help="Skill description (max 1024 chars)",
    ),
) -> None:
    """Create a new Claude Agent Skill scaffold.

    Generates a new skill directory with SKILL.md template.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    skill_service = SkillService(project_root)

    # Validate name using SkillManifest validator
    from open_agent_kit.models.skill import SkillManifest

    try:
        SkillManifest.validate_name(name)
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1)

    # Validate description
    if len(description) > 1024:
        print_error("Description must be 1024 characters or less.")
        raise typer.Exit(code=1)

    # Create scaffold in project .oak/skills/ directory
    tracker = StepTracker(1)
    tracker.start_step(f"Creating skill scaffold for {name}")

    try:
        output_dir = project_root / ".oak" / "skills"
        skill_path = skill_service.create_skill_scaffold(name, description, output_dir)
        tracker.complete_step("Created skill scaffold")
        tracker.finish(f"Skill '{name}' scaffold created!")

        print_info(f"\nCreated at: {skill_path}")
        print_info("\nNext steps:")
        print_info(f"1. Edit the skill content in {skill_path}")
        print_info(f"2. Install the skill: oak skill install {name}")

    except Exception as e:
        tracker.fail_step("Failed to create skill scaffold", str(e))
        raise typer.Exit(code=1)
