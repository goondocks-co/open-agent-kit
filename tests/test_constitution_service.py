"""Tests for constitution service."""

from datetime import date
from pathlib import Path

import pytest

from open_agent_kit.config.paths import CONSTITUTION_FILENAME
from open_agent_kit.models.constitution import AmendmentType, ConstitutionStatus
from open_agent_kit.services.constitution_service import ConstitutionService

# Default directory for test fixtures (matching config default)
CONSTITUTION_DIR = "oak"


def test_get_constitution_path(temp_project_dir: Path) -> None:
    """Test getting constitution file path."""
    service = ConstitutionService(temp_project_dir)
    expected_path = temp_project_dir / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    assert service.get_constitution_path() == expected_path


def test_exists_when_not_created(temp_project_dir: Path) -> None:
    """Test exists() returns False when constitution doesn't exist."""
    service = ConstitutionService(temp_project_dir)
    assert service.exists() is False


def test_create_constitution(temp_project_dir: Path) -> None:
    """Test creating a new constitution."""
    service = ConstitutionService(temp_project_dir)
    constitution = service.create(
        project_name="Test Project",
        author="Test Author",
        tech_stack="Python, FastAPI",
        description="Test description",
    )
    assert constitution.metadata.project_name == "Test Project"
    assert constitution.metadata.author == "Test Author"
    assert constitution.metadata.version == "1.0.0"
    assert constitution.metadata.status == ConstitutionStatus.RATIFIED
    assert constitution.metadata.ratification_date == date.today()
    assert constitution.metadata.tech_stack == "Python, FastAPI"
    assert constitution.metadata.description == "Test description"
    assert len(constitution.sections) > 0
    assert service.exists()


def test_create_constitution_minimal(temp_project_dir: Path) -> None:
    """Test creating constitution with minimal required fields."""
    service = ConstitutionService(temp_project_dir)
    constitution = service.create(project_name="Minimal Project", author="Author")
    assert constitution.metadata.project_name == "Minimal Project"
    assert constitution.metadata.author == "Author"
    assert constitution.metadata.tech_stack is None
    assert constitution.metadata.description is None


def test_create_constitution_already_exists(temp_project_dir: Path) -> None:
    """Test creating constitution when one already exists fails."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    with pytest.raises(FileExistsError, match="Constitution already exists"):
        service.create(project_name="Test2", author="Author2")


def test_load_constitution(temp_project_dir: Path) -> None:
    """Test loading existing constitution."""
    service = ConstitutionService(temp_project_dir)
    created = service.create(project_name="Test Project", author="Test Author", tech_stack="Python")
    loaded = service.load()
    assert loaded.metadata.project_name == created.metadata.project_name
    assert loaded.metadata.version == created.metadata.version
    assert loaded.metadata.author == created.metadata.author
    assert loaded.metadata.tech_stack == created.metadata.tech_stack


def test_load_constitution_not_exists(temp_project_dir: Path) -> None:
    """Test loading non-existent constitution fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.load()


def test_add_amendment_minor(temp_project_dir: Path) -> None:
    """Test adding a minor amendment."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    amendment = service.add_amendment(
        summary="Add security requirements",
        rationale="Security audit found gaps",
        amendment_type="minor",
        author="Security Team",
        section="Code Standards",
        impact="Teams must add security scanning",
    )
    assert amendment.version == "1.1.0"
    assert amendment.type == AmendmentType.MINOR
    assert amendment.summary == "Add security requirements"
    assert amendment.rationale == "Security audit found gaps"
    assert amendment.author == "Security Team"
    assert amendment.section == "Code Standards"
    assert amendment.impact == "Teams must add security scanning"
    assert amendment.date == date.today()
    loaded = service.load()
    assert len(loaded.amendments) == 1
    assert loaded.amendments[0].version == "1.1.0"
    assert loaded.metadata.version == "1.1.0"
    assert loaded.metadata.status == ConstitutionStatus.AMENDED


def test_add_amendment_major(temp_project_dir: Path) -> None:
    """Test adding a major amendment."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    amendment = service.add_amendment(
        summary="Remove test coverage requirement",
        rationale="Not practical for our team size",
        amendment_type="major",
        author="Engineering Lead",
    )
    assert amendment.version == "2.0.0"
    assert amendment.type == AmendmentType.MAJOR
    loaded = service.load()
    assert loaded.metadata.version == "2.0.0"


def test_add_amendment_patch(temp_project_dir: Path) -> None:
    """Test adding a patch amendment."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    amendment = service.add_amendment(
        summary="Clarify code review process",
        rationale="Team had questions about approval requirements",
        amendment_type="patch",
        author="Team Lead",
    )
    assert amendment.version == "1.0.1"
    assert amendment.type == AmendmentType.PATCH
    loaded = service.load()
    assert loaded.metadata.version == "1.0.1"


def test_add_multiple_amendments(temp_project_dir: Path) -> None:
    """Test adding multiple amendments in sequence."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    service.add_amendment("First", "First rationale", "patch", "Author1")
    service.add_amendment("Second", "Second rationale", "minor", "Author2")
    service.add_amendment("Third", "Third rationale", "patch", "Author3")
    loaded = service.load()
    assert len(loaded.amendments) == 3
    assert loaded.amendments[0].version == "1.0.1"
    assert loaded.amendments[1].version == "1.1.0"
    assert loaded.amendments[2].version == "1.1.1"
    assert loaded.metadata.version == "1.1.1"


