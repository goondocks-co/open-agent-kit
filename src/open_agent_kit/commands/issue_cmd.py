"""Issue commands intended for AI agent workflows."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import typer

from open_agent_kit.constants import (
    CONSTITUTION_DIR,
    CONSTITUTION_FILENAME,
    CONSTITUTION_RULE_KEYWORDS,
    CONSTITUTION_RULE_SECTIONS,
    ERROR_MESSAGES,
    INFO_MESSAGES,
    ISSUE_CONTEXT_FILENAME,
    ISSUE_NOTES_FILENAME,
    ISSUE_NOTES_MAX_LENGTH,
    ISSUE_PLAN_FILENAME,
    ISSUE_PLAN_SECTION_HEADINGS,
    ISSUE_VALIDATION_FILENAME,
    SUCCESS_MESSAGES,
    VALIDATION_STOPWORDS,
)
from open_agent_kit.models.issue import Issue
from open_agent_kit.services.issue_providers.base import IssueProvider, IssueProviderError
from open_agent_kit.services.issue_service import IssueService
from open_agent_kit.utils import (
    StepTracker,
    get_console,
    get_git_root,
    get_project_root,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_warning,
)

issue_app = typer.Typer(
    name="issue",
    help="Issue utilities (AI agents only)",
    no_args_is_help=True,
)


def _check_issue_prerequisites(
    project_root: Path, service: IssueService, provider: str | None = None
) -> bool:
    """Check prerequisites for issue commands.

    Args:
        project_root: Project root directory
        service: IssueService instance
        provider: Optional provider key override

    Returns:
        True if all prerequisites met, False otherwise (exits on failure)
    """
    missing_items: list[dict[str, str | list[str]]] = []

    # Check 1: Constitution exists
    constitution_path = project_root / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    if not constitution_path.exists():
        missing_items.append(
            {
                "name": "Constitution",
                "file": str(constitution_path),
                "command": "/oak.constitution-create (via your AI agent)",
                "help": "A constitution defines your project's standards and is required for issue planning.",
            }
        )

    # Check 2: Issue provider configured and valid
    issues = service.validate_provider(provider)
    if issues:
        missing_items.append(
            {
                "name": "Issue Provider Configuration",
                "issues": issues,
                "command": "oak config",
                "help": "Issue provider must be configured to fetch issues.",
            }
        )

    if missing_items:
        print_error("Missing prerequisites for issue commands:\n")
        for i, item in enumerate(missing_items, 1):
            print_error(f"{i}. {item['name']}")
            if "file" in item:
                print_info(f"   Missing: {item['file']}")
            if "issues" in item:
                for issue in item["issues"]:
                    print_info(f"   • {issue}")
            print_info(f"   → Run: {item['command']}")
            print_info(f"   {item['help']}\n")

        raise typer.Exit(code=1)

    return True


@issue_app.command("plan")
def plan_issue(
    issue: str = typer.Argument(..., help="Issue identifier or number"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Override configured issue provider (ado, github)"
    ),
) -> None:
    """Fetch an issue, scaffold artifacts under oak/issue, and prepare a git branch.

    This is a utility command for AI agents - it scaffolds artifacts deterministically
    without interactive prompts. Agents fill in plan details by editing plan.md."""
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = IssueService(project_root)

    # Check prerequisites: constitution and issue provider configuration
    _check_issue_prerequisites(project_root, service, provider)

    tracker = StepTracker(3)

    tracker.start_step(f"Fetching issue {issue}")
    provider_impl = service.get_provider(provider)
    try:
        issue_item = provider_impl.fetch(issue)
    except IssueProviderError as exc:
        tracker.fail_step("Failed to fetch issue", str(exc))
        raise typer.Exit(code=1)

    # Fetch related issues (parents, children, etc.) for additional context
    related_issues = []
    if issue_item.relations:
        print_info(f"Found {len(issue_item.relations)} related issue(s), fetching...")
        for relation in issue_item.relations:
            if relation.identifier:
                try:
                    related_item = provider_impl.fetch(relation.identifier)
                    related_issues.append(related_item)
                    # Update the relation with the fetched title for better context rendering
                    relation.title = related_item.title
                except IssueProviderError as exc:
                    print_warning(f"Could not fetch related {relation.identifier}: {exc}")

    tracker.complete_step(
        f"Fetched issue {issue_item.identifier}"
        + (f" with {len(related_issues)} related item(s)" if related_issues else "")
    )

    tracker.start_step("Writing issue artifacts")
    # Scaffold artifacts deterministically - agents fill in plan details by editing plan.md
    context_path = service.write_context(issue_item, related_issues)
    plan_path = service.write_plan(issue_item, details=None, related_items=related_issues)
    tracker.complete_step(f"Artifacts saved to {plan_path.parent}")

    tracker.start_step("Preparing git branch")
    branch_name = service.build_branch_name(issue_item, provider_impl)
    branch_exists = service.branch_exists(branch_name, git_root)
    try:
        service.checkout_branch(branch_name, git_root, create=not branch_exists)
    except subprocess.CalledProcessError as exc:
        tracker.fail_step("Git command failed", str(exc))
        print_error(ERROR_MESSAGES["git_command_failed"].format(details=str(exc)))
        raise typer.Exit(code=1)
    except OSError as exc:
        tracker.fail_step("File system error", str(exc))
        print_error(ERROR_MESSAGES["file_system_error"].format(details=str(exc)))
        raise typer.Exit(code=1)

    if branch_exists:
        print_info(INFO_MESSAGES["issue_branch_exists"].format(branch=branch_name))

    tracker.complete_step(SUCCESS_MESSAGES["issue_branch_ready"].format(branch=branch_name))
    try:
        service.record_plan(issue_item.provider, issue_item.identifier, branch_name)
        # Save branch name to context for consistency across operations
        service.update_branch_name(issue_item.provider, issue_item.identifier, branch_name)
    except Exception:
        print_warning("Unable to record plan metadata for auto-detection.")

    tracker.finish("Issue implementation context ready")

    print_panel(
        f"[bold]Issue:[/bold] {issue_item.identifier}\n"
        f"[cyan]Title:[/cyan] {issue_item.title}\n"
        f"[cyan]Provider:[/cyan] {issue_item.provider}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
        f"[cyan]Context:[/cyan] {context_path}\n"
        f"[cyan]Context Summary:[/cyan] {context_path.parent / 'context-summary.md'}\n"
        f"[cyan]Plan:[/cyan] {plan_path}",
        title="Issue Ready",
        style="green",
    )
    print_success(SUCCESS_MESSAGES["issue_artifacts_ready"])


@issue_app.command("refresh")
def refresh_issue(
    issue: str | None = typer.Argument(None, help="Issue identifier or number"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Issue provider key"),
) -> None:
    """Refresh issue context from provider (updates context.json and context-summary.md).

    Fetches fresh data from the issue provider and updates the local context files
    while preserving all other artifacts (plan.md, notes.md, codebase.md, etc.).

    This is useful when:
    - Issue has been updated since you last fetched it
    - New comments or context have been added
    - Acceptance criteria or requirements have changed
    - You want the latest state before implementing

    Examples:
        oak issue refresh 169029
        oak issue refresh 456 --provider github
        oak issue refresh  # Uses current branch/last issue
    """
    project_root = get_project_root()
    service = IssueService(project_root=project_root)

    # Resolve issue and provider
    try:
        resolved_provider, resolved_issue = service.resolve_issue(issue, provider)
    except IssueProviderError as e:
        print_error(str(e))
        raise typer.Exit(1)

    # Check if issue exists locally
    result = service.find_issue_dir(resolved_issue, resolved_provider)
    if not result:
        print_error(
            f"No local context found for {resolved_provider} issue {resolved_issue}. "
            f"Run `oak issue plan {resolved_issue}` first."
        )
        raise typer.Exit(1)

    found_provider, issue_dir = result

    # Refresh context
    print_info(f"Refreshing {found_provider} issue {resolved_issue} from provider...")

    try:
        old_item, new_item, changes = service.refresh_context(found_provider, resolved_issue)
    except IssueProviderError as e:
        print_error(f"Failed to fetch fresh data: {e}")
        raise typer.Exit(1)
    except FileNotFoundError:
        print_error(f"Context file not found for {found_provider}/{resolved_issue}")
        raise typer.Exit(1)

    # Display changes
    if not changes["has_changes"]:
        print_success(f"✓ Issue {resolved_issue} is up to date (no changes detected)")
        return

    # Show what changed
    console = get_console()
    console.print("\n[bold cyan]Changes detected:[/bold cyan]\n")

    if changes["title_changed"]:
        console.print("  [yellow]•[/yellow] Title changed")
        console.print(f"    [dim]Old:[/dim] {old_item.title}")
        console.print(f"    [dim]New:[/dim] {new_item.title}\n")

    if changes["description_changed"]:
        console.print("  [yellow]•[/yellow] Description updated\n")

    if changes["state_changed"]:
        console.print(
            f"  [yellow]•[/yellow] State changed: " f"{old_item.state} → {new_item.state}\n"
        )

    if changes["acceptance_criteria_changed"]:
        old_count = len(old_item.acceptance_criteria)
        new_count = len(new_item.acceptance_criteria)
        console.print(
            f"  [yellow]•[/yellow] Acceptance criteria updated: "
            f"{old_count} → {new_count} items\n"
        )

    if changes["tags_changed"]:
        old_tags = set(old_item.tags)
        new_tags = set(new_item.tags)
        added = new_tags - old_tags
        removed = old_tags - new_tags
        if added:
            console.print(f"  [yellow]•[/yellow] Tags added: {', '.join(added)}")
        if removed:
            console.print(f"  [yellow]•[/yellow] Tags removed: {', '.join(removed)}")
        if added or removed:
            console.print()

    if changes["assigned_to_changed"]:
        console.print(
            f"  [yellow]•[/yellow] Assignment changed: "
            f"{old_item.assigned_to or 'unassigned'} → {new_item.assigned_to or 'unassigned'}\n"
        )

    if changes["priority_changed"]:
        console.print(
            f"  [yellow]•[/yellow] Priority changed: "
            f"{old_item.priority} → {new_item.priority}\n"
        )

    if changes["milestone_changed"]:
        console.print(
            f"  [yellow]•[/yellow] Milestone changed: "
            f"{old_item.milestone or 'none'} → {new_item.milestone or 'none'}\n"
        )

    if changes["relations_added"] > 0:
        console.print(f"  [yellow]•[/yellow] {changes['relations_added']} related items added\n")

    if changes["relations_removed"] > 0:
        console.print(
            f"  [yellow]•[/yellow] {changes['relations_removed']} related items removed\n"
        )

    if changes["test_steps_changed"]:
        old_count = len(old_item.test_steps) if old_item.test_steps else 0
        new_count = len(new_item.test_steps) if new_item.test_steps else 0
        console.print(f"  [yellow]•[/yellow] Test steps updated: {old_count} → {new_count}\n")

    # Success message
    context_path = service.get_context_path(found_provider, resolved_issue)
    print_success(
        f"✓ Refreshed context for {found_provider} issue {resolved_issue}\n"
        f"  Updated: {context_path}\n"
        f"  Updated: {context_path.parent / 'context-summary.md'}"
    )


@issue_app.command("implement")
def implement_issue(
    issue: str | None = typer.Argument(None, help="Issue identifier or number"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Issue provider key"),
    notes: str | None = typer.Option(
        None, "--notes", "-n", help="Additional implementation context to log with the plan"
    ),
    checkout: bool = typer.Option(
        True,
        "--checkout/--no-checkout",
        help="Switch (or create) the implementation branch before returning context",
    ),
) -> None:
    """Use an existing plan to prepare implementation context."""
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = IssueService(project_root)

    # Check prerequisites: constitution and issue provider configuration
    _check_issue_prerequisites(project_root, service, provider)

    try:
        provider_key, resolved_issue = service.resolve_issue(issue, provider)
        if issue is None:
            print_info(
                INFO_MESSAGES["issue_inferred_issue"].format(
                    issue=resolved_issue, provider=provider_key
                )
            )
    except IssueProviderError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    issue_dir = service.get_issue_dir(provider_key, resolved_issue)
    if not issue_dir.exists():
        print_error(ERROR_MESSAGES["issue_dir_missing"].format(path=issue_dir))
        print_info(INFO_MESSAGES["issue_plan_hint"].format(issue=resolved_issue))
        raise typer.Exit(code=1)
    context_path = service.get_context_path(provider_key, resolved_issue)
    plan_path = service.get_plan_path(provider_key, resolved_issue)

    if not context_path.exists():
        print_error(ERROR_MESSAGES["issue_context_missing"].format(path=context_path))
        print_info(INFO_MESSAGES["issue_plan_hint"].format(issue=resolved_issue))
        raise typer.Exit(code=1)

    if not plan_path.exists():
        print_error(ERROR_MESSAGES["issue_plan_missing"].format(path=plan_path))
        print_info(INFO_MESSAGES["issue_plan_hint"].format(issue=resolved_issue))
        raise typer.Exit(code=1)

    issue_obj = service.load_issue(provider_key, resolved_issue)
    plan_text = service.read_plan(provider_key, resolved_issue)

    provider_impl: IssueProvider | None = None
    try:
        provider_impl = service.get_provider(provider_key)
    except IssueProviderError as exc:
        print_warning(str(exc))

    # Prefer saved branch name from context for consistency
    branch_name = issue_obj.branch_name or service.build_branch_name(issue_obj, provider_impl)
    branch_exists = service.branch_exists(branch_name, git_root)

    if checkout:
        try:
            service.checkout_branch(branch_name, git_root, create=not branch_exists)
        except subprocess.CalledProcessError as exc:
            print_warning(f"Git command failed switching to branch {branch_name}: {exc}")
        except OSError as exc:
            print_warning(f"File system error switching to branch {branch_name}: {exc}")

    notes_path = issue_dir / ISSUE_NOTES_FILENAME
    captured_notes = None
    if notes:
        # Validate notes length
        if len(notes) > ISSUE_NOTES_MAX_LENGTH:
            print_error(
                ERROR_MESSAGES["issue_notes_too_long"].format(max_length=ISSUE_NOTES_MAX_LENGTH)
            )
            raise typer.Exit(code=1)
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        with notes_path.open("a", encoding="utf-8") as fh:
            fh.write(notes.strip() + "\n")
        captured_notes = notes.strip()
    elif notes_path.exists():
        captured_notes = notes_path.read_text(encoding="utf-8").strip()

    objectives = _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Objectives"]) or "Pending"
    definition = (
        _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Definition of Done"]) or "Pending"
    )
    acceptance_preview = _preview_list_section(plan_text, "## Acceptance Criteria")
    risks_preview = (
        _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Risks & Mitigations"]) or "Pending"
    )

    context_summary_path = context_path.parent / "context-summary.md"
    print_panel(
        f"[bold]Issue:[/bold] {issue_obj.identifier}\n"
        f"[cyan]Title:[/cyan] {issue_obj.title}\n"
        f"[cyan]Provider:[/cyan] {provider_key}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
        f"[cyan]Context:[/cyan] {context_path}\n"
        f"[cyan]Context Summary:[/cyan] {context_summary_path if context_summary_path.exists() else 'none'}\n"
        f"[cyan]Plan:[/cyan] {plan_path}\n"
        f"[cyan]Notes:[/cyan] {notes_path if notes_path.exists() else 'none'}",
        title="Implementation Context",
        style="green",
    )
    print_info(f"Objectives: {objectives}")
    print_info(f"D.O.D.: {definition}")
    if acceptance_preview:
        print_info(f"Acceptance criteria (first 3): {acceptance_preview}")
    print_info(f"Risks/Mitigations: {risks_preview}")
    if captured_notes:
        print_info(f"Additional notes: {captured_notes}")

    print_success("Ready to implement using plan, notes, and branch above.")


@issue_app.command("validation-status")
def validation_status(
    issue: str | None = typer.Argument(None, help="Issue identifier or number"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Issue provider key"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Check if validation has been run for an issue (utility for agents).

    Returns validation status and results if available.
    Agents use this to determine if /oak.issue-validate has been run.

    Example:
        oak issue validation-status 12345 --provider ado
        oak issue validation-status 12345 --provider ado --json
    """
    import json as json_module

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = IssueService(project_root)

    try:
        provider_key, resolved_issue = service.resolve_issue(issue, provider)
        if issue is None:
            print_info(
                INFO_MESSAGES["issue_inferred_issue"].format(
                    issue=resolved_issue, provider=provider_key
                )
            )
    except IssueProviderError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    issue_dir = service.get_issue_dir(provider_key, resolved_issue)
    validation_path = issue_dir / ISSUE_VALIDATION_FILENAME

    if not validation_path.exists():
        if json_output:
            output = {
                "validated": False,
                "path": str(validation_path),
                "recommendation": "Run /oak.issue-validate to validate the issue plan",
            }
            print(json_module.dumps(output, indent=2))
        else:
            print_warning("Validation has not been run for this issue")
            print_info(f"Expected file: {validation_path}")
            print_info("Run: /oak.issue-validate to validate the issue plan")
        raise typer.Exit(code=1)

    # Read validation results
    validation_content = validation_path.read_text(encoding="utf-8")
    has_issues = "⚠️  Issues Found" in validation_content or "Issues Found" in validation_content

    # Extract timestamp if available
    timestamp_match = re.search(r"\*\*Validated:\*\* (.+)", validation_content)
    validated_at = timestamp_match.group(1) if timestamp_match else "Unknown"

    if json_output:
        output = {
            "validated": True,
            "path": str(validation_path),
            "validated_at": validated_at,
            "has_issues": has_issues,
            "status": "issues_found" if has_issues else "passed",
        }
        print(json_module.dumps(output, indent=2))
    else:
        status_icon = "⚠️" if has_issues else "✅"
        status_text = "Issues Found" if has_issues else "Passed"
        print_success(f"Validation status: {status_icon} {status_text}")
        print_info(f"Validated at: {validated_at}")
        print_info(f"Results file: {validation_path}")
        if has_issues:
            print_warning("Review validation.md for details before implementing")


