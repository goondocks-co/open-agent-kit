"""Constants and configuration defaults for Open Agent Kit (OAK)."""

from open_agent_kit import __version__

# Version - imported from package
VERSION = __version__

# Directory structure
OAK_DIR = ".oak"
RFC_DIR = "oak/rfc"
ISSUE_DIR = "oak/issue"
CONFIG_FILE = ".oak/config.yaml"
TEMPLATES_DIR = ".oak/templates"
ISSUE_CONTEXT_FILENAME = "context.json"
ISSUE_CONTEXT_SUMMARY_FILENAME = "context-summary.md"
ISSUE_PLAN_FILENAME = "plan.md"
ISSUE_NOTES_FILENAME = "notes.md"
ISSUE_VALIDATION_FILENAME = "validation.md"
ISSUE_MANIFEST_FILENAME = ".manifest.json"

# IDE settings
SUPPORTED_IDES = ["vscode", "cursor", "none"]
IDE_SETTINGS_TEMPLATES_DIR = "ide"
VSCODE_SETTINGS_FILE = ".vscode/settings.json"
CURSOR_SETTINGS_FILE = ".cursor/settings.json"
IDE_SETTINGS_TEMPLATES = {
    "vscode": "ide/vscode-settings.json",
    "cursor": "ide/cursor-settings.json",
}
IDE_DISPLAY_NAMES = {
    "vscode": "Visual Studio Code",
    "cursor": "Cursor",
}

# IDE settings JSON structure constants
IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS = "chat.promptFilesRecommendations"
IDE_SETTINGS_JSON_KEY_AUTO_APPROVE = "chat.tools.terminal.autoApprove"
IDE_SETTINGS_OAK_PROMPT_PREFIX = "oak."
IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS = [
    "oak",
    ".oak/scripts/bash/",
    ".oak/scripts/powershell/",
]

# Agent types
SUPPORTED_AGENTS = ["claude", "copilot", "codex", "cursor", "gemini", "windsurf", "none"]

# Issue provider support
SUPPORTED_ISSUE_PROVIDERS = ["ado", "github"]
ISSUE_PROVIDER_DISPLAY_NAMES = {
    "ado": "Azure DevOps",
    "github": "GitHub Issues",
}
ISSUE_PROVIDER_CONFIG_MAP = {
    "ado": "azure_devops",
    "github": "github",
}

# Issue provider default configuration values
ISSUE_PROVIDER_DEFAULTS = {
    "ado": {
        "organization": "",
    },
    "github": {
        "owner": "",
    },
}

# Issue validation configuration
ISSUE_PLAN_SECTION_HEADINGS = {
    "Objectives": "### Objectives",
    "Environment / Constraints": "### Environment / Constraints",
    "Risks & Mitigations": "### Risks & Mitigations",
    "Dependencies": "### Dependencies",
    "Definition of Done": "### Definition of Done",
}

CONSTITUTION_RULE_SECTIONS = frozenset(
    {
        "Code Standards",
        "Testing",
        "Documentation",
        "Architecture",
        "Best Practices",
    }
)

CONSTITUTION_RULE_KEYWORDS = ("must", "should", "always", "require", "ensure")

VALIDATION_STOPWORDS = frozenset(
    {
        "the",
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "must",
        "should",
        "ensure",
        "always",
        "require",
    }
)

# Issue provider API configuration
ISSUE_PROVIDER_TIMEOUT_SECONDS = 20.0
ISSUE_PROVIDER_MAX_RETRIES = 3
ISSUE_PROVIDER_RETRY_MIN_WAIT_SECONDS = 1.0
ISSUE_PROVIDER_RETRY_MAX_WAIT_SECONDS = 10.0
ISSUE_PROVIDER_USER_AGENT = "open-agent-kit/{version}"  # Format with VERSION at runtime

