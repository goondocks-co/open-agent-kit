"""Codebase Intelligence feature service.

Handles feature lifecycle hooks and coordinates CI functionality.
"""

import logging
import os
import webbrowser
from pathlib import Path
from typing import Any, cast

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
from open_agent_kit.features.codebase_intelligence.daemon.manager import get_project_port

logger = logging.getLogger(__name__)

# Path to the feature's MCP configuration directory
MCP_TEMPLATE_DIR = Path(__file__).parent / "mcp"


class CodebaseIntelligenceService:
    """Service for Codebase Intelligence feature lifecycle management.

    This service is called by OAK's feature system in response to
    lifecycle events defined in the manifest.yaml.
    """

    def __init__(self, project_root: Path):
        """Initialize CI service.

        Args:
            project_root: Root directory of the OAK project.
        """
        self.project_root = project_root
        self.ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        self._port: int | None = None

    @property
    def port(self) -> int:
        """Get the daemon port for this project.

        Port is derived deterministically from the project path to support
        multiple CI daemons running simultaneously.
        """
        if self._port is None:
            self._port = get_project_port(self.project_root, self.ci_data_dir)
        return self._port

    def _is_test_environment(self) -> bool:
        """Check if we're running in a test or CI environment.

        Returns:
            True if running in pytest, CI, or non-interactive environment.
        """
        import sys

        # Check if pytest is loaded (most reliable for pytest runs)
        if "pytest" in sys.modules:
            return True

        # Check for common test/CI environment variables
        test_indicators = [
            "PYTEST_CURRENT_TEST",  # Set by pytest
            "CI",  # Common CI indicator
            "GITHUB_ACTIONS",  # GitHub Actions
            "GITLAB_CI",  # GitLab CI
            "JENKINS_URL",  # Jenkins
            "OAK_TESTING",  # Our own testing flag
        ]
        return any(os.environ.get(var) for var in test_indicators)

    def _get_daemon_manager(self) -> Any:
        """Get daemon manager instance."""
        from open_agent_kit.features.codebase_intelligence.daemon.manager import DaemonManager

        return DaemonManager(
            project_root=self.project_root,
            port=self.port,
            ci_data_dir=self.ci_data_dir,
        )

    # Lifecycle hook handlers

    def initialize(self) -> dict:
        """Called when feature is enabled (on_feature_enabled hook).

        Sets up the CI data directory, installs agent hooks, and starts the daemon.
        Gitignore patterns are handled declaratively via the manifest 'gitignore' field.

        This method will auto-install CI dependencies if they're not present.

        Returns:
            Result dictionary with status.
        """
        from rich.console import Console

        from open_agent_kit.features.codebase_intelligence.deps import (
            check_ci_dependencies,
            ensure_ci_dependencies,
        )

        console = Console()
        logger.info("Initializing Codebase Intelligence feature")

        # Check and install dependencies if needed
        missing_deps = check_ci_dependencies()
        if missing_deps:
            console.print(
                f"[yellow]Installing CI dependencies: {', '.join(missing_deps)}...[/yellow]"
            )
            try:
                if not ensure_ci_dependencies(auto_install=True):
                    return {
                        "status": "error",
                        "message": "Failed to install CI dependencies. Check logs for details.",
                    }
                console.print("[green]CI dependencies installed successfully[/green]")
            except Exception as e:
                logger.error(f"Failed to install CI dependencies: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to install CI dependencies: {e}",
                }

        # Create data directory
        self.ci_data_dir.mkdir(parents=True, exist_ok=True)

        # Restore history from backup if exists
        # This must happen before daemon starts so data is available
        try:
            self._restore_history_backup()
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to restore history backup: {e}")

        # Install built-in agent tasks to project (won't overwrite existing)
        try:
            from open_agent_kit.features.codebase_intelligence.agents.registry import (
                AgentRegistry,
            )

            registry = AgentRegistry(project_root=self.project_root)
            install_results = registry.install_builtin_tasks(force=False)
            installed = [k for k, v in install_results.items() if v == "installed"]
            if installed:
                console.print(f"[green]Installed agent tasks: {', '.join(installed)}[/green]")
        except Exception as e:
            logger.warning(f"Failed to install built-in agent tasks: {e}")

        # Note: .gitignore is handled declaratively via manifest.yaml gitignore field
        # The feature_service adds .oak/ci/ on enable and removes it on disable

        # Get configured agents and call ensure_daemon to install hooks + start daemon
        # This ensures CI is fully operational whether called from oak init or oak feature add
        # Pass open_browser=True for interactive initialization
        daemon_result = {}
        try:
            from open_agent_kit.services.config_service import ConfigService

            config_service = ConfigService(self.project_root)
            agents = config_service.get_agents()
            daemon_result = self.ensure_daemon(agents, open_browser=True)
        except Exception as e:
            logger.warning(f"Failed to ensure daemon during initialize: {e}")
            daemon_result = {"status": "warning", "message": str(e)}

        return {
            "status": "success",
            "message": "CI feature initialized",
            **daemon_result,
        }

    def _export_history_backup(self) -> None:
        """Export activity history before cleanup.

        Exports sessions, prompts, and memory observations to a SQL file
        in the configured backup directory. This allows data to be
        restored when the feature is re-enabled.
        """
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
            get_backup_filename,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
        )

        db_path = self.ci_data_dir / CI_ACTIVITIES_DB_FILENAME
        if not db_path.exists():
            logger.debug("No activities database found, skipping backup export")
            return

        backup_dir = get_backup_dir(self.project_root)
        backup_path = backup_dir / get_backup_filename()

        try:
            from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

            logger.info("Exporting CI history before cleanup...")
            store = ActivityStore(db_path)
            count = store.export_to_sql(backup_path, include_activities=False)
            store.close()
            logger.info(f"CI history exported to {backup_path} ({count} records)")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to export CI history: {e}")

    def _restore_history_backup(self) -> None:
        """Restore activity history from backup if exists.

        Imports sessions, prompts, and memory observations from the SQL
        backup file. ChromaDB will be rebuilt automatically from the
        restored observations (they are marked as unembedded).
        """
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
            get_backup_filename,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
        )

        backup_dir = get_backup_dir(self.project_root)
        backup_path = backup_dir / get_backup_filename()
        if not backup_path.exists():
            logger.debug(f"No backup found at {backup_path}")
            return

        db_path = self.ci_data_dir / CI_ACTIVITIES_DB_FILENAME

        try:
            from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

            logger.info(f"Restoring CI history from {backup_path}")
            store = ActivityStore(db_path)
            count = store.import_from_sql(backup_path)
            store.close()
            logger.info(f"CI history restored: {count} records")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to restore CI history: {e}")

    def cleanup(self, agents: list[str] | None = None) -> dict:
        """Called when feature is disabled (on_feature_disabled hook).

        Performs full cleanup:
        1. Exports history to backup (preserves valuable data)
        2. Stops the daemon
        3. Removes CI data directory (database, config)
        4. Removes agent hooks
        5. Removes MCP server registrations

        Args:
            agents: List of configured agents to remove hooks from.

        Returns:
            Result dictionary with status.
        """
        import shutil

        from open_agent_kit.utils import print_info, print_success, print_warning

        logger.info("Cleaning up Codebase Intelligence feature")
        print_info("Cleaning up Codebase Intelligence...")

        results: dict[str, bool | dict[str, str]] = {
            "daemon_stopped": False,
            "data_removed": False,
            "hooks_removed": {},
            "notifications_removed": {},
            "mcp_removed": {},
            "history_exported": False,
        }

        # 0. Export history before cleanup
        try:
            self._export_history_backup()
            results["history_exported"] = True
            print_success("  History exported to oak/data/ci_history.sql")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to export history: {e}")
            print_warning(f"  Could not export history: {e}")

        # 1. Stop the daemon
        try:
            manager = self._get_daemon_manager()
            manager.stop()
            results["daemon_stopped"] = True
            print_success("  Daemon stopped")
        except Exception as e:
            logger.warning(f"Failed to stop daemon: {e}")
            print_warning(f"  Could not stop daemon: {e}")

        # 2. Remove CI data directory (contains ChromaDB, config, logs)
        if self.ci_data_dir.exists():
            try:
                shutil.rmtree(self.ci_data_dir)
                results["data_removed"] = True
                print_success(f"  Data directory removed: {self.ci_data_dir}")
                logger.info(f"Removed CI data directory: {self.ci_data_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove CI data directory: {e}")
                print_warning(f"  Could not remove data directory: {e}")

        # 3. Remove agent hooks
        if agents:
            results["hooks_removed"] = self._remove_agent_hooks(agents)
            hooks_removed = cast(dict[str, str], results["hooks_removed"])
            removed = [a for a, s in hooks_removed.items() if s == "removed"]
            if removed:
                print_success(f"  Hooks removed from: {', '.join(removed)}")

        # 4. Remove agent notifications
        if agents:
            results["notifications_removed"] = self._remove_agent_notifications(agents)
            notifications_removed = cast(dict[str, str], results["notifications_removed"])
            removed_notifications = [a for a, s in notifications_removed.items() if s == "removed"]
            if removed_notifications:
                print_success(f"  Notifications removed from: {', '.join(removed_notifications)}")

        # 5. Remove MCP server registrations
        if agents:
            results["mcp_removed"] = self.remove_mcp_server(agents)
            mcp_removed = cast(dict[str, str], results["mcp_removed"])
            removed_mcp = [a for a, s in mcp_removed.items() if s == "removed"]
            if removed_mcp:
                print_success(f"  MCP servers removed from: {', '.join(removed_mcp)}")

        return {
            "status": "success",
            "message": "CI feature cleaned up",
            **results,
        }

    def ensure_daemon(self, agents: list[str] | None = None, open_browser: bool = False) -> dict:
        """Ensure the daemon is running and agent hooks are installed.

        Called from initialize() during feature enable. Handles both daemon
        startup and hook installation in one place.

        Args:
            agents: List of configured agents.
            open_browser: If True, open browser to config page after daemon starts.
                          Only set True for interactive initialization.

        Returns:
            Result dictionary with status.
        """
        from open_agent_kit.utils import print_info, print_success, print_warning

        logger.info("Ensuring CI daemon is running")
        print_info("Starting Codebase Intelligence daemon (this may take a moment on first run)...")

        daemon_result = {"status": "unknown", "message": ""}

        try:
            manager = self._get_daemon_manager()
            if manager.ensure_running():
                port = manager.port
                print_success(f"CI daemon running at http://localhost:{port}")
                print_info(f"  Dashboard: http://localhost:{port}/ui")
                daemon_result = {"status": "success", "message": "CI daemon is running"}

                # Auto-launch browser to config page for initial setup
                # Only if explicitly requested AND not in test/CI environment
                if open_browser and not self._is_test_environment():
                    config_url = f"http://localhost:{port}/config"
                    print_info("  Opening config page in browser...")
                    try:
                        webbrowser.open(config_url)
                    except Exception as browser_err:
                        logger.warning(f"Could not open browser: {browser_err}")
                        print_info(f"  Open {config_url} to configure embedding settings")
            else:
                log_file = manager.log_file
                print_warning(f"CI daemon failed to start. Check logs: {log_file}")
                daemon_result = {
                    "status": "warning",
                    "message": f"Failed to start daemon. See {log_file}",
                }
        except Exception as e:
            logger.warning(f"Failed to ensure daemon: {e}")
            print_warning(f"CI daemon error: {e}")
            daemon_result = {"status": "warning", "message": str(e)}

        # Install agent hooks
        hooks_result: dict[str, Any] = {"agents": {}}
        if agents:
            logger.info(f"Installing CI hooks for agents: {agents}")
            hooks_result = self.update_agent_hooks(agents)
            if hooks_result.get("agents"):
                installed = [a for a, s in hooks_result["agents"].items() if s == "updated"]
                if installed:
                    print_info(f"  CI hooks installed for: {', '.join(installed)}")

        # Install agent notifications (notify handlers)
        notifications_result: dict[str, Any] = {"agents": {}}
        if agents:
            logger.info(f"Installing CI notifications for agents: {agents}")
            notifications_result = self.update_agent_notifications(agents)
            if notifications_result.get("agents"):
                installed = [a for a, s in notifications_result["agents"].items() if s == "updated"]
                if installed:
                    print_info(f"  CI notifications installed for: {', '.join(installed)}")

        # Install MCP servers for agents that support it
        mcp_result: dict[str, Any] = {"agents": {}}
        if agents:
            logger.info(f"Installing MCP servers for agents: {agents}")
            mcp_result["agents"] = self.install_mcp_server(agents)
            installed_mcp = [a for a, s in mcp_result["agents"].items() if s == "installed"]
            if installed_mcp:
                print_info(f"  MCP server registered for: {', '.join(installed_mcp)}")

        return {
            **daemon_result,
            "hooks": hooks_result,
            "notifications": notifications_result,
            "mcp": mcp_result,
        }

    def update_agent_hooks(self, agents: list[str]) -> dict:
        """Called when agents change (on_agents_changed hook) or during upgrade.

        Updates agent hook configurations to integrate with CI daemon.
        Uses the manifest-driven HooksInstaller for all agents.

        Args:
            agents: List of agent names that are configured.

        Returns:
            Result dictionary with status.
        """
        from open_agent_kit.features.codebase_intelligence.hooks import install_hooks

        logger.info(f"Updating CI hooks for agents: {agents}")

        results = {}
        for agent in agents:
            try:
                result = install_hooks(self.project_root, agent)
                if result.success:
                    results[agent] = "updated"
                    logger.info(f"Installed hooks for {agent} via {result.method}")
                else:
                    results[agent] = f"error: {result.message}"
                    logger.warning(f"Failed to install hooks for {agent}: {result.message}")
            except Exception as e:
                logger.warning(f"Failed to update hooks for {agent}: {e}")
                results[agent] = f"error: {e}"

        return {"status": "success", "agents": results}

    def update_mcp_servers(self, agents: list[str]) -> dict:
        """Update MCP server registrations for configured agents.

        Called during upgrade or when agents change. Installs/updates MCP
        server configurations for agents that support MCP (has_mcp=true).

        Args:
            agents: List of agent names that are configured.

        Returns:
            Result dictionary with status.
        """
        logger.info(f"Updating MCP servers for agents: {agents}")
        results = self.install_mcp_server(agents)
        return {"status": "success", "agents": results}

    def update_agent_notifications(self, agents: list[str]) -> dict:
        """Install or update agent notification handlers.

        Uses the manifest-driven NotificationsInstaller for all agents.

        Args:
            agents: List of agent names that are configured.

        Returns:
            Result dictionary with status.
        """
        from open_agent_kit.features.codebase_intelligence.notifications import (
            install_notifications,
        )

        logger.info(f"Updating CI notifications for agents: {agents}")

        results = {}
        for agent in agents:
            try:
                result = install_notifications(self.project_root, agent)
                if result.success:
                    results[agent] = "updated"
                    logger.info(f"Installed notifications for {agent} via {result.method}")
                else:
                    results[agent] = f"error: {result.message}"
                    logger.warning(f"Failed to install notifications for {agent}: {result.message}")
            except Exception as e:
                logger.warning(f"Failed to update notifications for {agent}: {e}")
                results[agent] = f"error: {e}"

        return {"status": "success", "agents": results}

    def _remove_agent_hooks(self, agents: list[str]) -> dict[str, str]:
        """Remove CI hooks from all specified agents.

        Uses the manifest-driven HooksInstaller for all agents.

        Args:
            agents: List of agent names to remove hooks from.

        Returns:
            Dictionary mapping agent names to removal status.
        """
        from open_agent_kit.features.codebase_intelligence.hooks import remove_hooks

        logger.info(f"Removing CI hooks from agents: {agents}")

        results = {}
        for agent in agents:
            try:
                result = remove_hooks(self.project_root, agent)
                if result.success:
                    results[agent] = "removed"
                    logger.info(f"Removed hooks for {agent} via {result.method}")
                else:
                    results[agent] = f"error: {result.message}"
                    logger.warning(f"Failed to remove hooks for {agent}: {result.message}")
            except Exception as e:
                logger.warning(f"Failed to remove hooks for {agent}: {e}")
                results[agent] = f"error: {e}"

        return results

    def _remove_agent_notifications(self, agents: list[str]) -> dict[str, str]:
        """Remove CI notification handlers from all specified agents.

        Uses the manifest-driven NotificationsInstaller for all agents.

        Args:
            agents: List of agent names to remove notifications from.

        Returns:
            Dictionary mapping agent names to removal status.
        """
        from open_agent_kit.features.codebase_intelligence.notifications import (
            remove_notifications,
        )

        logger.info(f"Removing CI notifications from agents: {agents}")

        results = {}
        for agent in agents:
            try:
                result = remove_notifications(self.project_root, agent)
                if result.success:
                    results[agent] = "removed"
                    logger.info(f"Removed notifications for {agent} via {result.method}")
                else:
                    results[agent] = f"error: {result.message}"
                    logger.warning(f"Failed to remove notifications for {agent}: {result.message}")
            except Exception as e:
                logger.warning(f"Failed to remove notifications for {agent}: {e}")
                results[agent] = f"error: {e}"

        return results

    # --- MCP Server Registration Methods ---

    def _load_mcp_config(self) -> dict[str, Any] | None:
        """Load MCP server configuration from mcp.yaml.

        Returns:
            MCP configuration dict, or None if not found.
        """
        import yaml

        mcp_config_path = MCP_TEMPLATE_DIR / "mcp.yaml"
        if not mcp_config_path.exists():
            logger.warning(f"MCP config not found: {mcp_config_path}")
            return None

        try:
            with open(mcp_config_path) as f:
                config = yaml.safe_load(f)
            return cast(dict[str, Any], config)
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return None

    def _get_agent_has_mcp(self, agent: str) -> bool:
        """Check if an agent has MCP capability.

        Args:
            agent: Agent name (claude, cursor, codex, etc.)

        Returns:
            True if agent supports MCP, False otherwise.
        """
        try:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService(self.project_root)
            context = agent_service.get_agent_context(agent)
            return bool(context.get("has_mcp", False))
        except Exception as e:
            logger.warning(f"Failed to check MCP capability for {agent}: {e}")
            return False

    def install_mcp_server(self, agents: list[str]) -> dict[str, str]:
        """Install MCP server for agents that support it.

        Uses the Python-based MCPInstaller which reads configuration from
        agent manifests. Tries CLI first if available, falls back to JSON.

        Args:
            agents: List of agent names.

        Returns:
            Dictionary mapping agent names to installation status.
        """
        from open_agent_kit.features.codebase_intelligence.mcp import install_mcp_server

        # Load MCP server configuration
        mcp_config = self._load_mcp_config()
        if not mcp_config:
            return dict.fromkeys(agents, "error: MCP config not found")

        server_name = mcp_config.get("name", "oak-ci")
        # Build command (no longer uses --project flag, relies on cwd)
        command = mcp_config.get("command", "oak ci mcp")
        # Remove any {{PROJECT_ROOT}} placeholder if present (legacy configs)
        command = command.replace("--project {{PROJECT_ROOT}}", "").strip()
        command = command.replace("{{PROJECT_ROOT}}", "").strip()

        results = {}
        for agent in agents:
            if not self._get_agent_has_mcp(agent):
                results[agent] = "skipped (no MCP support)"
                continue

            result = install_mcp_server(
                project_root=self.project_root,
                agent=agent,
                server_name=server_name,
                command=command,
            )

            if result.success:
                results[agent] = "installed"
                logger.info(f"Installed MCP server for {agent} via {result.method}")
            else:
                results[agent] = f"error: {result.message}"
                logger.warning(f"Failed to install MCP server for {agent}: {result.message}")

        return results

    def remove_mcp_server(self, agents: list[str]) -> dict[str, str]:
        """Remove MCP server from agents.

        Uses the Python-based MCPInstaller which reads configuration from
        agent manifests. Tries CLI first if available, falls back to JSON.

        Args:
            agents: List of agent names.

        Returns:
            Dictionary mapping agent names to removal status.
        """
        from open_agent_kit.features.codebase_intelligence.mcp import remove_mcp_server

        # Load MCP server configuration to get server name
        mcp_config = self._load_mcp_config()
        server_name = mcp_config.get("name", "oak-ci") if mcp_config else "oak-ci"

        results = {}
        for agent in agents:
            result = remove_mcp_server(
                project_root=self.project_root,
                agent=agent,
                server_name=server_name,
            )

            if result.success:
                results[agent] = "removed"
                logger.info(f"Removed MCP server for {agent} via {result.method}")
            else:
                results[agent] = f"error: {result.message}"
                logger.warning(f"Failed to remove MCP server for {agent}: {result.message}")

        return results


