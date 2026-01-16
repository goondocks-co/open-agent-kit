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


def add_gitignore_entries(
    project_root: Path,
    entries: list[str],
    section_comment: str | None = None,
) -> list[str]:
    """Add entries to .gitignore if not already present.

    This is a generic function for features to add gitignore patterns
    declaratively. Patterns are added in a single section with an
    optional comment header.

    Args:
        project_root: Project root directory
        entries: List of gitignore patterns to add (e.g., [".oak/ci/", "*.log"])
        section_comment: Optional comment to add before entries (e.g., "Feature: CI data")

    Returns:
        List of entries that were actually added (not already present)
    """
    gitignore_path = project_root / ".gitignore"

    # Read existing content
    existing_lines: list[str] = []
    existing_patterns: set[str] = set()

    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                existing_lines.append(line)
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    existing_patterns.add(stripped)

    # Find entries that need to be added
    entries_to_add = [e for e in entries if e.strip() not in existing_patterns]
    if not entries_to_add:
        return []

    # Ensure file ends with newline
    if existing_lines and not existing_lines[-1].endswith("\n"):
        existing_lines.append("\n")

    # Add section comment if provided
    if section_comment:
        existing_lines.append(f"\n# {section_comment}\n")
    elif existing_lines:
        existing_lines.append("\n")

    # Add new entries
    for entry in entries_to_add:
        existing_lines.append(f"{entry.strip()}\n")

    # Write back
    with gitignore_path.open("w", encoding="utf-8") as f:
        f.writelines(existing_lines)

    return entries_to_add


def remove_gitignore_entries(
    project_root: Path,
    entries: list[str],
) -> list[str]:
    """Remove entries from .gitignore.

    This is a generic function for features to remove gitignore patterns
    when the feature is disabled. Also removes associated comment lines
    if they immediately precede the removed entry.

    Args:
        project_root: Project root directory
        entries: List of gitignore patterns to remove

    Returns:
        List of entries that were actually removed
    """
    gitignore_path = project_root / ".gitignore"

    if not gitignore_path.exists():
        return []

    # Normalize entries for comparison
    entries_to_remove = {e.strip() for e in entries}

    # Read existing content
    with gitignore_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    # Build new content, removing specified entries
    new_lines: list[str] = []
    removed: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this line should be removed
        if stripped in entries_to_remove:
            removed.append(stripped)
            # Also remove preceding comment line if it looks related
            if new_lines and new_lines[-1].strip().startswith("#"):
                # Check if comment is on its own line (feature-specific)
                # Don't remove if it's a shared section header
                prev_comment = new_lines[-1].strip()
                # Remove preceding comment that looks feature-specific
                if "oak" in prev_comment.lower() or len(prev_comment) < 60:
                    new_lines.pop()
            i += 1
            continue

        new_lines.append(line)
        i += 1

    # Clean up excessive blank lines at end
    while len(new_lines) > 1 and new_lines[-1].strip() == "" and new_lines[-2].strip() == "":
        new_lines.pop()

    if not removed:
        return []

    # Write back
    with gitignore_path.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return removed


def ensure_gitignore_has_ci_data(project_root: Path) -> None:
    """Ensure .gitignore includes .oak/ci/ directory.

    DEPRECATED: This function is kept for backwards compatibility.
    Features should use the manifest 'gitignore' field instead.

    Args:
        project_root: Project root directory
    """
    add_gitignore_entries(
        project_root,
        entries=[".oak/ci/"],
        section_comment="open-agent-kit: Codebase Intelligence data (regenerated locally)",
    )
