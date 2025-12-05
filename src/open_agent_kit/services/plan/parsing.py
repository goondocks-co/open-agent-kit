"""Parsing utilities for plan artifacts.

This module provides functions for parsing plan markdown files
and detecting changes in issue data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.models.issue import Issue


def parse_list_items(lines: list[str]) -> list[str]:
    """Parse list items from markdown lines.

    Args:
        lines: Lines of markdown

    Returns:
        List of item strings
    """
    items = []
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:])
        elif line.startswith("* "):
            items.append(line[2:])
    return items


def parse_plan_file(content: str) -> dict[str, Any]:
    """Parse plan.md content into structured data.

    This is a simple parser that extracts sections from markdown.
    The agent will typically maintain the structured format.

    Args:
        content: Markdown content

    Returns:
        Dictionary with parsed plan data
    """
    # Basic parsing - extract sections by headers
    data: dict[str, Any] = {
        "overview": "",
        "goals": [],
        "success_criteria": [],
        "constraints": [],
        "research_topics": [],
        "tasks": [],
    }

    # For now, just extract the overview from content between first header and next header
    lines = content.split("\n")
    current_section = None
    section_content: list[str] = []

    for line in lines:
        if line.startswith("## "):
            # Save previous section
            if current_section == "overview":
                data["overview"] = "\n".join(section_content).strip()
            elif current_section == "goals":
                data["goals"] = parse_list_items(section_content)
            elif current_section == "success criteria":
                data["success_criteria"] = parse_list_items(section_content)
            elif current_section == "constraints":
                data["constraints"] = parse_list_items(section_content)

            # Start new section
            current_section = line[3:].strip().lower()
            section_content = []
        elif current_section:
            section_content.append(line)

    # Handle last section
    if current_section == "overview":
        data["overview"] = "\n".join(section_content).strip()
    elif current_section == "goals":
        data["goals"] = parse_list_items(section_content)

    return data


def detect_issue_changes(old: Issue, new: Issue) -> dict[str, Any]:
    """Detect meaningful changes between old and new issue.

    Args:
        old: Previous issue state
        new: New issue state

    Returns:
        Dictionary of changes with categories:
        - title_changed: bool
        - description_changed: bool
        - state_changed: bool
        - acceptance_criteria_changed: bool
        - tags_changed: bool
        - relations_added: int
        - relations_removed: int
        - has_changes: bool (any changes detected)
    """
    changes: dict[str, Any] = {
        "title_changed": old.title != new.title,
        "description_changed": old.description != new.description,
        "state_changed": old.state != new.state,
        "acceptance_criteria_changed": old.acceptance_criteria != new.acceptance_criteria,
        "tags_changed": set(old.tags) != set(new.tags),
        "assigned_to_changed": old.assigned_to != new.assigned_to,
        "priority_changed": old.priority != new.priority,
        "milestone_changed": old.milestone != new.milestone,
    }

    # Check relations
    old_relation_ids = {r.identifier for r in old.relations if r.identifier}
    new_relation_ids = {r.identifier for r in new.relations if r.identifier}
    changes["relations_added"] = len(new_relation_ids - old_relation_ids)
    changes["relations_removed"] = len(old_relation_ids - new_relation_ids)

    # Check test steps for Test Cases
    if new.test_steps and old.test_steps:
        changes["test_steps_changed"] = len(old.test_steps) != len(new.test_steps)
    else:
        changes["test_steps_changed"] = bool(old.test_steps) != bool(new.test_steps)

    # Overall flag
    changes["has_changes"] = any(
        [
            changes["title_changed"],
            changes["description_changed"],
            changes["state_changed"],
            changes["acceptance_criteria_changed"],
            changes["tags_changed"],
            changes["assigned_to_changed"],
            changes["priority_changed"],
            changes["milestone_changed"],
            changes["relations_added"] > 0,
            changes["relations_removed"] > 0,
            changes["test_steps_changed"],
        ]
    )

    return changes


# Legacy aliases for backward compatibility
_parse_list_items = parse_list_items
_parse_plan_file = parse_plan_file
_detect_issue_changes = detect_issue_changes
