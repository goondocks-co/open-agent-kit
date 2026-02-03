"""Notifications installer module.

Installs agent notification handlers based on manifest configuration.
Currently supports command-based notify handlers (Codex).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentManifest, AgentNotificationsConfig

logger = logging.getLogger(__name__)

# Path to notification templates directory (sibling directories: codex/)
NOTIFICATIONS_TEMPLATE_DIR = Path(__file__).parent


@dataclass
class NotificationsInstallResult:
    """Result of a notifications install/remove operation."""

    success: bool
    message: str
    method: str = "notify"


class NotificationsInstaller:
    """Install notification handlers using manifest-driven configuration."""

    def __init__(self, project_root: Path, agent: str):
        self.project_root = project_root
        self.agent = agent
        self._manifest: AgentManifest | None = None
        self._notifications_config: AgentNotificationsConfig | None = None

    @property
    def manifest(self) -> AgentManifest:
        if self._manifest is None:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService(self.project_root)
            self._manifest = agent_service.get_agent_manifest(self.agent)
        return self._manifest

    @property
    def notifications_config(self) -> AgentNotificationsConfig | None:
        if self._notifications_config is None:
            self._notifications_config = self.manifest.notifications
        return self._notifications_config

    @property
    def agent_folder(self) -> Path:
        folder = self.manifest.installation.folder.rstrip("/")
        return self.project_root / folder

    def _get_daemon_port(self) -> int:
        """Get the daemon port from the shared port file or return default."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_SHARED_PORT_DIR,
            CI_SHARED_PORT_FILE,
        )
        from open_agent_kit.features.codebase_intelligence.daemon.manager import DEFAULT_PORT

        shared_port_file = self.project_root / CI_SHARED_PORT_DIR / CI_SHARED_PORT_FILE
        if shared_port_file.exists():
            try:
                port = int(shared_port_file.read_text().strip())
                logger.debug(f"Read daemon port {port} from {shared_port_file}")
                return port
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to read shared port file {shared_port_file}: {e}")

        logger.debug(f"Using default daemon port {DEFAULT_PORT}")
        return DEFAULT_PORT

    def _get_notify_endpoint(self) -> str:
        """Build the notify endpoint URL for this project."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_NOTIFY_ENDPOINT,
            CI_CORS_HOST_LOOPBACK,
        )

        daemon_port = self._get_daemon_port()
        return f"http://{CI_CORS_HOST_LOOPBACK}:{daemon_port}{AGENT_NOTIFY_ENDPOINT}"

    def _render_notify_script(self, template_path: Path) -> str:
        """Render the notify script template with project settings."""
        from jinja2 import Template

        template_content = template_path.read_text()
        template = Template(template_content)
        return template.render(
            notify_endpoint=self._get_notify_endpoint(),
            agent_name=self.agent,
        )

    def _render_notify_config(self, template_path: Path, script_path: Path | None) -> dict:
        """Render notify config template and parse TOML into a dict."""
        from jinja2 import Template

        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_NOTIFY_DEFAULT_ARGS,
            AGENT_NOTIFY_DEFAULT_COMMAND,
        )

        notify_config = self.notifications_config.notify if self.notifications_config else None
        notify_command = (
            notify_config.command if notify_config else None
        ) or AGENT_NOTIFY_DEFAULT_COMMAND
        notify_args = list(notify_config.args or AGENT_NOTIFY_DEFAULT_ARGS) if notify_config else []
        script_value = str(script_path.resolve()) if script_path else None

        template_content = template_path.read_text()
        template = Template(template_content)
        rendered_config = template.render(
            notify_command=notify_command,
            notify_args=notify_args,
            notify_script_path=script_value,
        )

        import tomllib

        return tomllib.loads(rendered_config)

    def _load_config_file(self, config_path: Path) -> dict:
        """Load TOML config file contents or return empty dict."""
        import tomllib

        if not config_path.exists():
            return {}
        return tomllib.loads(config_path.read_text())

    def needs_upgrade(self) -> bool:
        """Check if notify configuration differs from expected state."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_NOTIFY_CONFIG_KEY,
            AGENT_NOTIFY_CONFIG_TYPE,
            AGENT_NOTIFY_DEFAULT_ARGS,
            AGENT_NOTIFY_DEFAULT_COMMAND,
        )

        if not self.notifications_config:
            return False

        if self.notifications_config.type != AGENT_NOTIFY_CONFIG_TYPE:
            return False

        notify_config = self.notifications_config.notify
        if not notify_config or not notify_config.enabled:
            return False

        if not self.notifications_config.config_file:
            return True

        script_path = None
        if notify_config.script_template or notify_config.script_path:
            if not notify_config.script_template or not notify_config.script_path:
                return True

            template_path = NOTIFICATIONS_TEMPLATE_DIR / self.agent / notify_config.script_template
            if not template_path.exists():
                return True

            script_path = self.agent_folder / notify_config.script_path
            if not script_path.exists():
                return True

            expected_script = self._render_notify_script(template_path)
            try:
                installed_script = script_path.read_text()
            except OSError:
                return True

            if installed_script != expected_script:
                return True

        notify_key = notify_config.config_key or AGENT_NOTIFY_CONFIG_KEY
        expected_value = None
        if self.notifications_config and self.notifications_config.config_template:
            config_template_path = (
                NOTIFICATIONS_TEMPLATE_DIR / self.agent / self.notifications_config.config_template
            )
            if not config_template_path.exists():
                return True
            rendered = self._render_notify_config(config_template_path, script_path)
            expected_value = rendered.get(notify_key)
        else:
            notify_command = notify_config.command or AGENT_NOTIFY_DEFAULT_COMMAND
            notify_args = list(notify_config.args or AGENT_NOTIFY_DEFAULT_ARGS)
            expected_value = [notify_command, *notify_args]
            if script_path:
                expected_value.append(str(script_path.resolve()))

        config_path = self.agent_folder / self.notifications_config.config_file
        try:
            config_data = self._load_config_file(config_path)
        except (OSError, ValueError):
            return True

        current_value = config_data.get(notify_key)
        return current_value != expected_value

    def install(self) -> NotificationsInstallResult:
        """Install notification handlers for the agent."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_NOTIFY_CONFIG_KEY,
            AGENT_NOTIFY_CONFIG_TYPE,
        )

        if not self.notifications_config:
            return NotificationsInstallResult(
                success=True,
                message=f"No notifications configuration in manifest for {self.agent}",
            )

        if self.notifications_config.type != AGENT_NOTIFY_CONFIG_TYPE:
            return NotificationsInstallResult(
                success=True,
                message=f"Notifications type {self.notifications_config.type} not supported",
            )

        notify_config = self.notifications_config.notify
        if not notify_config or not notify_config.enabled:
            return NotificationsInstallResult(
                success=True,
                message="Notifications disabled in manifest",
            )

        if not self.notifications_config.config_file:
            return NotificationsInstallResult(
                success=False,
                message="No config_file specified in notifications config",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )

        if not self.notifications_config.config_template:
            return NotificationsInstallResult(
                success=False,
                message="No config_template specified in notifications config",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )

        config_template_path = (
            NOTIFICATIONS_TEMPLATE_DIR / self.agent / self.notifications_config.config_template
        )
        if not config_template_path.exists():
            return NotificationsInstallResult(
                success=False,
                message=f"Notify config template not found: {config_template_path}",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )

        try:
            script_path = None
            if notify_config.script_template or notify_config.script_path:
                if not notify_config.script_template or not notify_config.script_path:
                    return NotificationsInstallResult(
                        success=False,
                        message="Missing script_template or script_path in notify config",
                        method=AGENT_NOTIFY_CONFIG_TYPE,
                    )

                template_path = (
                    NOTIFICATIONS_TEMPLATE_DIR / self.agent / notify_config.script_template
                )
                if not template_path.exists():
                    return NotificationsInstallResult(
                        success=False,
                        message=f"Notify script template not found: {template_path}",
                        method=AGENT_NOTIFY_CONFIG_TYPE,
                    )

                rendered_script = self._render_notify_script(template_path)

                script_path = self.agent_folder / notify_config.script_path
                script_path.parent.mkdir(parents=True, exist_ok=True)
                script_path.write_text(rendered_script, encoding="utf-8")

            try:
                import tomli_w
            except ImportError:
                return NotificationsInstallResult(
                    success=False,
                    message="TOML write support requires 'tomli_w' package",
                    method=AGENT_NOTIFY_CONFIG_TYPE,
                )

            config_path = self.agent_folder / self.notifications_config.config_file
            config_data = self._load_config_file(config_path)

            notify_key = notify_config.config_key or AGENT_NOTIFY_CONFIG_KEY
            rendered_config = self._render_notify_config(config_template_path, script_path)
            notify_value = rendered_config.get(notify_key)
            if notify_value is None:
                return NotificationsInstallResult(
                    success=False,
                    message=f"Notify config template missing key: {notify_key}",
                    method=AGENT_NOTIFY_CONFIG_TYPE,
                )
            config_data[notify_key] = notify_value

            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "wb") as f:
                f.write(tomli_w.dumps(config_data).encode("utf-8"))

            return NotificationsInstallResult(
                success=True,
                message=f"Notifications installed at {config_path}",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )
        except OSError as e:
            return NotificationsInstallResult(
                success=False,
                message=f"Failed to install notifications: {e}",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )

    def remove(self) -> NotificationsInstallResult:
        """Remove notification handlers for the agent."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            AGENT_NOTIFY_CONFIG_KEY,
            AGENT_NOTIFY_CONFIG_TYPE,
        )

        if not self.notifications_config or not self.notifications_config.notify:
            return NotificationsInstallResult(
                success=True,
                message="No notifications configuration, nothing to remove",
            )

        notify_config = self.notifications_config.notify
        if not self.notifications_config.config_file:
            return NotificationsInstallResult(
                success=True,
                message="No config_file specified, nothing to remove",
            )

        config_path = self.agent_folder / self.notifications_config.config_file
        script_path = None
        if notify_config.script_path:
            script_path = self.agent_folder / notify_config.script_path

        try:
            if script_path and script_path.exists():
                script_path.unlink()
                logger.info(f"Removed notify script: {script_path}")

            if config_path.exists():
                import tomllib

                try:
                    import tomli_w
                except ImportError:
                    return NotificationsInstallResult(
                        success=False,
                        message="TOML write support requires 'tomli_w' package",
                        method=AGENT_NOTIFY_CONFIG_TYPE,
                    )

                config_data = tomllib.loads(config_path.read_text())
                notify_key = notify_config.config_key or AGENT_NOTIFY_CONFIG_KEY
                current_value = config_data.get(notify_key)

                if isinstance(current_value, list) and current_value:
                    remove_entry = False
                    if script_path:
                        remove_entry = str(script_path.resolve()) in current_value
                    else:
                        remove_entry = True
                    if remove_entry:
                        config_data.pop(notify_key, None)
                        with open(config_path, "wb") as f:
                            f.write(tomli_w.dumps(config_data).encode("utf-8"))

            return NotificationsInstallResult(
                success=True,
                message=f"Notifications removed from {config_path}",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )
        except OSError as e:
            return NotificationsInstallResult(
                success=False,
                message=f"Failed to remove notifications: {e}",
                method=AGENT_NOTIFY_CONFIG_TYPE,
            )
