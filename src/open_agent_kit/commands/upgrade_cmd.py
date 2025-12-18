"""Upgrade command for updating open-agent-kit templates and commands."""

from pathlib import Path

import typer

from open_agent_kit.config.messages import (
    ERROR_MESSAGES,
    INFO_MESSAGES,
    PROJECT_URL,
    SUCCESS_MESSAGES,
    UPGRADE_MESSAGES,
    WARNING_MESSAGES,
)
from open_agent_kit.constants import VERSION
from open_agent_kit.services.upgrade_service import UpgradePlan, UpgradeResults, UpgradeService
from open_agent_kit.utils import (
    StepTracker,
    confirm,
    print_error,
    print_header,
    print_info,
    print_panel,
)


def upgrade_command(
    commands: bool = typer.Option(
        False,
        "--commands",
        "-c",
        help="Upgrade only agent command templates",
    ),
    templates: bool = typer.Option(
        False,
        "--templates",
        "-t",
        help="Upgrade only command templates",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Preview changes without applying them",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts",
    ),
) -> None:
    """Upgrade open-agent-kit templates and agent commands.

    Upgrades agent command prompts and command helper templates to the latest versions.
    Agent commands are always safe to upgrade. command helper templates will warn if customized.
    """
    project_root = Path.cwd()

    # Initialize upgrade service
    upgrade_service = UpgradeService(project_root)

    # Check if open-agent-kit is initialized
    if not upgrade_service.is_initialized():
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    print_header("Upgrade open-agent-kit")

    # Determine what to upgrade
    upgrade_all = not commands and not templates
    upgrade_commands = commands or upgrade_all
    upgrade_templates = templates or upgrade_all

    if dry_run:
        print_info(f"{INFO_MESSAGES['dry_run_mode']}\n")

    # Get upgrade plan
    plan = upgrade_service.plan_upgrade(
        commands=upgrade_commands,
        templates=upgrade_templates,
    )

    # Check if there's anything to upgrade
    skill_plan = plan["skills"]
    has_upgrades = (
        plan["commands"]
        or plan["templates"]
        or plan["obsolete_templates"]
        or plan["ide_settings"]
        or skill_plan["install"]
        or skill_plan["upgrade"]
        or plan["migrations"]
        or plan["structural_repairs"]
        or plan["version_outdated"]
    )

    if not has_upgrades:
        print_info(f"[green]✓[/green] {SUCCESS_MESSAGES['up_to_date']}")
        return

    # Display what will be upgraded
    _display_upgrade_plan(plan, dry_run)

    # Confirm if not forced and not dry-run
    if not force and not dry_run:
        if not confirm("\nProceed with upgrade?", default=True):
            print_info(f"\n{INFO_MESSAGES['upgrade_cancelled']}")
            return

    # Execute upgrade
    if not dry_run:
        print_info("")  # Blank line

        # Trigger pre-upgrade hooks
        from open_agent_kit.services.feature_service import FeatureService

        feature_service = FeatureService(project_root)
        try:
            feature_service.trigger_pre_upgrade_hooks(dict(plan))
        except Exception:
            pass  # Hook failures are not fatal

        # Execute the upgrade
        results = upgrade_service.execute_upgrade(plan)

        # Trigger post-upgrade hooks
        try:
            feature_service.trigger_post_upgrade_hooks(dict(results))
        except Exception:
            pass  # Hook failures are not fatal

        _display_upgrade_results(results)
    else:
        print_info(f"\n[dim]{INFO_MESSAGES['dry_run_complete']}[/dim]")


