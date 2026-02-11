"""Migration system for open-agent-kit upgrades.

This module provides a framework for running one-time migrations during upgrades.
Each migration is a function that gets executed once based on version tracking.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def _cleanup_builtin_agent_tasks(project_root: Path) -> None:
    """Remove redundant built-in task copies from oak/agents/.

    Built-in agent tasks are now loaded directly from the package by
    AgentRegistry._load_builtin_tasks(). Copies in oak/agents/ with
    ``is_builtin: true`` are unnecessary and were previously overwritten
    on every upgrade anyway. User-created tasks (which never have
    ``is_builtin: true`` — copy_task() strips it) are preserved.
    """
    import yaml

    from open_agent_kit.features.codebase_intelligence.constants import (
        AGENT_PROJECT_CONFIG_DIR,
        AGENT_PROJECT_CONFIG_EXTENSION,
    )

    agents_dir = project_root / AGENT_PROJECT_CONFIG_DIR
    if not agents_dir.is_dir():
        return

    for yaml_file in sorted(agents_dir.glob(f"*{AGENT_PROJECT_CONFIG_EXTENSION}")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and data.get("is_builtin") is True:
                yaml_file.unlink()
                logger.info(f"Removed built-in task copy: {yaml_file.name}")
        except Exception as e:
            logger.warning(f"Failed to check/remove {yaml_file.name}: {e}")

    # Remove the directory if it's now empty
    try:
        if agents_dir.is_dir() and not any(agents_dir.iterdir()):
            agents_dir.rmdir()
            logger.info(f"Removed empty directory: {agents_dir}")
    except OSError as e:
        logger.warning(f"Failed to remove empty agents directory: {e}")


def _cleanup_skill_generate_scripts(project_root: Path) -> None:
    """Remove build-time generate_*.py scripts from installed skill directories.

    These scripts are dev tools that should not be distributed to agent skill
    folders. They were previously copied by SkillService._copy_skill_dir()
    because they lived inside the skill source directory.
    """
    from open_agent_kit.services.agent_service import AgentService
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(project_root)
    agent_service = AgentService(project_root)

    try:
        config = config_service.load_config()
    except Exception:
        return

    for agent_name in config.agents:
        manifest = agent_service.get_agent_manifest(agent_name)
        if not manifest or not manifest.capabilities.has_skills:
            continue

        skills_base = manifest.capabilities.skills_folder or manifest.installation.folder
        skills_base = skills_base.rstrip("/")
        skills_subdir = manifest.capabilities.skills_directory
        skills_path = project_root / skills_base / skills_subdir

        target = skills_path / "codebase-intelligence" / "generate_schema_ref.py"
        if target.is_file():
            target.unlink()
            logger.info(f"Removed stale build script: {target.relative_to(project_root)}")


def get_migrations() -> list[tuple[str, str, Callable[[Path], None]]]:
    """Get all available migrations.

    Returns:
        List of tuples: (migration_id, description, migration_function)
        Migrations are executed in order when running upgrades.
    """
    return [
        (
            "cleanup-builtin-agent-tasks",
            "Remove redundant built-in task copies from oak/agents/",
            _cleanup_builtin_agent_tasks,
        ),
        (
            "cleanup-skill-generate-scripts",
            "Remove build-time generate scripts from installed skill directories",
            _cleanup_skill_generate_scripts,
        ),
    ]


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
