"""Agent notification installer for Codebase Intelligence."""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.notifications.installer import (
    NotificationsInstaller,
    NotificationsInstallResult,
)


def install_notifications(project_root: Path, agent: str) -> NotificationsInstallResult:
    """Install notification handlers for an agent."""
    return NotificationsInstaller(project_root, agent).install()


def remove_notifications(project_root: Path, agent: str) -> NotificationsInstallResult:
    """Remove notification handlers for an agent."""
    return NotificationsInstaller(project_root, agent).remove()


__all__ = [
    "install_notifications",
    "remove_notifications",
    "NotificationsInstallResult",
]
