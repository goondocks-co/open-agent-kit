"""Markdown rendering helpers for plan artifacts.

This module provides functions for rendering plan content to markdown format,
including plan files, research findings, tasks, and issue summaries.
All functions are pure and have no side effects.
"""

from __future__ import annotations

import html as html_module
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.models.issue import Issue
    from open_agent_kit.models.plan import Plan, PlanTask, ResearchFinding


def render_plan_file(plan: Plan) -> str:
    """Render plan.md content.

    Args:
        plan: Plan object

    Returns:
        Markdown content
    """
    sections = []

    # Header
    sections.append(f"# {plan.manifest.display_name}\n")
    sections.append(f"**Status:** {plan.manifest.status.value}  \n")
    sections.append(f"**Created:** {plan.manifest.created_at}  \n")
    if plan.manifest.branch_name:
        sections.append(f"**Branch:** `{plan.manifest.branch_name}`  \n")
    sections.append("\n")

    # Overview
    sections.append("## Overview\n\n")
    sections.append(f"{plan.overview or 'Pending'}\n\n")

    # Goals
    sections.append("## Goals\n\n")
    if plan.goals:
        for goal in plan.goals:
            sections.append(f"- {goal}\n")
    else:
        sections.append("- Pending\n")
    sections.append("\n")

    # Success Criteria
    sections.append("## Success Criteria\n\n")
    if plan.success_criteria:
        for criterion in plan.success_criteria:
            sections.append(f"- {criterion}\n")
    else:
        sections.append("- Pending\n")
    sections.append("\n")

    # Scope
    if plan.scope:
        sections.append("## Scope\n\n")
        sections.append(f"{plan.scope}\n\n")

    # Constraints
    if plan.constraints:
        sections.append("## Constraints\n\n")
        for constraint in plan.constraints:
            sections.append(f"- {constraint}\n")
        sections.append("\n")

    # Research Topics
    sections.append("## Research Topics\n\n")
    if plan.research_topics:
        for topic in plan.research_topics:
            status_emoji = get_status_emoji(topic.status)
            sections.append(f"### {status_emoji} {topic.title}\n")
            sections.append(f"**Slug:** `{topic.slug}`  \n")
            sections.append(f"**Priority:** {topic.priority}  \n")
            sections.append(f"**Status:** {topic.status}  \n\n")
            sections.append(f"{topic.description}\n\n")

            if topic.research_questions:
                sections.append("**Questions to answer:**\n")
                for q in topic.research_questions:
                    sections.append(f"- {q}\n")
                sections.append("\n")

            if topic.sources_to_check:
                sections.append("**Sources to check:**\n")
                for s in topic.sources_to_check:
                    sections.append(f"- {s}\n")
                sections.append("\n")

            if topic.findings_path:
                sections.append(f"**Findings:** [{topic.findings_path}]({topic.findings_path})\n\n")
    else:
        sections.append("No research topics defined yet.\n\n")

    return "".join(sections)


def render_research_findings(findings: ResearchFinding) -> str:
    """Render research findings to markdown.

    Args:
        findings: ResearchFinding object

    Returns:
        Markdown content
    """
    sections = []

    sections.append(f"# Research: {findings.topic_slug}\n\n")

    if findings.research_date:
        sections.append(f"**Date:** {findings.research_date}  \n\n")

    sections.append("## Summary\n\n")
    sections.append(f"{findings.summary}\n\n")

    if findings.key_insights:
        sections.append("## Key Insights\n\n")
        for insight in findings.key_insights:
            sections.append(f"- {insight}\n")
        sections.append("\n")

    if findings.recommendations:
        sections.append("## Recommendations\n\n")
        for rec in findings.recommendations:
            sections.append(f"- {rec}\n")
        sections.append("\n")

    if findings.trade_offs:
        sections.append("## Trade-offs\n\n")
        for trade_off in findings.trade_offs:
            sections.append(f"- {trade_off}\n")
        sections.append("\n")

    if findings.sources:
        sections.append("## Sources\n\n")
        for source in findings.sources:
            sections.append(f"- {source}\n")
        sections.append("\n")

    if findings.researcher_notes:
        sections.append("## Notes\n\n")
        sections.append(f"{findings.researcher_notes}\n")

    return "".join(sections)


