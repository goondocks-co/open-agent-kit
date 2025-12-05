"""Migration system for open-agent-kit upgrades.

This module provides a framework for running one-time migrations during upgrades.
Each migration is a function that gets executed once based on version tracking.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from open_agent_kit.utils import ensure_gitignore_has_issue_context


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
        except Exception:
            pass

    # Try to remove the directory if it's empty
    try:
        if not any(prompts_dir.iterdir()):
            prompts_dir.rmdir()
    except Exception:
        pass


def _migrate_features_restructure(project_root: Path) -> None:
    """Migrate to features-based organization.

    This migration:
    1. Infers enabled features from installed commands
    2. Updates config.yaml with features.enabled list
    3. Removes the old .oak/templates/ directory structure

    Args:
        project_root: Project root directory
    """
    import shutil

    from open_agent_kit.config.paths import CONFIG_FILE
    from open_agent_kit.constants import DEFAULT_FEATURES, FEATURE_CONFIG, SUPPORTED_FEATURES
    from open_agent_kit.utils import read_yaml

    config_path = project_root / CONFIG_FILE
    if not config_path.exists():
        return

    # Load current config
    data = read_yaml(config_path)
    if not data:
        return

    # Check if features already configured (but still run cleanup)
    features_already_configured = "features" in data and data["features"].get("enabled")

    if not features_already_configured:
        # Infer features from installed commands
        # Look in .claude/commands/ for oak.* files
        enabled_features: set[str] = set()

        claude_commands_dir = project_root / ".claude" / "commands"
        if claude_commands_dir.exists():
            for cmd_file in claude_commands_dir.glob("oak.*.md"):
                cmd_name = cmd_file.stem.replace("oak.", "")

                # Find which feature this command belongs to
                for feature_name in SUPPORTED_FEATURES:
                    feature_config = FEATURE_CONFIG.get(feature_name, {})
                    commands = cast(list[str], feature_config.get("commands", []))
                    if cmd_name in commands:
                        enabled_features.add(feature_name)
                        break

        # If no commands found, use defaults
        if not enabled_features:
            enabled_features = set(DEFAULT_FEATURES)

        # Add dependencies (constitution is required by rfc and issues)
        if "rfc" in enabled_features or "issues" in enabled_features:
            enabled_features.add("constitution")

        # Update config with features
        from open_agent_kit.models.config import OakConfig

        config = OakConfig.load(config_path)
        config.features.enabled = sorted(enabled_features)
        config.save(config_path)

    # Clean up old .oak/templates/ directory if new structure exists
    old_templates_dir = project_root / ".oak" / "templates"
    new_features_dir = project_root / ".oak" / "features"

    if old_templates_dir.exists() and new_features_dir.exists():
        # Remove old templates directories that have been migrated
        for subdir in ["constitution", "rfc", "commands"]:
            old_subdir = old_templates_dir / subdir
            if old_subdir.exists():
                try:
                    shutil.rmtree(old_subdir)
                except Exception:
                    pass

        # Remove ide directory (no longer needed in .oak/)
        old_ide_dir = old_templates_dir / "ide"
        if old_ide_dir.exists():
            try:
                shutil.rmtree(old_ide_dir)
            except Exception:
                pass

        # Try to remove the templates directory if empty
        try:
            if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                old_templates_dir.rmdir()
        except Exception:
            pass


def _migrate_cleanup_old_templates(project_root: Path) -> None:
    """Remove old .oak/templates/ directory structure and ensure feature directories exist.

    This is a follow-up migration to clean up projects that ran the
    features_restructure migration before the cleanup logic was added.

    Args:
        project_root: Project root directory
    """
    import shutil

    from open_agent_kit.config.paths import CONFIG_FILE
    from open_agent_kit.utils import read_yaml

    old_templates_dir = project_root / ".oak" / "templates"
    new_features_dir = project_root / ".oak" / "features"

    # Ensure features directory exists
    new_features_dir.mkdir(parents=True, exist_ok=True)

    # Create directories for all enabled features
    config_path = project_root / CONFIG_FILE
    if config_path.exists():
        data = read_yaml(config_path)
        if data and "features" in data:
            enabled_features = data["features"].get("enabled", [])
            for feature_name in enabled_features:
                feature_dir = new_features_dir / feature_name
                feature_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old templates directory if it exists
    if old_templates_dir.exists():
        # Remove old templates directories that have been migrated
        for subdir in ["constitution", "rfc", "commands", "ide"]:
            old_subdir = old_templates_dir / subdir
            if old_subdir.exists():
                try:
                    shutil.rmtree(old_subdir)
                except Exception:
                    pass

        # Try to remove the templates directory if empty
        try:
            if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                old_templates_dir.rmdir()
        except Exception:
            pass


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
