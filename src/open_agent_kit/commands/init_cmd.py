"""Initialize command for setting up open-agent-kit in a project."""

from pathlib import Path

import typer

from open_agent_kit.constants import (
    DEFAULT_AGENT_CONFIGS,
    ERROR_MESSAGES,
    IDE_DISPLAY_NAMES,
    INFO_MESSAGES,
    INIT_HELP_TEXT,
    NEXT_STEPS_INIT,
    OAK_DIR,
    PROJECT_URL,
    SUPPORTED_AGENTS,
    SUPPORTED_IDES,
    TEMPLATES_DIR,
    USAGE_EXAMPLES,
    VERSION,
)
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.ide_settings_service import IDESettingsService
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import (
    SelectOption,
    StepTracker,
    dir_exists,
    ensure_dir,
    ensure_gitignore_has_issue_context,
    multi_select,
    print_error,
    print_header,
    print_info,
    print_panel,
)


def init_command(
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
        help="Agent(s) to use (can specify multiple times). Options: claude, copilot, codex, cursor, gemini, windsurf, none",
    ),
    ide: list[str] = typer.Option(
        None,
        "--ide",
        help="IDE(s) to configure (can specify multiple times). Options: vscode, cursor, none",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Skip interactive prompts and use defaults",
    ),
) -> None:
    """Initialize open-agent-kit in the current project.

    Creates the .oak directory structure with templates, configuration,
    agent-specific command directories, and IDE settings.
    """
    project_root = Path.cwd()
    oak_dir = project_root / OAK_DIR

    # Detect if already initialized
    is_existing = dir_exists(oak_dir)

    # Check initialization state
    if is_existing and not force:
        # Idempotent mode: add agents to existing installation
        if agent:
            print_header("Update open-agent-kit Configuration")
            print_info(f"{INFO_MESSAGES['adding_agents']}\n")
        elif no_interactive:
            # Can't proceed without input in non-interactive mode
            examples = INIT_HELP_TEXT["examples"].format(
                init_agent=USAGE_EXAMPLES["init_agent"],
                init_multi_agent=USAGE_EXAMPLES["init_multi_agent"],
                init_force=USAGE_EXAMPLES["init_force"],
            )
            print_error(
                f"{ERROR_MESSAGES['oak_dir_exists'].format(oak_dir=oak_dir)}\n"
                f"{INIT_HELP_TEXT['no_interactive']}\n\n"
                f"{examples}"
            )
            raise typer.Exit(code=1)
        else:
            # Interactive mode: take them to agent addition flow
            print_header("Update open-agent-kit Configuration")
            print_info(f"{INFO_MESSAGES['add_more_agents']}\n")
    elif not is_existing:
        print_header("Initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['setting_up']}\n")
    else:
        # force=True
        print_header("Re-initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['force_reinit']}\n")

    config_service = ConfigService(project_root)

    # Load existing configuration if re-running init
    existing_agents: list[str] = []
    existing_ides: list[str] = []
    if is_existing:
        existing_agents = config_service.get_agents()
        existing_ides = config_service.get_ides()

    # Determine agent selection
    selected_agents: list[str] = []
    if agent:
        # Validate provided agents
        for a in agent:
            if a.lower() not in SUPPORTED_AGENTS:
                print_error(ERROR_MESSAGES["invalid_agent"].format(agent=a))
                print_info(
                    INFO_MESSAGES["supported_agents_list"].format(
                        agents=", ".join(SUPPORTED_AGENTS)
                    )
                )
                raise typer.Exit(code=1)

        # Convert to lowercase and filter out 'none'
        selected_agents = [a.lower() for a in agent if a.lower() != "none"]

        # Validate: 'none' cannot be combined with other agents
        if len(agent) != len(selected_agents) and len(selected_agents) > 0:
            print_error(ERROR_MESSAGES["none_with_others"])
            raise typer.Exit(code=1)
    elif not no_interactive:
        # Interactive mode - always show full list with pre-selection if existing
        selected_agents = _interactive_agent_selection(existing_agents if is_existing else None)

    # Determine IDE selection
    selected_ides: list[str] = []
    if ide and isinstance(ide, list) and len(ide) > 0:
        # Validate provided IDEs
        for i in ide:
            if i.lower() not in SUPPORTED_IDES:
                print_error(f"Invalid IDE: {i}")
                print_info(f"Supported IDEs: {', '.join(SUPPORTED_IDES)}")
                raise typer.Exit(code=1)

        # Convert to lowercase and filter out 'none'
        selected_ides = [i.lower() for i in ide if i.lower() != "none"]

        # Validate: 'none' cannot be combined with other IDEs
        if len(ide) != len(selected_ides) and len(selected_ides) > 0:
            print_error("Cannot specify 'none' with other IDEs")
            raise typer.Exit(code=1)
    elif not no_interactive:
        # Interactive mode - always show full list with pre-selection if existing
        selected_ides = _interactive_ide_selection(existing_ides if is_existing else None)

    # Handle idempotent mode (updating agents/IDEs in existing installation)
    if is_existing and not force:
        # Determine what changed
        agents_changed = set(selected_agents) != set(existing_agents)
        ides_changed = set(selected_ides) != set(existing_ides)

        if not agents_changed and not ides_changed:
            print_info("\nNo changes to configuration. Current setup:")
            if existing_agents:
                print_info(f"  Agents: {', '.join(existing_agents)}")
            if existing_ides:
                print_info(f"  IDEs: {', '.join(existing_ides)}")
            return

        # Determine steps needed
        steps_needed = 0
        if agents_changed:
            steps_needed += 2  # Update config + create/remove commands
        if ides_changed:
            steps_needed += 2  # Update config + install settings

        tracker = StepTracker(steps_needed)

        # Update agents if changed
        if agents_changed:
            # Determine which agents were removed
            agents_removed = set(existing_agents) - set(selected_agents)

            # Step: Update configuration with agents
            tracker.start_step("Updating agent configuration")
            try:
                config_service.update_agents(selected_agents)
                config_service.update_config(version=VERSION)  # Update version too
                # Ensure .gitignore excludes issue context.json files
                ensure_gitignore_has_issue_context(project_root)
                tracker.complete_step("Updated agent configuration")
            except Exception as e:
                tracker.fail_step("Failed to update configuration", str(e))
                raise typer.Exit(code=1)

            # Step: Update command templates
            tracker.start_step(f"Updating command templates for {len(selected_agents)} agent(s)")
            try:
                agent_service = AgentService(project_root)

                # Remove commands for removed agents
                for agent_type in agents_removed:
                    removed_count = agent_service.remove_agent_commands(agent_type)
                    if removed_count > 0:
                        print_info(f"  Removed {removed_count} command(s) for {agent_type}")

                # Create/update commands for selected agents
                for agent_type in selected_agents:
                    agent_service.create_default_commands(agent_type)

                tracker.complete_step("Updated command templates")
            except Exception as e:
                tracker.fail_step("Failed to update commands", str(e))
                # Not fatal, continue

        # Update IDEs if changed
        if ides_changed:
            # Determine which IDEs were removed
            ides_removed = set(existing_ides) - set(selected_ides)

            # Step: Update configuration with IDEs
            tracker.start_step("Updating IDE configuration")
            try:
                config_service.update_ides(selected_ides)
                config_service.update_config(version=VERSION)  # Update version too
                tracker.complete_step("Updated IDE configuration")
            except Exception as e:
                tracker.fail_step("Failed to update configuration", str(e))
                raise typer.Exit(code=1)

            # Step: Update IDE settings
            tracker.start_step(f"Updating IDE settings for {len(selected_ides)} IDE(s)")
            try:
                ide_settings_service = IDESettingsService(project_root)

                # Remove settings for removed IDEs
                for ide_type in ides_removed:
                    if ide_settings_service.remove_settings(ide_type):
                        ide_name = IDE_DISPLAY_NAMES.get(ide_type, ide_type.capitalize())
                        print_info(f"  Removed open-agent-kit settings from {ide_name}")

                # Install/update settings for selected IDEs
                installed_count = 0
                for ide_type in selected_ides:
                    if ide_settings_service.install_settings(ide_type):
                        installed_count += 1

                tracker.complete_step(f"Updated IDE settings for {installed_count} IDE(s)")
            except Exception as e:
                tracker.fail_step("Failed to update IDE settings", str(e))
                # Not fatal, continue

        tracker.finish("open-agent-kit configuration updated successfully!")
        _display_update_message(existing_agents, selected_agents, existing_ides, selected_ides)
        return

    # Full initialization flow
    tracker = StepTracker(7)

    # Step 1: Create .oak directory
    tracker.start_step("Creating .oak directory")
    try:
        ensure_dir(oak_dir)
        tracker.complete_step("Created .oak directory")
    except Exception as e:
        tracker.fail_step("Failed to create .oak directory", str(e))
        raise typer.Exit(code=1)

    # Step 2: Create subdirectories
    tracker.start_step("Creating subdirectories")
    try:
        ensure_dir(project_root / TEMPLATES_DIR / "rfc")
        # Note: oak/rfc/ directory is created on-demand when first RFC is created
        tracker.complete_step("Created subdirectories")
    except Exception as e:
        tracker.fail_step("Failed to create subdirectories", str(e))
        raise typer.Exit(code=1)

    # Step 3: Copy templates
    tracker.start_step("Copying templates")
    try:
        _copy_templates(project_root)
        tracker.complete_step("Copied templates")
    except Exception as e:
        tracker.fail_step("Failed to copy templates", str(e))
        raise typer.Exit(code=1)

    # Step 4: Create configuration
    tracker.start_step("Creating configuration")
    try:
        config_service.create_default_config(
            agents=selected_agents,
            ides=selected_ides,
        )
        # Ensure .gitignore excludes issue context.json files
        ensure_gitignore_has_issue_context(project_root)

        # Mark all current migrations as completed for new projects
        # (fresh installs start with latest code, so migrations are not needed)
        from open_agent_kit.services.migrations import get_migrations

        all_migration_ids = [migration_id for migration_id, _, _ in get_migrations()]
        if all_migration_ids:
            config_service.add_completed_migrations(all_migration_ids)

        tracker.complete_step("Created configuration")
    except Exception as e:
        tracker.fail_step("Failed to create configuration", str(e))
        raise typer.Exit(code=1)

    # Step 5: Create agent commands (if agents selected)
    if selected_agents:
        tracker.start_step(f"Creating command templates for {len(selected_agents)} agent(s)")
        try:
            agent_service = AgentService(project_root)
            for agent_type in selected_agents:
                agent_service.create_default_commands(agent_type)
            tracker.complete_step("Created command templates")
        except Exception as e:
            tracker.fail_step("Failed to create commands", str(e))
            # Not fatal, continue
    else:
        tracker.skip_step("No agents selected, skipping command creation")

    # Step 6: Install IDE settings (if IDEs selected)
    if selected_ides:
        tracker.start_step(f"Installing IDE settings for {len(selected_ides)} IDE(s)")
        try:
            ide_settings_service = IDESettingsService(project_root)
            installed_count = 0
            for ide_type in selected_ides:
                if ide_settings_service.install_settings(ide_type):
                    installed_count += 1
            if installed_count > 0:
                tracker.complete_step(f"Installed IDE settings for {installed_count} IDE(s)")
            else:
                tracker.complete_step("IDE settings already up to date")
        except Exception as e:
            tracker.fail_step("Failed to install IDE settings", str(e))
            # Not fatal, continue
    else:
        tracker.skip_step("No IDEs selected, skipping IDE settings installation")

    # Step 7: Finalize
    tracker.start_step("Finalizing setup")
    tracker.complete_step("Setup complete")

    # Display success message and next steps
    tracker.finish("open-agent-kit initialized successfully!")

    _display_next_steps(selected_agents, selected_ides)


