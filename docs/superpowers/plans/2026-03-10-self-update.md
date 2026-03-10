# Self-Update System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daemon-driven self-update system that auto-downloads new OAK releases from PyPI and applies them with a single click, plus a channel redesign from two binaries to one binary with config toggle.

**Architecture:** The daemon periodically polls PyPI for new versions, downloads the wheel to a global staging directory (`~/.oak/staging/`), and notifies the user via a subtle badge on the About icon. When the user clicks "Apply Update," a detached shell script installs the wheel, runs project upgrade, and restarts the daemon. Multi-daemon coordination uses a file lock so only one daemon per machine downloads.

**Tech Stack:** Python 3.13, FastAPI, httpx, React/TypeScript (Vite), packaging library, fcntl (POSIX file locking)

**Spec:** `docs/superpowers/specs/2026-03-09-self-update-design.md`

---

## Chunk 1: Foundation — Global Config + Install Method Detection

This chunk builds the foundation: the `~/.oak/` global directory, update config management, and install method detection for the update script.

### Task 1: Global Update Config Module

**Files:**
- Create: `src/open_agent_kit/utils/global_config.py`
- Test: `tests/unit/utils/test_global_config.py`

- [ ] **Step 1: Write tests for global config**

```python
# tests/unit/utils/test_global_config.py
"""Tests for ~/.oak/ global config management."""
import json
from pathlib import Path

import pytest
import yaml

from open_agent_kit.utils.global_config import (
    GLOBAL_OAK_DIR_NAME,
    UPDATE_CONFIG_FILE,
    STAGED_UPDATE_FILE,
    LAST_CHECK_FILE,
    UPDATE_ERROR_FILE,
    RELEASE_NOTES_CACHE_FILE,
    STAGING_DIR,
    LOCK_FILE,
    UpdateConfig,
    get_global_oak_dir,
    load_update_config,
    save_update_config,
    read_staged_update,
    write_staged_update,
    read_last_check,
    write_last_check,
    read_update_error,
    write_update_error,
    clear_update_error,
    ensure_global_dir,
)


class TestGetGlobalOakDir:
    """Test global directory path resolution."""

    def test_returns_home_dot_oak(self) -> None:
        result = get_global_oak_dir()
        assert result == Path.home() / GLOBAL_OAK_DIR_NAME

    def test_respects_override_env_var(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path / "custom"))
        result = get_global_oak_dir()
        assert result == tmp_path / "custom"


class TestEnsureGlobalDir:
    """Test directory creation."""

    def test_creates_directory_if_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        oak_dir = tmp_path / ".oak"
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(oak_dir))
        result = ensure_global_dir()
        assert result is True
        assert oak_dir.exists()
        assert (oak_dir / STAGING_DIR).exists()

    def test_returns_false_on_permission_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_load_returns_defaults_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_read_returns_none_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert read_staged_update() is None

    def test_write_and_read_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_read_returns_none_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert read_update_error() is None

    def test_write_and_clear(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        write_update_error("Install failed: permission denied")
        assert read_update_error() == "Install failed: permission denied"
        clear_update_error()
        assert read_update_error() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/utils/test_global_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement global config module**

```python
# src/open_agent_kit/utils/global_config.py
"""Global OAK configuration at ~/.oak/ for machine-wide update state.

Distinct from the per-project .oak/ directory. Holds update channel config,
staged wheels, lock files, and last-check timestamps.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

GLOBAL_OAK_DIR_NAME = ".oak"
UPDATE_CONFIG_FILE = "update.yaml"
STAGED_UPDATE_FILE = "staged-update.json"
LAST_CHECK_FILE = "last-check.json"
UPDATE_ERROR_FILE = "update-error.json"
RELEASE_NOTES_CACHE_FILE = "release-notes-cache.json"
STAGING_DIR = "staging"
LOCK_FILE = "update.lock"

# Defaults
DEFAULT_CHANNEL = "stable"
DEFAULT_AUTO_DOWNLOAD = True
DEFAULT_CHECK_INTERVAL_HOURS = 6


def get_global_oak_dir() -> Path:
    """Return the global ~/.oak/ directory path.

    Respects OAK_GLOBAL_DIR env var for testing/override.
    """
    override = os.environ.get("OAK_GLOBAL_DIR")
    if override:
        return Path(override)
    return Path.home() / GLOBAL_OAK_DIR_NAME


def ensure_global_dir() -> bool:
    """Create ~/.oak/ and subdirectories if they don't exist.

    Returns True on success, False if creation failed (permissions, etc.).
    """
    oak_dir = get_global_oak_dir()
    try:
        oak_dir.mkdir(mode=0o755, exist_ok=True)
        (oak_dir / STAGING_DIR).mkdir(mode=0o755, exist_ok=True)
        return True
    except OSError as exc:
        logger.warning("Cannot create global OAK directory %s: %s", oak_dir, exc)
        return False


@dataclass
class UpdateConfig:
    """Update configuration from ~/.oak/update.yaml."""

    channel: str = DEFAULT_CHANNEL
    auto_download: bool = DEFAULT_AUTO_DOWNLOAD
    check_interval_hours: int = DEFAULT_CHECK_INTERVAL_HOURS


def load_update_config() -> UpdateConfig:
    """Load update config from ~/.oak/update.yaml, returning defaults if missing."""
    config_path = get_global_oak_dir() / UPDATE_CONFIG_FILE
    try:
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text()) or {}
            update = raw.get("update", {})
            return UpdateConfig(
                channel=update.get("channel", DEFAULT_CHANNEL),
                auto_download=update.get("auto_download", DEFAULT_AUTO_DOWNLOAD),
                check_interval_hours=update.get("check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS),
            )
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to load update config: %s", exc)
    return UpdateConfig()


def save_update_config(config: UpdateConfig) -> None:
    """Save update config to ~/.oak/update.yaml."""
    config_path = get_global_oak_dir() / UPDATE_CONFIG_FILE
    data = {
        "update": {
            "channel": config.channel,
            "auto_download": config.auto_download,
            "check_interval_hours": config.check_interval_hours,
        }
    }
    config_path.write_text(yaml.dump(data, default_flow_style=False))


def _read_json(filename: str) -> dict | None:
    """Read a JSON file from the global dir, returning None if missing."""
    path = get_global_oak_dir() / filename
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return None


def _write_json(filename: str, data: dict) -> None:
    """Write a JSON file to the global dir."""
    path = get_global_oak_dir() / filename
    path.write_text(json.dumps(data, indent=2))


def read_staged_update() -> dict | None:
    """Read staged-update.json metadata."""
    return _read_json(STAGED_UPDATE_FILE)


def write_staged_update(data: dict) -> None:
    """Write staged-update.json metadata."""
    _write_json(STAGED_UPDATE_FILE, data)


def read_last_check() -> dict | None:
    """Read last-check.json timestamp and result."""
    return _read_json(LAST_CHECK_FILE)


def write_last_check(data: dict) -> None:
    """Write last-check.json timestamp and result."""
    _write_json(LAST_CHECK_FILE, data)


def read_update_error() -> str | None:
    """Read the last update error message, or None if no error."""
    data = _read_json(UPDATE_ERROR_FILE)
    if data:
        return data.get("error")
    return None


def write_update_error(message: str) -> None:
    """Write an update error message."""
    _write_json(UPDATE_ERROR_FILE, {"error": message})


def clear_update_error() -> None:
    """Remove the update error file."""
    path = get_global_oak_dir() / UPDATE_ERROR_FILE
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/utils/test_global_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/utils/global_config.py tests/unit/utils/test_global_config.py
git commit -m "feat(self-update): add global config module for ~/.oak/ directory"
```

---

### Task 2: Install Method Detection for Update Script

**Files:**
- Create: `src/open_agent_kit/utils/install_method.py`
- Test: `tests/unit/utils/test_install_method.py`

This module detects HOW oak was installed so the update script knows what command to run.

- [ ] **Step 1: Write tests for install method detection**

```python
# tests/unit/utils/test_install_method.py
"""Tests for install method detection."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.utils.install_method import (
    InstallMethod,
    detect_install_method,
    get_install_command,
)