def render_tasks(plan_name: str, tasks: list[PlanTask]) -> str:
    """Render tasks to markdown.

    Args:
        plan_name: Display name of the plan
        tasks: List of PlanTask objects

    Returns:
        Markdown content
    """
    sections = []

    sections.append(f"# Tasks: {plan_name}\n\n")

    if not tasks:
        sections.append("No tasks generated yet.\n")
        return "".join(sections)

    # Group tasks by type
    epics = [t for t in tasks if t.task_type.value == "epic"]
    stories = [t for t in tasks if t.task_type.value == "story"]
    task_items = [t for t in tasks if t.task_type.value == "task"]
    subtasks = [t for t in tasks if t.task_type.value == "subtask"]

    def render_task(task: PlanTask, level: int = 2) -> str:
        """Render a single task."""
        header = "#" * level
        parts = []

        # Header with priority badge
        priority_badge = f"[{task.priority.value.upper()}]"
        parts.append(f"{header} {task.id}: {task.title} {priority_badge}\n\n")

        # Metadata
        parts.append(f"**Type:** {task.task_type.value}  \n")
        if task.estimated_effort:
            parts.append(f"**Effort:** {task.estimated_effort}  \n")
        if task.dependencies:
            parts.append(f"**Dependencies:** {', '.join(task.dependencies)}  \n")
        if task.issue_link:
            parts.append(f"**Issue:** [{task.issue_id}]({task.issue_link})  \n")
        parts.append("\n")

        # Description
        parts.append(f"{task.description}\n\n")

        # Acceptance Criteria
        if task.acceptance_criteria:
            parts.append("**Acceptance Criteria:**\n")
            for criterion in task.acceptance_criteria:
                parts.append(f"- [ ] {criterion}\n")
            parts.append("\n")

        # Tags
        if task.tags:
            parts.append(f"**Tags:** {', '.join(f'`{t}`' for t in task.tags)}\n\n")

        return "".join(parts)

    # Render by type
    if epics:
        sections.append("## Epics\n\n")
        for task in epics:
            sections.append(render_task(task, 3))

    if stories:
        sections.append("## Stories\n\n")
        for task in stories:
            sections.append(render_task(task, 3))

    if task_items:
        sections.append("## Tasks\n\n")
        for task in task_items:
            sections.append(render_task(task, 3))

    if subtasks:
        sections.append("## Subtasks\n\n")
        for task in subtasks:
            sections.append(render_task(task, 3))

    return "".join(sections)


def get_status_emoji(status: str) -> str:
    """Get emoji for research status.

    Args:
        status: Status string

    Returns:
        Emoji character
    """
    return {
        "pending": "\u23f3",
        "in_progress": "\U0001f504",
        "completed": "\u2705",
        "skipped": "\u23ed\ufe0f",
    }.get(status, "\u2753")


