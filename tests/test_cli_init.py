"""Tests for oak init command."""

from pathlib import Path

from open_agent_kit.commands.init_cmd import init_command


def test_init_creates_oak_directory(temp_project_dir: Path) -> None:
    """Test that init creates .oak directory."""
    init_command(force=False, agent=[], no_interactive=True)
    oak_dir = temp_project_dir / ".oak"
    assert oak_dir.exists()
    assert oak_dir.is_dir()


def test_init_creates_essential_files(temp_project_dir: Path) -> None:
    """Test that init creates essential oak files.

    Note: .oak/features/ is no longer created - feature assets are read
    directly from the installed package.
    """
    init_command(force=False, agent=[], no_interactive=True)
    oak_dir = temp_project_dir / ".oak"
    # Only essential files should be created in .oak/
    assert (oak_dir / "config.yaml").exists()
    # .oak/features/ should NOT exist (assets read from package)
    assert not (oak_dir / "features").exists()


def test_init_creates_config_file(temp_project_dir: Path) -> None:
    """Test that init creates config.yaml."""
    init_command(force=False, agent=[], no_interactive=True)
    config_file = temp_project_dir / ".oak" / "config.yaml"
    assert config_file.exists()
    assert config_file.is_file()
    content = config_file.read_text(encoding="utf-8")
    assert "version:" in content
    assert "agents:" in content


def test_init_writes_package_version(temp_project_dir: Path) -> None:
    """Test that init writes the current package version to config."""
    from open_agent_kit import __version__

    init_command(force=False, agent=[], no_interactive=True)
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(temp_project_dir)
    config = config_service.load_config()
    assert config.version == __version__


def test_init_does_not_copy_templates(temp_project_dir: Path) -> None:
    """Test that init does NOT copy templates to project.

    Templates are now read directly from the installed package,
    not copied to .oak/features/.
    """
    init_command(force=False, agent=[], no_interactive=True)
    # Templates should NOT be copied to .oak/features/
    features_dir = temp_project_dir / ".oak" / "features"
    assert not features_dir.exists()


def test_init_with_claude_agent(temp_project_dir: Path) -> None:
    """Test init with Claude agent creates command files in native directory."""
    init_command(force=False, agent=["claude"], no_interactive=True)
    commands_dir = temp_project_dir / ".claude" / "commands"
    assert commands_dir.exists()
    assert (commands_dir / "oak.rfc-create.md").exists()
    assert (commands_dir / "oak.rfc-list.md").exists()
    assert (commands_dir / "oak.rfc-validate.md").exists()


def test_init_with_multiple_agents(temp_project_dir: Path) -> None:
    """Test init with multiple agents creates command files for all."""
    init_command(force=False, agent=["claude", "copilot"], no_interactive=True)
    claude_dir = temp_project_dir / ".claude" / "commands"
    assert claude_dir.exists()
    assert (claude_dir / "oak.rfc-create.md").exists()
    copilot_dir = temp_project_dir / ".github" / "agents"
    assert copilot_dir.exists()
    assert (copilot_dir / "oak.rfc-create.agent.md").exists()


def test_init_with_force_flag(temp_project_dir: Path) -> None:
    """Test that force flag allows re-initialization."""
    init_command(force=False, agent=[], no_interactive=True)
    init_command(force=True, agent=[], no_interactive=True)
    assert (temp_project_dir / ".oak").exists()


def test_init_creates_rfc_directory(temp_project_dir: Path) -> None:
    """Test that init does NOT create oak/rfc directory (created on-demand)."""
    init_command(force=False, agent=[], no_interactive=True)
    rfc_dir = temp_project_dir / "oak" / "rfc"
    assert not rfc_dir.exists()


def test_init_adding_agents_updates_version(temp_project_dir: Path) -> None:
    """Test that updating agents in existing installation updates version."""
    from open_agent_kit import __version__
    from open_agent_kit.services.config_service import ConfigService

    # Initial setup with claude
    init_command(force=False, agent=["claude"], no_interactive=True)
    config_service = ConfigService(temp_project_dir)
    config = config_service.load_config()
    config.version = "0.0.1"
    config_service.save_config(config)

    # Update to use both claude and copilot
    init_command(force=False, agent=["claude", "copilot"], no_interactive=True)
    config = config_service.load_config()
    assert config.version == __version__
    assert "claude" in config.agents
    assert "copilot" in config.agents
