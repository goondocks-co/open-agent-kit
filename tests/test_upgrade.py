"""Tests for upgrade command and service."""

from pathlib import Path

from open_agent_kit.services.upgrade_service import UpgradeService


def test_is_initialized_false_when_no_oak_dir(temp_project_dir: Path) -> None:
    """Test is_initialized returns False when .oak doesn't exist."""
    service = UpgradeService(temp_project_dir)
    assert not service.is_initialized()


def test_is_initialized_true_when_oak_dir_exists(initialized_project: Path) -> None:
    """Test is_initialized returns True when .oak exists."""
    service = UpgradeService(initialized_project)
    assert service.is_initialized()


def test_plan_upgrade_with_no_agents(initialized_project: Path) -> None:
    """Test plan_upgrade returns empty plan when no agents configured."""
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()
    assert "commands" in plan
    assert "templates" in plan
    assert plan["commands"] == []
    assert isinstance(plan["templates"], list)


def test_plan_upgrade_commands_only(initialized_project: Path) -> None:
    """Test plan_upgrade with commands=True, templates=False."""
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=True, templates=False)
    assert "commands" in plan
    assert "templates" in plan
    assert plan["templates"] == []


def test_plan_upgrade_templates_only(initialized_project: Path) -> None:
    """Test plan_upgrade with commands=False, templates=True."""
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=False, templates=True)
    assert "commands" in plan
    assert "templates" in plan
    assert plan["commands"] == []
    assert isinstance(plan["templates"], list)


def test_files_differ_identical_files(initialized_project: Path) -> None:
    """Test _files_differ returns False for identical files."""
    service = UpgradeService(initialized_project)
    file1 = initialized_project / "test1.txt"
    file2 = initialized_project / "test2.txt"
    content = "Test content\n"
    file1.write_text(content, encoding="utf-8")
    file2.write_text(content, encoding="utf-8")
    assert not service._files_differ(file1, file2)


def test_files_differ_different_files(initialized_project: Path) -> None:
    """Test _files_differ returns True for different files."""
    service = UpgradeService(initialized_project)
    file1 = initialized_project / "test1.txt"
    file2 = initialized_project / "test2.txt"
    file1.write_text("Content A\n", encoding="utf-8")
    file2.write_text("Content B\n", encoding="utf-8")
    assert service._files_differ(file1, file2)


def test_files_differ_nonexistent_file(initialized_project: Path) -> None:
    """Test _files_differ returns False when file doesn't exist."""
    service = UpgradeService(initialized_project)
    file1 = initialized_project / "test1.txt"
    file2 = initialized_project / "nonexistent.txt"
    file1.write_text("Content\n", encoding="utf-8")
    assert not service._files_differ(file1, file2)


def test_plan_upgrade_detects_modified_command(initialized_project: Path) -> None:
    """Test that plan_upgrade detects modified agent command files."""
    from open_agent_kit.commands.init_cmd import init_command

    init_command(force=False, agent=["claude"], no_interactive=True)
    commands_dir = initialized_project / ".claude" / "commands"
    command_file = commands_dir / "oak.rfc-create.md"
    assert command_file.exists()
    original_content = command_file.read_text(encoding="utf-8")
    command_file.write_text(original_content + "\n# Modified\n", encoding="utf-8")
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=True, templates=False)
    assert len(plan["commands"]) > 0
    assert any(cmd["file"] == "oak.rfc-create.md" for cmd in plan["commands"])


def test_execute_upgrade_restores_command(initialized_project: Path) -> None:
    """Test that execute_upgrade restores modified command file."""
    from open_agent_kit.commands.init_cmd import init_command

    init_command(force=False, agent=["claude"], no_interactive=True)
    commands_dir = initialized_project / ".claude" / "commands"
    command_file = commands_dir / "oak.rfc-create.md"
    original_content = command_file.read_text(encoding="utf-8")
    modified_content = original_content + "\n# Modified\n"
    command_file.write_text(modified_content, encoding="utf-8")
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=True, templates=False)
    results = service.execute_upgrade(plan)
    assert len(results["commands"]["upgraded"]) > 0
    assert "oak.rfc-create.md" in results["commands"]["upgraded"]
    restored_content = command_file.read_text(encoding="utf-8")
    assert "# Modified" not in restored_content
    assert restored_content == original_content


