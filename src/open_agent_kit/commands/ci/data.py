"""CI data management commands: backup, restore."""

from pathlib import Path

import typer

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_DATA_DIR,
)
from open_agent_kit.utils import (
    print_error,
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


def _show_backup_info(project_root: Path, machine_id: str) -> None:
    """Display backup directory configuration information."""
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        discover_backup_files,
        get_backup_dir,
        get_backup_dir_source,
        get_backup_filename,
        validate_backup_dir,
    )
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_HISTORY_BACKUP_DIR,
        OAK_CI_BACKUP_DIR_ENV,
    )

    backup_dir = get_backup_dir(project_root)
    backup_dir_source = get_backup_dir_source(project_root)
    is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

    console.print()
    console.print("[bold]Backup Directory Configuration:[/bold]")
    console.print(f"  Path: {backup_dir}")

    if backup_dir_source == "environment variable":
        console.print(f"  Source: [cyan]environment variable[/cyan] ({OAK_CI_BACKUP_DIR_ENV})")
    elif backup_dir_source == "dotenv file (.env)":
        console.print("  Source: [cyan]dotenv file[/cyan] (.env in project root)")
    else:
        console.print("  Source: [dim]default[/dim]")

    if is_valid:
        console.print("  Status: [green]valid[/green] (exists and writable)")
    else:
        console.print(f"  Status: [red]invalid[/red] ({error_msg})")

    # Count backup files
    backup_files = discover_backup_files(backup_dir) if backup_dir.exists() else []
    console.print(f"  Backup files: {len(backup_files)}")

    # Show own backup file info
    backup_filename = get_backup_filename(machine_id)
    own_backup = backup_dir / backup_filename
    if own_backup.exists():
        size_kb = own_backup.stat().st_size / 1024
        console.print(f"  Your backup: {backup_filename} ({size_kb:.1f} KB)")
    else:
        console.print(f"  Your backup: [dim]not created yet[/dim] ({backup_filename})")

    # Check if default location also has backups when using custom dir
    if backup_dir_source != "default":
        default_dir = project_root / CI_HISTORY_BACKUP_DIR
        if default_dir.exists():
            default_files = discover_backup_files(default_dir)
            if default_files:
                console.print()
                print_warning(
                    f"Note: {len(default_files)} backup(s) also exist in default location:"
                )
                console.print(f"    {default_dir}")


