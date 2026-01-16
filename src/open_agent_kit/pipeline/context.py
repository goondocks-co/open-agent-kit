"""Pipeline context for stage-based init/upgrade flows."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, overload


class FlowType(str, Enum):
    """Type of initialization flow being executed."""

    FRESH_INIT = "fresh_init"  # Brand new installation
    UPDATE = "update"  # Idempotent update (re-running init)
    UPGRADE = "upgrade"  # Version upgrade (oak upgrade)
    FORCE_REINIT = "force_reinit"  # Force re-initialization
    REMOVE = "remove"  # Uninstallation (oak remove)


@dataclass
class SelectionState:
    """User selections for agents and features."""

    # Current selections (what user wants)
    agents: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)

    # Previous state (for update flows)
    previous_agents: list[str] = field(default_factory=list)
    previous_features: list[str] = field(default_factory=list)

    @property
    def agents_added(self) -> set[str]:
        """Agents being added in this flow."""
        return set(self.agents) - set(self.previous_agents)

    @property
    def agents_removed(self) -> set[str]:
        """Agents being removed in this flow."""
        return set(self.previous_agents) - set(self.agents)

    @property
    def features_added(self) -> set[str]:
        """Features being added in this flow."""
        return set(self.features) - set(self.previous_features)

    @property
    def features_removed(self) -> set[str]:
        """Features being removed in this flow."""
        return set(self.previous_features) - set(self.features)

    @property
    def has_agent_changes(self) -> bool:
        """Whether agents changed from previous state."""
        return set(self.agents) != set(self.previous_agents)

    @property
    def has_feature_changes(self) -> bool:
        """Whether features changed from previous state."""
        return set(self.features) != set(self.previous_features)

    @property
    def has_any_changes(self) -> bool:
        """Whether any configuration changed."""
        return self.has_agent_changes or self.has_feature_changes


@dataclass
class PipelineContext:
    """Context shared across all pipeline stages.

    This is the primary data structure that flows through the pipeline.
    Stages read from context and can add to stage_results.

    Example:
        >>> ctx = PipelineContext(
        ...     project_root=Path.cwd(),
        ...     flow_type=FlowType.FRESH_INIT,
        ... )
        >>> ctx.selections.agents = ["claude", "cursor"]
        >>> ctx.is_fresh_install
        True
    """

    # Immutable configuration
    project_root: Path
    flow_type: FlowType

    # Runtime options
    force: bool = False
    interactive: bool = True
    dry_run: bool = False  # For upgrade preview

    # User selections (populated by selection stages or CLI)
    selections: SelectionState = field(default_factory=SelectionState)

    # Stage results (populated during execution)
    stage_results: dict[str, Any] = field(default_factory=dict)

    # Errors and warnings collected during execution
    errors: list[tuple[str, str]] = field(default_factory=list)  # (stage_name, error_msg)
    warnings: list[tuple[str, str]] = field(default_factory=list)

    @property
    def oak_dir(self) -> Path:
        """Path to .oak directory."""
        return self.project_root / ".oak"

    @property
    def is_fresh_install(self) -> bool:
        """Whether this is a fresh installation."""
        return self.flow_type == FlowType.FRESH_INIT

    @property
    def is_update(self) -> bool:
        """Whether this is an update to existing installation."""
        return self.flow_type == FlowType.UPDATE

    @property
    def is_upgrade(self) -> bool:
        """Whether this is a version upgrade."""
        return self.flow_type == FlowType.UPGRADE

    @property
    def is_force_reinit(self) -> bool:
        """Whether this is a forced re-initialization."""
        return self.flow_type == FlowType.FORCE_REINIT

    @property
    def is_remove(self) -> bool:
        """Whether this is an uninstallation."""
        return self.flow_type == FlowType.REMOVE

    def add_error(self, stage_name: str, message: str) -> None:
        """Record an error from a stage."""
        self.errors.append((stage_name, message))

    def add_warning(self, stage_name: str, message: str) -> None:
        """Record a warning from a stage."""
        self.warnings.append((stage_name, message))

    @overload
    def set_result(self, stage_name: str, result: dict[str, Any]) -> None:
        """Store result from a stage for later stages to use.

        Args:
            stage_name: Unique identifier for the stage producing this result
            result: Dictionary of result data from the stage
        """
        ...

    @overload
    def set_result(self, stage_name: str, result: Any) -> None:
        """Store result from a stage for later stages to use.

        Args:
            stage_name: Unique identifier for the stage producing this result
            result: Result data from the stage (any type)
        """
        ...

    def set_result(self, stage_name: str, result: Any) -> None:
        """Store result from a stage for later stages to use.

        Args:
            stage_name: Unique identifier for the stage producing this result
            result: Result data from the stage (typically a dict or None)

        Example:
            >>> ctx.set_result("install_agents", {"agents": ["claude", "cursor"]})
            >>> agents = ctx.get_result("install_agents", {}).get("agents", [])
        """
        self.stage_results[stage_name] = result

    @overload
    def get_result(self, stage_name: str, default: None = None) -> Any | None:
        """Get result from a previous stage with proper typing.

        Args:
            stage_name: Unique identifier for the stage
            default: Default value if stage result not found

        Returns:
            The stage result or default value, properly typed based on context
        """
        ...

    @overload
    def get_result(self, stage_name: str, default: dict[str, Any]) -> dict[str, Any]:
        """Get result from a previous stage expecting a dict.

        Args:
            stage_name: Unique identifier for the stage
            default: Default dict value if stage result not found

        Returns:
            The stage result dict or provided default (never None when default provided)
        """
        ...

    def get_result(self, stage_name: str, default: Any = None) -> Any:
        """Get result from a previous stage.

        This retrieves the result data stored by a previous stage execution.
        Most results are dictionaries with stage-specific keys.

        Args:
            stage_name: Unique identifier for the stage that produced the result
            default: Default value to return if stage result not found (defaults to None)

        Returns:
            The stage result data, or default if not found

        Example:
            >>> result = ctx.get_result("load_config", {})
            >>> agents = result.get("agents", [])
        """
        return self.stage_results.get(stage_name, default)
