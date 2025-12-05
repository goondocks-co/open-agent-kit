"""Plan commands for strategic planning workflows.

This module provides CLI commands for creating and managing strategic plans
with research phases, task generation, and issue export.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from open_agent_kit.config.messages import (
    ERROR_MESSAGES,
    PLAN_ERROR_MESSAGES,
    PLAN_INFO_MESSAGES,
    PLAN_SUCCESS_MESSAGES,
)
from open_agent_kit.config.paths import (
    CONSTITUTION_FILENAME,
)
from open_agent_kit.constants import (
    CONSTITUTION_RULE_KEYWORDS,
    CONSTITUTION_RULE_SECTIONS,
    ISSUE_PLAN_SECTION_HEADINGS,
    VALIDATION_STOPWORDS,
)
from open_agent_kit.models.issue import Issue
from open_agent_kit.models.plan import PlanStatus, ResearchDepth
from open_agent_kit.services.issue_providers.base import IssueProviderError
from open_agent_kit.services.plan_service import PlanService, PlanServiceError
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

plan_app = typer.Typer(
    name="plan",
    help="Strategic planning utilities (AI agents only)",
    no_args_is_help=True,
)


def _check_plan_prerequisites(
    project_root: Path, service: PlanService, provider: str | None = None
) -> bool:
    """Check prerequisites for plan commands.

    Args:
        project_root: Project root directory
        service: PlanService instance
        provider: Optional provider key override (required for issue-first plans)

    Returns:
        True if all prerequisites met, False otherwise (exits on failure)
    """
    missing_items: list[dict[str, str | list[str]]] = []

    # Check 1: Constitution exists
    constitution_dir = service.config_service.get_constitution_dir()
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    if not constitution_path.exists():
        missing_items.append(
            {
                "name": "Constitution",
                "file": str(constitution_path),
                "command": "/oak.constitution-create (via your AI agent)",
                "help": "A constitution defines your project's standards and is required for planning.",
            }
        )

    # Check 2: Issue provider configured and valid (if provider is specified)
    if provider is not None:
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
        print_error("Missing prerequisites for plan commands:\n")
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


@plan_app.command("create")
def create_plan(
    name: str = typer.Argument(..., help="URL-safe plan name (e.g., 'auth-redesign')"),
    display_name: str | None = typer.Option(
        None, "--display-name", "-d", help="Human-readable plan name"
    ),
    overview: str = typer.Option("", "--overview", "-o", help="High-level plan overview"),
    research_depth: str = typer.Option(
        "standard",
        "--depth",
        help="Research depth: minimal, standard, comprehensive",
    ),
    no_branch: bool = typer.Option(False, "--no-branch", help="Skip git branch creation"),
) -> None:
    """Create a new strategic plan with initial scaffolding.

    This command creates the plan directory structure, initializes the manifest,
    and optionally creates a git branch for the plan.

    Examples:
        oak plan create auth-redesign
        oak plan create auth-redesign --display-name "Authentication Redesign"
        oak plan create performance-audit --depth comprehensive
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root and not no_branch:
        print_warning("Not a git repository. Skipping branch creation.")
        no_branch = True

    service = PlanService(project_root)

    # Check prerequisites
    _check_plan_prerequisites(project_root, service)

    # Parse research depth
    try:
        depth = ResearchDepth(research_depth)
    except ValueError:
        print_error(
            f"Invalid research depth: {research_depth}. Use: minimal, standard, comprehensive"
        )
        raise typer.Exit(code=1)

    # Use name as display name if not provided
    final_display_name = display_name or name.replace("-", " ").replace("_", " ").title()

    tracker = StepTracker(3 if not no_branch else 2)

    tracker.start_step(f"Creating plan '{name}'")
    try:
        manifest = service.create_plan(
            plan_name=name,
            display_name=final_display_name,
            overview=overview,
            research_depth=depth,
            create_branch=not no_branch,
        )
    except PlanServiceError as exc:
        tracker.fail_step("Failed to create plan", str(exc))
        raise typer.Exit(code=1)

    tracker.complete_step(f"Plan '{name}' created")

    if not no_branch and manifest.branch_name:
        tracker.start_step(f"Switched to branch {manifest.branch_name}")
        tracker.complete_step(
            PLAN_SUCCESS_MESSAGES["branch_created"].format(branch=manifest.branch_name)
        )

    tracker.start_step("Writing plan artifacts")
    plan_dir = service.get_plan_dir(name)
    plan_file = service.get_plan_file_path(name)
    tracker.complete_step(f"Artifacts saved to {plan_dir}")

    tracker.finish("Plan ready for research")

    print_panel(
        f"[bold]Plan:[/bold] {name}\n"
        f"[cyan]Display Name:[/cyan] {final_display_name}\n"
        f"[cyan]Status:[/cyan] {manifest.status.value}\n"
        f"[cyan]Research Depth:[/cyan] {depth.value}\n"
        + (f"[cyan]Branch:[/cyan] {manifest.branch_name}\n" if manifest.branch_name else "")
        + f"[cyan]Plan File:[/cyan] {plan_file}\n"
        f"[cyan]Research Dir:[/cyan] {service.get_research_dir(name)}",
        title="Plan Created",
        style="green",
    )
    print_success(PLAN_SUCCESS_MESSAGES["plan_created"])


