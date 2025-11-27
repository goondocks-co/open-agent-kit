"""Tests for constitution data models."""

from datetime import date

from open_agent_kit.models.constitution import (
    Amendment,
    AmendmentType,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
)


def test_amendment_type_enum() -> None:
    """Test amendment type enumeration values."""
    assert AmendmentType.MAJOR.value == "major"
    assert AmendmentType.MINOR.value == "minor"
    assert AmendmentType.PATCH.value == "patch"


def test_constitution_status_enum() -> None:
    """Test constitution status enumeration values."""
    assert ConstitutionStatus.DRAFT.value == "draft"
    assert ConstitutionStatus.RATIFIED.value == "ratified"
    assert ConstitutionStatus.AMENDED.value == "amended"
    assert ConstitutionStatus.DEPRECATED.value == "deprecated"


def test_constitution_metadata_creation() -> None:
    """Test creating constitution metadata."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
        tech_stack="Python, FastAPI",
        description="Test project description",
    )
    assert metadata.project_name == "Test Project"
    assert metadata.version == "1.0.0"
    assert metadata.ratification_date == date(2025, 11, 6)
    assert metadata.author == "Test Author"
    assert metadata.status == ConstitutionStatus.RATIFIED
    assert metadata.tech_stack == "Python, FastAPI"
    assert metadata.description == "Test project description"


def test_constitution_metadata_defaults() -> None:
    """Test constitution metadata with default values."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
    )
    assert metadata.status == ConstitutionStatus.DRAFT
    assert metadata.last_amendment is None
    assert metadata.tech_stack is None
    assert metadata.description is None


def test_constitution_metadata_to_dict() -> None:
    """Test metadata serialization to dictionary."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
    )
    data = metadata.to_dict()
    assert data["project_name"] == "Test Project"
    assert data["version"] == "1.0.0"
    assert data["ratification_date"] == "2025-11-06"
    assert data["author"] == "Test Author"
    assert data["status"] == "ratified"


def test_constitution_metadata_from_dict() -> None:
    """Test metadata deserialization from dictionary."""
    data = {
        "project_name": "Test Project",
        "version": "1.0.0",
        "ratification_date": "2025-11-06",
        "author": "Test Author",
        "status": "ratified",
        "tech_stack": "Python",
    }
    metadata = ConstitutionMetadata.from_dict(data)
    assert metadata.project_name == "Test Project"
    assert metadata.version == "1.0.0"
    assert metadata.ratification_date == date(2025, 11, 6)
    assert metadata.author == "Test Author"
    assert metadata.status == ConstitutionStatus.RATIFIED
    assert metadata.tech_stack == "Python"


def test_constitution_section_creation() -> None:
    """Test creating a constitution section."""
    section = ConstitutionSection(
        title="Principles",
        content="**P1: Code Quality**\n\nAll code MUST pass automated checks.",
        order=1,
    )
    assert section.title == "Principles"
    assert "Code Quality" in section.content
    assert section.order == 1


def test_constitution_section_to_dict() -> None:
    """Test section serialization to dictionary."""
    section = ConstitutionSection(title="Testing", content="All code MUST have tests.", order=4)
    data = section.to_dict()
    assert data["title"] == "Testing"
    assert data["content"] == "All code MUST have tests."
    assert data["order"] == 4


def test_amendment_creation() -> None:
    """Test creating an amendment."""
    amendment = Amendment(
        version="1.1.0",
        date=date(2025, 11, 6),
        type=AmendmentType.MINOR,
        summary="Add security scanning requirements",
        rationale="Recent security audit revealed gaps",
        author="Security Team",
        section="Code Standards",
        impact="All repos must add security scanning",
    )
    assert amendment.version == "1.1.0"
    assert amendment.date == date(2025, 11, 6)
    assert amendment.type == AmendmentType.MINOR
    assert amendment.summary == "Add security scanning requirements"
    assert amendment.rationale == "Recent security audit revealed gaps"
    assert amendment.author == "Security Team"
    assert amendment.section == "Code Standards"
    assert amendment.impact == "All repos must add security scanning"


def test_amendment_to_markdown() -> None:
    """Test amendment markdown formatting."""
    amendment = Amendment(
        version="1.1.0",
        date=date(2025, 11, 6),
        type=AmendmentType.MINOR,
        summary="Add security scanning",
        rationale="Security gaps found",
        author="Security Team",
        section="Code Standards",
        impact="Add scanning to CI",
    )
    markdown = amendment.to_markdown()
    assert "## Amendment 1.1.0 (2025-11-06)" in markdown
    assert "**Type:** Minor" in markdown
    assert "**Author:** Security Team" in markdown
    assert "**Summary:** Add security scanning" in markdown
    assert "**Rationale:**" in markdown
    assert "Security gaps found" in markdown
    assert "**Section:** Code Standards" in markdown
    assert "**Impact:** Add scanning to CI" in markdown


def test_amendment_to_dict() -> None:
    """Test amendment serialization to dictionary."""
    amendment = Amendment(
        version="1.1.0",
        date=date(2025, 11, 6),
        type=AmendmentType.MINOR,
        summary="Add security scanning",
        rationale="Security audit",
        author="Security Team",
    )
    data = amendment.to_dict()
    assert data["version"] == "1.1.0"
    assert data["date"] == "2025-11-06"
    assert data["type"] == "minor"
    assert data["summary"] == "Add security scanning"
    assert data["author"] == "Security Team"


def test_amendment_from_dict() -> None:
    """Test amendment deserialization from dictionary."""
    data = {
        "version": "1.1.0",
        "date": "2025-11-06",
        "type": "minor",
        "summary": "Add security scanning",
        "rationale": "Security audit",
        "author": "Security Team",
        "section": "Code Standards",
    }
    amendment = Amendment.from_dict(data)
    assert amendment.version == "1.1.0"
    assert amendment.date == date(2025, 11, 6)
    assert amendment.type == AmendmentType.MINOR
    assert amendment.summary == "Add security scanning"
    assert amendment.section == "Code Standards"


def test_constitution_document_creation() -> None:
    """Test creating a constitution document."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
    )
    sections = [
        ConstitutionSection(title="Principles", content="P1: Quality", order=1),
        ConstitutionSection(title="Architecture", content="A1: Modularity", order=2),
    ]
    doc = ConstitutionDocument(metadata=metadata, sections=sections)
    assert doc.metadata.project_name == "Test Project"
    assert len(doc.sections) == 2
    assert doc.sections[0].title == "Principles"
    assert doc.amendments == []
    assert doc.file_path is None


