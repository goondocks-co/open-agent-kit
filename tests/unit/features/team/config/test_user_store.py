"""Tests for the user_store module (raw key/value access to user config)."""

from pathlib import Path
from unittest import mock

import yaml


class TestReadUserValue:
    """Tests for read_user_value."""

    def test_returns_value_when_present(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import read_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "config.test.yaml",
        ):
            (tmp_path / "config.test.yaml").write_text(
                yaml.dump({"swarm": {"swarm_token": "tok123"}})
            )
            result = read_user_value(tmp_path, "swarm", "swarm_token")

        assert result == "tok123"

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import read_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "nonexistent.yaml",
        ):
            result = read_user_value(tmp_path, "swarm", "swarm_token")

        assert result is None

    def test_returns_none_when_section_missing(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import read_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "config.test.yaml",
        ):
            (tmp_path / "config.test.yaml").write_text(yaml.dump({"other": {"key": "val"}}))
            result = read_user_value(tmp_path, "swarm", "swarm_token")

        assert result is None

    def test_returns_none_when_key_missing(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import read_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "config.test.yaml",
        ):
            (tmp_path / "config.test.yaml").write_text(yaml.dump({"swarm": {"other_key": "val"}}))
            result = read_user_value(tmp_path, "swarm", "swarm_token")

        assert result is None

    def test_returns_none_for_empty_string(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import read_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "config.test.yaml",
        ):
            (tmp_path / "config.test.yaml").write_text(yaml.dump({"swarm": {"swarm_token": ""}}))
            result = read_user_value(tmp_path, "swarm", "swarm_token")

        assert result is None


class TestWriteUserValue:
    """Tests for write_user_value."""

    def test_creates_file_and_section(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import write_user_value

        config_path = tmp_path / "config.test.yaml"
        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            write_user_value(tmp_path, "swarm", "swarm_token", "tok456")

        data = yaml.safe_load(config_path.read_text())
        assert data["swarm"]["swarm_token"] == "tok456"

    def test_preserves_other_sections(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import write_user_value

        config_path = tmp_path / "config.test.yaml"
        config_path.write_text(yaml.dump({"team": {"embedding": {"model": "test"}}}))

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            write_user_value(tmp_path, "swarm", "swarm_token", "tok789")

        data = yaml.safe_load(config_path.read_text())
        assert data["team"]["embedding"]["model"] == "test"
        assert data["swarm"]["swarm_token"] == "tok789"

    def test_preserves_other_keys_in_section(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import write_user_value

        config_path = tmp_path / "config.test.yaml"
        config_path.write_text(yaml.dump({"swarm": {"agent_token": "existing"}}))

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            write_user_value(tmp_path, "swarm", "swarm_token", "new_tok")

        data = yaml.safe_load(config_path.read_text())
        assert data["swarm"]["agent_token"] == "existing"
        assert data["swarm"]["swarm_token"] == "new_tok"


class TestRemoveUserValue:
    """Tests for remove_user_value."""

    def test_removes_key(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import remove_user_value

        config_path = tmp_path / "config.test.yaml"
        config_path.write_text(yaml.dump({"swarm": {"swarm_token": "tok", "agent_token": "atok"}}))

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            result = remove_user_value(tmp_path, "swarm", "swarm_token")

        assert result is True
        data = yaml.safe_load(config_path.read_text())
        assert "swarm_token" not in data["swarm"]
        assert data["swarm"]["agent_token"] == "atok"

    def test_removes_empty_section(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import remove_user_value

        config_path = tmp_path / "config.test.yaml"
        config_path.write_text(yaml.dump({"swarm": {"swarm_token": "tok"}, "team": {"k": "v"}}))

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            result = remove_user_value(tmp_path, "swarm", "swarm_token")

        assert result is True
        data = yaml.safe_load(config_path.read_text())
        assert "swarm" not in data
        assert data["team"]["k"] == "v"

    def test_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import remove_user_value

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=tmp_path / "nonexistent.yaml",
        ):
            result = remove_user_value(tmp_path, "swarm", "swarm_token")

        assert result is False

    def test_returns_false_when_key_missing(self, tmp_path: Path) -> None:
        from open_agent_kit.features.team.config.user_store import remove_user_value

        config_path = tmp_path / "config.test.yaml"
        config_path.write_text(yaml.dump({"swarm": {"agent_token": "tok"}}))

        with mock.patch(
            "open_agent_kit.features.team.config.user_store._user_config_path",
            return_value=config_path,
        ):
            result = remove_user_value(tmp_path, "swarm", "swarm_token")

        assert result is False
