"""Initialize command for setting up open-agent-kit in a project."""

from pathlib import Path

import typer

from open_agent_kit.config.messages import (
    ERROR_MESSAGES,
    INFO_MESSAGES,
    INIT_HELP_TEXT,
    NEXT_STEPS_INIT,
    PROJECT_URL,
    USAGE_EXAMPLES,
)
from open_agent_kit.config.paths import CONFIG_FILE, OAK_DIR, TEMPLATES_DIR
from open_agent_kit.constants import (
    DEFAULT_LANGUAGES,
    LANGUAGE_DISPLAY_NAMES,
    SUPPORTED_LANGUAGES,
)
from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState
from open_agent_kit.pipeline.executor import build_init_pipeline
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import (
    SelectOption,
    StepTracker,
    dir_exists,
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
        help="Agent(s) to use (can specify multiple times). Options: claude, copilot, codex, cursor, gemini, windsurf",
    ),
    language: list[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Language(s) for code intelligence (can specify multiple times). Options: python, javascript, typescript, java, csharp, go, rust, c, cpp, ruby, php, kotlin, scala",
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
    has_config = (project_root / CONFIG_FILE).is_file()

    # Determine flow type
    if force:
        flow_type = FlowType.FORCE_REINIT
    elif is_existing and has_config:
        flow_type = FlowType.UPDATE
    elif is_existing and not has_config:
        # .oak dir exists but config is missing (corrupted state) — repair via re-init
        flow_type = FlowType.FORCE_REINIT
    else:
        flow_type = FlowType.FRESH_INIT

    # Display appropriate header based on flow type
    if flow_type == FlowType.UPDATE:
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
            print_header("Update open-agent-kit Configuration")
            print_info(f"{INFO_MESSAGES['add_more_agents']}\n")
    elif flow_type == FlowType.FRESH_INIT:
        print_header("Initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['setting_up']}\n")
    else:  # FORCE_REINIT
        print_header("Re-initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['force_reinit']}\n")

    # Load existing configuration if applicable
    config_service = ConfigService(project_root)
    existing_agents: list[str] = []
    existing_languages: list[str] = []

    if is_existing and has_config:
        existing_agents = config_service.get_agents()
        config = config_service.load_config()
        existing_languages = config.languages.installed

    # Gather selections (CLI args or interactive)
    selected_agents = _gather_agent_selection(
        agent, no_interactive, existing_agents if is_existing else None
    )
    selected_languages = _gather_language_selection(
        language, no_interactive, is_existing, existing_languages
    )

    # Check for no changes in update flow
    if flow_type == FlowType.UPDATE:
        agents_changed = set(selected_agents) != set(existing_agents)
        languages_changed = set(selected_languages) != set(existing_languages)

        if not agents_changed and not languages_changed:
            print_info("\nNo changes to configuration. Current setup:")
            if existing_agents:
                print_info(f"  Agents: {', '.join(existing_agents)}")
            if existing_languages:
                display_names = [
                    LANGUAGE_DISPLAY_NAMES.get(lang, lang) for lang in existing_languages
                ]
                print_info(f"  Languages: {', '.join(display_names)}")
            return

    # Build pipeline context
    context = PipelineContext(
        project_root=project_root,
        flow_type=flow_type,
        force=force,
        interactive=not no_interactive,
        selections=SelectionState(
            agents=selected_agents,
            languages=selected_languages,
            previous_agents=existing_agents,
            previous_languages=existing_languages,
        ),
    )

    # Build and execute pipeline
    pipeline = build_init_pipeline().build()
    step_count = pipeline.get_stage_count(context)
    tracker = StepTracker(step_count)

    result = pipeline.execute(context, tracker)

    # Handle result
    if result.success:
        if flow_type == FlowType.UPDATE:
            tracker.finish("open-agent-kit configuration updated successfully!")
            _display_update_message(
                existing_agents,
                selected_agents,
                existing_languages,
                selected_languages,
            )
        else:
            tracker.finish("open-agent-kit initialized successfully!")
            _display_next_steps(selected_agents, selected_languages)

        # Display any hook information
        _display_hook_results(context)
    else:
        # Pipeline failed on critical stage
        for stage_name, error in result.stages_failed:
            print_error(f"Stage '{stage_name}' failed: {error}")
        raise typer.Exit(code=1)


def _gather_agent_selection(
    agent: list[str] | None,
    no_interactive: bool,
    existing_agents: list[str] | None,
) -> list[str]:
    """Gather agent selection from CLI args or interactive prompt.

    Args:
        agent: CLI-provided agents
        no_interactive: Whether to skip interactive prompts
        existing_agents: Previously configured agents (for pre-selection)

    Returns:
        List of selected agent names
    """
    if agent:
        # Validate provided agents using manifests
        agent_service = AgentService()
        available_agents = agent_service.list_available_agents()

        for a in agent:
            if a.lower() not in available_agents:
                print_error(ERROR_MESSAGES["invalid_agent"].format(agent=a))
                print_info(
                    INFO_MESSAGES["supported_agents_list"].format(
                        agents=", ".join(sorted(available_agents))
                    )
                )
                raise typer.Exit(code=1)

        return [a.lower() for a in agent]
    elif not no_interactive:
        return _interactive_agent_selection(existing_agents)
    else:
        return []


def _gather_language_selection(
    language: list[str] | None,
    no_interactive: bool,
    is_existing: bool,
    existing_languages: list[str],
) -> list[str]:
    """Gather language selection from CLI args or interactive prompt.

    Args:
        language: CLI-provided languages
        no_interactive: Whether to skip interactive prompts
        is_existing: Whether this is an existing installation
        existing_languages: Previously installed languages

    Returns:
        List of selected language names
    """
    if language and isinstance(language, list) and len(language) > 0:
        # Validate provided languages
        for lang in language:
            if lang.lower() not in SUPPORTED_LANGUAGES:
                print_error(f"Invalid language: {lang}")
                print_info(f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}")
                raise typer.Exit(code=1)

        return [lang.lower() for lang in language]
    elif not no_interactive:
        return _interactive_language_selection(existing_languages if is_existing else None)
    else:
        # Non-interactive mode - use defaults for new installs, preserve existing for updates
        if is_existing:
            return existing_languages
        else:
            return list(DEFAULT_LANGUAGES)


def _display_hook_results(context: PipelineContext) -> None:
    """Display useful information from hook stage results.

    Args:
        context: Pipeline context with stage results
    """
    # Check for agent hook results
    hook_result = context.get_result("trigger_agents_changed")
    if hook_result:
        hook_info = hook_result.get("hook_info", [])
        for info in hook_info:
            print_info(f"  {info}")


def _interactive_agent_selection(existing_agents: list[str] | None = None) -> list[str]:
    """Interactive agent selection with checkboxes (multi-select).

    Args:
        existing_agents: List of currently configured agents (will be pre-selected)

    Returns:
        List of selected agent names
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

    # Use AgentService to get available agents and their display names
    agent_service = AgentService()
    available_agents = agent_service.list_available_agents()

    # Add available agents from manifests
    for agent_name in available_agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
            display_name = manifest.display_name
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
        except ValueError:
            continue

    # Safety check - if no agents found, show helpful error
    if not options:
        print_error("No agent manifests found. This may indicate a corrupted installation.")
        print_info(f"Expected agents directory: {agent_service.package_agents_dir}")
        print_info(f"Available agents detected: {available_agents}")
        raise typer.Exit(code=1)

    selected = multi_select(
        options,
        "Which agents would you like to use? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=1,  # At least one agent is required
    )

    return selected


def _interactive_language_selection(existing_languages: list[str] | None = None) -> list[str]:
    """Interactive language selection with checkboxes.

    Args:
        existing_languages: List of currently installed languages (will be pre-selected)

    Returns:
        List of selected language names
    """
    if existing_languages:
        print_header("Update Languages")
        print_info("Current languages are pre-selected. Check/uncheck to modify.\n")
    else:
        print_header("Select Languages")
        print_info("Choose languages for code intelligence. Parsers will be installed.\n")

    existing_languages = existing_languages or []
    existing_languages_lower = [lang.lower() for lang in existing_languages]

    options = []
    default_selections = []

    for lang_id, info in SUPPORTED_LANGUAGES.items():
        options.append(
            SelectOption(
                value=lang_id,
                label=info["display"],
                description=f"Parser: {info['package']}",
            )
        )

        # Pre-select if already installed or if it's default for new installs
        if lang_id.lower() in existing_languages_lower:
            default_selections.append(lang_id)
        elif not existing_languages and lang_id in DEFAULT_LANGUAGES:
            default_selections.append(lang_id)

    selected = multi_select(
        options,
        "Which languages would you like to enable? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=0,
    )

    return selected


def _display_next_steps(agents: list[str], languages: list[str] | None = None) -> None:
    """Display next steps after initialization.

    Args:
        agents: List of selected agent names
        languages: List of selected language names
    """
    from open_agent_kit.config.paths import CONFIG_FILE

    next_steps_text = NEXT_STEPS_INIT.format(
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
    )
    print_panel(
        next_steps_text,
        title="Getting Started",
        style="green",
    )

    # Display Agent Configuration panel if agents were selected
    if agents:
        agent_service = AgentService()
        skills_agents = []
        command_agents = []

        for agent in agents:
            try:
                manifest = agent_service.get_agent_manifest(agent.lower())
                display_name = manifest.display_name

                if manifest.capabilities.has_skills:
                    # Skills-capable agent - show skills directory
                    skills_base = (
                        manifest.capabilities.skills_folder or manifest.installation.folder
                    )
                    skills_base = skills_base.rstrip("/")
                    skills_dir = manifest.capabilities.skills_directory
                    skills_agents.append(
                        f"  • [cyan]{display_name}[/cyan]: {skills_base}/{skills_dir}/"
                    )
                else:
                    # Command-only agent - show commands directory
                    folder = manifest.installation.folder
                    commands_subfolder = manifest.installation.commands_subfolder
                    command_agents.append(
                        f"  • [cyan]{display_name}[/cyan]: {folder}{commands_subfolder}/"
                    )
            except ValueError:
                command_agents.append(f"  • [cyan]{agent.capitalize()}[/cyan]")

        # Build the panel content
        panel_parts = ["[bold green]OAK Configured[/bold green]\n"]

        if skills_agents:
            panel_parts.append(
                f"[bold]Skills installed ({len(skills_agents)}):[/bold]\n"
                + "\n".join(skills_agents)
            )
            panel_parts.append("\nSkills are auto-discovered by your AI assistant.")

        if command_agents:
            panel_parts.append(
                f"\n[bold]Commands installed ({len(command_agents)}):[/bold]\n"
                + "\n".join(command_agents)
            )
            panel_parts.append(
                "\nType [cyan]/oak[/cyan] in your AI assistant to see available commands."
            )

        # Show languages
        if languages:
            display_names = [LANGUAGE_DISPLAY_NAMES.get(lang, lang) for lang in languages]
            panel_parts.append(
                f"\n[bold]Languages ({len(languages)}):[/bold]\n  {', '.join(display_names)}"
            )

        print_panel(
            "\n".join(panel_parts),
            title="Ready to Use",
            style="green",
        )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _get_agent_display_name(agent_service: AgentService, agent: str) -> str:
    """Get display name for an agent from manifest.

    Args:
        agent_service: AgentService instance
        agent: Agent name

    Returns:
        Display name (falls back to capitalized name if manifest not found)
    """
    try:
        manifest = agent_service.get_agent_manifest(agent.lower())
        return manifest.display_name
    except ValueError:
        return agent.capitalize()


def _display_update_message(
    old_agents: list[str],
    new_agents: list[str],
    old_languages: list[str] | None = None,
    new_languages: list[str] | None = None,
) -> None:
    """Display message showing what changed in configuration.

    Args:
        old_agents: Previously configured agents
        new_agents: Newly configured agents
        old_languages: Previously installed languages
        new_languages: Newly installed languages
    """
    agent_service = AgentService()
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
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [cyan]{agent_name}[/cyan]")

        if agents_added:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[green]Added:[/green]")
            for agent in sorted(agents_added):
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [green]{agent_name}[/green]")

        if agents_removed:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[red]Removed:[/red]")
            for agent in sorted(agents_removed):
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [red]{agent_name}[/red]")

        message_parts.append("\n**Agent Configuration:**\n" + "\n".join(agent_lines))

    # Show language changes
    old_languages_set = set(old_languages or [])
    new_languages_set = set(new_languages or [])
    languages_added = new_languages_set - old_languages_set
    languages_removed = old_languages_set - new_languages_set
    languages_kept = old_languages_set & new_languages_set

    if languages_added or languages_removed or languages_kept:
        language_lines = []

        if languages_kept:
            language_lines.append("[dim]Keeping:[/dim]")
            for lang in sorted(languages_kept):
                lang_name = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
                language_lines.append(f"  • [cyan]{lang_name}[/cyan]")

        if languages_added:
            if language_lines:
                language_lines.append("")
            language_lines.append("[green]Added:[/green]")
            for lang in sorted(languages_added):
                lang_name = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
                language_lines.append(f"  • [green]{lang_name}[/green]")

        if languages_removed:
            if language_lines:
                language_lines.append("")
            language_lines.append("[red]Removed:[/red]")
            for lang in sorted(languages_removed):
                lang_name = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
                language_lines.append(f"  • [red]{lang_name}[/red]")

        message_parts.append("\n**Language Configuration:**\n" + "\n".join(language_lines))

    print_panel(
        "\n".join(message_parts),
        title="Update Complete",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")
