"""Comprehensive tests for issue service - covering critical untested paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_agent_kit.models.issue import Comment, Issue, RelatedIssue, TestStep
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.issue_providers.base import IssueProviderError
from open_agent_kit.services.issue_service import (
    IssueService,
    _clean_html,
    _detect_issue_changes,
    _format_timestamp,
    _render_context_summary,
    _render_plan,
    _simplify_relation_type,
)


def _setup_project(tmp_path: Path) -> ConfigService:
    """Create a minimal project with config."""
    (tmp_path / ".oak").mkdir(exist_ok=True)
    config_service = ConfigService(tmp_path)
    config_service.create_default_config()
    return config_service


# -----------------------------------------------------------------------------
# Provider management tests
# -----------------------------------------------------------------------------


class TestResolveProviderKey:
    """Tests for resolve_provider_key method."""

    def test_resolve_explicit_provider(self, tmp_path: Path) -> None:
        """Explicit provider key should be used when provided."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)
        # Note: This will fail validation but should resolve the key
        with pytest.raises(IssueProviderError):
            service.resolve_provider_key("invalid_provider")

    def test_resolve_from_config(self, tmp_path: Path) -> None:
        """Should use config provider when none specified."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")
        service = IssueService(tmp_path)
        resolved = service.resolve_provider_key()
        assert resolved == "ado"

    def test_resolve_raises_when_no_provider_set(self, tmp_path: Path) -> None:
        """Should raise when no provider configured and none specified."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)
        with pytest.raises(IssueProviderError) as exc_info:
            service.resolve_provider_key()
        assert "not set" in str(exc_info.value).lower() or "provider" in str(exc_info.value).lower()

    def test_resolve_raises_for_invalid_provider(self, tmp_path: Path) -> None:
        """Should raise for unknown provider key."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)
        with pytest.raises(IssueProviderError) as exc_info:
            service.resolve_provider_key("unknown_provider")
        assert "invalid" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()


class TestGetProvider:
    """Tests for get_provider method."""

    def test_get_ado_provider(self, tmp_path: Path) -> None:
        """Should instantiate Azure DevOps provider."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider(
            "ado", organization="test", project="test", pat_env="ADO_PAT"
        )
        service = IssueService(tmp_path, environment={"ADO_PAT": "token"})
        provider = service.get_provider("ado")
        assert provider.key == "ado"

    def test_get_github_provider(self, tmp_path: Path) -> None:
        """Should instantiate GitHub provider."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider(
            "github", owner="test", repo="test", token_env="GITHUB_TOKEN"
        )
        service = IssueService(tmp_path, environment={"GITHUB_TOKEN": "token"})
        provider = service.get_provider("github")
        assert provider.key == "github"


# -----------------------------------------------------------------------------
# Artifact management tests
# -----------------------------------------------------------------------------


class TestFindIssueDir:
    """Tests for find_issue_dir method."""

    def test_find_existing_issue_dir(self, tmp_path: Path) -> None:
        """Should find existing issue directory."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        issue = Issue(provider="ado", identifier="12345", title="Test")
        service.write_context(issue)

        result = service.find_issue_dir("12345", "ado")
        assert result is not None
        provider, path = result
        assert provider == "ado"
        assert path.exists()

    def test_find_nonexistent_issue_dir(self, tmp_path: Path) -> None:
        """Should return None for non-existent issue."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        result = service.find_issue_dir("99999", "ado")
        assert result is None


class TestLoadIssue:
    """Tests for load_issue and read_context methods."""

    def test_load_issue_success(self, tmp_path: Path) -> None:
        """Should load issue from context file."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        original = Issue(
            provider="ado",
            identifier="12345",
            title="Test Issue",
            description="Test description",
            tags=["bug", "urgent"],
        )
        service.write_context(original)

        loaded = service.load_issue("ado", "12345")
        assert loaded.identifier == "12345"
        assert loaded.title == "Test Issue"
        assert loaded.description == "Test description"
        assert "bug" in loaded.tags

    def test_load_issue_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing context."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)

        with pytest.raises(FileNotFoundError):
            service.load_issue("ado", "nonexistent")

    def test_read_context_validates_data(self, tmp_path: Path) -> None:
        """read_context should use model validation."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        original = Issue(provider="ado", identifier="12345", title="Test")
        service.write_context(original)

        loaded = service.read_context("ado", "12345")
        assert loaded.identifier == "12345"


class TestReadPlan:
    """Tests for read_plan method."""

    def test_read_plan_success(self, tmp_path: Path) -> None:
        """Should read plan markdown from file."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        issue = Issue(provider="ado", identifier="12345", title="Test Issue")
        service.write_plan(issue)

        plan_content = service.read_plan("ado", "12345")
        assert "Test Issue" in plan_content
        assert "12345" in plan_content

    def test_read_plan_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing plan."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)

        with pytest.raises(FileNotFoundError):
            service.read_plan("ado", "nonexistent")


