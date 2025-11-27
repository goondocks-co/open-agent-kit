"""Input validation utilities for open-agent-kit."""

import re
from pathlib import Path

from open_agent_kit.constants import (
    REQUIRED_RFC_SECTIONS,
    RFC_FILENAME_PATTERN,
    RFC_NUMBER_PATTERN,
)
from open_agent_kit.models.enums import RFCStatus


def validate_rfc_number(rfc_number: str) -> bool:
    """Validate RFC number format.

    Args:
        rfc_number: RFC number to validate

    Returns:
        True if valid, False otherwise

    Valid formats:
        - 001, 002, 0001 (sequential)
        - 2024-001, 2024-002 (year-based)
    """
    pattern = re.compile(RFC_NUMBER_PATTERN)
    return bool(pattern.match(rfc_number))


def validate_rfc_filename(filename: str) -> bool:
    """Validate RFC filename format.

    Args:
        filename: Filename to validate

    Returns:
        True if valid, False otherwise

    Valid format: RFC-###-Title.md
    """
    pattern = re.compile(RFC_FILENAME_PATTERN)
    return bool(pattern.match(filename))


def parse_rfc_number(rfc_input: str) -> str | None:
    """Parse and normalize RFC number from various input formats.

    Args:
        rfc_input: RFC number in various formats (001, RFC-001, rfc-001, etc.)

    Returns:
        Normalized RFC number or None if invalid

    Examples:
        >>> parse_rfc_number("001")
        "001"
        >>> parse_rfc_number("RFC-001")
        "001"
        >>> parse_rfc_number("2024-001")
        "2024-001"
    """
    # Remove common prefixes
    rfc_input = rfc_input.strip()
    rfc_input = re.sub(r"^(?:RFC|rfc)[-_\s]*", "", rfc_input)

    # Validate
    if validate_rfc_number(rfc_input):
        return rfc_input

    return None


def parse_rfc_filename(filename: str) -> tuple[str, str] | None:
    """Parse RFC filename to extract number and title.

    Args:
        filename: RFC filename

    Returns:
        Tuple of (number, title) or None if invalid

    Example:
        >>> parse_rfc_filename("RFC-001-Add-User-Auth.md")
        ("001", "Add-User-Auth")
    """
    pattern = re.compile(RFC_FILENAME_PATTERN)
    match = pattern.match(filename)

    if match:
        number = match.group(1)
        title = match.group(2)
        return (number, title)

    return None


def validate_rfc_status(status: str) -> bool:
    """Validate RFC status value.

    Args:
        status: Status to validate

    Returns:
        True if valid, False otherwise
    """
    return status.lower() in RFCStatus.values()


def validate_agent_type(agent: str) -> bool:
    """Validate agent type.

    Args:
        agent: Agent type to validate

    Returns:
        True if valid, False otherwise
    """
    from open_agent_kit.services.agent_service import AgentService

    agent_service = AgentService()
    available_agents = agent_service.list_available_agents()
    return agent.lower() in available_agents


def validate_file_path(path: str) -> bool:
    """Validate file path exists and is a file.

    Args:
        path: Path to validate

    Returns:
        True if valid file path, False otherwise
    """
    try:
        p = Path(path)
        return p.exists() and p.is_file()
    except Exception:
        return False


def validate_dir_path(path: str) -> bool:
    """Validate directory path exists and is a directory.

    Args:
        path: Path to validate

    Returns:
        True if valid directory path, False otherwise
    """
    try:
        p = Path(path)
        return p.exists() and p.is_dir()
    except Exception:
        return False


def validate_rfc_content(content: str, strict: bool = False) -> tuple[bool, list[str]]:
    """Validate RFC content has required sections.

    Args:
        content: RFC markdown content
        strict: Whether to enforce strict validation

    Returns:
        Tuple of (is_valid, list_of_missing_sections)
    """
    missing_sections = []

    for section in REQUIRED_RFC_SECTIONS:
        # Check if section heading exists (with some flexibility)
        section_pattern = section.replace("#", r"\s*#").strip()
        if not re.search(rf"^{section_pattern}\s*$", content, re.MULTILINE):
            missing_sections.append(section)

    is_valid = len(missing_sections) == 0 if strict else len(missing_sections) < 3

    return (is_valid, missing_sections)


def validate_yaml_config(data: dict) -> tuple[bool, list[str]]:
    """Validate YAML configuration structure.

    Args:
        data: Parsed YAML configuration

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check version
    if "version" not in data:
        errors.append("Missing 'version' field")

    # Check agent
    if "agent" in data and data["agent"]:
        if not validate_agent_type(str(data["agent"])):
            errors.append(f"Invalid agent type: {data['agent']}")

    # Check RFC config
    if "rfc" in data:
        rfc_config = data["rfc"]
        if not isinstance(rfc_config, dict):
            errors.append("'rfc' must be a dictionary")
        else:
            if "directory" in rfc_config and not isinstance(rfc_config["directory"], str):
                errors.append("'rfc.directory' must be a string")

            if "template" in rfc_config and not isinstance(rfc_config["template"], str):
                errors.append("'rfc.template' must be a string")

            if "auto_number" in rfc_config and not isinstance(rfc_config["auto_number"], bool):
                errors.append("'rfc.auto_number' must be a boolean")

    return (len(errors) == 0, errors)


def validate_markdown_syntax(content: str) -> tuple[bool, list[str]]:
    """Basic markdown syntax validation.

    Args:
        content: Markdown content to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    lines = content.split("\n")

    # Check for consistent header levels
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    previous_level = 0

    for i, line in enumerate(lines, 1):
        match = header_pattern.match(line)
        if match:
            current_level = len(match.group(1))

            # Check if level increment is valid
            if previous_level > 0 and current_level > previous_level + 1:
                issues.append(
                    f"Line {i}: Header level skipped from {previous_level} to {current_level}"
                )

            previous_level = current_level

    # Check for trailing spaces
    for i, line in enumerate(lines, 1):
        if line.endswith(" ") and line.strip():
            issues.append(f"Line {i}: Trailing whitespace")

    # Check for empty links
    empty_link_pattern = re.compile(r"\[([^\]]+)\]\(\s*\)")
    for i, line in enumerate(lines, 1):
        if empty_link_pattern.search(line):
            issues.append(f"Line {i}: Empty link found")

    # Check for proper code block closure
    code_block_open = False
    for _i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            code_block_open = not code_block_open

    if code_block_open:
        issues.append("Unclosed code block")

    return (len(issues) == 0, issues)


def sanitize_title(title: str) -> str:
    """Sanitize title for use in filenames.

    Args:
        title: Original title

    Returns:
        Sanitized title safe for filenames
    """
    # Remove special characters
    title = re.sub(r'[<>:"/\\|?*]', "", title)

    # Replace spaces with hyphens
    title = re.sub(r"\s+", "-", title)

    # Remove multiple consecutive hyphens
    title = re.sub(r"-+", "-", title)

    # Remove leading/trailing hyphens
    title = title.strip("-")

    return title


def validate_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(pattern.match(email))


def validate_url(url: str) -> bool:
    """Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid URL format, False otherwise
    """
    pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url))


def validate_version(version: str) -> bool:
    """Validate semantic version format.

    Args:
        version: Version string to validate

    Returns:
        True if valid semver format, False otherwise

    Examples:
        >>> validate_version("1.0.0")
        True
        >>> validate_version("1.0")
        False
    """
    pattern = re.compile(
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )
    return bool(pattern.match(version))
