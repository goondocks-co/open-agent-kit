"""Service layer for issue workflows.

This module provides high-level orchestration for issue providers,
artifact management, and git branch operations. It serves as the main
interface between CLI commands and issue provider implementations (Azure DevOps, GitHub).

Key Classes:
    IssueService: Main service class for issue operations, context management,
                  and code summary generation

Dependencies:
    - ConfigService: For reading issue provider configuration
    - IssueProvider: Provider interface implementations (ADO, GitHub)
    - Git: For branch operations and repository introspection

Architecture:
    CLI Commands → IssueService → IssueProvider → External API
                                → Git Operations
                                → Artifact Storage (oak/issue/{provider}/{id}/)

Typical workflow:
    1. Configure provider: user runs `oak config`
    2. Plan issue: `oak issue plan <issue>` → fetch + scaffold artifacts
    3. Implement: `oak issue implement <issue>` → checkout branch + load context
    4. Validate: `oak issue validate <issue>` → check completeness

Example:
    >>> service = IssueService(project_root=Path.cwd())
    >>> provider = service.get_provider("ado")
    >>> issue = provider.fetch("12345")
    >>> service.write_context(issue)
    >>> service.write_plan(issue)
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from open_agent_kit.constants import (
    ERROR_MESSAGES,
    GIT_COMMAND_TIMEOUT_SECONDS,
    ISSUE_CONTEXT_FILENAME,
    ISSUE_CONTEXT_SUMMARY_FILENAME,
    ISSUE_DIR,
    ISSUE_MANIFEST_FILENAME,
    ISSUE_PLAN_FILENAME,
    ISSUE_PROVIDER_CONFIG_MAP,
    SUCCESS_MESSAGES,
)
from open_agent_kit.models.config import IssueProvidersConfig
from open_agent_kit.models.issue import Issue, IssuePlanDetails, RelatedIssue
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.issue_providers import AzureDevOpsProvider, GitHubIssuesProvider
from open_agent_kit.services.issue_providers.base import IssueProvider, IssueProviderError
from open_agent_kit.utils import ensure_dir, sanitize_filename

PROVIDER_REGISTRY: dict[str, type[IssueProvider]] = {
    "ado": AzureDevOpsProvider,
    "github": GitHubIssuesProvider,
}


class IssueService:
    """High-level orchestration for issue providers and artifacts."""

    def __init__(
        self, project_root: Path | None = None, environment: Mapping[str, str] | None = None
    ):
        self.project_root = project_root or Path.cwd()
        self.environment = environment or os.environ
        self.config_service = ConfigService(project_root)

    # -------------------------------------------------------------------------
    # Provider management
    # -------------------------------------------------------------------------
    def get_issue_config(self) -> IssueProvidersConfig:
        """Return current issue provider configuration."""
        return self.config_service.get_issue_config()

    def resolve_provider_key(self, provider_key: str | None = None) -> str:
        """Resolve provider key using explicit value or configuration."""
        config = self.get_issue_config()
        resolved = provider_key or config.provider
        if not resolved:
            raise IssueProviderError(ERROR_MESSAGES["issue_provider_not_set"])
        if resolved not in PROVIDER_REGISTRY:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_invalid"].format(provider=resolved)
            )
        return resolved

    def get_provider(self, provider_key: str | None = None) -> IssueProvider:
        """Instantiate provider implementation."""
        key = self.resolve_provider_key(provider_key)
        provider_cls = PROVIDER_REGISTRY[key]
        config = self.get_issue_config()
        provider_attr = ISSUE_PROVIDER_CONFIG_MAP.get(key)
        settings = getattr(config, provider_attr) if provider_attr else None
        return provider_cls(settings=settings, environment=self.environment)

    def validate_provider(self, provider_key: str | None = None) -> list[str]:
        """Return validation issues for the provider configuration."""
        try:
            provider = self.get_provider(provider_key)
        except IssueProviderError as exc:
            return [str(exc)]
        return provider.validate()

    # -------------------------------------------------------------------------
    # Artifact helpers
    # -------------------------------------------------------------------------
    def ensure_issue_dir(self) -> Path:
        """Ensure oak/issue directory exists."""
        issue_dir = self.project_root / ISSUE_DIR
        ensure_dir(issue_dir)
        return issue_dir

    def get_issue_dir(self, provider_key: str, identifier: str) -> Path:
        """Return directory for a specific issue."""
        issue_dir = self.ensure_issue_dir()
        safe_identifier = sanitize_filename(identifier)
        return issue_dir / provider_key / safe_identifier

    def find_issue_dir(
        self,
        identifier: str | None,
        provider_key: str | None = None,
    ) -> tuple[str, Path] | None:
        """Find an existing issue directory, optionally constrained to a provider."""
        try:
            resolved_provider, resolved_issue = self.resolve_issue(identifier, provider_key)
        except IssueProviderError:
            return None

        issue_dir = self.get_issue_dir(resolved_provider, resolved_issue)
        if issue_dir.exists():
            return resolved_provider, issue_dir
        return None

    def get_context_path(self, provider_key: str, identifier: str) -> Path:
        """Return context file path for issue."""
        return self.get_issue_dir(provider_key, identifier) / ISSUE_CONTEXT_FILENAME

    def get_plan_path(self, provider_key: str, identifier: str) -> Path:
        """Return plan markdown path for issue."""
        return self.get_issue_dir(provider_key, identifier) / ISSUE_PLAN_FILENAME

    def load_issue(self, provider_key: str, identifier: str) -> Issue:
        """Load stored issue context."""
        context_path = self.get_context_path(provider_key, identifier)
        if not context_path.exists():
            raise FileNotFoundError(context_path)
        with context_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return Issue(**data)

    def read_plan(self, provider_key: str, identifier: str) -> str:
        """Read stored plan markdown."""
        plan_path = self.get_plan_path(provider_key, identifier)
        if not plan_path.exists():
            raise FileNotFoundError(plan_path)
        return plan_path.read_text(encoding="utf-8")

    def write_context(self, issue: Issue, related_items: list[Issue] | None = None) -> Path:
        """Persist JSON context for the focus issue and its related issues.

        Also generates a context-summary.md file with agent-friendly formatting.

        Args:
            issue: The focus issue being planned/implemented
            related_items: Optional list of related issues (parents, children, etc.) for context

        Returns:
            Path to the focus issue's context.json file
        """
        issue_dir = self.get_issue_dir(issue.provider, issue.identifier)
        ensure_dir(issue_dir)

        # Write focus issue context (JSON)
        context_path = issue_dir / ISSUE_CONTEXT_FILENAME
        with context_path.open("w", encoding="utf-8") as fh:
            json.dump(issue.model_dump(mode="json"), fh, indent=2)

        # Write agent-friendly markdown summary
        summary_path = issue_dir / ISSUE_CONTEXT_SUMMARY_FILENAME
        summary_content = _render_context_summary(issue)
        summary_path.write_text(summary_content, encoding="utf-8")

        # Write related items in subdirectory for additional context
        if related_items:
            related_dir = issue_dir / "related"
            ensure_dir(related_dir)
            for related in related_items:
                related_item_dir = related_dir / related.identifier
                ensure_dir(related_item_dir)
                related_context_path = related_item_dir / ISSUE_CONTEXT_FILENAME
                with related_context_path.open("w", encoding="utf-8") as fh:
                    json.dump(related.model_dump(mode="json"), fh, indent=2)

                # Write summary for related items too
                related_summary_path = related_item_dir / ISSUE_CONTEXT_SUMMARY_FILENAME
                related_summary_content = _render_context_summary(related)
                related_summary_path.write_text(related_summary_content, encoding="utf-8")

        return context_path

    def read_context(self, provider_key: str, identifier: str) -> Issue:
        """Read issue context from JSON file.

        Args:
            provider_key: Issue provider key
            identifier: Issue identifier

        Returns:
            Issue loaded from context file

        Raises:
            FileNotFoundError: If context file doesn't exist
            ValueError: If context file is invalid
        """
        context_path = self.get_context_path(provider_key, identifier)
        with context_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return Issue.model_validate(data)

    def update_branch_name(self, provider_key: str, identifier: str, branch_name: str) -> None:
        """Update the branch name in the issue's context file.

        Args:
            provider_key: Issue provider key
            identifier: Issue identifier
            branch_name: Git branch name to save
        """
        try:
            issue = self.read_context(provider_key, identifier)
            issue.branch_name = branch_name
            issue_dir = self.get_issue_dir(provider_key, identifier)
            context_path = issue_dir / ISSUE_CONTEXT_FILENAME
            with context_path.open("w", encoding="utf-8") as fh:
                json.dump(issue.model_dump(mode="json"), fh, indent=2)
        except (FileNotFoundError, json.JSONDecodeError, ValidationError, OSError):
            # Non-fatal if we can't update - branch tracking is a convenience feature
            # Possible failures: context.json doesn't exist, is malformed, or can't be written
            # This is expected for issues created before branch tracking was added
            pass

    def refresh_context(
        self, provider_key: str, identifier: str
    ) -> tuple[Issue, Issue, dict[str, Any]]:
        """Refresh issue context from provider, preserving local artifacts.

        Fetches fresh data from the provider and updates context.json and context-summary.md
        while preserving all other artifacts (plan.md, notes.md, codebase.md, etc.).

        Args:
            provider_key: Issue provider key
            identifier: Issue identifier

        Returns:
            Tuple of (old_issue, new_issue, changes_summary)

        Raises:
            FileNotFoundError: If issue context doesn't exist
            IssueProviderError: If provider fetch fails
        """
        # Load existing context
        old_issue = self.read_context(provider_key, identifier)

        # Fetch fresh data from provider
        provider = self.get_provider(provider_key)
        new_issue = provider.fetch(identifier)

        # Preserve local-only fields from old context
        new_issue.branch_name = old_issue.branch_name or new_issue.branch_name

        # Detect changes
        changes = _detect_issue_changes(old_issue, new_issue)

        # Update context files (both JSON and markdown summary)
        issue_dir = self.get_issue_dir(provider_key, identifier)
        context_path = issue_dir / ISSUE_CONTEXT_FILENAME
        with context_path.open("w", encoding="utf-8") as fh:
            json.dump(new_issue.model_dump(mode="json"), fh, indent=2)

        # Update summary
        summary_path = issue_dir / ISSUE_CONTEXT_SUMMARY_FILENAME
        summary_content = _render_context_summary(new_issue)
        summary_path.write_text(summary_content, encoding="utf-8")

        return old_issue, new_issue, changes

    def write_plan(
        self,
        issue: Issue,
        details: IssuePlanDetails | None = None,
        related_items: list[Issue] | None = None,
    ) -> Path:
        """Persist plan markdown for the focus issue, including related issues for context.

        Args:
            issue: The focus issue being planned/implemented
            details: Optional planning details
            related_items: Optional list of related issues (parents, children, etc.) for context

        Returns:
            Path to the plan.md file
        """
        issue_dir = self.get_issue_dir(issue.provider, issue.identifier)
        ensure_dir(issue_dir)
        plan_path = issue_dir / ISSUE_PLAN_FILENAME
        plan_content = _render_plan(issue, details, related_items)
        plan_path.write_text(plan_content, encoding="utf-8")
        return plan_path

    def record_plan(self, provider_key: str, identifier: str, branch_name: str) -> None:
        """Record plan metadata for later inference."""
        provider_key = self.resolve_provider_key(provider_key)
        manifest = self._load_manifest()
        timestamp = datetime.now(UTC).isoformat()
        entry = {
            "provider": provider_key,
            "issue": identifier,
            "branch": branch_name,
            "timestamp": timestamp,
        }

        # Remove existing entry for same issue/provider
        manifest = [
            item
            for item in manifest
            if not (item.get("issue") == identifier and item.get("provider") == provider_key)
        ]
        manifest.append(entry)
        self._save_manifest(manifest)

    def resolve_issue(self, issue: str | None, provider_key: str | None) -> tuple[str, str]:
        """Resolve provider + issue based on inputs, branch, or manifest."""
        manifest = self._load_manifest()

        if issue:
            inferred_provider = provider_key or self._provider_for_issue(issue, manifest)
            if inferred_provider:
                return self.resolve_provider_key(inferred_provider), issue
            if provider_key:
                return self.resolve_provider_key(provider_key), issue
            raise IssueProviderError(ERROR_MESSAGES["issue_not_found"].format(issue=issue))

        # No issue provided: try current branch first
        branch_issue = self._issue_from_branch(manifest)
        if branch_issue:
            return branch_issue

        # Fallback to most recent manifest entry
        if manifest:
            latest = sorted(manifest, key=lambda item: item.get("timestamp", ""), reverse=True)[0]
            return latest["provider"], latest["issue"]

        raise IssueProviderError(ERROR_MESSAGES["issue_not_found"].format(issue=""))

    def _provider_for_issue(self, issue: str, manifest: list[dict]) -> str | None:
        for entry in manifest:
            if entry.get("issue") == issue:
                provider_key = entry.get("provider")
                if provider_key:
                    return self.resolve_provider_key(provider_key)
        return None

    def _issue_from_branch(self, manifest: list[dict]) -> tuple[str, str] | None:
        branch = self._current_branch()
        if not branch:
            return None
        slug = branch.split("-", 1)[0]
        for entry in manifest:
            if entry.get("branch") == branch or entry.get("issue") == slug:
                provider_key = entry.get("provider")
                issue = entry.get("issue")
                if provider_key and issue:
                    return self.resolve_provider_key(provider_key), issue
        return None

    def _current_branch(self) -> str | None:
        """Get current git branch name.

        Returns:
            Branch name or None if not in a git repo or detached HEAD
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
            branch = result.stdout.strip()
            return branch if branch and branch != "HEAD" else None
        except subprocess.CalledProcessError:
            # Git command failed (not a repo, etc)
            return None
        except subprocess.TimeoutExpired:
            # Git hanging - shouldn't happen for this command
            return None
        except FileNotFoundError:
            # Git not installed
            return None

    def _manifest_path(self) -> Path:
        return self.ensure_issue_dir() / ISSUE_MANIFEST_FILENAME

    def _load_manifest(self) -> list[dict]:
        """Load manifest file containing issue metadata.

        Returns:
            List of manifest entries, or empty list if file doesn't exist or is invalid
        """
        path = self._manifest_path()
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError, ValueError):
            # File read error, invalid JSON, or other parsing error
            return []
        return []

    def _save_manifest(self, manifest: list[dict]) -> None:
        path = self._manifest_path()
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # -------------------------------------------------------------------------
    # Git helpers
    # -------------------------------------------------------------------------
    def build_branch_name(self, issue: Issue, provider: IssueProvider | None = None) -> str:
        """Generate a branch name for the issue."""
        source = provider or self.get_provider(issue.provider)
        return source.build_branch_name(issue.identifier, issue.title)

    def branch_exists(self, branch_name: str, repo_root: Path) -> bool:
        """Check if a git branch already exists."""
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def checkout_branch(self, branch_name: str, repo_root: Path, create: bool = True) -> None:
        """Create or switch to a git branch."""
        command = ["git", "checkout", branch_name]
        if create:
            command.insert(2, "-b")
        subprocess.run(command, cwd=repo_root, check=True)


