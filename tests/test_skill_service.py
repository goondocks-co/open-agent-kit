"""Tests for SkillService."""

from unittest.mock import patch

import pytest

from open_agent_kit.models.agent_manifest import AgentCapabilities, AgentInstallation, AgentManifest
from open_agent_kit.services.skill_service import SkillService, get_skill_service


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    # Create .oak directory and config
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()

    # Create minimal config.yaml
    config_file = oak_dir / "config.yaml"
    config_file.write_text(
        """
version: "1.0"
agents: [claude]
features: [plan]
skills:
  installed: []
  auto_install: true
"""
    )

    # Create .claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    return tmp_path


@pytest.fixture
def mock_agent_manifest():
    """Create a mock agent manifest with skills support."""
    return AgentManifest(
        name="claude",
        display_name="Claude Code",
        description="Claude Code agent",
        version="1.0.0",
        capabilities=AgentCapabilities(has_skills=True, skills_directory="skills"),
        installation=AgentInstallation(folder=".claude/"),
    )


@pytest.fixture
def mock_agent_manifest_no_skills():
    """Create a mock agent manifest without skills support."""
    return AgentManifest(
        name="basic-agent",
        display_name="Basic Agent",
        description="Basic agent",
        version="1.0.0",
        capabilities=AgentCapabilities(has_skills=False),
        installation=AgentInstallation(folder=".basic-agent/"),
    )


@pytest.fixture
def package_skills_dir(tmp_path):
    """Create a temporary package features directory with skills."""
    # Create features/plan/skills structure
    features_dir = tmp_path / "features"
    features_dir.mkdir()

    plan_dir = features_dir / "plan"
    plan_dir.mkdir()

    # Create feature manifest
    (plan_dir / "manifest.yaml").write_text(
        """
name: plan
description: Planning feature
version: 1.0.0
"""
    )

    # Create skills directory
    skills_dir = plan_dir / "skills"
    skills_dir.mkdir()

    # Create test skill
    test_skill_dir = skills_dir / "test-skill"
    test_skill_dir.mkdir()
    (test_skill_dir / "SKILL.md").write_text(
        """---
name: test-skill
description: A test skill for testing
---

# Test Skill

This is a test skill.
"""
    )

    # Create another skill
    other_skill_dir = skills_dir / "other-skill"
    other_skill_dir.mkdir()
    (other_skill_dir / "SKILL.md").write_text(
        """---
name: other-skill
description: Another test skill
---

# Other Skill

Another skill body.
"""
    )

    return features_dir


class TestSkillServiceInit:
    """Tests for SkillService initialization."""

    def test_init_with_project_root(self, temp_project):
        """Initialize with explicit project root."""
        service = SkillService(temp_project)
        assert service.project_root == temp_project

    def test_init_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Initialize defaults to current working directory."""
        monkeypatch.chdir(tmp_path)
        service = SkillService()
        assert service.project_root == tmp_path


class TestSkillServiceDiscovery:
    """Tests for skill discovery methods."""

    def test_list_available_skills(self, temp_project, package_skills_dir):
        """List skills available from package features."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        skills = service.list_available_skills()
        assert len(skills) == 2
        names = [s.name for s in skills]
        assert "test-skill" in names
        assert "other-skill" in names

    def test_list_available_skills_empty_features(self, temp_project, tmp_path):
        """Return empty list when no features exist."""
        service = SkillService(temp_project)
        service.package_features_dir = tmp_path / "nonexistent"

        skills = service.list_available_skills()
        assert skills == []

    def test_get_skill_manifest(self, temp_project, package_skills_dir):
        """Get manifest for specific skill."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        manifest = service.get_skill_manifest("test-skill")
        assert manifest is not None
        assert manifest.name == "test-skill"
        assert manifest.description == "A test skill for testing"

    def test_get_skill_manifest_not_found(self, temp_project, package_skills_dir):
        """Return None for nonexistent skill."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        manifest = service.get_skill_manifest("nonexistent-skill")
        assert manifest is None

    def test_get_skills_for_feature(self, temp_project, package_skills_dir):
        """Get skills for a specific feature."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        skills = service.get_skills_for_feature("plan")
        assert len(skills) == 2
        assert "test-skill" in skills
        assert "other-skill" in skills

    def test_get_skills_for_feature_no_skills(self, temp_project, package_skills_dir):
        """Return empty list for feature without skills."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        skills = service.get_skills_for_feature("nonexistent-feature")
        assert skills == []

    def test_get_feature_for_skill(self, temp_project, package_skills_dir):
        """Get feature name containing a skill."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        feature = service.get_feature_for_skill("test-skill")
        assert feature == "plan"

    def test_get_feature_for_skill_not_found(self, temp_project, package_skills_dir):
        """Return None for skill not in any feature."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        feature = service.get_feature_for_skill("nonexistent")
        assert feature is None


