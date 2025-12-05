"""Azure DevOps issue provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from open_agent_kit.config.messages import ERROR_MESSAGES, ISSUE_PROVIDER_VALIDATION_MESSAGES
from open_agent_kit.config.settings import issue_provider_settings
from open_agent_kit.models.config import AzureDevOpsProviderConfig
from open_agent_kit.models.issue import Comment, Issue, IssueTestStep, RelatedIssue
from open_agent_kit.services.issue_providers.base import IssueProvider, IssueProviderError


class AzureDevOpsProvider(IssueProvider):
    """Fetch issues from Azure DevOps boards."""

    key: str = "ado"
    label: str = "Azure DevOps"
    api_version: str = "7.1-preview.3"

    settings: AzureDevOpsProviderConfig

    def __init__(self, settings: AzureDevOpsProviderConfig, environment: Mapping[str, str]):
        super().__init__(settings, environment)

    def validate(self) -> list[str]:
        """Validate configuration for Azure DevOps."""
        issues: list[str] = []
        if not self.settings.organization:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["ado_org_missing"])
        if not self.settings.project:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["ado_project_missing"])
        if not self.settings.pat_env:
            issues.append(ISSUE_PROVIDER_VALIDATION_MESSAGES["ado_pat_env_missing"])
        else:
            token = self.environment.get(self.settings.pat_env)
            if not token:
                issues.append(
                    ISSUE_PROVIDER_VALIDATION_MESSAGES["env_var_not_set"].format(
                        var_name=self.settings.pat_env
                    )
                )
        return issues

    def fetch(self, identifier: str) -> Issue:
        """Fetch issue details from Azure DevOps."""
        import base64

        issues = self.validate()
        if issues:
            raise IssueProviderError("; ".join(issues))

        pat = self.environment.get(self.settings.pat_env or "", "")
        if not pat:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_env_var_missing"].format(var=self.settings.pat_env)
            )

        # Azure DevOps requires Basic auth with empty username and PAT as password
        # Format: "Authorization: Basic base64(':PAT')"
        credentials = base64.b64encode(f":{pat}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

        url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workitems/{identifier}"
        )
        params = {"api-version": self.api_version, "$expand": "relations"}

        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=issue_provider_settings.timeout_seconds,
                follow_redirects=False,  # Don't follow redirects, they indicate auth failure
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

        if "fields" not in data:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_invalid_response"].format(provider=self.label)
            )

        fields = data.get("fields", {})
        if not isinstance(fields, dict):
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_invalid_response"].format(provider=self.label)
            )

        title = fields.get("System.Title", "Untitled Issue")
        description = fields.get("System.Description")
        state = fields.get("System.State")
        tags_value = fields.get("System.Tags", "")
        tags = [tag.strip() for tag in tags_value.split(";") if tag.strip()]

        acceptance_raw = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
        acceptance_criteria = _normalize_acceptance_criteria(acceptance_raw)

        relations_raw = data.get("relations", []) or []
        relations = [_normalize_relation(rel) for rel in relations_raw]

        # Batch fetch titles for related issues to populate relation titles
        if relations:
            related_ids = [r.identifier for r in relations if r.identifier]
            if related_ids:
                related_titles = self._batch_fetch_titles(related_ids, headers)
                for relation in relations:
                    if relation.identifier and relation.identifier in related_titles:
                        relation.title = related_titles[relation.identifier]

        web_url = data.get("_links", {}).get("html", {}).get("href")
        assigned = None
        assigned_data = fields.get("System.AssignedTo")
        if isinstance(assigned_data, dict):
            assigned = assigned_data.get("displayName")
        elif isinstance(assigned_data, str):
            assigned = assigned_data

        area_path = fields.get("System.AreaPath")
        iteration_path = fields.get("System.IterationPath")

        # Extract type-specific fields
        issue_type = fields.get("System.WorkItemType", "")
        effort = fields.get("Microsoft.VSTS.Scheduling.Effort")
        priority = fields.get("Microsoft.VSTS.Common.Priority")

        # Type-specific extraction
        test_steps = None
        repro_steps = None
        if issue_type == "Test Case":
            test_steps = _extract_test_steps(fields)
        elif issue_type == "Bug":
            repro_steps = _extract_repro_steps(fields)

        # Fetch comments for this issue
        comments = self._fetch_comments(identifier, headers)

        metadata = {
            "provider_url": web_url,
            "raw_fields": fields,
        }

        return Issue(
            provider=self.key,
            identifier=str(data.get("id", identifier)),
            title=title,
            description=description,
            state=state,
            url=web_url,
            assigned_to=assigned,
            area_path=area_path,
            iteration_path=iteration_path,
            tags=tags,
            acceptance_criteria=acceptance_criteria,
            relations=relations,
            metadata=metadata,
            issue_type=issue_type,
            effort=effort,
            priority=priority,
            test_steps=test_steps,
            repro_steps=repro_steps,
            comments=comments,
        )

    def _batch_fetch_titles(self, identifiers: list[str], headers: dict) -> dict[str, str]:
        """Batch fetch issue titles for multiple IDs.

        Args:
            identifiers: List of issue IDs to fetch titles for
            headers: Authentication headers to use

        Returns:
            Dictionary mapping issue ID to title
        """
        if not identifiers:
            return {}

        # Azure DevOps batch API endpoint
        # POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitemsbatch?api-version=7.1-preview.1
        url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workitemsbatch"
        )
        params = {"api-version": "7.1-preview.1"}

        # Request only the System.Title field for efficiency
        payload = {"ids": identifiers, "fields": ["System.Title"]}

        try:
            response = httpx.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=issue_provider_settings.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # If batch fetch fails, return empty dict - titles will show as None
            return {}

        data = response.json()
        if not isinstance(data, dict) or "value" not in data:
            return {}

        # Extract titles from response
        titles = {}
        for item in data.get("value", []):
            if isinstance(item, dict):
                item_id = str(item.get("id", ""))
                title = item.get("fields", {}).get("System.Title")
                if item_id and title:
                    titles[item_id] = title

        return titles

    def _fetch_comments(self, identifier: str, headers: dict) -> list[Comment]:
        """Fetch comments for an issue.

        Args:
            identifier: Issue ID
            headers: Authentication headers to use

        Returns:
            List of Comment objects
        """
        # Azure DevOps Comments API endpoint
        url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workItems/{identifier}/comments"
        )
        params = {"api-version": "7.1-preview.4"}

        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=issue_provider_settings.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # If comment fetch fails, return empty list - comments are optional
            return []

        data = response.json()
        if not isinstance(data, dict) or "comments" not in data:
            return []

        # Extract comments from response
        comments = []
        for comment_data in data.get("comments", []):
            if not isinstance(comment_data, dict):
                continue

            # Extract comment fields
            comment_id = str(comment_data.get("id", ""))
            text = comment_data.get("text", "")

            # Skip empty comments
            if not text:
                continue

            # Extract author information
            created_by = None
            created_by_data = comment_data.get("createdBy")
            if isinstance(created_by_data, dict):
                created_by = created_by_data.get("displayName")

            # Extract timestamps
            created_date = comment_data.get("createdDate")
            modified_date = comment_data.get("modifiedDate")

            comments.append(
                Comment(
                    comment_id=comment_id if comment_id else None,
                    text=text,
                    created_by=created_by,
                    created_date=created_date,
                    modified_date=modified_date,
                )
            )

        return comments

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
        """Create a new Azure DevOps work item.

        Args:
            title: Work item title
            description: Work item description
            issue_type: Work item type (Epic, Feature, User Story, Task, Bug)
            priority: Priority level (1-4)
            labels: Tags (semicolon-separated in ADO)
            parent_id: Parent work item ID for hierarchical linking
            acceptance_criteria: Acceptance criteria list
            **kwargs: Additional fields:
                - area_path: Area path
                - iteration_path: Iteration path
                - assigned_to: Display name or email

        Returns:
            Created Issue model

        Raises:
            IssueProviderError: If work item creation fails
        """
        import base64

        issues = self.validate()
        if issues:
            raise IssueProviderError("; ".join(issues))

        pat = self.environment.get(self.settings.pat_env or "", "")
        if not pat:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_env_var_missing"].format(var=self.settings.pat_env)
            )

        # Map issue types to ADO work item types
        work_item_type = _map_issue_type_to_ado(issue_type)

        # Build JSON Patch document
        operations: list[dict[str, Any]] = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": description},
        ]

        # Add acceptance criteria if provided
        if acceptance_criteria:
            ac_html = "<ul>" + "".join(f"<li>{c}</li>" for c in acceptance_criteria) + "</ul>"
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
                    "value": ac_html,
                }
            )

        # Add priority (1-4 in ADO)
        if priority:
            priority_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
            ado_priority = priority_map.get(priority.lower(), 3)
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.Priority",
                    "value": ado_priority,
                }
            )

        # Add tags
        if labels:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": "; ".join(labels),
                }
            )

        # Add area path (use configured default or provided value)
        area_path = kwargs.get("area_path") or self.settings.area_path
        if area_path:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": area_path,
                }
            )

        # Add iteration path
        iteration_path = kwargs.get("iteration_path")
        if iteration_path:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": iteration_path,
                }
            )

        # Add assigned to
        assigned_to = kwargs.get("assigned_to")
        if assigned_to:
            operations.append(
                {
                    "op": "add",
                    "path": "/fields/System.AssignedTo",
                    "value": assigned_to,
                }
            )

        # Credentials
        credentials = base64.b64encode(f":{pat}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json-patch+json",
        }

        # Create work item
        url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workitems/${work_item_type}"
        )
        params = {"api-version": self.api_version}

        try:
            response = httpx.post(
                url,
                params=params,
                headers=headers,
                json=operations,
                timeout=issue_provider_settings.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_api_error"].format(
                    provider=self.label, error_type=exc.__class__.__name__, details=str(exc)
                )
            ) from exc

        data = response.json()
        work_item_id = str(data.get("id", ""))

        # Add parent link if provided
        if parent_id and work_item_id:
            self._add_parent_link(work_item_id, parent_id, credentials)

        # Get web URL
        web_url = data.get("_links", {}).get("html", {}).get("href")

        # Return created issue
        fields = data.get("fields", {})
        return Issue(
            provider=self.key,
            identifier=work_item_id,
            title=fields.get("System.Title", title),
            description=fields.get("System.Description", description),
            state=fields.get("System.State"),
            url=web_url,
            area_path=fields.get("System.AreaPath"),
            iteration_path=fields.get("System.IterationPath"),
            tags=labels or [],
            acceptance_criteria=acceptance_criteria or [],
            issue_type=work_item_type,
            priority=fields.get("Microsoft.VSTS.Common.Priority"),
        )

    def _add_parent_link(self, child_id: str, parent_id: str, credentials: str) -> None:
        """Add parent-child link between work items.

        Args:
            child_id: Child work item ID
            parent_id: Parent work item ID
            credentials: Base64 encoded credentials
        """
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json-patch+json",
        }

        # Build link operation
        parent_url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workitems/{parent_id}"
        )

        operations = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_url,
                    "attributes": {"comment": "Added by open-agent-kit plan export"},
                },
            }
        ]

        url = (
            f"https://dev.azure.com/{self.settings.organization}/"
            f"{self.settings.project}/_apis/wit/workitems/{child_id}"
        )
        params = {"api-version": self.api_version}

        try:
            response = httpx.patch(
                url,
                params=params,
                headers=headers,
                json=operations,
                timeout=issue_provider_settings.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # Link creation failed - log but don't fail the whole operation
            pass


def _map_issue_type_to_ado(issue_type: str | None) -> str:
    """Map generic issue types to Azure DevOps work item types.

    Args:
        issue_type: Generic type (epic, story, task, subtask, bug)

    Returns:
        Azure DevOps work item type
    """
    if not issue_type:
        return "Task"

    type_map = {
        "epic": "Epic",
        "story": "User Story",
        "feature": "Feature",
        "task": "Task",
        "subtask": "Task",  # ADO doesn't have subtask, use Task
        "bug": "Bug",
    }

    return type_map.get(issue_type.lower(), "Task")


def _normalize_acceptance_criteria(value: str | None) -> list[str]:
    """Convert Azure DevOps acceptance criteria rich text to plain list."""
    if not value:
        return []

    # Basic normalization: split on newlines or bullet markers
    normalized: list[str] = []
    for line in value.replace("\r", "").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        stripped = stripped.lstrip("-•* ")
        if stripped:
            normalized.append(stripped)
    return normalized


def _normalize_relation(relation: dict) -> RelatedIssue:
    """Convert Azure DevOps relation record to RelatedIssue."""
    rel_type = relation.get("rel", "")
    url = relation.get("url")
    attributes = relation.get("attributes") or {}
    identifier = None
    if url and url.rsplit("/", 1)[-1].isdigit():
        identifier = url.rsplit("/", 1)[-1]
    return RelatedIssue(
        relation_type=rel_type,
        identifier=identifier,
        url=url,
        additional_metadata={
            k: str(v)
            for k, v in attributes.items()
            if isinstance(k, str) and isinstance(v, (str, int))
        },
    )


def _extract_test_steps(fields: dict) -> list[IssueTestStep] | None:
    """Extract and parse test steps from ADO Test Case XML.

    ADO Test Cases store steps in Microsoft.VSTS.TCM.Steps as XML:
    <steps>
      <step id="1" type="ActionStep">
        <parameterizedString>Action text</parameterizedString>
        <parameterizedString>Expected result</parameterizedString>
      </step>
    </steps>

    Args:
        fields: Raw fields dictionary from ADO API

    Returns:
        List of IssueTestStep objects, or None if no steps or parse error
    """
    import xml.etree.ElementTree as ET

    steps_xml = fields.get("Microsoft.VSTS.TCM.Steps")
    if not steps_xml:
        return None

    try:
        root = ET.fromstring(steps_xml)
        steps = []

        for step_elem in root.findall(".//step"):
            step_id_str = step_elem.get("id", "0")
            step_id = int(step_id_str) if step_id_str.isdigit() else 0

            # Check if this is a shared step reference
            step_type = step_elem.get("type", "")
            if step_type == "SharedStepReference":
                ref_id_str = step_elem.get("ref", "0")
                ref_id = int(ref_id_str) if ref_id_str.isdigit() else None
                steps.append(
                    IssueTestStep(
                        step_number=step_id,
                        action="[Shared Step Reference]",
                        expected_result=None,
                        shared_step_reference=ref_id,
                    )
                )
                continue

            # Regular action step - extract parameterized strings
            params = step_elem.findall(".//parameterizedString")
            action = params[0].text.strip() if len(params) > 0 and params[0].text else ""
            expected = params[1].text.strip() if len(params) > 1 and params[1].text else None

            if action or expected:  # Only add if we have content
                steps.append(
                    IssueTestStep(
                        step_number=step_id,
                        action=action,
                        expected_result=expected,
                        shared_step_reference=None,
                    )
                )

        return steps if steps else None

    except ET.ParseError:
        # XML parse error - return None to fall back to raw data
        return None
    except (ValueError, AttributeError):
        # Other parsing errors
        return None


def _extract_repro_steps(fields: dict) -> list[str] | None:
    """Extract reproduction steps from Bug issues.

    ADO Bugs store repro steps in Microsoft.VSTS.TCM.ReproSteps as HTML.
    We'll normalize it similar to acceptance criteria.

    Args:
        fields: Raw fields dictionary from ADO API

    Returns:
        List of reproduction step strings, or None if not present
    """
    repro_html = fields.get("Microsoft.VSTS.TCM.ReproSteps")
    if not repro_html:
        return None

    # Reuse acceptance criteria normalization for HTML parsing
    return _normalize_acceptance_criteria(repro_html)