class TestWriteContextWithRelated:
    """Tests for write_context with related items."""

    def test_write_context_with_related_items(self, tmp_path: Path) -> None:
        """Should write related items to subdirectory."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        main_issue = Issue(provider="ado", identifier="100", title="Main Issue")
        related = [
            Issue(provider="ado", identifier="101", title="Related 1"),
            Issue(provider="ado", identifier="102", title="Related 2"),
        ]

        service.write_context(main_issue, related_items=related)

        # Check related items were written
        related_dir = service.get_issue_dir("ado", "100") / "related"
        assert related_dir.exists()
        assert (related_dir / "101" / "context.json").exists()
        assert (related_dir / "102" / "context.json").exists()
        assert (related_dir / "101" / "context-summary.md").exists()

    def test_write_context_creates_summary(self, tmp_path: Path) -> None:
        """Should create context-summary.md alongside context.json."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test Issue",
            description="Test description",
        )
        service.write_context(issue)

        summary_path = service.get_issue_dir("ado", "12345") / "context-summary.md"
        assert summary_path.exists()
        content = summary_path.read_text()
        assert "Test Issue" in content


class TestUpdateBranchName:
    """Tests for update_branch_name method."""

    def test_update_branch_name_success(self, tmp_path: Path) -> None:
        """Should update branch name in context file."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        issue = Issue(provider="ado", identifier="12345", title="Test")
        service.write_context(issue)

        service.update_branch_name("ado", "12345", "feature/12345-test")

        loaded = service.load_issue("ado", "12345")
        assert loaded.branch_name == "feature/12345-test"

    def test_update_branch_name_nonexistent_silently_fails(self, tmp_path: Path) -> None:
        """Should not raise for non-existent context (non-fatal)."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)

        # Should not raise - this is a convenience feature
        service.update_branch_name("ado", "nonexistent", "some-branch")


# -----------------------------------------------------------------------------
# Manifest and resolution tests
# -----------------------------------------------------------------------------


