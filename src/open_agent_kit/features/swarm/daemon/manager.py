"""Swarm daemon lifecycle management.

Simplified daemon manager for the swarm daemon. Inherits common lifecycle
operations from ``BaseDaemonManager`` and adds swarm-specific behaviour
(config loading, swarm status endpoint).
"""

import logging
import os
import subprocess
import sys
from typing import Any

from open_agent_kit.features.swarm.config import get_swarm_config_dir, load_swarm_config
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_SWARM_KEY_PORT,
    CI_CONFIG_SWARM_KEY_TOKEN,
    CI_CONFIG_SWARM_KEY_URL,
    SWARM_AUTH_ENV_VAR,
    SWARM_AUTH_EPHEMERAL_TOKEN_BYTES,
    SWARM_CLI_COMMAND_ENV_VAR,
    SWARM_DAEMON_API_PATH_HEALTH,
    SWARM_DAEMON_CONFIG_FILE,
    SWARM_DAEMON_DEFAULT_PORT,
    SWARM_DAEMON_HEALTH_CHECK_INTERVAL,
    SWARM_DAEMON_LOG_FILE,
    SWARM_DAEMON_PID_FILE,
    SWARM_DAEMON_PORT_FILE,
    SWARM_DAEMON_PORT_RANGE_SIZE,
    SWARM_DAEMON_STARTUP_TIMEOUT,
    SWARM_ENV_VAR_CUSTOM_DOMAIN,
    SWARM_ENV_VAR_ID,
    SWARM_ENV_VAR_TOKEN,
    SWARM_ENV_VAR_URL,
    SWARM_MESSAGE_ALREADY_RUNNING,
)
from open_agent_kit.utils.daemon_manager import BaseDaemonManager, DaemonConfig
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)


class SwarmDaemonManager(BaseDaemonManager):
    """Manage the swarm daemon lifecycle.

    Handles starting, stopping, and monitoring the swarm daemon process.
    Uses a PID file for process tracking.
    """

    def __init__(self, swarm_id: str, port: int | None = None) -> None:
        """Initialize swarm daemon manager.

        Args:
            swarm_id: Swarm identifier.
            port: Port to run the daemon on (default from constants).
        """
        self.swarm_id = swarm_id
        self._auth_token: str | None = None
        config_dir = get_swarm_config_dir(swarm_id)

        # Read config once — reused by start() to avoid a second disk read
        self._saved_config: dict = load_swarm_config(swarm_id) or {}

        # Read previously assigned port from config, fall back to default
        if port:
            actual_port = port
        else:
            actual_port = self._saved_config.get(
                CI_CONFIG_SWARM_KEY_PORT, SWARM_DAEMON_DEFAULT_PORT
            )
        super().__init__(
            DaemonConfig(
                config_dir=config_dir,
                port=actual_port,
                pid_filename=SWARM_DAEMON_PID_FILE,
                log_filename=SWARM_DAEMON_LOG_FILE,
                health_endpoint=SWARM_DAEMON_API_PATH_HEALTH,
                startup_timeout=SWARM_DAEMON_STARTUP_TIMEOUT,
                health_check_interval=SWARM_DAEMON_HEALTH_CHECK_INTERVAL,
            )
        )
        self.port_file = config_dir / SWARM_DAEMON_PORT_FILE
        self.config_file = config_dir / SWARM_DAEMON_CONFIG_FILE

    def get_status(self) -> dict:
        """Get daemon status.

        Returns:
            Dictionary with status information including swarm-specific fields.
        """
        status: dict[str, Any] = super().get_status()
        status["swarm_id"] = self.swarm_id
        status["config_dir"] = str(self.config_dir)
        status["log_file"] = str(self.log_file)

        if status["running"]:
            try:
                import httpx

                headers: dict[str, str] = {}
                if self._auth_token:
                    headers["Authorization"] = f"Bearer {self._auth_token}"
                with httpx.Client(timeout=2.0) as client:
                    response = client.get(f"{self.base_url}/api/swarm/status", headers=headers)
                    if response.status_code == 200:
                        status.update(response.json())
            except Exception as exc:
                logger.debug("Failed to get swarm status: %s", exc)

        return status

    def start(self, wait: bool = True) -> bool:
        """Start the swarm daemon.

        If the configured port is in use, auto-probes the port range to find
        an available one and persists the choice in config.json.

        Args:
            wait: Wait for the daemon to be ready before returning.

        Returns:
            True if daemon started successfully.

        Raises:
            RuntimeError: If daemon fails to start.
        """
        if self.is_running():
            logger.info(SWARM_MESSAGE_ALREADY_RUNNING.format(port=self.port))
            return True

        # Clean up stale PID file
        if self.pid_file.exists():
            self._remove_pid()

        self._ensure_config_dir()

        # Reuse config loaded in __init__ (avoids second disk read)
        from open_agent_kit.features.swarm.config import save_swarm_config

        config = self._saved_config

        # Auto-assign port if the configured one is taken
        if not self._is_port_available(self.port):
            new_port = self._find_available_port(
                SWARM_DAEMON_DEFAULT_PORT, SWARM_DAEMON_PORT_RANGE_SIZE
            )
            logger.info("Port %d in use, auto-assigned port %d", self.port, new_port)
            self.port = new_port
            # Persist chosen port to config.json
            config[CI_CONFIG_SWARM_KEY_PORT] = new_port
            save_swarm_config(self.swarm_id, config)

        # Write port file
        self.port_file.write_text(str(self.port))

        # Build the command
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "open_agent_kit.features.swarm.daemon.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--log-level",
            "warning",
            "--no-access-log",
        ]

        # Environment
        env = os.environ.copy()
        env[SWARM_ENV_VAR_ID] = self.swarm_id

        # Pass the CLI command so the daemon can self-restart using the
        # correct binary (oak / oak-dev / oak-beta).
        from open_agent_kit.features.team.cli_command import detect_invoked_cli_command

        env[SWARM_CLI_COMMAND_ENV_VAR] = detect_invoked_cli_command()

        # Generate auth token for daemon authentication
        import secrets

        auth_token = secrets.token_hex(SWARM_AUTH_EPHEMERAL_TOKEN_BYTES)
        self._auth_token = auth_token
        env[SWARM_AUTH_ENV_VAR] = auth_token

        # Pass swarm config as env vars
        if config.get(CI_CONFIG_SWARM_KEY_URL):
            env[SWARM_ENV_VAR_URL] = config[CI_CONFIG_SWARM_KEY_URL]
        if config.get(CI_CONFIG_SWARM_KEY_TOKEN):
            env[SWARM_ENV_VAR_TOKEN] = config[CI_CONFIG_SWARM_KEY_TOKEN]
        if config.get(CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN):
            env[SWARM_ENV_VAR_CUSTOM_DOMAIN] = config[CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN]

        # Start the process
        try:
            log_handle = open(self.log_file, "a")
            output_handle = log_handle
        except OSError as exc:
            logger.warning("Cannot open log file %s: %s", self.log_file, exc)
            null_device = "/dev/null" if os.name != "nt" else "NUL"
            output_handle = open(null_device, "w")

        with output_handle:
            process = subprocess.Popen(
                cmd,
                stdout=output_handle,
                stderr=output_handle,
                env=env,
                **get_process_detach_kwargs(),
            )

        self._write_pid(process.pid)
        logger.info("Started swarm daemon with PID %d", process.pid)

        if wait:
            return self._wait_for_startup()

        return True
