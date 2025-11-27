"""Tests for IDE configuration storage in config service."""

from pathlib import Path

from open_agent_kit.services.config_service import ConfigService


class TestIDEConfigStorage:
    """Tests for IDE storage in configuration."""

    def test_get_ides_returns_empty_list_for_new_config(self, tmp_path: Path) -> None:
        """Test get_ides returns empty list for new config."""
        service = ConfigService(tmp_path)
        service.create_default_config()

        ides = service.get_ides()
        assert ides == []

    def test_get_ides_returns_configured_ides(self, tmp_path: Path) -> None:
        """Test get_ides returns configured IDEs."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode", "cursor"])

        ides = service.get_ides()
        assert ides == ["vscode", "cursor"]

    def test_update_ides_replaces_config(self, tmp_path: Path) -> None:
        """Test update_ides replaces existing IDE list."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode"])

        service.update_ides(["cursor"])
        ides = service.get_ides()
        assert ides == ["cursor"]

    def test_add_ides_merges_with_existing(self, tmp_path: Path) -> None:
        """Test add_ides merges new IDEs with existing ones."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode"])

        service.add_ides(["cursor"])
        ides = service.get_ides()
        assert set(ides) == {"vscode", "cursor"}

    def test_add_ides_deduplicates(self, tmp_path: Path) -> None:
        """Test add_ides deduplicates IDEs."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode"])

        service.add_ides(["vscode", "cursor"])
        ides = service.get_ides()
        assert set(ides) == {"vscode", "cursor"}
        assert len(ides) == 2

    def test_add_ides_to_empty_config(self, tmp_path: Path) -> None:
        """Test add_ides works with empty config."""
        service = ConfigService(tmp_path)
        service.create_default_config()

        service.add_ides(["vscode", "cursor"])
        ides = service.get_ides()
        assert set(ides) == {"vscode", "cursor"}

    def test_add_ides_updates_version(self, tmp_path: Path) -> None:
        """Test add_ides updates config version to current package version."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode"])

        # Update version field in config to an old version
        config = service.load_config()
        config.version = "0.1.0"
        service.save_config(config)

        # Add IDE - should update version
        from open_agent_kit.constants import VERSION

        service.add_ides(["cursor"])

        config = service.load_config()
        assert config.version == VERSION

    def test_create_default_config_with_agents_and_ides(self, tmp_path: Path) -> None:
        """Test create_default_config stores both agents and IDEs."""
        service = ConfigService(tmp_path)
        service.create_default_config(agents=["claude", "cursor"], ides=["vscode", "cursor"])

        config = service.load_config()
        assert config.agents == ["claude", "cursor"]
        assert config.ides == ["vscode", "cursor"]

    def test_config_yaml_format_includes_ides(self, tmp_path: Path) -> None:
        """Test config.yaml file includes ides field in proper format."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode", "cursor"])

        config_path = tmp_path / ".oak" / "config.yaml"
        content = config_path.read_text()

        assert "ides:" in content
        assert "[vscode, cursor]" in content

    def test_update_config_partial_update_preserves_ides(self, tmp_path: Path) -> None:
        """Test partial update doesn't clear IDEs."""
        service = ConfigService(tmp_path)
        service.create_default_config(agents=["claude"], ides=["vscode"])

        # Update just agents
        service.update_config(agents=["cursor"])

        config = service.load_config()
        assert config.agents == ["cursor"]
        assert config.ides == ["vscode"]  # Should be preserved

    def test_ides_field_persists_across_loads(self, tmp_path: Path) -> None:
        """Test IDEs persist when config is loaded multiple times."""
        service = ConfigService(tmp_path)
        service.create_default_config(ides=["vscode", "cursor"])

        # Load config multiple times
        ides1 = service.get_ides()
        ides2 = service.get_ides()

        assert ides1 == ides2 == ["vscode", "cursor"]
