"""Prompt classification utilities for codebase intelligence.

Dynamically discovers prompt patterns from agent manifests,
enabling automatic support for new agents without code changes.

Classification categories:
- user: Regular user prompts (extract memories normally)
- agent_notification: Background agent completions (preserve but skip memories)
- plan: Plan execution prompts (auto-injected by plan mode)
- system: System messages (skip memory extraction)

Architecture:
- Uses AgentService to discover plan execution prefixes from manifests
- Uses constants for internal message prefixes (task-notification, system)
- No hardcoded agent lists - new agents automatically supported
- Singleton pattern for efficient caching of patterns
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    INTERNAL_MESSAGE_PREFIXES,
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_USER,
)

if TYPE_CHECKING:
    from open_agent_kit.services.agent_service import AgentService

logger = logging.getLogger(__name__)


@dataclass
class PromptClassificationResult:
    """Result of prompt classification.

    Attributes:
        source_type: The classified source type (user, agent_notification, plan, system)
        agent_type: The agent type that matched (e.g., 'claude') - only for plan source
        matched_prefix: The prefix pattern that matched (for debugging)
    """

    source_type: str
    agent_type: str | None = None
    matched_prefix: str | None = None


class PromptClassifier:
    """Classifies prompts by source type across all supported AI coding agents.

    Uses AgentService to dynamically discover plan execution prefixes from manifests,
    making it automatically extensible when new agents are added.

    Classification priority:
    1. Internal message prefixes (task-notification, system) -> agent_notification/system
    2. Plan execution prefixes (from agent manifests) -> plan
    3. Default -> user

    Example:
        >>> classifier = PromptClassifier(project_root=Path("/repo"))
        >>> result = classifier.classify("Implement the following plan:\\n\\n# Feature X")
        >>> result.source_type
        'plan'
        >>> result.agent_type
        'claude'
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize prompt classifier.

        Args:
            project_root: Project root for AgentService (defaults to cwd)
        """
        self._project_root = project_root or Path.cwd()
        self._agent_service: AgentService | None = None  # Lazy initialization
        self._plan_execution_patterns: dict[str, str] | None = None

    def _get_agent_service(self) -> "AgentService":
        """Lazy initialization of AgentService to avoid circular imports."""
        if self._agent_service is None:
            from open_agent_kit.services.agent_service import AgentService

            self._agent_service = AgentService(self._project_root)
        return self._agent_service

    def _get_plan_execution_patterns(self) -> dict[str, str]:
        """Get plan execution prefix patterns from all agent manifests.

        Returns:
            Dict mapping plan execution prefix to agent type.
            Example: {'Implement the following plan:': 'claude'}

        Cached for performance after first call.
        """
        if self._plan_execution_patterns is None:
            self._plan_execution_patterns = {}
            try:
                agent_service = self._get_agent_service()
                prefixes = agent_service.get_all_plan_execution_prefixes()
                for agent_type, prefix in prefixes.items():
                    self._plan_execution_patterns[prefix] = agent_type
                logger.debug(
                    f"Loaded plan execution patterns for {len(self._plan_execution_patterns)} agents",
                    extra={"agents": list(self._plan_execution_patterns.values())},
                )
            except Exception as e:
                logger.warning(f"Failed to load plan execution patterns: {e}")
                self._plan_execution_patterns = {}
        return self._plan_execution_patterns

    def classify(self, prompt: str | None) -> PromptClassificationResult:
        """Classify a prompt by its source type.

        Classification priority:
        1. Empty/None prompt -> user (default)
        2. Internal message prefixes -> agent_notification or system
        3. Plan execution prefixes (from manifests) -> plan
        4. Default -> user

        Args:
            prompt: The prompt text to classify (can be None)

        Returns:
            PromptClassificationResult with source_type, agent_type, and matched_prefix
        """
        if not prompt:
            return PromptClassificationResult(source_type=PROMPT_SOURCE_USER)

        prompt_stripped = prompt.strip()

        # Check internal message prefixes first (task-notification, system)
        for prefix in INTERNAL_MESSAGE_PREFIXES:
            if prompt_stripped.startswith(prefix):
                source_type = (
                    PROMPT_SOURCE_AGENT if prefix == "<task-notification>" else PROMPT_SOURCE_SYSTEM
                )
                logger.debug(
                    f"Classified prompt as {source_type}",
                    extra={
                        "source_type": source_type,
                        "matched_prefix": prefix,
                        "prompt_preview": prompt_stripped[:50],
                    },
                )
                return PromptClassificationResult(
                    source_type=source_type,
                    matched_prefix=prefix,
                )

        # Check plan execution prefixes (from agent manifests)
        plan_patterns = self._get_plan_execution_patterns()
        for prefix, agent_type in plan_patterns.items():
            if prompt_stripped.startswith(prefix):
                logger.info(
                    f"Classified prompt as plan execution for {agent_type}",
                    extra={
                        "source_type": PROMPT_SOURCE_PLAN,
                        "agent_type": agent_type,
                        "matched_prefix": prefix,
                        "prompt_length": len(prompt),
                    },
                )
                return PromptClassificationResult(
                    source_type=PROMPT_SOURCE_PLAN,
                    agent_type=agent_type,
                    matched_prefix=prefix,
                )

        # Default to user prompt
        return PromptClassificationResult(source_type=PROMPT_SOURCE_USER)

    def is_plan_execution(self, prompt: str | None) -> bool:
        """Check if a prompt is a plan execution prompt.

        Convenience method for simple boolean checks.

        Args:
            prompt: The prompt text to check

        Returns:
            True if prompt is auto-injected plan execution
        """
        return self.classify(prompt).source_type == PROMPT_SOURCE_PLAN

    def is_internal_message(self, prompt: str | None) -> bool:
        """Check if a prompt is an internal message (agent notification or system).

        Convenience method for simple boolean checks.

        Args:
            prompt: The prompt text to check

        Returns:
            True if prompt is from background agent or system
        """
        source_type = self.classify(prompt).source_type
        return source_type in (PROMPT_SOURCE_AGENT, PROMPT_SOURCE_SYSTEM)

    def get_supported_agents(self) -> list[str]:
        """Get list of agents with plan execution prefix configured.

        Returns:
            List of agent type names that have plan_execution_prefix defined
        """
        return list(self._get_plan_execution_patterns().values())


# Module-level singleton for convenience
_classifier: PromptClassifier | None = None


def get_prompt_classifier(project_root: Path | None = None) -> PromptClassifier:
    """Get or create the prompt classifier singleton.

    The singleton is lazily initialized on first access. If a different
    project_root is needed, create a new PromptClassifier instance directly.

    Args:
        project_root: Project root (only used on first call)

    Returns:
        PromptClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = PromptClassifier(project_root)
    return _classifier


def reset_prompt_classifier() -> None:
    """Reset the prompt classifier singleton.

    Useful for testing or when project root changes.
    """
    global _classifier
    _classifier = None


def classify_prompt(prompt: str | None) -> PromptClassificationResult:
    """Convenience function to classify a prompt with full details.

    Args:
        prompt: The prompt text to classify

    Returns:
        PromptClassificationResult with source type and agent info
    """
    return get_prompt_classifier().classify(prompt)


def is_plan_execution(prompt: str | None) -> bool:
    """Convenience function to check if prompt is plan execution.

    Args:
        prompt: The prompt text to check

    Returns:
        True if prompt is auto-injected plan execution
    """
    return get_prompt_classifier().is_plan_execution(prompt)


def is_internal_message(prompt: str | None) -> bool:
    """Convenience function to check if prompt is internal message.

    Args:
        prompt: The prompt text to check

    Returns:
        True if prompt is from background agent or system
    """
    return get_prompt_classifier().is_internal_message(prompt)