def _interactive_agent_selection(existing_agents: list[str] | None = None) -> list[str]:
    """Interactive agent selection with checkboxes (multi-select).

    Args:
        existing_agents: List of currently configured agents (will be pre-selected)

    Returns:
        List of selected agent names (empty if "none" selected)
    """
    if existing_agents:
        print_header("Update AI Agents")
        print_info("Current agents are pre-selected. Check/uncheck to modify configuration.\n")
    else:
        print_header("Select AI Agents")
        print_info(f"{INFO_MESSAGES['select_agents_prompt']}\n")

    existing_agents = existing_agents or []

    # Normalize existing agents to lowercase for comparison
    existing_agents_lower = [a.lower() for a in existing_agents]

    options = []
    default_selections = []

    for agent_name in SUPPORTED_AGENTS:
        if agent_name == "none":
            options.append(
                SelectOption(
                    value="none",
                    label="None (Skip AI agent setup)",
                    description="Use open-agent-kit without AI assistance",
                )
            )
            # Pre-select "none" only if there are no existing agents
            if not existing_agents:
                # Don't auto-select "none", let user choose
                pass
        else:
            agent_config = DEFAULT_AGENT_CONFIGS.get(agent_name, {})
            display_name = str(agent_config.get("name", agent_name.capitalize()))
            options.append(
                SelectOption(
                    value=agent_name,
                    label=display_name,
                    description=f"Use {display_name} for AI assistance",
                )
            )
            # Pre-select if this agent is already configured
            if agent_name.lower() in existing_agents_lower:
                default_selections.append(agent_name)

    selected = multi_select(
        options,
        "Which agents would you like to use? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=0,
    )

    # Filter out 'none' - if 'none' is selected with others, remove 'none'
    if "none" in selected and len(selected) > 1:
        selected = [s for s in selected if s != "none"]
    elif "none" in selected:
        return []

    return selected


