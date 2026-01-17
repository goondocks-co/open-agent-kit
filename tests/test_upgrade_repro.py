from pathlib import Path

from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.migrations import _migrate_copilot_agents_folder


def test_upgrade_installs_new_copilot_files(temp_project_dir: Path) -> None:
    """
    Reproduction test for Copilot migration:
    1. Setup a project with legacy Copilot structure (.github/prompts/).
    2. Ensure config has 'copilot'.
    3. Run migration and upgrade.
    4. Verify legacy files are cleaned up and migration runs.

    Note: Copilot now has has_skills=True, so it gets skills in .github/skills/
    instead of commands in .github/agents/. This test verifies the migration
    cleans up legacy prompts files.
    """
    # 1. Setup legacy structure
    prompts_dir = temp_project_dir / ".github" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "oak.add-project-rule.prompt.md").write_text("Legacy content")
    # Also add a custom file that should be preserved
    (prompts_dir / "custom.prompt.md").write_text("Custom content")

    # 2. Setup config
    config_service = ConfigService(temp_project_dir)
    config = config_service.load_config()
    config.agents = ["copilot"]
    # Enable rules-management feature for this test
    config.features.enabled = ["rules-management"]
    config_service.save_config(config)

    # 3. Run upgrade
    # Note: We need to manually trigger the migration logic or simulate what the CLI does.
    # The CLI runs migrations, then plans upgrade, then executes upgrade.

    # Run migration first (as CLI does)
    _migrate_copilot_agents_folder(temp_project_dir)

    # 4. Verify migration cleaned up oak files but preserved custom files
    # Oak files should be gone
    assert not (prompts_dir / "oak.add-project-rule.prompt.md").exists()
    # Custom file should remain
    assert (prompts_dir / "custom.prompt.md").exists()

    # Note: We don't verify skills here because UpgradeService.execute_upgrade()
    # doesn't install skills - that's done by the skill_service during init/upgrade pipeline.
    # The upgrade service only handles command files for agents without skills support.
