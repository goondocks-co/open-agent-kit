"""UI messages and strings for open-agent-kit.

This module consolidates all user-facing messages including:
- Success/error/info/warning messages
- Banner and help text
- Interactive prompts
- Feature-specific messages
"""

# =============================================================================
# Project Metadata
# =============================================================================

PROJECT_TAGLINE = "Your Team's Memory in the Age of AI-Written Code"
PROJECT_URL = "https://openagentkit.app"

# =============================================================================
# Banner and Help
# =============================================================================

BANNER = """
╭─────────────────────────────────────────────────────────╮
│                                                         │
│              ██████╗  █████╗ ██╗  ██╗                   │
│             ██╔═══██╗██╔══██╗██║ ██╔╝                   │
│             ██║   ██║███████║█████╔╝                    │
│             ██║   ██║██╔══██║██╔═██╗                    │
│             ╚██████╔╝██║  ██║██║  ██╗                   │
│              ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝                   │
│                                                         │
│   Open Agent Kit - AI-Powered Development Workflows     │
│                                                         │
╰─────────────────────────────────────────────────────────╯
"""

HELP_TEXT = f"""
[bold cyan]oak[/bold cyan] - Open Agent Kit: {PROJECT_TAGLINE}

[bold]Primary Commands:[/bold]
  [cyan]init[/cyan]        Initialize .oak directory with templates and configs
  [cyan]ci[/cyan]          Codebase Intelligence — daemon, search, memories
  [cyan]upgrade[/cyan]     Upgrade templates and agent commands to latest versions
  [cyan]languages[/cyan]   Manage language support for code intelligence
  [cyan]remove[/cyan]      Remove open-agent-kit from the current project
  [cyan]version[/cyan]     Show version information

[bold]Examples:[/bold]
  [dim]# Initialize with guided setup[/dim]
  [dim]$ oak init[/dim]

  [dim]# One-shot initialize by setting agents[/dim]
  [dim]$ oak init --agent claude --agent cursor[/dim]

  [dim]# Start Codebase Intelligence with the dashboard[/dim]
  [dim]$ oak ci start --open[/dim]

  [dim]# Upgrade to latest version[/dim]
  [dim]$ oak upgrade --dry-run[/dim]

[bold]Get Started:[/bold]
  1. Run [cyan]oak init[/cyan] to set up your project
  2. Run [cyan]oak ci start --open[/cyan] to launch Codebase Intelligence
  3. See the Quick Start guide: [dim]QUICKSTART.md[/dim]

For more information, visit: {PROJECT_URL}
"""

NEXT_STEPS_INIT = """[bold green]What's Next?[/bold green]

OAK enhances your AI coding assistants with code intelligence.

[bold]For agents with skills support (Claude, VS Code Copilot, Gemini):[/bold]
  Skills are automatically discovered. Use them naturally:
  [dim]• "add a project rule about test coverage"[/dim]
  [dim]• "create an RFC for the new authentication system"[/dim]

[bold]For agents with commands (Cursor, Windsurf, Codex):[/bold]
  Type [cyan]/oak[/cyan] to see available commands.

[bold]Start code intelligence:[/bold]
  [dim]$ oak ci start[/dim]          # Start the CI daemon
  [dim]$ oak languages list[/dim]    # See installed languages
  [dim]$ oak languages add ruby[/dim] # Add more language support"""

# =============================================================================
# Success Messages
# =============================================================================

SUCCESS_MESSAGES = {
    "init": "Successfully initialized Open Agent Kit!",
    "rfc_created": "RFC created successfully!",
    "rfc_validated": "RFC validation passed!",
    "up_to_date": "Everything is already up to date!",
    "constitution_created": "Constitution created successfully!",
    "constitution_validated": "Constitution validation passed!",
    "constitution_amended": "Amendment added successfully!",
    "agent_files_generated": "Agent instruction files generated",
    "agent_files_updated": "Agent instruction files updated",
    "upgrade_complete": "Upgrade complete!",
    "upgraded_agent_commands": "Updated {count} agent command(s) with latest improvements",
    "upgraded_templates": "Updated {count} template(s)",
    "updated_project_version": "Updated project to OAK v{version}",
}