# Issue provider validation messages
ISSUE_PROVIDER_VALIDATION_MESSAGES = {
    "ado_org_missing": "Azure DevOps organization is not configured (issue.azure_devops.organization)",
    "ado_project_missing": "Azure DevOps project is not configured (issue.azure_devops.project)",
    "ado_pat_env_missing": "Azure DevOps PAT environment variable is not configured (issue.azure_devops.pat_env)",
    "github_owner_missing": "GitHub repository owner is not configured (issue.github.owner)",
    "github_repo_missing": "GitHub repository name is not configured (issue.github.repo)",
    "github_token_env_missing": "GitHub token environment variable is not configured (issue.github.token_env)",
    "env_var_not_set": "Environment variable '{var_name}' is not set",
}

# Issue item limits and validation
ISSUE_NOTES_MAX_LENGTH = 10000  # Maximum characters for notes

# Git operation configuration
GIT_COMMAND_TIMEOUT_SECONDS = 30.0

# Agent configurations - maps agents to their native command directories
# Following spec-kit pattern: each agent has a native folder where commands are installed
AGENT_CONFIG = {
    "claude": {
        "name": "Claude Code",
        "folder": ".claude/",
        "commands_subfolder": "commands",  # .claude/commands/
        "file_extension": ".md",
        "requires_cli": True,
        "install_url": "https://docs.anthropic.com/en/docs/claude-code",
    },
    "copilot": {
        "name": "GitHub Copilot",
        "folder": ".github/",
        "commands_subfolder": "agents",  # .github/agents/
        "file_extension": ".agent.md",
        "requires_cli": False,
        "install_url": None,
    },
    "cursor": {
        "name": "Cursor",
        "folder": ".cursor/",
        "commands_subfolder": "commands",  # .cursor/commands/
        "file_extension": ".md",
        "requires_cli": False,
        "install_url": None,
    },
    "codex": {
        "name": "Codex CLI",
        "folder": ".codex/",
        "commands_subfolder": "prompts",  # .codex/prompts/
        "file_extension": ".md",
        "requires_cli": True,
        "install_url": "https://github.com/openai/codex",
    },
    "gemini": {
        "name": "Gemini CLI",
        "folder": ".gemini/",
        "commands_subfolder": "commands",  # .gemini/commands/
        "file_extension": ".md",
        "requires_cli": True,
        "install_url": "https://github.com/google-gemini/gemini-cli",
    },
    "windsurf": {
        "name": "Windsurf",
        "folder": ".windsurf/",
        "commands_subfolder": "commands",  # .windsurf/commands/
        "file_extension": ".md",
        "requires_cli": False,
        "install_url": None,
    },
}

# Backward compatibility
DEFAULT_AGENT_CONFIGS = AGENT_CONFIG

# RFC configuration
RFC_NUMBER_FORMATS = {
    "sequential": "NNN",
    "year_based": "YYYY-NNN",
    "four_digit": "NNNN",
}

DEFAULT_RFC_FORMAT = "sequential"

RFC_STATUSES = [
    "draft",
    "review",
    "approved",
    "adopted",
    "abandoned",
    "implemented",
    "wont-implement",
]

# RFC quality heuristics
RFC_PLACEHOLDER_KEYWORDS = [
    "provide",
    "explain",
    "describe",
    "summarize",
    "outline",
    "identify",
    "state",
    "list",
    "detail",
    "define",
    "specify",
    "capture",
    "link",
    "note",
]
RFC_STALE_DRAFT_DAYS = 60

# Template names
RFC_TEMPLATES = {
    "engineering": "Engineering RFC Template",
    "architecture": "Architecture Decision Record",
    "feature": "Feature Proposal",
    "process": "Process Improvement",
}

DEFAULT_RFC_TEMPLATE = "engineering"

# File extensions
RFC_FILE_EXTENSION = ".md"

# Git configuration
GIT_COMMIT_MESSAGE_TEMPLATE = "docs: Add {rfc_number} - {title}"

# ============================================================================
# CONSTITUTION CONFIGURATION
# ============================================================================

# Constitution directory and file paths
CONSTITUTION_DIR = "oak"
CONSTITUTION_FILENAME = "constitution.md"
CONSTITUTION_FILE_EXTENSION = ".md"

