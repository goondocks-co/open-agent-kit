"""Smoke tests for release installer scripts."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH_PATH = REPO_ROOT / "install.sh"
INSTALL_PS1_PATH = REPO_ROOT / "install.ps1"

PIPX_FORCE_FLAG = "pipx install --force"
UV_FORCE_FLAG = "uv tool install --force"
PIP_USER_UPGRADE_FLAG = "pip install --user --upgrade"
INSTALL_VERIFICATION_TOKEN = "Installation verification failed for method"
PIPX_VERIFY_TOKEN = "pipx list --short"
UV_VERIFY_TOKEN = "uv tool list"
PIP_VERIFY_TOKEN = "-m pip show"

SHELL_BINARY = "sh"
POWERSHELL_BINARY = "pwsh"
SUCCESS_EXIT_CODE = 0


def test_install_sh_uses_idempotent_install_flags() -> None:
    """install.sh should force-install for pipx/uv and use pip --user --upgrade."""
    content = INSTALL_SH_PATH.read_text(encoding="utf-8")
    assert PIPX_FORCE_FLAG in content
    assert UV_FORCE_FLAG in content
    assert PIP_USER_UPGRADE_FLAG in content


def test_install_ps1_uses_idempotent_install_flags() -> None:
    """install.ps1 should force-install for pipx/uv and use pip --user --upgrade."""
    content = INSTALL_PS1_PATH.read_text(encoding="utf-8")
    assert PIPX_FORCE_FLAG in content
    assert UV_FORCE_FLAG in content
    assert PIP_USER_UPGRADE_FLAG in content


def test_install_scripts_verify_selected_method() -> None:
    """Both installers should verify installs using method-specific checks."""
    shell_content = INSTALL_SH_PATH.read_text(encoding="utf-8")
    powershell_content = INSTALL_PS1_PATH.read_text(encoding="utf-8")

    assert INSTALL_VERIFICATION_TOKEN in shell_content
    assert INSTALL_VERIFICATION_TOKEN in powershell_content

    assert PIPX_VERIFY_TOKEN in shell_content
    assert PIPX_VERIFY_TOKEN in powershell_content
    assert UV_VERIFY_TOKEN in shell_content
    assert UV_VERIFY_TOKEN in powershell_content
    assert PIP_VERIFY_TOKEN in shell_content
    assert PIP_VERIFY_TOKEN in powershell_content


def test_install_sh_has_valid_syntax() -> None:
    """install.sh should parse successfully with POSIX shell."""
    result = subprocess.run(
        [SHELL_BINARY, "-n", str(INSTALL_SH_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == SUCCESS_EXIT_CODE, result.stderr


@pytest.mark.skipif(shutil.which(POWERSHELL_BINARY) is None, reason="pwsh not available")
def test_install_ps1_has_valid_syntax() -> None:
    """install.ps1 should parse successfully in PowerShell."""
    command = (
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{INSTALL_PS1_PATH}',[ref]$null,[ref]$null)"
    )
    result = subprocess.run(
        [POWERSHELL_BINARY, "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == SUCCESS_EXIT_CODE, result.stderr
