"""Hook dispatcher for feature lifecycle events.

Replaces the hardcoded if/elif chain in feature_service._execute_hook with
a registration-based pattern. Each feature registers its own hook handler,
making hook dispatch extensible without modifying the dispatcher.
"""

import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class HookHandler(Protocol):
    """Protocol for feature hook handlers.

    Each feature that subscribes to lifecycle hooks must provide a handler
    that conforms to this protocol.
    """

    def execute(self, action: str, project_root: Path, **kwargs: Any) -> Any:
        """Execute a hook action.

        Args:
            action: Hook action name (e.g., "sync_agent_files")
            project_root: Project root directory
            **kwargs: Arguments for the action

        Returns:
            Result from the action

        Raises:
            ValueError: If action is unknown
        """
        ...


class ConstitutionHookHandler:
    """Hook handler for the constitution (rules-management) feature."""

    def execute(self, action: str, project_root: Path, **kwargs: Any) -> Any:
        """Execute a constitution hook action.

        Args:
            action: Hook action name
            project_root: Project root directory
            **kwargs: Arguments for the action

        Returns:
            Result from the action
        """
        from open_agent_kit.features.rules_management.constitution import ConstitutionService

        constitution_service = ConstitutionService(project_root)

        if action == "sync_agent_files":
            return constitution_service.sync_agent_instruction_files(
                agents_added=kwargs.get("agents_added", []),
                agents_removed=kwargs.get("agents_removed", []),
            )
        else:
            raise ValueError(f"Unknown constitution hook action: {action}")


class TeamHookHandler:
    """Hook handler for the team feature."""

    def execute(self, action: str, project_root: Path, **kwargs: Any) -> Any:
        """Execute a team hook action.

        Args:
            action: Hook action name
            project_root: Project root directory
            **kwargs: Arguments for the action

        Returns:
            Result from the action
        """
        from open_agent_kit.features.team.service import execute_hook

        # For update_agent_hooks, we need to handle agent removal first
        if action == "update_agent_hooks":
            from open_agent_kit.services.config_service import ConfigService

            config = ConfigService(project_root).load_config()
            kwargs["agents"] = config.agents

            agents_removed = kwargs.get("agents_removed", [])
            if agents_removed:
                execute_hook("remove_agent_hooks", project_root, agents_removed=agents_removed)
                execute_hook("remove_mcp_servers", project_root, agents_removed=agents_removed)

        return execute_hook(action, project_root, **kwargs)


class HookDispatcher:
    """Dispatches lifecycle hooks to registered feature handlers.

    Uses a registration pattern so new features can add hook handlers
    without modifying the dispatcher code.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, HookHandler] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register the built-in feature hook handlers."""
        self.register("constitution", ConstitutionHookHandler())
        self.register("team", TeamHookHandler())

    def register(self, feature_name: str, handler: HookHandler) -> None:
        """Register a hook handler for a feature.

        Args:
            feature_name: Feature identifier used in hook specs
            handler: Handler implementing the HookHandler protocol
        """
        self._handlers[feature_name] = handler

    def dispatch(self, hook_spec: str, project_root: Path, **kwargs: Any) -> Any:
        """Execute a feature hook by its specification.

        Hook spec format: "feature:action" (e.g., "constitution:sync_agent_files")

        Args:
            hook_spec: Hook specification string
            project_root: Project root directory
            **kwargs: Arguments to pass to the hook handler

        Returns:
            Result from the hook handler

        Raises:
            ValueError: If hook spec is invalid or handler not found
        """
        if ":" not in hook_spec:
            raise ValueError(f"Invalid hook spec format: {hook_spec} (expected 'feature:action')")

        feature_name, action = hook_spec.split(":", 1)

        handler = self._handlers.get(feature_name)
        if handler is None:
            raise ValueError(f"No hook handler registered for feature: {feature_name}")

        return handler.execute(action, project_root, **kwargs)
