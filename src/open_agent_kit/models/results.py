"""Result types for commands and services.

This module provides TypedDict definitions for command and service results,
ensuring type-safe dictionary structures with IDE autocompletion support.
"""

from typing import TypedDict


class DaemonStatus(TypedDict, total=False):
    """Status of the CI daemon.

    All fields are optional to support partial status updates.
    """

    running: bool
    port: int
    pid: int
    indexed_files: int
    memory_entries: int


class SearchResult(TypedDict):
    """Result from code/memory search.

    Represents a single search result with location and relevance information.
    """

    type: str  # "code" or "memory"
    content: str
    file_path: str | None
    line_number: int | None
    score: float


class FeatureInstallResult(TypedDict):
    """Result of feature installation.

    Tracks what was successfully installed and any errors encountered.
    """

    success: bool
    feature: str
    commands_installed: list[str]
    skills_installed: list[str]
    hooks_triggered: list[str]
    errors: list[str]


class BatchOperationResult(TypedDict):
    """Result of a batch operation.

    Tracks which items succeeded and which failed with error messages.
    """

    succeeded: list[str]
    failed: list[tuple[str, str]]  # (item, error_message)


class UpgradePlanData(TypedDict, total=False):
    """Typed structure for upgrade plan dictionary.

    Represents the complete upgrade plan with all possible categories.
    Uses total=False since not all categories may be present in every plan.
    """

    commands: list[str]
    templates: list[str]
    obsolete_templates: list[str]
    agent_settings: list[str]
    hooks: list[str]
    mcp_servers: list[str]
    gitignore: list[str]
    migrations: list[str]
    structural_repairs: list[str]
    version_outdated: bool
    skills: dict[str, list[str]]
