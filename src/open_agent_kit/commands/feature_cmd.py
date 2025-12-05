"""Feature management commands for open-agent-kit."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from open_agent_kit.config.messages import FEATURE_MESSAGES
from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import FEATURE_DISPLAY_NAMES, SUPPORTED_FEATURES
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.feature_service import FeatureService
from open_agent_kit.utils import (
    SelectOption,
    StepTracker,
    dir_exists,
    multi_select,
    print_error,
    print_header,
    print_info,
    prompt,
)

console = Console()

feature_app = typer.Typer(
    name="feature",
    help="Manage OAK features (RFC, Constitution, Issues)",
    no_args_is_help=False,  # Allow callback to run without subcommand
)


@feature_app.callback(invoke_without_command=True)
def feature_interactive(ctx: typer.Context) -> None:
    """Manage OAK features interactively.

    When invoked without a subcommand, launches interactive feature selection.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Check if OAK is initialized
    project_root = Path.cwd()
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    # Interactive feature selection
    _interactive_feature_management(project_root)


@feature_app.command("list")
def feature_list() -> None:
    """List all available features and their installation status."""
    project_root = Path.cwd()
    feature_service = FeatureService(project_root)

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    installed = set(feature_service.list_installed_features())

    # Create table
    table = Table(title="OAK Features")
    table.add_column("Feature", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Dependencies")
    table.add_column("Description")

    for feature_name in SUPPORTED_FEATURES:
        manifest = feature_service.get_feature_manifest(feature_name)
        if not manifest:
            continue

        status = (
            "[green]✓ Installed[/green]"
            if feature_name in installed
            else "[dim]Not installed[/dim]"
        )
        deps = ", ".join(manifest.dependencies) if manifest.dependencies else "-"

        table.add_row(
            manifest.display_name,
            status,
            deps,
            (
                manifest.description[:50] + "..."
                if len(manifest.description) > 50
                else manifest.description
            ),
        )

    console.print(table)


@feature_app.command("add")
def feature_add(
    name: str = typer.Argument(..., help="Feature name to add (constitution, rfc, issues)"),
) -> None:
    """Add a feature to your OAK installation.

    Dependencies will be automatically installed if needed.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    feature_service = FeatureService(project_root)
    config_service = ConfigService(project_root)

    # Validate feature name
    name_lower = name.lower()
    if name_lower not in SUPPORTED_FEATURES:
        print_error(FEATURE_MESSAGES["feature_not_found"].format(feature=name))
        print_info(f"Available features: {', '.join(SUPPORTED_FEATURES)}")
        raise typer.Exit(code=1)

    # Check if already installed
    if feature_service.is_feature_installed(name_lower):
        print_info(FEATURE_MESSAGES["feature_already_installed"].format(feature=name_lower))
        return

    # Resolve dependencies
    features_to_install = feature_service.resolve_dependencies([name_lower])
    already_installed = set(feature_service.list_installed_features())
    new_features = [f for f in features_to_install if f not in already_installed]

    if not new_features:
        print_info(FEATURE_MESSAGES["feature_already_installed"].format(feature=name_lower))
        return

    # Show dependencies being auto-added
    deps_to_add = [f for f in new_features if f != name_lower]
    if deps_to_add:
        print_info(
            FEATURE_MESSAGES["feature_deps_auto_added"].format(dependencies=", ".join(deps_to_add))
        )

    # Get agents from config
    agents = config_service.get_agents()
    if not agents:
        print_error("No agents configured. Run 'oak init' to configure agents first.")
        raise typer.Exit(code=1)

    # Install features
    tracker = StepTracker(len(new_features))

    for feature_name in new_features:
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        tracker.start_step(f"Installing {display_name}")

        try:
            results = feature_service.install_feature(feature_name, agents)
            cmd_count = len(results["commands_installed"])
            tracker.complete_step(f"Installed {display_name} ({cmd_count} commands)")
        except Exception as e:
            tracker.fail_step(f"Failed to install {display_name}", str(e))
            raise typer.Exit(code=1)

    tracker.finish(FEATURE_MESSAGES["feature_added"].format(feature=name_lower))


@feature_app.command("refresh")
def feature_refresh() -> None:
    """Refresh all features by re-rendering with current config.

    Use this after modifying agent_capabilities in .oak/config.yaml
    to apply capability changes to command templates without upgrading.

    Example workflow:
        1. Edit .oak/config.yaml to change agent_capabilities
        2. Run 'oak feature refresh' to re-render commands
        3. Commands now reflect the updated capabilities
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    feature_service = FeatureService(project_root)
    config_service = ConfigService(project_root)

    # Get current state
    installed = feature_service.list_installed_features()
    agents = config_service.get_agents()

    if not installed:
        print_info("No features installed. Nothing to refresh.")
        return

    if not agents:
        print_error("No agents configured. Run 'oak init' to configure agents first.")
        raise typer.Exit(code=1)

    # Show what will be refreshed
    print_header("Refreshing Features")
    print_info(f"Features: {', '.join(installed)}")
    print_info(f"Agents: {', '.join(agents)}\n")

    # Perform refresh
    tracker = StepTracker(len(installed))

    for feature_name in installed:
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        tracker.start_step(f"Refreshing {display_name}")

        try:
            results = feature_service.install_feature(feature_name, agents)
            cmd_count = len(results.get("commands_installed", []))
            tracker.complete_step(f"Refreshed {display_name} ({cmd_count} commands)")
        except Exception as e:
            tracker.fail_step(f"Failed to refresh {display_name}", str(e))
            raise typer.Exit(code=1)

    tracker.finish("Features refreshed with current configuration!")


@feature_app.command("remove")
def feature_remove(
    name: str = typer.Argument(..., help="Feature name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
) -> None:
    """Remove a feature from your OAK installation.

    Will warn if other features depend on this one.
    """
    project_root = Path.cwd()

    # Check if OAK is initialized
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)

    feature_service = FeatureService(project_root)
    config_service = ConfigService(project_root)

    # Validate feature name
    name_lower = name.lower()
    if name_lower not in SUPPORTED_FEATURES:
        print_error(FEATURE_MESSAGES["feature_not_found"].format(feature=name))
        raise typer.Exit(code=1)

    # Check if installed
    if not feature_service.is_feature_installed(name_lower):
        print_info(FEATURE_MESSAGES["feature_not_installed"].format(feature=name_lower))
        return

    # Check for dependents
    can_remove, blocking = feature_service.can_remove_feature(name_lower)
    if not can_remove:
        print_error(
            FEATURE_MESSAGES["feature_required_by"].format(
                feature=name_lower, dependents=", ".join(blocking)
            )
        )
        print_info(f"Remove {', '.join(blocking)} first, or remove all together.")
        raise typer.Exit(code=1)

    # Confirm removal
    if not force:
        display_name = FEATURE_DISPLAY_NAMES.get(name_lower, name_lower)
        confirm = prompt(f"Remove {display_name}? This will remove its commands. [y/N]")
        if confirm.lower() not in ("y", "yes"):
            print_info("Cancelled.")
            return

    # Ask about config removal
    remove_config = False
    if not force:
        remove_config_input = prompt("Also remove feature configuration from config.yaml? [y/N]")
        remove_config = remove_config_input.lower() in ("y", "yes")

    # Get agents from config
    agents = config_service.get_agents()

    # Remove feature
    tracker = StepTracker(1)
    display_name = FEATURE_DISPLAY_NAMES.get(name_lower, name_lower)
    tracker.start_step(f"Removing {display_name}")

    try:
        results = feature_service.remove_feature(name_lower, agents, remove_config=remove_config)
        cmd_count = len(results["commands_removed"])
        tracker.complete_step(f"Removed {display_name} ({cmd_count} commands)")
    except Exception as e:
        tracker.fail_step(f"Failed to remove {display_name}", str(e))
        raise typer.Exit(code=1)

    tracker.finish(FEATURE_MESSAGES["feature_removed"].format(feature=name_lower))


def _interactive_feature_management(project_root: Path) -> None:
    """Interactive feature selection and management.

    Args:
        project_root: Project root directory
    """
    feature_service = FeatureService(project_root)
    config_service = ConfigService(project_root)

    print_header("Manage OAK Features")
    print_info("Select which features to enable. Dependencies will be auto-selected.\n")

    installed = set(feature_service.list_installed_features())

    # Build options and dependents map for cascade deselection
    options = []
    default_selections = []
    dependents_map: dict[str, list[str]] = {}

    for feature_name in SUPPORTED_FEATURES:
        manifest = feature_service.get_feature_manifest(feature_name)
        if not manifest:
            continue

        deps_str = (
            f" (requires: {', '.join(manifest.dependencies)})" if manifest.dependencies else ""
        )

        options.append(
            SelectOption(
                value=feature_name,
                label=manifest.display_name,
                description=manifest.description + deps_str,
            )
        )

        if feature_name in installed:
            default_selections.append(feature_name)

        # Build dependents map: for each dependency, track which features depend on it
        for dep in manifest.dependencies:
            if dep not in dependents_map:
                dependents_map[dep] = []
            dependents_map[dep].append(feature_name)

    selected = multi_select(
        options,
        "Which features would you like to enable? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=0,
        dependents_map=dependents_map,
    )

    selected_set = set(selected)

    # Cascade deselection: if a dependency is removed, remove features that depend on it
    # This handles the case where user unchecks "constitution" but keeps "issues" checked
    # We need to also remove "issues" since it requires "constitution"
    cascade_removed: list[str] = []
    changed = True
    while changed:
        changed = False
        for feature_name in list(selected_set):
            deps = feature_service.get_feature_dependencies(feature_name)
            missing_deps = [d for d in deps if d not in selected_set]
            if missing_deps:
                # This feature has missing dependencies, must be removed
                selected_set.remove(feature_name)
                cascade_removed.append(feature_name)
                changed = True

    # Show cascade removals
    if cascade_removed:
        display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in cascade_removed]
        print_info(
            f"\nNote: {', '.join(display_names)} will also be removed "
            "(missing required dependencies)."
        )

    # Now resolve remaining dependencies (adds any missing deps for selected features)
    resolved = feature_service.resolve_dependencies(list(selected_set)) if selected_set else []

    # Show auto-added dependencies
    auto_added = [f for f in resolved if f not in selected_set]
    if auto_added:
        display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in auto_added]
        print_info(f"\nNote: {', '.join(display_names)} will be auto-added (required dependency).")

    # Determine changes
    to_add = [f for f in resolved if f not in installed]
    to_remove = [f for f in installed if f not in resolved]

    if not to_add and not to_remove:
        print_info("\nNo changes to features.")
        return

    # Show what will happen
    if to_add:
        print_info(f"\nFeatures to add: {', '.join(to_add)}")
    if to_remove:
        print_info(f"Features to remove: {', '.join(to_remove)}")

    # Get agents
    agents = config_service.get_agents()
    if not agents and to_add:
        print_error("No agents configured. Run 'oak init' to configure agents first.")
        raise typer.Exit(code=1)

    # Execute changes
    total_steps = len(to_add) + len(to_remove)
    tracker = StepTracker(total_steps)

    # Remove features first (in reverse dependency order)
    for feature_name in reversed(to_remove):
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        tracker.start_step(f"Removing {display_name}")
        try:
            feature_service.remove_feature(feature_name, agents)
            tracker.complete_step(f"Removed {display_name}")
        except Exception as e:
            tracker.fail_step(f"Failed to remove {display_name}", str(e))

    # Add features (in dependency order)
    for feature_name in to_add:
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        tracker.start_step(f"Installing {display_name}")
        try:
            feature_service.install_feature(feature_name, agents)
            tracker.complete_step(f"Installed {display_name}")
        except Exception as e:
            tracker.fail_step(f"Failed to install {display_name}", str(e))

    tracker.finish("Feature configuration updated!")
