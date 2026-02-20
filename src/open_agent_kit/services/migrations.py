"""Migration system for open-agent-kit upgrades.

This module provides a framework for running one-time migrations during upgrades.
Each migration is a function that gets executed once based on version tracking.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from open_agent_kit.models.enums import HookType

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
    except (OSError, ValueError):
        return

    for agent_name in config.agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
        except ValueError:
            continue
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


def _hooks_local_only(project_root: Path) -> None:
    """Make hook config files local-only (gitignored, not committed).

    For each configured agent:
    1. Compute hook file path from manifest
    2. Add .gitignore entry
    3. Run ``git rm --cached`` to untrack (best-effort)
    4. Claude special case: move hooks from settings.json -> settings.local.json
    """
    import subprocess

    from open_agent_kit.services.agent_service import AgentService
    from open_agent_kit.services.config_service import ConfigService
    from open_agent_kit.utils.env_utils import add_gitignore_entries

    try:
        config_service = ConfigService(project_root)
        config = config_service.load_config()
    except (OSError, ValueError):
        return

    if not config.agents:
        return

    agent_service = AgentService(project_root)
    gitignore_entries: list[str] = []

    for agent_name in config.agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
        except (OSError, ValueError):
            continue

        if not manifest or not manifest.hooks:
            continue

        hooks_config = manifest.hooks
        folder = manifest.installation.folder.rstrip("/")

        # Determine the hook file path from manifest
        if hooks_config.type == HookType.PLUGIN:
            if hooks_config.plugin_dir and hooks_config.plugin_file:
                hook_rel = f"{folder}/{hooks_config.plugin_dir}/{hooks_config.plugin_file}"
            else:
                continue
        elif hooks_config.config_file:
            hook_rel = f"{folder}/{hooks_config.config_file}"
        else:
            continue

        gitignore_entries.append(hook_rel)

        # Best-effort: untrack the file from git index
        hook_abs = project_root / hook_rel
        if hook_abs.exists():
            try:
                subprocess.run(
                    ["git", "rm", "--cached", "--quiet", hook_rel],
                    cwd=project_root,
                    capture_output=True,
                    check=False,
                )
            except FileNotFoundError:
                pass  # git not installed

        # Claude special case: move hooks from settings.json -> settings.local.json
        if agent_name == "claude":
            _migrate_claude_hooks_to_local(project_root, folder)

    if gitignore_entries:
        add_gitignore_entries(
            project_root,
            gitignore_entries,
            section_comment="open-agent-kit: CI hook configs (local-only, regenerated by oak ci start)",
        )


def _migrate_claude_hooks_to_local(project_root: Path, folder: str) -> None:
    """Move Claude hooks from settings.json to settings.local.json.

    Reads the ``hooks`` key from settings.json, merges it into
    settings.local.json, then cleans up settings.json.
    """
    import json
    import subprocess

    old_path = project_root / folder / "settings.json"
    new_path = project_root / folder / "settings.local.json"

    if not old_path.exists():
        return

    try:
        with open(old_path) as f:
            old_config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    hooks_data = old_config.get("hooks")
    if not hooks_data:
        return

    # Merge hooks into settings.local.json
    local_config: dict = {}
    if new_path.exists():
        try:
            with open(new_path) as f:
                local_config = json.load(f)
        except (OSError, json.JSONDecodeError):
            local_config = {}

    local_config["hooks"] = hooks_data

    new_path.parent.mkdir(parents=True, exist_ok=True)
    with open(new_path, "w") as f:
        json.dump(local_config, f, indent=2)

    # Remove hooks key from settings.json
    del old_config["hooks"]

    # If settings.json only has $schema (or is empty), remove it entirely
    remaining_keys = {k for k in old_config if k != "$schema"}
    if not remaining_keys:
        old_path.unlink()
        logger.info(f"Removed empty {old_path.relative_to(project_root)}")
        # Untrack from git
        try:
            subprocess.run(
                ["git", "rm", "--cached", "--quiet", str(old_path.relative_to(project_root))],
                cwd=project_root,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            pass
    else:
        with open(old_path, "w") as f:
            json.dump(old_config, f, indent=2)

    logger.info("Migrated Claude hooks from settings.json to settings.local.json")


def _migrate_copilot_to_vscode_copilot(project_root: Path) -> None:
    """Rename 'copilot' agent to 'vscode-copilot' in config and remove old-format hooks.

    1. Updates .oak/config.yaml agents list: replaces "copilot" with "vscode-copilot".
    2. Removes .github/hooks/oak-ci-hooks.json if it contains old-format hooks
       (detected by "bash"/"powershell" keys or "--agent copilot" pattern).
    """
    import json

    import yaml

    config_path = project_root / ".oak" / "config.yaml"
    if config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if isinstance(config_data, dict):
                agents = config_data.get("agents", [])
                if isinstance(agents, list) and "copilot" in agents:
                    config_data["agents"] = [
                        "vscode-copilot" if a == "copilot" else a for a in agents
                    ]
                    with open(config_path, "w", encoding="utf-8") as f:
                        yaml.safe_dump(config_data, f, default_flow_style=False)
                    logger.info(
                        "Renamed 'copilot' to 'vscode-copilot' in .oak/config.yaml agents list"
                    )
        except Exception as e:
            logger.warning(f"Failed to update .oak/config.yaml for copilot rename: {e}")

    # Remove old-format hooks file if it exists and contains old-format hooks
    old_hooks_path = project_root / ".github" / "hooks" / "oak-ci-hooks.json"
    if old_hooks_path.is_file():
        try:
            content = old_hooks_path.read_text(encoding="utf-8")
            # Detect old-format hooks by presence of shell keys or old agent flag
            is_old_format = (
                '"bash"' in content or '"powershell"' in content or "--agent copilot" in content
            )
            if is_old_format:
                old_hooks_path.unlink()
                logger.info("Removed old-format hooks file: .github/hooks/oak-ci-hooks.json")
                # Clean up empty parent directories
                hooks_dir = old_hooks_path.parent
                try:
                    if hooks_dir.is_dir() and not any(hooks_dir.iterdir()):
                        hooks_dir.rmdir()
                except OSError:
                    pass
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to check/remove old hooks file: {e}")


def _migrate_skills_to_shared_agents_dir(project_root: Path) -> None:
    """Move skills from agent-specific dirs to shared .agents/skills/ for supported agents.

    Agents that now read .agents/skills/ (codex, gemini, vscode-copilot, windsurf, opencode)
    previously had skills in their own folders (e.g., .codex/skills/, .gemini/skills/).
    This migration copies skills to .agents/skills/ and removes the old directories.
    """
    import shutil

    from open_agent_kit.config.paths import SHARED_SKILLS_FOLDER
    from open_agent_kit.services.agent_service import AgentService
    from open_agent_kit.services.config_service import ConfigService

    try:
        config_service = ConfigService(project_root)
        config = config_service.load_config()
    except (OSError, ValueError):
        return

    installed_skills = config.skills.installed
    if not installed_skills:
        return

    agent_service = AgentService(project_root)

    # Identify agents that now use .agents/ but previously used their own folder
    shared_agents: list[str] = []
    for agent_name in config.agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
        except ValueError:
            continue
        if not manifest or not manifest.capabilities.has_skills:
            continue
        if manifest.capabilities.skills_folder == SHARED_SKILLS_FOLDER:
            shared_agents.append(agent_name)

    if not shared_agents:
        return

    shared_skills_dir = project_root / SHARED_SKILLS_FOLDER / "skills"

    for skill_name in installed_skills:
        dest = shared_skills_dir / skill_name
        if dest.exists():
            continue  # Already present in shared location

        # Try to copy from any old agent-specific location
        for agent_name in shared_agents:
            try:
                manifest = agent_service.get_agent_manifest(agent_name)
            except ValueError:
                continue
            old_dir = (
                project_root
                / manifest.installation.folder.rstrip("/")
                / manifest.capabilities.skills_directory
                / skill_name
            )
            if old_dir.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(old_dir, dest)
                logger.info(
                    f"Copied skill '{skill_name}' from {old_dir.relative_to(project_root)} "
                    f"to {dest.relative_to(project_root)}"
                )
                break

    # Clean up old agent-specific skill directories for shared agents
    for agent_name in shared_agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
        except ValueError:
            continue
        old_skills_dir = (
            project_root
            / manifest.installation.folder.rstrip("/")
            / manifest.capabilities.skills_directory
        )
        if old_skills_dir.exists():
            shutil.rmtree(old_skills_dir)
            logger.info(f"Removed old skills directory: {old_skills_dir.relative_to(project_root)}")


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
        (
            "hooks-local-only",
            "Make hook config files local-only (gitignored, not committed)",
            _hooks_local_only,
        ),
        (
            "rename-copilot-to-vscode-copilot",
            "Rename copilot agent to vscode-copilot and remove old-format hooks",
            _migrate_copilot_to_vscode_copilot,
        ),
        (
            "migrate-skills-to-shared-agents-dir",
            "Move skills from agent-specific dirs to shared .agents/skills/",
            _migrate_skills_to_shared_agents_dir,
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
