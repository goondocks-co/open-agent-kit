from pathlib import Path

from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.migrations import _migrate_copilot_agents_folder
from open_agent_kit.services.upgrade_service import UpgradeService


def test_upgrade_installs_new_copilot_files(temp_project_dir: Path) -> None:
    """
    Reproduction test:
    1. Setup a project with legacy Copilot structure.
    2. Ensure config has 'copilot'.
    3. Run upgrade.
    4. Expect new .agent.md files in .github/agents.
    """
    # 1. Setup legacy structure
    prompts_dir = temp_project_dir / ".github" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "oak.rfc-create.prompt.md").write_text("Legacy content")

    # 2. Setup config
    config_service = ConfigService(temp_project_dir)
    config = config_service.load_config()
    config.agents = ["copilot"]
    config_service.save_config(config)

    # 3. Run upgrade
    # Note: We need to manually trigger the migration logic or simulate what the CLI does.
    # The CLI runs migrations, then plans upgrade, then executes upgrade.

    # Run migration first (as CLI does)
    _migrate_copilot_agents_folder(temp_project_dir)

    # Now run upgrade service
    service = UpgradeService(temp_project_dir)
    plan = service.plan_upgrade(commands=True, templates=False)

    # Verify plan includes Copilot commands
    copilot_commands = [cmd for cmd in plan["commands"] if cmd["agent"] == "copilot"]
    assert len(copilot_commands) > 0, "Upgrade plan should include Copilot commands"

    # Execute upgrade
    service.execute_upgrade(plan)

    # 4. Verify new files exist
    agents_dir = temp_project_dir / ".github" / "agents"
    assert agents_dir.exists()
    assert (agents_dir / "oak.rfc-create.agent.md").exists()
