"""Tests for ~/.oak/ global config management."""

from pathlib import Path

import pytest

from open_agent_kit.utils.global_config import (
    GLOBAL_OAK_DIR_NAME,
    STAGING_DIR,
    UpdateConfig,
    clear_update_error,
    ensure_global_dir,
    get_global_oak_dir,
    load_update_config,
    read_staged_update,
    read_update_error,
    save_update_config,
    write_staged_update,
    write_update_error,
)


class TestGetGlobalOakDir:
    """Test global directory path resolution."""

    def test_returns_home_dot_oak(self) -> None:
        result = get_global_oak_dir()
        assert result == Path.home() / GLOBAL_OAK_DIR_NAME

    def test_respects_override_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path / "custom"))
        result = get_global_oak_dir()
        assert result == tmp_path / "custom"


class TestEnsureGlobalDir:
    """Test directory creation."""

    def test_creates_directory_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        oak_dir = tmp_path / ".oak"
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(oak_dir))
        result = ensure_global_dir()
        assert result is True
        assert oak_dir.exists()
        assert (oak_dir / STAGING_DIR).exists()

    def test_returns_false_on_permission_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        oak_dir = tmp_path / "readonly" / ".oak"
        (tmp_path / "readonly").mkdir()
        (tmp_path / "readonly").chmod(0o444)
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(oak_dir))
        result = ensure_global_dir()
        assert result is False
        # Cleanup
        (tmp_path / "readonly").chmod(0o755)


class TestUpdateConfig:
    """Test update config load/save."""

    def test_default_values(self) -> None:
        config = UpdateConfig()
        assert config.channel == "stable"
        assert config.auto_download is True
        assert config.check_interval_hours == 6

    def test_load_returns_defaults_when_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        config = load_update_config()
        assert config.channel == "stable"

    def test_save_and_load_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        config = UpdateConfig(channel="beta", auto_download=False, check_interval_hours=12)
        save_update_config(config)
        loaded = load_update_config()
        assert loaded.channel == "beta"
        assert loaded.auto_download is False
        assert loaded.check_interval_hours == 12


class TestStagedUpdate:
    """Test staged update JSON management."""

    def test_read_returns_none_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert read_staged_update() is None

    def test_write_and_read_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        data = {
            "schema_version": 1,
            "version": "1.3.0",
            "wheel_path": str(tmp_path / "staging" / "oak_ci-1.3.0.whl"),
            "channel": "stable",
            "downloaded_at": "2026-03-10T00:00:00Z",
            "sha256": "abc123",
        }
        write_staged_update(data)
        loaded = read_staged_update()
        assert loaded is not None
        assert loaded["version"] == "1.3.0"
        assert loaded["schema_version"] == 1


class TestUpdateError:
    """Test error file management."""

    def test_read_returns_none_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert read_update_error() is None

    def test_write_and_clear(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        write_update_error("Install failed: permission denied")
        assert read_update_error() == "Install failed: permission denied"
        clear_update_error()
        assert read_update_error() is None