class TestDetectInstallMethod:
    """Test install method detection from sys.executable."""

    def test_detects_editable(self) -> None:
        with patch("open_agent_kit.utils.install_method.get_install_source", return_value=("/path", True)):
            assert detect_install_method() == InstallMethod.EDITABLE

    def test_detects_homebrew_apple_silicon(self) -> None:
        with (
            patch("open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
        ):
            mock_sys.executable = "/opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            mock_sys.platform = "darwin"
            assert detect_install_method() == InstallMethod.HOMEBREW

    def test_detects_homebrew_intel(self) -> None:
        with (
            patch("open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
        ):
            mock_sys.executable = "/usr/local/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            mock_sys.platform = "darwin"
            assert detect_install_method() == InstallMethod.HOMEBREW

    def test_detects_uv_tool(self) -> None:
        with (
            patch("open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
            patch("open_agent_kit.utils.install_method.is_uv_tool_install", return_value=True),
        ):
            mock_sys.executable = "/home/user/.local/share/uv/tools/oak-ci/bin/python3.13"
            mock_sys.platform = "linux"
            assert detect_install_method() == InstallMethod.UV_TOOL

    def test_detects_pipx(self) -> None:
        with (
            patch("open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.install_method.sys") as mock_sys,
            patch("open_agent_kit.utils.install_method.is_uv_tool_install", return_value=False),
        ):
            mock_sys.executable = "/home/user/.local/share/pipx/venvs/oak-ci/bin/python3.13"
            mock_sys.platform = "linux"
            assert detect_install_method() == InstallMethod.PIPX

    def test_falls_back_to_pip(self) -> None:
        with (
            patch("open_agent_kit.utils.install_method.get_install_source", return_value=(None, False)),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/utils/test_install_method.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement install method detection**

```python
# src/open_agent_kit/utils/install_method.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/utils/test_install_method.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/utils/install_method.py tests/unit/utils/test_install_method.py
git commit -m "feat(self-update): add install method detection for update script"
```

---

### Task 3: Self-Update Exemption Check

**Files:**
- Create: `src/open_agent_kit/utils/update_exempt.py`
- Test: `tests/unit/utils/test_update_exempt.py`

Single function that checks all exemption reasons. Used by UpdateChecker, API routes, and UI.

- [ ] **Step 1: Write tests**

```python
# tests/unit/utils/test_update_exempt.py
"""Tests for self-update exemption checks."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from open_agent_kit.utils.update_exempt import (
    UpdateExemption,
    check_update_exempt,
)


class TestCheckUpdateExempt:
    """Test exemption detection."""

    def test_not_exempt_on_normal_install(self) -> None:
        with (
            patch("open_agent_kit.utils.update_exempt.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            result = check_update_exempt()
        assert result is None

    def test_exempt_on_editable_install(self) -> None:
        with (
            patch("open_agent_kit.utils.update_exempt.get_install_source", return_value=("/path", True)),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "editable_install"

    def test_exempt_on_windows(self) -> None:
        with (
            patch("open_agent_kit.utils.update_exempt.get_install_source", return_value=(None, False)),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "windows_unsupported"

    def test_editable_takes_priority_over_windows(self) -> None:
        with (
            patch("open_agent_kit.utils.update_exempt.get_install_source", return_value=("/path", True)),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "editable_install"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/utils/test_update_exempt.py -v`
Expected: FAIL

- [ ] **Step 3: Implement exemption check**

```python
# src/open_agent_kit/utils/update_exempt.py
"""Self-update exemption checks.

Two categories are exempt: editable installs (development) and Windows.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from open_agent_kit.utils.install_detection import get_install_source


@dataclass(frozen=True)
class UpdateExemption:
    """Reason why self-update is disabled."""

    reason: str  # "editable_install" | "windows_unsupported"
    message: str


def check_update_exempt() -> UpdateExemption | None:
    """Check if self-update should be disabled.

    Returns None if self-update is allowed, or an UpdateExemption with the reason.
    """
    _, is_editable = get_install_source()
    if is_editable:
        return UpdateExemption(
            reason="editable_install",
            message="Self-update is disabled for editable (development) installs.",
        )

    if sys.platform == "win32":
        return UpdateExemption(
            reason="windows_unsupported",
            message="Self-update is not yet supported on Windows. Use pip install --upgrade oak-ci.",
        )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/utils/test_update_exempt.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/utils/update_exempt.py tests/unit/utils/test_update_exempt.py
git commit -m "feat(self-update): add exemption checks for editable installs and Windows"
```

---

## Chunk 2: Update Checker + Downloader

Core update logic: polling PyPI for new versions and downloading wheels.

### Task 4: Update Checker — PyPI Version Polling

**Files:**
- Create: `src/open_agent_kit/features/team/daemon/lifecycle/update_checker.py`
- Test: `tests/unit/features/team/daemon/test_update_checker.py`
- Modify: `src/open_agent_kit/utils/release_channel.py:54-90` (reuse `fetch_pypi_raw`, `parse_pypi_versions`)

The checker polls PyPI, filters by channel, and determines if a newer version is available.

- [ ] **Step 1: Write tests for update checker**

```python
# tests/unit/features/team/daemon/test_update_checker.py
"""Tests for the PyPI update checker."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
    UpdateCheckResult,
    check_for_update,
    should_check_now,
)
from open_agent_kit.utils.global_config import UpdateConfig


_PYPI_RESPONSE = json.dumps({
    "releases": {
        "1.0.0": [],
        "1.1.0": [],
        "1.2.0": [],
        "1.3.0b1": [],
        "1.3.0b2": [],
    }
}).encode()


class TestCheckForUpdate:
    """Test the core version check logic."""

    @pytest.mark.asyncio
    async def test_detects_newer_stable_version(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.1.0", config=config)
        assert result.update_available is True
        assert result.latest_version == "1.2.0"

    @pytest.mark.asyncio
    async def test_no_update_when_current(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.2.0", config=config)
        assert result.update_available is False

    @pytest.mark.asyncio
    async def test_beta_channel_considers_prereleases(self) -> None:
        config = UpdateConfig(channel="beta")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.2.0", config=config)
        assert result.update_available is True
        assert result.latest_version == "1.3.0b2"

    @pytest.mark.asyncio
    async def test_beta_channel_prefers_stable_if_newer(self) -> None:
        """If latest stable > latest beta, offer stable even on beta channel."""
        pypi_data = json.dumps({
            "releases": {"2.0.0": [], "1.9.0b1": []}
        }).encode()
        config = UpdateConfig(channel="beta")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=pypi_data,
        ):
            result = await check_for_update(running_version="1.8.0", config=config)
        assert result.latest_version == "2.0.0"

    @pytest.mark.asyncio
    async def test_no_downgrade(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="5.0.0", config=config)
        assert result.update_available is False

    @pytest.mark.asyncio
    async def test_handles_pypi_failure(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            side_effect=Exception("Network error"),
        ):
            result = await check_for_update(running_version="1.0.0", config=config)
        assert result.update_available is False
        assert result.error is not None


class TestShouldCheckNow:
    """Test check interval logic."""

    def test_true_when_no_last_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert should_check_now(check_interval_hours=6) is True

    def test_false_when_recently_checked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir, write_last_check
        ensure_global_dir()
        write_last_check({"timestamp": time.time(), "version": "1.0.0"})
        assert should_check_now(check_interval_hours=6) is False

    def test_true_when_interval_expired(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir, write_last_check
        ensure_global_dir()
        write_last_check({"timestamp": time.time() - 7 * 3600, "version": "1.0.0"})
        assert should_check_now(check_interval_hours=6) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_checker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update checker**

```python
# src/open_agent_kit/features/team/daemon/lifecycle/update_checker.py
"""PyPI update checker for the self-update system.

Periodically polls PyPI to detect new OAK versions. Filters by channel
config (stable/beta) and applies no-downgrade rule.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from packaging.version import Version

from open_agent_kit.utils.global_config import (
    UpdateConfig,
    load_update_config,
    read_last_check,
    write_last_check,
)
from open_agent_kit.utils.release_channel import fetch_pypi_raw, parse_pypi_versions

logger = logging.getLogger(__name__)

PYPI_PACKAGE_NAME = "oak-ci"


@dataclass
class UpdateCheckResult:
    """Result of a PyPI version check."""

    update_available: bool = False
    latest_version: str | None = None
    running_version: str | None = None
    channel: str = "stable"
    error: str | None = None
    checked_at: float = field(default_factory=time.time)


def should_check_now(check_interval_hours: int) -> bool:
    """Return True if enough time has passed since the last check."""
    last = read_last_check()
    if not last or "timestamp" not in last:
        return True
    elapsed_hours = (time.time() - last["timestamp"]) / 3600
    return elapsed_hours >= check_interval_hours


async def check_for_update(
    running_version: str,
    config: UpdateConfig | None = None,
) -> UpdateCheckResult:
    """Check PyPI for a newer version of OAK.

    Args:
        running_version: The currently running OAK version string.
        config: Update config (loaded from ~/.oak/update.yaml if None).

    Returns:
        UpdateCheckResult with version info and availability.
    """
    if config is None:
        config = load_update_config()

    try:
        # fetch_pypi_raw is synchronous — run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, fetch_pypi_raw)
        stable_str, beta_str = parse_pypi_versions(raw)

        # Determine the best available version for this channel
        if config.channel == "beta":
            # Beta channel: max(stable, beta) — never downgrade
            candidates = []
            if stable_str:
                candidates.append(Version(stable_str))
            if beta_str:
                candidates.append(Version(beta_str))
            best = max(candidates) if candidates else None
        else:
            # Stable channel: only stable releases
            best = Version(stable_str) if stable_str else None

        if best is None:
            return UpdateCheckResult(
                running_version=running_version,
                channel=config.channel,
            )

        running = Version(running_version)
        is_newer = best > running

        result = UpdateCheckResult(
            update_available=is_newer,
            latest_version=str(best) if is_newer else None,
            running_version=running_version,
            channel=config.channel,
        )

        # Record the check
        write_last_check({
            "timestamp": time.time(),
            "version": str(best),
            "update_available": is_newer,
            "channel": config.channel,
        })

        return result

    except Exception as exc:
        logger.warning("PyPI update check failed: %s", exc)
        return UpdateCheckResult(
            running_version=running_version,
            channel=config.channel,
            error=str(exc),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_checker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/lifecycle/update_checker.py tests/unit/features/team/daemon/test_update_checker.py
git commit -m "feat(self-update): add PyPI update checker with channel filtering"
```

---

### Task 5: Update Downloader — Wheel Staging

**Files:**
- Create: `src/open_agent_kit/features/team/daemon/lifecycle/update_downloader.py`
- Test: `tests/unit/features/team/daemon/test_update_downloader.py`

Downloads a wheel from PyPI, verifies checksum, stages it in `~/.oak/staging/`.

- [ ] **Step 1: Write tests for update downloader**

```python
# tests/unit/features/team/daemon/test_update_downloader.py
"""Tests for wheel download and staging."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_downloader import (
    download_and_stage,
    clean_staging,
    _find_wheel_url,
)
from open_agent_kit.utils.global_config import ensure_global_dir, read_staged_update


_FAKE_WHEEL_CONTENT = b"PK\x03\x04fake-wheel-content-for-testing"
_FAKE_SHA256 = hashlib.sha256(_FAKE_WHEEL_CONTENT).hexdigest()

_PYPI_JSON = {
    "releases": {
        "1.3.0": [
            {
                "filename": "oak_ci-1.3.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/oak_ci-1.3.0-py3-none-any.whl",
                "digests": {"sha256": _FAKE_SHA256},
                "packagetype": "bdist_wheel",
            },
            {
                "filename": "oak_ci-1.3.0.tar.gz",
                "url": "https://files.pythonhosted.org/packages/oak_ci-1.3.0.tar.gz",
                "digests": {"sha256": "ignored"},
                "packagetype": "sdist",
            },
        ]
    }
}


class TestFindWheelUrl:
    """Test wheel URL extraction from PyPI metadata."""

    def test_finds_wheel_not_sdist(self) -> None:
        url, sha, filename = _find_wheel_url(_PYPI_JSON, "1.3.0")
        assert "whl" in url
        assert sha == _FAKE_SHA256
        assert filename == "oak_ci-1.3.0-py3-none-any.whl"

    def test_raises_when_version_missing(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            _find_wheel_url(_PYPI_JSON, "9.9.9")

    def test_raises_when_no_wheel(self) -> None:
        data = {"releases": {"1.0.0": [{"packagetype": "sdist", "filename": "x.tar.gz", "url": "x", "digests": {"sha256": "x"}}]}}
        with pytest.raises(ValueError, match="No wheel"):
            _find_wheel_url(data, "1.0.0")


class TestCleanStaging:
    """Test staging directory cleanup."""

    def test_removes_existing_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        (tmp_path / "staging" / "old_wheel.whl").write_bytes(b"old")
        clean_staging()
        assert list((tmp_path / "staging").iterdir()) == []


class TestDownloadAndStage:
    """Test full download + verify + stage flow."""

    @pytest.mark.asyncio
    async def test_successful_download(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader.fetch_pypi_raw",
                return_value=json.dumps(_PYPI_JSON).encode(),
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._download_file",
                new_callable=AsyncMock,
                return_value=_FAKE_WHEEL_CONTENT,
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._try_acquire_lock",
                return_value=MagicMock(__enter__=MagicMock(return_value=True), __exit__=MagicMock(return_value=False)),
            ),
        ):
            result = await download_and_stage("1.3.0", channel="stable")

        assert result is True
        staged = read_staged_update()
        assert staged is not None
        assert staged["version"] == "1.3.0"
        assert staged["channel"] == "stable"
        assert staged["schema_version"] == 1
        # Wheel file exists
        wheel_path = Path(staged["wheel_path"])
        assert wheel_path.exists()

    @pytest.mark.asyncio
    async def test_checksum_mismatch_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader.fetch_pypi_raw",
                return_value=json.dumps(_PYPI_JSON).encode(),
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._download_file",
                new_callable=AsyncMock,
                return_value=b"corrupted-content",
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._try_acquire_lock",
                return_value=MagicMock(__enter__=MagicMock(return_value=True), __exit__=MagicMock(return_value=False)),
            ),
        ):
            result = await download_and_stage("1.3.0")

        assert result is False
        assert read_staged_update() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_downloader.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update downloader**

```python
# src/open_agent_kit/features/team/daemon/lifecycle/update_downloader.py
"""Download and stage OAK wheels from PyPI.

Downloads the wheel for a specific version, verifies its SHA256 checksum,
and stages it in ~/.oak/staging/ for later installation.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import httpx

# fcntl is POSIX-only; Windows is exempt from self-update but we guard the import
if sys.platform != "win32":
    import fcntl

from open_agent_kit.utils.global_config import (
    LOCK_FILE,
    STAGING_DIR,
    get_global_oak_dir,
    read_staged_update,
    write_staged_update,
)
from open_agent_kit.utils.release_channel import fetch_pypi_raw

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 120


def _find_wheel_url(pypi_data: dict, version: str) -> tuple[str, str, str]:
    """Extract wheel URL, SHA256, and filename from PyPI JSON data.

    Raises ValueError if version or wheel not found.
    """
    releases = pypi_data.get("releases", {})
    if version not in releases:
        msg = f"Version {version} not found in PyPI releases"
        raise ValueError(msg)

    for entry in releases[version]:
        if entry.get("packagetype") == "bdist_wheel":
            return entry["url"], entry["digests"]["sha256"], entry["filename"]

    msg = f"No wheel found for version {version}"
    raise ValueError(msg)


async def _download_file(url: str) -> bytes:
    """Download a file from URL and return its content."""
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT_SECONDS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


@contextlib.contextmanager
def _try_acquire_lock():
    """Try to acquire the update lock file. Yields True if acquired, False if busy."""
    lock_path = get_global_oak_dir() / LOCK_FILE
    try:
        lock_fd = lock_path.open("w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except BlockingIOError:
            yield False
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            lock_fd.close()
    except OSError:
        yield False


def clean_staging() -> None:
    """Remove all files from the staging directory."""
    staging = get_global_oak_dir() / STAGING_DIR
    if staging.exists():
        for f in staging.iterdir():
            f.unlink(missing_ok=True)


async def download_and_stage(version: str, channel: str = "stable") -> bool:
    """Download a wheel from PyPI and stage it for installation.

    Args:
        version: The version string to download.
        channel: The update channel that triggered this download.

    Returns True on success, False on failure.
    """
    with _try_acquire_lock() as acquired:
        if not acquired:
            # Another daemon is downloading — check if it already staged
            existing = read_staged_update()
            if existing and existing.get("version") == version:
                logger.info("Update already staged by another process")
                return True
            logger.info("Update lock held by another process, skipping download")
            return False

        try:
            # Fetch PyPI metadata (fetch_pypi_raw is synchronous)
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, fetch_pypi_raw)
            pypi_data = json.loads(raw)

            # Find the wheel
            url, expected_sha256, filename = _find_wheel_url(pypi_data, version)

            # Clean staging directory
            clean_staging()

            # Download
            logger.info("Downloading %s from PyPI...", filename)
            content = await _download_file(url)

            # Verify checksum
            actual_sha256 = hashlib.sha256(content).hexdigest()
            if actual_sha256 != expected_sha256:
                logger.error(
                    "Checksum mismatch for %s: expected %s, got %s",
                    filename, expected_sha256, actual_sha256,
                )
                return False

            # Write wheel to staging
            staging_dir = get_global_oak_dir() / STAGING_DIR
            wheel_path = staging_dir / filename
            wheel_path.write_bytes(content)

            # Write metadata
            write_staged_update({
                "schema_version": 1,
                "version": version,
                "wheel_path": str(wheel_path),
                "channel": channel,
                "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sha256": actual_sha256,
            })

            logger.info("Successfully staged %s at %s", filename, wheel_path)
            return True

        except Exception as exc:
            logger.error("Failed to download and stage update: %s", exc)
            clean_staging()
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_downloader.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/lifecycle/update_downloader.py tests/unit/features/team/daemon/test_update_downloader.py
git commit -m "feat(self-update): add wheel downloader with checksum verification and file locking"
```

---

## Chunk 3: Update Installer + API Routes

### Task 6: Update Installer — Script Generation + Spawn

**Files:**
- Create: `src/open_agent_kit/features/team/daemon/lifecycle/update_installer.py`
- Test: `tests/unit/features/team/daemon/test_update_installer.py`

Generates a shell script and spawns it as a detached process. The script installs the wheel, runs project upgrade, and restarts the daemon.

- [ ] **Step 1: Write tests for update installer**

```python
# tests/unit/features/team/daemon/test_update_installer.py
"""Tests for update script generation and spawning."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_installer import (
    generate_update_script,
    apply_staged_update,
)
from open_agent_kit.utils.install_method import InstallMethod


class TestGenerateUpdateScript:
    """Test shell script generation."""

    def test_script_starts_with_shebang(self) -> None:
        script = generate_update_script(
            project_root=Path("/home/user/project"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert script.startswith("#!/bin/sh")

    def test_script_contains_cd_to_project(self) -> None:
        script = generate_update_script(
            project_root=Path("/home/user/project"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert 'cd "/home/user/project"' in script

    def test_script_contains_pip_install_for_pip_user(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "--user" in script
        assert "/tmp/oak_ci-1.3.0.whl" in script

    def test_script_contains_uv_for_uv_tool(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.UV_TOOL,
            daemon_type="team",
        )
        assert "uv tool install" in script
        assert "--force" in script

    def test_script_uses_homebrew_pip(self) -> None:
        with patch("open_agent_kit.features.team.daemon.lifecycle.update_installer.sys") as mock_sys:
            mock_sys.executable = "/opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            script = generate_update_script(
                project_root=Path("/tmp/proj"),
                wheel_path="/tmp/oak_ci-1.3.0.whl",
                install_method=InstallMethod.HOMEBREW,
                daemon_type="team",
            )
        assert "libexec/bin/pip" in script

    def test_script_runs_oak_upgrade(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "oak upgrade --force" in script

    def test_team_daemon_restarts_with_team_start(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "oak team start" in script

    def test_swarm_daemon_restarts_with_swarm_start(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="swarm",
        )
        assert "oak swarm start" in script

    def test_script_writes_error_on_failure(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "update-error.json" in script

    def test_script_attempts_restart_on_failure(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        # The error handler should still try to restart
        assert script.count("oak team start") >= 2  # normal + fallback

    def test_raises_for_editable(self) -> None:
        with pytest.raises(ValueError, match="editable"):
            generate_update_script(
                project_root=Path("/tmp/proj"),
                wheel_path="/tmp/w.whl",
                install_method=InstallMethod.EDITABLE,
                daemon_type="team",
            )


class TestApplyStagedUpdate:
    """Test the full apply flow: generate script, spawn, exit."""

    def test_spawns_detached_subprocess(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        # Create staged update
        from open_agent_kit.utils.global_config import ensure_global_dir, write_staged_update
        ensure_global_dir()
        wheel = tmp_path / "staging" / "oak_ci-1.3.0.whl"
        wheel.write_bytes(b"fake")
        write_staged_update({
            "schema_version": 1,
            "version": "1.3.0",
            "wheel_path": str(wheel),
            "channel": "stable",
            "downloaded_at": "2026-03-10T00:00:00Z",
            "sha256": "abc",
        })

        with (
            patch("open_agent_kit.features.team.daemon.lifecycle.update_installer.detect_install_method", return_value=InstallMethod.PIP_USER),
            patch("open_agent_kit.features.team.daemon.lifecycle.update_installer.subprocess.Popen") as mock_popen,
        ):
            result = apply_staged_update(
                project_root=tmp_path,
                daemon_type="team",
            )

        assert result is True
        mock_popen.assert_called_once()
        # Verify it's using /bin/sh
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "/bin/sh"

    def test_returns_false_when_no_staged_update(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        result = apply_staged_update(project_root=tmp_path, daemon_type="team")
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_installer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update installer**

```python
# src/open_agent_kit/features/team/daemon/lifecycle/update_installer.py
"""Generate and spawn update scripts for the self-update system.

The daemon cannot replace itself while running. Instead, it generates a
shell script that installs the new wheel, runs project upgrade, and restarts
the daemon. The script is spawned as a detached subprocess so it survives
the daemon's exit.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from open_agent_kit.utils.global_config import (
    get_global_oak_dir,
    read_staged_update,
    UPDATE_ERROR_FILE,
    STAGED_UPDATE_FILE,
    STAGING_DIR,
)
from open_agent_kit.utils.install_method import (
    InstallMethod,
    detect_install_method,
    get_install_command,
)

logger = logging.getLogger(__name__)


def generate_update_script(
    project_root: Path,
    wheel_path: str,
    install_method: InstallMethod,
    daemon_type: str,
) -> str:
    """Generate a shell script that installs the wheel and restarts the daemon.

    Args:
        project_root: Absolute path to the project directory.
        wheel_path: Absolute path to the staged .whl file.
        install_method: How OAK was installed (determines install command).
        daemon_type: "team" or "swarm".

    Returns:
        Shell script content as a string.

    Raises:
        ValueError: If install_method is EDITABLE.
    """
    if install_method == InstallMethod.EDITABLE:
        msg = "Cannot generate update script for editable installs"
        raise ValueError(msg)

    # Build the install command
    install_cmd_parts = get_install_command(install_method, wheel_path)
    install_cmd = " ".join(f'"{p}"' if " " in p else p for p in install_cmd_parts)

    restart_cmd = f"oak {daemon_type} start"
    global_dir = get_global_oak_dir()
    error_file = global_dir / UPDATE_ERROR_FILE
    staged_file = global_dir / STAGED_UPDATE_FILE
    staging_dir = global_dir / STAGING_DIR

    return f"""#!/bin/sh
# OAK self-update script — generated by daemon
# Installs staged wheel, upgrades project, restarts daemon.
set -e

# Wait for daemon to exit cleanly
sleep 2

cd "{project_root}"

# Install the new package
if ! {install_cmd}; then
    echo '{{"error": "Package install failed"}}' > "{error_file}"
    # Fallback: try to restart old version
    {restart_cmd} --quiet || true
    exit 1
fi

# Run project-level upgrade
if ! oak upgrade --force; then
    echo '{{"error": "Project upgrade failed (package was installed successfully)"}}' > "{error_file}"
    # Package installed but project upgrade failed — still restart with new version
    {restart_cmd} --quiet || true
    exit 1
fi

# Restart daemon with new version
{restart_cmd} --quiet || {{
    echo '{{"error": "Daemon restart failed after successful update"}}' > "{error_file}"
    exit 1
}}

# Cleanup on success
rm -f "{staged_file}"
rm -rf "{staging_dir}"/*
rm -f "{error_file}"
"""


def apply_staged_update(
    project_root: Path,
    daemon_type: str,
) -> bool:
    """Apply a staged update by generating and spawning the update script.

    Returns True if the script was spawned successfully, False otherwise.
    """
    staged = read_staged_update()
    if not staged:
        logger.warning("No staged update found")
        return False

    wheel_path = staged.get("wheel_path")
    if not wheel_path or not Path(wheel_path).exists():
        logger.error("Staged wheel not found at %s", wheel_path)
        return False

    method = detect_install_method()

    script = generate_update_script(
        project_root=project_root,
        wheel_path=wheel_path,
        install_method=method,
        daemon_type=daemon_type,
    )

    # Write script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sh",
        prefix="oak-update-",
        delete=False,
    ) as f:
        f.write(script)
        script_path = f.name

    Path(script_path).chmod(0o755)

    # Spawn detached subprocess
    try:
        subprocess.Popen(
            ["/bin/sh", script_path],
            cwd=str(project_root),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        logger.info("Update script spawned: %s", script_path)
        return True
    except OSError as exc:
        logger.error("Failed to spawn update script: %s", exc)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/features/team/daemon/test_update_installer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/lifecycle/update_installer.py tests/unit/features/team/daemon/test_update_installer.py
git commit -m "feat(self-update): add update script generation and detached spawn"
```

---

### Task 7: Update API Routes

**Files:**
- Create: `src/open_agent_kit/features/team/daemon/routes/update.py`
- Test: `tests/unit/features/team/daemon/test_routes_update.py`
- Modify: `src/open_agent_kit/features/team/daemon/server.py:195-200` (mount update routes)
- Modify: `src/open_agent_kit/features/swarm/daemon/server.py:145` (mount update routes)

- [ ] **Step 1: Write tests for update API routes**

```python
# tests/unit/features/team/daemon/test_routes_update.py
"""Tests for /api/update/* endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from open_agent_kit.features.team.daemon.server import create_app
from open_agent_kit.features.team.daemon.state import get_state, reset_state


@pytest.fixture(autouse=True)
def _reset_state():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(auth_headers):
    app = create_app()
    return TestClient(app, headers=auth_headers)


@pytest.fixture
def setup_state(tmp_path: Path):
    state = get_state()
    state.initialize(tmp_path)
    return state


class TestUpdateStatus:
    """Test GET /api/update/status."""

    def test_returns_exempt_for_editable(self, client, setup_state) -> None:
        with patch(
            "open_agent_kit.features.team.daemon.routes.update.check_update_exempt",
            return_value=MagicMock(reason="editable_install", message="dev install"),
        ):
            resp = client.get("/api/update/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["exempt"] is True
        assert data["reason"] == "editable_install"

    def test_returns_update_status(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        with patch(
            "open_agent_kit.features.team.daemon.routes.update.check_update_exempt",
            return_value=None,
        ):
            resp = client.get("/api/update/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["exempt"] is False
        assert "channel" in data
        assert "staged_update" in data


class TestUpdateCheck:
    """Test POST /api/update/check."""

    def test_triggers_check(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        with (
            patch(
                "open_agent_kit.features.team.daemon.routes.update.check_update_exempt",
                return_value=None,
            ),
            patch(
                "open_agent_kit.features.team.daemon.routes.update.check_for_update",
                new_callable=AsyncMock,
                return_value=MagicMock(
                    update_available=True,
                    latest_version="1.3.0",
                    error=None,
                ),
            ),
        ):
            resp = client.post("/api/update/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["latest_version"] == "1.3.0"


class TestUpdateApply:
    """Test POST /api/update/apply."""

    def test_returns_error_when_no_staged_update(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        with patch(
            "open_agent_kit.features.team.daemon.routes.update.check_update_exempt",
            return_value=None,
        ):
            resp = client.post("/api/update/apply")
        assert resp.status_code == 400

    def test_spawns_update_and_schedules_shutdown(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir, write_staged_update
        ensure_global_dir()
        wheel = tmp_path / "staging" / "oak_ci-1.3.0.whl"
        wheel.write_bytes(b"fake")
        write_staged_update({
            "schema_version": 1,
            "version": "1.3.0",
            "wheel_path": str(wheel),
            "channel": "stable",
            "downloaded_at": "2026-03-10T00:00:00Z",
            "sha256": "abc",
        })

        with (
            patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None),
            patch("open_agent_kit.features.team.daemon.routes.update.apply_staged_update", return_value=True),
            patch("open_agent_kit.features.team.daemon.routes.update.delayed_shutdown") as mock_shutdown,
        ):
            resp = client.post("/api/update/apply")

        assert resp.status_code == 200
        assert resp.json()["status"] == "applying"
        mock_shutdown.assert_called_once()


class TestUpdateChannel:
    """Test PUT /api/update/channel."""

    def test_switches_channel(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir
        ensure_global_dir()

        with patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None):
            resp = client.put("/api/update/channel", json={"channel": "beta"})
        assert resp.status_code == 200

        from open_agent_kit.utils.global_config import load_update_config
        config = load_update_config()
        assert config.channel == "beta"

    def test_rejects_invalid_channel(self, client, setup_state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        with patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None):
            resp = client.put("/api/update/channel", json={"channel": "nightly"})
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/features/team/daemon/test_routes_update.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update API routes**

```python
# src/open_agent_kit/features/team/daemon/routes/update.py
"""Self-update API routes.

Mounted on both team and swarm daemon routers. Provides endpoints for
checking update status, triggering checks, applying updates, switching
channels, and fetching release notes.
"""
from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.constants import VERSION
from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
    UpdateCheckResult,
    check_for_update,
)
from open_agent_kit.features.team.daemon.lifecycle.update_installer import (
    apply_staged_update,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.global_config import (
    ensure_global_dir,
    load_update_config,
    read_staged_update,
    read_update_error,
    save_update_config,
    read_last_check,
)
from open_agent_kit.utils.update_exempt import check_update_exempt

logger = logging.getLogger(__name__)

VALID_CHANNELS = ("stable", "beta")
GITHUB_RELEASES_URL = "https://api.github.com/repos/goondocks-co/open-agent-kit/releases/tags/v{version}"
RELEASE_NOTES_TIMEOUT_SECONDS = 10

_DAEMON_TYPE = "team"  # Overridden by create_update_router() for swarm


def create_update_router(daemon_type: str = "team") -> APIRouter:
    """Create the update router, parameterised by daemon type."""
    global _DAEMON_TYPE
    _DAEMON_TYPE = daemon_type
    return router


router = APIRouter(prefix="/api/update", tags=["update"])


class ChannelRequest(BaseModel):
    """Request body for channel switch."""

    channel: str


@router.get("/status")
async def update_status() -> dict:
    """Return current self-update state."""
    exemption = check_update_exempt()
    if exemption:
        return {"exempt": True, "reason": exemption.reason, "message": exemption.message}

    config = load_update_config()
    staged = read_staged_update()
    last_check = read_last_check()
    error = read_update_error()

    return {
        "exempt": False,
        "running_version": VERSION,
        "channel": config.channel,
        "auto_download": config.auto_download,
        "check_interval_hours": config.check_interval_hours,
        "staged_update": staged,
        "last_check": last_check,
        "error": error,
    }


@router.post("/check")
async def update_check() -> dict:
    """Trigger an on-demand PyPI version check."""
    exemption = check_update_exempt()
    if exemption:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=exemption.message,
        )

    config = load_update_config()
    result = await check_for_update(running_version=VERSION, config=config)

    return {
        "update_available": result.update_available,
        "latest_version": result.latest_version,
        "channel": result.channel,
        "error": result.error,
    }


@router.post("/apply")
async def update_apply() -> dict:
    """Apply a staged update: spawn update script and shut down."""
    exemption = check_update_exempt()
    if exemption:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=exemption.message,
        )

    staged = read_staged_update()
    if not staged:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="No staged update available. Run a check first.",
        )

    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No project root configured.",
        )

    success = apply_staged_update(
        project_root=state.project_root,
        daemon_type=_DAEMON_TYPE,
    )

    if not success:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to spawn update script.",
        )

    # Schedule daemon shutdown after response is sent
    asyncio.create_task(delayed_shutdown(2, log_message="Shutting down for self-update."))

    return {"status": "applying", "version": staged.get("version")}


@router.put("/channel")
async def update_channel(request: ChannelRequest) -> dict:
    """Switch the update channel (stable/beta)."""
    exemption = check_update_exempt()
    if exemption:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=exemption.message,
        )

    if request.channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid channel '{request.channel}'. Must be one of: {', '.join(VALID_CHANNELS)}",
        )

    ensure_global_dir()
    config = load_update_config()
    config.channel = request.channel
    save_update_config(config)

    return {"channel": config.channel, "message": f"Switched to {config.channel} channel."}


@router.get("/release-notes")
async def update_release_notes(version: str) -> dict:
    """Fetch release notes from GitHub Releases API."""
    url = GITHUB_RELEASES_URL.format(version=version)
    try:
        async with httpx.AsyncClient(timeout=RELEASE_NOTES_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return {
                "version": version,
                "name": data.get("name", ""),
                "body": data.get("body", ""),
                "published_at": data.get("published_at", ""),
                "html_url": data.get("html_url", ""),
            }
    except Exception as exc:
        logger.warning("Failed to fetch release notes for v%s: %s", version, exc)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=f"Could not fetch release notes: {exc}",
        ) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/features/team/daemon/test_routes_update.py -v`
Expected: ALL PASS

- [ ] **Step 5: Mount routes on team daemon server**

Modify `src/open_agent_kit/features/team/daemon/server.py` — add import and mount the update router alongside the existing release_channel routes (around line 195-200):

```python
# After the existing release channel routes import, add:
from open_agent_kit.features.team.daemon.routes.update import router as update_router
# In the route mounting section:
app.include_router(update_router)
```

- [ ] **Step 6: Mount routes on swarm daemon server**

Modify `src/open_agent_kit/features/swarm/daemon/server.py` — mount with `daemon_type="swarm"` (around line 145):

```python
from open_agent_kit.features.team.daemon.routes.update import create_update_router
app.include_router(create_update_router(daemon_type="swarm"))
```

- [ ] **Step 7: Run all tests to verify nothing broken**

Run: `uv run pytest tests/unit/features/team/daemon/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/routes/update.py tests/unit/features/team/daemon/test_routes_update.py src/open_agent_kit/features/team/daemon/server.py src/open_agent_kit/features/swarm/daemon/server.py
git commit -m "feat(self-update): add update API routes and mount on both daemons"
```

---

### Task 8: Integrate Periodic Update Check into Daemon Lifecycle

**Files:**
- Modify: `src/open_agent_kit/features/team/daemon/lifecycle/version_check.py:113-140` (add update checking to periodic loop)
- Modify: `src/open_agent_kit/features/team/daemon/state.py:147` (add self-update state fields to DaemonState)

- [ ] **Step 1: Add update state fields to DaemonState**

Modify `src/open_agent_kit/features/team/daemon/state.py` — add new fields to the `DaemonState` class (defined at line 147):

```python
# Add these fields to the DaemonState dataclass:
    # Self-update state
    self_update_exempt: bool = False
    self_update_exempt_reason: str | None = None
    self_update_available: bool = False
    self_update_version: str | None = None
    self_update_staged: bool = False
    self_update_error: str | None = None
```

- [ ] **Step 2: Add periodic self-update check to version_check.py**

Modify `src/open_agent_kit/features/team/daemon/lifecycle/version_check.py` to add a `periodic_self_update_check` function that runs alongside the existing `periodic_version_check`:

```python
async def periodic_self_update_check(state: "DaemonState") -> None:
    """Periodically check PyPI for new OAK versions and auto-download.

    Runs as a non-blocking async task. Respects exemptions, channel config,
    and check interval. Downloads wheel if auto_download is enabled.
    """
    from open_agent_kit.utils.update_exempt import check_update_exempt
    from open_agent_kit.utils.global_config import (
        ensure_global_dir,
        load_update_config,
        read_staged_update,
        read_update_error,
    )
    from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
        check_for_update,
        should_check_now,
    )
    from open_agent_kit.features.team.daemon.lifecycle.update_downloader import (
        download_and_stage,
    )

    # Check exemptions once at startup
    exemption = check_update_exempt()
    if exemption:
        state.self_update_exempt = True
        state.self_update_exempt_reason = exemption.reason
        logger.info("Self-update disabled: %s", exemption.message)
        return

    if not ensure_global_dir():
        state.self_update_exempt = True
        state.self_update_exempt_reason = "global_dir_unavailable"
        logger.warning("Self-update disabled: cannot create ~/.oak/")
        return

    while True:
        try:
            config = load_update_config()
            if should_check_now(config.check_interval_hours):
                result = await check_for_update(
                    running_version=VERSION,
                    config=config,
                )
                state.self_update_available = result.update_available
                state.self_update_version = result.latest_version

                if result.update_available and config.auto_download and result.latest_version:
                    # Check if already staged
                    staged = read_staged_update()
                    if not staged or staged.get("version") != result.latest_version:
                        await download_and_stage(result.latest_version, channel=config.channel)

                # Update staged status
                staged = read_staged_update()
                state.self_update_staged = staged is not None

            # Check for errors from previous update attempts
            error = read_update_error()
            state.self_update_error = error

        except Exception as exc:
            logger.warning("Self-update check failed: %s", exc)

        await asyncio.sleep(config.check_interval_hours * 3600)
```

- [ ] **Step 3: Start the periodic check in daemon lifespan**

Modify the daemon lifespan/startup to launch `periodic_self_update_check` as an async task (similar to how `periodic_version_check` is started).

- [ ] **Step 4: Run all daemon tests**

Run: `uv run pytest tests/unit/features/team/daemon/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/state.py src/open_agent_kit/features/team/daemon/lifecycle/version_check.py
git commit -m "feat(self-update): integrate periodic update check into daemon lifecycle"
```

---

## Chunk 4: UI Changes

### Task 9: Team Daemon UI — Update Status Hook

**Files:**
- Create: `src/open_agent_kit/features/team/daemon/ui/src/hooks/use-update-status.ts`
- Modify: `src/open_agent_kit/features/team/daemon/ui/src/lib/constants/api-endpoints.ts` (add update endpoints)

- [ ] **Step 1: Add API endpoints**

Add to `api-endpoints.ts`:

```typescript
// Self-update endpoints
UPDATE_STATUS: "/api/update/status",
UPDATE_CHECK: "/api/update/check",
UPDATE_APPLY: "/api/update/apply",
UPDATE_CHANNEL: "/api/update/channel",
UPDATE_RELEASE_NOTES: "/api/update/release-notes",
```

- [ ] **Step 2: Create update status hook**

```typescript
// src/open_agent_kit/features/team/daemon/ui/src/hooks/use-update-status.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, putJson } from "../lib/api";
import { API_ENDPOINTS } from "../lib/constants";

export interface UpdateStatus {
  exempt: boolean;
  reason?: string;
  message?: string;
  running_version?: string;
  channel?: string;
  auto_download?: boolean;
  staged_update?: {
    version: string;
    wheel_path: string;
    downloaded_at: string;
  } | null;
  last_check?: {
    timestamp: number;
    version: string;
    update_available: boolean;
  } | null;
  error?: string | null;
}

export interface CheckResult {
  update_available: boolean;
  latest_version: string | null;
  channel: string;
  error: string | null;
}

export function useUpdateStatus() {
  return useQuery<UpdateStatus>({
    queryKey: ["update-status"],
    queryFn: () => fetchJson(API_ENDPOINTS.UPDATE_STATUS) as Promise<UpdateStatus>,
    refetchInterval: 30_000,
  });
}

export function useUpdateCheck() {
  const queryClient = useQueryClient();
  return useMutation<CheckResult>({
    mutationFn: () => postJson(API_ENDPOINTS.UPDATE_CHECK) as Promise<CheckResult>,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["update-status"] }),
  });
}

export function useUpdateApply() {
  return useMutation({
    mutationFn: () => postJson(API_ENDPOINTS.UPDATE_APPLY),
  });
}

export function useUpdateChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (channel: string) => putJson(API_ENDPOINTS.UPDATE_CHANNEL, { channel }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["update-status"] }),
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/ui/src/hooks/use-update-status.ts src/open_agent_kit/features/team/daemon/ui/src/lib/constants/api-endpoints.ts
git commit -m "feat(self-update): add update status hooks and API endpoints to UI"
```

---

### Task 10: About Panel Redesign

**Files:**
- Modify: `src/open_agent_kit/ui/shared/components/ui/about-dialog.tsx` (replace ChannelSection with update-aware panel)
- Modify: `src/open_agent_kit/features/team/daemon/ui/src/components/about/AboutDialog.tsx` (pass update status)
- Modify: `src/open_agent_kit/features/team/daemon/ui/src/layouts/Layout.tsx:166-253` (add badge to About icon)

- [ ] **Step 1: Add badge to About icon in Layout sidebar**

Modify `Layout.tsx` sidebar footer. The About button (Info icon) needs a green dot badge when an update is staged. Add the `useUpdateStatus` hook and conditionally render a badge:

```tsx
// In Layout.tsx, import the hook:
import { useUpdateStatus } from "../hooks/use-update-status";

// In the component body:
const { data: updateStatus } = useUpdateStatus();
const hasUpdate = updateStatus && !updateStatus.exempt && updateStatus.staged_update;

// On the About button (Info icon), wrap with relative positioning and add badge:
<button onClick={() => setAboutOpen(true)} className="relative ...">
  <Info className="h-4 w-4" />
  {hasUpdate && (
    <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-sidebar" />
  )}
</button>
```

- [ ] **Step 2: Add update section to AboutDialog**

Modify the shared `about-dialog.tsx` to accept update status and render the three states (up-to-date, update ready, applying). Add new props to `AboutDialogConfig`:

```typescript
// New prop on AboutDialogConfig:
updateStatus?: UpdateStatus;
onCheckUpdate?: () => void;
onApplyUpdate?: () => void;
onSwitchChannel?: (channel: string) => void;
```

Add an `UpdateSection` component inside `about-dialog.tsx` that renders:
- Current version + channel
- "Up to date" / "Update ready" / error states
- "Apply Update" button / "Check Now" button
- Channel toggle (Stable / Beta)
- "Last checked X ago" timestamp
- Release notes link

- [ ] **Step 3: Remove old UpdateBanner from Layout**

Remove the `UpdateBanner` rendering from `Layout.tsx` main content area (around lines 260-266). The update indicator now lives on the About icon badge, and the apply action lives in the About panel.

- [ ] **Step 4: Build and verify team UI**

Run: `cd src/open_agent_kit/features/team/daemon/ui && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/ui/shared/components/ui/about-dialog.tsx src/open_agent_kit/features/team/daemon/ui/src/components/about/AboutDialog.tsx src/open_agent_kit/features/team/daemon/ui/src/layouts/Layout.tsx
git commit -m "feat(self-update): redesign About panel with update status and channel toggle"
```

---

### Task 11: Swarm Daemon UI — Mirror Update Integration

**Files:**
- Modify: `src/open_agent_kit/features/swarm/daemon/ui/src/layouts/Layout.tsx` (add badge + update hooks)
- Create: `src/open_agent_kit/features/swarm/daemon/ui/src/hooks/use-update-status.ts` (same hook, different api client)
- Modify: `src/open_agent_kit/features/swarm/daemon/ui/src/lib/constants/api-endpoints.ts` (add update endpoints)

- [ ] **Step 1: Add update endpoints to swarm constants**

Same endpoints as team — `/api/update/status`, `/api/update/check`, `/api/update/apply`, `/api/update/channel`.

- [ ] **Step 2: Create swarm update status hook**

Mirror the team's `use-update-status.ts` using the swarm's API client.

- [ ] **Step 3: Add badge and update section to swarm Layout**

Same pattern as team Layout — green dot on About icon, update section in About panel.

- [ ] **Step 4: Build and verify swarm UI**

Run: `cd src/open_agent_kit/features/swarm/daemon/ui && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/open_agent_kit/features/swarm/daemon/ui/
git commit -m "feat(self-update): add update status to swarm daemon UI"
```

---

## Chunk 5: Channel Migration + Cleanup

### Task 12: Remove Old Beta Channel Infrastructure

**Files:**
- Modify: `src/open_agent_kit/features/team/daemon/routes/release_channel.py` (simplify or remove switch_channel)
- Modify: `src/open_agent_kit/features/swarm/daemon/routes/release_channel.py` (same)
- Modify: `src/open_agent_kit/utils/release_channel.py` (remove target_binary_name, get_current_channel)
- Modify: `src/open_agent_kit/features/team/daemon/server.py` (update route mounting)
- Modify: `src/open_agent_kit/features/swarm/daemon/server.py` (update route mounting)

- [ ] **Step 1: Simplify release_channel.py utility**

Remove `get_current_channel()` (line 117), `target_binary_name()` (line 129), and `SwitchChannelRequest` (line 139). Keep `fetch_pypi_raw()`, `parse_pypi_versions()`, `fetch_pypi_versions()`, and `build_channel_info()` — these are still used by the update checker.

Update `build_channel_info()` to read channel from `~/.oak/update.yaml` instead of detecting from binary name.

- [ ] **Step 2: Replace release_channel routes**

The old `/api/channel` and `/api/channel/switch` routes are replaced by `/api/update/channel` (PUT). Either remove the old routes entirely or make them thin wrappers that redirect to the new endpoint for backwards compatibility.

- [ ] **Step 3: Update imports and tests**

Find all usages of `get_current_channel`, `target_binary_name`, and `SwitchChannelRequest` and update or remove them.

Run: `uv run pytest tests/ -v -k "channel or release"` to find affected tests.

- [ ] **Step 4: Run full test suite**

Run: `make check`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(channels): replace binary-swap channel switching with config-based toggle"
```

---

### Task 13: Remove Old Update Banner

**Files:**
- Remove: `src/open_agent_kit/features/team/daemon/ui/src/components/ui/update-banner.tsx`
- Modify: `src/open_agent_kit/features/team/daemon/ui/src/lib/constants/ui.ts` (remove UPDATE_BANNER constants)
- Modify: `src/open_agent_kit/cli.py:217-257` (remove `_check_daemon_version_hint` or simplify)

- [ ] **Step 1: Remove UpdateBanner component**

Delete the file and remove all imports of it.

- [ ] **Step 2: Clean up UI constants**

Remove `UPDATE_BANNER` object from `ui.ts` (lines 139-157).

- [ ] **Step 3: Simplify CLI version hint**

The `_check_daemon_version_hint()` function in `cli.py` (line 217) currently prints a yellow banner in the terminal. Since the daemon now handles update notifications in the UI, simplify this to just log at debug level or remove entirely.

- [ ] **Step 4: Build both UIs and run tests**

Run:
```bash
cd src/open_agent_kit/features/team/daemon/ui && npm run build
cd src/open_agent_kit/features/swarm/daemon/ui && npm run build
make check
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "cleanup: remove old update banner and CLI version hint"
```

---

### Task 14: Integration Test — Full Self-Update Flow

**Files:**
- Create: `tests/integration/test_self_update_flow.py`

End-to-end test of the self-update flow using mocked PyPI responses and subprocess.

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_self_update_flow.py
"""Integration test for the full self-update flow.

Tests: detect → download → stage → apply sequence with mocked PyPI
and subprocess. Verifies all components work together.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from starlette.testclient import TestClient

from open_agent_kit.features.team.daemon.server import create_app
from open_agent_kit.features.team.daemon.state import get_state, reset_state
from open_agent_kit.utils.global_config import ensure_global_dir, read_staged_update


_WHEEL_CONTENT = b"PK\x03\x04integration-test-wheel"
_WHEEL_SHA = hashlib.sha256(_WHEEL_CONTENT).hexdigest()

_PYPI_RESPONSE = json.dumps({
    "releases": {
        "1.0.0": [],
        "2.0.0": [{
            "filename": "oak_ci-2.0.0-py3-none-any.whl",
            "url": "https://example.com/oak_ci-2.0.0.whl",
            "digests": {"sha256": _WHEEL_SHA},
            "packagetype": "bdist_wheel",
        }],
    }
}).encode()


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(auth_headers):
    app = create_app()
    return TestClient(app, headers=auth_headers)


class TestSelfUpdateFlow:
    """Test the complete check → download → apply sequence."""

    def test_check_detects_update(self, client, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        state = get_state()
        state.initialize(tmp_path)

        with (
            patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None),
            patch("open_agent_kit.features.team.daemon.routes.update.VERSION", "1.0.0"),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
                return_value=_PYPI_RESPONSE,
            ),
        ):
            resp = client.post("/api/update/check")

        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["latest_version"] == "2.0.0"

    def test_status_shows_staged_update(self, client, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        state = get_state()
        state.initialize(tmp_path)

        # Pre-stage an update
        from open_agent_kit.utils.global_config import write_staged_update
        wheel = tmp_path / "staging" / "oak_ci-2.0.0.whl"
        wheel.write_bytes(_WHEEL_CONTENT)
        write_staged_update({
            "schema_version": 1,
            "version": "2.0.0",
            "wheel_path": str(wheel),
            "channel": "stable",
            "downloaded_at": "2026-03-10T00:00:00Z",
            "sha256": _WHEEL_SHA,
        })

        with patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None):
            resp = client.get("/api/update/status")

        data = resp.json()
        assert data["staged_update"]["version"] == "2.0.0"
```

- [ ] **Step 2: Run integration test**

Run: `uv run pytest tests/integration/test_self_update_flow.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_self_update_flow.py
git commit -m "test: add integration test for self-update flow"
```

---

### Task 15: Final Quality Gate

- [ ] **Step 1: Run full quality gate**

Run: `make check`
Expected: ALL PASS (format, typecheck, tests)

- [ ] **Step 2: Verify both UIs build**

Run:
```bash
cd src/open_agent_kit/features/team/daemon/ui && npm run build
cd src/open_agent_kit/features/swarm/daemon/ui && npm run build
```
Expected: Both build without errors

- [ ] **Step 3: Manual smoke test**

Start a daemon and verify:
1. `/api/update/status` returns correct state
2. About panel shows version and channel
3. Green badge appears when update is staged (mock by writing `staged-update.json`)

- [ ] **Step 4: Final commit with any fixups**

```bash
git add -A
git commit -m "chore: fixups from quality gate"
```