def _display_upgrade_plan(plan: UpgradePlan, dry_run: bool) -> None:
    """Display what will be upgraded.

    Args:
        plan: Upgrade plan from UpgradeService.plan_upgrade()
        dry_run: Whether this is a dry run
    """
    action = UPGRADE_MESSAGES["would_upgrade"] if dry_run else UPGRADE_MESSAGES["will_upgrade"]

    sections = []

    # Version upgrade
    if plan.get("version_outdated"):
        current_ver = plan.get("current_version", "unknown")
        package_ver = plan.get("package_version", "unknown")
        sections.append(
            f"[cyan]{UPGRADE_MESSAGES['section_project_version']}[/cyan]\n"
            f"  • {UPGRADE_MESSAGES['current_version'].format(version=current_ver)}\n"
            f"  • {UPGRADE_MESSAGES['update_to_version'].format(version=package_ver)}"
        )

    # Command upgrades
    if plan["commands"]:
        command_list = "\n".join([f"  • {cmd['agent']}: {cmd['file']}" for cmd in plan["commands"]])
        sections.append(
            f"[cyan]{UPGRADE_MESSAGES['section_agent_commands']}[/cyan] ({len(plan['commands'])} files)\n{command_list}"
        )

    # Template upgrades
    if plan["templates"]:
        template_list = "\n".join([f"  • {tpl}" for tpl in plan["templates"]])
        sections.append(
            f"[cyan]{UPGRADE_MESSAGES['section_templates']}[/cyan] ({len(plan['templates'])} files)\n{template_list}"
        )

        if plan.get("templates_customized"):
            sections.append(f"\n[yellow]⚠[/yellow]  {WARNING_MESSAGES['templates_customized']}")

    # Obsolete templates to remove
    if plan.get("obsolete_templates"):
        obsolete_list = "\n".join([f"  • {tpl}" for tpl in plan["obsolete_templates"]])
        sections.append(
            f"[cyan]Obsolete Templates[/cyan] ({len(plan['obsolete_templates'])} files to remove)\n{obsolete_list}"
        )

    # IDE settings upgrades
    if plan["ide_settings"]:
        ide_list = "\n".join([f"  • {ide}" for ide in plan["ide_settings"]])
        sections.append(
            f"[cyan]IDE Settings[/cyan] ({len(plan['ide_settings'])} IDE(s))\n{ide_list}"
        )

    # Skills installation and upgrade
    skill_plan = plan["skills"]
    skills_to_install = skill_plan["install"]
    skills_to_upgrade = skill_plan["upgrade"]

    if skills_to_install:
        install_list = "\n".join(
            [f"  • {s['skill']} (from {s['feature']} feature)" for s in skills_to_install]
        )
        sections.append(
            f"[cyan]Skills to Install[/cyan] ({len(skills_to_install)} skill(s))\n{install_list}"
        )

    if skills_to_upgrade:
        upgrade_list = "\n".join(
            [f"  • {s['skill']} (from {s['feature']} feature)" for s in skills_to_upgrade]
        )
        sections.append(
            f"[cyan]Skills to Upgrade[/cyan] ({len(skills_to_upgrade)} skill(s))\n{upgrade_list}"
        )

    # Structural repairs
    if plan.get("structural_repairs"):
        repair_list = "\n".join([f"  • {r}" for r in plan["structural_repairs"]])
        sections.append(
            f"[cyan]Structural Repairs[/cyan] ({len(plan['structural_repairs'])} item(s))\n{repair_list}"
        )

    # Migrations
    if plan.get("migrations"):
        migration_list = "\n".join([f"  • {m['description']}" for m in plan["migrations"]])
        sections.append(
            f"[cyan]Migrations[/cyan] ({len(plan['migrations'])} task(s))\n{migration_list}"
        )

    content = f"[bold]{action}:[/bold]\n\n" + "\n\n".join(sections)

    print_panel(content, title=UPGRADE_MESSAGES["upgrade_plan_title"], style="cyan")


def _display_upgrade_results(results: UpgradeResults) -> None:
    """Display upgrade results.

    Args:
        results: Upgrade results TypedDict
    """
    # Count total steps needed
    steps = 0
    if results.get("commands", {}).get("upgraded"):
        steps += 1
    if results.get("templates", {}).get("upgraded"):
        steps += 1
    if results.get("obsolete_removed", {}).get("upgraded"):
        steps += 1
    if results.get("ide_settings", {}).get("upgraded"):
        steps += 1
    if results.get("skills", {}).get("upgraded"):
        steps += 1
    if results.get("structural_repairs"):
        steps += 1
    if results.get("migrations", {}).get("upgraded"):
        steps += 1
    if results.get("version_updated"):
        steps += 1

    tracker = StepTracker(steps)

    # Commands upgrade
    if results.get("commands"):
        upgraded = results["commands"]["upgraded"]
        failed = results["commands"]["failed"]

        if upgraded:
            tracker.start_step(
                INFO_MESSAGES["upgrading_agent_commands"].format(count=len(upgraded))
            )
            tracker.complete_step(
                SUCCESS_MESSAGES["upgraded_agent_commands"].format(count=len(upgraded))
            )

        if failed:
            tracker.start_step("Command upgrade failures")
            tracker.fail_step(
                f"Failed to upgrade {len(failed)} command(s)",
                ", ".join(failed),
            )

    # Templates upgrade
    if results.get("templates"):
        upgraded = results["templates"]["upgraded"]
        failed = results["templates"]["failed"]

        if upgraded:
            tracker.start_step(INFO_MESSAGES["upgrading_templates"].format(count=len(upgraded)))
            tracker.complete_step(
                SUCCESS_MESSAGES["upgraded_templates"].format(count=len(upgraded))
            )

        if failed:
            tracker.start_step("Template upgrade failures")
            tracker.fail_step(
                f"Failed to upgrade {len(failed)} template(s)",
                ", ".join(failed),
            )

    # Obsolete template removal
    if results.get("obsolete_removed"):
        upgraded = results["obsolete_removed"]["upgraded"]
        failed = results["obsolete_removed"]["failed"]

        if upgraded:
            tracker.start_step(f"Removing {len(upgraded)} obsolete template(s)")
            tracker.complete_step(f"Removed {len(upgraded)} obsolete template(s)")

        if failed:
            tracker.start_step("Obsolete removal failures")
            tracker.fail_step(
                f"Failed to remove {len(failed)} template(s)",
                ", ".join(failed),
            )

    # IDE settings upgrade
    if results.get("ide_settings"):
        upgraded = results["ide_settings"]["upgraded"]
        failed = results["ide_settings"]["failed"]

        if upgraded:
            tracker.start_step(f"Upgrading IDE settings for {len(upgraded)} IDE(s)")
            tracker.complete_step(f"Upgraded IDE settings for {len(upgraded)} IDE(s)")

        if failed:
            tracker.start_step("IDE settings upgrade failures")
            tracker.fail_step(
                f"Failed to upgrade {len(failed)} IDE setting(s)",
                ", ".join(failed),
            )

    # Skills installation/upgrade
    if results.get("skills"):
        upgraded = results["skills"]["upgraded"]
        failed = results["skills"]["failed"]

        if upgraded:
            tracker.start_step(f"Installing/upgrading {len(upgraded)} skill(s)")
            tracker.complete_step(f"Installed/upgraded {len(upgraded)} skill(s)")

        if failed:
            tracker.start_step("Skill installation failures")
            tracker.fail_step(
                f"Failed to install/upgrade {len(failed)} skill(s)",
                ", ".join(failed),
            )

    # Structural repairs
    if results.get("structural_repairs"):
        repaired = results["structural_repairs"]
        tracker.start_step(f"Repairing {len(repaired)} structural issue(s)")
        tracker.complete_step(f"Repaired {len(repaired)} structural issue(s)")

    # Migrations
    if results.get("migrations"):
        upgraded = results["migrations"]["upgraded"]
        failed = results["migrations"]["failed"]

        if upgraded:
            tracker.start_step(f"Running {len(upgraded)} migration(s)")
            tracker.complete_step(f"Completed {len(upgraded)} migration(s)")

        if failed:
            tracker.start_step("Migration failures")
            tracker.fail_step(
                f"Failed to run {len(failed)} migration(s)",
                ", ".join(failed),
            )

    # Version update
    if results.get("version_updated"):
        tracker.start_step(INFO_MESSAGES["updating_project_version"])
        tracker.complete_step(SUCCESS_MESSAGES["updated_project_version"].format(version=VERSION))

    tracker.finish(SUCCESS_MESSAGES["upgrade_complete"])

    # Display what's new based on what was upgraded
    _display_whats_new(results)


