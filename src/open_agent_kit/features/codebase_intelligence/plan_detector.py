"""Plan detection utilities for codebase intelligence.

Dynamically discovers plan directories from agent manifests,
enabling automatic support for new agents without code changes.

Supports both:
- Project-local plans: .claude/plans/, .cursor/plans/ (in project root)
- Global plans: ~/.claude/plans/, ~/.cursor/plans/ (in home directory)

Architecture:
- Uses AgentService to discover plan directories from manifests
- No hardcoded agent lists or plan patterns
- New agents automatically supported when manifest includes plans_subfolder
- Singleton pattern for efficient caching of plan patterns
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.services.agent_service import AgentService

logger = logging.getLogger(__name__)


@dataclass
class PlanDetectionResult:
    """Result of plan file detection.

    Attributes:
        is_plan: Whether the file is a plan file
        agent_type: The agent type that owns the plan (e.g., 'claude', 'cursor')
        plans_dir: The plans directory pattern that matched
        is_global: True if plan is in global (~/) directory, False if project-local
    """

    is_plan: bool
    agent_type: str | None = None
    plans_dir: str | None = None
    is_global: bool = False


class PlanDetector:
    """Detects plan files across all supported AI coding agents.

    Uses AgentService to dynamically discover plan directories from manifests,
    making it automatically extensible when new agents are added.

    Supports both project-local and global (home directory) plan locations:
    - Project: /path/to/project/.claude/plans/my-plan.md
    - Global: ~/.claude/plans/my-plan.md (cloud agents, shared plans)

    Example:
        >>> detector = PlanDetector(project_root=Path("/repo"))
        >>> result = detector.detect("/repo/.claude/plans/feature.md")
        >>> result.is_plan
        True
        >>> result.agent_type
        'claude'
        >>> result.is_global
        False
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize plan detector.

        Args:
            project_root: Project root for AgentService (defaults to cwd)
        """
        self._project_root = project_root or Path.cwd()
        self._agent_service: AgentService | None = None  # Lazy initialization
        self._plan_patterns: dict[str, str] | None = None
        self._home_dir = Path.home()

    def _get_agent_service(self) -> "AgentService":
        """Lazy initialization of AgentService to avoid circular imports."""
        if self._agent_service is None:
            from open_agent_kit.services.agent_service import AgentService

            self._agent_service = AgentService(self._project_root)
        return self._agent_service

    def _get_plan_patterns(self) -> dict[str, str]:
        """Get plan directory patterns from all agent manifests.

        Returns:
            Dict mapping plan directory pattern to agent type.
            Example: {'.claude/plans/': 'claude', '.cursor/plans/': 'cursor'}

        Patterns are normalized to match both project-local and global paths.
        Cached for performance after first call.
        """
        if self._plan_patterns is None:
            self._plan_patterns = {}
            try:
                agent_service = self._get_agent_service()
                plan_dirs = agent_service.get_all_plan_directories()
                for agent_type, plans_dir in plan_dirs.items():
                    # Store the pattern with trailing slash for matching
                    # e.g., '.claude/plans/' matches both '/project/.claude/plans/file.md'
                    # and '~/.claude/plans/file.md'
                    pattern = plans_dir.rstrip("/") + "/"
                    self._plan_patterns[pattern] = agent_type
                logger.debug(
                    f"Loaded plan patterns for {len(self._plan_patterns)} agents",
                    extra={"agents": list(self._plan_patterns.values())},
                )
            except Exception as e:
                logger.warning(f"Failed to load plan patterns: {e}")
                self._plan_patterns = {}
        return self._plan_patterns

    def _is_global_path(self, file_path: str) -> bool:
        """Determine if a file path is in the global (home) directory.

        Args:
            file_path: Absolute or relative file path

        Returns:
            True if path is in home directory but not in project root
        """
        try:
            path = Path(file_path).resolve()
            # Check if path is under home but not under project root
            is_under_home = str(path).startswith(str(self._home_dir))
            is_under_project = str(path).startswith(str(self._project_root.resolve()))
            return is_under_home and not is_under_project
        except (ValueError, OSError):
            return False

    def detect(self, file_path: str | None) -> PlanDetectionResult:
        """Detect if a file path is a plan file.

        Checks both project-local and global plan directories for all
        supported agents. Detection is pattern-based using the plans_subfolder
        from each agent's manifest.

        Args:
            file_path: File path to check (can be None)

        Returns:
            PlanDetectionResult with is_plan, agent_type, plans_dir, and is_global
        """
        if not file_path:
            return PlanDetectionResult(is_plan=False)

        patterns = self._get_plan_patterns()
        for pattern, agent_type in patterns.items():
            if pattern in file_path:
                is_global = self._is_global_path(file_path)
                location = "global" if is_global else "project"
                logger.info(
                    f"Detected {location} plan file for {agent_type}",
                    extra={
                        "agent_type": agent_type,
                        "file_path": file_path,
                        "plans_dir": pattern,
                        "is_global": is_global,
                        "location": location,
                    },
                )
                return PlanDetectionResult(
                    is_plan=True,
                    agent_type=agent_type,
                    plans_dir=pattern,
                    is_global=is_global,
                )

        return PlanDetectionResult(is_plan=False)

    def is_plan_file(self, file_path: str | None) -> bool:
        """Check if a file path is a plan file.

        Convenience method for simple boolean checks.

        Args:
            file_path: File path to check

        Returns:
            True if file is in any agent's plans directory (local or global)
        """
        return self.detect(file_path).is_plan

    def get_supported_agents(self) -> list[str]:
        """Get list of agents with plan support.

        Returns:
            List of agent type names that have plans directories configured
        """
        return list(self._get_plan_patterns().values())


# Module-level singleton for convenience
_detector: PlanDetector | None = None


def get_plan_detector(project_root: Path | None = None) -> PlanDetector:
    """Get or create the plan detector singleton.

    The singleton is lazily initialized on first access. If a different
    project_root is needed, create a new PlanDetector instance directly.

    Args:
        project_root: Project root (only used on first call)

    Returns:
        PlanDetector instance
    """
    global _detector
    if _detector is None:
        _detector = PlanDetector(project_root)
    return _detector


def reset_plan_detector() -> None:
    """Reset the plan detector singleton.

    Useful for testing or when project root changes.
    """
    global _detector
    _detector = None


def is_plan_file(file_path: str | None) -> bool:
    """Convenience function to check if path is a plan file.

    Args:
        file_path: File path to check

    Returns:
        True if file is in any agent's plans directory
    """
    return get_plan_detector().is_plan_file(file_path)


def detect_plan(file_path: str | None) -> PlanDetectionResult:
    """Convenience function to detect plan file with full details.

    Args:
        file_path: File path to check

    Returns:
        PlanDetectionResult with agent info
    """
    return get_plan_detector().detect(file_path)
