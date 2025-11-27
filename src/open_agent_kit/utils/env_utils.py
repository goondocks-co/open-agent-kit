"""Utilities for managing .env files."""

from __future__ import annotations

from pathlib import Path


def update_env_file(project_root: Path, key: str, value: str) -> None:
    """Update or create .env file with a key-value pair.

    Args:
        project_root: Project root directory
        key: Environment variable name
        value: Environment variable value
    """
    env_path = project_root / ".env"

    # Read existing content
    existing_lines: list[str] = []
    key_found = False

    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                # Check if this line sets our key
                if stripped.startswith(f"{key}="):
                    # Replace with new value
                    existing_lines.append(f"{key}={value}\n")
                    key_found = True
                else:
                    existing_lines.append(line)

    # If key wasn't found, append it
    if not key_found:
        # Ensure file ends with newline before adding
        if existing_lines and not existing_lines[-1].endswith("\n"):
            existing_lines.append("\n")
        existing_lines.append(f"{key}={value}\n")

    # Write back
    with env_path.open("w", encoding="utf-8") as f:
        f.writelines(existing_lines)


def ensure_gitignore_has_env(project_root: Path) -> None:
    """Ensure .gitignore includes .env file.

    Args:
        project_root: Project root directory
    """
    gitignore_path = project_root / ".gitignore"

    # Read existing content
    existing_lines: list[str] = []
    has_env = False

    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                existing_lines.append(line)
                if line.strip() == ".env":
                    has_env = True

    # Add .env if not present
    if not has_env:
        # Add header comment if file is new
        if not existing_lines:
            existing_lines.append("# Environment variables (contains secrets)\n")
        elif existing_lines and not existing_lines[-1].endswith("\n"):
            existing_lines.append("\n")

        existing_lines.append(".env\n")

        # Write back
        with gitignore_path.open("w", encoding="utf-8") as f:
            f.writelines(existing_lines)


def ensure_gitignore_has_issue_context(project_root: Path) -> None:
    """Ensure .gitignore includes oak/issue/**/context.json pattern.

    This ensures the raw JSON API responses from issue providers (ADO/GitHub)
    are not committed to git, as they're local debugging files. The
    context-summary.md files remain tracked as they're the agent-friendly format.

    Args:
        project_root: Project root directory
    """
    gitignore_path = project_root / ".gitignore"

    # Read existing content
    existing_lines: list[str] = []
    has_issue_context = False

    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                existing_lines.append(line)
                if line.strip() == "oak/issue/**/context.json":
                    has_issue_context = True

    # Add pattern if not present
    if not has_issue_context:
        # Add header comment if file is new
        if not existing_lines:
            existing_lines.append("# open-agent-kit issue context (generated files)\n")
        elif existing_lines and not existing_lines[-1].endswith("\n"):
            existing_lines.append("\n")

        # Add comment explaining the pattern
        existing_lines.append("\n# open-agent-kit: Issue raw JSON (local debugging only)\n")
        existing_lines.append("oak/issue/**/context.json\n")

        # Write back
        with gitignore_path.open("w", encoding="utf-8") as f:
            f.writelines(existing_lines)