def test_execute_upgrade_with_empty_plan(initialized_project: Path) -> None:
    """Test execute_upgrade with empty plan does nothing."""
    service = UpgradeService(initialized_project)
    empty_plan = {
        "commands": [],
        "templates": [],
        "templates_customized": False,
        "obsolete_templates": [],
        "ide_settings": [],
        "skills": {"install": [], "upgrade": []},
        "migrations": [],
        "structural_repairs": [],
        "version_outdated": False,
        "current_version": "1.0.0",
        "package_version": "1.0.0",
    }
    results = service.execute_upgrade(empty_plan)
    assert results["commands"]["upgraded"] == []
    assert results["commands"]["failed"] == []
    assert results["templates"]["upgraded"] == []
    assert results["templates"]["failed"] == []
    assert results["ide_settings"]["upgraded"] == []
    assert results["ide_settings"]["failed"] == []


def test_plan_upgrade_multiple_agents(initialized_project: Path) -> None:
    """Test plan_upgrade with multiple agents configured."""
    from open_agent_kit.commands.init_cmd import init_command

    init_command(force=False, agent=["claude", "copilot"], no_interactive=True)
    claude_dir = initialized_project / ".claude" / "commands"
    copilot_dir = initialized_project / ".github" / "agents"
    claude_file = claude_dir / "oak.rfc-create.md"
    copilot_file = copilot_dir / "oak.rfc-create.agent.md"
    claude_file.write_text(
        claude_file.read_text(encoding="utf-8") + "\n# Modified Claude\n", encoding="utf-8"
    )
    copilot_file.write_text(
        copilot_file.read_text(encoding="utf-8") + "\n# Modified Copilot\n", encoding="utf-8"
    )
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=True, templates=False)
    assert len(plan["commands"]) >= 2
    agents = [cmd["agent"] for cmd in plan["commands"]]
    assert "claude" in agents
    assert "copilot" in agents


def test_get_upgrade_service_helper() -> None:
    """Test get_upgrade_service helper function."""
    from open_agent_kit.services.upgrade_service import get_upgrade_service

    service = get_upgrade_service()
    assert isinstance(service, UpgradeService)
    assert service.project_root == Path.cwd()


def test_upgrade_service_with_custom_project_root(temp_project_dir: Path) -> None:
    """Test UpgradeService with custom project root."""
    service = UpgradeService(temp_project_dir)
    assert service.project_root == temp_project_dir


def test_execute_upgrade_updates_config_version(initialized_project: Path) -> None:
    """Test that execute_upgrade updates the config version."""
    from open_agent_kit import __version__
    from open_agent_kit.commands.init_cmd import init_command
    from open_agent_kit.services.config_service import ConfigService

    init_command(force=False, agent=["claude"], no_interactive=True)
    config_service = ConfigService(initialized_project)
    config = config_service.load_config()
    config.version = "0.0.1"
    config_service.save_config(config)
    commands_dir = initialized_project / ".claude" / "commands"
    command_file = commands_dir / "oak.rfc-create.md"
    original_content = command_file.read_text(encoding="utf-8")
    command_file.write_text(original_content + "\n# Modified\n", encoding="utf-8")
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade(commands=True, templates=False)
    results = service.execute_upgrade(plan)
    assert results["version_updated"] is True
    config = config_service.load_config()
    assert config.version == __version__


def test_execute_upgrade_no_version_update_when_nothing_upgraded(initialized_project: Path) -> None:
    """Test that version is not updated when nothing was upgraded."""
    service = UpgradeService(initialized_project)
    empty_plan = {
        "commands": [],
        "templates": [],
        "templates_customized": False,
        "obsolete_templates": [],
        "ide_settings": [],
        "skills": {"install": [], "upgrade": []},
        "migrations": [],
        "structural_repairs": [],
        "version_outdated": False,
        "current_version": "1.0.0",
        "package_version": "1.0.0",
    }
    results = service.execute_upgrade(empty_plan)
    assert results["version_updated"] is False