@ci_app.command("backup")
def ci_backup(
    include_activities: bool = typer.Option(
        False,
        "--include-activities",
        "-a",
        help="Include activities table (can be large)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: oak/history/{machine}.sql)",
    ),
    info: bool = typer.Option(
        False,
        "--info",
        help="Show backup directory configuration and exit",
    ),
) -> None:
    """Export CI database to machine-specific SQL backup file.

    Exports sessions, prompts, and memory observations. Use --include-activities
    to also include the activities table (warning: can be large).

    Each machine creates its own backup file ({github_user}_{hash}.sql)
    in oak/history/ to prevent git conflicts when multiple developers commit backups.

    The backup file is text-based, can be committed to git, and will be
    automatically restored when the feature is re-enabled.

    Set OAK_CI_BACKUP_DIR environment variable to override the default
    backup directory (useful for shared drives or separate repos).

    Examples:
        oak ci backup                    # Backup to machine-specific file
        oak ci backup -a                 # Include activities
        oak ci backup -o custom.sql      # Custom output path
        oak ci backup --info             # Show backup config info
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_backup_dir,
        get_backup_filename,
        get_machine_identifier,
    )

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    machine_id = get_machine_identifier(project_root)

    # Handle --info flag
    if info:
        _show_backup_info(project_root, machine_id)
        return

    db_path = project_root / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        print_error("No CI database found. Start the daemon first: oak ci start")
        raise typer.Exit(code=1)

    if output:
        backup_path = Path(output)
    else:
        # Use machine-specific filename in configured backup directory
        backup_dir = get_backup_dir(project_root)
        backup_filename = get_backup_filename(machine_id)
        backup_path = backup_dir / backup_filename

    backup_path.parent.mkdir(parents=True, exist_ok=True)

    print_info(f"Exporting CI database (machine: {machine_id})...")
    print_info(f"  Output: {backup_path}")
    if include_activities:
        print_info("  Including activities table (may be large)")

    store = ActivityStore(db_path, machine_id=machine_id)
    count = store.export_to_sql(backup_path, include_activities=include_activities)
    store.close()

    print_success(f"Exported {count} records to {backup_path}")
    print_info("  This file can be committed to git for version control")
    print_info("  Other team members' backups will have different filenames")


@ci_app.command("restore")
def ci_restore(
    input_path: str | None = typer.Option(
        None,
        "--input",
        "-i",
        help="Input path (default: your machine's backup file)",
    ),
    all_backups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Restore from all backup files in oak/data/ (merge team backups)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Preview what would be restored without making changes",
    ),
) -> None:
    """Restore CI database from SQL backup file(s).

    Imports sessions, prompts, and memory observations from backup with
    content-based deduplication to prevent duplicates across machines.

    Use --all to merge all team members' backups into your database.
    Each record is only imported once based on its content hash.

    After restore, use the UI dev tools to re-embed memories to ChromaDB.

    Examples:
        oak ci restore                    # Restore from your machine's backup
        oak ci restore --all              # Merge all team backups
        oak ci restore --all --dry-run    # Preview what would be imported
        oak ci restore -i backup.sql      # Restore from specific file
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        discover_backup_files,
        extract_machine_id_from_filename,
        get_backup_dir,
        get_backup_filename,
        get_machine_identifier,
    )

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    db_path = project_root / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        print_error("No CI database found. Start the daemon first: oak ci start")
        raise typer.Exit(code=1)

    machine_id = get_machine_identifier(project_root)
    backup_dir = get_backup_dir(project_root)
    store = ActivityStore(db_path, machine_id=machine_id)

    if all_backups:
        # Restore from all backup files
        backup_files = discover_backup_files(backup_dir)

        if not backup_files:
            print_warning(f"No backup files found in {backup_dir}")
            store.close()
            return

        print_info(f"Found {len(backup_files)} backup file(s):")
        for bf in backup_files:
            machine_id = extract_machine_id_from_filename(bf.name)
            size_kb = bf.stat().st_size / 1024
            console.print(f"  • {bf.name} ({machine_id}, {size_kb:.1f} KB)")

        if dry_run:
            print_info("\nDry run - previewing what would be imported...")

        console.print()
        results = store.restore_all_backups(backup_dir, dry_run=dry_run)

        # Show summary
        total_imported = sum(r.total_imported for r in results.values())
        total_skipped = sum(r.total_skipped for r in results.values())
        total_errors = sum(r.errors for r in results.values())

        console.print()
        if dry_run:
            print_info("Dry run summary (no changes made):")
        else:
            print_success("Restore complete!")

        print_info(
            f"  Sessions: {sum(r.sessions_imported for r in results.values())} imported, "
            f"{sum(r.sessions_skipped for r in results.values())} skipped"
        )
        print_info(
            f"  Batches: {sum(r.batches_imported for r in results.values())} imported, "
            f"{sum(r.batches_skipped for r in results.values())} skipped"
        )
        print_info(
            f"  Memories: {sum(r.observations_imported for r in results.values())} imported, "
            f"{sum(r.observations_skipped for r in results.values())} skipped"
        )
        print_info(
            f"  Activities: {sum(r.activities_imported for r in results.values())} imported, "
            f"{sum(r.activities_skipped for r in results.values())} skipped"
        )

        if total_errors > 0:
            print_warning(f"  Errors: {total_errors}")

        console.print()
        print_info(f"  Total: {total_imported} imported, {total_skipped} skipped (duplicates)")

    else:
        # Restore from single file
        if input_path:
            backup_path = Path(input_path)
        else:
            # Default to this machine's backup file
            backup_filename = get_backup_filename(machine_id)
            backup_path = backup_dir / backup_filename

            # Fall back to legacy filename if machine-specific doesn't exist
            if not backup_path.exists():
                legacy_path = backup_dir / "ci_history.sql"
                if legacy_path.exists():
                    backup_path = legacy_path
                    print_info("Using legacy backup file (ci_history.sql)")

        if not backup_path.exists():
            print_error(f"Backup file not found: {backup_path}")
            print_info("  Available backups:")
            for bf in discover_backup_files(backup_dir):
                console.print(f"    • {bf.name}")
            store.close()
            raise typer.Exit(code=1)

        if dry_run:
            print_info(f"Dry run - previewing restore from {backup_path}...")
        else:
            print_info(f"Restoring CI database from {backup_path}...")

        result = store.import_from_sql_with_dedup(backup_path, dry_run=dry_run)

        console.print()
        if dry_run:
            print_info("Dry run summary (no changes made):")
        else:
            print_success("Restore complete!")

        print_info(
            f"  Sessions: {result.sessions_imported} imported, "
            f"{result.sessions_skipped} skipped"
        )
        print_info(
            f"  Batches: {result.batches_imported} imported, " f"{result.batches_skipped} skipped"
        )
        print_info(
            f"  Memories: {result.observations_imported} imported, "
            f"{result.observations_skipped} skipped"
        )
        print_info(
            f"  Activities: {result.activities_imported} imported, "
            f"{result.activities_skipped} skipped"
        )

        if result.errors > 0:
            print_warning(f"  Errors: {result.errors}")

    store.close()

    if not dry_run:
        console.print()
        print_info("Next steps:")
        print_info("  1. Restart daemon: oak ci restart")
        print_info("  2. Re-embed memories: Use UI Dev Tools → Re-embed Memories to ChromaDB")
