"""Migration system for open-agent-kit upgrades.

This module provides a framework for running one-time migrations during upgrades.
Each migration is a function that gets executed once based on version tracking.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from open_agent_kit.utils import ensure_gitignore_has_issue_context

logger = logging.getLogger(__name__)


def get_migrations() -> list[tuple[str, str, Callable[[Path], None]]]:
    """Get all available migrations.

    Returns:
        List of tuples: (migration_id, description, migration_function)
        Migrations are executed in order when running upgrades.
    """
    return [
        (
            "2024.11.13_gitignore_issue_context",
            "Add oak/issue/**/context.json to .gitignore",
            _migrate_gitignore_issue_context,
        ),
        (
            "2024.11.18_copilot_agents_folder",
            "Migrate Copilot prompts to .github/agents/",
            _migrate_copilot_agents_folder,
        ),
        (
            "2025.11.28_features_restructure",
            "Migrate to features-based organization",
            _migrate_features_restructure,
        ),
        (
            "2025.11.28_cleanup_old_templates",
            "Remove old .oak/templates/ directory",
            _migrate_cleanup_old_templates,
        ),
        (
            "2025.12.05_unify_plan_create",
            "Remove deprecated plan-issue command (merged into plan-create)",
            _migrate_remove_plan_issue,
        ),
        (
            "2026.01.05_remove_oak_features_dir",
            "Remove .oak/features/ directory (assets now read from package)",
            _migrate_remove_oak_features_dir,
        ),
        (
            "2026.01.09_remove_ide_settings_config",
            "Remove deprecated IDE settings (now handled by agent settings)",
            _migrate_remove_ide_settings_config,
        ),
        (
            "2026.01.31_mcp_remove_project_flag",
            "Remove --project flag from MCP configs (portability)",
            _migrate_mcp_remove_project_flag,
        ),
        (
            "2026.02.01_populate_initialized_features",
            "Populate initialized_features in state for existing installs",
            _migrate_populate_initialized_features,
        ),
        (
            "2026.02.01_features_to_languages",
            "Convert features config to languages config",
            _migrate_features_to_languages,
        ),
        (
            "2026.02.07_split_user_config",
            "Split machine-local CI settings into user config overlay",
            _migrate_split_user_config,
        ),
        (
            "2026.02.07_restore_user_config_defaults",
            "Restore user-classified CI defaults to project config",
            _migrate_restore_user_config_defaults,
        ),
    ]


def _migrate_gitignore_issue_context(project_root: Path) -> None:
    """Add oak/issue/**/context.json pattern to .gitignore.

    This migration was introduced in the token optimization update to prevent
    raw JSON API responses from being committed to git.

    Args:
        project_root: Project root directory
    """
    ensure_gitignore_has_issue_context(project_root)


def _migrate_copilot_agents_folder(project_root: Path) -> None:
    """Migrate Copilot prompts from .github/prompts to .github/agents.

    Removes legacy oak.*.prompt.md files from .github/prompts.
    The new files will be installed by the upgrade service in the new location.

    Args:
        project_root: Project root directory
    """
    prompts_dir = project_root / ".github" / "prompts"
    if not prompts_dir.exists():
        return

    # Remove legacy open-agent-kit prompt files
    for file in prompts_dir.glob("oak.*.prompt.md"):
        try:
            file.unlink()
        except OSError as e:
            logger.warning(f"Failed to remove legacy prompt file {file}: {e}")

    # Try to remove the directory if it's empty
    try:
        if not any(prompts_dir.iterdir()):
            prompts_dir.rmdir()
    except OSError as e:
        logger.warning(f"Failed to remove empty prompts directory {prompts_dir}: {e}")


def _migrate_features_restructure(project_root: Path) -> None:
    """Migrate to features-based organization.

    This migration cleans up the old .oak/templates/ directory structure.
    Features are now always enabled (not user-selectable) and all feature
    assets are read directly from the installed package.

    Args:
        project_root: Project root directory
    """
    import shutil

    # Clean up old .oak/templates/ directory if it exists
    old_templates_dir = project_root / ".oak" / "templates"

    if old_templates_dir.exists():
        # Remove old templates directories that have been migrated
        for subdir in ["constitution", "rfc", "commands"]:
            old_subdir = old_templates_dir / subdir
            if old_subdir.exists():
                try:
                    shutil.rmtree(old_subdir)
                except OSError as e:
                    logger.warning(f"Failed to remove old templates subdir {old_subdir}: {e}")

        # Remove ide directory (no longer needed in .oak/)
        old_ide_dir = old_templates_dir / "ide"
        if old_ide_dir.exists():
            try:
                shutil.rmtree(old_ide_dir)
            except OSError as e:
                logger.warning(f"Failed to remove old ide directory {old_ide_dir}: {e}")

        # Try to remove the templates directory if empty
        try:
            if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                old_templates_dir.rmdir()
        except OSError as e:
            logger.warning(f"Failed to remove empty templates directory {old_templates_dir}: {e}")


def _migrate_cleanup_old_templates(project_root: Path) -> None:
    """Remove old .oak/templates/ directory structure.

    This is a follow-up migration to clean up projects that ran the
    features_restructure migration before the cleanup logic was added.

    Note: We no longer create .oak/features/ directories - feature assets
    are now read directly from the installed package.

    Args:
        project_root: Project root directory
    """
    import shutil

    old_templates_dir = project_root / ".oak" / "templates"

    # Clean up old templates directory if it exists
    if old_templates_dir.exists():
        # Remove old templates directories that have been migrated
        for subdir in ["constitution", "rfc", "commands", "ide"]:
            old_subdir = old_templates_dir / subdir
            if old_subdir.exists():
                try:
                    shutil.rmtree(old_subdir)
                except OSError as e:
                    logger.warning(f"Failed to remove old templates subdir {old_subdir}: {e}")

        # Try to remove the templates directory if empty
        try:
            if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                old_templates_dir.rmdir()
        except OSError as e:
            logger.warning(f"Failed to remove empty templates directory {old_templates_dir}: {e}")


def _migrate_remove_plan_issue(project_root: Path) -> None:
    """Remove deprecated plan-issue command files.

    The plan-issue command has been merged into plan-create, which now supports
    both idea-based and issue-based planning through early triage.

    This migration removes:
    - .claude/commands/oak.plan-issue.md
    - .github/agents/oak.plan-issue.md (if exists)

    Args:
        project_root: Project root directory
    """
    # Locations where the deprecated command might exist
    deprecated_files = [
        project_root / ".claude" / "commands" / "oak.plan-issue.md",
        project_root / ".github" / "agents" / "oak.plan-issue.md",
    ]

    for file_path in deprecated_files:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove deprecated file {file_path}: {e}")


def _migrate_remove_oak_features_dir(project_root: Path) -> None:
    """Remove .oak/features/ directory.

    Feature assets (commands, templates) are now read directly from the installed
    package rather than being copied to the user's project. This reduces file
    duplication and simplifies the oak installation footprint.

    Only .oak/config.yaml and .oak/state.yaml are needed in the project.

    Args:
        project_root: Project root directory
    """
    import shutil

    features_dir = project_root / ".oak" / "features"

    if features_dir.exists():
        try:
            shutil.rmtree(features_dir)
        except OSError as e:
            # If removal fails, don't block the migration
            logger.warning(f"Failed to remove .oak/features/ directory: {e}")


def _migrate_remove_ide_settings_config(project_root: Path) -> None:
    """Remove deprecated IDE settings configuration.

    IDE settings have been consolidated into agent settings. This migration
    removes the 'ides' key from config.yaml if present. Agent settings are now
    managed by AgentSettingsService based on configured agents.

    Args:
        project_root: Project root directory
    """
    from open_agent_kit.config.paths import CONFIG_FILE
    from open_agent_kit.utils import read_yaml, write_yaml

    config_path = project_root / CONFIG_FILE
    if not config_path.exists():
        return

    data = read_yaml(config_path)
    if not data:
        return

    # Remove 'ides' key if present
    if "ides" in data:
        del data["ides"]
        write_yaml(config_path, data)


def _migrate_mcp_remove_project_flag(project_root: Path) -> None:
    """Remove --project flag from MCP server configurations.

    MCP configs now use cwd-relative paths instead of absolute --project flags.
    This makes configs portable across machines.

    Args:
        project_root: Project root directory
    """
    import json

    # MCP config files to check (from agent manifests)
    mcp_configs = [
        (".mcp.json", "mcpServers"),  # Claude
        (".cursor/mcp.json", "mcpServers"),  # Cursor
        (".gemini/settings.json", "mcpServers"),  # Gemini
        (".vscode/mcp.json", "servers"),  # Copilot
        ("opencode.json", "mcp"),  # OpenCode
    ]

    for config_file, servers_key in mcp_configs:
        config_path = project_root / config_file
        if not config_path.exists():
            continue

        try:
            with open(config_path) as f:
                config = json.load(f)

            servers = config.get(servers_key, {})
            modified = False

            # Check each server for oak-ci pattern
            for _server_name, server_config in servers.items():
                # Handle standard format: {"command": "oak", "args": ["ci", "mcp", "--project", "<path>"]}
                args = server_config.get("args", [])
                if isinstance(args, list) and len(args) >= 4:
                    if args[:2] == ["ci", "mcp"] and args[2] == "--project":
                        # Remove --project and its value
                        server_config["args"] = ["ci", "mcp"]
                        modified = True

                # Handle opencode format: {"command": ["oak", "ci", "mcp", "--project", "<path>"]}
                cmd = server_config.get("command", [])
                if isinstance(cmd, list) and len(cmd) >= 5:
                    if cmd[:3] == ["oak", "ci", "mcp"] and cmd[3] == "--project":
                        server_config["command"] = ["oak", "ci", "mcp"]
                        modified = True

            if modified:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                logger.info(f"Migrated MCP config {config_path}: removed --project flag")

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to migrate MCP config {config_path}: {e}")


def _migrate_populate_initialized_features(project_root: Path) -> None:
    """Populate initialized_features in state.yaml for existing installs.

    This ensures that existing installs don't re-trigger on_feature_enabled
    hooks when upgrading. All features are considered initialized if the
    .oak directory exists.

    Args:
        project_root: Project root directory
    """
    from open_agent_kit.config.paths import STATE_FILE
    from open_agent_kit.constants import SUPPORTED_FEATURES
    from open_agent_kit.utils import read_yaml, write_yaml

    state_path = project_root / STATE_FILE
    if not state_path.exists():
        return

    data = read_yaml(state_path)
    if not data:
        data = {}

    # If initialized_features already exists and is populated, skip
    if data.get("initialized_features"):
        return

    # For existing installs, mark all features as initialized
    # This prevents re-triggering on_feature_enabled hooks
    data["initialized_features"] = list(SUPPORTED_FEATURES)

    write_yaml(state_path, data)
    logger.info(f"Migrated state {state_path}: populated initialized_features")


def _migrate_features_to_languages(project_root: Path) -> None:
    """Convert old features config to languages config.

    This migration removes the 'features' section from config.yaml and
    adds an empty 'languages' section. Users can add languages later
    via 'oak languages add'.

    Args:
        project_root: Project root directory
    """
    from open_agent_kit.config.paths import CONFIG_FILE
    from open_agent_kit.utils import read_yaml, write_yaml

    config_path = project_root / CONFIG_FILE
    if not config_path.exists():
        return

    data = read_yaml(config_path)
    if not data:
        return

    modified = False

    # Remove features section if present
    if "features" in data:
        del data["features"]
        modified = True

    # Add empty languages section if not present
    if "languages" not in data:
        data["languages"] = {"installed": []}
        modified = True

    if modified:
        write_yaml(config_path, data)
        logger.info(f"Migrated config {config_path}: converted features to languages")


def _migrate_split_user_config(project_root: Path) -> None:
    """Split machine-local CI settings into a user config overlay.

    Reads .oak/config.yaml, separates user-classified keys (embedding,
    summarization, tunnel, log_level, log_rotation, agent provider settings)
    into .oak/config.{machine_id}.yaml, and rewrites the project config
    with only project-classified keys.

    Idempotent: skips if user overlay already exists.

    Args:
        project_root: Project root directory
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        _split_by_classification,
        _user_config_path,
        _write_yaml_config,
    )
    from open_agent_kit.utils import read_yaml

    config_path = project_root / ".oak" / "config.yaml"
    if not config_path.exists():
        return

    # Skip if user overlay already exists (idempotent)
    user_file = _user_config_path(project_root)
    if user_file.exists():
        logger.info(f"User config overlay already exists at {user_file}, skipping migration")
        return

    data = read_yaml(config_path)
    if not data:
        return

    ci_data = data.get("codebase_intelligence")
    if not ci_data or not isinstance(ci_data, dict):
        return

    user_keys, project_keys = _split_by_classification(ci_data)

    if not user_keys:
        # Nothing to split
        return

    # Copy user keys to overlay (project config keeps them as defaults)
    _write_yaml_config(user_file, {"codebase_intelligence": user_keys})
    logger.info(f"Copied user CI settings to {user_file}")


