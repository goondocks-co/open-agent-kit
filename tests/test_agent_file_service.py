"""Tests for agent file service."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from open_agent_kit.config.paths import CONFIG_FILE, OAK_DIR
from open_agent_kit.models.constitution import (
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
)
from open_agent_kit.services.agent_file_service import AgentFileService
from open_agent_kit.utils import write_file


@pytest.fixture
def sample_constitution() -> ConstitutionDocument:
    """Create a sample constitution for testing."""
    metadata = ConstitutionMetadata(
        project_name="Test Project",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Test Author",
        status=ConstitutionStatus.RATIFIED,
        tech_stack="Python, FastAPI",
    )
    sections = [ConstitutionSection(title="Principles", content="P1: Quality", order=1)]
    return ConstitutionDocument(metadata=metadata, sections=sections)


def test_detect_installed_agents_from_config(temp_project_dir: Path) -> None:
    """Test detecting agents from config file."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude", "copilot"], "version": "0.1.0"}
    config_path = oak_dir / CONFIG_FILE
    write_file(config_path, yaml.dump(config))
    service = AgentFileService(temp_project_dir)
    agents = service.detect_installed_agents()
    assert "claude" in agents
    assert "copilot" in agents


def test_detect_installed_agents_from_directories(temp_project_dir: Path) -> None:
    """Test detecting agents from directory structure."""
    (temp_project_dir / ".claude").mkdir()
    (temp_project_dir / ".github").mkdir()
    service = AgentFileService(temp_project_dir)
    agents = service.detect_installed_agents()
    assert "claude" in agents
    assert "copilot" in agents


def test_detect_installed_agents_empty_project(temp_project_dir: Path) -> None:
    """Test detecting agents in empty project."""
    service = AgentFileService(temp_project_dir)
    agents = service.detect_installed_agents()
    assert len(agents) == 0


def test_detect_installed_agents_removes_duplicates(temp_project_dir: Path) -> None:
    """Test that duplicate agents are removed."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude"], "version": "0.1.0"}
    write_file(oak_dir / CONFIG_FILE, yaml.dump(config))
    (temp_project_dir / ".claude").mkdir()
    service = AgentFileService(temp_project_dir)
    agents = service.detect_installed_agents()
    assert agents.count("claude") == 1


def test_list_agent_files_no_files(temp_project_dir: Path) -> None:
    """Test listing agent files when none exist."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude"], "version": "0.1.0"}
    write_file(oak_dir / CONFIG_FILE, yaml.dump(config))
    service = AgentFileService(temp_project_dir)
    agent_files = service.list_agent_files()
    assert "claude" in agent_files
    assert agent_files["claude"] is None


def test_list_agent_files_with_existing_files(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test listing agent files when they exist."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude"], "version": "0.1.0"}
    write_file(oak_dir / CONFIG_FILE, yaml.dump(config))
    service = AgentFileService(temp_project_dir)
    service.generate_agent_files(sample_constitution, ["claude"])
    agent_files = service.list_agent_files()
    assert "claude" in agent_files
    assert agent_files["claude"] is not None
    assert agent_files["claude"].exists()


