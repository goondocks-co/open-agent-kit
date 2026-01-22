"""Rules management utility commands.

This module provides CLI commands for managing AI agent rules files.
These are lightweight utilities - agents write constitutions and agent files
directly using the project-rules skill.

Commands:
- analyze: Analyze project to classify as greenfield/brownfield/mature
- sync-agents: Ensure all configured agents have instruction files
- detect-existing: Detect existing agent instruction files for context
"""

import json

import typer

from open_agent_kit.config.messages import ERROR_MESSAGES
from open_agent_kit.features.rules_management.constitution import ConstitutionService
from open_agent_kit.utils import (
    get_project_root,
    print_error,
    print_info,
    print_success,
)

# Create rules command group
rules_app = typer.Typer(
    name="rules",
    help="Rules management utility commands",
    no_args_is_help=True,
)


@rules_app.command("analyze")
def analyze(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Analyze project for constitution creation workflow.

    Performs comprehensive project analysis to determine if the project is
    greenfield, brownfield-minimal, or brownfield-mature. Useful for agents
    to understand the project context before creating a constitution.

    Analysis includes:
    - Test infrastructure detection (tests/, spec/, etc.)
    - CI/CD workflow detection (GitHub Actions, GitLab CI, etc.)
    - Agent instruction file detection (with content analysis)
    - Project type file detection (package.json, pyproject.toml, etc.)
    - Application code directory detection (src/, lib/, etc.)

    OAK-installed files (.oak/, oak.* commands) are excluded from analysis.

    Example:
        oak rules analyze
        oak rules analyze --json
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        service = ConstitutionService.from_config(project_root)
        results = service.analyze_project()

        if json_output:
            print(json.dumps(results, indent=2))
        else:
            # Human-readable output
            print_info("Project Analysis\n")

            # Classification
            classification = results["classification"]
            classification_emoji = {
                "greenfield": "🌱",
                "brownfield-minimal": "🏗️",
                "brownfield-mature": "🏛️",
            }
            print(
                f"Classification: {classification_emoji.get(classification, '')} {classification.upper()}\n"
            )

            # OAK status
            if results["oak_installed"]:
                print("  ℹ️  OAK installed (excluded from analysis)\n")

            # Test infrastructure
            if results["test_infrastructure"]["found"]:
                dirs = ", ".join(results["test_infrastructure"]["directories"])
                print(f"  ✓ Test infrastructure: {dirs}")
            else:
                print("  ○ Test infrastructure: None found")

            # CI/CD
            if results["ci_cd"]["found"]:
                count = len(results["ci_cd"]["workflows"])
                print(f"  ✓ CI/CD workflows: {count} found")
                for wf in results["ci_cd"]["workflows"][:3]:
                    print(f"      - {wf}")
                if count > 3:
                    print(f"      ... and {count - 3} more")
            else:
                print("  ○ CI/CD workflows: None found")

            # Agent instructions
            if results["agent_instructions"]["found"]:
                meaningful = [
                    f for f in results["agent_instructions"]["files"] if not f["oak_only"]
                ]
                print(f"  ✓ Agent instructions: {len(meaningful)} with non-OAK content")
                for f in meaningful[:3]:
                    print(f"      - {f['path']}")
            else:
                oak_only = [f for f in results["agent_instructions"]["files"] if f["oak_only"]]
                if oak_only:
                    print(f"  ○ Agent instructions: {len(oak_only)} found (OAK-only content)")
                else:
                    print("  ○ Agent instructions: None found")

            # Project files
            if results["project_files"]["found"]:
                files = ", ".join(results["project_files"]["files"][:5])
                count = len(results["project_files"]["files"])
                suffix = f" (+{count - 5} more)" if count > 5 else ""
                print(f"  ✓ Project files: {files}{suffix}")
            else:
                print("  ○ Project files: None found")

            # Application code
            if results["application_code"]["found"]:
                dirs = ", ".join(results["application_code"]["directories"])
                print(f"  ✓ Application code: {dirs}")
            else:
                print("  ○ Application code: None found")

            # Constitution status
            print()
            if results["has_constitution"]:
                print(f"  📜 Constitution exists: {results['constitution_path']}")
            else:
                print("  📜 Constitution: Not yet created")

            print(f"\nSummary: {results['summary']}")

    except Exception as e:
        print_error(f"Error analyzing project: {e}")
        raise typer.Exit(code=1)


@rules_app.command("sync-agents")
def sync_agents(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
) -> None:
    """Sync agent instruction files with constitution.

    Ensures all configured agents have instruction files (CLAUDE.md, AGENTS.md, etc.)
    that reference the project constitution. This is automatically called when agents
    are added via 'oak init', but can be run manually if needed.

    Behavior:
    - Creates instruction files for agents that don't have one
    - Appends constitution reference to existing files that don't have one
    - Skips files that already reference the constitution
    - Never removes files (may have user modifications)

    Example:
        oak rules sync-agents
        oak rules sync-agents --dry-run
        oak rules sync-agents --json
    """
    from open_agent_kit.services.agent_service import AgentService

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    constitution_service = ConstitutionService.from_config(project_root)
    agent_service = AgentService(project_root)

    # Check if constitution exists
    if not constitution_service.exists():
        print_error("No constitution found. Create one first using the project-rules skill.")
        raise typer.Exit(code=1)

    if dry_run:
        # Show what would be done
        existing = agent_service.detect_existing_agent_instructions()

        if json_output:
            print(json.dumps(existing, indent=2, default=str))
            return

        print_info("Dry run - showing what would be done:\n")
        for agent_type, info in existing.items():
            if not info["exists"]:
                print(f"  Would CREATE: {agent_type} ({info['path']})")
            elif not info["has_constitution_ref"]:
                print(f"  Would UPDATE: {agent_type} (append constitution reference)")
            else:
                print(f"  Would SKIP: {agent_type} (already has reference)")
        print_info("\nRun without --dry-run to apply changes.")
        return

    # Perform the sync
    results = constitution_service.sync_agent_instruction_files(
        agents_added=list(agent_service.detect_existing_agent_instructions().keys()),
        agents_removed=[],
    )

    if json_output:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_success("✓ Agent instruction files synced:\n")

        if results["created"]:
            print(f"  Created: {', '.join(results['created'])}")
        if results["updated"]:
            print(f"  Updated (appended reference): {', '.join(results['updated'])}")
        if results["skipped"]:
            skipped = [s for s in results["skipped"] if s != "(no constitution exists)"]
            if skipped:
                print(f"  Skipped (already has reference): {', '.join(skipped)}")
        if results["errors"]:
            print_error(f"\n  Errors: {', '.join(results['errors'])}")

        if not results["created"] and not results["updated"]:
            print("  All agent instruction files are already in sync.")


@rules_app.command("detect-existing")
def detect_existing(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Detect existing agent instruction files.

    Checks for existing agent instruction files like .github/copilot-instructions.md,
    CLAUDE.md, etc. and returns information about what exists. Useful for agents
    to gather context before creating a constitution.

    Example:
        oak rules detect-existing
        oak rules detect-existing --json
    """
    from open_agent_kit.services.agent_service import AgentService

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    agent_service = AgentService(project_root)
    existing = agent_service.detect_existing_agent_instructions()

    if json_output:
        # Output JSON for AI agent parsing
        result = {}
        for agent_type, info in existing.items():
            result[agent_type] = {
                "exists": info["exists"],
                "path": str(info["path"]),
                "has_content": info["content"] is not None,
                "content_length": len(info["content"]) if info["content"] else 0,
                "has_constitution_ref": info["has_constitution_ref"],
            }
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        print_info("Checking for existing agent instruction files...\n")
        found_any = False
        for agent_type, info in existing.items():
            if info["exists"]:
                found_any = True
                content_len = len(info["content"]) if info["content"] else 0
                status = "(has constitution ref)" if info["has_constitution_ref"] else ""
                print(f"  ✓ {agent_type}: {info['path']} ({content_len} chars) {status}")
            else:
                print(f"  ○ {agent_type}: {info['path']} (not found)")

        if not found_any:
            print_info("\nNo existing agent instruction files found.")
        else:
            print_success("\nExisting files can be used as context for constitution generation.")
