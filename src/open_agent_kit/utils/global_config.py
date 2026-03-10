"""Global OAK configuration at ~/.oak/ for machine-wide update state.

Distinct from the per-project .oak/ directory. Holds update channel config,
staged wheels, lock files, and last-check timestamps.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
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
                check_interval_hours=update.get(
                    "check_interval_hours", DEFAULT_CHECK_INTERVAL_HOURS
                ),
            )
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to load update config: %s", exc)
    return UpdateConfig()


def save_update_config(config: UpdateConfig) -> None:
    """Save update config to ~/.oak/update.yaml, creating the dir if needed."""
    ensure_global_dir()
    config_path = get_global_oak_dir() / UPDATE_CONFIG_FILE
    data = {
        "update": {
            "channel": config.channel,
            "auto_download": config.auto_download,
            "check_interval_hours": config.check_interval_hours,
        }
    }
    config_path.write_text(yaml.dump(data, default_flow_style=False))


def _read_json(filename: str) -> dict | None:  # type: ignore[type-arg]
    """Read a JSON file from the global dir, returning None if missing."""
    path = get_global_oak_dir() / filename
    try:
        if path.exists():
            return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return None


def _write_json(filename: str, data: dict) -> None:  # type: ignore[type-arg]
    """Write a JSON file to the global dir, creating it if needed."""
    ensure_global_dir()
    path = get_global_oak_dir() / filename
    path.write_text(json.dumps(data, indent=2))


def read_staged_update() -> dict | None:  # type: ignore[type-arg]
    """Read staged-update.json metadata."""
    return _read_json(STAGED_UPDATE_FILE)


def write_staged_update(data: dict) -> None:  # type: ignore[type-arg]
    """Write staged-update.json metadata."""
    _write_json(STAGED_UPDATE_FILE, data)


def read_last_check() -> dict | None:  # type: ignore[type-arg]
    """Read last-check.json timestamp and result."""
    return _read_json(LAST_CHECK_FILE)


def write_last_check(data: dict) -> None:  # type: ignore[type-arg]
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
