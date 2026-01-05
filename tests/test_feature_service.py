"""Tests for FeatureService - feature installation, removal, and refresh."""

from pathlib import Path

from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.feature_service import FeatureService


class TestFeatureServiceBasics:
    """Tests for basic FeatureService functionality."""

    def test_list_available_features(self, initialized_project: Path) -> None:
        """Test listing all available features from package."""
        service = FeatureService(initialized_project)
        features = service.list_available_features()

        # Should have at least constitution, rfc, plan
        feature_names = [f.name for f in features]
        assert "constitution" in feature_names
        assert "rfc" in feature_names
        assert "plan" in feature_names

    def test_get_feature_manifest(self, initialized_project: Path) -> None:
        """Test getting manifest for a specific feature."""
        service = FeatureService(initialized_project)
        manifest = service.get_feature_manifest("constitution")

        assert manifest is not None
        assert manifest.name == "constitution"
        assert "constitution" in manifest.display_name.lower()
        assert manifest.dependencies == []  # Constitution has no dependencies

    def test_get_feature_manifest_not_found(self, initialized_project: Path) -> None:
        """Test getting manifest for non-existent feature returns None."""
        service = FeatureService(initialized_project)
        manifest = service.get_feature_manifest("nonexistent")
        assert manifest is None

    def test_list_installed_features(self, initialized_project: Path) -> None:
        """Test listing installed features."""
        service = FeatureService(initialized_project)
        installed = service.list_installed_features()

        # After init, constitution should be installed by default
        assert isinstance(installed, list)

    def test_is_feature_installed(self, initialized_project: Path) -> None:
        """Test checking if a feature is installed."""
        service = FeatureService(initialized_project)

        # Install constitution
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        if "constitution" not in config.features.enabled:
            config.features.enabled.append("constitution")
            config_service.save_config(config)

        assert service.is_feature_installed("constitution") is True
        assert service.is_feature_installed("nonexistent") is False


class TestFeatureDependencies:
    """Tests for feature dependency resolution."""

    def test_get_feature_dependencies(self, initialized_project: Path) -> None:
        """Test getting direct dependencies for a feature."""
        service = FeatureService(initialized_project)

        # RFC depends on constitution
        rfc_deps = service.get_feature_dependencies("rfc")
        assert "constitution" in rfc_deps

        # Constitution has no dependencies
        const_deps = service.get_feature_dependencies("constitution")
        assert const_deps == []

    def test_resolve_dependencies_single(self, initialized_project: Path) -> None:
        """Test resolving dependencies for a single feature."""
        service = FeatureService(initialized_project)

        # Resolving RFC should include constitution first
        resolved = service.resolve_dependencies(["rfc"])
        assert "constitution" in resolved
        assert "rfc" in resolved
        assert resolved.index("constitution") < resolved.index("rfc")

    def test_resolve_dependencies_multiple(self, initialized_project: Path) -> None:
        """Test resolving dependencies for multiple features."""
        service = FeatureService(initialized_project)

        resolved = service.resolve_dependencies(["rfc", "plan"])
        # Should include constitution (dependency) and both requested features
        assert "constitution" in resolved
        assert "rfc" in resolved
        assert "plan" in resolved
        # Constitution should come first
        assert resolved.index("constitution") < resolved.index("rfc")
        assert resolved.index("constitution") < resolved.index("plan")

    def test_resolve_dependencies_empty(self, initialized_project: Path) -> None:
        """Test resolving empty feature list."""
        service = FeatureService(initialized_project)
        resolved = service.resolve_dependencies([])
        assert resolved == []

    def test_get_features_requiring(self, initialized_project: Path) -> None:
        """Test getting features that depend on a given feature."""
        service = FeatureService(initialized_project)

        # RFC depends on constitution
        dependents = service.get_features_requiring("constitution")
        assert "rfc" in dependents

    def test_can_remove_feature_no_dependents(self, initialized_project: Path) -> None:
        """Test can_remove_feature when no dependents are installed."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup: only constitution is installed
        config = config_service.load_config()
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        can_remove, blocking = service.can_remove_feature("constitution")
        assert can_remove is True
        assert blocking == []

    def test_can_remove_feature_with_dependents(self, initialized_project: Path) -> None:
        """Test can_remove_feature when dependents are installed."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup: both constitution and rfc are installed
        config = config_service.load_config()
        config.features.enabled = ["constitution", "rfc"]
        config_service.save_config(config)

        can_remove, blocking = service.can_remove_feature("constitution")
        assert can_remove is False
        assert "rfc" in blocking


