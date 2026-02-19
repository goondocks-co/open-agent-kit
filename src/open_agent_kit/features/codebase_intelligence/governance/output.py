"""Governance output formatting: manifest-driven deny response construction.

Transforms governance deny decisions into agent-specific hook response
formats based on the agent's manifest governance configuration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    GOVERNANCE_ACTION_DENY,
    HOOK_EVENT_PRE_TOOL_USE,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.governance.engine import (
        GovernanceDecision,
    )

logger = logging.getLogger(__name__)

# Deny format identifiers (from AgentGovernanceConfig.deny_format)
DENY_FORMAT_HOOK_SPECIFIC = "hookSpecificOutput"
DENY_FORMAT_CURSOR_PERMISSION = "cursor_permission"


def apply_governance_decision(
    hook_output: dict[str, Any],
    decision: GovernanceDecision,
    agent: str,
    hook_event_name: str,
) -> dict[str, Any]:
    """Apply a governance decision to a hook response.

    Only modifies the response for deny decisions on PreToolUse events.
    Reads the agent manifest to determine the correct deny format.

    Args:
        hook_output: The hook response dict being built.
        decision: The governance evaluation result.
        agent: Agent name (e.g., "claude", "cursor").
        hook_event_name: Hook event name (e.g., "PreToolUse").

    Returns:
        Modified hook_output dict (may be mutated in place).
    """
    # Only act on deny for PreToolUse
    if decision.action != GOVERNANCE_ACTION_DENY:
        return hook_output
    # hook_event_name arrives as PascalCase from agents (e.g. "PreToolUse")
    # but HOOK_EVENT_PRE_TOOL_USE is kebab-case ("pre-tool-use").
    # Normalize both sides for a robust comparison.
    normalised = hook_event_name.lower().replace("-", "").replace("_", "")
    if normalised != HOOK_EVENT_PRE_TOOL_USE.lower().replace("-", ""):
        return hook_output

    # Load agent manifest to determine deny format
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        manifest = agent_service.get_agent_manifest(agent)
        gov_config = manifest.governance
    except (ValueError, AttributeError) as e:
        logger.warning(
            "Cannot determine deny format for agent %s: %s. " "Falling back to hookSpecificOutput.",
            agent,
            e,
        )
        return _apply_hook_specific_deny(hook_output, decision)

    if not gov_config.supports_deny:
        logger.debug(
            "Agent %s does not support deny; governance deny logged but not enforced.",
            agent,
        )
        return hook_output

    deny_format = gov_config.deny_format

    if deny_format == DENY_FORMAT_CURSOR_PERMISSION:
        return _apply_cursor_deny(hook_output, decision)

    # Default to hookSpecificOutput (Claude, Copilot, and fallback)
    return _apply_hook_specific_deny(hook_output, decision)


def _apply_hook_specific_deny(
    hook_output: dict[str, Any],
    decision: GovernanceDecision,
) -> dict[str, Any]:
    """Apply deny via hookSpecificOutput (Claude Code / VS Code Copilot format).

    Sets permissionDecision and permissionDecisionReason in the
    hookSpecificOutput envelope.

    Args:
        hook_output: The hook response dict.
        decision: The governance deny decision.

    Returns:
        Modified hook_output.
    """
    reason = (
        decision.message or decision.reason or f"Blocked by governance rule: {decision.rule_id}"
    )

    if "hookSpecificOutput" not in hook_output:
        hook_output["hookSpecificOutput"] = {}

    hook_output["hookSpecificOutput"]["permissionDecision"] = "deny"
    hook_output["hookSpecificOutput"]["permissionDecisionReason"] = reason

    return hook_output


def _apply_cursor_deny(
    hook_output: dict[str, Any],
    decision: GovernanceDecision,
) -> dict[str, Any]:
    """Apply deny via Cursor permission format.

    Sets continue=False and permission-related fields in the response.

    Args:
        hook_output: The hook response dict.
        decision: The governance deny decision.

    Returns:
        Modified hook_output.
    """
    reason = (
        decision.message or decision.reason or f"Blocked by governance rule: {decision.rule_id}"
    )

    hook_output["continue"] = False
    hook_output["permission"] = "deny"
    hook_output["userMessage"] = reason
    hook_output["agentMessage"] = (
        f"Tool call blocked by governance policy (rule: {decision.rule_id}). " f"{reason}"
    )

    return hook_output