def render_issue_summary(issue: Issue) -> str:
    """Render LLM-optimized markdown summary of issue context.

    This provides a clean, readable format optimized for LLM consumption,
    extracting key information from the issue and presenting it in
    a structured way that's easier to parse than raw JSON.

    Args:
        issue: Issue to summarize

    Returns:
        Markdown-formatted summary string
    """
    sections = []

    # Header with issue type
    issue_type = issue.issue_type or "Issue"
    sections.append(f"# {issue.identifier}: {issue.title}\n")
    sections.append(f"**Type:** {issue_type}  \n")
    sections.append(f"**State:** {issue.state or 'Unknown'}  \n")

    if issue.assigned_to:
        sections.append(f"**Assigned To:** {issue.assigned_to}  \n")

    if issue.priority:
        sections.append(f"**Priority:** {issue.priority}  \n")

    if issue.effort:
        sections.append(f"**Effort:** {issue.effort}  \n")

    if issue.area_path:
        sections.append(f"**Area:** {issue.area_path}  \n")

    if issue.iteration_path:
        sections.append(f"**Iteration:** {issue.iteration_path}  \n")

    # GitHub-specific fields
    if issue.milestone:
        sections.append(f"**Milestone:** {issue.milestone}  \n")

    if issue.comments_count is not None:
        sections.append(f"**Comments:** {issue.comments_count}  \n")

    if issue.created_at:
        created_date = format_timestamp(issue.created_at)
        sections.append(f"**Created:** {created_date}  \n")

    if issue.updated_at:
        updated_date = format_timestamp(issue.updated_at)
        sections.append(f"**Updated:** {updated_date}  \n")

    if issue.closed_at:
        closed_date = format_timestamp(issue.closed_at)
        sections.append(f"**Closed:** {closed_date}  \n")

    if issue.url:
        sections.append(f"**URL:** {issue.url}  \n")

    sections.append("\n")

    # Description (clean HTML if present)
    if issue.description:
        sections.append("## Description\n\n")
        clean_description = clean_html(issue.description)
        sections.append(f"{clean_description}\n\n")

    # Type-specific sections
    if issue_type == "Test Case" and issue.test_steps:
        sections.append("## Test Steps\n\n")
        for step in issue.test_steps:
            if step.shared_step_reference:
                sections.append(
                    f"**Step {step.step_number}:** [Shared Step #{step.shared_step_reference}]\n\n"
                )
            else:
                sections.append(f"**Step {step.step_number}:**\n")
                sections.append(f"- **Action:** {step.action}\n")
                if step.expected_result:
                    sections.append(f"- **Expected:** {step.expected_result}\n")
                sections.append("\n")

    if issue_type == "Bug" and issue.repro_steps:
        sections.append("## Reproduction Steps\n\n")
        for i, repro_step in enumerate(issue.repro_steps, 1):
            sections.append(f"{i}. {repro_step}\n")
        sections.append("\n")

    # Acceptance Criteria
    if issue.acceptance_criteria:
        sections.append("## Acceptance Criteria\n\n")
        for criterion in issue.acceptance_criteria:
            sections.append(f"- {criterion}\n")
        sections.append("\n")

    # Relations
    if issue.relations:
        sections.append("## Related Issues\n\n")
        # Group by relation type
        by_type: dict[str, list] = {}
        for relation in issue.relations:
            rel_type = relation.relation_type or "Related"
            # Simplify ADO relation names
            rel_type_display = simplify_relation_type(rel_type)
            by_type.setdefault(rel_type_display, []).append(relation)

        for rel_type, items in by_type.items():
            sections.append(f"### {rel_type}\n\n")
            for item in items:
                item_id = item.identifier or "Unknown"
                item_title = item.title or "Untitled"
                sections.append(f"- **{item_id}:** {item_title}\n")
            sections.append("\n")

    # Comments
    if issue.comments:
        sections.append("## Comments\n\n")
        for i, comment in enumerate(issue.comments, 1):
            # Format comment header with author and date
            header_parts = []
            if comment.created_by:
                header_parts.append(f"**{comment.created_by}**")
            if comment.created_date:
                # Extract just the date portion for readability
                date_str = (
                    comment.created_date.split("T")[0]
                    if "T" in comment.created_date
                    else comment.created_date
                )
                header_parts.append(f"({date_str})")

            if header_parts:
                sections.append(f"**Comment {i}** - {' '.join(header_parts)}:\n")
            else:
                sections.append(f"**Comment {i}**:\n")

            # Add comment text (clean HTML if present)
            clean_text = clean_html(comment.text) if comment.text else ""
            sections.append(f"> {clean_text}\n\n")

    # Tags
    if issue.tags:
        sections.append("## Tags\n\n")
        sections.append(", ".join(f"`{tag}`" for tag in issue.tags))
        sections.append("\n\n")

    return "".join(sections)