def execute_hook(hook_action: str, project_root: Path, **kwargs: Any) -> dict[str, Any]:
    """Execute a CI hook action.

    This function is called by OAK's feature system to handle
    lifecycle hooks for the codebase-intelligence feature.

    Args:
        hook_action: The action to perform (e.g., "initialize", "cleanup").
        project_root: Root directory of the project.
        **kwargs: Additional arguments passed to the hook.

    Returns:
        Result dictionary from the hook.
    """
    service = CodebaseIntelligenceService(project_root)

    def _get_agents() -> list[str]:
        """Get agents from kwargs or load from config."""
        agents: list[str] = kwargs.get("agents", [])
        if not agents:
            # Load from config (for on_post_upgrade which doesn't pass agents)
            from open_agent_kit.services.config_service import ConfigService

            config = ConfigService(project_root).load_config()
            agents = config.agents
        return agents

    def _get_removed_agents() -> list[str]:
        """Get removed agents from kwargs."""
        removed: list[str] = kwargs.get("agents_removed", [])
        return removed

    handlers = {
        "initialize": service.initialize,
        "cleanup": lambda: service.cleanup(agents=_get_agents()),
        "on_pre_remove": lambda: service.cleanup(agents=_get_agents()),  # Same as cleanup
        "ensure_daemon": lambda: service.ensure_daemon(agents=_get_agents()),
        # Hooks management
        "update_agent_hooks": lambda: service.update_agent_hooks(_get_agents()),
        "remove_agent_hooks": lambda: {
            "status": "success",
            "agents": service._remove_agent_hooks(_get_removed_agents()),
        },
        "update_agent_notifications": lambda: service.update_agent_notifications(_get_agents()),
        "remove_agent_notifications": lambda: {
            "status": "success",
            "agents": service._remove_agent_notifications(_get_removed_agents()),
        },
        # MCP server management (separate from hooks)
        "update_mcp_servers": lambda: service.update_mcp_servers(_get_agents()),
        "remove_mcp_servers": lambda: {
            "status": "success",
            "agents": service.remove_mcp_server(_get_removed_agents()),
        },
    }

    handler = handlers.get(hook_action)
    if not handler:
        return {"status": "error", "message": f"Unknown hook action: {hook_action}"}

    return handler()