def test_generate_agent_files_for_claude(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for Claude."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["claude"])
    assert "claude" in generated
    assert generated["claude"].exists()
    expected_path = temp_project_dir / ".claude" / "CLAUDE.md"
    assert generated["claude"] == expected_path
    content = generated["claude"].read_text(encoding="utf-8")
    assert "Test Project" in content
    assert "1.0.0" in content
    assert "oak/constitution.md" in content


def test_generate_agent_files_for_copilot(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for GitHub Copilot."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["copilot"])
    assert "copilot" in generated
    expected_path = temp_project_dir / ".github" / "copilot-instructions.md"
    assert generated["copilot"] == expected_path


def test_generate_agent_files_for_cursor(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for Cursor."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["cursor"])
    assert "cursor" in generated
    expected_path = temp_project_dir / "AGENTS.md"
    assert generated["cursor"] == expected_path


def test_generate_agent_files_for_codex(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for Codex."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["codex"])
    assert "codex" in generated
    expected_path = temp_project_dir / "AGENTS.md"
    assert generated["codex"] == expected_path


def test_generate_agent_files_for_gemini(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for Gemini."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["gemini"])
    assert "gemini" in generated
    expected_path = temp_project_dir / "GEMINI.md"
    assert generated["gemini"] == expected_path


def test_generate_agent_files_for_windsurf(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating agent file for Windsurf."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["windsurf"])
    assert "windsurf" in generated
    expected_path = temp_project_dir / ".windsurf" / "rules" / "rules.md"
    assert generated["windsurf"] == expected_path


def test_generate_agent_files_multiple_agents(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating files for multiple agents at once."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["claude", "copilot", "cursor"])
    assert len(generated) == 3
    assert "claude" in generated
    assert "copilot" in generated
    assert "cursor" in generated
    assert all(path.exists() for path in generated.values())


def test_generate_agent_files_auto_detect(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating files for auto-detected agents."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude", "copilot"], "version": "0.1.0"}
    write_file(oak_dir / CONFIG_FILE, yaml.dump(config))
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution)
    assert "claude" in generated
    assert "copilot" in generated


def test_generate_agent_files_creates_directories(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test that generating agent files creates necessary directories."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["claude"])
    assert (temp_project_dir / ".claude").exists()
    assert generated["claude"].exists()


def test_update_agent_files(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test updating existing agent files."""
    service = AgentFileService(temp_project_dir)
    service.generate_agent_files(sample_constitution, ["claude"])
    sample_constitution.metadata.version = "1.1.0"
    updated = service.update_agent_files(sample_constitution)
    assert "claude" in updated
    content = updated["claude"].read_text(encoding="utf-8")
    assert "1.1.0" in content


def test_update_agent_files_only_existing(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test that update only updates existing agent files."""
    oak_dir = temp_project_dir / OAK_DIR
    oak_dir.mkdir(exist_ok=True)
    config = {"agents": ["claude", "copilot"], "version": "0.1.0"}
    write_file(oak_dir / CONFIG_FILE, yaml.dump(config))
    service = AgentFileService(temp_project_dir)
    service.generate_agent_files(sample_constitution, ["claude"])
    updated = service.update_agent_files(sample_constitution)
    assert "claude" in updated
    assert "copilot" not in updated


def test_generate_agent_file_invalid_agent(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test generating file for invalid agent."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["invalid_agent"])
    assert len(generated) == 0


def test_agent_file_content_includes_project_info(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test that generated agent files include project information."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["claude"])
    content = generated["claude"].read_text(encoding="utf-8")
    assert sample_constitution.metadata.project_name in content
    assert sample_constitution.metadata.version in content
    if sample_constitution.metadata.tech_stack:
        assert sample_constitution.metadata.tech_stack in content


def test_agent_file_content_minimal_when_missing_optional_fields(temp_project_dir: Path) -> None:
    """Test that agent files handle missing optional fields."""
    metadata = ConstitutionMetadata(
        project_name="Test",
        version="1.0.0",
        ratification_date=date(2025, 11, 6),
        author="Author",
        tech_stack=None,
    )
    constitution = ConstitutionDocument(metadata=metadata, sections=[])
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(constitution, ["claude"])
    assert "claude" in generated
    assert generated["claude"].exists()
    content = generated["claude"].read_text(encoding="utf-8")
    assert "N/A" in content


def test_from_config(temp_project_dir: Path) -> None:
    """Test creating service from configuration."""
    service = AgentFileService.from_config(temp_project_dir)
    assert isinstance(service, AgentFileService)
    assert service.project_root == temp_project_dir


def test_get_agent_file_path_claude(temp_project_dir: Path) -> None:
    """Test getting file path for Claude."""
    service = AgentFileService(temp_project_dir)
    path = service._get_agent_file_path("claude")
    assert path == temp_project_dir / ".claude" / "CLAUDE.md"


def test_get_agent_file_path_copilot(temp_project_dir: Path) -> None:
    """Test getting file path for GitHub Copilot."""
    service = AgentFileService(temp_project_dir)
    path = service._get_agent_file_path("copilot")
    assert path == temp_project_dir / ".github" / "copilot-instructions.md"


def test_get_agent_file_path_cursor_and_codex_shared(temp_project_dir: Path) -> None:
    """Test that Cursor and Codex share the same file path."""
    service = AgentFileService(temp_project_dir)
    cursor_path = service._get_agent_file_path("cursor")
    codex_path = service._get_agent_file_path("codex")
    assert cursor_path == temp_project_dir / "AGENTS.md"
    assert codex_path == temp_project_dir / "AGENTS.md"
    assert cursor_path == codex_path


def test_get_agent_file_path_invalid_agent(temp_project_dir: Path) -> None:
    """Test getting file path for invalid agent returns None."""
    service = AgentFileService(temp_project_dir)
    path = service._get_agent_file_path("invalid_agent")
    assert path is None


def test_agent_files_persist_across_service_instances(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test that generated agent files persist across service instances."""
    service1 = AgentFileService(temp_project_dir)
    generated1 = service1.generate_agent_files(sample_constitution, ["claude"])
    service2 = AgentFileService(temp_project_dir)
    agent_files = service2.list_agent_files()
    assert "claude" in agent_files
    assert agent_files["claude"] == generated1["claude"]


def test_generate_agent_files_handles_none_agent_gracefully(
    temp_project_dir: Path, sample_constitution: ConstitutionDocument
) -> None:
    """Test that 'none' agent is skipped gracefully."""
    service = AgentFileService(temp_project_dir)
    generated = service.generate_agent_files(sample_constitution, ["claude", "none"])
    assert "claude" in generated
    assert "none" not in generated
