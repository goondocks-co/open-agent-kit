"""Skill service for managing Agent Skills.

This service manages skills (reusable agent capabilities) that are bundled with
features. Skills are only installed to agents that have the `has_skills` capability
defined in their manifest. Currently supported agents include:
- Claude Code (.claude/skills/)
- Codex CLI (.codex/skills/)
- VS Code Copilot (.github/skills/)
- Gemini CLI (.gemini/skills/)

Directory structure:
- Package skills: {package_root}/features/{feature}/skills/{skill_name}/SKILL.md
- Agent skills: {agent_folder}/{skills_directory}/{skill_name}/SKILL.md

Skills are installed and removed as part of the feature lifecycle - when a feature
is installed, its associated skills are automatically installed (for agents with
skills support). When a feature is removed, its skills are also removed.
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import (
    FEATURE_MANIFEST_FILE,
    FEATURES_DIR,
    SKILL_MANIFEST_FILE,
    SKILLS_DIR,
)
from open_agent_kit.features.codebase_intelligence.cli_command import resolve_ci_cli_command
from open_agent_kit.models.results import SkillInstallResult, SkillRefreshResult, SkillRemoveResult
from open_agent_kit.models.skill import SkillManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import ensure_dir, write_file
from open_agent_kit.utils.naming import feature_name_to_dir as _feature_name_to_dir

logger = logging.getLogger(__name__)

SKILL_CLI_COMMAND_PLACEHOLDER = "{oak-cli-command}"
SKILL_BINARY_NULL_BYTE = b"\x00"


class SkillService:
    """Service for managing Agent Skills.

    Handles skill discovery, installation, and removal. Skills are bundled with
    features and installed to any configured agent that has `has_skills: true`
    in its manifest.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize skill service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.cli_command = resolve_ci_cli_command(self.project_root)

        # Package features directory (where feature manifests/templates/skills are stored)
        # Skills are read directly from the package and installed to agent directories
        # Path: services/skill_service.py -> services/ -> open_agent_kit/
        self.package_features_dir = Path(__file__).parent.parent / FEATURES_DIR

    def _render_skill_text(self, content: str) -> str:
        """Render skill text content with the configured CLI command."""
        return content.replace(SKILL_CLI_COMMAND_PLACEHOLDER, self.cli_command)

    def _load_text_for_render(self, path: Path) -> str | None:
        """Load UTF-8 text content for rendering, or return None for binary content."""
        raw = path.read_bytes()
        if SKILL_BINARY_NULL_BYTE in raw:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _copy_skill_dir(self, source_skill_dir: Path, dest_skill_dir: Path) -> None:
        """Copy a skill directory while rendering text files for CLI command."""
        for source_path in source_skill_dir.rglob("*"):
            relative_path = source_path.relative_to(source_skill_dir)
            dest_path = dest_skill_dir / relative_path

            if source_path.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
                continue

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            text_content = self._load_text_for_render(source_path)
            if text_content is None:
                shutil.copy2(source_path, dest_path)
                continue

            write_file(dest_path, self._render_skill_text(text_content))

    def skill_dirs_differ(self, package_dir: Path, installed_dir: Path) -> bool:
        """Check if skill directories differ after applying CLI-aware rendering."""
        package_files = {
            f.relative_to(package_dir): f for f in package_dir.rglob("*") if f.is_file()
        }
        installed_files = {
            f.relative_to(installed_dir): f for f in installed_dir.rglob("*") if f.is_file()
        }

        if set(package_files.keys()) != set(installed_files.keys()):
            return True

        for rel_path, package_file in package_files.items():
            installed_file = installed_files[rel_path]
            package_text = self._load_text_for_render(package_file)
            installed_text = self._load_text_for_render(installed_file)
            if package_text is not None and installed_text is not None:
                if self._render_skill_text(package_text) != installed_text:
                    return True
                continue

            if package_text is None and installed_text is None:
                if self._files_differ(package_file, installed_file):
                    return True
                continue

            # One side is text and the other is binary; treat as different.
            if package_text is None or installed_text is None:
                return True

        return False

    def _files_differ(self, file1: Path, file2: Path) -> bool:
        """Check if two files differ."""
        try:
            return file1.read_bytes() != file2.read_bytes()
        except OSError:
            return True

    def _get_agents_with_skills_support(self) -> list[tuple[str, Path, str]]:
        """Get configured agents that support skills.

        Returns:
            List of tuples: (agent_name, skills_dir_path, skills_directory_name)
            for each agent that has has_skills: true in its capabilities.
        """
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)
        config = self.config_service.load_config()

        agents_with_skills: list[tuple[str, Path, str]] = []

        for agent_name in config.agents:
            try:
                manifest = agent_service.get_agent_manifest(agent_name)
            except ValueError:
                # Agent may have been renamed/removed — skip gracefully
                # (e.g. "copilot" → "vscode-copilot" migration pending)
                continue
            if manifest and manifest.capabilities.has_skills:
                # Build the skills directory path
                # Use skills_folder override if specified, otherwise use installation.folder
                skills_base = manifest.capabilities.skills_folder or manifest.installation.folder
                skills_base = skills_base.rstrip("/")
                skills_subdir = manifest.capabilities.skills_directory
                skills_path = self.project_root / skills_base / skills_subdir
                agents_with_skills.append((agent_name, skills_path, skills_subdir))

        return agents_with_skills

    def _get_unique_skills_paths(self) -> list[tuple[list[str], Path, str]]:
        """Deduplicate skills paths, grouping agents that share the same directory.

        Returns:
            List of (agent_names, skills_dir_path, skills_directory_name)
            deduplicated by skills_dir_path.
        """
        agents_with_skills = self._get_agents_with_skills_support()
        path_to_agents: dict[Path, tuple[list[str], str]] = {}
        for agent_name, skills_path, skills_subdir in agents_with_skills:
            if skills_path not in path_to_agents:
                path_to_agents[skills_path] = ([], skills_subdir)
            path_to_agents[skills_path][0].append(agent_name)
        return [(names, path, sub) for path, (names, sub) in path_to_agents.items()]

    def _has_skills_capable_agent(self) -> bool:
        """Check if any configured agent supports skills.

        Returns:
            True if at least one configured agent has has_skills: true
        """
        return len(self._get_agents_with_skills_support()) > 0

    def _get_feature_skills_dir(self, feature_name: str) -> Path:
        """Get the skills directory for a feature in the package.

        Args:
            feature_name: Name of the feature

        Returns:
            Path to feature's skills directory
        """
        feature_dir = _feature_name_to_dir(feature_name)
        return self.package_features_dir / feature_dir / SKILLS_DIR

    def list_available_skills(self) -> list[SkillManifest]:
        """List all available skills from all features in the package.

        Returns:
            List of SkillManifest objects for all available skills
        """
        skills: list[SkillManifest] = []

        if not self.package_features_dir.exists():
            return skills

        # Scan each feature directory for skills
        for feature_dir in self.package_features_dir.iterdir():
            if not feature_dir.is_dir():
                continue

            # Check if this is a valid feature (has manifest.yaml)
            if not (feature_dir / FEATURE_MANIFEST_FILE).exists():
                continue

            skills_dir = feature_dir / SKILLS_DIR
            if not skills_dir.exists():
                continue

            # Scan skills in this feature
            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / SKILL_MANIFEST_FILE
                if skill_file.exists():
                    try:
                        manifest = SkillManifest.load(skill_file)
                        skills.append(manifest)
                    except (FileNotFoundError, ValueError):
                        # Skip invalid skill manifests
                        continue

        return sorted(skills, key=lambda s: s.name)

    def get_skill_manifest(self, skill_name: str) -> SkillManifest | None:
        """Get manifest for a specific skill by searching all features.

        Args:
            skill_name: Name of the skill

        Returns:
            SkillManifest or None if not found
        """
        skill_path = self._find_skill_in_features(skill_name)
        if skill_path:
            try:
                return SkillManifest.load(skill_path)
            except (FileNotFoundError, ValueError):
                return None
        return None

    def _find_skill_in_features(self, skill_name: str) -> Path | None:
        """Find a skill's SKILL.md path by searching all feature directories.

        Args:
            skill_name: Name of the skill

        Returns:
            Path to SKILL.md or None if not found
        """
        if not self.package_features_dir.exists():
            return None

        for feature_dir in self.package_features_dir.iterdir():
            if not feature_dir.is_dir():
                continue

            skill_file = feature_dir / SKILLS_DIR / skill_name / SKILL_MANIFEST_FILE
            if skill_file.exists():
                return skill_file

        return None

    def _find_skill_dir_in_features(self, skill_name: str) -> Path | None:
        """Find a skill's directory path by searching all feature directories.

        Args:
            skill_name: Name of the skill

        Returns:
            Path to skill directory or None if not found
        """
        if not self.package_features_dir.exists():
            return None

        for feature_dir in self.package_features_dir.iterdir():
            if not feature_dir.is_dir():
                continue

            skill_dir = feature_dir / SKILLS_DIR / skill_name
            if skill_dir.exists() and (skill_dir / SKILL_MANIFEST_FILE).exists():
                return skill_dir

        return None

    def get_feature_for_skill(self, skill_name: str) -> str | None:
        """Get the feature name that contains a given skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Feature name or None if not found
        """
        if not self.package_features_dir.exists():
            return None

        for feature_dir in self.package_features_dir.iterdir():
            if not feature_dir.is_dir():
                continue

            skill_dir = feature_dir / SKILLS_DIR / skill_name
            if skill_dir.exists():
                return feature_dir.name

        return None

    def list_installed_skills(self) -> list[str]:
        """List skills currently installed in the project.

        Returns:
            List of installed skill names
        """
        config = self.config_service.load_config()
        return config.skills.installed

    def is_skill_installed(self, skill_name: str) -> bool:
        """Check if a skill is installed.

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill is installed
        """
        return skill_name in self.list_installed_skills()

    def get_skills_for_feature(self, feature_name: str) -> list[str]:
        """Get list of skills available in a feature's skills directory.

        Args:
            feature_name: Name of the feature

        Returns:
            List of skill names in the feature
        """
        skills: list[str] = []
        skills_dir = self._get_feature_skills_dir(feature_name)

        if not skills_dir.exists():
            return skills

        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / SKILL_MANIFEST_FILE).exists():
                skills.append(skill_dir.name)

        return sorted(skills)

    def install_skill(self, skill_name: str, feature_name: str | None = None) -> SkillInstallResult:
        """Install a skill to all agents that support skills.

        Args:
            skill_name: Name of the skill to install
            feature_name: Optional feature name (for finding skill location)

        Returns:
            SkillInstallResult with installation details.
        """
        results: SkillInstallResult = {
            "skill_name": skill_name,
            "installed_to": [],
            "agents": [],
            "already_installed": False,
            "skipped": False,
        }

        # Get unique skills paths (deduped across agents sharing the same dir)
        unique_paths = self._get_unique_skills_paths()
        if not unique_paths:
            results["skipped"] = True
            results["reason"] = "No configured agents support skills"
            return results

        # Check if already installed
        if self.is_skill_installed(skill_name):
            results["already_installed"] = True
            return results

        # Find source skill directory in package
        source_skill_dir = self._find_skill_dir_in_features(skill_name)
        if not source_skill_dir:
            results["error"] = f"Skill not found: {skill_name}"
            return results

        # Install once per unique skills directory (copy entire directory)
        for agent_names, skills_dir, _ in unique_paths:
            dest_skill_dir = skills_dir / skill_name
            # Remove existing directory if present (clean install)
            if dest_skill_dir.exists():
                shutil.rmtree(dest_skill_dir)
            # Copy and render markdown content with configured CLI command
            self._copy_skill_dir(source_skill_dir, dest_skill_dir)
            results["installed_to"].append(str(dest_skill_dir.relative_to(self.project_root)))
            results["agents"].extend(agent_names)

        # Update config to mark skill as installed
        config = self.config_service.load_config()
        if skill_name not in config.skills.installed:
            config.skills.installed.append(skill_name)
            self.config_service.save_config(config)

        return results

    def install_skills_for_feature(self, feature_name: str) -> dict[str, Any]:
        """Install all skills for a feature (for agents that support skills).

        Args:
            feature_name: Name of the feature

        Returns:
            Dictionary with installation results:
            {
                'feature_name': 'plan',
                'skills_available': ['planning-workflow', 'research-synthesis'],
                'skills_installed': ['planning-workflow'],
                'skills_already_installed': ['research-synthesis'],
                'skills_skipped': [],
                'agents': ['claude'],
                'errors': []
            }
        """
        results: dict[str, Any] = {
            "feature_name": feature_name,
            "skills_available": [],
            "skills_installed": [],
            "skills_already_installed": [],
            "skills_skipped": [],
            "agents": [],
            "errors": [],
        }

        # Get skills for feature from the skills directory
        skills = self.get_skills_for_feature(feature_name)
        results["skills_available"] = skills

        if not skills:
            return results

        # Check if any agent supports skills (early exit)
        if not self._has_skills_capable_agent():
            results["skills_skipped"] = skills
            results["reason"] = "No configured agents support skills"
            return results

        # Install each skill
        for skill_name in skills:
            install_result = self.install_skill(skill_name, feature_name)

            if "error" in install_result:
                results["errors"].append(install_result["error"])
            elif install_result.get("already_installed"):
                results["skills_already_installed"].append(skill_name)
            elif install_result.get("skipped"):
                results["skills_skipped"].append(skill_name)
            else:
                results["skills_installed"].append(skill_name)
                # Track which agents got skills
                for agent in install_result.get("agents", []):
                    if agent not in results["agents"]:
                        results["agents"].append(agent)

        return results

    def remove_skill(self, skill_name: str) -> SkillRemoveResult:
        """Remove a skill from the project.

        Args:
            skill_name: Name of the skill to remove

        Returns:
            SkillRemoveResult with removal details.
        """
        results: SkillRemoveResult = {
            "skill_name": skill_name,
            "removed_from": [],
            "agents": [],
            "not_installed": False,
        }

        # Check if installed
        if not self.is_skill_installed(skill_name):
            results["not_installed"] = True
            return results

        # Remove once per unique skills directory
        unique_paths = self._get_unique_skills_paths()
        for agent_names, skills_dir, _ in unique_paths:
            skill_dir = skills_dir / skill_name
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
                results["removed_from"].append(str(skill_dir.relative_to(self.project_root)))
                results["agents"].extend(agent_names)

        # Update config to mark skill as uninstalled
        config = self.config_service.load_config()
        if skill_name in config.skills.installed:
            config.skills.installed.remove(skill_name)
            self.config_service.save_config(config)

        return results

    def remove_skills_for_feature(self, feature_name: str) -> dict[str, Any]:
        """Remove all skills associated with a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Dictionary with removal results:
            {
                'feature_name': 'plan',
                'skills_removed': ['planning-workflow', 'research-synthesis'],
                'errors': []
            }
        """
        results: dict[str, Any] = {
            "feature_name": feature_name,
            "skills_removed": [],
            "errors": [],
        }

        # Get skills for this feature
        skills = self.get_skills_for_feature(feature_name)

        for skill_name in skills:
            if self.is_skill_installed(skill_name):
                remove_result = self.remove_skill(skill_name)
                if "error" in remove_result:
                    results["errors"].append(remove_result["error"])
                elif not remove_result.get("not_installed"):
                    results["skills_removed"].append(skill_name)

        return results

    def cleanup_skills_for_removed_agents(self, removed_agents: list[str]) -> dict[str, Any]:
        """Remove skills directories for agents that were removed.

        When an agent is removed from the configuration, this method cleans up
        the skills that were installed in that agent's skills directory.

        Args:
            removed_agents: List of agent type names that were removed

        Returns:
            Dictionary with cleanup results:
            {
                'agents_cleaned': ['codex'],
                'skills_removed': ['planning-workflow', 'research-synthesis'],
                'directories_removed': ['.codex/skills/planning-workflow'],
                'errors': []
            }
        """
        from open_agent_kit.services.agent_service import AgentService

        results: dict[str, Any] = {
            "agents_cleaned": [],
            "skills_removed": [],
            "directories_removed": [],
            "errors": [],
        }

        agent_service = AgentService(self.project_root)

        # Collect paths still in use by remaining configured agents
        remaining_paths = {p for _, p, _ in self._get_agents_with_skills_support()}

        for agent_type in removed_agents:
            # Get agent manifest to find skills directory
            manifest = agent_service.get_agent_manifest(agent_type)
            if not manifest:
                continue

            # Check if agent supports skills
            if not manifest.capabilities.has_skills:
                continue

            # Build the skills directory path
            # Use skills_folder override if specified, otherwise use installation.folder
            skills_base = manifest.capabilities.skills_folder or manifest.installation.folder
            skills_base = skills_base.rstrip("/")
            skills_subdir = manifest.capabilities.skills_directory
            skills_dir = self.project_root / skills_base / skills_subdir

            if not skills_dir.exists():
                continue

            # If other agents still use this shared path, skip cleanup
            if skills_dir in remaining_paths:
                continue

            # Remove all skill subdirectories
            try:
                for skill_dir in skills_dir.iterdir():
                    if skill_dir.is_dir():
                        skill_name = skill_dir.name
                        shutil.rmtree(skill_dir)
                        results["directories_removed"].append(
                            str(skill_dir.relative_to(self.project_root))
                        )
                        if skill_name not in results["skills_removed"]:
                            results["skills_removed"].append(skill_name)

                # Try to remove the skills directory if empty
                if skills_dir.exists() and not any(skills_dir.iterdir()):
                    skills_dir.rmdir()

                results["agents_cleaned"].append(agent_type)
            except Exception as e:
                results["errors"].append(f"Error cleaning skills for {agent_type}: {e}")

        return results

    def refresh_skills(self) -> SkillRefreshResult:
        """Refresh all installed skills by re-copying from package.

        This updates skill content to match the latest package versions.
        Only refreshes for agents that support skills.

        Returns:
            SkillRefreshResult with refresh details.
        """
        results: SkillRefreshResult = {
            "skills_refreshed": [],
            "agents": [],
            "errors": [],
        }

        # Get unique skills paths (deduped across agents sharing the same dir)
        unique_paths = self._get_unique_skills_paths()
        if not unique_paths:
            results["skipped"] = True
            results["reason"] = "No configured agents support skills"
            return results

        # Get installed skills
        installed_skills = self.list_installed_skills()

        for skill_name in installed_skills:
            # Find source skill directory in package
            source_skill_dir = self._find_skill_dir_in_features(skill_name)
            if not source_skill_dir:
                results["errors"].append(f"Skill not found in package: {skill_name}")
                continue

            # Re-install once per unique skills directory
            for agent_names, skills_dir, _ in unique_paths:
                dest_skill_dir = skills_dir / skill_name
                # Remove existing directory and copy fresh (handles subdirectory changes)
                if dest_skill_dir.exists():
                    shutil.rmtree(dest_skill_dir)
                self._copy_skill_dir(source_skill_dir, dest_skill_dir)
                for agent_name in agent_names:
                    if agent_name not in results["agents"]:
                        results["agents"].append(agent_name)

            results["skills_refreshed"].append(skill_name)

        return results

    def upgrade_skill(self, skill_name: str) -> dict[str, Any]:
        """Upgrade a specific skill to the latest package version.

        Args:
            skill_name: Name of the skill to upgrade

        Returns:
            Dictionary with upgrade results:
            {
                'skill_name': 'planning-workflow',
                'upgraded': True,
                'old_version': '1.0.0',
                'new_version': '1.1.0',
                'agents': ['claude']
            }
        """
        results: dict[str, Any] = {
            "skill_name": skill_name,
            "upgraded": False,
            "agents": [],
        }

        # Check if installed
        if not self.is_skill_installed(skill_name):
            results["error"] = f"Skill not installed: {skill_name}"
            return results

        # Get unique skills paths (deduped across agents sharing the same dir)
        unique_paths = self._get_unique_skills_paths()
        if not unique_paths:
            results["error"] = "No configured agents support skills"
            return results

        # Get current version from first unique path's installed skill
        first_agent_names, first_skills_dir, _ = unique_paths[0]
        skill_file = first_skills_dir / skill_name / SKILL_MANIFEST_FILE
        if skill_file.exists():
            try:
                current_manifest = SkillManifest.load(skill_file)
                results["old_version"] = current_manifest.version
            except (FileNotFoundError, ValueError):
                results["old_version"] = "unknown"
        else:
            results["old_version"] = "unknown"

        # Find source skill directory in package
        source_skill_dir = self._find_skill_dir_in_features(skill_name)
        if not source_skill_dir:
            results["error"] = f"Skill not found in package: {skill_name}"
            return results

        # Get new version from package manifest
        manifest = self.get_skill_manifest(skill_name)
        if manifest:
            results["new_version"] = manifest.version
        else:
            results["new_version"] = "unknown"

        # Re-install once per unique skills directory
        for agent_names, skills_dir, _ in unique_paths:
            dest_skill_dir = skills_dir / skill_name
            # Remove existing directory and copy fresh (handles subdirectory changes)
            if dest_skill_dir.exists():
                shutil.rmtree(dest_skill_dir)
            self._copy_skill_dir(source_skill_dir, dest_skill_dir)
            results["agents"].extend(agent_names)

        results["upgraded"] = True
        return results

    def remove_obsolete_skills(self) -> dict[str, Any]:
        """Remove skills that are installed but no longer exist in any feature.

        This handles cases like renamed skills (e.g., adding-project-rules -> project-rules)
        where the old skill should be removed and the new one installed.

        Returns:
            Dictionary with removal results:
            {
                'skills_removed': ['old-skill-name'],
                'agents': ['claude'],
                'errors': []
            }
        """
        from open_agent_kit.constants import SUPPORTED_FEATURES

        results: dict[str, Any] = {
            "skills_removed": [],
            "agents": [],
            "errors": [],
        }

        # All features are always enabled
        enabled_features = SUPPORTED_FEATURES

        all_valid_skills: set[str] = set()
        for feature_name in enabled_features:
            feature_skills = self.get_skills_for_feature(feature_name)
            all_valid_skills.update(feature_skills)

        # Get currently installed skills
        installed_skills = set(self.list_installed_skills())

        # Find obsolete skills (installed but not in any feature)
        obsolete_skills = installed_skills - all_valid_skills

        # Remove each obsolete skill
        for skill_name in obsolete_skills:
            remove_result = self.remove_skill(skill_name)
            if "error" in remove_result:
                results["errors"].append(remove_result["error"])
            elif not remove_result.get("not_installed"):
                results["skills_removed"].append(skill_name)
                for agent in remove_result.get("agents", []):
                    if agent not in results["agents"]:
                        results["agents"].append(agent)

        return results

    def create_skill_scaffold(
        self, skill_name: str, description: str, output_dir: Path | None = None
    ) -> Path:
        """Create a new skill scaffold with basic structure.

        Args:
            skill_name: Name for the skill (e.g., 'api-design')
            description: Brief description of the skill
            output_dir: Directory to create skill in (defaults to project .oak/skills/)

        Returns:
            Path to created SKILL.md file
        """
        if output_dir is None:
            output_dir = self.project_root / ".oak" / SKILLS_DIR

        # Create skill directory
        skill_dir = output_dir / skill_name
        ensure_dir(skill_dir)

        # Create manifest
        display_name = skill_name.replace("-", " ").title()
        body_content = (
            f"# {display_name}\n\n{description}\n\n## Usage\n\nDescribe how to use this skill.\n"
        )

        manifest = SkillManifest(
            name=skill_name,
            description=description,
            version="1.0.0",
            allowed_tools=[],
            body=body_content,
        )

        # Save manifest
        skill_file = skill_dir / SKILL_MANIFEST_FILE
        write_file(skill_file, manifest.to_skill_file())

        return skill_file


def get_skill_service(project_root: Path | None = None) -> SkillService:
    """Get a SkillService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        SkillService instance
    """
    return SkillService(project_root)
