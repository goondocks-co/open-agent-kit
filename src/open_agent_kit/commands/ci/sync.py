"""CI sync command: synchronize CI state after code changes."""

from pathlib import Path

import typer

from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    ci_app,
    console,
)


@ci_app.command("sync")
def ci_sync(
    full: bool = typer.Option(
        False,
        "--full",
        "-f",
        help="Force full index rebuild (deletes ChromaDB and re-indexes everything)",
    ),
    team: bool = typer.Option(
        False,
        "--team",
        "-t",
        help="Restore team backups (uses OAK_CI_BACKUP_DIR if set, else oak/history/)",
    ),
    include_activities: bool = typer.Option(
        False,
        "--include-activities",
        "-a",
        help="Include activities table in backup (larger file, useful for debugging)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Preview what would happen without making changes",
    ),
) -> None:
    """Synchronize CI state after code changes.

    Detects version mismatches and orchestrates the sync workflow:

    \b
    1. Stops daemon if version mismatch detected
    2. Restores team backups - first pass (--team)
    3. Starts daemon (runs any pending schema migrations)
    4. Creates fresh backup with current schema
    5. Restores team backups - second pass (--team)

    \b
    Examples:
        oak ci sync              # Quick sync after OAK code pull
        oak ci sync --team       # Sync + merge team backups
        oak ci sync --full       # Sync + full index rebuild
        oak ci sync --dry-run    # Preview what would happen
    """
    from open_agent_kit.features.codebase_intelligence.sync import SyncService
    from open_agent_kit.features.codebase_intelligence.sync.models import SyncReason

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    service = SyncService(project_root)

    # Detect what needs to sync
    plan = service.detect_changes(include_team=team, force_full=full)

    print_header("Codebase Intelligence Sync")

    # Show version info
    console.print()
    print_info("Version Information:")
    console.print(f"  OAK Code: {plan.current_oak_version}")
    if plan.daemon_running:
        if plan.running_oak_version:
            if plan.running_oak_version == plan.current_oak_version:
                console.print(f"  Daemon:   {plan.running_oak_version} [green](current)[/green]")
            else:
                console.print(f"  Daemon:   {plan.running_oak_version} [yellow](mismatch)[/yellow]")
        else:
            # Daemon running but not reporting version (old code)
            console.print("  Daemon:   running [yellow](old version, needs restart)[/yellow]")
    else:
        console.print("  Daemon:   not running")

    console.print(f"  Schema Code: v{plan.current_schema_version}")
    if plan.db_schema_version is not None:
        if plan.db_schema_version == plan.current_schema_version:
            console.print(f"  Schema DB:   v{plan.db_schema_version} [green](current)[/green]")
        else:
            console.print(
                f"  Schema DB:   v{plan.db_schema_version} [yellow](upgrade pending)[/yellow]"
            )

    # Show sync reasons
    console.print()
    if SyncReason.NO_CHANGES in plan.reasons:
        print_success("No sync needed - everything is up to date")
        return

    print_info("Sync Required:")
    reason_labels = {
        SyncReason.OAK_VERSION_CHANGED: "OAK version changed",
        SyncReason.SCHEMA_VERSION_CHANGED: "Schema upgrade needed",
        SyncReason.TEAM_BACKUPS_AVAILABLE: "Team backups available",
        SyncReason.MANUAL_FULL_REBUILD: "Full rebuild requested",
    }
    for reason in plan.reasons:
        if reason in reason_labels:
            console.print(f"  - {reason_labels[reason]}")

    # Show team backup info
    if plan.restore_team_backups:
        console.print()
        print_info(f"Team Backups ({plan.team_backup_count} files):")
        for f in plan.team_backup_files[:5]:
            console.print(f"  - {f}")
        if len(plan.team_backup_files) > 5:
            console.print(f"  ... and {len(plan.team_backup_files) - 5} more")

    # Show planned operations with dynamic numbering
    console.print()
    print_info("Planned Operations:")
    operations: list[str] = []
    if plan.stop_daemon:
        operations.append("Stop daemon")
    if plan.restore_team_backups:
        operations.append("Import team backups (first pass)")
    if plan.full_index_rebuild:
        operations.append("Delete ChromaDB for full rebuild")
    if plan.start_daemon:
        operations.append("Start daemon (runs migrations)")
    if plan.restore_team_backups:
        activities_note = " (with activities)" if include_activities else ""
        operations.append(f"Create fresh backup{activities_note}")
        operations.append("Import team backups (second pass)")
    for i, op in enumerate(operations, 1):
        console.print(f"  {i}. {op}")

    # Dry run stops here
    if dry_run:
        console.print()
        print_warning("Dry run - no changes made")
        return

    # Confirm and execute
    console.print()
    result = service.execute_sync(plan, dry_run=False, include_activities=include_activities)

    # Show results
    console.print()
    if result.success:
        print_success("Sync completed successfully")
    else:
        print_error("Sync completed with errors")

    if result.operations_completed:
        print_info("Operations completed:")
        for op in result.operations_completed:
            console.print(f"  [green]✓[/green] {op}")

    if result.warnings:
        console.print()
        print_warning("Warnings:")
        for warning in result.warnings:
            console.print(f"  [yellow]![/yellow] {warning}")

    if result.errors:
        console.print()
        print_error("Errors:")
        for error in result.errors:
            console.print(f"  [red]✗[/red] {error}")

    if result.records_imported > 0 or result.records_skipped > 0:
        console.print()
        print_info(
            f"Records: {result.records_imported} imported, {result.records_skipped} skipped (duplicates)"
        )

    if result.migrations_applied > 0:
        print_info(f"Migrations: {result.migrations_applied} applied")

    if not result.success:
        raise typer.Exit(code=1)
