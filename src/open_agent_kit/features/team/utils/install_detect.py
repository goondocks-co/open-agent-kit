"""Install method detection and channel-switch command builder.

Cross-platform: uses ``Path.parts`` and ``sys.platform`` throughout.
Never hardcodes Unix path separators as string literals.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
    CI_INSTALL_METHOD_HOMEBREW,
    CI_INSTALL_METHOD_PIPX,
    CI_INSTALL_METHOD_UNKNOWN,
    CI_INSTALL_METHOD_UV,
)


def detect_install_method(binary_name: str) -> str:
    """Detect how the current OAK binary was installed.

    Args:
        binary_name: The CLI binary name (e.g. ``"oak"``, ``"oak-beta"``).

    Returns:
        One of the ``CI_INSTALL_METHOD_*`` constants.
    """
    binary_path = shutil.which(binary_name)
    if binary_path:
        parts = set(Path(binary_path).parts)
        # Homebrew: "Cellar" or "homebrew" appear as path components (macOS only)
        if "Cellar" in parts or "homebrew" in parts:
            return CI_INSTALL_METHOD_HOMEBREW

    # pipx: check PIPX_HOME env var, then platform default
    pipx_home_env = os.environ.get("PIPX_HOME")
    if pipx_home_env:
        pipx_home = Path(pipx_home_env)
    elif sys.platform == "win32":
        pipx_home = Path.home() / "AppData" / "Roaming" / "pipx"
    else:
        pipx_home = Path.home() / ".local" / "share" / "pipx"

    if (pipx_home / "venvs" / "oak-ci").exists():
        return CI_INSTALL_METHOD_PIPX

    # uv: check UV_TOOL_DIR env var, then platform default
    uv_tool_dir_env = os.environ.get("UV_TOOL_DIR")
    if uv_tool_dir_env:
        uv_tool_dir = Path(uv_tool_dir_env)
    elif sys.platform == "win32":
        uv_tool_dir = Path.home() / "AppData" / "Roaming" / "uv" / "tools"
    else:
        uv_tool_dir = Path.home() / ".local" / "share" / "uv" / "tools"

    if (uv_tool_dir / "oak-ci").exists():
        return CI_INSTALL_METHOD_UV

    return CI_INSTALL_METHOD_UNKNOWN


def build_channel_switch_command(
    from_channel: str,
    to_channel: str,
    install_method: str,
    project_root: str,
) -> str | None:
    """Return a shell command to switch channels, or ``None`` if unsupported.

    Args:
        from_channel: Current release channel (``CI_CHANNEL_STABLE`` or ``CI_CHANNEL_BETA``).
        to_channel: Target release channel.
        install_method: How OAK was installed (``CI_INSTALL_METHOD_*``).
        project_root: Absolute path to the project root directory.

    Returns:
        A shell one-liner, or ``None`` when the install method does not support
        automated channel switching.
    """
    new_binary = "oak-beta" if to_channel == CI_CHANNEL_BETA else "oak"
    start_suffix = f"cd {shlex.quote(project_root)} && {new_binary} team start"

    if install_method == CI_INSTALL_METHOD_HOMEBREW:
        # macOS only — Homebrew is not available on Windows or Linux
        from_formula = "oak-ci" if from_channel == CI_CHANNEL_STABLE else "oak-ci-beta"
        to_formula = "oak-ci-beta" if to_channel == CI_CHANNEL_BETA else "oak-ci"
        return (
            f"brew uninstall {from_formula} && "
            f"brew install goondocks-co/oak/{to_formula} && {start_suffix}"
        )

    if install_method == CI_INSTALL_METHOD_UV:
        pre_flag = " --prerelease=allow" if to_channel == CI_CHANNEL_BETA else ""
        return f"uv tool install oak-ci --python python3.13{pre_flag} && {start_suffix}"

    if install_method == CI_INSTALL_METHOD_PIPX:
        pre_flag = " --pip-args='--pre'" if to_channel == CI_CHANNEL_BETA else ""
        suffix_flag = " --suffix=-beta" if to_channel == CI_CHANNEL_BETA else ""
        return f"pipx install oak-ci --python python3.13{pre_flag}{suffix_flag} && {start_suffix}"

    return None  # Unknown install method — UI shows manual instructions
