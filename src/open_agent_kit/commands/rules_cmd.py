"""Rules management utility commands for agents.

This module provides CLI commands for managing AI agent rules files (constitution.md).
The 'oak rules' command group replaces the legacy 'oak constitution' commands.
"""

import json

import typer

from open_agent_kit.config.messages import ERROR_MESSAGES, INFO_MESSAGES, SUCCESS_MESSAGES
from open_agent_kit.services.agent_file_service import AgentFileService
from open_agent_kit.services.constitution_service import ConstitutionService
from open_agent_kit.services.validation_service import ValidationService
from open_agent_kit.utils import (
    get_project_root,
    print_error,
    print_info,
    print_success,
    print_warning,
)

# Create rules command group (replaces legacy 'constitution' commands)
rules_app = typer.Typer(
    name="rules",
    help="Rules management utility commands (for agent use)",
    no_args_is_help=True,
)


@rules_app.command("create")
def create(
    project_name: str = typer.Option(..., "--project-name", help="Project name"),
    author: str = typer.Option(..., "--author", help="Author name"),
    tech_stack: str | None = typer.Option(None, "--tech-stack", help="Technology stack"),
    description: str | None = typer.Option(None, "--description", help="Project description"),
    context_file: str | None = typer.Option(
        None, "--context-file", help="JSON file with decision context"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing constitution"),
    skip_agent_files: bool = typer.Option(
        False, "--skip-agent-files", help="Skip automatic agent file generation"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip automatic validation"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Create constitution with full workflow (recommended for agents).

    This is the PRIMARY command for constitution creation. It combines:
    1. Constitution file creation (from metadata + decision context)
    2. Agent instruction file generation (automatic)
    3. Validation (automatic)

    The agent's job is to gather user decisions and create a decision context JSON file.
    This command handles all the deterministic steps automatically.

    Example:
        # Basic usage with decision context
        oak constitution create --project-name "MyProject" --author "Jane" --context-file decisions.json

        # Full workflow with JSON output for agent parsing
        oak constitution create --project-name "MyProject" --author "Jane" \\
            --tech-stack "FastAPI, Python" --description "API service" \\
            --context-file decisions.json --json

        # Skip optional steps
        oak constitution create --project-name "MyProject" --author "Jane" \\
            --context-file decisions.json --skip-validation
    """
    from pathlib import Path

    from open_agent_kit.services.agent_service import AgentService

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    results: dict = {
        "success": False,
        "constitution_path": None,
        "agent_files": {},
        "validation": None,
        "errors": [],
    }

    # Step 1: Create constitution file
    service = ConstitutionService.from_config(project_root)
    constitution_path = service.get_constitution_path()

    if constitution_path.exists() and not force:
        error_msg = f"Constitution already exists at {constitution_path}. Use --force to overwrite."
        if json_output:
            results["errors"].append(error_msg)
            print(json.dumps(results, indent=2))
        else:
            print_error(error_msg)
        raise typer.Exit(code=1)

    if force and constitution_path.exists():
        if not json_output:
            print_warning(f"Overwriting existing constitution at {constitution_path}")
        constitution_path.unlink()

    # Load decision context if provided
    decision_context = None
    if context_file:
        try:
            from pydantic import ValidationError

            from open_agent_kit.models.constitution import DecisionContext

            context_path = Path(context_file)
            if not context_path.exists():
                error_msg = f"Context file not found: {context_file}"
                if json_output:
                    results["errors"].append(error_msg)
                    print(json.dumps(results, indent=2))
                else:
                    print_error(error_msg)
                raise typer.Exit(code=1)

            with open(context_path) as f:
                context_data = json.load(f)

            decision_context = DecisionContext(**context_data)
            if not json_output:
                print_info(f"Loaded decision context from {context_file}")

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in context file: {e}"
            if json_output:
                results["errors"].append(error_msg)
                print(json.dumps(results, indent=2))
            else:
                print_error(error_msg)
            raise typer.Exit(code=1)
        except ValidationError as e:
            error_details = "\n".join([f"  - {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            error_msg = f"Invalid decision context:\n{error_details}"
            if json_output:
                results["errors"].append(error_msg)
                print(json.dumps(results, indent=2))
            else:
                print_error(error_msg)
            raise typer.Exit(code=1)

    try:
        if not json_output:
            print_info(INFO_MESSAGES["generating_constitution"])

        constitution = service.create(
            project_name=project_name,
            author=author,
            tech_stack=tech_stack,
            description=description,
            decision_context=decision_context,
        )

        results["constitution_path"] = str(constitution.file_path)

        if not json_output:
            print_success(f"Constitution created at {constitution.file_path}")

    except Exception as e:
        error_msg = f"Error creating constitution: {e}"
        if json_output:
            results["errors"].append(error_msg)
            print(json.dumps(results, indent=2))
        else:
            print_error(error_msg)
        raise typer.Exit(code=1)

    # Step 2: Generate agent instruction files (unless skipped)
    if not skip_agent_files:
        try:
            if not json_output:
                print_info(INFO_MESSAGES["generating_agent_files"])

            agent_service = AgentService(project_root)
            agent_results = agent_service.update_agent_instructions_from_constitution(
                constitution_path
            )

            results["agent_files"] = {
                "updated": agent_results.get("updated", []),
                "created": agent_results.get("created", []),
                "skipped": agent_results.get("skipped", []),
            }

            if not json_output:
                if agent_results["updated"]:
                    print_success(f"Updated agent files: {', '.join(agent_results['updated'])}")
                if agent_results["created"]:
                    print_success(f"Created agent files: {', '.join(agent_results['created'])}")
                if agent_results["skipped"]:
                    print_info(f"Skipped (already updated): {', '.join(agent_results['skipped'])}")

        except Exception as e:
            error_msg = f"Error updating agent files: {e}"
            results["errors"].append(error_msg)
            if not json_output:
                print_warning(error_msg)
            # Don't exit - agent files are important but not fatal

    # Step 3: Validate constitution (unless skipped)
    if not skip_validation:
        try:
            validation_service = ValidationService.from_config()
            constitution = service.load()
            validation_result = validation_service.validate(constitution)

            results["validation"] = {
                "is_valid": validation_result.is_valid,
                "total_issues": validation_result.total_issues,
                "high_priority": validation_result.high_priority_count,
            }

            if not json_output:
                if validation_result.is_valid:
                    print_success("Validation passed")
                else:
                    print_warning(
                        f"Validation found {validation_result.total_issues} issues "
                        f"({validation_result.high_priority_count} high priority)"
                    )
                    print_info("Run 'oak constitution validate --json' for details")

        except Exception as e:
            error_msg = f"Error validating constitution: {e}"
            results["errors"].append(error_msg)
            if not json_output:
                print_warning(error_msg)
            # Don't exit - validation is informational

    # Final output
    results["success"] = len(results["errors"]) == 0 or (results["constitution_path"] is not None)

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print()
        if results["success"]:
            print_success("✓ Constitution creation complete!")
            print_info(f"  Constitution: {results['constitution_path']}")
            if results["agent_files"]:
                total_files = len(results["agent_files"].get("updated", [])) + len(
                    results["agent_files"].get("created", [])
                )
                print_info(f"  Agent files: {total_files} updated/created")
            print_info("\nNext steps:")
            print_info("  1. Review the generated constitution")
            print_info("  2. Commit changes to version control")
        else:
            print_error("Constitution creation completed with errors")
            for error in results["errors"]:
                print_error(f"  - {error}")


@rules_app.command("create-file")
def create_file(
    project_name: str = typer.Option(..., "--project-name", help="Project name"),
    author: str = typer.Option(..., "--author", help="Author name"),
    tech_stack: str | None = typer.Option(None, "--tech-stack", help="Technology stack"),
    description: str | None = typer.Option(None, "--description", help="Project description"),
    context_file: str | None = typer.Option(
        None, "--context-file", help="JSON file with decision context"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing constitution (use for modernization/upgrades)"
    ),
) -> None:
    """Create constitution file with metadata and optional decision context (utility for agents).

    This command creates a constitution file based on the provided metadata and optional
    decision context. The decision context should be a JSON file containing user decisions
    about testing strategy, code review policies, documentation level, and CI/CD enforcement.

    The constitution template uses conditional sections based on these decisions to generate
    requirements that match the project's needs.

    Use --force to overwrite an existing constitution (typically during modernization/upgrade).

    Example:
        oak constitution create-file --project-name "MyProject" --author "Jane Doe"
        oak constitution create-file --project-name "MyProject" --author "Jane" --context-file decisions.json
        oak constitution create-file --project-name "MyProject" --author "Jane" --context-file decisions.json --force
    """
    from pathlib import Path

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    # Check if constitution exists and handle force flag
    service = ConstitutionService.from_config(project_root)
    constitution_path = service.get_constitution_path()

    if constitution_path.exists() and not force:
        print_error(ERROR_MESSAGES["constitution_exists"].format(path=str(constitution_path)))
        print_info("Use --force to overwrite existing constitution")
        raise typer.Exit(code=1)

    if force and constitution_path.exists():
        print_warning(f"Overwriting existing constitution at {constitution_path}")

    print_info(INFO_MESSAGES["generating_constitution"])

    # Load decision context if provided
    decision_context = None
    if context_file:
        try:
            from pydantic import ValidationError

            from open_agent_kit.models.constitution import DecisionContext

            context_path = Path(context_file)
            if not context_path.exists():
                print_error(f"Context file not found: {context_file}")
                raise typer.Exit(code=1)

            with open(context_path) as f:
                context_data = json.load(f)

            # Validate and convert to DecisionContext model
            decision_context = DecisionContext(**context_data)
            print_info(f"Loaded decision context from {context_file}")

        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON in context file: {e}")
            raise typer.Exit(code=1)
        except ValidationError as e:
            error_details = "\n".join([f"  - {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            print_error(f"Invalid decision context:\n{error_details}")
            raise typer.Exit(code=1)
        except Exception as e:
            print_error(f"Error loading context file: {e}")
            raise typer.Exit(code=1)

    try:
        # If forcing and file exists, remove the FileExistsError check in service
        if force and constitution_path.exists():
            # Delete existing file before creating
            constitution_path.unlink()

        constitution = service.create(
            project_name=project_name,
            author=author,
            tech_stack=tech_stack,
            description=description,
            decision_context=decision_context,
        )

        # Print path to stdout for agent to read
        print(str(constitution.file_path))

        if force:
            print_success("Constitution regenerated successfully")
        else:
            print_success(SUCCESS_MESSAGES["constitution_created"])

        if decision_context:
            print_info(
                "Constitution generated with decision context - review sections to verify they match your decisions"
            )

    except FileExistsError as e:
        print_error(ERROR_MESSAGES["constitution_exists"].format(path=str(e)))
        print_info("Use --force to overwrite existing constitution")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error creating constitution: {e}")
        raise typer.Exit(code=1)


@rules_app.command("validate")
def validate(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Validate constitution and return issues (utility for agents).

    Returns validation issues in human-readable or JSON format.
    Agents should use --json flag to parse the results.

    Example:
        oak constitution validate --json
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        constitution_service = ConstitutionService.from_config(project_root)
        validation_service = ValidationService.from_config()

        constitution = constitution_service.load()
        result = validation_service.validate(constitution)
        raw_category_counts = result.stats.get("category_counts", {})
        raw_priority_counts = result.stats.get("priority_counts", {})
        # Ensure we have dict types
        category_counts: dict[str, int] = (
            raw_category_counts if isinstance(raw_category_counts, dict) else {}
        )
        priority_counts: dict[str, int] = (
            raw_priority_counts if isinstance(raw_priority_counts, dict) else {}
        )

        focus_areas: list[str] = []
        if category_counts.get("quality"):
            focus_areas.append(f"quality ({category_counts['quality']})")
        if category_counts.get("consistency"):
            focus_areas.append(f"consistency ({category_counts['consistency']})")
        if category_counts.get("structure"):
            focus_areas.append(f"structure ({category_counts['structure']})")

        summary_text = (
            "No issues detected. Lead with your own qualitative assessment before relying on this output."
            if result.is_valid
            else (
                "Focus areas: " + ", ".join(focus_areas)
                if focus_areas
                else "Issues detected. Review categories below and synthesize your own remediation plan."
            )
        )

        if json_output:
            # Output JSON for agent parsing
            output = {
                "is_valid": result.is_valid,
                "issues": [issue.to_dict() for issue in result.issues],
                "stats": result.stats,
                "summary": {
                    "text": summary_text,
                    "total_issues": result.total_issues,
                    "priority_counts": priority_counts,
                    "category_counts": category_counts,
                    "focus_areas": focus_areas,
                    "guidance": "This validator uses pattern-matching heuristics (keyword detection, sentence counting) rather than semantic content analysis. Use findings as supporting evidence, not definitive judgments.",
                },
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            if result.is_valid:
                print_success(SUCCESS_MESSAGES["constitution_validated"])
            else:
                print_error(ERROR_MESSAGES["constitution_validation_failed"])

            print_info("\nValidation summary:")
            print(f"  Total issues: {result.total_issues}")
            print(
                f"  Priority counts → High: {result.high_priority_count} | Medium: {result.medium_priority_count} | Low: {result.low_priority_count}"
            )

            if focus_areas:
                print(f"  Focus areas: {', '.join(focus_areas)}")

            if category_counts:
                print("\nCategory breakdown:")
                for category, count in sorted(
                    category_counts.items(), key=lambda item: item[1], reverse=True
                ):
                    if count:
                        print(f"  - {category.capitalize()}: {count}")

            print_info(
                "\nNote: This validator uses pattern-matching heuristics (keyword detection, "
                "sentence counting) rather than semantic content analysis. Use findings as "
                "supporting evidence, not definitive judgments."
            )

            if not result.is_valid:
                raise typer.Exit(code=1)

    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error validating constitution: {e}")
        raise typer.Exit(code=1)


@rules_app.command("add-amendment")
def add_amendment(
    summary: str = typer.Option(..., "--summary", help="Amendment summary"),
    rationale: str = typer.Option(..., "--rationale", help="Amendment rationale"),
    amendment_type: str = typer.Option(..., "--type", help="Amendment type (major/minor/patch)"),
    author: str = typer.Option(..., "--author", help="Author name"),
    section: str | None = typer.Option(None, "--section", help="Section being amended"),
    impact: str | None = typer.Option(None, "--impact", help="Impact description"),
) -> None:
    """Add amendment and increment version (utility for agents).

    Creates an amendment, increments the version, and saves the constitution.
    Agents should then call list-agent-files to update agent instruction files.

    Example:
        oak constitution add-amendment --summary "Add testing req" --rationale "..." --type minor --author "Jane"
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    print_info(INFO_MESSAGES["adding_amendment"])

    try:
        service = ConstitutionService.from_config(project_root)

        amendment = service.add_amendment(
            summary=summary,
            rationale=rationale,
            amendment_type=amendment_type,
            author=author,
            section=section,
            impact=impact,
        )

        # Print new version to stdout for agent to read
        print(amendment.version)
        print_success(SUCCESS_MESSAGES["constitution_amended"])

    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error adding amendment: {e}")
        raise typer.Exit(code=1)


@rules_app.command("check")
def check(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Check if constitution exists and is valid (utility for agents).

    Performs basic checks:
    - File exists at oak/constitution.md
    - File is not empty
    - File has minimum required content

    Does NOT reason about quality or completeness - that's the agent's job.

    Example:
        oak constitution check
        oak constitution check --json
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        constitution_service = ConstitutionService.from_config(project_root)
        constitution_path = constitution_service.get_constitution_path()

        # Check 1: File exists
        if not constitution_path.exists():
            if json_output:
                output = {
                    "exists": False,
                    "path": str(constitution_path),
                    "error": "Constitution file not found",
                    "recommendation": "Run /oak.constitution-create to create one",
                }
                print(json.dumps(output, indent=2))
            else:
                print_error(ERROR_MESSAGES["no_constitution"])
                print_info("Run /oak.constitution-create to create one")
            raise typer.Exit(code=1)

        # Check 2: File is not empty
        content = constitution_service.get_content()
        if not content or len(content.strip()) == 0:
            if json_output:
                output = {
                    "exists": True,
                    "path": str(constitution_path),
                    "is_empty": True,
                    "error": "Constitution file is empty",
                    "recommendation": "File exists but has no content",
                }
                print(json.dumps(output, indent=2))
            else:
                print_error("Constitution file is empty")
                print_info(f"File exists at {constitution_path} but has no content")
            raise typer.Exit(code=1)

        # All checks passed (file exists and has content)
        if json_output:
            output = {
                "exists": True,
                "path": str(constitution_path),
                "is_empty": False,
                "content_length": len(content),
                "valid": True,
            }
            print(json.dumps(output, indent=2))
        else:
            print_success(f"Constitution exists at {constitution_path}")
            print_info(f"Content length: {len(content)} characters")

    except Exception as e:
        if json_output:
            output = {
                "exists": False,
                "error": str(e),
            }
            print(json.dumps(output, indent=2))
        else:
            print_error(f"Error checking constitution: {e}")
        raise typer.Exit(code=1)


@rules_app.command("get-version")
def get_version() -> None:
    """Get the current constitution version.

    Example:
        oak constitution get-version
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        constitution_service = ConstitutionService.from_config(project_root)
        constitution = constitution_service.load()
        print(constitution.metadata.version)
    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error getting version: {e}")
        raise typer.Exit(code=1)


@rules_app.command("list-agent-files")
def list_agent_files(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """List all agent instruction file paths (utility for agents).

    Returns paths to agent instruction files for all detected agents.
    Agents use this to know which files to update after amendments.

    Example:
        oak constitution list-agent-files --json
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        service = AgentFileService.from_config(project_root)
        agent_files = service.list_agent_files()

        if json_output:
            # Output JSON for agent parsing
            output = {agent: str(path) if path else None for agent, path in agent_files.items()}
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print("Agent instruction files:")
            for agent, path in agent_files.items():
                if path:
                    print(f"  {agent}: {path}")
                else:
                    print(f"  {agent}: (not found)")

    except Exception as e:
        print_error(f"Error listing agent files: {e}")
        raise typer.Exit(code=1)


@rules_app.command("get-content")
def get_content() -> None:
    """Get constitution content (utility for agents).

    Prints the raw constitution file content to stdout.
    Agents use this to read the current constitution.

    Example:
        oak constitution get-content
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        service = ConstitutionService.from_config(project_root)
        content = service.get_content()
        print(content)

    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error getting content: {e}")
        raise typer.Exit(code=1)


@rules_app.command("update-content")
def update_content(
    content: str = typer.Option(..., "--content", help="New constitution content"),
) -> None:
    """Update constitution content (utility for agents).

    Writes new content to the constitution file.
    Agents use this after enhancing or fixing the constitution.

    Example:
        oak constitution update-content --content "$(cat new_constitution.md)"
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    try:
        service = ConstitutionService.from_config(project_root)
        service.update_content(content)
        print_success("Constitution updated")

    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error updating content: {e}")
        raise typer.Exit(code=1)


@rules_app.command("generate-agent-files")
def generate_agent_files(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Generate agent instruction files (utility for agents).

    Creates or updates agent instruction files for all detected agents.
    Agents use this after creating a constitution.

    Example:
        oak constitution generate-agent-files
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    if not json_output:
        print_info(INFO_MESSAGES["generating_agent_files"])

    try:
        constitution_service = ConstitutionService.from_config(project_root)
        agent_service = AgentFileService.from_config(project_root)

        constitution = constitution_service.load()
        generated = agent_service.generate_agent_files(constitution)

        if json_output:
            # Output JSON for agent parsing
            output = {agent: str(path) for agent, path in generated.items()}
            print(json.dumps(output, indent=2))
        else:
            # Print generated files to stdout
            for agent, path in generated.items():
                print(f"{agent}: {path}")

            print_success(SUCCESS_MESSAGES["agent_files_generated"] + f" ({len(generated)} files)")

    except FileNotFoundError:
        print_error(ERROR_MESSAGES["no_constitution"])
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error generating agent files: {e}")
        raise typer.Exit(code=1)


@rules_app.command("detect-existing")
def detect_existing(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Detect existing agent instruction files (utility for agents).

    Checks for existing agent instruction files like .github/copilot-instructions.md
    and returns information about what exists and can be used as context.

    Example:
        oak constitution detect-existing --json
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


@rules_app.command("update-agent-files")
def update_agent_files(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be updated without making changes"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Update agent instruction files with constitution reference (utility for agents).

    IMPORTANT: This operation is ADDITIVE ONLY:
    - Existing files: Constitution reference appended (backup created)
    - New files: Created with constitution reference
    - Already updated: Skipped (idempotent)

    Example:
        oak constitution update-agent-files
        oak constitution update-agent-files --dry-run
        oak constitution update-agent-files --json
    """
    from open_agent_kit.services.agent_service import AgentService

    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    constitution_service = ConstitutionService.from_config(project_root)
    if not constitution_service.exists():
        print_error("Constitution not found. Run 'oak constitution create-file' first.")
        raise typer.Exit(code=1)

    constitution_path = constitution_service.get_constitution_path()
    agent_service = AgentService(project_root)

    if dry_run:
        # Show what would be updated
        existing = agent_service.detect_existing_agent_instructions()
        print_info("Dry run - showing what would be updated:\n")
        for agent_type, info in existing.items():
            if info["exists"] and not info["has_constitution_ref"]:
                print(f"  Would UPDATE: {agent_type} ({info['path']})")
            elif not info["exists"]:
                print(f"  Would CREATE: {agent_type} ({info['path']})")
            elif info["has_constitution_ref"]:
                print(f"  Would SKIP: {agent_type} (already has reference)")
        print_info("\nRun without --dry-run to apply changes.")
        return

    # Perform the update
    results = agent_service.update_agent_instructions_from_constitution(constitution_path)

    if json_output:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_success("✓ Agent instruction files updated:\n")

        if results["updated"]:
            print(f"  Updated (appended reference): {', '.join(results['updated'])}")
        if results["created"]:
            print(f"  Created: {', '.join(results['created'])}")
        if results["skipped"]:
            print(f"  Skipped (already has reference): {', '.join(results['skipped'])}")
        if results["backed_up"]:
            print("\n  Backups created:")
            for backup in results["backed_up"]:
                print(f"    - {backup}")
        if results["errors"]:
            print_error(f"\n  Errors: {', '.join(results['errors'])}")


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
        oak constitution sync-agents
        oak constitution sync-agents --dry-run
        oak constitution sync-agents --json
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
        print_error("No constitution found. Create one first with 'oak constitution create'.")
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


@rules_app.command("analyze")
def analyze(
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Analyze project for constitution creation workflow (utility for agents).

    Performs comprehensive project analysis to determine if the project is
    greenfield, brownfield-minimal, or brownfield-mature. This command replaces
    multiple bash commands with a single CLI call.

    Analysis includes:
    - Test infrastructure detection (tests/, spec/, etc.)
    - CI/CD workflow detection (GitHub Actions, GitLab CI, etc.)
    - Agent instruction file detection (with content analysis)
    - Project type file detection (package.json, pyproject.toml, etc.)
    - Application code directory detection (src/, lib/, etc.)

    IMPORTANT: OAK-installed files (.oak/, oak.* commands) are excluded from
    analysis to avoid false positives on projects that only have OAK tooling.

    Example:
        oak constitution analyze --json
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
            print_info("Project Analysis for Constitution Creation\n")

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
                for wf in results["ci_cd"]["workflows"][:3]:  # Show first 3
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