class TestFeatureInstallation:
    """Tests for feature installation."""

    def test_install_feature_basic(self, initialized_project: Path) -> None:
        """Test basic feature installation."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup agent
        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)

        # Install constitution
        results = service.install_feature("constitution", ["claude"])

        assert "commands_installed" in results
        assert len(results["commands_installed"]) > 0
        assert "claude" in results["agents"]

        # Verify feature is marked as installed
        assert service.is_feature_installed("constitution")

    def test_install_feature_creates_directories(self, initialized_project: Path) -> None:
        """Test that install creates necessary directories."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)

        service.install_feature("constitution", ["claude"])

        # Check agent commands directory exists
        claude_commands = initialized_project / ".claude" / "commands"
        assert claude_commands.exists()

        # Note: .oak/features/ is no longer created - assets read from package
        # Only agent-native directories receive the commands
        feature_dir = initialized_project / ".oak" / "features" / "constitution"
        assert not feature_dir.exists()

    def test_install_feature_multiple_agents(self, initialized_project: Path) -> None:
        """Test installing feature for multiple agents."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude", "copilot"]
        config_service.save_config(config)

        results = service.install_feature("constitution", ["claude", "copilot"])

        assert "claude" in results["agents"]
        assert "copilot" in results["agents"]

        # Check both agent directories have commands
        assert (initialized_project / ".claude" / "commands").exists()
        assert (initialized_project / ".github" / "agents").exists()


class TestFeatureRemoval:
    """Tests for feature removal."""

    def test_remove_feature_basic(self, initialized_project: Path) -> None:
        """Test basic feature removal."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        # Setup and install
        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)
        service.install_feature("constitution", ["claude"])

        # Remove
        results = service.remove_feature("constitution", ["claude"])

        assert "commands_removed" in results
        assert service.is_feature_installed("constitution") is False

    def test_remove_feature_removes_agent_commands(self, initialized_project: Path) -> None:
        """Test that removal cleans up agent command files.

        Note: .oak/features/ is no longer created - only agent-native directories
        receive the commands, so removal just cleans up those files.
        """
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)
        service.install_feature("constitution", ["claude"])

        # Verify command file exists before removal
        command_file = initialized_project / ".claude" / "commands" / "oak.constitution-create.md"
        assert command_file.exists()

        # Remove
        service.remove_feature("constitution", ["claude"])

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
        config.features.enabled = ["constitution"]
        config_service.save_config(config)
        service.install_feature("constitution", ["claude"])

        # Refresh
        results = service.refresh_features()

        assert "features_refreshed" in results
        assert "constitution" in results["features_refreshed"]
        assert "claude" in results["agents"]
        assert "constitution" in results["commands_rendered"]

    def test_refresh_features_empty(self, initialized_project: Path) -> None:
        """Test refresh with no features installed."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = []
        config_service.save_config(config)

        results = service.refresh_features()

        assert results["features_refreshed"] == []

    def test_refresh_features_no_agents(self, initialized_project: Path) -> None:
        """Test refresh with no agents configured."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = []
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        results = service.refresh_features()

        assert results["agents"] == []
        assert results["features_refreshed"] == []

    def test_refresh_features_multiple(self, initialized_project: Path) -> None:
        """Test refreshing multiple features."""
        service = FeatureService(initialized_project)
        config_service = ConfigService(initialized_project)

        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution", "rfc"]
        config_service.save_config(config)

        # Install both features
        service.install_feature("constitution", ["claude"])
        service.install_feature("rfc", ["claude"])

        # Refresh
        results = service.refresh_features()

        assert "constitution" in results["features_refreshed"]
        assert "rfc" in results["features_refreshed"]


class TestJinja2Rendering:
    """Tests for Jinja2 template rendering in features."""

    def test_has_jinja2_syntax_detection(self, initialized_project: Path) -> None:
        """Test detection of Jinja2 syntax in content."""
        service = FeatureService(initialized_project)

        # Should detect {{ and {%
        assert service._has_jinja2_syntax("Hello {{ name }}")
        assert service._has_jinja2_syntax("{% if condition %}yes{% endif %}")
        assert service._has_jinja2_syntax("{{ var }} and {% block %}")

        # Should not detect regular content
        assert not service._has_jinja2_syntax("Hello world")
        assert not service._has_jinja2_syntax("Just some text")
        assert not service._has_jinja2_syntax("Curly { braces } alone")