# Constitution sections (required)
CONSTITUTION_REQUIRED_SECTIONS = [
    "Metadata",
    "Principles",
    "Architecture",
    "Code Standards",
    "Testing",
    "Documentation",
    "Governance",
]

# Constitution metadata fields
CONSTITUTION_METADATA_PROJECT_NAME = "project_name"
CONSTITUTION_METADATA_VERSION = "version"
CONSTITUTION_METADATA_RATIFICATION_DATE = "ratification_date"
CONSTITUTION_METADATA_LAST_AMENDMENT = "last_amendment"

# Constitution metadata fields (required)
CONSTITUTION_REQUIRED_METADATA = [
    CONSTITUTION_METADATA_PROJECT_NAME,
    CONSTITUTION_METADATA_VERSION,
    CONSTITUTION_METADATA_RATIFICATION_DATE,
]

# Constitution metadata fields (optional but recommended)
CONSTITUTION_METADATA_OPTIONAL = [
    CONSTITUTION_METADATA_LAST_AMENDMENT,
]

# Constitution version format
CONSTITUTION_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"  # Semantic versioning
CONSTITUTION_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"  # ISO date format

# Constitution validation issue priorities
VALIDATION_PRIORITY_HIGH = "high"
VALIDATION_PRIORITY_MEDIUM = "medium"
VALIDATION_PRIORITY_LOW = "low"
VALIDATION_PRIORITIES = [
    VALIDATION_PRIORITY_HIGH,
    VALIDATION_PRIORITY_MEDIUM,
    VALIDATION_PRIORITY_LOW,
]

# Constitution validation issue categories
VALIDATION_CATEGORY_STRUCTURE = "structure"
VALIDATION_CATEGORY_METADATA = "metadata"
VALIDATION_CATEGORY_TOKENS = "tokens"
VALIDATION_CATEGORY_DATES = "dates"
VALIDATION_CATEGORY_LANGUAGE = "language"
VALIDATION_CATEGORY_VERSIONING = "versioning"
VALIDATION_CATEGORY_QUALITY = "quality"
VALIDATION_CATEGORY_CONSISTENCY = "consistency"
VALIDATION_CATEGORIES = [
    VALIDATION_CATEGORY_STRUCTURE,
    VALIDATION_CATEGORY_METADATA,
    VALIDATION_CATEGORY_TOKENS,
    VALIDATION_CATEGORY_DATES,
    VALIDATION_CATEGORY_LANGUAGE,
    VALIDATION_CATEGORY_VERSIONING,
    VALIDATION_CATEGORY_QUALITY,
    VALIDATION_CATEGORY_CONSISTENCY,
]

# Constitution quality heuristics
CONSTITUTION_SECTION_MIN_SENTENCE_COUNT = 2
CONSTITUTION_NORMATIVE_SECTIONS = [
    "Principles",
    "Architecture",
    "Code Standards",
    "Testing",
    "Governance",
]
CONSTITUTION_NORMATIVE_KEYWORDS = [
    "MUST",
    "MUST NOT",
    "SHALL",
    "SHALL NOT",
    "MAY",
]
CONSTITUTION_VAGUE_POLICY_PATTERNS = [
    r"\btry to\b",
    r"\bstrive\b",
    r"\bendeavor\b",
    r"\baspire\b",
    r"\bideally\b",
    r"\bencourage\b",
]

# Constitution amendment types
AMENDMENT_TYPE_MAJOR = "major"  # Breaking changes (X.0.0)
AMENDMENT_TYPE_MINOR = "minor"  # New requirements (0.X.0)
AMENDMENT_TYPE_PATCH = "patch"  # Clarifications (0.0.X)
AMENDMENT_TYPES = [
    AMENDMENT_TYPE_MAJOR,
    AMENDMENT_TYPE_MINOR,
    AMENDMENT_TYPE_PATCH,
]

# Agent instruction file patterns
# Note: Some agents use root-level files, others use folder-based files
AGENT_INSTRUCTION_PATTERNS = {
    "claude": "{agent_folder}CLAUDE.md",  # .claude/CLAUDE.md
    "copilot": "{agent_folder}copilot-instructions.md",  # .github/copilot-instructions.md
    "cursor": "AGENTS.md",  # AGENTS.md in project root (same as Codex)
    "codex": "AGENTS.md",  # AGENTS.md in project root
    "gemini": "GEMINI.md",  # GEMINI.md in project root
    "windsurf": ".windsurf/rules/rules.md",  # .windsurf/rules/rules.md or global_rules.md
}