@plan_app.command("issue")
def plan_from_issue(
    name: Annotated[str, typer.Argument(help="Plan name (URL-safe identifier)")],
    issue_id: Annotated[str, typer.Option("--id", "-i", help="Issue identifier")],
    provider: Annotated[str | None, typer.Option("--provider", "-p", help="Issue provider")] = None,
) -> None:
    """Create a plan from an external issue (issue-first workflow).

    This command fetches an issue from an external provider (ADO, GitHub) and creates
    a plan with the issue context. It scaffolds artifacts deterministically and
    prepares a git branch for implementation.

    Examples:
        oak plan issue auth-fix --id 169029 --provider ado
        oak plan issue bug-123 --id 456 --provider github
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Check prerequisites: constitution and issue provider configuration
    _check_plan_prerequisites(project_root, service, provider)

    tracker = StepTracker(2)

    tracker.start_step(f"Creating plan from issue {issue_id}")
    try:
        manifest = service.create_plan_from_issue(
            plan_name=name,
            issue_id=issue_id,
            provider_key=provider,
            create_branch=True,
        )
    except PlanServiceError as exc:
        tracker.fail_step("Failed to create plan", str(exc))
        raise typer.Exit(code=1)
    except IssueProviderError as exc:
        tracker.fail_step("Failed to fetch issue", str(exc))
        raise typer.Exit(code=1)

    tracker.complete_step(f"Plan '{name}' created")

    tracker.start_step("Preparing git branch")
    branch_name = manifest.branch_name or service.build_branch_name(name)
    if manifest.branch_name:
        print_info(f"Switched to branch {branch_name}")
    tracker.complete_step(f"Branch {branch_name} ready")

    tracker.finish("Issue-first plan ready")

    # Build paths for display
    plan_file = service.get_plan_file_path(name)
    context_path = service.get_issue_context_path(name)
    summary_path = service.get_issue_summary_path(name)

    # Get issue info from manifest
    issue_ref = manifest.issue

    print_panel(
        f"[bold]Plan:[/bold] {name}\n"
        f"[cyan]Issue:[/cyan] {issue_ref.id if issue_ref else issue_id}\n"
        f"[cyan]Title:[/cyan] {issue_ref.title if issue_ref else 'N/A'}\n"
        f"[cyan]Provider:[/cyan] {issue_ref.provider if issue_ref else 'N/A'}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
        f"[cyan]Plan File:[/cyan] {plan_file}\n"
        f"[cyan]Issue Context:[/cyan] {context_path}\n"
        f"[cyan]Context Summary:[/cyan] {summary_path}",
        title="Plan Ready",
        style="green",
    )
    print_success("Issue-first plan created. Edit plan.md to complete planning.")


@plan_app.command("show")
def show_plan(
    name: str | None = typer.Argument(None, help="Plan name (inferred from branch if omitted)"),
) -> None:
    """Show plan status and artifact paths.

    If no plan name is provided, attempts to infer from current git branch.

    Examples:
        oak plan show auth-redesign
        oak plan show  # Uses current branch
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Resolve plan name
    plan_name = name or service.infer_plan_from_branch()
    if not plan_name:
        print_error(PLAN_ERROR_MESSAGES["plan_not_specified"])
        raise typer.Exit(code=1)

    # Load plan
    try:
        plan = service.load_plan(plan_name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=plan_name))
        raise typer.Exit(code=1)

    # Get research status
    research_status = service.get_research_status(plan_name)

    # Format research progress
    research_progress = (
        f"{research_status['completed']}/{research_status['total']} topics completed"
        if research_status["total"] > 0
        else "No research topics defined"
    )

    # Format task count
    task_count = len(plan.tasks)
    task_info = f"{task_count} tasks" if task_count > 0 else "No tasks generated"

    # Detect source type and build appropriate display
    has_issue_source = "issue" in plan.manifest.sources
    has_research_source = "research" in plan.manifest.sources

    # Build panel content
    panel_content = (
        f"[bold]Plan:[/bold] {plan_name}\n"
        f"[cyan]Display Name:[/cyan] {plan.manifest.display_name}\n"
        f"[cyan]Sources:[/cyan] {', '.join(plan.manifest.sources) if plan.manifest.sources else 'none'}\n"
        f"[cyan]Status:[/cyan] {plan.manifest.status.value}\n"
        f"[cyan]Research Depth:[/cyan] {plan.manifest.research_depth.value}\n"
    )

    if plan.manifest.branch_name:
        panel_content += f"[cyan]Branch:[/cyan] {plan.manifest.branch_name}\n"

    panel_content += (
        f"[cyan]Created:[/cyan] {plan.manifest.created_at}\n"
        f"[cyan]Updated:[/cyan] {plan.manifest.updated_at}\n"
    )

    # Add issue information if this is an issue-first plan
    if has_issue_source and plan.manifest.issue:
        panel_content += (
            f"\n[bold]Issue Source:[/bold]\n"
            f"  Provider: {plan.manifest.issue.provider}\n"
            f"  ID: {plan.manifest.issue.id}\n"
        )
        if plan.manifest.issue.title:
            panel_content += f"  Title: {plan.manifest.issue.title}\n"

    # Add progress section
    panel_content += "\n[bold]Progress:[/bold]\n"

    if has_research_source:
        panel_content += f"  Research: {research_progress}\n"

    panel_content += f"  Tasks: {task_info}\n"

    # Add artifacts section
    panel_content += "\n[bold]Artifacts:[/bold]\n"
    panel_content += f"  Plan: {service.get_plan_file_path(plan_name)}\n"

    if task_count > 0:
        panel_content += f"  Tasks: {service.get_tasks_file_path(plan_name)}\n"

    if has_issue_source:
        context_path = service.get_issue_context_path(plan_name)
        summary_path = service.get_issue_summary_path(plan_name)
        if context_path.exists():
            panel_content += f"  Issue Context: {context_path}\n"
        if summary_path.exists():
            panel_content += f"  Context Summary: {summary_path}\n"

        # Show related items if present
        related_dir = service.get_issue_related_dir(plan_name)
        if related_dir.exists():
            related_count = len(list(related_dir.iterdir()))
            if related_count > 0:
                panel_content += f"  Related Items: {related_count} in {related_dir}/\n"

    if has_research_source and research_status["total"] > 0:
        panel_content += f"  Research: {service.get_research_dir(plan_name)}/"

    print_panel(
        panel_content,
        title="Plan Status",
        style="cyan",
    )


