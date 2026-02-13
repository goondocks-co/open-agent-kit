"""Tests for FeatureService - feature installation, removal, and refresh."""

from pathlib import Path

from open_agent_kit.constants import SUPPORTED_FEATURES
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.feature_service import FeatureService


class TestFeatureServiceBasics:
    """Tests for basic FeatureService functionality."""

    def test_list_available_features(self, initialized_project: Path) -> None:
        """Test listing all available features from package."""
        service = FeatureService(initialized_project)
        features = service.list_available_features()

        # Should have at least rules-management, strategic-planning
        feature_names = [f.name for f in features]
        assert "rules-management" in feature_names
        assert "strategic-planning" in feature_names

    def test_get_feature_manifest(self, initialized_project: Path) -> None:
        """Test getting manifest for a specific feature."""
        service = FeatureService(initialized_project)
        manifest = service.get_feature_manifest("rules-management")

        assert manifest is not None
        assert manifest.name == "rules-management"
        assert manifest.dependencies == []  # rules-management has no dependencies

    def test_get_feature_manifest_not_found(self, initialized_project: Path) -> None:
        """Test getting manifest for non-existent feature returns None."""
        service = FeatureService(initialized_project)
        manifest = service.get_feature_manifest("nonexistent")
        assert manifest is None

    def test_list_installed_features(self, initialized_project: Path) -> None:
        """Test listing installed features.

        All features are always installed (not user-selectable).
        """
        service = FeatureService(initialized_project)
        installed = service.list_installed_features()

        # All supported features should be installed
        assert installed == list(SUPPORTED_FEATURES)

    def test_is_feature_installed(self, initialized_project: Path) -> None:
        """Test checking if a feature is installed.

        All features are always installed.
        """
        service = FeatureService(initialized_project)

        # All supported features should be installed
        assert service.is_feature_installed("rules-management") is True
        assert service.is_feature_installed("strategic-planning") is True
        assert service.is_feature_installed("codebase-intelligence") is True

        # Non-existent features should not be installed
        assert service.is_feature_installed("nonexistent") is False


class TestFeatureDependencies:
    """Tests for feature dependency resolution."""

    def test_get_feature_dependencies(self, initialized_project: Path) -> None:
        """Test getting direct dependencies for a feature."""
        service = FeatureService(initialized_project)

        # strategic-planning depends on rules-management
        planning_deps = service.get_feature_dependencies("strategic-planning")
        assert "rules-management" in planning_deps

        # rules-management has no dependencies
        rules_deps = service.get_feature_dependencies("rules-management")
        assert rules_deps == []

    def test_resolve_dependencies_single(self, initialized_project: Path) -> None:
        """Test resolving dependencies for a single feature."""
        service = FeatureService(initialized_project)

        # Resolving strategic-planning should include rules-management first
        resolved = service.resolve_dependencies(["strategic-planning"])
        assert "rules-management" in resolved
        assert "strategic-planning" in resolved
        assert resolved.index("rules-management") < resolved.index("strategic-planning")

    def test_resolve_dependencies_multiple(self, initialized_project: Path) -> None:
        """Test resolving dependencies for multiple features."""
        service = FeatureService(initialized_project)

        resolved = service.resolve_dependencies(["strategic-planning", "codebase-intelligence"])
        # Should include rules-management (dependency) and both requested features
        assert "rules-management" in resolved
        assert "strategic-planning" in resolved

    def test_resolve_dependencies_empty(self, initialized_project: Path) -> None:
        """Test resolving empty feature list."""
        service = FeatureService(initialized_project)
        resolved = service.resolve_dependencies([])
        assert resolved == []

    def test_get_features_requiring(self, initialized_project: Path) -> None:
        """Test getting features that depend on a given feature."""
        service = FeatureService(initialized_project)

        # strategic-planning depends on rules-management
        dependents = service.get_features_requiring("rules-management")
        assert "strategic-planning" in dependents

    def test_can_remove_feature_no_dependents(self, initialized_project: Path) -> None:
        """Test can_remove_feature when checking a feature with no dependents installed.

        All features are always installed, but can_remove checks if dependents
        (also always installed) block removal.
        """
        service = FeatureService(initialized_project)

        # Since all features are always installed, and strategic-planning depends
        # on rules-management, rules-management cannot be removed
        can_remove, blocking = service.can_remove_feature("rules-management")
        assert can_remove is False
        assert "strategic-planning" in blocking

    def test_can_remove_feature_leaf_feature(self, initialized_project: Path) -> None:
        """Test can_remove_feature for a feature that nothing depends on."""
        service = FeatureService(initialized_project)

        # codebase-intelligence has no dependents
        can_remove, blocking = service.can_remove_feature("codebase-intelligence")
        assert can_remove is True
        assert blocking == []