def _interactive_ide_selection(existing_ides: list[str] | None = None) -> list[str]:
    """Interactive IDE selection with checkboxes (multi-select).

    Args:
        existing_ides: List of currently configured IDEs (will be pre-selected)

    Returns:
        List of selected IDE names (empty if "none" selected)
    """
    if existing_ides:
        print_header("Update IDEs")
        print_info("Current IDEs are pre-selected. Check/uncheck to modify configuration.\n")
    else:
        print_header("Select IDEs")
        print_info("Choose which IDEs you'd like to configure with auto-approval settings.\n")

    existing_ides = existing_ides or []

    # Normalize existing IDEs to lowercase for comparison
    existing_ides_lower = [i.lower() for i in existing_ides]

    options = []
    default_selections = []

    for ide_name in SUPPORTED_IDES:
        if ide_name == "none":
            options.append(
                SelectOption(
                    value="none",
                    label="None (Skip IDE configuration)",
                    description="Don't install IDE settings",
                )
            )
            # Don't auto-select "none"
        else:
            display_name = IDE_DISPLAY_NAMES.get(ide_name, ide_name.capitalize())
            options.append(
                SelectOption(
                    value=ide_name,
                    label=display_name,
                    description=f"Configure {display_name} with auto-approval settings",
                )
            )
            # Pre-select if this IDE is already configured
            if ide_name.lower() in existing_ides_lower:
                default_selections.append(ide_name)

    selected = multi_select(
        options,
        "Which IDEs would you like to configure? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=0,
    )

    # Filter out 'none' - if 'none' is selected with others, remove 'none'
    if "none" in selected and len(selected) > 1:
        selected = [s for s in selected if s != "none"]
    elif "none" in selected:
        return []

    return selected