# =============================================================================
# Error Messages
# =============================================================================

ERROR_MESSAGES = {
    "no_oak_dir": "No .oak directory found. Run 'oak init' first.",
    "invalid_rfc_number": "Invalid RFC number format.",
    "rfc_not_found": "RFC not found: {identifier}",
    "invalid_template": "Invalid template name.",
    "git_not_initialized": "Git repository not initialized.",
    "oak_dir_exists": ".oak directory already exists at {oak_dir}",
    "invalid_agent": "Invalid agent: {agent}",
    "none_with_others": "Cannot combine 'none' with other agents",
    "rfc_file_required": "RFC file or number required",
    "rfc_validation_failed": "RFC validation failed!",
    "generic_error": "An error occurred: {error}",
    "field_required": "This field is required",
    "invalid_input": "Invalid input, please try again",
    "no_constitution": "Constitution not found. Run: /oak.constitution-create",
    "constitution_exists": "Constitution already exists at {path}",
    "constitution_not_found": "Constitution not found: {path}",
    "constitution_validation_failed": "Constitution validation failed!",
    "invalid_version": "Invalid version format. Use semantic versioning (e.g., 1.0.0)",
    "invalid_date": "Invalid date format. Use ISO format (YYYY-MM-DD)",
    "missing_section": "Required section missing: {section}",
    "missing_metadata": "Required metadata field missing: {field}",
    "token_not_replaced": "Template token not replaced: {token}",
    "invalid_amendment_type": "Invalid amendment type. Must be: major, minor, or patch",
    "no_agents_detected": "No agents detected. Run: oak init",
    "git_command_failed": "Git command failed: {details}",
    "file_system_error": "File system error: {details}",
}

# =============================================================================
# Info Messages
# =============================================================================

INFO_MESSAGES = {
    "adding_agents": "Adding new agents to existing installation...",
    "add_more_agents": "OAK is already initialized. Let's add more agents!",
    "setting_up": "Setting up Open Agent Kit in your project...",
    "force_reinit": "Forcing re-initialization of OAK...",
    "no_agents_selected": "No agents selected. Configuration unchanged.",
    "select_agents_prompt": (
        "Choose one or more AI agents to integrate with oak.\n"
        "You can always add more agents later by running 'oak init' again."
    ),
    "more_info": "For more information, visit: {url}",
    "select_additional_agents": "Select additional agents to add to your existing OAK installation.",
    "all_agents_installed": "All supported agents are already installed!",
    "reinit_hint": "Run 'oak init --force' to re-initialize if needed.",
    "no_agents_added": "No agents were added.",
    "dry_run_mode": "Running in dry-run mode - no changes will be made",
    "upgrade_cancelled": "Upgrade cancelled.",
    "dry_run_complete": "Dry-run complete. Run without --dry-run to apply changes.",
    "upgrading_agent_commands": "Upgrading {count} agent command(s)",
    "upgrading_templates": "Upgrading {count} template(s)",
    "updating_project_version": "Updating project version",
    "rfc_next_steps": "Next steps:",
    "rfc_step_edit": "Edit the RFC: {path}",
    "rfc_step_review": "Review and update sections as needed",
    "rfc_step_commit": "Commit to version control",
    "no_rfcs_created": "No RFCs have been created yet.",
    "no_rfcs_with_status": "No RFCs found with status '{status}'",
    "no_rfcs_found": "No RFCs found",
    "total_rfcs": "Total RFCs: {count}",
    "no_rfcs_to_validate": "No RFCs found to validate",
    "validation_summary": "Validated {total} RFCs: {passed} passed, {failed} failed",
    "supported_agents_list": "Supported agents: {agents}",
    "currently_installed": "Currently installed: {agents}",
    "cancelled": "Cancelled",
    "analyzing_codebase": "Analyzing codebase patterns...",
    "generating_constitution": "Generating constitution...",
    "validating_structure": "Validating structure...",
    "validating_metadata": "Validating metadata...",
    "validating_tokens": "Validating token replacement...",
    "validating_dates": "Validating date formats...",
    "validating_language": "Validating language style...",
    "categorizing_issues": "Categorizing validation issues...",
    "applying_fixes": "Applying fixes...",
    "adding_amendment": "Adding amendment...",
    "incrementing_version": "Incrementing version...",
    "generating_agent_files": "Generating agent instruction files...",
    "updating_agent_files": "Updating agent instruction files...",
    "detecting_agents": "Detecting installed agents...",
    "loading_constitution": "Loading constitution...",
}

