"""Tests for validation service."""

from datetime import date, timedelta

import pytest

from open_agent_kit.models.constitution import (
    Amendment,
    AmendmentType,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
)
from open_agent_kit.models.validation import ValidationCategory, ValidationPriority
from open_agent_kit.services.validation_service import ValidationService


@pytest.fixture
def valid_constitution() -> ConstitutionDocument:
    """Create a valid constitution for testing."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
    )
    sections = [
        ConstitutionSection(
            title="Metadata",
            content="Project metadata includes ownership, lifecycle, and auditing references.",
            order=0,
            required=False,
        ),
        ConstitutionSection(
            title="Principles",
            content="Code MUST be tested before merge. Each release MUST document the quality gate outcomes.",
            order=1,
            required=True,
        ),
        ConstitutionSection(
            title="Architecture",
            content="Services MUST be modular and observable. Architecture decisions MUST document trade-offs and impacts.",
            order=2,
            required=True,
        ),
        ConstitutionSection(
            title="Code Standards",
            content="Code MUST pass linting with zero warnings. Pull requests MUST include automated formatting checks.",
            order=3,
            required=True,
        ),
        ConstitutionSection(
            title="Testing",
            content="Coverage MUST exceed 80%. Test suites MUST block merges when coverage drops below the threshold.",
            order=4,
            required=True,
        ),
        ConstitutionSection(
            title="Documentation",
            content="APIs MUST be documented before release. Documentation MUST include examples and update history.",
            order=5,
            required=True,
        ),
        ConstitutionSection(
            title="Governance",
            content="Changes MUST be reviewed by the Architecture Council. Governance reviews MUST record rationale and dissent.",
            order=6,
            required=True,
        ),
    ]
    return ConstitutionDocument(metadata=metadata, sections=sections)


def test_validate_valid_constitution(valid_constitution: ConstitutionDocument) -> None:
    """Test validating a valid constitution."""
    service = ValidationService()
    result = service.validate(valid_constitution)
    assert result.is_valid
    assert len(result.issues) == 0


def test_validate_missing_required_section() -> None:
    """Test validation fails when required section is missing."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [ConstitutionSection(title="Principles", content="Test", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert not result.is_valid
    assert len(result.issues) > 0
    missing_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.STRUCTURE
    ]
    assert len(missing_issues) > 0
    missing_sections = [issue.message for issue in missing_issues]
    assert any("Architecture" in msg for msg in missing_sections)
    assert any("Code Standards" in msg for msg in missing_sections)


