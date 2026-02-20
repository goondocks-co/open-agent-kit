"""Path constants for open-agent-kit.

This module defines all directory structure and file path constants.
These are stable values that rarely change and define where oak stores
its configuration, templates, and artifacts.
"""

# =============================================================================
# Core Directory Structure
# =============================================================================

OAK_DIR = ".oak"
CONFIG_FILE = ".oak/config.yaml"
STATE_FILE = ".oak/state.yaml"
TEMPLATES_DIR = ".oak/templates"

# =============================================================================
# Feature Files
# =============================================================================
# Note: Feature directory paths (oak/rfc, oak/) are config-driven via config.yaml.
# Use ConfigService.get_rfc_dir(), get_constitution_dir() to retrieve paths at runtime.

CONSTITUTION_FILENAME = "constitution.md"
CONSTITUTION_FILE_EXTENSION = ".md"
RFC_FILE_EXTENSION = ".md"

# =============================================================================
# Package Structure
# =============================================================================

FEATURES_DIR = "features"
AGENTS_DIR = "agents"
FEATURE_MANIFEST_FILE = "manifest.yaml"
FEATURE_COMMANDS_SUBDIR = "commands"
FEATURE_TEMPLATES_SUBDIR = "templates"

# =============================================================================
# Skills Structure
# =============================================================================

SKILLS_DIR = "skills"
SKILL_MANIFEST_FILE = "SKILL.md"
SHARED_SKILLS_FOLDER = ".agents"

# =============================================================================
# Agent Settings (command auto-approval)
# =============================================================================
# Agent settings configure auto-approval for oak commands in various AI agents.
# Configuration is declared in agent manifests (agents/<agent>/manifest.yaml)
# and templates are stored in features/core/agent-settings/.

AGENT_SETTINGS_TEMPLATES_DIR = "agent-settings"

# Agent settings file paths (for reference - actual paths come from manifests)
CLAUDE_SETTINGS_FILE = ".claude/settings.local.json"
COPILOT_SETTINGS_FILE = ".vscode/settings.json"  # VS Code Copilot uses VSCode settings
CURSOR_SETTINGS_FILE = ".cursor/settings.json"
GEMINI_SETTINGS_FILE = ".gemini/settings.json"
WINDSURF_SETTINGS_FILE = ".windsurf/settings.json"

# Note: Codex uses global TOML config (~/.codex/config.toml) - not project-specific
AGENT_SETTINGS_TEMPLATES = {
    "claude": "agent-settings/claude-settings.json",
    "vscode-copilot": "agent-settings/vscode-copilot-settings.json",
    "cursor": "agent-settings/cursor-settings.json",
    "gemini": "agent-settings/gemini-settings.json",
    "windsurf": "agent-settings/windsurf-settings.json",
}

# =============================================================================
# Git Integration
# =============================================================================

GIT_DIR = ".git"
GIT_COMMIT_MESSAGE_TEMPLATE = "docs: Add {rfc_number} - {title}"

# =============================================================================
# Template Paths
# =============================================================================
