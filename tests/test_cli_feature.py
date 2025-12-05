"""Tests for feature CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from open_agent_kit.cli import app
from open_agent_kit.services.config_service import ConfigService

runner = CliRunner()


class TestFeatureList:
    """Tests for 'oak feature list' command."""

    def test_feature_list_shows_features(self, initialized_project: Path) -> None:
        """Test that feature list shows available features."""
        result = runner.invoke(app, ["feature", "list"])

        assert result.exit_code == 0
        assert "Constitution" in result.stdout or "constitution" in result.stdout.lower()

    def test_feature_list_shows_status(self, initialized_project: Path) -> None:
        """Test that feature list shows installation status."""
        result = runner.invoke(app, ["feature", "list"])

        assert result.exit_code == 0
        # Should show either installed or not installed indicators
        assert "Installed" in result.stdout or "Not installed" in result.stdout

    def test_feature_list_not_initialized(self, temp_project_dir: Path) -> None:
        """Test feature list fails when OAK not initialized."""
        result = runner.invoke(app, ["feature", "list"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()


class TestFeatureAdd:
    """Tests for 'oak feature add' command."""

    def test_feature_add_basic(self, initialized_project: Path) -> None:
        """Test adding a feature."""
        # Setup agent first
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "add", "constitution"])

        # May already be installed or succeed
        assert result.exit_code == 0

    def test_feature_add_with_dependencies(self, initialized_project: Path) -> None:
        """Test adding a feature auto-installs dependencies."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = []  # Start fresh
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "add", "rfc"])

        assert result.exit_code == 0
        # RFC should trigger constitution installation
        assert "constitution" in result.stdout.lower() or "rfc" in result.stdout.lower()

    def test_feature_add_invalid(self, initialized_project: Path) -> None:
        """Test adding an invalid feature fails."""
        result = runner.invoke(app, ["feature", "add", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "unknown" in result.stdout.lower()

    def test_feature_add_already_installed(self, initialized_project: Path) -> None:
        """Test adding already installed feature shows message."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "add", "constitution"])

        assert result.exit_code == 0
        assert "already installed" in result.stdout.lower()

    def test_feature_add_no_agents(self, initialized_project: Path) -> None:
        """Test adding feature without agents fails."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = []
        config.features.enabled = []
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "add", "constitution"])

        assert result.exit_code == 1
        assert "no agents" in result.stdout.lower()

    def test_feature_add_not_initialized(self, temp_project_dir: Path) -> None:
        """Test feature add fails when OAK not initialized."""
        result = runner.invoke(app, ["feature", "add", "constitution"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()


class TestFeatureRemove:
    """Tests for 'oak feature remove' command."""

    def test_feature_remove_basic(self, initialized_project: Path) -> None:
        """Test removing a feature."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "remove", "constitution", "--force"])

        assert result.exit_code == 0

    def test_feature_remove_not_installed(self, initialized_project: Path) -> None:
        """Test removing a feature that's not installed."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.features.enabled = []
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "remove", "rfc", "--force"])

        assert result.exit_code == 0
        assert "not installed" in result.stdout.lower()

    def test_feature_remove_with_dependents(self, initialized_project: Path) -> None:
        """Test removing a feature with dependents fails."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution", "rfc"]
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "remove", "constitution", "--force"])

        assert result.exit_code == 1
        assert "required" in result.stdout.lower() or "rfc" in result.stdout.lower()

    def test_feature_remove_invalid(self, initialized_project: Path) -> None:
        """Test removing an invalid feature fails."""
        result = runner.invoke(app, ["feature", "remove", "nonexistent", "--force"])

        assert result.exit_code == 1

    def test_feature_remove_not_initialized(self, temp_project_dir: Path) -> None:
        """Test feature remove fails when OAK not initialized."""
        result = runner.invoke(app, ["feature", "remove", "constitution", "--force"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()


class TestFeatureRefresh:
    """Tests for 'oak feature refresh' command."""

    def test_feature_refresh_basic(self, initialized_project: Path) -> None:
        """Test refreshing features."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        # Install the feature first
        from open_agent_kit.services.feature_service import FeatureService

        feature_service = FeatureService(initialized_project)
        feature_service.install_feature("constitution", ["claude"])

        result = runner.invoke(app, ["feature", "refresh"])

        assert result.exit_code == 0
        assert "refresh" in result.stdout.lower()

    def test_feature_refresh_no_features(self, initialized_project: Path) -> None:
        """Test refresh with no features installed."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = []
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "refresh"])

        assert result.exit_code == 0
        assert "no features" in result.stdout.lower() or "nothing" in result.stdout.lower()

    def test_feature_refresh_no_agents(self, initialized_project: Path) -> None:
        """Test refresh with no agents fails."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = []
        config.features.enabled = ["constitution"]
        config_service.save_config(config)

        result = runner.invoke(app, ["feature", "refresh"])

        assert result.exit_code == 1
        assert "no agents" in result.stdout.lower()

    def test_feature_refresh_not_initialized(self, temp_project_dir: Path) -> None:
        """Test feature refresh fails when OAK not initialized."""
        result = runner.invoke(app, ["feature", "refresh"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()

    def test_feature_refresh_multiple_features(self, initialized_project: Path) -> None:
        """Test refreshing multiple features."""
        config_service = ConfigService(initialized_project)
        config = config_service.load_config()
        config.agents = ["claude"]
        config.features.enabled = ["constitution", "rfc"]
        config_service.save_config(config)

        # Install features
        from open_agent_kit.services.feature_service import FeatureService

        feature_service = FeatureService(initialized_project)
        feature_service.install_feature("constitution", ["claude"])
        feature_service.install_feature("rfc", ["claude"])

        result = runner.invoke(app, ["feature", "refresh"])

        assert result.exit_code == 0


class TestFeatureInteractive:
    """Tests for interactive feature management."""

    def test_feature_no_subcommand_not_initialized(self, temp_project_dir: Path) -> None:
        """Test 'oak feature' without subcommand fails when not initialized."""
        result = runner.invoke(app, ["feature"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()
