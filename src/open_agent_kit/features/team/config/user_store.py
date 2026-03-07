"""Raw key/value access to the per-machine user override config.

The user override file (.oak/config.{machine_id}.yaml) stores machine-local
settings that should not be git-tracked.  ``save_ci_config()`` already
preserves non-``team`` top-level keys (io.py:513-522), so sections written
here (e.g. ``swarm:``, ``backup:``) coexist safely with CI config data.

These helpers bypass CIConfig — they are for values that don't belong in
the CI config model (swarm tokens, backup dir overrides, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from open_agent_kit.features.team.config.io import (
    _user_config_path,
    _write_yaml_config,
)

logger = logging.getLogger(__name__)


def read_user_value(project_root: Path, section: str, key: str) -> str | None:
    """Read a single value from the user override config.

    Args:
        project_root: Project root directory.
        section: Top-level YAML section (e.g. ``"swarm"``).
        key: Key within the section (e.g. ``"swarm_token"``).

    Returns:
        The value as a string if present and non-empty, ``None`` otherwise.
    """
    user_file = _user_config_path(project_root)
    if not user_file.exists():
        return None

    try:
        with open(user_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.debug("Failed to read user config %s: %s", user_file, e)
        return None

    section_data = data.get(section)
    if not isinstance(section_data, dict):
        return None

    value = section_data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    return str(value)


def write_user_value(project_root: Path, section: str, key: str, value: str) -> None:
    """Write a single value to the user override config.

    Creates the file and section if they don't exist.  Preserves all other
    sections and keys already in the file.

    Args:
        project_root: Project root directory.
        section: Top-level YAML section.
        key: Key within the section.
        value: Value to write.
    """
    user_file = _user_config_path(project_root)

    existing: dict[str, Any] = {}
    if user_file.exists():
        try:
            with open(user_file, encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to read existing user config %s: %s", user_file, e)

    section_data = existing.get(section)
    if not isinstance(section_data, dict):
        section_data = {}
    section_data[key] = value
    existing[section] = section_data

    _write_yaml_config(user_file, existing)


def remove_user_value(project_root: Path, section: str, key: str) -> bool:
    """Remove a single value from the user override config.

    Removes the section entirely if the last key is removed.

    Args:
        project_root: Project root directory.
        section: Top-level YAML section.
        key: Key within the section.

    Returns:
        ``True`` if the key was found and removed.
    """
    user_file = _user_config_path(project_root)
    if not user_file.exists():
        return False

    try:
        with open(user_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to read user config %s: %s", user_file, e)
        return False

    section_data = data.get(section)
    if not isinstance(section_data, dict) or key not in section_data:
        return False

    del section_data[key]

    # Remove empty section
    if not section_data:
        del data[section]
    else:
        data[section] = section_data

    _write_yaml_config(user_file, data)
    return True
