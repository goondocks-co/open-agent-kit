"""Detect how OAK was installed to determine the correct update command.

Each install method (Homebrew, uv tool, pipx, pip --user) creates a Python
environment with pip. This module detects which one and returns the appropriate
install command for a staged wheel.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

from open_agent_kit.utils.install_detection import get_install_source
from open_agent_kit.utils.platform import is_uv_tool_install

_HOMEBREW_CELLAR_PREFIXES = ("/opt/homebrew/Cellar/", "/usr/local/Cellar/")
_PIPX_VENV_MARKER = "/pipx/venvs/"


class InstallMethod(str, Enum):
    """How OAK was installed on this machine."""

    EDITABLE = "editable"
    HOMEBREW = "homebrew"
    UV_TOOL = "uv_tool"
    PIPX = "pipx"
    PIP_USER = "pip_user"


def detect_install_method() -> InstallMethod:
    """Detect the install method by inspecting sys.executable and metadata."""
    _, is_editable = get_install_source()
    if is_editable:
        return InstallMethod.EDITABLE

    executable = sys.executable

    # Homebrew: Python lives inside Cellar
    for prefix in _HOMEBREW_CELLAR_PREFIXES:
        if prefix in executable:
            return InstallMethod.HOMEBREW

    # uv tool: uses isolated tool venv
    if is_uv_tool_install():
        return InstallMethod.UV_TOOL

    # pipx: Python lives inside pipx venvs directory
    if _PIPX_VENV_MARKER in executable:
        return InstallMethod.PIPX

    return InstallMethod.PIP_USER


def _find_homebrew_pip() -> str:
    """Find the pip binary inside the Homebrew libexec venv."""
    executable = Path(sys.executable)
    # sys.executable is like /opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13
    # pip is at the same level: .../libexec/bin/pip
    return str(executable.parent / "pip")


def get_install_command(method: InstallMethod, wheel_path: str) -> list[str]:
    """Return the shell command to install a staged wheel for the given method.

    Args:
        method: The detected install method.
        wheel_path: Absolute path to the staged .whl file.

    Returns:
        List of command arguments suitable for subprocess.

    Raises:
        ValueError: If method is EDITABLE (should never be called).
    """
    if method == InstallMethod.EDITABLE:
        msg = "Cannot generate install command for editable installs"
        raise ValueError(msg)

    if method == InstallMethod.HOMEBREW:
        pip_path = _find_homebrew_pip()
        return [pip_path, "install", wheel_path]

    if method == InstallMethod.UV_TOOL:
        return ["uv", "tool", "install", wheel_path, "--force"]

    if method == InstallMethod.PIPX:
        return ["pipx", "install", wheel_path, "--force"]

    # PIP_USER fallback
    return [sys.executable, "-m", "pip", "install", "--user", wheel_path]


__all__ = ["InstallMethod", "detect_install_method", "get_install_command"]