class TestSkillServiceInstallation:
    """Tests for skill installation."""

    def test_install_skill_success(self, temp_project, package_skills_dir, mock_agent_manifest):
        """Install skill to agent with skills support."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # Mock agent service to return skills-capable agent
        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            skills_dir = temp_project / ".claude" / "skills"
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.install_skill("test-skill")

        assert result["skill_name"] == "test-skill"
        assert not result["already_installed"]
        assert not result["skipped"]
        assert "claude" in result["agents"]
        assert len(result["installed_to"]) > 0

        # Verify skill was written
        installed_skill = skills_dir / "test-skill" / "SKILL.md"
        assert installed_skill.exists()

    def test_install_skill_already_installed(
        self, temp_project, package_skills_dir, mock_agent_manifest
    ):
        """Skip installation if skill already installed."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # Add skill to installed list
        config = service.config_service.load_config()
        config.skills.installed.append("test-skill")
        service.config_service.save_config(config)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            skills_dir = temp_project / ".claude" / "skills"
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.install_skill("test-skill")

        assert result["already_installed"] is True

    def test_install_skill_no_skills_capable_agents(self, temp_project, package_skills_dir):
        """Skip installation when no agents support skills."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = []

            result = service.install_skill("test-skill")

        assert result["skipped"] is True
        assert "No configured agents support skills" in result.get("reason", "")

    def test_install_skill_not_found(self, temp_project, package_skills_dir):
        """Return error for nonexistent skill."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            skills_dir = temp_project / ".claude" / "skills"
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.install_skill("nonexistent-skill")

        assert "error" in result
        assert "not found" in result["error"]

    def test_install_skills_for_feature(self, temp_project, package_skills_dir):
        """Install all skills for a feature."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            skills_dir = temp_project / ".claude" / "skills"
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.install_skills_for_feature("plan")

        assert result["feature_name"] == "plan"
        assert len(result["skills_available"]) == 2
        assert "test-skill" in result["skills_installed"]
        assert "other-skill" in result["skills_installed"]
        assert "claude" in result["agents"]

    def test_install_skills_for_feature_no_skills(self, temp_project, package_skills_dir):
        """Return empty result for feature without skills."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        result = service.install_skills_for_feature("nonexistent")

        assert result["feature_name"] == "nonexistent"
        assert result["skills_available"] == []
        assert result["skills_installed"] == []


class TestSkillServiceRemoval:
    """Tests for skill removal."""

    def test_remove_skill_success(self, temp_project, package_skills_dir):
        """Remove installed skill."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # First install the skill
        skills_dir = temp_project / ".claude" / "skills"
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\n---\n")

        config = service.config_service.load_config()
        config.skills.installed.append("test-skill")
        service.config_service.save_config(config)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.remove_skill("test-skill")

        assert result["skill_name"] == "test-skill"
        assert not result["not_installed"]
        assert "claude" in result["agents"]
        assert not skill_dir.exists()

    def test_remove_skill_not_installed(self, temp_project):
        """Return not_installed for skill not in installed list."""
        service = SkillService(temp_project)

        result = service.remove_skill("never-installed")

        assert result["not_installed"] is True

    def test_remove_skills_for_feature(self, temp_project, package_skills_dir):
        """Remove all skills for a feature."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # Setup installed skills
        skills_dir = temp_project / ".claude" / "skills"
        for skill_name in ["test-skill", "other-skill"]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {skill_name}\ndescription: Test\n---\n"
            )

        config = service.config_service.load_config()
        config.skills.installed = ["test-skill", "other-skill"]
        service.config_service.save_config(config)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.remove_skills_for_feature("plan")

        assert result["feature_name"] == "plan"
        assert "test-skill" in result["skills_removed"]
        assert "other-skill" in result["skills_removed"]


