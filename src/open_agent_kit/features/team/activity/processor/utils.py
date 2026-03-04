"""Shared utilities for activity processor modules."""

from __future__ import annotations

from open_agent_kit.features.team.constants import RECOVERY_BATCH_PROMPT


def is_recovery_prompt(prompt: str | None) -> bool:
    """Check if a prompt is a continuation placeholder (from session transitions)."""
    if not prompt:
        return False
    return prompt.startswith("[Recovery batch") or prompt == RECOVERY_BATCH_PROMPT
