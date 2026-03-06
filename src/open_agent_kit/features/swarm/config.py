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


def ensure_swarm_config(
    swarm_name: str,
    swarm_token: str,
    swarm_url: str,
    *,
    agent_token: str | None = None,
) -> dict[str, Any]:
    """Ensure a local swarm config exists, creating it if needed.

    This is the canonical way to set up ``~/.oak/swarms/{name}/config.json``
    for an existing swarm.  Both the CLI and the team daemon UI call this.

    Returns the config dict (existing or newly created).
    """
    from open_agent_kit.features.swarm.constants import (
        CI_CONFIG_SWARM_KEY_AGENT_TOKEN,
        CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN,
        CI_CONFIG_SWARM_KEY_SWARM_ID,
        CI_CONFIG_SWARM_KEY_TOKEN,
        CI_CONFIG_SWARM_KEY_URL,
        CI_CONFIG_SWARM_KEY_WORKER_NAME,
    )
    from open_agent_kit.features.swarm.scaffold import make_worker_name

    existing = load_swarm_config(swarm_name)
    if existing is not None:
        return existing

    worker_name = make_worker_name(swarm_name)
    config: dict[str, Any] = {
        CI_CONFIG_SWARM_KEY_SWARM_ID: swarm_name,
        CI_CONFIG_SWARM_KEY_TOKEN: swarm_token,
        CI_CONFIG_SWARM_KEY_URL: swarm_url,
        CI_CONFIG_SWARM_KEY_WORKER_NAME: worker_name,
    }

    if agent_token:
        config[CI_CONFIG_SWARM_KEY_AGENT_TOKEN] = agent_token

    # Derive custom_domain from swarm_url (e.g. *.openagentkit.app → openagentkit.app)
    try:
        from urllib.parse import urlparse

        hostname = urlparse(swarm_url).hostname or ""
        parts = hostname.split(".")
        if len(parts) >= 2:
            config[CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN] = ".".join(parts[-2:])
    except Exception:
        pass

    save_swarm_config(swarm_name, config)
    return config


def save_swarm_config(swarm_id: str, config: dict[str, Any]) -> None:
    """Save swarm config to disk."""
    swarm_dir = get_swarm_config_dir(swarm_id)
    swarm_dir.mkdir(parents=True, exist_ok=True)
    config_file = swarm_dir / SWARM_DAEMON_CONFIG_FILE
    config_file.write_text(json.dumps(config, indent=2))
    os.chmod(config_file, SWARM_CONFIG_FILE_PERMISSIONS)
