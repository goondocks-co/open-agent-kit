"""Tests for install source detection utilities.

Tests cover:
- get_install_source() with PyPI install (no direct_url.json)
- get_install_source() with local/editable install
- get_install_source() with git URL install
- get_install_source() graceful fallback on missing metadata
- is_uv_tool_install() environment detection
"""

from unittest.mock import MagicMock, patch

from open_agent_kit.utils.install_detection import get_install_source
from open_agent_kit.utils.platform import is_uv_tool_install

# Patch target: distribution is imported lazily inside get_install_source(),
# so we patch it at the stdlib level where the local import resolves.
_DISTRIBUTION_PATH = "importlib.metadata.distribution"


# =============================================================================
# get_install_source()
# =============================================================================


class TestGetInstallSource:
    """Test get_install_source() with mocked importlib.metadata."""

    def test_pypi_install_returns_none(self) -> None:
        """PyPI install has no direct_url.json -- returns (None, False)."""
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = None

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source is None
        assert is_editable is False

    def test_local_editable_install(self) -> None:
        """Editable local install returns the file path and is_editable=True."""
        import json

        direct_url_data = {
            "url": "file:///home/user/projects/oak",
            "dir_info": {"editable": True},
        }
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = json.dumps(direct_url_data)

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source == "/home/user/projects/oak"
        assert is_editable is True

    def test_local_non_editable_install(self) -> None:
        """Non-editable local install returns the file path and is_editable=False."""
        import json

        direct_url_data = {
            "url": "file:///opt/oak",
            "dir_info": {},
        }
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = json.dumps(direct_url_data)

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source == "/opt/oak"
        assert is_editable is False

    def test_git_url_install(self) -> None:
        """Git URL install returns vcs+url and is_editable=False."""
        import json

        direct_url_data = {
            "url": "https://github.com/user/oak.git",
            "vcs_info": {"vcs": "git", "commit_id": "abc123"},
        }
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = json.dumps(direct_url_data)

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source == "git+https://github.com/user/oak.git"
        assert is_editable is False

    def test_git_install_is_never_editable(self) -> None:
        """Even if dir_info.editable is set, git installs return is_editable=False."""
        import json

        direct_url_data = {
            "url": "https://github.com/user/oak.git",
            "vcs_info": {"vcs": "git", "commit_id": "abc123"},
            "dir_info": {"editable": True},
        }
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = json.dumps(direct_url_data)

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source == "git+https://github.com/user/oak.git"
        assert is_editable is False

    def test_missing_metadata_returns_fallback(self) -> None:
        """When distribution() raises, returns (None, False) gracefully."""
        with patch(
            _DISTRIBUTION_PATH,
            side_effect=Exception("Package not found"),
        ):
            source, is_editable = get_install_source("nonexistent-pkg")

        assert source is None
        assert is_editable is False

    def test_corrupt_json_returns_fallback(self) -> None:
        """When direct_url.json contains invalid JSON, returns (None, False)."""
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = "not valid json {{"

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist):
            source, is_editable = get_install_source("test-pkg")

        assert source is None
        assert is_editable is False

    def test_default_package_name(self) -> None:
        """Default package name is 'oak-ci'."""
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = None

        with patch(_DISTRIBUTION_PATH, return_value=mock_dist) as mock_fn:
            get_install_source()

        mock_fn.assert_called_once_with("oak-ci")


# =============================================================================
# is_uv_tool_install()
# =============================================================================


class TestIsUvToolInstall:
    """Test is_uv_tool_install() with mocked sys.executable."""

    def test_detects_posix_uv_tool_path(self) -> None:
        """Returns True when sys.executable contains POSIX uv tools path."""
        fake_executable = "/home/user/.local/share/uv/tools/oak-ci/bin/python3"
        with patch("open_agent_kit.utils.platform.sys") as mock_sys:
            mock_sys.executable = fake_executable
            mock_sys.platform = "linux"
            assert is_uv_tool_install() is True

    def test_returns_false_for_system_python(self) -> None:
        """Returns False for a regular system Python path."""
        fake_executable = "/usr/bin/python3"
        with patch("open_agent_kit.utils.platform.sys") as mock_sys:
            mock_sys.executable = fake_executable
            mock_sys.platform = "linux"
            assert is_uv_tool_install() is False

    def test_returns_false_for_venv_python(self) -> None:
        """Returns False for a virtualenv Python."""
        fake_executable = "/home/user/project/.venv/bin/python3"
        with patch("open_agent_kit.utils.platform.sys") as mock_sys:
            mock_sys.executable = fake_executable
            mock_sys.platform = "linux"
            assert is_uv_tool_install() is False