@plan_app.command("list")
def list_plans() -> None:
    """List all plans with their status.

    Examples:
        oak plan list
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)
    plans = service.list_plans()

    if not plans:
        print_info(PLAN_INFO_MESSAGES["no_plans"])
        return

    # Build table content
    lines = []
    lines.append("[bold]Plans:[/bold]\n")

    for plan in plans:
        status_color = {
            PlanStatus.DRAFT: "yellow",
            PlanStatus.RESEARCHING: "blue",
            PlanStatus.PLANNING: "magenta",
            PlanStatus.READY: "green",
            PlanStatus.IMPLEMENTING: "bright_yellow",
            PlanStatus.IMPLEMENTED: "bright_green",
            PlanStatus.EXPORTED: "cyan",
        }.get(plan.status, "white")

        lines.append(
            f"  [{status_color}]●[/{status_color}] {plan.name} "
            f"[dim]({plan.display_name})[/dim] "
            f"[{status_color}]{plan.status.value}[/{status_color}]"
        )
        if plan.branch_name:
            lines.append(f"    [dim]Branch: {plan.branch_name}[/dim]")

    print_panel("\n".join(lines), title=f"Plans ({len(plans)})", style="cyan")


@plan_app.command("research")
def show_research(
    name: str | None = typer.Argument(None, help="Plan name (inferred from branch if omitted)"),
) -> None:
    """Show research status for a plan.

    Examples:
        oak plan research auth-redesign
        oak plan research  # Uses current branch
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Resolve plan name
    plan_name = name or service.infer_plan_from_branch()
    if not plan_name:
        print_error(PLAN_ERROR_MESSAGES["plan_not_specified"])
        raise typer.Exit(code=1)

    # Get research status
    try:
        status = service.get_research_status(plan_name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=plan_name))
        raise typer.Exit(code=1)

    if status["total"] == 0:
        print_info(PLAN_INFO_MESSAGES["no_research_topics"].format(name=plan_name))
        return

    # Build status display
    lines = []
    lines.append(f"[bold]Research Progress:[/bold] {status['completed']}/{status['total']}\n")

    status_emoji = {
        "pending": "⏳",
        "in_progress": "🔄",
        "completed": "✅",
        "skipped": "⏭️",
    }

    for topic in status["topics"]:
        emoji = status_emoji.get(topic["status"], "❓")
        findings_marker = " [dim](has findings)[/dim]" if topic["has_findings"] else ""
        lines.append(
            f"  {emoji} {topic['title']} [dim]({topic['slug']})[/dim] "
            f"P{topic['priority']}{findings_marker}"
        )

    print_panel(
        "\n".join(lines),
        title=f"Research: {plan_name}",
        style="blue",
    )


