"""RFC management commands."""

import json
import os
from pathlib import Path

import typer

from open_agent_kit.config.messages import (
    ERROR_MESSAGES,
    HINTS,
    INFO_MESSAGES,
    SUCCESS_MESSAGES,
    USAGE_EXAMPLES,
    WARNING_MESSAGES,
)
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.rfc_service import RFCService
from open_agent_kit.utils import (
    StepTracker,
    dir_exists,
    get_project_root,
    print_divider,
    print_error,
    print_header,
    print_info,
    print_key_value,
    print_muted,
    print_panel,
    print_success,
    print_table,
    print_warning,
    prompt,
)

# Create RFC command group
rfc_app = typer.Typer(
    name="rfc",
    help="RFC management commands (create, validate, list)",
    no_args_is_help=True,
)


@rfc_app.command("create")
def create_rfc(
    description: str = typer.Argument(..., help="RFC description or title"),
    author: str | None = typer.Option(
        None,
        "--author",
        "-a",
        help="RFC author name",
    ),
    template: str = typer.Option(
        "engineering",
        "--template",
        "-t",
        help="Template to use",
    ),
    tags: str | None = typer.Option(
        None,
        "--tags",
        help="Comma-separated tags",
    ),
    number: str | None = typer.Option(
        None,
        "--number",
        "-n",
        help="Custom RFC number",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Skip interactive prompts",
    ),
) -> None:
    """Create a new RFC document.

    Creates an RFC document from a template with auto-generated number,
    filename, and initial content structure.

    Example:
        oak rfc create "Add user authentication system"
    """
    # Check if open-agent-kit is initialized
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    print_header("Create RFC")

    # Get author from environment or prompt
    rfc_author = author
    if not rfc_author:
        # Try to get from git config
        try:
            import subprocess

            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                rfc_author = result.stdout.strip()
        except Exception:
            pass

        # Prompt if still not found and interactive mode
        if not rfc_author and not no_interactive:
            rfc_author = prompt("Author name", required=True)
        elif not rfc_author:
            rfc_author = "Unknown"

    # Parse tags
    rfc_tags = []
    if tags:
        rfc_tags = [tag.strip() for tag in tags.split(",")]

    # Create RFC
    tracker = StepTracker(3)

    tracker.start_step("Generating RFC")
    try:
        rfc_service = RFCService(project_root)
        rfc = rfc_service.create_rfc(
            title=description,
            author=rfc_author,
            template_name=template,
            tags=rfc_tags,
            rfc_number=number,
        )
        tracker.complete_step(f"Created RFC-{rfc.number}")
    except FileExistsError as e:
        tracker.fail_step("RFC already exists", str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        tracker.fail_step("Failed to create RFC", str(e))
        raise typer.Exit(code=1)

    # Validate RFC
    tracker.start_step("Validating RFC")
    try:
        config_service = ConfigService(project_root)
        config = config_service.load_config()

        if config.rfc.validate_on_create:
            is_valid, issues = rfc_service.validate_rfc(rfc.path, strict=False)  # type: ignore[arg-type]  # path is Path | None but guaranteed to be Path after create_rfc()
            if is_valid:
                tracker.complete_step("RFC validation passed")
            else:
                tracker.fail_step("RFC validation failed")
                print_warning(WARNING_MESSAGES["validation_issues"])
                for issue in issues[:5]:  # Show first 5 issues
                    print_muted(f"  - {issue}")
                if len(issues) > 5:
                    print_muted(f"  ... and {len(issues) - 5} more issues")
        else:
            tracker.skip_step("Validation disabled")
    except Exception:
        tracker.skip_step("Validation skipped")

    # Finalize
    tracker.start_step("Finalizing")
    tracker.complete_step("RFC created successfully")
    tracker.finish()

    # Display RFC details
    print_panel(
        f"[bold]RFC-{rfc.number}[/bold]\n\n"
        f"[cyan]Title:[/cyan] {rfc.title}\n"
        f"[cyan]Author:[/cyan] {rfc.author}\n"
        f"[cyan]Status:[/cyan] {rfc.status.value}\n"
        f"[cyan]File:[/cyan] {rfc.path}\n",
        title="RFC Created",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['rfc_next_steps']}")
    print_muted(f"  1. {INFO_MESSAGES['rfc_step_edit'].format(path=rfc.path)}")
    print_muted(f"  2. Validate: oak rfc validate RFC-{rfc.number}")
    print_muted("  3. Share for review")


@rfc_app.command("list")
def list_rfcs(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (draft, review, approved, adopted, abandoned, implemented, wont-implement)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed information",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON summary instead of formatted text",
    ),
) -> None:
    """List all RFC documents.

    Displays a table of all RFCs with their status, title, and other metadata.

    Example:
        oak rfc list --status draft
    """
    # Check if open-agent-kit is initialized
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    # Check if RFC directory exists
    config_service = ConfigService(project_root)
    rfc_dir = config_service.get_rfc_dir()

    if not dir_exists(rfc_dir):
        print_warning(WARNING_MESSAGES["rfc_dir_not_found"].format(dir=rfc_dir))
        print_info(INFO_MESSAGES["no_rfcs_created"])
        print_muted(f'\n{HINTS["create_first_rfc"]}')
        return

    # Get RFCs
    rfc_service = RFCService(project_root)
    rfcs = rfc_service.list_rfcs(status=status)

    if not rfcs:
        if status:
            print_info(INFO_MESSAGES["no_rfcs_with_status"].format(status=status))
        else:
            print_info(INFO_MESSAGES["no_rfcs_found"])
        return

    stats = rfc_service.get_rfc_statistics(rfcs)

    if json_output:
        output = {
            "rfcs": [
                {
                    "number": f"RFC-{rfc.number}",
                    "title": rfc.title,
                    "author": rfc.author,
                    "date": rfc.date,
                    "status": rfc.status.value,
                    "path": str(rfc.path) if rfc.path else None,
                    "tags": rfc.tags,
                }
                for rfc in rfcs
            ],
            "stats": stats,
        }
        print(json.dumps(output, indent=2))
        return

    # Display header
    title = "All RFCs" if not status else f"RFCs with status: {status}"
    print_header(title)
    print_divider()

    if verbose:
        # Verbose mode: show detailed info for each RFC
        for rfc in rfcs:
            print_panel(
                f"[bold]{rfc.title}[/bold]\n\n"
                f"[cyan]Number:[/cyan] RFC-{rfc.number}\n"
                f"[cyan]Author:[/cyan] {rfc.author}\n"
                f"[cyan]Date:[/cyan] {rfc.date}\n"
                f"[cyan]Status:[/cyan] {rfc.status.value}\n"
                f"[cyan]Tags:[/cyan] {', '.join(rfc.tags) if rfc.tags else 'None'}\n"
                f"[cyan]File:[/cyan] {rfc.path}",
                title=f"RFC-{rfc.number}",
            )
            print()
    else:
        # Table mode: show summary table
        data = []
        for rfc in rfcs:
            data.append(
                {
                    "number": f"RFC-{rfc.number}",
                    "status": rfc.status.value.upper(),
                    "title": rfc.title[:50] + "..." if len(rfc.title) > 50 else rfc.title,
                    "author": rfc.author,
                    "date": rfc.date,
                }
            )

        print_table(data, title=f"RFCs ({len(rfcs)})")

    # Show summary
    print_divider()
    print_info(INFO_MESSAGES["total_rfcs"].format(count=len(rfcs)))

    # Status breakdown
    status_counts: dict[str, int] = {}
    for rfc in rfcs:
        status_key = rfc.status.value
        status_counts[status_key] = status_counts.get(status_key, 0) + 1

    if len(status_counts) > 1:
        print_muted("\nBy status:")
        for stat, count in sorted(status_counts.items()):
            print_muted(f"  {stat}: {count}")

    stale_drafts = stats.get("stale_drafts", [])
    if stale_drafts:
        print_warning("\nStale draft RFCs detected (consider follow-up):")
        for entry in stale_drafts:
            print_muted(f"  RFC-{entry['number']} ({entry['date']}): {entry['title']}")

    if stats.get("by_author"):
        top_authors = sorted(
            ((author, len(numbers)) for author, numbers in stats["by_author"].items()),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        print_muted("\nTop contributors:")
        for author, count in top_authors:
            print_muted(f"  {author}: {count} RFC(s)")


@rfc_app.command("adopt")
def adopt_rfc(
    rfc_number: str = typer.Argument(..., help="RFC number (e.g., 008 or RFC-001)"),
) -> None:
    """Mark an RFC as adopted and move it to the adopted directory."""

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    sanitized_number = rfc_number.replace("RFC-", "").replace("rfc-", "")

    service = RFCService(project_root)
    try:
        adopted = service.adopt_rfc(sanitized_number)
    except FileExistsError as err:
        print_error(str(err))
        raise typer.Exit(code=1)

    if not adopted:
        print_error(ERROR_MESSAGES["rfc_not_found"].format(identifier=rfc_number))
        raise typer.Exit(code=1)

    print_success(f"RFC-{adopted.number} marked as adopted")
    print_panel(
        f"Status updated to [bold]adopted[/bold]\nLocation: {adopted.path}",
        title=f"RFC-{adopted.number}",
        style="green",
    )


@rfc_app.command("abandon")
def abandon_rfc(
    rfc_number: str = typer.Argument(..., help="RFC number (e.g., 008 or RFC-001)"),
) -> None:
    """Mark an RFC as abandoned and move it to the abandoned directory."""

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    sanitized_number = rfc_number.replace("RFC-", "").replace("rfc-", "")

    service = RFCService(project_root)
    try:
        abandoned = service.abandon_rfc(sanitized_number)
    except FileExistsError as err:
        print_error(str(err))
        raise typer.Exit(code=1)

    if not abandoned:
        print_error(ERROR_MESSAGES["rfc_not_found"].format(identifier=rfc_number))
        raise typer.Exit(code=1)

    print_success(f"RFC-{abandoned.number} marked as abandoned")
    print_panel(
        f"Status updated to [bold]abandoned[/bold]\nLocation: {abandoned.path}",
        title=f"RFC-{abandoned.number}",
        style="yellow",
    )


@rfc_app.command("validate")
def validate_rfc(
    rfc_file: str | None = typer.Argument(
        None,
        help="RFC file to validate (RFC number or file path)",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Use strict validation rules",
    ),
    all_rfcs: bool = typer.Option(
        False,
        "--all",
        help="Validate all RFCs",
    ),
) -> None:
    """Validate RFC document(s).

    Checks RFC for:
    - Proper filename format
    - Required sections
    - Markdown syntax
    - Content structure

    Example:
        oak rfc validate RFC-001
        oak rfc validate --all
    """
    # Check if open-agent-kit is initialized
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    rfc_service = RFCService(project_root)

    if all_rfcs:
        # Validate all RFCs
        print_header("Validate All RFCs")
        rfcs = rfc_service.list_rfcs()

        if not rfcs:
            print_info(INFO_MESSAGES["no_rfcs_to_validate"])
            return

        total = len(rfcs)
        passed = 0
        failed = 0

        for rfc in rfcs:
            if not rfc.path:
                continue

            is_valid, issues = rfc_service.validate_rfc(rfc.path, strict=strict)

            if is_valid:
                print_success(f"RFC-{rfc.number}: {rfc.title}")
                passed += 1
            else:
                print_error(f"RFC-{rfc.number}: {rfc.title}")
                for issue in issues[:3]:  # Show first 3 issues
                    print_muted(f"  - {issue}")
                if len(issues) > 3:
                    print_muted(f"  ... and {len(issues) - 3} more issues")
                failed += 1

        # Summary
        print_divider()
        print_info(
            INFO_MESSAGES["validation_summary"].format(total=total, passed=passed, failed=failed)
        )

        if failed > 0:
            raise typer.Exit(code=1)

    else:
        # Validate single RFC
        if not rfc_file:
            print_error(ERROR_MESSAGES["rfc_file_required"])
            print_info(f"Usage: {USAGE_EXAMPLES['rfc_validate_number']}")
            print_info(f"       {USAGE_EXAMPLES['rfc_validate_path']}")
            print_info(f"       {USAGE_EXAMPLES['rfc_validate_all']}")
            raise typer.Exit(code=1)

        print_header(f"Validate RFC: {rfc_file}")

        # Determine RFC path
        rfc_path = None

        # Check if it's a file path
        if os.path.exists(rfc_file):
            rfc_path = Path(rfc_file)
        else:
            # Try to find by RFC number
            rfc_number = rfc_file.replace("RFC-", "").replace("rfc-", "")
            rfc_doc = rfc_service.get_rfc(rfc_number)
            if rfc_doc and rfc_doc.path:
                rfc_path = rfc_doc.path

        if not rfc_path:
            print_error(ERROR_MESSAGES["rfc_not_found"].format(identifier=rfc_file))
            raise typer.Exit(code=1)

        # Validate
        is_valid, issues = rfc_service.validate_rfc(rfc_path, strict=strict)

        if is_valid:
            print_success(SUCCESS_MESSAGES["rfc_validated"])
            print_panel(
                "✓ Filename format is correct\n"
                "✓ All required sections present\n"
                "✓ Markdown syntax is valid\n"
                "✓ Content structure is correct",
                title="Validation Results",
                style="green",
            )
        else:
            print_error(ERROR_MESSAGES["rfc_validation_failed"])
            print_panel(
                "\n".join([f"✗ {issue}" for issue in issues]),
                title="Validation Issues",
                style="red",
            )
            raise typer.Exit(code=1)


@rfc_app.command("show")
def show_rfc(
    rfc_number: str = typer.Argument(..., help="RFC number (e.g., 001, 2024-001)"),
) -> None:
    """Show RFC details.

    Displays detailed information about a specific RFC including
    metadata, status, and file location.

    Example:
        oak rfc show 001
    """
    # Check if open-agent-kit is initialized
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    rfc_service = RFCService(project_root)

    # Remove RFC- prefix if present
    rfc_num = rfc_number.replace("RFC-", "").replace("rfc-", "")

    # Get RFC
    rfc = rfc_service.get_rfc(rfc_num)

    if not rfc:
        print_error(ERROR_MESSAGES["rfc_not_found"].format(identifier=f"RFC-{rfc_num}"))
        raise typer.Exit(code=1)

    # Display RFC details
    print_header(f"RFC-{rfc.number}: {rfc.title}")
    print_divider()

    print_key_value("Number", f"RFC-{rfc.number}")
    print_key_value("Title", rfc.title)
    print_key_value("Author", rfc.author)
    print_key_value("Date", rfc.date)
    print_key_value("Status", rfc.status.value.upper())

    if rfc.tags:
        print_key_value("Tags", ", ".join(rfc.tags))

    if rfc.path:
        print_key_value("File", str(rfc.path))

    print_divider()

    # Show file preview
    if rfc.path and rfc.path.exists():
        try:
            from open_agent_kit.utils import read_file

            content = read_file(rfc.path)
            lines = content.split("\n")

            # Show first 20 lines
            preview_lines = lines[:20]
            preview = "\n".join(preview_lines)

            print_panel(
                preview + ("\n..." if len(lines) > 20 else ""),
                title="Content Preview",
            )

            print_muted(f"\nView full content: cat {rfc.path}")
            print_muted(f"Edit RFC: {os.environ.get('EDITOR', 'vim')} {rfc.path}")
        except Exception:
            pass