def _render_plan(
    issue: Issue,
    details: IssuePlanDetails | None,
    related_items: list[Issue] | None = None,
) -> str:
    """Render markdown plan content for the focus issue, including related issues for context."""
    details = details or IssuePlanDetails()
    related_items = related_items or []

    acceptance_section = "\n".join(f"- {item}" for item in issue.acceptance_criteria) or "- Pending"
    tags_text = ", ".join(issue.tags) if issue.tags else "none"
    relations_section = _render_relations(issue)

    # Categorize related items based on relation types from the focus issue
    parents = []
    children = []
    other_related = []

    for related in related_items:
        # Find the relation from focus issue to this related item
        matching_relation = next(
            (r for r in issue.relations if r.identifier == related.identifier), None
        )
        if matching_relation:
            rel_type = matching_relation.relation_type
            if "parent" in rel_type.lower() or "hierarchy-reverse" in rel_type.lower():
                parents.append(related)
            elif "child" in rel_type.lower() or "hierarchy-forward" in rel_type.lower():
                children.append(related)
            else:
                other_related.append(related)
        else:
            other_related.append(related)

    # Build related issues sections for context
    related_context_section = ""

    if parents:
        related_context_section += "\n## Parent Issues (Context)\n\n"
        for parent in parents:
            issue_type = parent.issue_type or "Unknown"
            related_context_section += f"### {parent.identifier}: {parent.title}\n"
            related_context_section += (
                f"**{issue_type}:** {parent.description or 'No description provided'}\n\n"
            )
            related_context_section += (
                f"**Context:** `related/{parent.identifier}/context.json`\n\n"
            )

    if children:
        related_context_section += "\n## Child Issues (Context)\n\n"
        for child in children:
            issue_type = child.issue_type or "Task"
            related_context_section += f"### {child.identifier}: {child.title}\n"
            related_context_section += (
                f"**{issue_type}:** {child.description or 'No description provided'}\n\n"
            )
            if child.acceptance_criteria:
                related_context_section += "**Acceptance Criteria:**\n"
                for criterion in child.acceptance_criteria:
                    related_context_section += f"- {criterion}\n"
                related_context_section += "\n"
            related_context_section += f"**Context:** `related/{child.identifier}/context.json`\n\n"

    if other_related:
        related_context_section += "\n## Related Issues (Context)\n\n"
        for other in other_related:
            issue_type = other.issue_type or "Unknown"
            related_context_section += f"### {other.identifier}: {other.title}\n"
            related_context_section += (
                f"**{issue_type}:** {other.description or 'No description provided'}\n\n"
            )
            related_context_section += f"**Context:** `related/{other.identifier}/context.json`\n\n"

    def _section(title: str, value: str | None) -> str:
        if value:
            return value.strip()
        return "Pending"

    return f"""# Issue {issue.identifier}: {issue.title}

## Provider Context
- Provider: {issue.provider}
- URL: {issue.url or 'n/a'}
- State: {issue.state or 'unknown'}
- Assigned To: {issue.assigned_to or 'unassigned'}
- Area Path: {issue.area_path or 'n/a'}
- Iteration Path: {issue.iteration_path or 'n/a'}
- Tags: {tags_text}

## Description
{issue.description or 'No description provided'}
{related_context_section}
## Acceptance Criteria
{acceptance_section}

## Related Artifacts
{relations_section}

## Implementation Plan
### Objectives
{_section('Objectives', details.objectives)}

### Environment / Constraints
{_section('Environment', details.environment)}

### Risks & Mitigations
{_section('Risks', details.risks)}

### Dependencies
{_section('Dependencies', details.dependencies)}

### Definition of Done
{_section('Definition of Done', details.definition_of_done)}

    ---
    {SUCCESS_MESSAGES['issue_artifacts_ready']}
    """


