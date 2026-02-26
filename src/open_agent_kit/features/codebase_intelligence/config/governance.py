"""Governance configuration for Codebase Intelligence."""

import re
from dataclasses import dataclass, field
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    GOVERNANCE_ACTION_OBSERVE,
    GOVERNANCE_ACTIONS,
    GOVERNANCE_MODE_OBSERVE,
    GOVERNANCE_MODES,
    GOVERNANCE_RETENTION_DAYS_DEFAULT,
    GOVERNANCE_RETENTION_DAYS_MAX,
    GOVERNANCE_RETENTION_DAYS_MIN,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)


@dataclass
class GovernanceRule:
    """A single governance policy rule.

    Attributes:
        id: Unique rule identifier (e.g., "no-env-edit").
        description: Human-readable description.
        enabled: Whether this rule is active.
        tool: Tool name or glob pattern (e.g., "Bash", "Write", "*").
        pattern: Regex for tool_input matching.
        path_pattern: fnmatch pattern for file path matching.
        action: Action when matched: allow | deny | warn | observe.
        message: Message shown to agent on deny/warn.
    """

    id: str = ""
    description: str = ""
    enabled: bool = True
    tool: str = "*"
    pattern: str = ""
    path_pattern: str = ""
    action: str = GOVERNANCE_ACTION_OBSERVE
    message: str = ""

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.id:
            raise ValidationError(
                "Rule id is required", field="id", value=self.id, expected="non-empty string"
            )
        if self.action not in GOVERNANCE_ACTIONS:
            raise ValidationError(
                f"Invalid governance action: {self.action}",
                field="action",
                value=self.action,
                expected=f"one of {GOVERNANCE_ACTIONS}",
            )
        if self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValidationError(
                    f"Invalid regex pattern: {e}",
                    field="pattern",
                    value=self.pattern,
                    expected="valid regex",
                ) from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GovernanceRule":
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            tool=data.get("tool", "*"),
            pattern=data.get("pattern", ""),
            path_pattern=data.get("path_pattern", ""),
            action=data.get("action", GOVERNANCE_ACTION_OBSERVE),
            message=data.get("message", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "enabled": self.enabled,
            "tool": self.tool,
            "pattern": self.pattern,
            "path_pattern": self.path_pattern,
            "action": self.action,
            "message": self.message,
        }


@dataclass
class GovernanceConfig:
    """Configuration for agent governance (observability and enforcement).

    Attributes:
        enabled: Whether governance evaluation is active.
        enforcement_mode: "observe" (log only) or "enforce" (can deny).
        log_allowed: If true, log allow decisions too (verbose).
        retention_days: Number of days to keep audit events before pruning.
        rules: List of governance policy rules.
    """

    enabled: bool = False
    enforcement_mode: str = GOVERNANCE_MODE_OBSERVE
    log_allowed: bool = False
    retention_days: int = GOVERNANCE_RETENTION_DAYS_DEFAULT
    rules: list[GovernanceRule] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.enforcement_mode not in GOVERNANCE_MODES:
            raise ValidationError(
                f"Invalid enforcement mode: {self.enforcement_mode}",
                field="enforcement_mode",
                value=self.enforcement_mode,
                expected=f"one of {GOVERNANCE_MODES}",
            )
        # Validate retention_days bounds
        if not (
            GOVERNANCE_RETENTION_DAYS_MIN <= self.retention_days <= GOVERNANCE_RETENTION_DAYS_MAX
        ):
            raise ValidationError(
                f"retention_days must be between {GOVERNANCE_RETENTION_DAYS_MIN} "
                f"and {GOVERNANCE_RETENTION_DAYS_MAX}",
                field="retention_days",
                value=self.retention_days,
                expected=f">= {GOVERNANCE_RETENTION_DAYS_MIN} and <= {GOVERNANCE_RETENTION_DAYS_MAX}",
            )
        # Validate rule IDs are unique
        rule_ids = [r.id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            dupes = [rid for rid in rule_ids if rule_ids.count(rid) > 1]
            raise ValidationError(
                f"Duplicate rule IDs: {set(dupes)}",
                field="rules",
                value=dupes,
                expected="unique rule IDs",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GovernanceConfig":
        rules_data = data.get("rules", [])
        rules = [GovernanceRule.from_dict(r) if isinstance(r, dict) else r for r in rules_data]
        return cls(
            enabled=data.get("enabled", False),
            enforcement_mode=data.get("enforcement_mode", GOVERNANCE_MODE_OBSERVE),
            log_allowed=data.get("log_allowed", False),
            retention_days=data.get("retention_days", GOVERNANCE_RETENTION_DAYS_DEFAULT),
            rules=rules,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "enforcement_mode": self.enforcement_mode,
            "log_allowed": self.log_allowed,
            "retention_days": self.retention_days,
            "rules": [r.to_dict() for r in self.rules],
        }