def _copy_templates(project_root: Path) -> None:
    """Copy default templates to project.

    Args:
        project_root: Project root directory
    """
    template_service = TemplateService(project_root=project_root)

    # Get available templates from package
    package_templates = template_service.list_templates()

    # Copy each template to project
    for template_name in package_templates:
        try:
            template_service.copy_template_to_project(template_name)
        except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError):
            # Skip if template cannot be copied (missing, permission denied, I/O error, or encoding issue)
            # This allows initialization to continue even if some templates are unavailable
            # Specific error for {template_name} - template skipped
            continue


def _display_next_steps(agents: list[str], ides: list[str]) -> None:
    """Display next steps after initialization.

    Args:
        agents: List of selected agent names
        ides: List of selected IDE names
    """
    from open_agent_kit.constants import CONFIG_FILE

    next_steps_text = NEXT_STEPS_INIT.format(
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
    )
    print_panel(
        next_steps_text,
        title="Getting Started",
        style="green",
    )

    # Display Agent Commands panel if agents were selected
    if agents:
        from open_agent_kit.constants import AGENT_CONFIG

        agent_info_lines = []
        for agent in agents:
            agent_config = AGENT_CONFIG.get(agent.lower(), {})
            folder = agent_config.get("folder", "")
            commands_subfolder = agent_config.get("commands_subfolder", "commands")
            agent_name = agent_config.get("name", agent.capitalize())
            agent_info_lines.append(f"  • [cyan]{agent_name}[/cyan]: {folder}{commands_subfolder}/")

        agent_list = "\n".join(agent_info_lines)

        print_panel(
            f"[bold green]Agent Commands Installed[/bold green]\n\n"
            f"Commands have been installed for {len(agents)} agent(s):\n\n"
            f"{agent_list}\n\n"
            f"All commands start with [cyan]/oak.[/cyan] in your AI assistant.\n"
            f"Examples: [dim]/oak.rfc-create, /oak.constitution-create[/dim]\n\n"
            f"Type [cyan]/oak[/cyan] in your AI assistant to discover available commands!",
            title="Ready to Use",
            style="green",
        )

    # Display IDE Settings panel if IDEs were selected
    if ides:
        ide_info_lines = []
        for ide in ides:
            ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
            settings_file = f".{ide}/settings.json"
            ide_info_lines.append(f"  • [cyan]{ide_name}[/cyan]: {settings_file}")

        ide_list = "\n".join(ide_info_lines)

        print_panel(
            f"[bold green]IDE Settings Configured[/bold green]\n\n"
            f"Auto-approval settings have been installed for {len(ides)} IDE(s):\n\n"
            f"{ide_list}\n\n"
            f"Your IDE will now auto-approve [cyan]oak[/cyan] commands.\n"
            f"Prompt files are also recommended automatically in chat!",
            title="Ready to Use",
            style="green",
        )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _display_additions_message(agents: list[str], ides: list[str]) -> None:
    """Display message after adding agents/IDEs to existing installation.

    Args:
        agents: List of agent names that were added
        ides: List of IDE names that were added
    """
    if not agents and not ides:
        print_info(f"\n{INFO_MESSAGES['no_agents_added']}")
        print_info("No IDEs added either.")
        return

    from open_agent_kit.constants import AGENT_CONFIG

    message_parts = ["[bold green]Configuration Updated Successfully[/bold green]\n"]

    # Add agents info if any
    if agents:
        agent_info_lines = []
        for agent in agents:
            agent_config = AGENT_CONFIG.get(agent.lower(), {})
            folder = agent_config.get("folder", "")
            commands_subfolder = agent_config.get("commands_subfolder", "commands")
            agent_name = agent_config.get("name", agent.capitalize())
            agent_info_lines.append(f"  • [cyan]{agent_name}[/cyan]: {folder}{commands_subfolder}/")

        agent_list = "\n".join(agent_info_lines)
        message_parts.append(
            f"\n**Agents Added ({len(agents)}):**\n{agent_list}\n"
            f"You can now use open-agent-kit commands in these AI assistants!"
        )

    # Add IDEs info if any
    if ides:
        ide_info_lines = []
        for ide in ides:
            ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
            settings_file = f".{ide}/settings.json"
            ide_info_lines.append(f"  • [cyan]{ide_name}[/cyan]: {settings_file}")

        ide_list = "\n".join(ide_info_lines)
        message_parts.append(
            f"\n**IDEs Configured ({len(ides)}):**\n{ide_list}\n"
            f"Auto-approval settings have been installed!"
        )

    print_panel(
        "\n".join(message_parts),
        title="Update Complete",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _display_update_message(
    old_agents: list[str],
    new_agents: list[str],
    old_ides: list[str],
    new_ides: list[str],
) -> None:
    """Display message showing what changed in configuration.

    Args:
        old_agents: Previously configured agents
        new_agents: Newly configured agents
        old_ides: Previously configured IDEs
        new_ides: Newly configured IDEs
    """
    from open_agent_kit.constants import AGENT_CONFIG

    message_parts = ["[bold green]Configuration Updated Successfully[/bold green]\n"]

    # Show agent changes
    old_agents_set = set(old_agents)
    new_agents_set = set(new_agents)
    agents_added = new_agents_set - old_agents_set
    agents_removed = old_agents_set - new_agents_set
    agents_kept = old_agents_set & new_agents_set

    if agents_added or agents_removed or agents_kept:
        agent_lines = []

        if agents_kept:
            agent_lines.append("[dim]Keeping:[/dim]")
            for agent in sorted(agents_kept):
                agent_config = AGENT_CONFIG.get(agent.lower(), {})
                agent_name = agent_config.get("name", agent.capitalize())
                agent_lines.append(f"  • [cyan]{agent_name}[/cyan]")

        if agents_added:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[green]Added:[/green]")
            for agent in sorted(agents_added):
                agent_config = AGENT_CONFIG.get(agent.lower(), {})
                agent_name = agent_config.get("name", agent.capitalize())
                agent_lines.append(f"  • [green]{agent_name}[/green]")

        if agents_removed:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[red]Removed:[/red]")
            for agent in sorted(agents_removed):
                agent_config = AGENT_CONFIG.get(agent.lower(), {})
                agent_name = agent_config.get("name", agent.capitalize())
                agent_lines.append(f"  • [red]{agent_name}[/red]")

        message_parts.append("\n**Agent Configuration:**\n" + "\n".join(agent_lines))

    # Show IDE changes
    old_ides_set = set(old_ides)
    new_ides_set = set(new_ides)
    ides_added = new_ides_set - old_ides_set
    ides_removed = old_ides_set - new_ides_set
    ides_kept = old_ides_set & new_ides_set

    if ides_added or ides_removed or ides_kept:
        ide_lines = []

        if ides_kept:
            ide_lines.append("[dim]Keeping:[/dim]")
            for ide in sorted(ides_kept):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [cyan]{ide_name}[/cyan]")

        if ides_added:
            if ide_lines:
                ide_lines.append("")
            ide_lines.append("[green]Added:[/green]")
            for ide in sorted(ides_added):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [green]{ide_name}[/green]")

        if ides_removed:
            if ide_lines:
                ide_lines.append("")
            ide_lines.append("[red]Removed:[/red]")
            for ide in sorted(ides_removed):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [red]{ide_name}[/red]")

        message_parts.append("\n**IDE Configuration:**\n" + "\n".join(ide_lines))

    print_panel(
        "\n".join(message_parts),
        title="Update Complete",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _display_agent_added_message(agents: list[str]) -> None:
    """Display message after adding agents to existing installation.

    DEPRECATED: Use _display_additions_message instead.

    Args:
        agents: List of agent names that were added
    """
    _display_additions_message(agents, [])