# Constitution tokens (placeholders to replace)
CONSTITUTION_TOKENS = [
    "{{PROJECT_NAME}}",
    "{{PROJECT_DESCRIPTION}}",
    "{{VERSION}}",
    "{{DATE}}",
    "{{AUTHOR}}",
    "{{TECH_STACK}}",
]

# Constitution decision context keys (for decision-driven constitution generation)
DECISION_TESTING_STRATEGY = "testing_strategy"
DECISION_COVERAGE_TARGET = "coverage_target"
DECISION_COVERAGE_STRICT = "coverage_strict"
DECISION_HAS_E2E_INFRASTRUCTURE = "has_e2e_infrastructure"
DECISION_E2E_PLANNED = "e2e_planned"
DECISION_CRITICAL_INTEGRATION_POINTS = "critical_integration_points"
DECISION_TDD_REQUIRED = "tdd_required"
DECISION_TESTING_RATIONALE = "testing_rationale"
DECISION_CODE_REVIEW_POLICY = "code_review_policy"
DECISION_NUM_REVIEWERS = "num_reviewers"
DECISION_REVIEWER_QUALIFICATIONS = "reviewer_qualifications"
DECISION_HOTFIX_DEFINITION = "hotfix_definition"
DECISION_DOCUMENTATION_LEVEL = "documentation_level"
DECISION_ADR_REQUIRED = "adr_required"
DECISION_DOCSTRING_STYLE = "docstring_style"
DECISION_CI_ENFORCEMENT = "ci_enforcement"
DECISION_REQUIRED_CHECKS = "required_checks"
DECISION_CI_PLATFORM = "ci_platform"
DECISION_ARCHITECTURAL_PATTERN = "architectural_pattern"
DECISION_ERROR_HANDLING_PATTERN = "error_handling_pattern"
DECISION_DEPENDENCY_INJECTION = "dependency_injection"
DECISION_DOMAIN_EVENTS = "domain_events"
DECISION_FEATURE_ORGANIZATION = "feature_organization"
DECISION_LAYER_ORGANIZATION = "layer_organization"
DECISION_CODING_PRINCIPLES = "coding_principles"
DECISION_ARCHITECTURAL_RATIONALE = "architectural_rationale"

# Constitution decision default values
DECISION_DEFAULT_TESTING_STRATEGY = "balanced"
DECISION_DEFAULT_CODE_REVIEW_POLICY = "standard"
DECISION_DEFAULT_NUM_REVIEWERS = 1
DECISION_DEFAULT_DOCUMENTATION_LEVEL = "standard"
DECISION_DEFAULT_DOCSTRING_STYLE = "google"
DECISION_DEFAULT_CI_ENFORCEMENT = "standard"
DECISION_DEFAULT_TESTING_RATIONALE = (
    "Balanced approach to testing ensures reliability while maintaining velocity"
)

# Constitution template names
CONSTITUTION_TEMPLATE_BASE = "constitution/base_constitution.md"
CONSTITUTION_TEMPLATE_AGENT_INSTRUCTIONS = "constitution/agent_instructions.md"
CONSTITUTION_TEMPLATE_DECISION_POINTS = "constitution/decision_points.yaml"

# Non-declarative language patterns to detect
NON_DECLARATIVE_PATTERNS = [
    r"\bshould\b",
    r"\bcould\b",
    r"\bmight\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
]

# Console styling
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

# Success messages
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

# Error messages
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

