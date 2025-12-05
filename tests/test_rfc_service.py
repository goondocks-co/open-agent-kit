from datetime import datetime, timedelta
from pathlib import Path

import pytest

from open_agent_kit.config.settings import validation_settings
from open_agent_kit.models.rfc import RFCStatus
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.rfc_service import RFCService
from open_agent_kit.utils import read_file, write_file


@pytest.fixture(name="configured_project")
def fixture_configured_project(tmp_path: Path) -> RFCService:
    """Create a temporary project root with default configuration."""
    config_service = ConfigService(tmp_path)
    config_service.create_default_config()
    return RFCService(tmp_path)


def _update_rfc_metadata(
    rfc_path: Path | None, *, status: RFCStatus = RFCStatus.DRAFT, date: datetime | None = None
) -> None:
    """Replace metadata in an RFC file for testing purposes."""
    if rfc_path is None:
        raise ValueError("RFC path is required for metadata updates")
    lines = read_file(rfc_path).splitlines()
    for index, line in enumerate(lines):
        if line.startswith("**Status:**"):
            lines[index] = f"**Status:** {status.value}"
        if date is not None and line.startswith("**Date:**"):
            lines[index] = f"**Date:** {date.strftime('%Y-%m-%d')}"
    write_file(rfc_path, "\n".join(lines) + "\n")


def test_validate_rfc_detects_placeholders(configured_project: RFCService) -> None:
    rfc = configured_project.create_rfc(title="Placeholder RFC", author="Test Author")
    is_valid, issues = configured_project.validate_rfc(rfc.path)
    assert not is_valid
    assert any("Placeholder content detected" in issue for issue in issues)


@pytest.mark.parametrize("template_name", ["engineering", "architecture", "feature", "process"])
def test_templates_surface_guidance_placeholders(
    configured_project: RFCService, template_name: str
) -> None:
    rfc = configured_project.create_rfc(
        title=f"{template_name.title()} Workflow",
        author="Guided Author",
        template_name=template_name,
    )
    is_valid, issues = configured_project.validate_rfc(rfc.path)
    assert not is_valid
    assert any("Placeholder content detected" in issue for issue in issues)


def test_get_rfc_statistics_identifies_stale_drafts(configured_project: RFCService) -> None:
    old_date = datetime.now() - timedelta(days=validation_settings.rfc_stale_draft_days + 5)
    recent_date = datetime.now()
    stale_rfc = configured_project.create_rfc(title="Legacy Cleanup", author="Alex", tags=["ops"])
    _update_rfc_metadata(stale_rfc.path, date=old_date)
    active_rfc = configured_project.create_rfc(
        title="New Feature", author="Blair", tags=["feature"]
    )
    _update_rfc_metadata(active_rfc.path, status=RFCStatus.APPROVED, date=recent_date)
    stats = configured_project.get_rfc_statistics()
    assert stats["total"] == 2
    assert stats["by_status"]["draft"] == 1
    assert stats["by_status"]["approved"] == 1
    assert any(entry["number"] == stale_rfc.number for entry in stats["stale_drafts"])


def test_get_rfc_statistics_with_subset(configured_project: RFCService) -> None:
    rfc = configured_project.create_rfc(title="Scoped Stats", author="Dana")
    stats = configured_project.get_rfc_statistics([rfc])
    assert stats["total"] == 1
    assert stats["by_status"][rfc.status.value] == 1


def test_find_related_rfcs_filters_by_keywords_and_tags(configured_project: RFCService) -> None:
    telemetry_rfc = configured_project.create_rfc(
        title="Telemetry Pipeline Adoption", author="Casey", tags=["observability"]
    )
    _update_rfc_metadata(telemetry_rfc.path, status=RFCStatus.ADOPTED)
    configured_project.create_rfc(
        title="Performance Budget Guidelines", author="Casey", tags=["performance"]
    )
    related = configured_project.find_related_rfcs(
        title="Telemetry pipeline improvements",
        tags=["observability"],
        statuses=[RFCStatus.ADOPTED],
    )
    assert len(related) == 1
    assert related[0].number == telemetry_rfc.number


def test_adopt_rfc_updates_status_and_moves_file(configured_project: RFCService) -> None:
    rfc = configured_project.create_rfc(title="Caching Strategy", author="Alex")
    original_path = rfc.path
    adopted = configured_project.adopt_rfc(rfc.number)
    assert adopted is not None
    assert adopted.status == RFCStatus.ADOPTED
    assert adopted.path is not None
    assert adopted.path.parent.name == "adopted"
    assert original_path is not None and (not original_path.exists())


def test_abandon_rfc_updates_status_and_moves_file(configured_project: RFCService) -> None:
    rfc = configured_project.create_rfc(title="Deprecated API", author="Jordan")
    original_path = rfc.path
    abandoned = configured_project.abandon_rfc(rfc.number)
    assert abandoned is not None
    assert abandoned.status == RFCStatus.ABANDONED
    assert abandoned.path is not None
    assert abandoned.path.parent.name == "abandoned"
    assert original_path is not None and (not original_path.exists())
