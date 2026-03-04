"""Swarm configuration helpers.

Shared path resolution and config load/save for the swarm feature.
Used by both CLI commands and the daemon manager.
"""

import json
import os
from pathlib import Path
from typing import Any

from open_agent_kit.features.swarm.constants import (
    SWARM_CONFIG_FILE_PERMISSIONS,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_CONFIG_FILE,
)


def get_swarm_config_dir(swarm_id: str) -> Path:
    """Get the configuration directory for a swarm.

    Args:
        swarm_id: Swarm identifier.

    Returns:
        Path to ``~/.oak/swarms/{swarm_id}/``.
    """
    return Path(SWARM_DAEMON_CONFIG_DIR).expanduser() / swarm_id


def load_swarm_config(swarm_id: str) -> dict[str, Any] | None:
    """Load swarm config from disk.

    Returns:
        Config dict, or ``None`` if the file does not exist.
    """
    config_file = get_swarm_config_dir(swarm_id) / SWARM_DAEMON_CONFIG_FILE
    if not config_file.is_file():
        return None
    data: dict[str, Any] = json.loads(config_file.read_text())
    return data


def save_swarm_config(swarm_id: str, config: dict[str, Any]) -> None:
    """Save swarm config to disk."""
    swarm_dir = get_swarm_config_dir(swarm_id)
    swarm_dir.mkdir(parents=True, exist_ok=True)
    config_file = swarm_dir / SWARM_DAEMON_CONFIG_FILE
    config_file.write_text(json.dumps(config, indent=2))
    os.chmod(config_file, SWARM_CONFIG_FILE_PERMISSIONS)
