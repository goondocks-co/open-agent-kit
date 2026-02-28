"""Smoke tests for release installer scripts."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH_PATH = REPO_ROOT / "install.sh"
INSTALL_PS1_PATH = REPO_ROOT / "install.ps1"

PIPX_UNINSTALL_TOKEN = "pipx uninstall"
UV_UNINSTALL_TOKEN = "uv tool uninstall"
PIP_USER_UPGRADE_FLAG = "pip install --user --upgrade"
INSTALL_VERIFICATION_TOKEN = "Installation verification failed for method"
PIPX_VERIFY_TOKEN = "pipx list --short"
UV_VERIFY_TOKEN = "uv tool list"
PIP_VERIFY_TOKEN = "-m pip show"

BETA_CHANNEL_TOKEN = "OAK_CHANNEL"
PIPX_BETA_SUFFIX_TOKEN = "--suffix=-beta"
PIPX_BETA_PRE_FLAG_TOKEN = "--pip-args="
UV_BETA_FLAG_TOKEN = "--prerelease=allow"
PIP_BETA_FLAG_TOKEN = "--pre"
BETA_BINARY_TOKEN = "oak-beta"

SHELL_BINARY = "sh"
POWERSHELL_BINARY = "pwsh"
SUCCESS_EXIT_CODE = 0


def test_install_sh_uses_idempotent_install_flags() -> None:
    """install.sh should uninstall-then-install for pipx/uv and use pip --user --upgrade."""
    content = INSTALL_SH_PATH.read_text(encoding="utf-8")
    assert PIPX_UNINSTALL_TOKEN in content
    assert UV_UNINSTALL_TOKEN in content
    assert PIP_USER_UPGRADE_FLAG in content


def test_install_ps1_uses_idempotent_install_flags() -> None:
    """install.ps1 should uninstall-then-install for pipx/uv and use pip --user --upgrade."""
    content = INSTALL_PS1_PATH.read_text(encoding="utf-8")
    assert PIPX_UNINSTALL_TOKEN in content
    assert UV_UNINSTALL_TOKEN in content
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


def test_install_scripts_support_beta_channel() -> None:
    """Both installers must honour OAK_CHANNEL=beta and produce the oak-beta binary."""
    sh_content = INSTALL_SH_PATH.read_text(encoding="utf-8")
    ps1_content = INSTALL_PS1_PATH.read_text(encoding="utf-8")

    for content, name in ((sh_content, "install.sh"), (ps1_content, "install.ps1")):
        assert BETA_CHANNEL_TOKEN in content, f"{name}: missing OAK_CHANNEL support"
        assert PIPX_BETA_SUFFIX_TOKEN in content, f"{name}: missing --suffix=-beta for pipx beta"
        assert PIPX_BETA_PRE_FLAG_TOKEN in content, f"{name}: missing --pip-args for pipx beta"
        assert UV_BETA_FLAG_TOKEN in content, f"{name}: missing --prerelease=allow for uv beta"
        assert PIP_BETA_FLAG_TOKEN in content, f"{name}: missing --pre for pip beta"
        assert BETA_BINARY_TOKEN in content, f"{name}: missing oak-beta binary reference"


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