# Info messages
INFO_MESSAGES = {
    "adding_agents": "Adding new agents to existing installation...",
    "add_more_agents": "OAK is already initialized. Let's add more agents!",
    "setting_up": "Setting up Open Agent Kit in your project...",
    "force_reinit": "Forcing re-initialization of OAK...",
    "no_agents_selected": "No agents selected. Configuration unchanged.",
    "select_agents_prompt": "Choose one or more AI agents to assist with RFC generation and code reviews.\nYou can always add more agents later by running 'oak init' again.",
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

# Warning messages
WARNING_MESSAGES = {
    "rfc_dir_not_found": "RFC directory not found: {dir}",
    "validation_issues": "Validation issues found:",
    "templates_customized": "Some templates may have been customized.\nUpgrading will overwrite your changes.\nConsider backing them up first.",
}

# Upgrade messages
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

# Upgrade configuration
UPGRADE_TEMPLATE_CATEGORIES = ["rfc", "constitution", "commands"]
UPGRADE_IDE_SETTINGS = ["vscode", "cursor"]  # IDE settings to install/upgrade
UPGRADE_COMMAND_NAMES = [
    "rfc-create",
    "rfc-list",
    "rfc-validate",
    "issue-plan",
    "issue-implement",
    "issue-validate",
    "constitution-create",
    "constitution-validate",
    "constitution-amend",
]

# Validation patterns
RFC_NUMBER_PATTERN = r"^(?:RFC-)?(\d{3,4}|20\d{2}-\d{3})$"
RFC_FILENAME_PATTERN = r"^RFC-(\d{3,4}|20\d{2}-\d{3})-(.+)\.md$"

# Default configuration content
DEFAULT_CONFIG_YAML = """# Open Agent Kit (OAK) configuration
version: {version}

# AI Agent configuration (supports multiple agents)
agents: {agents}

# IDE configuration (supports multiple IDEs)
ides: {ides}

# RFC configuration
rfc:
  directory: oak/rfc
  template: engineering
  auto_number: true
  number_format: sequential
  validate_on_create: true

# Issue provider configuration
issue:
  provider:
  azure_devops:
    organization:
    project:
    team:
    area_path:
    pat_env:
  github:
    owner:
    repo:
    token_env:
"""

# Required RFC sections
REQUIRED_RFC_SECTIONS = [
    "# Summary",
    "## Motivation",
    "## Detailed Design",
    "## Drawbacks",
    "## Alternatives",
    "## Unresolved Questions",
]

# CLI colors and styles
COLORS = {
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "blue",
    "muted": "dim",
}

# Progress indicators
PROGRESS_CHARS = {
    "complete": "✓",
    "incomplete": "○",
    "current": "●",
    "error": "✗",
}

# Project URLs
PROJECT_URL = "https://github.com/sirkirby/open-agent-kit"

# Usage examples
USAGE_EXAMPLES = {
    "init_agent": "oak init --agent claude",
    "init_multi_agent": "oak init --agent copilot --agent cursor",
    "init_force": "oak init --force",
    "rfc_validate_number": "oak rfc validate RFC-001",
    "rfc_validate_path": "oak rfc validate path/to/rfc.md",
    "rfc_validate_all": "oak rfc validate --all",
    "rfc_create": 'oak rfc create "Description"',
}

# Help text for init command
INIT_HELP_TEXT = {
    "no_interactive": "In non-interactive mode, use --agent to add new agents, or --force to re-initialize",
    "examples": "Examples:\n  {init_agent}\n  {init_multi_agent}\n  {init_force}",
}

# Next steps text
NEXT_STEPS_INIT = """[bold green]Next Steps[/bold green]

1. Review your configuration:
   [dim]$ cat {config_file}[/dim]

2. Create your first RFC:
   [dim]$ oak rfc create "Your RFC description"[/dim]

3. List available templates:
   [dim]$ ls {templates_dir}/rfc/[/dim]

4. Customize templates:
   [dim]Edit files in {templates_dir}/[/dim]"""

# Hints
HINTS = {
    "create_first_rfc": 'Create your first RFC with: oak rfc create "Description"',
}

# Interactive prompts
INTERACTIVE_HINTS = {
    "navigate": "(Use arrow keys to navigate, Enter to select)",
    "search": "(Type to search, use arrow keys to navigate, Enter to select)",
    "multi_select": "(Use arrow keys, Space to select/deselect, Enter to confirm)",
}
