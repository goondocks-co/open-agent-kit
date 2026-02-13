"""Transcript path resolution for codebase intelligence.

Dynamically discovers transcript storage patterns from agent manifests,
enabling automatic support for new agents without code changes.

Architecture:
- Uses AgentService to discover transcript configs from manifests
- No hardcoded agent paths or patterns
- New agents automatically supported when manifest includes ci.transcript config
- Singleton pattern for efficient caching of transcript patterns
"""

import logging
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentTranscriptConfig
    from open_agent_kit.services.agent_service import AgentService

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResolutionResult:
    """Result of transcript path resolution.

    Attributes:
        path: Full path to the transcript file, or None if not resolvable
        agent_type: The agent type that owns the transcript
        exists: Whether the transcript file exists on disk
    """

    path: Path | None
    agent_type: str | None = None
    exists: bool = False


class TranscriptResolver:
    """Resolves transcript file paths for AI coding agents.

    Uses AgentService to dynamically discover transcript patterns from manifests,
    making it automatically extensible when new agents are added.

    Supports different path encoding schemes:
    - slash-to-dash: /foo/bar -> -foo-bar (used by Claude Code)
    - url-encode: /foo/bar -> %2Ffoo%2Fbar
    - none: /foo/bar -> /foo/bar (path used as-is)

    Example:
        >>> resolver = TranscriptResolver(project_root=Path("/repo"))
        >>> result = resolver.resolve("abc-123", "claude", "/repo")
        >>> result.path
        PosixPath('/Users/user/.claude/projects/-repo/abc-123.jsonl')
        >>> result.exists
        True
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize transcript resolver.

        Args:
            project_root: Project root for AgentService (defaults to cwd)
        """
        self._project_root = project_root or Path.cwd()
        self._agent_service: AgentService | None = None  # Lazy initialization
        self._transcript_configs: dict[str, AgentTranscriptConfig] | None = None
        self._home_dir = Path.home()

    def _get_agent_service(self) -> "AgentService":
        """Lazy initialization of AgentService to avoid circular imports."""
        if self._agent_service is None:
            from open_agent_kit.services.agent_service import AgentService

            self._agent_service = AgentService(self._project_root)
        return self._agent_service

    def _get_transcript_configs(self) -> dict[str, "AgentTranscriptConfig"]:
        """Get transcript configurations from all agent manifests.

        Returns:
            Dict mapping agent type to transcript config.
            Only includes agents that have ci.transcript configured.
            Cached for performance after first call.
        """
        if self._transcript_configs is None:
            try:
                agent_service = self._get_agent_service()
                self._transcript_configs = agent_service.get_all_transcript_configs()
                logger.debug(
                    f"Loaded transcript configs for {len(self._transcript_configs)} agents",
                    extra={"agents": list(self._transcript_configs.keys())},
                )
            except (OSError, ValueError, KeyError, AttributeError) as e:
                logger.warning(f"Failed to load transcript configs: {e}")
                self._transcript_configs = {}
        return self._transcript_configs

    def _encode_project_path(self, project_root: str, encoding: str) -> str:
        """Encode project path according to the specified scheme.

        Args:
            project_root: Absolute project root path
            encoding: Encoding scheme ('slash-to-dash', 'slash-to-dash-no-leading', 'url-encode', 'none')

        Returns:
            Encoded project path string
        """
        if encoding == "slash-to-dash":
            # /Users/chris/Repos/project -> -Users-chris-Repos-project
            return project_root.replace("/", "-")
        elif encoding == "slash-to-dash-no-leading":
            # /Users/chris/Repos/project -> Users-chris-Repos-project (no leading dash)
            encoded = project_root.replace("/", "-")
            return encoded.lstrip("-")
        elif encoding == "url-encode":
            # /Users/chris/Repos/project -> %2FUsers%2Fchris%2FRepos%2Fproject
            return urllib.parse.quote(project_root, safe="")
        elif encoding == "none":
            return project_root
        else:
            logger.warning(f"Unknown project encoding '{encoding}', using slash-to-dash")
            return project_root.replace("/", "-")

    def resolve(
        self,
        session_id: str,
        agent_type: str | None = None,
        project_root: str | None = None,
    ) -> TranscriptResolutionResult:
        """Resolve the transcript file path for a session.

        Args:
            session_id: Session identifier (typically a UUID)
            agent_type: Agent type (e.g., 'claude', 'cursor'). If None, tries all agents.
            project_root: Absolute project root path. If None, uses resolver's project_root.

        Returns:
            TranscriptResolutionResult with path, agent_type, and exists flag.
        """
        if not session_id:
            return TranscriptResolutionResult(path=None)

        project = project_root or str(self._project_root.resolve())
        configs = self._get_transcript_configs()

        # If agent_type specified, try only that agent
        if agent_type and agent_type in configs:
            return self._resolve_for_agent(session_id, agent_type, project, configs[agent_type])

        # If agent_type specified but not in configs, return not found
        if agent_type:
            logger.debug(f"No transcript config for agent '{agent_type}'")
            return TranscriptResolutionResult(path=None, agent_type=agent_type)

        # Try all agents, return first that exists
        for agent, config in configs.items():
            result = self._resolve_for_agent(session_id, agent, project, config)
            if result.exists:
                return result

        # No existing transcript found, return first resolution attempt
        if configs:
            first_agent = next(iter(configs))
            return self._resolve_for_agent(session_id, first_agent, project, configs[first_agent])

        return TranscriptResolutionResult(path=None)

    def _resolve_for_agent(
        self,
        session_id: str,
        agent_type: str,
        project_root: str,
        config: "AgentTranscriptConfig",
    ) -> TranscriptResolutionResult:
        """Resolve transcript path for a specific agent.

        Args:
            session_id: Session identifier
            agent_type: Agent type name
            project_root: Absolute project root path
            config: Agent's transcript configuration

        Returns:
            TranscriptResolutionResult with resolved path
        """
        if not config.base_dir:
            return TranscriptResolutionResult(path=None, agent_type=agent_type)

        # Encode project path
        encoded_project = self._encode_project_path(project_root, config.project_encoding)

        # Build path from pattern
        relative_path = config.path_pattern.format(
            session_id=session_id,
            encoded_project=encoded_project,
        )

        # Construct full path (base_dir is relative to home)
        full_path = self._home_dir / config.base_dir / relative_path

        exists = full_path.exists() and full_path.is_file()

        if exists:
            logger.debug(
                f"Resolved transcript for {agent_type}: {full_path}",
                extra={"agent_type": agent_type, "session_id": session_id},
            )

        return TranscriptResolutionResult(
            path=full_path,
            agent_type=agent_type,
            exists=exists,
        )

    def get_supported_agents(self) -> list[str]:
        """Get list of agents with transcript support.

        Returns:
            List of agent type names that have transcript config
        """
        return list(self._get_transcript_configs().keys())


# Module-level singleton for convenience
_resolver: TranscriptResolver | None = None


def get_transcript_resolver(project_root: Path | None = None) -> TranscriptResolver:
    """Get or create the transcript resolver singleton.

    The singleton is lazily initialized on first access. If a different
    project_root is needed, create a new TranscriptResolver instance directly.

    Args:
        project_root: Project root (only used on first call)

    Returns:
        TranscriptResolver instance
    """
    global _resolver
    if _resolver is None:
        _resolver = TranscriptResolver(project_root)
    return _resolver


def reset_transcript_resolver() -> None:
    """Reset the transcript resolver singleton.

    Useful for testing or when project root changes.
    """
    global _resolver
    _resolver = None


def resolve_transcript_path(
    session_id: str,
    agent_type: str | None = None,
    project_root: str | None = None,
) -> Path | None:
    """Convenience function to resolve a transcript path.

    Args:
        session_id: Session identifier
        agent_type: Optional agent type to narrow resolution
        project_root: Optional project root path

    Returns:
        Path to transcript file if found, None otherwise
    """
    result = get_transcript_resolver().resolve(session_id, agent_type, project_root)
    return result.path if result.exists else None