class TestManifestOperations:
    """Tests for manifest-based issue resolution."""

    def test_record_and_resolve_plan(self, tmp_path: Path) -> None:
        """Should record plan and resolve issue from manifest."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        service.record_plan("ado", "12345", "feature/12345-test")

        # Resolve without explicit issue should find from manifest
        provider, issue_id = service.resolve_issue(None, None)
        assert provider == "ado"
        assert issue_id == "12345"

    def test_resolve_with_explicit_issue(self, tmp_path: Path) -> None:
        """Should resolve explicit issue with provider from manifest."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        service.record_plan("ado", "12345", "feature/12345-test")

        provider, issue_id = service.resolve_issue("12345", None)
        assert provider == "ado"
        assert issue_id == "12345"

    def test_record_plan_replaces_existing(self, tmp_path: Path) -> None:
        """Recording same issue should update, not duplicate."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("ado", organization="test", project="test")

        service = IssueService(tmp_path)
        service.record_plan("ado", "12345", "old-branch")
        service.record_plan("ado", "12345", "new-branch")

        manifest = service._load_manifest()
        matching = [e for e in manifest if e.get("issue") == "12345"]
        assert len(matching) == 1
        assert matching[0]["branch"] == "new-branch"


# -----------------------------------------------------------------------------
# Rendering helper tests
# -----------------------------------------------------------------------------


class TestRenderPlan:
    """Tests for _render_plan helper."""

    def test_render_basic_plan(self) -> None:
        """Should render basic plan markdown."""
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test Issue",
            description="Test description",
            state="Active",
        )
        content = _render_plan(issue, None)
        assert "# Issue 12345: Test Issue" in content
        assert "Test description" in content
        assert "Active" in content

    def test_render_plan_with_relations(self) -> None:
        """Should render relations section."""
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test",
            relations=[
                RelatedIssue(
                    relation_type="Parent",
                    identifier="100",
                    title="Parent Issue",
                ),
            ],
        )
        content = _render_plan(issue, None)
        assert "Parent" in content
        assert "100" in content

    def test_render_plan_with_related_items(self) -> None:
        """Should render parent/child context sections."""
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test",
            relations=[
                RelatedIssue(
                    relation_type="System.LinkTypes.Hierarchy-Reverse",
                    identifier="100",
                ),
            ],
        )
        related = [Issue(provider="ado", identifier="100", title="Parent Task")]
        content = _render_plan(issue, None, related_items=related)
        assert "Parent Issues" in content or "Parent Task" in content


class TestRenderContextSummary:
    """Tests for _render_context_summary helper."""

    def test_render_basic_summary(self) -> None:
        """Should render basic context summary."""
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test Issue",
            state="Active",
            description="Test description",
        )
        content = _render_context_summary(issue)
        assert "# 12345: Test Issue" in content
        assert "Active" in content
        assert "Test description" in content

    def test_render_summary_with_test_steps(self) -> None:
        """Should render test steps for Test Case type."""
        issue = Issue(
            provider="ado",
            identifier="TC-1",
            title="Test Case",
            issue_type="Test Case",
            test_steps=[
                TestStep(step_number=1, action="Click button", expected_result="Dialog opens"),
                TestStep(step_number=2, action="Enter data", expected_result=None),
            ],
        )
        content = _render_context_summary(issue)
        assert "Test Steps" in content
        assert "Click button" in content
        assert "Dialog opens" in content

    def test_render_summary_with_repro_steps(self) -> None:
        """Should render repro steps for Bug type."""
        issue = Issue(
            provider="ado",
            identifier="BUG-1",
            title="Bug Report",
            issue_type="Bug",
            repro_steps=["Open app", "Click button", "Observe crash"],
        )
        content = _render_context_summary(issue)
        assert "Reproduction Steps" in content
        assert "Open app" in content

    def test_render_summary_with_comments(self) -> None:
        """Should render comments section."""
        issue = Issue(
            provider="ado",
            identifier="12345",
            title="Test",
            comments=[
                Comment(
                    comment_id="1",
                    text="This is a comment",
                    created_by="Alice",
                    created_date="2025-01-15T10:00:00Z",
                ),
            ],
        )
        content = _render_context_summary(issue)
        assert "Comments" in content
        assert "This is a comment" in content
        assert "Alice" in content


class TestDetectIssueChanges:
    """Tests for _detect_issue_changes helper."""

    def test_detect_no_changes(self) -> None:
        """Should detect when issues are identical."""
        old = Issue(provider="ado", identifier="1", title="Test", state="Active")
        new = Issue(provider="ado", identifier="1", title="Test", state="Active")
        changes = _detect_issue_changes(old, new)
        assert not changes["has_changes"]

    def test_detect_title_change(self) -> None:
        """Should detect title change."""
        old = Issue(provider="ado", identifier="1", title="Old Title")
        new = Issue(provider="ado", identifier="1", title="New Title")
        changes = _detect_issue_changes(old, new)
        assert changes["title_changed"]
        assert changes["has_changes"]

    def test_detect_state_change(self) -> None:
        """Should detect state change."""
        old = Issue(provider="ado", identifier="1", title="Test", state="Active")
        new = Issue(provider="ado", identifier="1", title="Test", state="Closed")
        changes = _detect_issue_changes(old, new)
        assert changes["state_changed"]
        assert changes["has_changes"]

    def test_detect_relations_added(self) -> None:
        """Should detect new relations."""
        old = Issue(provider="ado", identifier="1", title="Test")
        new = Issue(
            provider="ado",
            identifier="1",
            title="Test",
            relations=[RelatedIssue(relation_type="Related", identifier="100")],
        )
        changes = _detect_issue_changes(old, new)
        assert changes["relations_added"] == 1
        assert changes["has_changes"]

    def test_detect_acceptance_criteria_change(self) -> None:
        """Should detect acceptance criteria change."""
        old = Issue(provider="ado", identifier="1", title="Test", acceptance_criteria=["AC1"])
        new = Issue(
            provider="ado", identifier="1", title="Test", acceptance_criteria=["AC1", "AC2"]
        )
        changes = _detect_issue_changes(old, new)
        assert changes["acceptance_criteria_changed"]
        assert changes["has_changes"]


class TestCleanHtml:
    """Tests for _clean_html helper."""

    def test_clean_basic_html(self) -> None:
        """Should remove HTML tags."""
        html = "<p>Hello <b>World</b></p>"
        result = _clean_html(html)
        assert result == "Hello World"

    def test_clean_br_tags(self) -> None:
        """Should convert br tags to newlines."""
        html = "Line 1<br/>Line 2<BR>Line 3"
        result = _clean_html(html)
        assert "Line 1" in result
        assert "Line 2" in result

    def test_clean_list_items(self) -> None:
        """Should convert list items to markdown."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = _clean_html(html)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_clean_html_entities(self) -> None:
        """Should decode HTML entities."""
        html = "Hello&nbsp;World &amp; Friends"
        result = _clean_html(html)
        assert "Hello" in result
        assert "World" in result
        assert "&" in result