def render_issue_plan(issue: Issue, related_issues: list[Issue]) -> str:
    """Render plan.md content for issue-first plans.

    Args:
        issue: Main issue
        related_issues: Related issues for context

    Returns:
        Markdown content for plan.md
    """
    sections = []

    # Header
    sections.append(f"# Plan: {issue.title}\n\n")
    sections.append(f"**Issue:** {issue.identifier}  \n")
    sections.append(f"**Type:** {issue.issue_type or 'Unknown'}  \n")
    sections.append(f"**State:** {issue.state or 'Unknown'}  \n")
    if issue.url:
        sections.append(f"**URL:** {issue.url}  \n")
    sections.append("\n")

    # Overview from issue description
    sections.append("## Overview\n\n")
    if issue.description:
        clean_description = clean_html(issue.description)
        sections.append(f"{clean_description}\n\n")
    else:
        sections.append("No description provided.\n\n")

    # Acceptance Criteria
    sections.append("## Acceptance Criteria\n\n")
    if issue.acceptance_criteria:
        for criterion in issue.acceptance_criteria:
            sections.append(f"- [ ] {criterion}\n")
    else:
        sections.append("- [ ] To be defined\n")
    sections.append("\n")

    # Related Issues (Context)
    if related_issues:
        sections.append("## Related Issues (Context)\n\n")
        # Group by relation type
        by_type: dict[str, list[Issue]] = {}
        for related in related_issues:
            # Find relation type from main issue
            rel_type = "Related"
            for relation in issue.relations:
                if relation.identifier == related.identifier:
                    rel_type = simplify_relation_type(relation.relation_type or "Related")
                    break
            by_type.setdefault(rel_type, []).append(related)

        for rel_type, items in by_type.items():
            sections.append(f"### {rel_type}\n\n")
            for related in items:
                sections.append(f"**{related.identifier}: {related.title}**\n")
                sections.append(f"- Type: {related.issue_type or 'Unknown'}\n")
                sections.append(f"- State: {related.state or 'Unknown'}\n")
                if related.description:
                    clean_desc = clean_html(related.description)
                    # Truncate long descriptions
                    if len(clean_desc) > 200:
                        clean_desc = clean_desc[:200] + "..."
                    sections.append(f"- Description: {clean_desc}\n")
                sections.append("\n")

    # Implementation Plan (scaffold)
    sections.append("## Implementation Plan\n\n")
    sections.append("*To be filled in during planning phase*\n\n")

    # Tasks
    sections.append("## Tasks\n\n")
    sections.append("*To be generated during task breakdown phase*\n\n")

    return "".join(sections)


def clean_html(html: str) -> str:
    """Clean HTML content for readable markdown.

    Removes HTML tags and normalizes whitespace while preserving
    basic structure like lists and line breaks.

    Args:
        html: HTML string to clean

    Returns:
        Plain text with minimal formatting
    """
    # Replace common HTML elements with markdown equivalents (case-insensitive)
    text = html
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities (&nbsp;, &amp;, etc.)
    text = html_module.unescape(text)

    # Normalize whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Max 2 newlines
    text = re.sub(r"[ \t]+", " ", text)  # Normalize spaces
    text = text.strip()

    return text


def simplify_relation_type(relation_type: str) -> str:
    """Simplify ADO relation type names for readability.

    Args:
        relation_type: Full ADO relation type (e.g., "System.LinkTypes.Hierarchy-Forward")

    Returns:
        Simplified name (e.g., "Child Tasks")
    """
    # Common ADO relation types
    simplifications = {
        "System.LinkTypes.Hierarchy-Forward": "Child Tasks",
        "System.LinkTypes.Hierarchy-Reverse": "Parent",
        "Microsoft.VSTS.Common.TestedBy-Forward": "Tested By",
        "Microsoft.VSTS.Common.TestedBy-Reverse": "Tests",
        "System.LinkTypes.Related": "Related",
        "System.LinkTypes.Dependency-Forward": "Depends On",
        "System.LinkTypes.Dependency-Reverse": "Required By",
    }

    return simplifications.get(relation_type, relation_type)


def format_timestamp(timestamp: str) -> str:
    """Format ISO 8601 timestamp to readable date.

    Args:
        timestamp: ISO 8601 timestamp string (e.g., "2025-01-13T10:30:00Z")

    Returns:
        Formatted date string (e.g., "Jan 13, 2025")
    """
    try:
        # Parse ISO 8601 format
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, AttributeError):
        # Fallback to original if parsing fails
        return timestamp


# Legacy aliases for backward compatibility
_render_plan_file = render_plan_file
_render_research_findings = render_research_findings
_render_tasks = render_tasks
_status_emoji = get_status_emoji
_render_issue_summary = render_issue_summary
_render_issue_plan = render_issue_plan
_clean_html = clean_html
_simplify_relation_type = simplify_relation_type
_format_timestamp = format_timestamp
