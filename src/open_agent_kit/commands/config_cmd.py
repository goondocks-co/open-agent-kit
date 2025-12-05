"""Configuration commands intended for human operators."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from open_agent_kit.config.messages import ERROR_MESSAGES, INFO_MESSAGES
from open_agent_kit.constants import (
    ISSUE_PROVIDER_DEFAULTS,
    ISSUE_PROVIDER_DISPLAY_NAMES,
    SUPPORTED_ISSUE_PROVIDERS,
)
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.plan_service import PlanService
from open_agent_kit.utils import (
    ensure_gitignore_has_env,
    get_project_root,
    print_error,
    print_info,
    print_panel,
    print_success,
    update_env_file,
)
from open_agent_kit.utils.interactive import SelectOption, password_prompt, prompt, select

config_app = typer.Typer(
    name="config",
    help="Project configuration utilities (for human operators)",
    no_args_is_help=False,  # We want to handle no-args case with callback
)

issue_provider_app = typer.Typer(
    name="issue-provider",
    help="Configure issue providers used by AI agents",
    no_args_is_help=True,
)
config_app.add_typer(issue_provider_app, name="issue-provider")


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context) -> None:
    """Project configuration utilities.

    Run without arguments for interactive guided setup,
    or use subcommands for specific configuration tasks.
    """
    # If a subcommand was invoked, let it handle the request
    if ctx.invoked_subcommand is not None:
        return

    # No subcommand: run interactive setup
    _interactive_config()


def _require_project_root() -> Path:
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)
    return project_root


def _interactive_config() -> None:
    """Interactive guided configuration setup."""
    project_root = _require_project_root()

    # Step 1: What to configure
    config_options = [
        SelectOption(
            "issue-provider",
            "Issue Provider",
            "Configure Azure DevOps or GitHub Issues integration",
        ),
    ]

    config_choice = select(
        config_options,
        message="What would you like to configure?",
    )

    if config_choice == "issue-provider":
        _interactive_issue_provider_setup(project_root)


def _interactive_issue_provider_setup(project_root: Path) -> None:
    """Interactive issue provider configuration."""
    print_info("\n[bold]Issue Provider Setup[/bold]")
    print_info("Configure integration with your issue tracking system\n")

    # Step 1: Choose provider
    provider_options = [
        SelectOption("ado", "Azure DevOps", "Microsoft Azure DevOps Boards"),
        SelectOption("github", "GitHub Issues", "GitHub Issues and Pull Requests"),
    ]

    provider_key = select(
        provider_options,
        message="Which issue provider do you use?",
    )

    provider_label = ISSUE_PROVIDER_DISPLAY_NAMES.get(provider_key, provider_key)
    print_info(f"\nConfiguring [cyan]{provider_label}[/cyan]...")
    print_info("[dim]Press Enter to accept defaults shown in brackets[/dim]\n")

    config_service = ConfigService(project_root)
    settings: dict[str, str | None] = {}
    defaults = ISSUE_PROVIDER_DEFAULTS.get(provider_key, {})

    # Step 2: Collect settings based on provider
    if provider_key == "ado":
        # Azure DevOps settings
        default_org = defaults.get("organization")
        settings["organization"] = prompt(
            "Azure DevOps organization name",
            default=default_org,
            validator=lambda x: len(x.strip()) > 0,
            error_message="Organization name cannot be empty",
        )

        settings["project"] = prompt(
            "Azure DevOps project name",
            validator=lambda x: len(x.strip()) > 0,
            error_message="Project name cannot be empty",
        )

        # Set optional fields to None (not collected in interactive mode)
        settings["team"] = None
        settings["area_path"] = None

        # Use standard PAT environment variable
        pat_env_name = "AZURE_DEVOPS_PAT"
        settings["pat_env"] = pat_env_name

        # Check if PAT is already set
        pat_value = os.environ.get(pat_env_name, "")
        if pat_value:
            print_success(f"✓ Environment variable '{pat_env_name}' is already set")
            print_info("Using existing value from environment.\n")
        else:
            print_info(f"\n[yellow]⚠[/yellow] Environment variable '{pat_env_name}' is not set")
            print_info("You can provide your Azure DevOps Personal Access Token now,")
            print_info("and we'll save it to .env (which is automatically gitignored).\n")

            store_in_env = prompt(
                "Save token to .env file? (y/n):",
                validator=lambda x: x.lower() in ["y", "n", "yes", "no"],
                error_message="Please enter y or n",
            ).lower()

            if store_in_env in ["y", "yes"]:
                pat_value = password_prompt("Enter your Azure DevOps PAT (input hidden)")
                if pat_value.strip():
                    update_env_file(project_root, pat_env_name, pat_value)
                    ensure_gitignore_has_env(project_root)
                    # Reload .env so validation can see the new value
                    load_dotenv(project_root / ".env", override=True)
                    print_success("✓ Saved to .env and added .env to .gitignore\n")
                else:
                    print_info("Skipped (empty value). Set it manually later.\n")
            else:
                print_info(f"Skipped. Set it manually: export {pat_env_name}=your-pat\n")

    else:  # github
        # GitHub settings
        default_owner = defaults.get("owner")
        settings["owner"] = prompt(
            "GitHub repository owner",
            default=default_owner,
            validator=lambda x: len(x.strip()) > 0,
            error_message="Owner cannot be empty",
        )

        settings["repo"] = prompt(
            "GitHub repository name",
            validator=lambda x: len(x.strip()) > 0,
            error_message="Repository name cannot be empty",
        )

        # Use standard token environment variable
        token_env_name = "GITHUB_TOKEN"
        settings["token_env"] = token_env_name

        # Check if token is already set
        token_value = os.environ.get(token_env_name, "")
        if token_value:
            print_success(f"✓ Environment variable '{token_env_name}' is already set")
            print_info("Using existing value from environment.\n")
        else:
            print_info(f"\n[yellow]⚠[/yellow] Environment variable '{token_env_name}' is not set")
            print_info("You can provide your GitHub Personal Access Token now,")
            print_info("and we'll save it to .env (which is automatically gitignored).\n")

            store_in_env = prompt(
                "Save token to .env file? (y/n):",
                validator=lambda x: x.lower() in ["y", "n", "yes", "no"],
                error_message="Please enter y or n",
            ).lower()

            if store_in_env in ["y", "yes"]:
                token_value = password_prompt("Enter your GitHub token (input hidden)")
                if token_value.strip():
                    update_env_file(project_root, token_env_name, token_value)
                    ensure_gitignore_has_env(project_root)
                    # Reload .env so validation can see the new value
                    load_dotenv(project_root / ".env", override=True)
                    print_success("✓ Saved to .env and added .env to .gitignore\n")
                else:
                    print_info("Skipped (empty value). Set it manually later.\n")
            else:
                print_info(f"Skipped. Set it manually: export {token_env_name}=your-token\n")

    # Save configuration
    config_service.update_issue_provider(provider_key, **settings)
    print_success(f"\n✓ Configured issue provider: {provider_label}")

    # Run validation
    print_info("\nValidating configuration...")
    service = PlanService(project_root)
    issues = service.validate_provider(provider_key)

    if issues:
        print_info("\n[yellow]Configuration validation found issues:[/yellow]")
        for issue in issues:
            print_info(f"  • {issue}")
        print_info("\nPlease fix these issues before using issue commands.")
    else:
        print_success("✓ Configuration is valid and ready to use!\n")


@issue_provider_app.command("set")
def set_issue_provider(
    provider: str = typer.Option(..., "--provider", "-p", help="Issue provider key (ado, github)"),
    organization: str | None = typer.Option(None, help="Azure DevOps organization name"),
    project: str | None = typer.Option(None, help="Azure DevOps project name"),
    team: str | None = typer.Option(None, help="Default team name (Azure DevOps)"),
    area_path: str | None = typer.Option(None, help="Default area path (Azure DevOps)"),
    pat_env: str | None = typer.Option(
        None, help="Environment variable containing Azure DevOps PAT (ado)"
    ),
    owner: str | None = typer.Option(None, help="GitHub repository owner (github)"),
    repo: str | None = typer.Option(None, help="GitHub repository name (github)"),
    token_env: str | None = typer.Option(
        None, help="Environment variable containing GitHub token (github)"
    ),
    default_branch: str | None = typer.Option(
        None, help="Default branch used when creating issue branches"
    ),
) -> None:
    """Configure the issue provider used by AI agent commands."""
    provider_key = provider.lower().strip()
    if provider_key not in SUPPORTED_ISSUE_PROVIDERS:
        print_error(ERROR_MESSAGES["issue_provider_invalid"].format(provider=provider_key))
        raise typer.Exit(code=1)

    project_root = _require_project_root()
    config_service = ConfigService(project_root)

    settings: dict[str, str | None]
    if provider_key == "ado":
        settings = {
            "organization": organization,
            "project": project,
            "team": team,
            "area_path": area_path,
            "pat_env": pat_env,
            "default_branch": default_branch,
        }
    else:  # github
        settings = {
            "owner": owner,
            "repo": repo,
            "token_env": token_env,
            "default_branch": default_branch,
        }

    config_service.update_issue_provider(provider_key, **settings)
    provider_label = ISSUE_PROVIDER_DISPLAY_NAMES.get(provider_key, provider_key)
    print_success(f"Configured issue provider: {provider_label}")


@issue_provider_app.command("show")
def show_issue_provider() -> None:
    """Show current issue provider configuration."""
    project_root = _require_project_root()
    config_service = ConfigService(project_root)
    issue_config = config_service.get_issue_config()
    provider_key = issue_config.provider or "none"
    provider_label = ISSUE_PROVIDER_DISPLAY_NAMES.get(provider_key, provider_key)

    data = issue_config.model_dump(mode="json", exclude_none=True)
    panel_content = f"[bold]Active Provider:[/bold] {provider_label}\n\n"
    panel_content += json.dumps(data, indent=2)
    print_panel(panel_content, title="Issue Provider Configuration", style="cyan")


@issue_provider_app.command("check")
def check_issue_provider(provider: str | None = typer.Option(None, "--provider", "-p")) -> None:
    """Validate provider configuration and prerequisite secrets."""
    project_root = _require_project_root()
    service = PlanService(project_root)
    issues = service.validate_provider(provider)
    if issues:
        print_error("Issue provider configuration is incomplete:")
        for issue in issues:
            print_info(f"- {issue}")
        print_info(INFO_MESSAGES["issue_config_prompt"])
        raise typer.Exit(code=1)

    resolved = provider or service.resolve_provider_key()
    provider_label = ISSUE_PROVIDER_DISPLAY_NAMES.get(resolved, resolved)
    print_success(f"Issue provider '{provider_label}' is configured")
