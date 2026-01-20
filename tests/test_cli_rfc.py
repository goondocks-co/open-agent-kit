"""Tests for oak rfc commands."""

from pathlib import Path

from open_agent_kit.features.strategic_planning.rfc import RFCService


def test_rfc_create_generates_file(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that rfc create generates an RFC file."""
    service = RFCService(project_root=initialized_project)
    rfc = service.create_rfc(
        title=sample_rfc_data["title"],
        author=sample_rfc_data["author"],
        template_name=sample_rfc_data["template"],
        tags=sample_rfc_data["tags"],
    )
    assert rfc.path is not None
    assert rfc.path.exists()
    assert rfc.path.is_file()


def test_rfc_create_has_correct_content(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that created RFC has expected content."""
    service = RFCService(project_root=initialized_project)
    rfc = service.create_rfc(
        title=sample_rfc_data["title"],
        author=sample_rfc_data["author"],
        template_name=sample_rfc_data["template"],
    )
    assert rfc.path is not None
    content = rfc.path.read_text(encoding="utf-8")
    assert "# RFC" in content
    assert sample_rfc_data["title"] in content
    assert sample_rfc_data["author"] in content
    assert "## Motivation" in content or "## Objective" in content
    assert "## Detailed Design" in content or "## Problem Description" in content


def test_rfc_create_auto_numbers(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that RFC numbers auto-increment."""
    service = RFCService(project_root=initialized_project)
    rfc1 = service.create_rfc(title="First RFC", author=sample_rfc_data["author"])
    rfc2 = service.create_rfc(title="Second RFC", author=sample_rfc_data["author"])
    assert rfc1.number == "001"
    assert rfc2.number == "002"


def test_rfc_list_shows_created_rfcs(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that list command shows created RFCs."""
    service = RFCService(project_root=initialized_project)
    service.create_rfc(title="Test RFC 1", author=sample_rfc_data["author"])
    service.create_rfc(title="Test RFC 2", author=sample_rfc_data["author"])
    rfcs = service.list_rfcs()
    assert len(rfcs) == 2
    assert any(rfc.title == "Test RFC 1" for rfc in rfcs)
    assert any(rfc.title == "Test RFC 2" for rfc in rfcs)


def test_rfc_list_filters_by_status(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that list command can filter by status."""
    service = RFCService(project_root=initialized_project)
    service.create_rfc(title="Draft RFC", author=sample_rfc_data["author"])
    draft_rfcs = service.list_rfcs(status="draft")
    assert len(draft_rfcs) == 1
    assert draft_rfcs[0].status.value == "draft"


def test_rfc_validate_checks_structure(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that validate checks RFC structure."""
    service = RFCService(project_root=initialized_project)
    rfc = service.create_rfc(title=sample_rfc_data["title"], author=sample_rfc_data["author"])
    is_valid, issues = service.validate_rfc(rfc.path)
    assert isinstance(is_valid, bool)
    assert isinstance(issues, list)
    placeholder_issues = [i for i in issues if "Placeholder content detected" in i]
    assert len(placeholder_issues) > 0, "Template should contain placeholder content"


def test_rfc_create_with_tags(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test creating RFC with tags."""
    service = RFCService(project_root=initialized_project)
    tags = ["testing", "automation", "cli"]
    rfc = service.create_rfc(
        title=sample_rfc_data["title"], author=sample_rfc_data["author"], tags=tags
    )
    assert rfc.tags == tags


def test_rfc_create_with_custom_number(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test creating RFC with custom number."""
    service = RFCService(project_root=initialized_project)
    rfc = service.create_rfc(
        title=sample_rfc_data["title"], author=sample_rfc_data["author"], rfc_number="999"
    )
    assert rfc.number == "999"


def test_rfc_filename_format(initialized_project: Path, sample_rfc_data: dict) -> None:
    """Test that RFC filename follows expected format."""
    service = RFCService(project_root=initialized_project)
    rfc = service.create_rfc(title="My Test RFC Document", author=sample_rfc_data["author"])
    assert rfc.path is not None
    filename = rfc.path.name
    assert filename.startswith("RFC-")
    assert filename.endswith(".md")
    assert "001" in filename
