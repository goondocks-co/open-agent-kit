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
# Note: Feature directory paths (oak/rfc, oak/issue, oak/plan, oak/) are now
# config-driven via config.yaml. Use ConfigService.get_rfc_dir(), get_issue_dir(),
# get_plan_dir(), get_constitution_dir() to retrieve paths at runtime.

CONSTITUTION_FILENAME = "constitution.md"
CONSTITUTION_FILE_EXTENSION = ".md"
RFC_FILE_EXTENSION = ".md"

# Issue artifacts
ISSUE_CONTEXT_FILENAME = "context.json"
ISSUE_CONTEXT_SUMMARY_FILENAME = "context-summary.md"
ISSUE_PLAN_FILENAME = "plan.md"
ISSUE_NOTES_FILENAME = "notes.md"
ISSUE_VALIDATION_FILENAME = "validation.md"
ISSUE_MANIFEST_FILENAME = ".manifest.json"

# Plan artifacts
PLAN_MANIFEST_FILENAME = ".manifest.json"
PLAN_DATA_FILENAME = ".data.json"
PLAN_FILE_FILENAME = "plan.md"
PLAN_TASKS_FILENAME = "tasks.md"
PLAN_RESEARCH_DIR = "research"

# Plan issue subdirectory
PLAN_ISSUE_DIR = "issue"
PLAN_ISSUE_CONTEXT_FILENAME = "context.json"
PLAN_ISSUE_SUMMARY_FILENAME = "summary.md"
PLAN_ISSUE_RELATED_DIR = "related"

# =============================================================================
# Features Structure
# =============================================================================

FEATURES_DIR = "features"
FEATURE_MANIFEST_FILE = "manifest.yaml"
FEATURE_COMMANDS_SUBDIR = "commands"
FEATURE_TEMPLATES_SUBDIR = "templates"

# =============================================================================
# Skills Structure
# =============================================================================

SKILLS_DIR = "skills"
SKILL_MANIFEST_FILE = "SKILL.md"

# =============================================================================
# IDE Settings
# =============================================================================

IDE_SETTINGS_TEMPLATES_DIR = "ide"
VSCODE_SETTINGS_FILE = ".vscode/settings.json"
CURSOR_SETTINGS_FILE = ".cursor/settings.json"
IDE_SETTINGS_TEMPLATES = {
    "vscode": "ide/vscode-settings.json",
    "cursor": "ide/cursor-settings.json",
}

# =============================================================================
# Git Integration
# =============================================================================

PLAN_BRANCH_PREFIX = "plan/"
GIT_COMMIT_MESSAGE_TEMPLATE = "docs: Add {rfc_number} - {title}"

# =============================================================================
# Template Paths
# =============================================================================

CONSTITUTION_TEMPLATE_BASE = "constitution/base_constitution.md"
CONSTITUTION_TEMPLATE_AGENT_INSTRUCTIONS = "constitution/agent_instructions.md"
CONSTITUTION_TEMPLATE_DECISION_POINTS = "constitution/decision_points.yaml"