@issue_app.command("show")
def show_issue(
    issue: str | None = typer.Argument(None, help="Issue identifier or number"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Issue provider key"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show issue structure, paths, and related items.

    This is a utility command for AI agents - it surfaces all artifact paths
    and related item information without requiring hardcoded paths in prompts.
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    console = get_console()
    service = IssueService(project_root)

    # Resolve provider and issue
    try:
        provider_key, issue_id = service.resolve_issue(issue, provider)
    except IssueProviderError as e:
        print_error(str(e))
        raise typer.Exit(code=1)

    # Get issue directory
    issue_dir = service.get_issue_dir(provider_key, issue_id)

    if not issue_dir.exists():
        print_error(f"No issue found for {provider_key}/{issue_id}")
        print_info(f"Run: oak issue plan {issue_id} --provider {provider_key}")
        raise typer.Exit(code=1)

    # Build structure information
    context_path = issue_dir / "context.json"
    plan_path = issue_dir / "plan.md"
    codebase_path = issue_dir / "codebase.md"
    validation_path = issue_dir / "validation.md"
    related_dir = issue_dir / "related"

    # Load context to get title and branch name
    title = "Unknown"
    branch_name = None
    if context_path.exists():
        import json

        try:
            with context_path.open() as f:
                context_data = json.load(f)
                title = context_data.get("title", "Unknown")
                branch_name = context_data.get("branch_name")
        except Exception:
            pass

    # Find related items
    related_items = []
    if related_dir.exists():
        for related_item_dir in sorted(related_dir.iterdir()):
            if related_item_dir.is_dir():
                related_context = related_item_dir / "context.json"
                if related_context.exists():
                    try:
                        with related_context.open() as f:
                            related_data = json.load(f)
                            related_items.append(
                                {
                                    "identifier": related_data.get(
                                        "identifier", related_item_dir.name
                                    ),
                                    "title": related_data.get("title", "Unknown"),
                                    "context_path": str(related_context),
                                }
                            )
                    except Exception:
                        related_items.append(
                            {
                                "identifier": related_item_dir.name,
                                "title": "Unknown",
                                "context_path": str(related_context),
                            }
                        )

    if json_output:
        import json

        output = {
            "provider": provider_key,
            "identifier": issue_id,
            "title": title,
            "directory": str(issue_dir),
            "branch_name": branch_name,
            "artifacts": {
                "context": str(context_path) if context_path.exists() else None,
                "plan": str(plan_path) if plan_path.exists() else None,
                "codebase": str(codebase_path) if codebase_path.exists() else None,
                "validation": str(validation_path) if validation_path.exists() else None,
            },
            "related_items": related_items,
        }
        print(json.dumps(output, indent=2))
    else:
        branch_info = f"\n[cyan]Branch:[/cyan] {branch_name}" if branch_name else ""
        print_panel(
            f"[bold]Issue:[/bold] {issue_id}\n"
            f"[cyan]Title:[/cyan] {title}\n"
            f"[cyan]Provider:[/cyan] {provider_key}\n"
            f"[cyan]Directory:[/cyan] {issue_dir}"
            f"{branch_info}",
            title="Issue Structure",
            style="cyan",
        )

        console.print("\n[bold]Artifacts:[/bold]")
        console.print(
            f"  Context:    {context_path}" + (" ✓" if context_path.exists() else " [red]✗[/red]")
        )
        console.print(
            f"  Plan:       {plan_path}" + (" ✓" if plan_path.exists() else " [red]✗[/red]")
        )
        console.print(
            f"  Codebase:   {codebase_path}" + (" ✓" if codebase_path.exists() else " [red]✗[/red]")
        )
        console.print(
            f"  Validation: {validation_path}"
            + (" ✓" if validation_path.exists() else " [dim](not run)[/dim]")
        )

        if related_items:
            console.print(f"\n[bold]Related Items ({len(related_items)}):[/bold]")
            for item in related_items:
                console.print(f"  {item['identifier']}: {item['title']}")
                console.print(f"    → {item['context_path']}")


@issue_app.command("validate")
def validate_issue(
    issue: str | None = typer.Argument(None, help="Issue identifier or number"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Issue provider key"),
) -> None:
    """Validate stored issue artifacts and surface potential gaps."""
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = IssueService(project_root)

    # Check prerequisites: constitution and issue provider configuration
    _check_issue_prerequisites(project_root, service, provider)

    try:
        provider_key, resolved_issue = service.resolve_issue(issue, provider)
        if issue is None:
            print_info(
                INFO_MESSAGES["issue_inferred_issue"].format(
                    issue=resolved_issue, provider=provider_key
                )
            )
    except IssueProviderError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    issue_dir = service.get_issue_dir(provider_key, resolved_issue)
    if not issue_dir.exists():
        print_error(ERROR_MESSAGES["issue_dir_missing"].format(path=issue_dir))
        raise typer.Exit(code=1)

    context_path = issue_dir / ISSUE_CONTEXT_FILENAME
    plan_path = issue_dir / ISSUE_PLAN_FILENAME

    if not context_path.exists():
        print_error(ERROR_MESSAGES["issue_context_missing"].format(path=context_path))
        raise typer.Exit(code=1)
    if not plan_path.exists():
        print_error(ERROR_MESSAGES["issue_plan_missing"].format(path=plan_path))
        raise typer.Exit(code=1)

    issue_obj = service.load_issue(provider_key, resolved_issue)
    plan_text = service.read_plan(provider_key, resolved_issue)

    try:
        provider_impl: IssueProvider | None = service.get_provider(provider_key)
    except IssueProviderError as exc:
        print_warning(str(exc))
        provider_impl = None

    # Prefer saved branch name from context for consistency
    branch_name = issue_obj.branch_name or service.build_branch_name(issue_obj, provider_impl)
    branch_exists = service.branch_exists(branch_name, git_root)

    issues = _validate_issue(
        issue_obj,
        plan_text,
        branch_exists,
        branch_name,
        project_root,
    )

    # Save validation results to file
    validation_path = issue_dir / ISSUE_VALIDATION_FILENAME
    _save_validation_results(validation_path, issue_obj, issues, branch_name)

    print_panel(
        f"[bold]Issue:[/bold] {issue_obj.identifier}\n"
        f"[cyan]Provider:[/cyan] {provider_key}\n"
        f"[cyan]Context:[/cyan] {context_path}\n"
        f"[cyan]Plan:[/cyan] {plan_path}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
        f"[cyan]Validation:[/cyan] {validation_path}",
        title="Issue Artifacts",
        style="cyan",
    )

    if issues:
        print_warning("Validation identified the following items to review:")
        for message in issues:
            print_error(f"- {message}")
        print_info(f"\nValidation results saved to: {validation_path}")
    else:
        print_success(SUCCESS_MESSAGES["issue_validated"])
        print_info(f"Validation results saved to: {validation_path}")


def _validate_issue(
    issue_obj: Issue,
    plan_text: str,
    branch_exists: bool,
    branch_name: str,
    project_root: Path,
) -> list[str]:
    """Return a list of validation issues for the given issue."""
    issues: list[str] = []

    if not issue_obj.acceptance_criteria:
        issues.append("No acceptance criteria captured in context.json.")

    acceptance_pending = _section_contains_pending(plan_text, "## Acceptance Criteria")
    if acceptance_pending:
        issues.append("Acceptance criteria in plan.md are still marked as pending.")

    for title, heading in ISSUE_PLAN_SECTION_HEADINGS.items():
        section_body = _extract_section(plan_text, heading)
        if not section_body or _is_pending(section_body):
            issues.append(f"{title} section is incomplete in plan.md.")

    if not branch_exists:
        issues.append(f"Branch '{branch_name}' does not exist locally. Create or push the branch.")

    issues.extend(_validate_against_constitution(plan_text, project_root))
    return issues


def _extract_section(plan_text: str, heading: str) -> str | None:
    """Extract text following a markdown heading.

    Args:
        plan_text: Full markdown document text
        heading: Markdown heading to search for (e.g., "### Objectives")

    Returns:
        Extracted section text, or None if heading not found

    Example:
        >>> text = "### Objectives\nGoal 1\n## Next"
        >>> _extract_section(text, "### Objectives")
        'Goal 1'
    """
    pattern = rf"{re.escape(heading)}\s*(.*?)(?=\n## |\n### |\Z)"
    match = re.search(pattern, plan_text, re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _section_contains_pending(plan_text: str, heading: str) -> bool:
    """Check if a section still has 'Pending' placeholders.

    Args:
        plan_text: Full markdown document text
        heading: Markdown heading to check

    Returns:
        True if section is missing or contains "pending", False otherwise
    """
    section = _extract_section(plan_text, heading)
    if not section:
        return True
    return "pending" in section.strip().lower()


def _is_pending(value: str) -> bool:
    """Determine if a section is effectively pending or empty.

    Args:
        value: Section text to check

    Returns:
        True if value is empty or a pending placeholder
    """
    stripped = value.strip().lower()
    if not stripped:
        return True
    return stripped in {"pending", "- pending", "tbd", "n/a"}


def _preview_list_section(plan_text: str, heading: str, limit: int = 3) -> str:
    """Return up to N bullet items from a section.

    Args:
        plan_text: Full markdown document text
        heading: Markdown heading to extract from
        limit: Maximum number of bullet items to return (default: 3)

    Returns:
        Semicolon-separated preview of first N bullet items, or empty string
    """
    section = _extract_section(plan_text, heading)
    if not section:
        return ""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("-")]
    if not lines:
        return ""
    preview = [line.lstrip("-").strip() for line in lines[:limit]]
    return "; ".join(preview)


def _validate_against_constitution(plan_text: str, project_root: Path) -> list[str]:
    """Check plan content against constitution rules.

    Args:
        plan_text: Full plan markdown text
        project_root: Project root directory

    Returns:
        List of validation issues for missing constitution requirements
    """
    constitution_path = project_root / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    if not constitution_path.exists():
        return [ERROR_MESSAGES["constitution_not_found"].format(path=constitution_path)]

    content = constitution_path.read_text(encoding="utf-8")
    rules = _extract_constitution_rules(content)
    plan_lower = plan_text.lower()
    issues: list[str] = []

    for section, section_rules in rules.items():
        for rule_text in section_rules:
            keywords = _rule_keywords(rule_text)
            if not keywords:
                continue
            if not any(keyword in plan_lower for keyword in keywords):
                issues.append(
                    f"{section}: '{rule_text}' from constitution is not addressed in plan.md."
                )
                break
    return issues


def _save_validation_results(
    validation_path: Path,
    issue_obj: Issue,
    issues: list[str],
    branch_name: str,
) -> None:
    """Save validation results to markdown file.

    Args:
        validation_path: Path to save validation results
        issue_obj: Issue being validated
        issues: List of validation issues found
        branch_name: Git branch name
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = f"""# Validation Results

**Issue:** {issue_obj.identifier}
**Title:** {issue_obj.title}
**Branch:** {branch_name}
**Validated:** {timestamp}
**Status:** {'⚠️  Issues Found' if issues else '✅ Passed'}

## Summary

"""

    if issues:
        content += (
            f"Found {len(issues)} issue(s) that should be addressed before implementation:\n\n"
        )
        for i, issue in enumerate(issues, 1):
            content += f"{i}. {issue}\n"
        content += (
            "\n**Recommendation:** Address these issues before running `/oak.issue-implement`.\n"
        )
    else:
        content += "All validation checks passed! The issue artifacts are complete and ready for implementation.\n\n"
        content += "**Next Step:** Run `/oak.issue-implement` to begin implementation.\n"

    validation_path.write_text(content, encoding="utf-8")


def _extract_constitution_rules(content: str) -> dict[str, list[str]]:
    """Extract MUST/SHOULD rules from constitution sections.

    Args:
        content: Full constitution document text

    Returns:
        Dictionary mapping section names to lists of normative rules
    """
    rules: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            continue

        if (
            current_section in CONSTITUTION_RULE_SECTIONS
            and stripped.startswith("-")
            and any(keyword in stripped.lower() for keyword in CONSTITUTION_RULE_KEYWORDS)
        ):
            text = stripped.lstrip("-").strip()
            if text:
                rules.setdefault(current_section, []).append(text)
    return rules


def _rule_keywords(rule_text: str) -> list[str]:
    """Derive keywords from a constitution rule.

    Args:
        rule_text: Constitution rule text

    Returns:
        List of up to 3 significant keywords (excludes stopwords)
    """
    words = re.findall(r"[a-zA-Z]{4,}", rule_text.lower())
    keywords = [word for word in words if word not in VALIDATION_STOPWORDS]
    return keywords[:3]