def test_constitution_document_add_amendment() -> None:
    """Test adding amendment to constitution."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Author",
        status=ConstitutionStatus.RATIFIED,
    )
    doc = ConstitutionDocument(metadata=metadata, sections=[])
    amendment = Amendment(
        version="1.1.0",
        date=date(2025, 11, 7),
        type=AmendmentType.MINOR,
        summary="New feature",
        rationale="User request",
        author="Developer",
    )
    doc.add_amendment(amendment)
    assert len(doc.amendments) == 1
    assert doc.amendments[0].version == "1.1.0"
    assert doc.metadata.version == "1.1.0"
    assert doc.metadata.last_amendment == date(2025, 11, 7)
    assert doc.metadata.status == ConstitutionStatus.AMENDED


def test_constitution_document_get_latest_version() -> None:
    """Test getting latest version from constitution."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    doc = ConstitutionDocument(metadata=metadata, sections=[])
    assert doc.get_latest_version() == "1.0.0"
    doc.add_amendment(
        Amendment(
            version="1.1.0",
            date=date(2025, 11, 7),
            type=AmendmentType.MINOR,
            summary="First",
            rationale="Test",
            author="Author",
        )
    )
    doc.add_amendment(
        Amendment(
            version="1.2.0",
            date=date(2025, 11, 8),
            type=AmendmentType.MINOR,
            summary="Second",
            rationale="Test",
            author="Author",
        )
    )
    assert doc.get_latest_version() == "1.2.0"


def test_constitution_document_to_markdown() -> None:
    """Test constitution markdown formatting."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
        tech_stack="Python",
    )
    sections = [
        ConstitutionSection(title="Principles", content="P1: Quality", order=1),
        ConstitutionSection(title="Testing", content="T1: Coverage", order=2),
    ]
    doc = ConstitutionDocument(metadata=metadata, sections=sections)
    markdown = doc.to_markdown()
    assert "# Test Project Engineering Constitution" in markdown
    assert "## Metadata" in markdown
    assert "- **Project:** Test Project" in markdown
    assert "- **Version:** 1.0.0" in markdown
    assert "- **Tech Stack:** Python" in markdown
    assert "## Principles" in markdown
    assert "P1: Quality" in markdown
    assert "## Testing" in markdown
    assert "T1: Coverage" in markdown


def test_constitution_document_to_markdown_with_amendments() -> None:
    """Test constitution markdown with amendments."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Author",
        status=ConstitutionStatus.RATIFIED,
    )
    doc = ConstitutionDocument(metadata=metadata, sections=[])
    doc.add_amendment(
        Amendment(
            version="1.1.0",
            date=date(2025, 11, 7),
            type=AmendmentType.MINOR,
            summary="New feature",
            rationale="User request",
            author="Developer",
        )
    )
    markdown = doc.to_markdown()
    assert "# Amendments" in markdown
    assert "## Amendment 1.1.0 (2025-11-07)" in markdown
    assert "**Type:** Minor" in markdown
    assert "**Summary:** New feature" in markdown


def test_constitution_document_to_dict() -> None:
    """Test constitution serialization to dictionary."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Author",
        status=ConstitutionStatus.RATIFIED,
    )
    sections = [ConstitutionSection(title="Principles", content="P1", order=1)]
    doc = ConstitutionDocument(metadata=metadata, sections=sections)
    data = doc.to_dict()
    assert data["metadata"]["project_name"] == "Test"
    assert data["metadata"]["version"] == "1.0.0"
    assert len(data["sections"]) == 1
    assert data["sections"][0]["title"] == "Principles"
    assert data["amendments"] == []


def test_constitution_document_from_dict() -> None:
    """Test constitution deserialization from dictionary."""
    data = {
        "metadata": {
            "project_name": "Test",
            "version": "1.0.0",
            "ratification_date": "2025-11-06",
            "author": "Author",
            "status": "ratified",
        },
        "sections": [{"title": "Principles", "content": "P1", "order": 1}],
        "amendments": [],
    }
    doc = ConstitutionDocument.from_dict(data)
    assert doc.metadata.project_name == "Test"
    assert doc.metadata.version == "1.0.0"
    assert len(doc.sections) == 1
    assert doc.sections[0].title == "Principles"
    assert doc.amendments == []
