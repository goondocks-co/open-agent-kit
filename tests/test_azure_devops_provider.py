"""Comprehensive tests for Azure DevOps issue provider."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from open_agent_kit.models.config import AzureDevOpsProviderConfig
from open_agent_kit.services.issue_providers.azure_devops import (
    AzureDevOpsProvider,
    _extract_repro_steps,
    _extract_test_steps,
    _normalize_acceptance_criteria,
    _normalize_relation,
)
from open_agent_kit.services.issue_providers.base import IssueProviderError


class DummyResponse:
    """Mock HTTP response for testing."""

    def __init__(self, data: dict, status_code: int = 200):
        self.data = data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code),
            )

    def json(self) -> dict:
        return self.data


# -----------------------------------------------------------------------------
# Validation tests
# -----------------------------------------------------------------------------


class TestAzureDevOpsValidation:
    """Tests for Azure DevOps provider validation."""

    def test_validate_missing_organization(self) -> None:
        """Should flag missing organization."""
        settings = AzureDevOpsProviderConfig(project="test", pat_env="ADO_PAT")
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})
        issues = provider.validate()
        assert any("organization" in issue.lower() for issue in issues)

    def test_validate_missing_project(self) -> None:
        """Should flag missing project."""
        settings = AzureDevOpsProviderConfig(organization="test", pat_env="ADO_PAT")
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})
        issues = provider.validate()
        assert any("project" in issue.lower() for issue in issues)

    def test_validate_missing_pat_env(self) -> None:
        """Should flag missing PAT environment variable name."""
        settings = AzureDevOpsProviderConfig(organization="test", project="test")
        provider = AzureDevOpsProvider(settings, {})
        issues = provider.validate()
        assert any("pat" in issue.lower() for issue in issues)

    def test_validate_missing_pat_value(self) -> None:
        """Should flag when PAT env var is not set."""
        settings = AzureDevOpsProviderConfig(organization="test", project="test", pat_env="ADO_PAT")
        provider = AzureDevOpsProvider(settings, {})  # Empty environment
        issues = provider.validate()
        assert any("ADO_PAT" in issue for issue in issues)

    def test_validate_all_configured(self) -> None:
        """Should return no issues when fully configured."""
        settings = AzureDevOpsProviderConfig(organization="test", project="test", pat_env="ADO_PAT")
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})
        issues = provider.validate()
        assert len(issues) == 0


# -----------------------------------------------------------------------------
# Fetch tests
# -----------------------------------------------------------------------------


class TestAzureDevOpsFetch:
    """Tests for Azure DevOps provider fetch method."""

    def _create_provider(self, environment: dict | None = None) -> AzureDevOpsProvider:
        """Create a configured provider for testing."""
        settings = AzureDevOpsProviderConfig(
            organization="contoso", project="webapp", pat_env="ADO_PAT"
        )
        env = environment or {"ADO_PAT": "test-token"}
        return AzureDevOpsProvider(settings, env)

    def test_fetch_basic_issue(self, monkeypatch: Any) -> None:
        """Should parse basic work item response."""
        provider = self._create_provider()

        payload = {
            "id": 12345,
            "fields": {
                "System.Title": "Fix login bug",
                "System.Description": "Users cannot login",
                "System.State": "Active",
                "System.Tags": "bug; priority-high",
                "System.AssignedTo": {"displayName": "Alice"},
                "System.AreaPath": "WebApp\\Auth",
                "System.IterationPath": "WebApp\\Sprint 1",
                "System.WorkItemType": "Bug",
            },
            "_links": {"html": {"href": "https://dev.azure.com/contoso/webapp/_workitems/12345"}},
        }

        # Mock the comments endpoint to return empty
        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse({"comments": []})
            return DummyResponse(payload)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        issue = provider.fetch("12345")

        assert issue.identifier == "12345"
        assert issue.title == "Fix login bug"
        assert issue.description == "Users cannot login"
        assert issue.state == "Active"
        assert issue.assigned_to == "Alice"
        assert issue.area_path == "WebApp\\Auth"
        assert "bug" in issue.tags
        assert "priority-high" in issue.tags
        assert issue.issue_type == "Bug"

    def test_fetch_with_relations(self, monkeypatch: Any) -> None:
        """Should parse work item with relations."""
        provider = self._create_provider()

        payload = {
            "id": 100,
            "fields": {
                "System.Title": "Parent Task",
                "System.WorkItemType": "Task",
            },
            "relations": [
                {
                    "rel": "System.LinkTypes.Hierarchy-Forward",
                    "url": "https://dev.azure.com/contoso/webapp/_apis/wit/workitems/101",
                    "attributes": {"name": "Child"},
                },
                {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": "https://dev.azure.com/contoso/webapp/_apis/wit/workitems/99",
                    "attributes": {},
                },
            ],
        }

        batch_response = {
            "value": [
                {"id": 101, "fields": {"System.Title": "Child Task 1"}},
                {"id": 99, "fields": {"System.Title": "Epic Feature"}},
            ]
        }

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse({"comments": []})
            return DummyResponse(payload)

        def mock_post(url: str, **kwargs: Any) -> DummyResponse:
            return DummyResponse(batch_response)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )
        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.post",
            mock_post,
        )

        issue = provider.fetch("100")

        assert len(issue.relations) == 2
        child_rel = next(r for r in issue.relations if r.identifier == "101")
        assert child_rel.title == "Child Task 1"
        assert child_rel.relation_type == "System.LinkTypes.Hierarchy-Forward"

    def test_fetch_with_acceptance_criteria(self, monkeypatch: Any) -> None:
        """Should parse acceptance criteria from rich text."""
        provider = self._create_provider()

        payload = {
            "id": 200,
            "fields": {
                "System.Title": "User Story",
                "System.WorkItemType": "User Story",
                "Microsoft.VSTS.Common.AcceptanceCriteria": "- Must validate input\n- Should show error message\n- Must log failures",
            },
        }

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse({"comments": []})
            return DummyResponse(payload)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        issue = provider.fetch("200")

        assert len(issue.acceptance_criteria) == 3
        assert "Must validate input" in issue.acceptance_criteria
        assert "Should show error message" in issue.acceptance_criteria

    def test_fetch_with_comments(self, monkeypatch: Any) -> None:
        """Should fetch and parse comments."""
        provider = self._create_provider()

        issue_payload = {
            "id": 300,
            "fields": {
                "System.Title": "Task with Comments",
                "System.WorkItemType": "Task",
            },
        }

        comments_payload = {
            "comments": [
                {
                    "id": 1,
                    "text": "First comment",
                    "createdBy": {"displayName": "Alice"},
                    "createdDate": "2025-01-15T10:00:00Z",
                },
                {
                    "id": 2,
                    "text": "Second comment",
                    "createdBy": {"displayName": "Bob"},
                    "createdDate": "2025-01-16T11:00:00Z",
                },
            ]
        }

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse(comments_payload)
            return DummyResponse(issue_payload)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        issue = provider.fetch("300")

        assert len(issue.comments) == 2
        assert issue.comments[0].text == "First comment"
        assert issue.comments[0].created_by == "Alice"
        assert issue.comments[1].text == "Second comment"

    def test_fetch_test_case_with_steps(self, monkeypatch: Any) -> None:
        """Should parse test steps XML for Test Case type."""
        provider = self._create_provider()

        test_steps_xml = """
        <steps>
            <step id="1" type="ActionStep">
                <parameterizedString>Click login button</parameterizedString>
                <parameterizedString>Login form appears</parameterizedString>
            </step>
            <step id="2" type="ActionStep">
                <parameterizedString>Enter credentials</parameterizedString>
                <parameterizedString>Credentials accepted</parameterizedString>
            </step>
        </steps>
        """

        payload = {
            "id": 400,
            "fields": {
                "System.Title": "Login Test Case",
                "System.WorkItemType": "Test Case",
                "Microsoft.VSTS.TCM.Steps": test_steps_xml,
            },
        }

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse({"comments": []})
            return DummyResponse(payload)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        issue = provider.fetch("400")

        assert issue.issue_type == "Test Case"
        assert issue.test_steps is not None
        assert len(issue.test_steps) == 2
        assert issue.test_steps[0].action == "Click login button"
        assert issue.test_steps[0].expected_result == "Login form appears"

    def test_fetch_bug_with_repro_steps(self, monkeypatch: Any) -> None:
        """Should parse reproduction steps for Bug type."""
        provider = self._create_provider()

        payload = {
            "id": 500,
            "fields": {
                "System.Title": "Crash on Submit",
                "System.WorkItemType": "Bug",
                "Microsoft.VSTS.TCM.ReproSteps": "1. Open form\n2. Click submit\n3. App crashes",
            },
        }

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            if "comments" in url:
                return DummyResponse({"comments": []})
            return DummyResponse(payload)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        issue = provider.fetch("500")

        assert issue.issue_type == "Bug"
        assert issue.repro_steps is not None
        assert len(issue.repro_steps) == 3

    def test_fetch_validation_failure(self) -> None:
        """Should raise IssueProviderError on validation failure."""
        settings = AzureDevOpsProviderConfig()  # Missing required fields
        provider = AzureDevOpsProvider(settings, {})

        with pytest.raises(IssueProviderError):
            provider.fetch("12345")

    def test_fetch_http_error(self, monkeypatch: Any) -> None:
        """Should raise IssueProviderError on HTTP error."""
        provider = self._create_provider()

        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            return DummyResponse({}, status_code=404)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        with pytest.raises(IssueProviderError) as exc_info:
            provider.fetch("nonexistent")
        assert "API" in str(exc_info.value) or "error" in str(exc_info.value).lower()

    def test_fetch_invalid_response_structure(self, monkeypatch: Any) -> None:
        """Should raise IssueProviderError for invalid response."""
        provider = self._create_provider()

        # Response missing 'fields'
        def mock_get(url: str, **kwargs: Any) -> DummyResponse:
            return DummyResponse({"id": 12345})  # Missing 'fields'

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.get",
            mock_get,
        )

        with pytest.raises(IssueProviderError) as exc_info:
            provider.fetch("12345")
        assert "invalid" in str(exc_info.value).lower() or "response" in str(exc_info.value).lower()


# -----------------------------------------------------------------------------
# Helper function tests
# -----------------------------------------------------------------------------


class TestNormalizeAcceptanceCriteria:
    """Tests for _normalize_acceptance_criteria helper."""

    def test_normalize_bullet_list(self) -> None:
        """Should parse bullet list."""
        text = "- Item 1\n- Item 2\n- Item 3"
        result = _normalize_acceptance_criteria(text)
        assert result == ["Item 1", "Item 2", "Item 3"]

    def test_normalize_asterisk_list(self) -> None:
        """Should parse asterisk list."""
        text = "* First\n* Second"
        result = _normalize_acceptance_criteria(text)
        assert result == ["First", "Second"]

    def test_normalize_mixed_bullets(self) -> None:
        """Should handle mixed bullet styles."""
        text = "- Dash item\n* Asterisk item\n• Bullet item"
        result = _normalize_acceptance_criteria(text)
        assert len(result) == 3

    def test_normalize_empty_lines(self) -> None:
        """Should skip empty lines."""
        text = "- Item 1\n\n- Item 2\n\n"
        result = _normalize_acceptance_criteria(text)
        assert result == ["Item 1", "Item 2"]

    def test_normalize_none_input(self) -> None:
        """Should return empty list for None."""
        result = _normalize_acceptance_criteria(None)
        assert result == []

    def test_normalize_empty_string(self) -> None:
        """Should return empty list for empty string."""
        result = _normalize_acceptance_criteria("")
        assert result == []


class TestNormalizeRelation:
    """Tests for _normalize_relation helper."""

    def test_normalize_with_url_id(self) -> None:
        """Should extract ID from URL."""
        relation = {
            "rel": "System.LinkTypes.Hierarchy-Forward",
            "url": "https://dev.azure.com/org/proj/_apis/wit/workitems/12345",
            "attributes": {"name": "Child"},
        }
        result = _normalize_relation(relation)
        assert result.identifier == "12345"
        assert result.relation_type == "System.LinkTypes.Hierarchy-Forward"

    def test_normalize_without_numeric_id(self) -> None:
        """Should handle URL without numeric ID."""
        relation = {
            "rel": "Related",
            "url": "https://example.com/something",
            "attributes": {},
        }
        result = _normalize_relation(relation)
        assert result.identifier is None
        assert result.url == "https://example.com/something"

    def test_normalize_with_attributes(self) -> None:
        """Should copy safe attributes to metadata."""
        relation = {
            "rel": "Dependency",
            "url": "https://dev.azure.com/org/proj/_apis/wit/workitems/999",
            "attributes": {"name": "Blocked By", "isLocked": False, "count": 5},
        }
        result = _normalize_relation(relation)
        assert result.additional_metadata.get("name") == "Blocked By"
        assert result.additional_metadata.get("count") == "5"


class TestExtractTestSteps:
    """Tests for _extract_test_steps helper."""

    def test_extract_valid_xml(self) -> None:
        """Should parse valid test steps XML."""
        fields = {
            "Microsoft.VSTS.TCM.Steps": """
            <steps>
                <step id="1" type="ActionStep">
                    <parameterizedString>Do something</parameterizedString>
                    <parameterizedString>Something happens</parameterizedString>
                </step>
            </steps>
            """
        }
        result = _extract_test_steps(fields)
        assert result is not None
        assert len(result) == 1
        assert result[0].step_number == 1
        assert result[0].action == "Do something"
        assert result[0].expected_result == "Something happens"

    def test_extract_shared_step_reference(self) -> None:
        """Should handle shared step references."""
        fields = {
            "Microsoft.VSTS.TCM.Steps": """
            <steps>
                <step id="1" type="SharedStepReference" ref="500">
                </step>
            </steps>
            """
        }
        result = _extract_test_steps(fields)
        assert result is not None
        assert len(result) == 1
        assert result[0].shared_step_reference == 500

    def test_extract_missing_steps(self) -> None:
        """Should return None when no steps field."""
        fields = {"System.Title": "Test"}
        result = _extract_test_steps(fields)
        assert result is None

    def test_extract_invalid_xml(self) -> None:
        """Should return None for invalid XML."""
        fields = {"Microsoft.VSTS.TCM.Steps": "not valid xml <><>"}
        result = _extract_test_steps(fields)
        assert result is None

    def test_extract_empty_steps(self) -> None:
        """Should return None for empty steps."""
        fields = {"Microsoft.VSTS.TCM.Steps": "<steps></steps>"}
        result = _extract_test_steps(fields)
        assert result is None


class TestExtractReproSteps:
    """Tests for _extract_repro_steps helper."""

    def test_extract_repro_steps(self) -> None:
        """Should parse reproduction steps."""
        fields = {"Microsoft.VSTS.TCM.ReproSteps": "1. Open app\n2. Click button\n3. Observe error"}
        result = _extract_repro_steps(fields)
        assert result is not None
        assert len(result) == 3

    def test_extract_missing_repro_steps(self) -> None:
        """Should return None when no repro steps."""
        fields = {"System.Title": "Bug"}
        result = _extract_repro_steps(fields)
        assert result is None


# -----------------------------------------------------------------------------
# Batch fetch tests
# -----------------------------------------------------------------------------


class TestBatchFetchTitles:
    """Tests for _batch_fetch_titles method."""

    def test_batch_fetch_success(self, monkeypatch: Any) -> None:
        """Should fetch titles for multiple IDs."""
        settings = AzureDevOpsProviderConfig(
            organization="contoso", project="webapp", pat_env="ADO_PAT"
        )
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})

        batch_response = {
            "value": [
                {"id": 1, "fields": {"System.Title": "First Issue"}},
                {"id": 2, "fields": {"System.Title": "Second Issue"}},
            ]
        }

        def mock_post(url: str, **kwargs: Any) -> DummyResponse:
            return DummyResponse(batch_response)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.post",
            mock_post,
        )

        headers = {"Authorization": "Basic test"}
        result = provider._batch_fetch_titles(["1", "2"], headers)

        assert result["1"] == "First Issue"
        assert result["2"] == "Second Issue"

    def test_batch_fetch_empty_list(self) -> None:
        """Should return empty dict for empty ID list."""
        settings = AzureDevOpsProviderConfig(
            organization="contoso", project="webapp", pat_env="ADO_PAT"
        )
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})

        result = provider._batch_fetch_titles([], {})
        assert result == {}

    def test_batch_fetch_http_error(self, monkeypatch: Any) -> None:
        """Should return empty dict on HTTP error."""
        settings = AzureDevOpsProviderConfig(
            organization="contoso", project="webapp", pat_env="ADO_PAT"
        )
        provider = AzureDevOpsProvider(settings, {"ADO_PAT": "token"})

        def mock_post(url: str, **kwargs: Any) -> DummyResponse:
            return DummyResponse({}, status_code=500)

        monkeypatch.setattr(
            "open_agent_kit.services.issue_providers.azure_devops.httpx.post",
            mock_post,
        )

        headers = {"Authorization": "Basic test"}
        result = provider._batch_fetch_titles(["1", "2"], headers)
        assert result == {}