# =============================================================================
# Warning Messages
# =============================================================================

WARNING_MESSAGES = {
    "rfc_dir_not_found": "RFC directory not found: {dir}",
    "validation_issues": "Validation issues found:",
    "templates_customized": (
        "Some templates may have been customized.\n"
        "Upgrading will overwrite your changes.\n"
        "Consider backing them up first."
    ),
}

# =============================================================================
# Upgrade Messages
# =============================================================================

UPGRADE_MESSAGES = {
    "section_agent_commands": "Agent Commands",
    "section_templates": "Templates",
    "section_project_version": "Project Version",
    "will_upgrade": "Will upgrade",
    "would_upgrade": "Would upgrade",
    "current_version": "Current: {version}",
    "update_to_version": "Update to: {version}",
    "whats_new_title": "What's New",
    "upgrade_summary_title": "Upgrade Summary",
    "upgrade_plan_title": "Upgrade Plan",
    "release_notes": "For full release notes, see:",
}

# =============================================================================
# Feature Messages
# =============================================================================

FEATURE_MESSAGES = {
    "feature_added": "Feature '{feature}' added successfully!",
    "feature_removed": "Feature '{feature}' removed successfully!",
    "feature_not_found": "Feature '{feature}' not found.",
    "feature_already_installed": "Feature '{feature}' is already installed.",
    "feature_not_installed": "Feature '{feature}' is not installed.",
    "feature_required_by": "Feature '{feature}' is required by: {dependents}",
    "feature_requires": "Feature '{feature}' requires: {dependencies}",
    "feature_deps_auto_added": "Auto-adding required dependencies: {dependencies}",
    "no_features_selected": "No features selected.",
    "select_features_prompt": "Choose features to install. Dependencies will be auto-selected.",
}

# =============================================================================
# Interactive Hints
# =============================================================================

INTERACTIVE_HINTS = {
    "navigate": "(Use arrow keys to navigate, Enter to select)",
    "search": "(Type to search, use arrow keys to navigate, Enter to select)",
    "multi_select": "(Use arrow keys, Space to select/deselect, Enter to confirm)",
}

# =============================================================================
# CLI Help Text
# =============================================================================

INIT_HELP_TEXT = {
    "no_interactive": "In non-interactive mode, use --agent to add new agents, or --force to re-initialize",
    "examples": "Examples:\n  {init_agent}\n  {init_multi_agent}\n  {init_force}",
}

USAGE_EXAMPLES = {
    "init_agent": "oak init --agent claude",
    "init_multi_agent": "oak init --agent vscode-copilot --agent cursor",
    "init_force": "oak init --force",
    "rfc_validate_number": "oak rfc validate RFC-001",
    "rfc_validate_path": "oak rfc validate path/to/rfc.md",
    "rfc_validate_all": "oak rfc validate --all",
    "rfc_create": 'oak rfc create "Description"',
}

HINTS = {
    "create_first_rfc": 'Create your first RFC with: oak rfc create "Description"',
}

# =============================================================================
# UI Styling
# =============================================================================

COLORS = {
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "blue",
    "muted": "dim",
}

PROGRESS_CHARS = {
    "complete": "✓",
    "incomplete": "○",
    "current": "●",
    "error": "✗",
}