def test_plan_upgrade_detects_outdated_version(initialized_project: Path) -> None:
    """Test that plan_upgrade detects when config version is outdated."""
    from open_agent_kit import __version__
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(initialized_project)
    config = config_service.load_config()
    config.version = "0.0.1"
    config_service.save_config(config)
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()
    assert plan["version_outdated"] is True
    assert plan["current_version"] == "0.0.1"
    assert plan["package_version"] == __version__


def test_plan_upgrade_current_version_not_outdated(initialized_project: Path) -> None:
    """Test that plan_upgrade recognizes current version as up to date."""
    from open_agent_kit import __version__
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(initialized_project)
    config = config_service.load_config()
    config.version = __version__
    config_service.save_config(config)
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()
    assert plan["version_outdated"] is False
    assert plan["current_version"] == __version__
    assert plan["package_version"] == __version__


def test_execute_upgrade_updates_version_when_outdated(initialized_project: Path) -> None:
    """Test that execute_upgrade updates version even if no files changed."""
    from open_agent_kit import __version__
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(initialized_project)
    config = config_service.load_config()
    config.version = "0.0.1"
    config_service.save_config(config)
    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()
    assert plan["version_outdated"] is True
    assert len(plan["commands"]) == 0
    assert len(plan["templates"]) == 0
    results = service.execute_upgrade(plan)
    assert results["version_updated"] is True
    config = config_service.load_config()
    assert config.version == __version__


def test_detects_rfc_templates_needing_upgrade(initialized_project: Path) -> None:
    """Test that upgrade detects RFC templates that need updating."""
    from open_agent_kit.config.paths import OAK_DIR

    # Templates directory exists from initialization
    templates_dir = initialized_project / OAK_DIR / "features" / "rfc" / "templates"

    # Modify a template to make it different from package version
    (templates_dir / "engineering.md").write_text("# Old content", encoding="utf-8")

    # Delete some templates to test detection of missing templates
    (templates_dir / "architecture.md").unlink()
    (templates_dir / "feature.md").unlink()

    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()

    # Should detect engineering.md needs update (exists but differs)
    assert "rfc/engineering.md" in plan["templates"]
    # Should also detect deleted templates as needing installation
    assert "rfc/architecture.md" in plan["templates"]
    assert "rfc/feature.md" in plan["templates"]
    # process.md should not be in list (exists and matches package version)
    # Unless we also deleted it, but we didn't, so it should be identical


def test_detects_constitution_templates_needing_upgrade(initialized_project: Path) -> None:
    """Test that upgrade detects constitution templates that need updating."""
    from open_agent_kit.config.paths import OAK_DIR

    # Templates directory exists from initialization
    templates_dir = initialized_project / OAK_DIR / "features" / "constitution" / "templates"

    # Modify a template to make it different from package version
    (templates_dir / "base_constitution.md").write_text("# Old content", encoding="utf-8")

    # Delete another template to test detection of missing templates
    (templates_dir / "agent_instructions.md").unlink()

    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()

    # Should detect both templates
    assert "constitution/base_constitution.md" in plan["templates"]
    assert "constitution/agent_instructions.md" in plan["templates"]


def test_upgrade_only_checks_known_template_categories(initialized_project: Path) -> None:
    """Test that upgrade only checks RFC and constitution templates, not all .md files."""
    from open_agent_kit.config.paths import OAK_DIR

    # Create a random .md file that shouldn't be detected
    (initialized_project / "README.md").write_text("# Random file", encoding="utf-8")
    (initialized_project / OAK_DIR / "notes.md").write_text("# Notes", encoding="utf-8")

    service = UpgradeService(initialized_project)
    plan = service.plan_upgrade()

    # Should not include README.md or notes.md
    assert not any("README" in t for t in plan["templates"])
    assert not any("notes" in t for t in plan["templates"])
    # Should only include RFC and constitution templates
    assert all(t.startswith(("rfc/", "constitution/")) for t in plan["templates"])
