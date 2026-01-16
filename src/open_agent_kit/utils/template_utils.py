"""Template utilities for Jinja2 processing."""

import re

JINJA2_PATTERN = re.compile(r"\{\{|\{%")


def has_jinja2_syntax(content: str) -> bool:
    """Check if content contains Jinja2 template syntax.

    Args:
        content: String content to check

    Returns:
        True if Jinja2 syntax is detected
    """
    return bool(JINJA2_PATTERN.search(content))
