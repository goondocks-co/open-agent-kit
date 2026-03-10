"""Tests for install method detection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from open_agent_kit.utils.install_method import (
    InstallMethod,
    detect_install_method,
    get_install_command,
)


class TestDetectInstallMethod:
    """Test install method detection from sys.executable."""

    def test_detects_editable(self) -> None:
        with patch(
            "open_agent_kit.utils.install_method.get_install_source", return_value=("/path", True)
        ):
            assert detect_install_method() == InstallMethod.EDITABLE

    def test_detects_homebrew_apple_silicon(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
        ):
            mock_sys.executable = "/opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            mock_sys.platform = "darwin"
            assert detect_install_method() == InstallMethod.HOMEBREW

    def test_detects_homebrew_intel(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
        ):
            mock_sys.executable = "/usr/local/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            mock_sys.platform = "darwin"
            assert detect_install_method() == InstallMethod.HOMEBREW

    def test_detects_uv_tool(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
            patch("open_agent_kit.utils.install_method.is_uv_tool_install", return_value=True),
        ):
            mock_sys.executable = "/home/user/.local/share/uv/tools/oak-ci/bin/python3.13"
            mock_sys.platform = "linux"
            assert detect_install_method() == InstallMethod.UV_TOOL

    def test_detects_pipx(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
            patch("open_agent_kit.utils.install_method.is_uv_tool_install", return_value=False),
        ):
            mock_sys.executable = "/home/user/.local/share/pipx/venvs/oak-ci/bin/python3.13"
            mock_sys.platform = "linux"
            assert detect_install_method() == InstallMethod.PIPX

    def test_falls_back_to_pip(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
            patch("open_agent_kit.utils.install_method.is_uv_tool_install", return_value=False),
        ):
            mock_sys.executable = "/usr/bin/python3.13"
            mock_sys.platform = "linux"
            assert detect_install_method() == InstallMethod.PIP_USER


class TestGetInstallCommand:
    """Test install command generation for each method."""

    def test_homebrew_uses_libexec_pip(self) -> None:
        wheel = "/tmp/oak_ci-1.3.0.whl"
        with patch("open_agent_kit.utils.install_method.sys") as mock_sys:
            mock_sys.executable = "/opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            cmd = get_install_command(InstallMethod.HOMEBREW, wheel)
        assert "libexec/bin/pip" in cmd[0]
        assert "install" in cmd
        assert wheel in cmd

    def test_uv_tool_uses_force(self) -> None:
        wheel = "/tmp/oak_ci-1.3.0.whl"
        cmd = get_install_command(InstallMethod.UV_TOOL, wheel)
        assert cmd[0] == "uv"
        assert "tool" in cmd
        assert "--force" in cmd
        assert wheel in cmd

    def test_pipx_uses_force(self) -> None:
        wheel = "/tmp/oak_ci-1.3.0.whl"
        cmd = get_install_command(InstallMethod.PIPX, wheel)
        assert cmd[0] == "pipx"
        assert "--force" in cmd
        assert wheel in cmd

    def test_pip_user_uses_user_flag(self) -> None:
        wheel = "/tmp/oak_ci-1.3.0.whl"
        cmd = get_install_command(InstallMethod.PIP_USER, wheel)
        assert "--user" in cmd
        assert wheel in cmd

    def test_editable_raises(self) -> None:
        with pytest.raises(ValueError, match="editable"):
            get_install_command(InstallMethod.EDITABLE, "/tmp/wheel.whl")
