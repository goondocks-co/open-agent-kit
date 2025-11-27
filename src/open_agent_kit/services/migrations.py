"""Migration system for open-agent-kit upgrades.

This module provides a framework for running one-time migrations during upgrades.
Each migration is a function that gets executed once based on version tracking.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