def _display_whats_new(results: UpgradeResults) -> None:
    """Display what's new after upgrade.

    Args:
        results: Upgrade results from UpgradeService
    """
    commands_upgraded = len(results.get("commands", {}).get("upgraded", []))
    templates_upgraded = len(results.get("templates", {}).get("upgraded", []))
    obsolete_removed = len(results.get("obsolete_removed", {}).get("upgraded", []))
    ide_settings_upgraded = len(results.get("ide_settings", {}).get("upgraded", []))
    skills_upgraded = len(results.get("skills", {}).get("upgraded", []))
    version_updated = results.get("version_updated", False)

    # Build message based on what was upgraded
    if (
        commands_upgraded > 0
        or templates_upgraded > 0
        or obsolete_removed > 0
        or ide_settings_upgraded > 0
        or skills_upgraded > 0
    ):
        # Files were upgraded
        message_parts = [f"[bold green]{UPGRADE_MESSAGES['whats_new_title']}[/bold green]\n\n"]

        if commands_upgraded > 0:
            message_parts.append(
                f"✓ {SUCCESS_MESSAGES['upgraded_agent_commands'].format(count=commands_upgraded)}\n"
            )

        if templates_upgraded > 0:
            message_parts.append(
                f"✓ {SUCCESS_MESSAGES['upgraded_templates'].format(count=templates_upgraded)}\n"
            )

        if obsolete_removed > 0:
            message_parts.append(f"✓ Removed {obsolete_removed} obsolete template(s)\n")

        if ide_settings_upgraded > 0:
            message_parts.append(f"✓ Upgraded IDE settings for {ide_settings_upgraded} IDE(s)\n")

        if skills_upgraded > 0:
            message_parts.append(f"✓ Installed/upgraded {skills_upgraded} agent skill(s)\n")

        if version_updated:
            message_parts.append(
                f"✓ {SUCCESS_MESSAGES['updated_project_version'].format(version=VERSION)}\n"
            )

        release_url = f"{PROJECT_URL}/releases/tag/v{VERSION}"
        message_parts.append(
            f"\n[dim]{UPGRADE_MESSAGES['release_notes']}[/dim]\n" f"[cyan]{release_url}[/cyan]"
        )

        print_panel(
            "".join(message_parts),
            title=UPGRADE_MESSAGES["upgrade_summary_title"],
            style="green",
        )
    elif version_updated:
        # Only version was updated
        release_url = f"{PROJECT_URL}/releases/tag/v{VERSION}"
        print_panel(
            f"[bold green]Updated to v{VERSION}[/bold green]\n\n"
            f"[dim]{UPGRADE_MESSAGES['release_notes']}[/dim]\n"
            f"[cyan]{release_url}[/cyan]",
            title=UPGRADE_MESSAGES["upgrade_summary_title"],
            style="green",
        )
