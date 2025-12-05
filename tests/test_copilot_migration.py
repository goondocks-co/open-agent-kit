import pytest

from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.migrations import _migrate_copilot_agents_folder


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    # Create .oak directory
    (tmp_path / ".oak").mkdir()

    # Create legacy prompts directory
    prompts_dir = tmp_path / ".github" / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create dummy legacy prompt file
    (prompts_dir / "oak.test.prompt.md").write_text("Legacy content")
    (prompts_dir / "custom.prompt.md").write_text("Custom content")

    return tmp_path


def test_copilot_config_uses_new_paths():
    """Verify Copilot manifest uses new paths."""
    service = AgentService()
    manifest = service.get_agent_manifest("copilot")
    assert manifest.installation.commands_subfolder == "agents"
    assert manifest.installation.file_extension == ".agent.md"


def test_migration_removes_legacy_files(temp_project):
    """Verify migration removes legacy oak files but keeps custom ones."""
    # Run migration
    _migrate_copilot_agents_folder(temp_project)

    prompts_dir = temp_project / ".github" / "prompts"

    # Oak file should be gone
    assert not (prompts_dir / "oak.test.prompt.md").exists()

    # Custom file should remain
    assert (prompts_dir / "custom.prompt.md").exists()
    assert prompts_dir.exists()


def test_migration_removes_empty_dir(temp_project):
    """Verify migration removes directory if empty."""
    # Remove custom file so dir becomes empty after migration
    (temp_project / ".github" / "prompts" / "custom.prompt.md").unlink()

    # Run migration
    _migrate_copilot_agents_folder(temp_project)

    prompts_dir = temp_project / ".github" / "prompts"
    assert not prompts_dir.exists()


def test_agent_service_paths(temp_project):
    """Verify AgentService uses new paths for Copilot."""
    service = AgentService(project_root=temp_project)

    # Check commands dir
    commands_dir = service.get_agent_commands_dir("copilot")
    assert commands_dir == temp_project / ".github" / "agents"

    # Check filename
    filename = service.get_command_filename("copilot", "rfc-create")
    assert filename == "oak.rfc-create.agent.md"