@plan_app.command("tasks")
def show_tasks(
    name: str | None = typer.Argument(None, help="Plan name (inferred from branch if omitted)"),
) -> None:
    """Show tasks for a plan.

    Examples:
        oak plan tasks auth-redesign
        oak plan tasks  # Uses current branch
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Resolve plan name
    plan_name = name or service.infer_plan_from_branch()
    if not plan_name:
        print_error(PLAN_ERROR_MESSAGES["plan_not_specified"])
        raise typer.Exit(code=1)

    # Load tasks
    try:
        tasks = service.load_tasks(plan_name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=plan_name))
        raise typer.Exit(code=1)

    if not tasks:
        print_info(PLAN_INFO_MESSAGES["no_tasks"].format(name=plan_name))
        return

    # Build task display
    lines = []
    lines.append(f"[bold]Tasks:[/bold] {len(tasks)}\n")

    priority_color = {
        "critical": "red",
        "high": "yellow",
        "medium": "blue",
        "low": "dim",
    }

    for task in tasks:
        color = priority_color.get(task.priority.value, "white")
        exported = " ✓" if task.issue_link else ""
        lines.append(
            f"  [{color}]{task.id}[/{color}] {task.title} "
            f"[dim]({task.task_type.value})[/dim]{exported}"
        )
        if task.issue_link:
            lines.append(f"    [dim]→ {task.issue_link}[/dim]")

    print_panel(
        "\n".join(lines),
        title=f"Tasks: {plan_name}",
        style="magenta",
    )


@plan_app.command("status")
def update_status(
    name: str = typer.Argument(..., help="Plan name"),
    status: str = typer.Argument(
        ...,
        help="New status: draft, researching, planning, ready, implementing, implemented, exported",
    ),
) -> None:
    """Update plan status.

    Examples:
        oak plan status auth-redesign researching
        oak plan status auth-redesign implementing
        oak plan status auth-redesign implemented
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Parse status
    try:
        new_status = PlanStatus(status)
    except ValueError:
        valid = ", ".join(s.value for s in PlanStatus)
        print_error(f"Invalid status: {status}. Valid options: {valid}")
        raise typer.Exit(code=1)

    # Update status
    try:
        service.update_plan_status(name, new_status)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=name))
        raise typer.Exit(code=1)

    print_success(
        PLAN_SUCCESS_MESSAGES["status_updated"].format(name=name, status=new_status.value)
    )


