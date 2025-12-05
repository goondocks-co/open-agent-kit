"""UI messages and strings for open-agent-kit.

This module consolidates all user-facing messages including:
- Success/error/info/warning messages
- Banner and help text
- Interactive prompts
- Feature-specific messages
"""

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

HELP_TEXT = """
[bold cyan]oak[/bold cyan] - Open Agent Kit: AI-powered development workflows

[bold]Primary Commands:[/bold]
  [cyan]init[/cyan]        Initialize .oak directory with templates and configs
  [cyan]config[/cyan]      Configure issue providers and project settings
  [cyan]upgrade[/cyan]     Upgrade templates and agent commands to latest versions
  [cyan]version[/cyan]     Show version information

[bold]Examples:[/bold]
  [dim]# Initialize with guided setup[/dim]
  [dim]$ oak init[/dim]

  [dim]# Configure issue provider interactively[/dim]
  [dim]$ oak config[/dim]

  [dim]# One-shot initialize by setting agents[/dim]
  [dim]$ oak init --agent copilot --agent codex[/dim]

  [dim]# Upgrade to latest version[/dim]
  [dim]$ oak upgrade --dry-run[/dim]

[bold]Get Started:[/bold]
  1. Run [cyan]oak init[/cyan] to set up your project
  2. Run [cyan]oak config[/cyan] to configure issue providers
  3. See the Quick Start guide: [dim]QUICKSTART.md[/dim]

For more information, visit: https://github.com/sirkirby/open-agent-kit
"""

NEXT_STEPS_INIT = """[bold green]Next Steps[/bold green]

1. Review your configuration:
   [dim]$ cat {config_file}[/dim]

2. Create your first RFC:
   [dim]$ oak rfc create "Your RFC description"[/dim]

3. List available templates:
   [dim]$ ls {templates_dir}/rfc/[/dim]

4. Customize templates:
   [dim]Edit files in {templates_dir}/[/dim]"""

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
    "issue_artifacts_ready": "Issue item artifacts ready",
    "issue_branch_ready": "Branch {branch} is ready for implementation",
    "issue_validated": "Issue item artifacts look complete. Ready for review!",
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
    "issue_provider_not_set": "No issue provider configured. Run: oak config issue-provider set",
    "issue_provider_invalid": "Issue provider '{provider}' is not supported.",
    "issue_provider_missing_secret": "Environment variable '{env_var}' is not set.",
    "issue_fetch_failed": "Failed to load issue item {identifier}: {error}",
    "issue_dir_missing": "Issue directory not found: {path}",
    "issue_context_missing": "Issue context file not found: {path}",
    "issue_plan_missing": "Issue plan file not found: {path}",
    "issue_not_found": "Unable to determine issue item context. Provide an issue or run /oak.issue-plan first.",
    "issue_provider_api_error": "{provider} API error ({error_type}): {details}",
    "issue_provider_env_var_missing": "Environment variable '{var}' is not set or empty",
    "issue_provider_invalid_response": "Invalid API response format from {provider}",
    "issue_notes_too_long": "Notes exceed maximum length of {max_length} characters",
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
        "Choose one or more AI agents to assist with RFC generation and code reviews.\n"
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
    "issue_artifacts_location": "Issue item assets saved to {path}",
    "issue_branch_exists": "Branch {branch} already exists. Switching to it.",
    "issue_config_prompt": "Configure your issue provider with: oak config issue-provider set",
    "issue_plan_hint": "Generate a plan first via /oak.issue-plan {issue}",
    "issue_inferred": "Using issue item {issue} ({provider}).",
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
# Plan Feature Messages
# =============================================================================

PLAN_SUCCESS_MESSAGES = {
    "plan_created": "Plan created successfully!",
    "plan_research_complete": "Research completed for {count} topic(s)",
    "plan_tasks_generated": "Generated {count} task(s) from plan",
    "plan_exported": "Exported {count} issue(s) to {provider}",
    "plan_branch_ready": "Branch {branch} is ready for planning",
    "branch_created": "Switched to branch {branch}",
    "status_updated": "Plan '{name}' status updated to {status}",
}

PLAN_ERROR_MESSAGES = {
    "no_oak_dir": "Not an oak project. Run `oak init` first.",
    "plan_not_found": "Plan '{name}' not found. Run `oak plan create {name}` first.",
    "plan_not_specified": "No plan specified. Provide a plan name or switch to a plan branch.",
    "plan_exists": "Plan '{name}' already exists at {path}",
    "plan_already_exists": "Plan '{name}' already exists. Use a different name or delete the existing plan.",
    "plan_no_research_topics": "Plan has no research topics defined. Add topics to plan.md first.",
    "plan_no_tasks": "Plan has no tasks. Run `/oak.plan-tasks` to generate tasks from research.",
    "plan_export_failed": "Failed to export task '{task}' to {provider}: {error}",
    "plan_research_incomplete": "Research incomplete. Complete research for: {topics}",
    "constitution_required": "Constitution is required for the plan feature. Run `oak constitution init` first.",
}

PLAN_INFO_MESSAGES = {
    "plan_branch_exists": "Branch {branch} already exists. Switching to it.",
    "plan_encourage_web_search": (
        "Web search is strongly encouraged for comprehensive research. "
        "Use available search tools."
    ),
    "plan_encourage_background": "Consider using background agents for context-efficient research.",
    "plan_encourage_mcp": "MCP tools are available for enhanced research capabilities.",
    "plan_research_fallback": "Web search unavailable. Using general knowledge for research.",
    "no_plans": "No plans found. Create one with `oak plan create <name>`.",
    "no_research_topics": "No research topics defined for plan '{name}'. Add topics via /oak.plan-research.",
    "no_tasks": "No tasks found for plan '{name}'. Generate tasks via /oak.plan-tasks.",
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
# Issue Provider Validation Messages
# =============================================================================

ISSUE_PROVIDER_VALIDATION_MESSAGES = {
    "ado_org_missing": "Azure DevOps organization is not configured (issue.azure_devops.organization)",
    "ado_project_missing": "Azure DevOps project is not configured (issue.azure_devops.project)",
    "ado_pat_env_missing": "Azure DevOps PAT environment variable is not configured (issue.azure_devops.pat_env)",
    "github_owner_missing": "GitHub repository owner is not configured (issue.github.owner)",
    "github_repo_missing": "GitHub repository name is not configured (issue.github.repo)",
    "github_token_env_missing": "GitHub token environment variable is not configured (issue.github.token_env)",
    "env_var_not_set": "Environment variable '{var_name}' is not set",
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
    "init_multi_agent": "oak init --agent copilot --agent cursor",
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

# =============================================================================
# URLs
# =============================================================================

PROJECT_URL = "https://github.com/sirkirby/open-agent-kit"
