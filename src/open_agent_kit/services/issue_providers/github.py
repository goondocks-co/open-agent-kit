"""GitHub Issues issue provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from open_agent_kit.config.messages import ERROR_MESSAGES, ISSUE_PROVIDER_VALIDATION_MESSAGES
from open_agent_kit.config.settings import issue_provider_settings
from open_agent_kit.models.config import GitHubIssuesProviderConfig
from open_agent_kit.models.issue import Issue, RelatedIssue
from open_agent_kit.services.issue_providers.base import IssueProvider, IssueProviderError


class GitHubIssuesProvider(IssueProvider):
    """Fetch issues from GitHub Issues."""

    key: str = "github"
    label: str = "GitHub Issues"

    settings: GitHubIssuesProviderConfig

    def __init__(self, settings: GitHubIssuesProviderConfig, environment: Mapping[str, str]):
        super().__init__(settings, environment)

    def validate(self) -> list[str]:
        """Validate configuration for GitHub."""
        issues: list[str] = []
        if not self.settings.owner:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["github_owner_missing"])
        if not self.settings.repo:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["github_repo_missing"])
        if not self.settings.token_env:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["github_token_env_missing"])
        else:
            token = self.environment.get(self.settings.token_env)
            if not token:
                issues.append(
                    ISSUE_PROVIDER_VALIDATION_MESSAGES["env_var_not_set"].format(
                        var_name=self.settings.token_env
                    )
                )
        return issues

    def fetch(self, identifier: str) -> Issue:
        """Fetch a GitHub issue."""
        issues = self.validate()
        if issues:
            raise IssueProviderError("; ".join(issues))

        token = self.environment.get(self.settings.token_env or "", "")
        if not token:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_env_var_missing"].format(var=self.settings.token_env)
            )

        issue_number = identifier.lstrip("#")
        url = f"https://api.github.com/repos/{self.settings.owner}/{self.settings.repo}/issues/{issue_number}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        try:
            response = httpx.get(
                url, headers=headers, timeout=issue_provider_settings.timeout_seconds
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_api_error"].format(
                    provider=self.label, error_type=exc.__class__.__name__, details=str(exc)
                )
            ) from exc

        data = response.json()

        # Validate API response structure
        if not isinstance(data, dict):
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_invalid_response"].format(provider=self.label)
            )

        title = data.get("title", f"Issue {issue_number}")
        body = data.get("body") or ""
        state = data.get("state")
        html_url = data.get("html_url")

        labels = [label.get("name", "") for label in data.get("labels", []) if label.get("name")]
        assignees = data.get("assignees", [])
        assigned_to = None
        if assignees:
            assigned_to = ", ".join(
                [assignee.get("login", "") for assignee in assignees if assignee.get("login")]
            )

        acceptance_criteria = _extract_checklist(body)
        relations = _extract_relations(data)

        # Extract GitHub-specific metadata
        milestone_data = data.get("milestone")
        milestone = milestone_data.get("title") if milestone_data else None
        comments_count = data.get("comments", 0)
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        closed_at = data.get("closed_at")

        # Detect issue type from labels
        issue_type = _detect_issue_type(labels)

        # Extract issue references from body (related issues)
        body_relations = _extract_issue_references(body)
        relations.extend(body_relations)

        metadata = {
            "body": body,
            "repository": f"{self.settings.owner}/{self.settings.repo}",
            "raw_data": data,  # Store full API response
        }

        return Issue(
            provider=self.key,
            identifier=str(data.get("number", issue_number)),
            title=title,
            description=body,
            state=state,
            url=html_url,
            assigned_to=assigned_to,
            area_path=None,
            iteration_path=None,
            tags=labels,
            acceptance_criteria=acceptance_criteria,
            relations=relations,
            metadata=metadata,
            issue_type=issue_type,
            milestone=milestone,
            comments_count=comments_count,
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
        )

    def create_issue(
        self,
        title: str,
        description: str,
        issue_type: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        acceptance_criteria: list[str] | None = None,
        **kwargs: Any,
    ) -> Issue:
        """Create a new GitHub issue.

        Args:
            title: Issue title
            description: Issue description/body
            issue_type: Type of issue (used for labels: epic, story, task)
            priority: Priority level (used for labels)
            labels: Additional labels
            parent_id: Parent issue ID (adds task list reference in description)
            acceptance_criteria: Acceptance criteria (added as checklist)
            **kwargs: Additional fields:
                - assignees: List of GitHub usernames
                - milestone: Milestone number

        Returns:
            Created Issue model

        Raises:
            IssueProviderError: If issue creation fails
        """
        issues = self.validate()
        if issues:
            raise IssueProviderError("; ".join(issues))

        token = self.environment.get(self.settings.token_env or "", "")
        if not token:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_env_var_missing"].format(var=self.settings.token_env)
            )

        # Build issue body
        body_parts = [description]

        # Add parent reference if hierarchical
        if parent_id:
            body_parts.insert(0, f"Parent: #{parent_id}\n")

        # Add acceptance criteria as checklist
        if acceptance_criteria:
            body_parts.append("\n## Acceptance Criteria\n")
            for criterion in acceptance_criteria:
                body_parts.append(f"- [ ] {criterion}")

        body = "\n".join(body_parts)

        # Build labels list
        all_labels = list(labels) if labels else []

        # Add type label
        if issue_type:
            type_label = f"type:{issue_type.lower()}"
            if type_label not in all_labels:
                all_labels.append(type_label)

        # Add priority label
        if priority:
            priority_label = f"priority:{priority.lower()}"
            if priority_label not in all_labels:
                all_labels.append(priority_label)

        # Build request payload
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
        }

        if all_labels:
            payload["labels"] = all_labels

        # Optional fields
        if kwargs.get("assignees"):
            payload["assignees"] = kwargs["assignees"]
        if kwargs.get("milestone"):
            payload["milestone"] = kwargs["milestone"]

        url = f"https://api.github.com/repos/{self.settings.owner}/{self.settings.repo}/issues"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                url, headers=headers, json=payload, timeout=issue_provider_settings.timeout_seconds
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_api_error"].format(
                    provider=self.label, error_type=exc.__class__.__name__, details=str(exc)
                )
            ) from exc

        data = response.json()

        # Return created issue
        return Issue(
            provider=self.key,
            identifier=str(data.get("number")),
            title=data.get("title", title),
            description=data.get("body", body),
            state=data.get("state"),
            url=data.get("html_url"),
            tags=[label.get("name", "") for label in data.get("labels", [])],
            acceptance_criteria=acceptance_criteria or [],
            issue_type=issue_type,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


def _extract_checklist(body: str) -> list[str]:
    """Extract acceptance criteria from markdown checklists."""
    acceptance: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- [ ]", "- [x]", "- [X]")):
            text = stripped.split("]", 1)[-1].strip()
            if text:
                acceptance.append(text)
    return acceptance


def _extract_relations(data: dict) -> list[RelatedIssue]:
    """Extract related artifacts from GitHub payload."""
    relations: list[RelatedIssue] = []
    pull_request = data.get("pull_request")
    if isinstance(pull_request, dict):
        pr_url = pull_request.get("html_url") or pull_request.get("url")
        if pr_url:
            relations.append(
                RelatedIssue(
                    relation_type="pull_request",
                    url=pr_url,
                    additional_metadata={"mergeable": str(pull_request.get("mergeable", ""))},
                )
            )
    return relations


def _detect_issue_type(labels: list[str]) -> str:
    """Detect issue type from GitHub labels.

    Args:
        labels: List of label names

    Returns:
        Detected issue type (Bug, Feature, Task, or Issue)
    """
    labels_lower = [label.lower() for label in labels]

    # Check for bug indicators
    bug_labels = {"bug", "defect", "error", "regression", "hotfix"}
    if any(label in bug_labels for label in labels_lower):
        return "Bug"

    # Check for feature indicators
    feature_labels = {"enhancement", "feature", "feature-request", "new-feature"}
    if any(label in feature_labels for label in labels_lower):
        return "Feature"

    # Check for task indicators
    task_labels = {"task", "chore", "maintenance", "refactor", "tech-debt"}
    if any(label in task_labels for label in labels_lower):
        return "Task"

    # Check for documentation
    doc_labels = {"documentation", "docs"}
    if any(label in doc_labels for label in labels_lower):
        return "Documentation"

    # Default
    return "Issue"


def _extract_issue_references(body: str) -> list[RelatedIssue]:
    """Extract related issue references from issue body.

    Looks for patterns like:
    - Fixes #123
    - Closes #456
    - Related to #789
    - See #101
    - owner/repo#123

    Args:
        body: Issue body text

    Returns:
        List of related issues
    """
    import re

    relations: list[RelatedIssue] = []
    if not body:
        return relations

    # Pattern for issue references: #123 or owner/repo#123
    # Common keywords: fixes, closes, resolves, related, see, ref
    patterns = [
        (r"(?:fixes|closes|resolves|fixed|closed|resolved)\s+#(\d+)", "Fixes"),
        (r"(?:related to|relates to|related)\s+#(\d+)", "Related"),
        (r"(?:see|ref|reference)\s+#(\d+)", "Reference"),
        (r"(?:blocked by|blocks)\s+#(\d+)", "Blocks"),
        (r"(?:depends on|requires)\s+#(\d+)", "Depends On"),
        (r"#(\d+)", "Reference"),  # Catch-all for any #123
    ]

    seen_issues: set[str] = set()

    for pattern, relation_type in patterns:
        matches = re.finditer(pattern, body, re.IGNORECASE)
        for match in matches:
            issue_num = match.group(1)
            if issue_num not in seen_issues:
                seen_issues.add(issue_num)
                relations.append(
                    RelatedIssue(
                        relation_type=relation_type,
                        identifier=issue_num,
                        title=None,  # Would need separate API call to get title
                        url=None,  # Would need repo context to build URL
                        additional_metadata={},
                    )
                )

    return relations