class TestSimplifyRelationType:
    """Tests for _simplify_relation_type helper."""

    def test_simplify_hierarchy_forward(self) -> None:
        """Should simplify child relation."""
        result = _simplify_relation_type("System.LinkTypes.Hierarchy-Forward")
        assert result == "Child Tasks"

    def test_simplify_hierarchy_reverse(self) -> None:
        """Should simplify parent relation."""
        result = _simplify_relation_type("System.LinkTypes.Hierarchy-Reverse")
        assert result == "Parent"

    def test_passthrough_unknown(self) -> None:
        """Should pass through unknown relation types."""
        result = _simplify_relation_type("Custom.RelationType")
        assert result == "Custom.RelationType"


class TestFormatTimestamp:
    """Tests for _format_timestamp helper."""

    def test_format_iso_timestamp(self) -> None:
        """Should format ISO 8601 timestamp."""
        result = _format_timestamp("2025-01-15T10:30:00Z")
        assert "Jan" in result
        assert "15" in result
        assert "2025" in result

    def test_format_invalid_timestamp(self) -> None:
        """Should return original on parse failure."""
        result = _format_timestamp("invalid")
        assert result == "invalid"


# -----------------------------------------------------------------------------
# Git helper tests
# -----------------------------------------------------------------------------


class TestGitHelpers:
    """Tests for git helper methods."""

    def test_build_branch_name(self, tmp_path: Path) -> None:
        """Should build branch name using provider."""
        config_service = _setup_project(tmp_path)
        config_service.update_issue_provider("github", owner="test", repo="test", token_env="TOKEN")

        service = IssueService(tmp_path, environment={"TOKEN": "test"})
        issue = Issue(provider="github", identifier="42", title="Fix the bug")

        branch_name = service.build_branch_name(issue)
        assert "42" in branch_name

    def test_branch_exists_false(self, tmp_path: Path) -> None:
        """Should return False for non-existent branch."""
        _setup_project(tmp_path)
        service = IssueService(tmp_path)

        # Not a git repo, so branch check should fail gracefully
        result = service.branch_exists("nonexistent-branch", tmp_path)
        assert result is False