@plan_app.command("checkout")
def checkout_plan(
    name: str = typer.Argument(..., help="Plan name"),
) -> None:
    """Checkout the git branch for a plan.

    Examples:
        oak plan checkout auth-redesign
    """
    project_root = get_project_root()
    if not project_root:
        print_error(PLAN_ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error("Not a git repository.")
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Load plan to get branch name
    try:
        manifest = service.load_manifest(name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=name))
        raise typer.Exit(code=1)

    if not manifest.branch_name:
        # Create branch if it doesn't exist
        branch_name = service.build_branch_name(name)
        try:
            service.checkout_branch(branch_name, create=True)
            manifest.branch_name = branch_name
            service._save_manifest(name, manifest)
            print_success(f"Created and switched to branch: {branch_name}")
        except subprocess.CalledProcessError as exc:
            print_error(f"Failed to create branch: {exc}")
            raise typer.Exit(code=1)
    else:
        try:
            service.checkout_branch(manifest.branch_name, create=False)
            print_success(f"Switched to branch: {manifest.branch_name}")
        except subprocess.CalledProcessError as exc:
            print_error(f"Failed to checkout branch: {exc}")
            raise typer.Exit(code=1)


@plan_app.command("validate")
def validate_plan(
    name: Annotated[str, typer.Argument(help="Plan name")],
) -> None:
    """Validate plan against requirements and constitution.

    This command checks the plan for completeness, validates against constitution rules,
    and (for issue-first plans) checks acceptance criteria alignment.

    Examples:
        oak plan validate auth-redesign
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Check prerequisites
    _check_plan_prerequisites(project_root, service)

    # Load plan
    try:
        plan = service.load_plan(name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=name))
        raise typer.Exit(code=1)

    # Get plan file path and read content
    plan_file_path = service.get_plan_file_path(name)
    if not plan_file_path.exists():
        print_error(f"Plan file not found: {plan_file_path}")
        raise typer.Exit(code=1)

    plan_text = plan_file_path.read_text(encoding="utf-8")

    # Load issue context if this is an issue-first plan
    issue_obj: Issue | None = None
    has_issue_source = "issue" in plan.manifest.sources
    if has_issue_source:
        try:
            issue_obj = service.load_issue_context(name)
        except FileNotFoundError:
            print_warning("Issue context not found, skipping issue-specific validation")

    # Get branch info
    branch_name = plan.manifest.branch_name or service.build_branch_name(name)
    branch_exists = service.branch_exists(branch_name)

    # Run validation
    issues = _validate_plan(
        issue_obj,
        plan_text,
        branch_exists,
        branch_name,
        project_root,
    )

    # Save validation results
    validation_path = service.get_plan_dir(name) / "validation.md"
    _save_validation_results(validation_path, issue_obj, name, issues, branch_name)

    # Display results
    print_panel(
        f"[bold]Plan:[/bold] {name}\n"
        f"[cyan]Display Name:[/cyan] {plan.manifest.display_name}\n"
        + (
            f"[cyan]Sources:[/cyan] {', '.join(plan.manifest.sources)}\n"
            if plan.manifest.sources
            else ""
        )
        + f"[cyan]Plan File:[/cyan] {plan_file_path}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
        f"[cyan]Validation:[/cyan] {validation_path}",
        title="Plan Artifacts",
        style="cyan",
    )

    if issues:
        print_warning("Validation identified the following items to review:")
        for message in issues:
            print_error(f"- {message}")
        print_info(f"\nValidation results saved to: {validation_path}")
    else:
        print_success("All validation checks passed!")
        print_info(f"Validation results saved to: {validation_path}")


@plan_app.command("refresh")
def refresh_plan(
    name: Annotated[str, typer.Argument(help="Plan name")],
) -> None:
    """Refresh issue context from provider (issue-first plans only).

    Fetches fresh data from the issue provider and updates the local context files
    while preserving all other artifacts (plan.md, tasks.md, research/, etc.).

    This is useful when:
    - Issue has been updated since you last fetched it
    - New comments or context have been added
    - Acceptance criteria or requirements have changed
    - You want the latest state before implementing

    Examples:
        oak plan refresh auth-fix
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Load plan to check if it's issue-first
    try:
        plan = service.load_plan(name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=name))
        raise typer.Exit(code=1)

    # Check if this is an issue-first plan
    if "issue" not in plan.manifest.sources or not plan.manifest.issue:
        print_error(
            f"Plan '{name}' is not an issue-first plan. Refresh only works for issue-first plans."
        )
        print_info("Issue-first plans are created with: oak plan issue <name> --id <issue-id>")
        raise typer.Exit(code=1)

    # Get provider
    provider_key = plan.manifest.issue.provider
    issue_id = plan.manifest.issue.id

    print_info(f"Refreshing {provider_key} issue {issue_id} from provider...")

    # Refresh context
    try:
        old_item, new_item, changes = service.refresh_issue_context(name)
    except IssueProviderError as e:
        print_error(f"Failed to fetch fresh data: {e}")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        print_error(f"Context file not found for {name}")
        raise typer.Exit(code=1)

    # Display changes
    if not changes["has_changes"]:
        print_success(f"Plan '{name}' is up to date (no changes detected)")
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
    context_path = service.get_issue_context_path(name)
    summary_path = service.get_issue_summary_path(name)
    print_success(
        f"Refreshed context for plan '{name}'\n"
        f"  Updated: {context_path}\n"
        f"  Updated: {summary_path}"
    )


