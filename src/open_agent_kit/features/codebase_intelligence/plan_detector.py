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
- Heuristic response pattern matching for inline plan detection
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import PLAN_RESPONSE_SCAN_LENGTH

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
            except (OSError, ValueError, KeyError, AttributeError) as e:
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

    def find_recent_plan_file(
        self,
        max_age_seconds: int = 300,
        agent_type: str | None = None,
    ) -> PlanDetectionResult | None:
        """Find the most recently modified plan file on disk.

        Scans both project-local and global plan directories for all agents
        (or a specific agent). Returns the newest file modified within the
        time window.

        This handles agents like Cursor that create plan files internally
        (IDE-side) without using Read/Edit/Write tools, so the file never
        appears in hook activity.

        Args:
            max_age_seconds: Maximum file age in seconds (default 5 minutes).
            agent_type: Optional agent to restrict search to.

        Returns:
            PlanDetectionResult with ``plans_dir`` set to the file path,
            or None if no recent plan file found.
        """
        import time

        patterns = self._get_plan_patterns()
        if not patterns:
            return None

        now = time.time()
        best_path: Path | None = None
        best_mtime: float = 0.0
        best_agent: str | None = None
        best_is_global = False

        for pattern, pat_agent in patterns.items():
            if agent_type and pat_agent != agent_type:
                continue

            # Derive directory name from pattern (e.g. ".cursor/plans/" -> ".cursor/plans")
            dir_rel = pattern.rstrip("/")

            # Check both project-local and global (home) locations
            candidates: list[tuple[Path, bool]] = []
            if self._project_root:
                candidates.append((self._project_root / dir_rel, False))
            candidates.append((self._home_dir / dir_rel, True))

            for plans_dir, is_global in candidates:
                if not plans_dir.is_dir():
                    continue
                try:
                    for child in plans_dir.iterdir():
                        if not child.is_file():
                            continue
                        try:
                            mtime = child.stat().st_mtime
                        except OSError:
                            continue
                        age = now - mtime
                        if age <= max_age_seconds and mtime > best_mtime:
                            best_path = child
                            best_mtime = mtime
                            best_agent = pat_agent
                            best_is_global = is_global
                except OSError:
                    continue

        if best_path is None:
            return None

        logger.info(
            f"Found recent plan file: {best_path} "
            f"(agent={best_agent}, age={now - best_mtime:.0f}s)"
        )
        return PlanDetectionResult(
            is_plan=True,
            agent_type=best_agent,
            plans_dir=str(best_path),
            is_global=best_is_global,
        )


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


def find_recent_plan_file(
    max_age_seconds: int = 300,
    agent_type: str | None = None,
) -> PlanDetectionResult | None:
    """Convenience function: find the most recently modified plan file.

    Args:
        max_age_seconds: Maximum file age in seconds.
        agent_type: Optional agent to restrict search to.

    Returns:
        PlanDetectionResult with plans_dir set to the file path, or None.
    """
    return get_plan_detector().find_recent_plan_file(max_age_seconds, agent_type)


def detect_plan(file_path: str | None) -> PlanDetectionResult:
    """Convenience function to detect plan file with full details.

    Args:
        file_path: File path to check

    Returns:
        PlanDetectionResult with agent info
    """
    return get_plan_detector().detect(file_path)


@dataclass
class PlanResolution:
    """Result of resolving plan content from a file on disk.

    Returned by :func:`resolve_plan_content` when a plan file is found
    and its content passes the size threshold.

    Attributes:
        file_path: Absolute path to the plan file.
        content: Full text content read from disk.
        strategy: Which strategy found the file — for logging/debugging.
            One of ``"known_path"``, ``"candidate"``, ``"transcript"``,
            ``"filesystem"``.
    """

    file_path: str
    content: str
    strategy: str


def _read_plan_file(file_path: str, project_root: Path | None = None) -> str | None:
    """Read a plan file from disk, resolving relative paths."""
    path = Path(file_path)
    if not path.is_absolute() and project_root:
        path = project_root / path
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        logger.warning("Failed to read plan file %s: %s", path, e)
    return None


def _content_passes_threshold(
    content: str,
    min_content_length: int,
    existing_content_length: int,
) -> bool:
    """Check if resolved content is large enough to be useful.

    When ``existing_content_length > 0``, the resolved content must be at
    least twice as large — this prevents overriding Claude's prompt-embedded
    plans with a stale file that happens to match.
    """
    if min_content_length > 0 and len(content) < min_content_length:
        return False
    if existing_content_length > 0 and len(content) <= existing_content_length * 2:
        return False
    return True