def _render_relations(issue: Issue) -> str:
    """Render related items grouped by relation type."""
    if not issue.relations:
        return "- None captured"

    grouped: dict[str, list[RelatedIssue]] = {}
    for relation in issue.relations:
        grouped.setdefault(relation.relation_type or "related", []).append(relation)

    lines: list[str] = []
    for relation_type, items in grouped.items():
        lines.append(f"- **{relation_type}**:")
        for rel in items:
            title = rel.title or ""
            identifier = rel.identifier or ""
            url = rel.url or ""
            details = ", ".join(
                f"{k}={v}" for k, v in rel.additional_metadata.items() if v and k != "comment"
            )
            bullet = f"    - {identifier} {title}".strip()
            if url:
                bullet += f" ({url})"
            if details:
                bullet += f" [{details}]"
            lines.append(bullet)
    return "\n".join(lines) if lines else "- None captured"


def _render_context_summary(issue: Issue) -> str:
    """Render agent-friendly markdown summary of issue context.

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
        # Format timestamp nicely
        created_date = _format_timestamp(issue.created_at)
        sections.append(f"**Created:** {created_date}  \n")

    if issue.updated_at:
        updated_date = _format_timestamp(issue.updated_at)
        sections.append(f"**Updated:** {updated_date}  \n")

    if issue.closed_at:
        closed_date = _format_timestamp(issue.closed_at)
        sections.append(f"**Closed:** {closed_date}  \n")

    if issue.url:
        sections.append(f"**URL:** {issue.url}  \n")

    sections.append("\n")

    # Description (clean HTML if present)
    if issue.description:
        sections.append("## Description\n\n")
        clean_description = _clean_html(issue.description)
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
            rel_type_display = _simplify_relation_type(rel_type)
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
            clean_text = _clean_html(comment.text) if comment.text else ""
            sections.append(f"> {clean_text}\n\n")

    # Tags
    if issue.tags:
        sections.append("## Tags\n\n")
        sections.append(", ".join(f"`{tag}`" for tag in issue.tags))
        sections.append("\n\n")

    return "".join(sections)


def _clean_html(html: str) -> str:
    """Clean HTML content for readable markdown.

    Removes HTML tags and normalizes whitespace while preserving
    basic structure like lists and line breaks.

    Args:
        html: HTML string to clean

    Returns:
        Plain text with minimal formatting
    """
    import html as html_module
    import re

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


def _simplify_relation_type(relation_type: str) -> str:
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


def _format_timestamp(timestamp: str) -> str:
    """Format ISO 8601 timestamp to readable date.

    Args:
        timestamp: ISO 8601 timestamp string (e.g., "2025-01-13T10:30:00Z")

    Returns:
        Formatted date string (e.g., "Jan 13, 2025")
    """
    from datetime import datetime

    try:
        # Parse ISO 8601 format
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, AttributeError):
        # Fallback to original if parsing fails
        return timestamp


def _detect_issue_changes(old: Issue, new: Issue) -> dict[str, Any]:
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