def test_add_amendment_invalid_type(temp_project_dir: Path) -> None:
    """Test adding amendment with invalid type fails."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    with pytest.raises(ValueError, match="Invalid amendment type"):
        service.add_amendment(
            summary="Test", rationale="Test", amendment_type="invalid", author="Author"
        )


def test_add_amendment_constitution_not_exists(temp_project_dir: Path) -> None:
    """Test adding amendment when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.add_amendment(
            summary="Test", rationale="Test", amendment_type="minor", author="Author"
        )


def test_get_content(temp_project_dir: Path) -> None:
    """Test getting raw constitution content."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test Project", author="Author")
    content = service.get_content()
    assert "# Test Project Engineering Constitution" in content
    assert "## Metadata" in content
    assert "## Principles" in content


def test_get_content_not_exists(temp_project_dir: Path) -> None:
    """Test getting content when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.get_content()


def test_update_content(temp_project_dir: Path) -> None:
    """Test updating constitution content."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    new_content = "# Updated Constitution\n\nNew content here"
    service.update_content(new_content)
    loaded_content = service.get_content()
    assert loaded_content == new_content


def test_update_content_not_exists(temp_project_dir: Path) -> None:
    """Test updating content when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.update_content("New content")


def test_get_current_version(temp_project_dir: Path) -> None:
    """Test getting current constitution version."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    assert service.get_current_version() == "1.0.0"
    service.add_amendment("Test", "Test", "minor", "Author")
    assert service.get_current_version() == "1.1.0"


def test_get_current_version_not_exists(temp_project_dir: Path) -> None:
    """Test getting version when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.get_current_version()


def test_from_config(temp_project_dir: Path) -> None:
    """Test creating service from configuration."""
    service = ConstitutionService.from_config(temp_project_dir)
    assert service.project_root == temp_project_dir
    assert isinstance(service, ConstitutionService)


def test_parse_constitution_with_amendments(temp_project_dir: Path) -> None:
    """Test parsing constitution with amendments."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    service.add_amendment("First", "First rationale", "minor", "Author1")
    service.add_amendment("Second", "Second rationale", "patch", "Author2")
    loaded = service.load()
    assert len(loaded.amendments) == 2
    assert loaded.amendments[0].version == "1.1.0"
    assert loaded.amendments[0].summary == "First"
    assert loaded.amendments[1].version == "1.1.1"
    assert loaded.amendments[1].summary == "Second"


def test_amendment_persists_across_loads(temp_project_dir: Path) -> None:
    """Test that amendments persist correctly across multiple loads."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    service.add_amendment("Test amendment", "Test rationale", "minor", "Author")
    loaded1 = service.load()
    loaded2 = service.load()
    loaded3 = service.load()
    assert len(loaded1.amendments) == 1
    assert len(loaded2.amendments) == 1
    assert len(loaded3.amendments) == 1
    assert loaded1.metadata.version == "1.1.0"
    assert loaded2.metadata.version == "1.1.0"
    assert loaded3.metadata.version == "1.1.0"


def test_constitution_sections_parsed_correctly(temp_project_dir: Path) -> None:
    """Test that constitution sections are parsed correctly."""
    service = ConstitutionService(temp_project_dir)
    constitution = service.create(project_name="Test", author="Author")
    section_titles = [s.title for s in constitution.sections]
    assert "Principles" in section_titles
    assert "Architecture" in section_titles
    assert "Code Standards" in section_titles
    assert "Testing" in section_titles
    assert "Documentation" in section_titles
    assert "Governance" in section_titles
    assert "Metadata" not in section_titles
    assert "Amendments" not in section_titles


def test_constitution_file_created_at_correct_location(temp_project_dir: Path) -> None:
    """Test that constitution file is created at the correct location."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    expected_path = temp_project_dir / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    assert expected_path.exists()
    assert expected_path.is_file()


def test_amendment_date_is_current(temp_project_dir: Path) -> None:
    """Test that amendment date is set to current date."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    amendment = service.add_amendment("Test", "Test", "minor", "Author")
    assert amendment.date == date.today()


def test_constitution_status_changes_with_amendments(temp_project_dir: Path) -> None:
    """Test that constitution status changes from RATIFIED to AMENDED."""
    service = ConstitutionService(temp_project_dir)
    service.create(project_name="Test", author="Author")
    loaded = service.load()
    assert loaded.metadata.status == ConstitutionStatus.RATIFIED
    service.add_amendment("Test", "Test", "minor", "Author")
    loaded = service.load()
    assert loaded.metadata.status == ConstitutionStatus.AMENDED