def _migrate_restore_user_config_defaults(project_root: Path) -> None:
    """Restore user-classified CI defaults to project config.

    The original split_user_config migration incorrectly removed
    user-classified keys from the project config. This migration
    restores them from the user overlay so other machines still
    have sensible defaults when they clone.

    Uses deep merge with project config winning, so any values
    already present in the project config are preserved.

    Args:
        project_root: Project root directory
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        _deep_merge,
        _user_config_path,
        _write_yaml_config,
    )
    from open_agent_kit.utils import read_yaml

    config_path = project_root / ".oak" / "config.yaml"
    if not config_path.exists():
        return

    user_file = _user_config_path(project_root)
    if not user_file.exists():
        return  # No overlay, nothing to restore

    user_data = read_yaml(user_file)
    if not user_data:
        return

    user_ci = user_data.get("codebase_intelligence", {})
    if not user_ci or not isinstance(user_ci, dict):
        return

    data = read_yaml(config_path)
    if not data:
        return

    project_ci = data.get("codebase_intelligence", {})
    if not isinstance(project_ci, dict):
        project_ci = {}

    # Merge: project_ci wins for existing keys, user_ci fills in gaps
    restored = _deep_merge(user_ci, project_ci)
    data["codebase_intelligence"] = restored
    _write_yaml_config(config_path, data)
    logger.info(f"Restored user-classified CI defaults to {config_path}")


def run_migrations(
    project_root: Path,
    completed_migrations: set[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Run all pending migrations.

    Args:
        project_root: Project root directory
        completed_migrations: Set of migration IDs that have already been completed

    Returns:
        Tuple of (successful_migrations, failed_migrations)
        - successful_migrations: List of migration IDs that succeeded
        - failed_migrations: List of (migration_id, error_message) tuples
    """
    successful = []
    failed = []

    all_migrations = get_migrations()

    for migration_id, _description, migration_func in all_migrations:
        # Skip if already completed
        if migration_id in completed_migrations:
            continue

        try:
            migration_func(project_root)
            successful.append(migration_id)
        except Exception as e:
            failed.append((migration_id, str(e)))

    return successful, failed