@plan_app.command("implement")
def implement_plan(
    name: Annotated[
        str | None, typer.Argument(help="Plan name (inferred from branch if omitted)")
    ] = None,
) -> None:
    """Prepare implementation context for a plan.

    This command displays all relevant information needed to begin implementing a plan,
    including plan details, acceptance criteria, tasks, and research findings.

    Works with both issue-first and research-first plans:
    - Issue-first: Shows issue context, acceptance criteria, related items
    - Research-first: Shows research topics, key findings, recommendations

    Examples:
        oak plan implement auth-redesign
        oak plan implement  # Uses current branch
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    git_root = get_git_root(project_root)
    if not git_root:
        print_error(ERROR_MESSAGES["git_not_initialized"])
        raise typer.Exit(code=1)

    service = PlanService(project_root)

    # Resolve plan name
    plan_name = name or service.infer_plan_from_branch()
    if not plan_name:
        print_error(PLAN_ERROR_MESSAGES["plan_not_specified"])
        raise typer.Exit(code=1)

    # Load plan
    try:
        plan = service.load_plan(plan_name)
    except FileNotFoundError:
        print_error(PLAN_ERROR_MESSAGES["plan_not_found"].format(name=plan_name))
        raise typer.Exit(code=1)

    # Get plan file and read content
    plan_file_path = service.get_plan_file_path(plan_name)
    if not plan_file_path.exists():
        print_error(f"Plan file not found: {plan_file_path}")
        raise typer.Exit(code=1)

    plan_text = plan_file_path.read_text(encoding="utf-8")

    # Detect source types
    has_issue_source = "issue" in plan.manifest.sources
    has_research_source = "research" in plan.manifest.sources

    # Get branch info
    branch_name = plan.manifest.branch_name or service.build_branch_name(plan_name)

    # Extract common sections
    objectives = _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Objectives"]) or "Pending"
    definition = (
        _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Definition of Done"]) or "Pending"
    )
    risks_preview = (
        _extract_section(plan_text, ISSUE_PLAN_SECTION_HEADINGS["Risks & Mitigations"]) or "Pending"
    )

    # Build implementation panel
    panel_content = (
        f"[bold]Plan:[/bold] {plan_name}\n"
        f"[cyan]Display Name:[/cyan] {plan.manifest.display_name}\n"
        f"[cyan]Status:[/cyan] {plan.manifest.status.value}\n"
        f"[cyan]Sources:[/cyan] {', '.join(plan.manifest.sources) if plan.manifest.sources else 'none'}\n"
        f"[cyan]Branch:[/cyan] {branch_name}\n"
    )

    # Add issue-specific information
    if has_issue_source and plan.manifest.issue:
        panel_content += (
            f"\n[bold]Issue Source:[/bold]\n"
            f"  Provider: {plan.manifest.issue.provider}\n"
            f"  ID: {plan.manifest.issue.id}\n"
        )
        if plan.manifest.issue.title:
            panel_content += f"  Title: {plan.manifest.issue.title}\n"

        # Show issue context paths
        context_path = service.get_issue_context_path(plan_name)
        summary_path = service.get_issue_summary_path(plan_name)
        panel_content += f"\n[cyan]Issue Context:[/cyan] {context_path}\n"
        if summary_path.exists():
            panel_content += f"[cyan]Context Summary:[/cyan] {summary_path}\n"

    # Add research information
    if has_research_source:
        research_status = service.get_research_status(plan_name)
        if research_status["total"] > 0:
            panel_content += (
                f"\n[bold]Research:[/bold]\n"
                f"  Topics: {research_status['completed']}/{research_status['total']} completed\n"
                f"  Research Dir: {service.get_research_dir(plan_name)}/\n"
            )

    # Add plan artifacts
    panel_content += f"\n[cyan]Plan File:[/cyan] {plan_file_path}\n"

    # Add tasks if available
    if len(plan.tasks) > 0:
        tasks_path = service.get_tasks_file_path(plan_name)
        panel_content += f"[cyan]Tasks:[/cyan] {tasks_path} ({len(plan.tasks)} tasks)\n"

    print_panel(
        panel_content,
        title="Implementation Context",
        style="green",
    )

    # Display key plan sections
    print_info(f"Objectives: {objectives}")
    print_info(f"Definition of Done: {definition}")

    # Show acceptance criteria preview (issue-first plans)
    if has_issue_source:
        acceptance_preview = _preview_list_section(plan_text, "## Acceptance Criteria")
        if acceptance_preview:
            print_info(f"Acceptance criteria (first 3): {acceptance_preview}")

    # Show research topics (research-first plans)
    if has_research_source:
        research_status = service.get_research_status(plan_name)
        if research_status["completed"] > 0:
            completed_topics = [t for t in research_status["topics"] if t["status"] == "completed"]
            if completed_topics:
                topic_names = ", ".join(t["title"] for t in completed_topics[:3])
                print_info(f"Completed research: {topic_names}")

    print_info(f"Risks/Mitigations: {risks_preview}")

    print_success("Ready to implement using plan, artifacts, and branch above.")


# Helper functions for validation and plan processing


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


def _validate_plan(
    issue_obj: Issue | None,
    plan_text: str,
    branch_exists: bool,
    branch_name: str,
    project_root: Path,
) -> list[str]:
    """Return a list of validation issues for the given plan.

    Args:
        issue_obj: Optional Issue object for issue-first plans
        plan_text: Plan markdown content
        branch_exists: Whether the branch exists
        branch_name: Git branch name
        project_root: Project root directory

    Returns:
        List of validation issue messages
    """
    issues: list[str] = []

    # Check acceptance criteria (only for issue-first plans)
    if issue_obj:
        if not issue_obj.acceptance_criteria:
            issues.append("No acceptance criteria captured in context.json.")

        acceptance_pending = _section_contains_pending(plan_text, "## Acceptance Criteria")
        if acceptance_pending:
            issues.append("Acceptance criteria in plan.md are still marked as pending.")

    # Check required sections
    for title, heading in ISSUE_PLAN_SECTION_HEADINGS.items():
        section_body = _extract_section(plan_text, heading)
        if not section_body or _is_pending(section_body):
            issues.append(f"{title} section is incomplete in plan.md.")

    # Check branch
    if not branch_exists:
        issues.append(f"Branch '{branch_name}' does not exist locally. Create or push the branch.")

    # Validate against constitution
    issues.extend(_validate_against_constitution(plan_text, project_root))
    return issues


def _validate_against_constitution(plan_text: str, project_root: Path) -> list[str]:
    """Check plan content against constitution rules.

    Args:
        plan_text: Full plan markdown text
        project_root: Project root directory

    Returns:
        List of validation issues for missing constitution requirements
    """
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(project_root)
    constitution_dir = config_service.get_constitution_dir()
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
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
    issue_obj: Issue | None,
    plan_name: str,
    issues: list[str],
    branch_name: str,
) -> None:
    """Save validation results to markdown file.

    Args:
        validation_path: Path to save validation results
        issue_obj: Optional Issue being validated (for issue-first plans)
        plan_name: Plan name
        issues: List of validation issues found
        branch_name: Git branch name
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build header based on whether this is issue-first or research-first
    if issue_obj:
        header = f"""# Validation Results

**Issue:** {issue_obj.identifier}
**Title:** {issue_obj.title}
**Branch:** {branch_name}
**Validated:** {timestamp}
**Status:** {'⚠️  Issues Found' if issues else '✅ Passed'}

## Summary

"""
    else:
        header = f"""# Validation Results

**Plan:** {plan_name}
**Branch:** {branch_name}
**Validated:** {timestamp}
**Status:** {'⚠️  Issues Found' if issues else '✅ Passed'}

## Summary

"""

    if issues:
        content = header + (
            f"Found {len(issues)} issue(s) that should be addressed before implementation:\n\n"
        )
        for i, issue in enumerate(issues, 1):
            content += f"{i}. {issue}\n"
        content += "\n**Recommendation:** Address these issues before running implementation.\n"
    else:
        content = (
            header
            + "All validation checks passed! The plan is complete and ready for implementation.\n\n"
        )
        content += "**Next Step:** Begin implementation.\n"

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
