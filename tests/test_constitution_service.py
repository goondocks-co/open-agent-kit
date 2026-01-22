"""Tests for constitution service."""

from pathlib import Path

import pytest

from open_agent_kit.config.paths import CONSTITUTION_FILENAME
from open_agent_kit.features.rules_management.constitution import ConstitutionService

# Default directory for test fixtures (matching config default)
CONSTITUTION_DIR = "oak"

# Sample constitution content for testing
SAMPLE_CONSTITUTION = """# Test Project Engineering Constitution

## Metadata

- **Project:** Test Project
- **Version:** 1.0.0
- **Status:** Ratified
- **Ratification Date:** 2025-01-01
- **Last Amendment:** N/A
- **Author:** Test Author
- **Tech Stack:** Python

---

## Principles

**P1: Code Quality**

All code MUST pass automated checks.

## Architecture

**A1: Modularity**

Components MUST be loosely coupled.

## Code Standards

**C1: Style**

Follow PEP 8 guidelines.

## Testing

**T1: Coverage**

All new code MUST have tests.

## Documentation

**D1: Comments**

Code SHOULD be self-documenting.

## Governance

**G1: Review**

All changes MUST be reviewed.
"""


@pytest.fixture
def constitution_file(temp_project_dir: Path) -> Path:
    """Create a sample constitution file for testing.

    Args:
        temp_project_dir: Temporary project directory

    Returns:
        Path to created constitution file
    """
    constitution_dir = temp_project_dir / CONSTITUTION_DIR
    constitution_dir.mkdir(parents=True, exist_ok=True)
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    constitution_path.write_text(SAMPLE_CONSTITUTION, encoding="utf-8")
    return constitution_path


def test_get_constitution_path(temp_project_dir: Path) -> None:
    """Test getting constitution file path."""
    service = ConstitutionService(temp_project_dir)
    expected_path = temp_project_dir / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    assert service.get_constitution_path() == expected_path


def test_exists_when_not_created(temp_project_dir: Path) -> None:
    """Test exists() returns False when constitution doesn't exist."""
    service = ConstitutionService(temp_project_dir)
    assert service.exists() is False


def test_exists_when_created(temp_project_dir: Path, constitution_file: Path) -> None:
    """Test exists() returns True when constitution exists."""
    service = ConstitutionService(temp_project_dir)
    assert service.exists() is True


def test_load_constitution(temp_project_dir: Path, constitution_file: Path) -> None:
    """Test loading existing constitution."""
    service = ConstitutionService(temp_project_dir)
    loaded = service.load()
    assert loaded.metadata.project_name == "Test Project"
    assert loaded.metadata.version == "1.0.0"
    assert loaded.metadata.author == "Test Author"
    assert loaded.metadata.tech_stack == "Python"


def test_load_constitution_not_exists(temp_project_dir: Path) -> None:
    """Test loading non-existent constitution fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.load()


def test_get_content(temp_project_dir: Path, constitution_file: Path) -> None:
    """Test getting raw constitution content."""
    service = ConstitutionService(temp_project_dir)
    content = service.get_content()
    assert "# Test Project Engineering Constitution" in content
    assert "## Metadata" in content
    assert "## Principles" in content


def test_get_content_not_exists(temp_project_dir: Path) -> None:
    """Test getting content when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.get_content()


def test_update_content(temp_project_dir: Path, constitution_file: Path) -> None:
    """Test updating constitution content."""
    service = ConstitutionService(temp_project_dir)
    new_content = "# Updated Constitution\n\nNew content here"
    service.update_content(new_content)
    loaded_content = service.get_content()
    assert loaded_content == new_content


def test_update_content_not_exists(temp_project_dir: Path) -> None:
    """Test updating content when constitution doesn't exist fails."""
    service = ConstitutionService(temp_project_dir)
    with pytest.raises(FileNotFoundError, match="Constitution not found"):
        service.update_content("New content")


def test_get_current_version(temp_project_dir: Path, constitution_file: Path) -> None:
    """Test getting current constitution version."""
    service = ConstitutionService(temp_project_dir)
    assert service.get_current_version() == "1.0.0"


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


def test_constitution_sections_parsed_correctly(
    temp_project_dir: Path, constitution_file: Path
) -> None:
    """Test that constitution sections are parsed correctly."""
    service = ConstitutionService(temp_project_dir)
    constitution = service.load()
    section_titles = [s.title for s in constitution.sections]
    assert "Principles" in section_titles
    assert "Architecture" in section_titles
    assert "Code Standards" in section_titles
    assert "Testing" in section_titles
    assert "Documentation" in section_titles
    assert "Governance" in section_titles
    # Metadata is NOT a section (parsed separately)
    assert "Metadata" not in section_titles


def test_analyze_project_greenfield(temp_project_dir: Path) -> None:
    """Test project analysis for greenfield project."""
    # Set up minimal project (no tests, no CI, no agent files)
    (temp_project_dir / ".oak").mkdir()

    service = ConstitutionService(temp_project_dir)
    results = service.analyze_project()

    assert results["classification"] == "greenfield"
    assert results["oak_installed"] is True
    assert results["test_infrastructure"]["found"] is False
    assert results["ci_cd"]["found"] is False


def test_analyze_project_brownfield_minimal(temp_project_dir: Path) -> None:
    """Test project analysis for brownfield-minimal project."""
    # Set up project with tests directory
    (temp_project_dir / ".oak").mkdir()
    (temp_project_dir / "tests").mkdir()
    (temp_project_dir / "tests" / "test_example.py").write_text("# test file")

    service = ConstitutionService(temp_project_dir)
    results = service.analyze_project()

    assert results["classification"] in ["brownfield-minimal", "brownfield-mature"]
    assert results["test_infrastructure"]["found"] is True


def test_analyze_project_brownfield_mature(temp_project_dir: Path) -> None:
    """Test project analysis for brownfield-mature project."""
    # Set up project with tests, CI, and meaningful agent instructions
    (temp_project_dir / ".oak").mkdir()
    (temp_project_dir / "tests").mkdir()
    (temp_project_dir / "tests" / "test_example.py").write_text("# test file")
    (temp_project_dir / ".github" / "workflows").mkdir(parents=True)
    (temp_project_dir / ".github" / "workflows" / "ci.yml").write_text("name: CI")
    # Create a meaningful agent instruction file (not OAK-only content)
    # Needs more than 3 non-oak lines to be considered meaningful
    (temp_project_dir / "CLAUDE.md").write_text(
        "# Project Instructions\n\n"
        "This project uses Python 3.10+.\n"
        "Run tests with pytest.\n"
        "Follow PEP 8 style guidelines.\n"
        "All code must have type hints.\n"
    )

    service = ConstitutionService(temp_project_dir)
    results = service.analyze_project()

    assert results["classification"] == "brownfield-mature"
    assert results["test_infrastructure"]["found"] is True
    assert results["ci_cd"]["found"] is True
