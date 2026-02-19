"""Governance engine: rule evaluation for agent tool calls.

Evaluates tool calls against configured governance rules and returns
decisions (allow, deny, warn, observe). In observe mode, deny/warn
are downgraded to observe for safe rollout.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    GOVERNANCE_ACTION_ALLOW,
    GOVERNANCE_ACTION_DENY,
    GOVERNANCE_ACTION_OBSERVE,
    GOVERNANCE_ACTION_WARN,
    GOVERNANCE_AGENT_TOOLS,
    GOVERNANCE_FILESYSTEM_TOOLS,
    GOVERNANCE_MODE_OBSERVE,
    GOVERNANCE_NETWORK_TOOLS,
    GOVERNANCE_SHELL_TOOLS,
    GOVERNANCE_TOOL_CATEGORY_AGENT,
    GOVERNANCE_TOOL_CATEGORY_FILESYSTEM,
    GOVERNANCE_TOOL_CATEGORY_NETWORK,
    GOVERNANCE_TOOL_CATEGORY_OTHER,
    GOVERNANCE_TOOL_CATEGORY_SHELL,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.config import (
        GovernanceConfig,
        GovernanceRule,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GovernanceDecision:
    """Result of evaluating a tool call against governance rules.

    Attributes:
        action: The governance action (allow, deny, warn, observe).
        rule_id: ID of the matched rule, or empty if default allow.
        rule_description: Description of the matched rule.
        reason: Human-readable reason for this decision.
        matched_pattern: The pattern that matched (for audit trail).
        tool_category: Categorization of the tool (filesystem, shell, etc.).
        message: Message to show to the agent on deny/warn.
    """

    action: str = GOVERNANCE_ACTION_ALLOW
    rule_id: str = ""
    rule_description: str = ""
    reason: str = ""
    matched_pattern: str = ""
    tool_category: str = GOVERNANCE_TOOL_CATEGORY_OTHER
    message: str = ""


@dataclass
class _CompiledRule:
    """Internal representation of a governance rule with pre-compiled regex."""

    rule: GovernanceRule
    compiled_pattern: re.Pattern[str] | None = None


class GovernanceEngine:
    """Evaluates tool calls against governance policy rules.

    Pre-compiles regex patterns at construction time for efficient matching.
    Thread-safe for concurrent evaluation (read-only after init).
    """

    def __init__(self, config: GovernanceConfig) -> None:
        self._config = config
        self._compiled_rules: list[_CompiledRule] = []

        for rule in config.rules:
            if not rule.enabled:
                continue
            compiled = None
            if rule.pattern:
                try:
                    compiled = re.compile(rule.pattern)
                except re.error as e:
                    logger.warning(
                        "Skipping rule %s: invalid regex %r: %s",
                        rule.id,
                        rule.pattern,
                        e,
                    )
                    continue
            self._compiled_rules.append(_CompiledRule(rule=rule, compiled_pattern=compiled))

    def evaluate(self, tool_name: str, tool_input: dict[str, object] | str) -> GovernanceDecision:
        """Evaluate a tool call against all enabled governance rules.

        Rules are evaluated in order; the first matching rule wins.
        In observe mode, deny/warn actions are downgraded to observe.

        Args:
            tool_name: Name of the tool being called (e.g., "Bash", "Write").
            tool_input: Tool input as dict or JSON string.

        Returns:
            GovernanceDecision with the evaluation result.
        """
        category = self.categorize_tool(tool_name)

        # Serialize tool_input to string for regex matching
        if isinstance(tool_input, dict):
            try:
                input_str = json.dumps(tool_input, default=str)
            except (TypeError, ValueError):
                input_str = str(tool_input)
        else:
            input_str = str(tool_input)

        for compiled in self._compiled_rules:
            rule = compiled.rule
            if not _rule_matches(rule, compiled.compiled_pattern, tool_name, input_str):
                continue

            action = rule.action
            matched = _describe_match(rule, tool_name)

            # In observe mode, downgrade deny/warn to observe
            if self._config.enforcement_mode == GOVERNANCE_MODE_OBSERVE:
                if action in (GOVERNANCE_ACTION_DENY, GOVERNANCE_ACTION_WARN):
                    reason = (
                        f"Rule '{rule.id}' would {action} but enforcement_mode=observe; "
                        f"downgraded to observe"
                    )
                    return GovernanceDecision(
                        action=GOVERNANCE_ACTION_OBSERVE,
                        rule_id=rule.id,
                        rule_description=rule.description,
                        reason=reason,
                        matched_pattern=matched,
                        tool_category=category,
                        message=rule.message,
                    )

            return GovernanceDecision(
                action=action,
                rule_id=rule.id,
                rule_description=rule.description,
                reason=(
                    f"Matched rule '{rule.id}': {rule.description}"
                    if rule.description
                    else f"Matched rule '{rule.id}'"
                ),
                matched_pattern=matched,
                tool_category=category,
                message=rule.message,
            )

        # No rule matched -> allow
        return GovernanceDecision(
            action=GOVERNANCE_ACTION_ALLOW,
            reason="No rule matched",
            tool_category=category,
        )

    @staticmethod
    def categorize_tool(tool_name: str) -> str:
        """Categorize a tool by name using the constants frozensets.

        Args:
            tool_name: Tool name (e.g., "Bash", "Read").

        Returns:
            Tool category string.
        """
        if tool_name in GOVERNANCE_FILESYSTEM_TOOLS:
            return GOVERNANCE_TOOL_CATEGORY_FILESYSTEM
        if tool_name in GOVERNANCE_SHELL_TOOLS:
            return GOVERNANCE_TOOL_CATEGORY_SHELL
        if tool_name in GOVERNANCE_NETWORK_TOOLS:
            return GOVERNANCE_TOOL_CATEGORY_NETWORK
        if tool_name in GOVERNANCE_AGENT_TOOLS:
            return GOVERNANCE_TOOL_CATEGORY_AGENT
        return GOVERNANCE_TOOL_CATEGORY_OTHER


def _rule_matches(
    rule: GovernanceRule,
    compiled_pattern: re.Pattern[str] | None,
    tool_name: str,
    input_str: str,
) -> bool:
    """Check if a rule matches a tool call (AND semantics).

    All present conditions must match:
    - tool: fnmatch against tool_name
    - pattern: regex search against serialized tool_input
    - path_pattern: fnmatch against file_path extracted from tool_input

    Args:
        rule: The governance rule to check.
        compiled_pattern: Pre-compiled regex for rule.pattern (or None).
        tool_name: Tool name being called.
        input_str: Serialized tool input string.

    Returns:
        True if all present conditions match.
    """
    # Tool match (fnmatch allows "*" wildcard)
    if rule.tool != "*" and not fnmatch.fnmatch(tool_name, rule.tool):
        return False

    # Pattern match (regex on serialized input)
    if compiled_pattern is not None:
        if not compiled_pattern.search(input_str):
            return False

    # Path pattern match (fnmatch on file_path from input)
    if rule.path_pattern:
        # Try to extract file_path from input JSON
        file_path = _extract_file_path(input_str)
        if file_path is None:
            return False
        if not fnmatch.fnmatch(file_path, rule.path_pattern):
            return False

    return True


def _extract_file_path(input_str: str) -> str | None:
    """Extract file_path from serialized tool input.

    Looks for common field names: file_path, path, command (for Bash).

    Args:
        input_str: Serialized tool input JSON.

    Returns:
        Extracted file path, or None if not found.
    """
    try:
        data = json.loads(input_str)
        if not isinstance(data, dict):
            return None
        # Try common field names
        for key in ("file_path", "path", "filename"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _describe_match(rule: GovernanceRule, tool_name: str) -> str:
    """Build a human-readable description of what matched.

    Args:
        rule: The matched rule.
        tool_name: Tool that was matched.

    Returns:
        Description string for audit trail.
    """
    parts = [f"tool={tool_name}"]
    if rule.pattern:
        parts.append(f"pattern={rule.pattern!r}")
    if rule.path_pattern:
        parts.append(f"path_pattern={rule.path_pattern!r}")
    return ", ".join(parts)
