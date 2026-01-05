"""Skill service for managing Agent Skills.

This service manages skills (reusable agent capabilities) that are bundled with
features. Skills are only installed to agents that have the `has_skills` capability
defined in their manifest (currently only Claude Code).

Directory structure:
- Package skills: {package_root}/features/{feature}/skills/{skill_name}/SKILL.md
- Agent skills: {agent_folder}/{skills_directory}/{skill_name}/SKILL.md

Skills are installed and removed as part of the feature lifecycle - when a feature
is installed, its associated skills are automatically installed (for agents with
skills support). When a feature is removed, its skills are also removed.
"""

import shutil
from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import (
    FEATURE_MANIFEST_FILE,
    FEATURES_DIR,
    SKILL_MANIFEST_FILE,
    SKILLS_DIR,
)
from open_agent_kit.models.skill import SkillManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import ensure_dir, write_file


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

        # Package features directory (where feature manifests/templates/skills are stored)
        # Skills are read directly from the package and installed to agent directories
        self.package_features_dir = Path(__file__).parent.parent.parent.parent / FEATURES_DIR

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
            manifest = agent_service.get_agent_manifest(agent_name)
            if manifest and manifest.capabilities.has_skills:
                # Build the skills directory path: {agent_folder}/{skills_directory}
                agent_folder = manifest.installation.folder.rstrip("/")
                skills_subdir = manifest.capabilities.skills_directory
                skills_path = self.project_root / agent_folder / skills_subdir
                agents_with_skills.append((agent_name, skills_path, skills_subdir))

        return agents_with_skills

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
        return self.package_features_dir / feature_name / SKILLS_DIR

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

    def install_skill(self, skill_name: str, feature_name: str | None = None) -> dict[str, Any]:
        """Install a skill to all agents that support skills.

        Args:
            skill_name: Name of the skill to install
            feature_name: Optional feature name (for finding skill location)

        Returns:
            Dictionary with installation results:
            {
                'skill_name': 'planning-workflow',
                'installed_to': ['.claude/skills/planning-workflow'],
                'agents': ['claude'],
                'already_installed': False,
                'skipped': False  # True if no agents support skills
            }
        """
        results: dict[str, Any] = {
            "skill_name": skill_name,
            "installed_to": [],
            "agents": [],
            "already_installed": False,
            "skipped": False,
        }

        # Get agents that support skills
        agents_with_skills = self._get_agents_with_skills_support()
        if not agents_with_skills:
            results["skipped"] = True
            results["reason"] = "No configured agents support skills"
            return results

        # Check if already installed
        if self.is_skill_installed(skill_name):
            results["already_installed"] = True
            return results

        # Get skill manifest from package
        manifest = self.get_skill_manifest(skill_name)
        if not manifest:
            results["error"] = f"Skill not found: {skill_name}"
            return results

        # Install to each agent's skills directory
        for agent_name, skills_dir, _ in agents_with_skills:
            skill_dir = skills_dir / skill_name
            ensure_dir(skill_dir)
            skill_file = skill_dir / SKILL_MANIFEST_FILE
            write_file(skill_file, manifest.to_skill_file())
            results["installed_to"].append(str(skill_file.relative_to(self.project_root)))
            results["agents"].append(agent_name)

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

    def remove_skill(self, skill_name: str) -> dict[str, Any]:
        """Remove a skill from the project.

        Args:
            skill_name: Name of the skill to remove

        Returns:
            Dictionary with removal results:
            {
                'skill_name': 'planning-workflow',
                'removed_from': ['.claude/skills/planning-workflow'],
                'agents': ['claude'],
                'not_installed': False
            }
        """
        results: dict[str, Any] = {
            "skill_name": skill_name,
            "removed_from": [],
            "agents": [],
            "not_installed": False,
        }

        # Check if installed
        if not self.is_skill_installed(skill_name):
            results["not_installed"] = True
            return results

        # Remove from all agents with skills support
        agents_with_skills = self._get_agents_with_skills_support()
        for agent_name, skills_dir, _ in agents_with_skills:
            skill_dir = skills_dir / skill_name
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
                results["removed_from"].append(str(skill_dir.relative_to(self.project_root)))
                results["agents"].append(agent_name)

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

        for agent_type in removed_agents:
            # Get agent manifest to find skills directory
            manifest = agent_service.get_agent_manifest(agent_type)
            if not manifest:
                continue

            # Check if agent supports skills
            if not manifest.capabilities.has_skills:
                continue

            # Build the skills directory path: {agent_folder}/{skills_directory}
            agent_folder = manifest.installation.folder.rstrip("/")
            skills_subdir = manifest.capabilities.skills_directory
            skills_dir = self.project_root / agent_folder / skills_subdir

            if not skills_dir.exists():
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

    def refresh_skills(self) -> dict[str, Any]:
        """Refresh all installed skills by re-copying from package.

        This updates skill content to match the latest package versions.
        Only refreshes for agents that support skills.

        Returns:
            Dictionary with refresh results:
            {
                'skills_refreshed': ['planning-workflow', 'research-synthesis'],
                'agents': ['claude'],
                'errors': []
            }
        """
        results: dict[str, Any] = {
            "skills_refreshed": [],
            "agents": [],
            "errors": [],
        }

        # Get agents with skills support
        agents_with_skills = self._get_agents_with_skills_support()
        if not agents_with_skills:
            results["skipped"] = True
            results["reason"] = "No configured agents support skills"
            return results

        # Get installed skills
        installed_skills = self.list_installed_skills()

        for skill_name in installed_skills:
            # Get latest manifest from package
            manifest = self.get_skill_manifest(skill_name)
            if not manifest:
                results["errors"].append(f"Skill not found in package: {skill_name}")
                continue

            # Re-install to all agents with skills support
            for agent_name, skills_dir, _ in agents_with_skills:
                skill_dir = skills_dir / skill_name
                ensure_dir(skill_dir)
                skill_file = skill_dir / SKILL_MANIFEST_FILE
                write_file(skill_file, manifest.to_skill_file())
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

        # Get agents with skills support
        agents_with_skills = self._get_agents_with_skills_support()
        if not agents_with_skills:
            results["error"] = "No configured agents support skills"
            return results

        # Get current version from first agent's installed skill
        first_agent_name, first_skills_dir, _ = agents_with_skills[0]
        skill_file = first_skills_dir / skill_name / SKILL_MANIFEST_FILE
        if skill_file.exists():
            try:
                current_manifest = SkillManifest.load(skill_file)
                results["old_version"] = current_manifest.version
            except (FileNotFoundError, ValueError):
                results["old_version"] = "unknown"
        else:
            results["old_version"] = "unknown"

        # Get latest manifest from package
        manifest = self.get_skill_manifest(skill_name)
        if not manifest:
            results["error"] = f"Skill not found in package: {skill_name}"
            return results

        results["new_version"] = manifest.version

        # Re-install to all agents with skills support
        for agent_name, skills_dir, _ in agents_with_skills:
            skill_dir = skills_dir / skill_name
            ensure_dir(skill_dir)
            skill_file = skill_dir / SKILL_MANIFEST_FILE
            write_file(skill_file, manifest.to_skill_file())
            results["agents"].append(agent_name)

        results["upgraded"] = True
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