class TestSkillServiceRefresh:
    """Tests for skill refresh operations."""

    def test_refresh_skills(self, temp_project, package_skills_dir):
        """Refresh all installed skills from package."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # Setup installed skill with old content
        skills_dir = temp_project / ".claude" / "skills"
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: Old version\n---\n"
        )

        config = service.config_service.load_config()
        config.skills.installed = ["test-skill"]
        service.config_service.save_config(config)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.refresh_skills()

        assert "test-skill" in result["skills_refreshed"]
        assert "claude" in result["agents"]

        # Verify content was updated
        content = (skill_dir / "SKILL.md").read_text()
        assert "A test skill for testing" in content

    def test_refresh_skills_no_agents(self, temp_project):
        """Skip refresh when no agents support skills."""
        service = SkillService(temp_project)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = []

            result = service.refresh_skills()

        assert result.get("skipped") is True


class TestSkillServiceUpgrade:
    """Tests for skill upgrade operations."""

    def test_upgrade_skill(self, temp_project, package_skills_dir):
        """Upgrade specific skill to latest version."""
        service = SkillService(temp_project)
        service.package_features_dir = package_skills_dir

        # Setup installed skill
        skills_dir = temp_project / ".claude" / "skills"
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: Old\nversion: 0.9.0\n---\n"
        )

        config = service.config_service.load_config()
        config.skills.installed = ["test-skill"]
        service.config_service.save_config(config)

        with patch.object(service, "_get_agents_with_skills_support") as mock_agents:
            mock_agents.return_value = [("claude", skills_dir, "skills")]

            result = service.upgrade_skill("test-skill")

        assert result["skill_name"] == "test-skill"
        assert result["upgraded"] is True
        assert "claude" in result["agents"]

    def test_upgrade_skill_not_installed(self, temp_project):
        """Return error for upgrading non-installed skill."""
        service = SkillService(temp_project)

        result = service.upgrade_skill("not-installed")

        assert "error" in result
        assert "not installed" in result["error"]


class TestSkillServiceScaffold:
    """Tests for skill scaffolding."""

    def test_create_skill_scaffold(self, temp_project):
        """Create new skill scaffold."""
        service = SkillService(temp_project)

        output_dir = temp_project / "custom-skills"
        output_dir.mkdir()

        skill_file = service.create_skill_scaffold(
            "my-new-skill", "A brand new skill for testing", output_dir
        )

        assert skill_file.exists()
        assert skill_file.name == "SKILL.md"

        content = skill_file.read_text()
        assert "name: my-new-skill" in content
        assert "A brand new skill for testing" in content
        assert "# My New Skill" in content

    def test_create_skill_scaffold_default_location(self, temp_project):
        """Create scaffold in default location."""
        service = SkillService(temp_project)

        skill_file = service.create_skill_scaffold("default-skill", "Test description")

        assert skill_file.exists()
        expected_dir = temp_project / ".oak" / "skills" / "default-skill"
        assert skill_file.parent == expected_dir


class TestSkillServiceHelpers:
    """Tests for helper methods."""

    def test_is_skill_installed(self, temp_project):
        """Check if skill is installed."""
        service = SkillService(temp_project)

        config = service.config_service.load_config()
        config.skills.installed = ["installed-skill"]
        service.config_service.save_config(config)

        assert service.is_skill_installed("installed-skill") is True
        assert service.is_skill_installed("not-installed") is False

    def test_list_installed_skills(self, temp_project):
        """List installed skills from config."""
        service = SkillService(temp_project)

        config = service.config_service.load_config()
        config.skills.installed = ["skill-a", "skill-b"]
        service.config_service.save_config(config)

        installed = service.list_installed_skills()
        assert "skill-a" in installed
        assert "skill-b" in installed


class TestGetSkillService:
    """Tests for get_skill_service factory function."""

    def test_get_skill_service_with_path(self, temp_project):
        """Get service with explicit path."""
        service = get_skill_service(temp_project)
        assert isinstance(service, SkillService)
        assert service.project_root == temp_project

    def test_get_skill_service_default(self, tmp_path, monkeypatch):
        """Get service with default cwd."""
        # Create minimal config
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        (oak_dir / "config.yaml").write_text("version: '1.0'\nagents: []\nfeatures: []")

        monkeypatch.chdir(tmp_path)
        service = get_skill_service()
        assert isinstance(service, SkillService)


class TestManifestSkillsConsistency:
    """Integration tests validating manifest skills match directory contents.

    These tests ensure that the skills listed in each feature's manifest.yaml
    match the actual skill directories present in features/{feature}/skills/.
    """

    @pytest.fixture
    def package_features_path(self):
        """Get the real package features directory."""
        from pathlib import Path

        # Navigate from tests/ to features/
        return Path(__file__).parent.parent / "features"

    def test_plan_manifest_skills_match_directories(self, package_features_path):
        """Validate plan feature manifest skills match skill directories."""
        from open_agent_kit.models.feature import FeatureManifest

        feature_dir = package_features_path / "plan"
        manifest = FeatureManifest.load(feature_dir / "manifest.yaml")

        skills_dir = feature_dir / "skills"
        if not skills_dir.exists():
            # No skills directory means manifest should have empty skills list
            assert manifest.skills == [], "Manifest lists skills but no skills/ directory exists"
            return

        # Get actual skill directories (those containing SKILL.md)
        actual_skills = sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        )
        manifest_skills = sorted(manifest.skills)

        assert manifest_skills == actual_skills, (
            f"plan manifest skills mismatch:\n"
            f"  In manifest but not directory: {set(manifest_skills) - set(actual_skills)}\n"
            f"  In directory but not manifest: {set(actual_skills) - set(manifest_skills)}"
        )

    def test_rfc_manifest_skills_match_directories(self, package_features_path):
        """Validate rfc feature manifest skills match skill directories."""
        from open_agent_kit.models.feature import FeatureManifest

        feature_dir = package_features_path / "rfc"
        manifest = FeatureManifest.load(feature_dir / "manifest.yaml")

        skills_dir = feature_dir / "skills"
        if not skills_dir.exists():
            assert manifest.skills == [], "Manifest lists skills but no skills/ directory exists"
            return

        actual_skills = sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        )
        manifest_skills = sorted(manifest.skills)

        assert manifest_skills == actual_skills, (
            f"rfc manifest skills mismatch:\n"
            f"  In manifest but not directory: {set(manifest_skills) - set(actual_skills)}\n"
            f"  In directory but not manifest: {set(actual_skills) - set(manifest_skills)}"
        )

    def test_constitution_manifest_skills_match_directories(self, package_features_path):
        """Validate constitution feature manifest skills match skill directories."""
        from open_agent_kit.models.feature import FeatureManifest

        feature_dir = package_features_path / "constitution"
        manifest = FeatureManifest.load(feature_dir / "manifest.yaml")

        skills_dir = feature_dir / "skills"
        if not skills_dir.exists():
            assert manifest.skills == [], "Manifest lists skills but no skills/ directory exists"
            return

        actual_skills = sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        )
        manifest_skills = sorted(manifest.skills)

        assert manifest_skills == actual_skills, (
            f"constitution manifest skills mismatch:\n"
            f"  In manifest but not directory: {set(manifest_skills) - set(actual_skills)}\n"
            f"  In directory but not manifest: {set(actual_skills) - set(manifest_skills)}"
        )

    def test_all_features_manifest_skills_consistency(self, package_features_path):
        """Validate all features have consistent manifest skills declarations.

        This is a comprehensive test that checks every feature in the features/
        directory to ensure manifest skills match actual skill directories.
        """
        from open_agent_kit.models.feature import FeatureManifest

        if not package_features_path.exists():
            pytest.skip("Package features directory not found")

        errors = []

        for feature_dir in package_features_path.iterdir():
            if not feature_dir.is_dir():
                continue

            manifest_path = feature_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue

            try:
                manifest = FeatureManifest.load(manifest_path)
            except Exception as e:
                errors.append(f"{feature_dir.name}: Failed to load manifest - {e}")
                continue

            skills_dir = feature_dir / "skills"

            if not skills_dir.exists():
                if manifest.skills:
                    errors.append(
                        f"{feature_dir.name}: Manifest lists {manifest.skills} "
                        f"but no skills/ directory exists"
                    )
                continue

            actual_skills = sorted(
                d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
            )
            manifest_skills = sorted(manifest.skills)

            if manifest_skills != actual_skills:
                in_manifest_only = set(manifest_skills) - set(actual_skills)
                in_directory_only = set(actual_skills) - set(manifest_skills)
                errors.append(
                    f"{feature_dir.name}: Skills mismatch - "
                    f"manifest-only: {in_manifest_only or 'none'}, "
                    f"directory-only: {in_directory_only or 'none'}"
                )

        assert not errors, "Manifest/directory skill mismatches found:\n" + "\n".join(errors)