class TestFeatureInstallation:
    """Tests for feature installation."""

    def test_install_feature_basic(self, initialized_project: Path) -> None:
        """Test basic feature installation.

        Commands (sub-agents) are installed for all agents.
        We test with codebase-intelligence which has the backend-python-expert command.
        """
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup agent
        config = config_service.load_config()
        config.agents = ["cursor"]
        config_service.save_config(config)

        # Install codebase-intelligence (which has commands)
        results = service.install_feature("codebase-intelligence", ["cursor"])

        assert "commands_installed" in results
        assert len(results["commands_installed"]) > 0
        assert "backend-python-expert" in results["commands_installed"]
        assert "cursor" in results["agents"]

        # All features are always installed
        assert service.is_feature_installed("codebase-intelligence")

    def test_install_feature_creates_directories(self, initialized_project: Path) -> None:
        """Test that install creates necessary directories.

        Note: We use 'cursor' agent because it doesn't have has_skills=True,
        which means it uses command prompts instead of SKILL.md files.
        VS Code Copilot now has has_skills=True like Claude.
        """
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["cursor"]
        config_service.save_config(config)

        service.install_feature("rules-management", ["cursor"])

        # Check agent commands directory exists
        cursor_commands = initialized_project / ".cursor" / "commands"
        assert cursor_commands.exists()

        # Note: .oak/features/ is no longer created - assets read from package
        # Only agent-native directories receive the commands
        feature_dir = initialized_project / ".oak" / "features" / "rules-management"
        assert not feature_dir.exists()

    def test_install_feature_multiple_agents(self, initialized_project: Path) -> None:
        """Test installing feature for multiple agents.

        Test with one skill agent (claude) and one command agent (cursor).
        Claude has has_skills=True and uses SKILL.md files.
        Cursor doesn't have skills and uses command prompts.
        """
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude", "cursor"]
        config_service.save_config(config)

        results = service.install_feature("rules-management", ["claude", "cursor"])

        assert "claude" in results["agents"]
        assert "cursor" in results["agents"]

        # Claude gets skills, cursor gets commands
        # Note: skills are installed via skill_service, not directly in install_feature
        assert (initialized_project / ".cursor" / "commands").exists()


class TestFeatureRemoval:
    """Tests for feature removal."""

    def test_remove_feature_basic(self, initialized_project: Path) -> None:
        """Test basic feature removal (command files, not the feature itself)."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup and install
        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)
        service.install_feature("rules-management", ["claude"])

        # Remove
        results = service.remove_feature("rules-management", ["claude"])

        assert "commands_removed" in results
        # All features are always installed (in SUPPORTED_FEATURES)
        # The remove_feature just removes command files, not the feature itself
        assert service.is_feature_installed("rules-management") is True

    def test_remove_feature_removes_agent_commands(self, initialized_project: Path) -> None:
        """Test that removal cleans up agent command files.

        Commands (sub-agents) are installed for all agents.
        We test with codebase-intelligence which has the backend-python-expert command.
        """
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["cursor"]
        config_service.save_config(config)
        service.install_feature("codebase-intelligence", ["cursor"])

        # Verify command file exists before removal
        command_file = initialized_project / ".cursor" / "commands" / "oak.backend-python-expert.md"
        assert command_file.exists()

        # Remove
        service.remove_feature("codebase-intelligence", ["cursor"])

        # Verify command file is removed
        assert not command_file.exists()


class TestFeatureRefresh:
    """Tests for feature refresh functionality."""

    def test_refresh_features_basic(self, initialized_project: Path) -> None:
        """Test basic feature refresh."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup and install
        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)
        service.install_feature("rules-management", ["claude"])

        # Refresh
        results = service.refresh_features()

        assert "features_refreshed" in results
        # All features are always installed
        assert "rules-management" in results["features_refreshed"]
        assert "claude" in results["agents"]
        assert "rules-management" in results["commands_rendered"]

    def test_refresh_features_no_agents(self, initialized_project: Path) -> None:
        """Test refresh with no agents configured."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = []
        config_service.save_config(config)

        results = service.refresh_features()

        assert results["agents"] == []
        assert results["features_refreshed"] == []


class TestJinja2Rendering:
    """Tests for Jinja2 template rendering in features."""

    def test_has_jinja2_syntax_detection(self, initialized_project: Path) -> None:
        """Test detection of Jinja2 syntax in content."""
        from open_agent_kit.utils.template_utils import has_jinja2_syntax

        # Should detect {{ and {%
        assert has_jinja2_syntax("Hello {{ name }}")
        assert has_jinja2_syntax("{% if condition %}yes{% endif %}")
        assert has_jinja2_syntax("{{ var }} and {% block %}")

        # Should not detect regular content
        assert not has_jinja2_syntax("Hello world")
        assert not has_jinja2_syntax("Just some text")
        assert not has_jinja2_syntax("Curly { braces } alone")