def resolve_plan_content(
    *,
    known_plan_file_path: str | None = None,
    candidate_paths: list[str] | None = None,
    transcript_path: str | None = None,
    agent_type: str | None = None,
    max_age_seconds: int = 300,
    project_root: Path | None = None,
    min_content_length: int = 0,
    existing_content_length: int = 0,
) -> PlanResolution | None:
    """Resolve plan file path and content using multiple strategies.

    Strategies are tried in order until one succeeds:

    1. **known_plan_file_path** — direct file path from an existing plan
       batch (set via Read/Edit/Write tool detection).
    2. **candidate_paths** — file paths from batch activities, filtered
       through :func:`detect_plan` to confirm they are plan files.
    3. **transcript_path** — parse a transcript JSONL for
       ``<code_selection path="file://...">`` references (Cursor attaches
       plan files this way).
    4. **Filesystem scan** — search plan directories for recently-modified
       files within *max_age_seconds*.

    Content filtering (applied to every strategy):

    - *min_content_length*: skip files smaller than this (0 = no minimum).
    - *existing_content_length*: only accept if content is > 2x this value.

    Args:
        known_plan_file_path: A file path already known to be a plan.
        candidate_paths: File paths to check via ``detect_plan()``.
        transcript_path: Path to a JSONL transcript to parse.
        agent_type: Restrict filesystem scan to this agent.
        max_age_seconds: Age window for the filesystem scan.
        project_root: For resolving relative paths.
        min_content_length: Minimum content length to accept.
        existing_content_length: Existing content length for 2x comparison.

    Returns:
        :class:`PlanResolution` or ``None`` if no suitable plan found.
    """
    # Strategy 1: Known plan file path (from existing batch)
    if known_plan_file_path:
        content = _read_plan_file(known_plan_file_path, project_root)
        if content and _content_passes_threshold(
            content, min_content_length, existing_content_length
        ):
            logger.info(
                "Resolved plan from known path: %s (%d chars)",
                known_plan_file_path,
                len(content),
            )
            return PlanResolution(
                file_path=known_plan_file_path,
                content=content,
                strategy="known_path",
            )

    # Strategy 2: Candidate paths from batch activities
    if candidate_paths:
        for cpath in candidate_paths:
            detection = detect_plan(cpath)
            if detection.is_plan:
                content = _read_plan_file(cpath, project_root)
                if content and _content_passes_threshold(
                    content, min_content_length, existing_content_length
                ):
                    logger.info(
                        "Resolved plan from activity path: %s (%d chars)", cpath, len(content)
                    )
                    return PlanResolution(file_path=cpath, content=content, strategy="candidate")

    # Strategy 3: Parse transcript for attached plan files
    if transcript_path:
        try:
            from open_agent_kit.features.codebase_intelligence.transcript import (
                extract_attached_file_paths,
            )

            attached_paths = extract_attached_file_paths(transcript_path)
            for attached_path in reversed(attached_paths):
                detection = detect_plan(attached_path)
                if detection.is_plan:
                    content = _read_plan_file(attached_path, project_root)
                    if content and _content_passes_threshold(
                        content, min_content_length, existing_content_length
                    ):
                        logger.info(
                            "Resolved plan from transcript: %s (%d chars)",
                            attached_path,
                            len(content),
                        )
                        return PlanResolution(
                            file_path=attached_path, content=content, strategy="transcript"
                        )
        except Exception as e:
            logger.warning("Failed to extract plan from transcript: %s", e)

    # Strategy 4: Filesystem scan for recently-modified plan files
    try:
        recent = find_recent_plan_file(max_age_seconds=max_age_seconds, agent_type=agent_type)
        if recent and recent.plans_dir:
            content = _read_plan_file(recent.plans_dir, project_root)
            if content and _content_passes_threshold(
                content, min_content_length, existing_content_length
            ):
                logger.info(
                    "Resolved plan from filesystem: %s (%d chars, agent=%s)",
                    recent.plans_dir,
                    len(content),
                    recent.agent_type,
                )
                return PlanResolution(
                    file_path=recent.plans_dir, content=content, strategy="filesystem"
                )
    except Exception as e:
        logger.warning("Failed filesystem scan for plan: %s", e)

    return None


def detect_plan_in_response(
    response_summary: str,
    agent: str,
) -> bool:
    """Check if response text matches any plan heuristic pattern from the agent manifest.

    This is the 4th plan detection mechanism (heuristic), checked after the three
    deterministic mechanisms (file-based, tool-based, prefix-based). It enables
    plan detection for agents like VS Code Copilot that generate plans inline
    in response text rather than writing to disk or using specific tools.

    Args:
        response_summary: The captured agent response text.
        agent: Agent name (e.g., "vscode-copilot").

    Returns:
        True if any plan_response_patterns match the response head.
    """
    if not response_summary:
        return False

    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        manifest = agent_service.get_agent_manifest(agent)
        if not manifest or not manifest.ci:
            return False

        patterns = manifest.ci.plan_response_patterns
        if not patterns:
            return False

        # Only scan the beginning of the response for efficiency and precision
        head = response_summary[:PLAN_RESPONSE_SCAN_LENGTH]
        for pattern in patterns:
            if re.search(pattern, head, re.IGNORECASE | re.MULTILINE):
                return True
    except (OSError, ValueError, KeyError, AttributeError, re.error):
        logger.debug("Failed to check plan response patterns for agent %s", agent)

    return False
