"""open-agent-kit: CLI tool for engineering productivity."""

import tomllib
from pathlib import Path

try:
    # First, try to read from pyproject.toml (for development mode)
    # This ensures we always get the latest version during development
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    __version__ = data["project"]["version"]
except Exception:
    # Fallback: Get version from installed package metadata
    # This is used when installed via pip/uv in non-editable mode
    try:
        from importlib.metadata import version

        __version__ = version("open_agent_kit")
    except Exception:
        # Last resort fallback
        __version__ = "0.0.0-dev"