def test_validate_empty_section(valid_constitution: ConstitutionDocument) -> None:
    """Test validation detects empty sections."""
    valid_constitution.sections.append(
        ConstitutionSection(title="Empty Section", content="", order=10)
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    assert not result.is_valid
    empty_issues = [
        issue
        for issue in result.issues
        if "Empty section" in issue.message and issue.category == ValidationCategory.STRUCTURE
    ]
    assert len(empty_issues) == 1
    assert empty_issues[0].priority == ValidationPriority.MEDIUM


def test_validate_missing_metadata_field() -> None:
    """Test validation detects missing metadata fields."""
    metadata = ConstitutionMetadata(
        project_name="", version="1.0.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [ConstitutionSection(title="Principles", content="Test", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert not result.is_valid
    metadata_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.METADATA
    ]
    assert len(metadata_issues) > 0
    assert any("Project name cannot be empty" in issue.message for issue in metadata_issues)


def test_validate_unreplaced_tokens(valid_constitution: ConstitutionDocument) -> None:
    """Test validation detects unreplaced template tokens."""
    valid_constitution.sections.append(
        ConstitutionSection(title="Test", content="Project: {{PROJECT_NAME}}", order=10)
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    assert not result.is_valid
    token_issues = [issue for issue in result.issues if issue.category == ValidationCategory.TOKENS]
    assert len(token_issues) == 1
    assert "{{PROJECT_NAME}}" in token_issues[0].message
    assert token_issues[0].priority == ValidationPriority.HIGH


def test_validate_invalid_version_format() -> None:
    """Test validation detects invalid version format."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [ConstitutionSection(title="Principles", content="Test", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert not result.is_valid
    version_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.VERSIONING
    ]
    assert len(version_issues) == 1
    assert "Invalid version format" in version_issues[0].message
    assert version_issues[0].priority == ValidationPriority.HIGH


def test_validate_version_mismatch_with_amendment(valid_constitution: ConstitutionDocument) -> None:
    """Test validation detects version mismatch with amendments."""
    amendment = Amendment(
        version="1.1.0",
        date=date(2025, 11, 7),
        type=AmendmentType.MINOR,
        summary="Test",
        rationale="Test",
        author="Author",
    )
    valid_constitution.amendments.append(amendment)
    assert valid_constitution.metadata.version == "1.0.0"
    service = ValidationService()
    result = service.validate(valid_constitution)
    assert not result.is_valid
    version_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.VERSIONING
    ]
    assert len(version_issues) == 1
    assert "Version mismatch" in version_issues[0].message
    assert version_issues[0].priority == ValidationPriority.HIGH
    assert version_issues[0].auto_fixable is True


def test_validate_future_ratification_date() -> None:
    """Test validation detects future ratification date."""
    tomorrow = date.today() + timedelta(days=1)
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0.0", ratification_date=tomorrow, author="Author"
    )
    sections = [ConstitutionSection(title="Principles", content="Test", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert not result.is_valid
    date_issues = [issue for issue in result.issues if issue.category == ValidationCategory.DATES]
    assert len(date_issues) == 1
    assert "future" in date_issues[0].message.lower()
    assert date_issues[0].priority == ValidationPriority.LOW


def test_validate_non_declarative_language(valid_constitution: ConstitutionDocument) -> None:
    """Test validation detects non-declarative language.

    Note: Validation is case-sensitive to avoid flagging RFC 2119 keywords
    (MUST, SHOULD, MAY) which are uppercase. We only flag lowercase informal
    usage like "should", "could", "maybe".
    """
    valid_constitution.sections.append(
        ConstitutionSection(
            title="Soft Requirements",
            # Use lowercase to ensure detection (uppercase SHOULD/MAY are valid RFC 2119)
            content="Code should be tested\nYou could add comments\nThis maybe needs types",
            order=10,
        )
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    assert not result.is_valid
    language_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.LANGUAGE
    ]
    assert len(language_issues) >= 3
    non_declarative_words = [issue.message for issue in language_issues]
    assert any("should" in msg.lower() for msg in non_declarative_words)
    assert any("could" in msg.lower() for msg in non_declarative_words)
    assert any("maybe" in msg.lower() for msg in non_declarative_words)
    assert all(issue.priority == ValidationPriority.LOW for issue in language_issues)


def test_validate_non_declarative_with_line_numbers(
    valid_constitution: ConstitutionDocument,
) -> None:
    """Test that non-declarative language issues include line numbers."""
    valid_constitution.sections.append(
        ConstitutionSection(
            title="Test",
            content="Line 1: Code MUST be tested\nLine 2: Tests should cover edge cases",
            order=10,
        )
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    language_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.LANGUAGE
    ]
    assert len(language_issues) == 1
    assert language_issues[0].line_number == 2


def test_rfc_2119_keywords_not_flagged(valid_constitution: ConstitutionDocument) -> None:
    """Test that uppercase RFC 2119 keywords are NOT flagged as non-declarative.

    RFC 2119 defines MUST, SHOULD, MAY as valid requirement keywords.
    These should NOT be flagged when used in uppercase.
    """
    valid_constitution.sections.append(
        ConstitutionSection(
            title="Requirements",
            content=(
                "All code MUST pass tests.\n"
                "Documentation SHOULD be comprehensive.\n"
                "Edge cases MAY be handled gracefully.\n"
                "Code MUST NOT contain secrets."
            ),
            order=10,
        )
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    language_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.LANGUAGE
    ]
    # No language issues should be flagged for uppercase RFC 2119 keywords
    assert len(language_issues) == 0


def test_validation_categorizes_by_priority() -> None:
    """Test that validation result categorizes issues by priority."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="invalid-version",
        ratification_date=date.today() + timedelta(days=1),
        author="Author",
    )
    sections = [
        ConstitutionSection(title="Principles", content="", order=1),
        ConstitutionSection(title="Testing", content="Tests should be written", order=2),
    ]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    categorized = result.categorize_issues()
    assert len(categorized[ValidationPriority.HIGH]) > 0
    assert len(categorized[ValidationPriority.MEDIUM]) > 0
    assert len(categorized[ValidationPriority.LOW]) > 0


def test_validation_get_issues_by_priority() -> None:
    """Test getting issues filtered by priority."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="invalid", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = []
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    high_issues = result.get_issues_by_priority(ValidationPriority.HIGH)
    assert len(high_issues) > 0
    assert all(issue.priority == ValidationPriority.HIGH for issue in high_issues)


def test_validation_from_config() -> None:
    """Test creating validation service from config."""
    service = ValidationService.from_config()
    assert isinstance(service, ValidationService)


def test_validation_multiple_missing_sections() -> None:
    """Test validation detects multiple missing required sections."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [ConstitutionSection(title="Principles", content="Test", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    structure_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.STRUCTURE
    ]
    missing_sections = ["Architecture", "Code Standards", "Testing", "Documentation", "Governance"]
    for section_name in missing_sections:
        assert any(
            section_name in issue.message
            for issue in structure_issues
            if "Missing required section" in issue.message
        )


def test_validation_auto_fixable_flag() -> None:
    """Test that auto-fixable flag is set correctly."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="1.0.0",
        ratification_date=date.today() + timedelta(days=1),
        author="Author",
    )
    sections = [ConstitutionSection(title="Empty", content="", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    date_issues = [issue for issue in result.issues if issue.category == ValidationCategory.DATES]
    assert all(issue.auto_fixable for issue in date_issues)
    structure_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.STRUCTURE
    ]
    assert all(not issue.auto_fixable for issue in structure_issues)


def test_validation_suggested_fixes() -> None:
    """Test that validation issues include suggested fixes."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="invalid", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [ConstitutionSection(title="Test", content="{{PROJECT_NAME}}", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert all(issue.suggested_fix is not None for issue in result.issues)
    assert all(len(issue.suggested_fix) > 0 for issue in result.issues)


def test_validation_result_calculate_stats() -> None:
    """Test that validation result calculates statistics."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="invalid",
        ratification_date=date.today() + timedelta(days=1),
        author="Author",
    )
    sections = [ConstitutionSection(title="Empty", content="", order=1)]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    assert result.total_issues > 0
    assert result.high_priority_count > 0
    assert result.medium_priority_count > 0
    assert result.low_priority_count > 0


def test_validation_empty_content_tokens() -> None:
    """Test that validation handles multiple token types."""
    metadata = ConstitutionMetadata(
        project_name="Test", version="1.0.0", ratification_date=date(2025, 11, 6), author="Author"
    )
    sections = [
        ConstitutionSection(
            title="Test",
            content="Project: {{PROJECT_NAME}}\nVersion: {{VERSION}}\nAuthor: {{AUTHOR}}",
            order=1,
        )
    ]
    constitution = ConstitutionDocument(metadata=metadata, sections=sections)
    service = ValidationService()
    result = service.validate(constitution)
    token_issues = [issue for issue in result.issues if issue.category == ValidationCategory.TOKENS]
    assert len(token_issues) == 3


def test_quality_flags_short_section(valid_constitution: ConstitutionDocument) -> None:
    """Quality assessment flags sections with insufficient detail."""
    testing_section = valid_constitution.get_section("Testing")
    assert testing_section is not None
    testing_section.content = "Testing MUST exist."
    service = ValidationService()
    result = service.validate(valid_constitution)
    quality_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.QUALITY
    ]
    assert any("thin" in issue.message for issue in quality_issues)


def test_quality_flags_missing_normative_language(valid_constitution: ConstitutionDocument) -> None:
    """Quality assessment flags sections that lack normative words."""
    governance_section = valid_constitution.get_section("Governance")
    assert governance_section is not None
    governance_section.content = "The architecture council reviews proposals on Tuesdays."
    service = ValidationService()
    result = service.validate(valid_constitution)
    quality_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.QUALITY
    ]
    assert any("normative" in issue.message.lower() for issue in quality_issues)


def test_quality_flags_vague_language(valid_constitution: ConstitutionDocument) -> None:
    """Quality assessment flags vague commitments."""
    principles_section = valid_constitution.get_section("Principles")
    assert principles_section is not None
    principles_section.content = (
        "We strive to deliver quality outcomes. Teams should try to write tests when possible."
    )
    service = ValidationService()
    result = service.validate(valid_constitution)
    quality_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.QUALITY
    ]
    assert any("vague commitment" in issue.message.lower() for issue in quality_issues)


def test_consistency_flags_unsorted_amendments(valid_constitution: ConstitutionDocument) -> None:
    """Consistency assessment flags unsorted amendments."""
    valid_constitution.metadata.version = "1.0.1"
    valid_constitution.metadata.last_amendment = date(2025, 11, 10)
    valid_constitution.amendments = [
        Amendment(
            version="1.1.0",
            date=date(2025, 11, 10),
            type=AmendmentType.MINOR,
            summary="Introduce observability requirements.",
            rationale="Ensure traceability for services.",
            author="Author",
        ),
        Amendment(
            version="1.0.1",
            date=date(2025, 11, 5),
            type=AmendmentType.PATCH,
            summary="Clarify testing thresholds.",
            rationale="Align coverage metric with tooling.",
            author="Author",
        ),
    ]
    service = ValidationService()
    result = service.validate(valid_constitution)
    consistency_issues = [
        issue for issue in result.issues if issue.category == ValidationCategory.CONSISTENCY
    ]
    assert any("chronological" in issue.message.lower() for issue in consistency_issues)
    assert any("monotonically" in issue.message.lower() for issue in consistency_issues)
