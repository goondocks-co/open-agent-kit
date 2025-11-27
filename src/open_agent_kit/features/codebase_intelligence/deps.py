"""Dependency management for Codebase Intelligence feature.

This module handles automatic installation of CI dependencies when the feature
is enabled, keeping the base oak install lightweight.

The installation approach directly installs individual packages rather than
relying on extras syntax, ensuring it works for all install methods:
- PyPI installs
- Git URL installs
- Local editable installs
"""

import importlib.util
import logging
import subprocess
import sys
from typing import Final

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger(__name__)
console = Console()

# Map of import names to package names for pip install
# Format: {import_name: pip_package_name}
CI_REQUIRED_PACKAGES: Final[dict[str, str]] = {
    "uvicorn": "uvicorn>=0.27.0",
    "fastapi": "fastapi>=0.109.0",
    "chromadb": "chromadb>=0.5.0",
    "tree_sitter": "tree-sitter>=0.23.0",
    "watchdog": "watchdog>=4.0.0",
    "aiofiles": "aiofiles>=23.0.0",
}

# Tree-sitter language parsers (import name -> pip package)
CI_PARSER_PACKAGES: Final[dict[str, str]] = {
    "tree_sitter_python": "tree-sitter-python>=0.23.0",
    "tree_sitter_javascript": "tree-sitter-javascript>=0.23.0",
    "tree_sitter_typescript": "tree-sitter-typescript>=0.23.0",
    "tree_sitter_java": "tree-sitter-java>=0.23.0",
    "tree_sitter_c_sharp": "tree-sitter-c-sharp>=0.23.0",
    "tree_sitter_go": "tree-sitter-go>=0.23.0",
    "tree_sitter_rust": "tree-sitter-rust>=0.23.0",
}


def check_ci_dependencies() -> list[str]:
    """Check which CI dependencies are missing.

    Returns:
        List of missing package import names (core packages only, not parsers).
    """
    missing = []
    for import_name in CI_REQUIRED_PACKAGES:
        if importlib.util.find_spec(import_name) is None:
            missing.append(import_name)
    return missing


def get_packages_to_install() -> list[str]:
    """Get list of pip package specs to install.

    Returns all CI packages (core + parsers) as pip-installable strings.

    Returns:
        List of package specs like ["uvicorn>=0.27.0", "fastapi>=0.109.0", ...].
    """
    packages = list(CI_REQUIRED_PACKAGES.values())
    packages.extend(CI_PARSER_PACKAGES.values())
    return packages


def install_ci_dependencies(quiet: bool = False, show_packages: bool = True) -> bool:
    """Install CI dependencies into the current Python environment.

    Directly installs individual packages using uv pip, which works for all
    installation methods (PyPI, git URL, local editable).

    Args:
        quiet: Suppress installation output (no progress spinner or package list).
        show_packages: Show which packages will be installed before starting.

    Returns:
        True if installation succeeded, False otherwise.
    """
    packages = get_packages_to_install()
    logger.info(f"Installing {len(packages)} CI packages...")

    # Show packages being installed (unless quiet)
    if show_packages and not quiet:
        console.print(f"  Installing {len(packages)} CI packages...", style="dim")
        # Highlight large packages
        large_packages = ["chromadb"]
        for pkg in large_packages:
            if any(pkg in p for p in packages):
                console.print(f"    • {pkg} (large package, may take a moment)", style="yellow")

    # Build the install command - use uv directly with --python to target
    # the current interpreter's environment
    cmd = [
        "uv",
        "pip",
        "install",
        "--python",
        sys.executable,
        *packages,
    ]

    if quiet:
        cmd.append("--quiet")

    try:
        # Run with progress spinner for user feedback
        if not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
                console=console,
            ) as progress:
                progress.add_task("Installing dependencies...", total=None)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode == 0:
            logger.info("CI dependencies installed successfully")
            return True
        else:
            _surface_installation_error(result.stderr, result.stdout, quiet)
            return False

    except FileNotFoundError:
        logger.error("uv command not found - ensure uv is installed and in PATH")
        if not quiet:
            console.print("  [red]Error:[/red] uv command not found", style="red")
            console.print("    Install uv: https://docs.astral.sh/uv/", style="dim")
        return False


def _surface_installation_error(stderr: str, stdout: str, quiet: bool) -> None:
    """Surface installation errors in a user-friendly way.

    Args:
        stderr: Standard error output from the installation command.
        stdout: Standard output from the installation command.
        quiet: If True, only log the error without console output.
    """
    logger.error(f"uv pip install failed: {stderr or stdout}")

    if quiet:
        return

    console.print("  [red]Installation encountered issues:[/red]")

    # Show last 10 error lines
    error_output = stderr or stdout
    error_lines = [
        line for line in error_output.split("\n") if line.strip() and "error" in line.lower()
    ]
    if error_lines:
        for line in error_lines[-10:]:
            console.print(f"    {line}", style="red dim")
    else:
        # Show last few lines if no explicit errors found
        all_lines = [line for line in error_output.split("\n") if line.strip()]
        for line in all_lines[-5:]:
            console.print(f"    {line}", style="dim")

    # Suggest manual installation
    console.print("")
    console.print("  Try manual installation:", style="yellow")
    console.print("    uv pip install chromadb tree-sitter ...", style="dim")


def ensure_ci_dependencies(auto_install: bool = True) -> bool:
    """Ensure CI dependencies are available, optionally installing them.

    Args:
        auto_install: If True, automatically install missing dependencies.

    Returns:
        True if all dependencies are available, False otherwise.

    Raises:
        RuntimeError: If dependencies are missing and auto_install is False.
    """
    missing = check_ci_dependencies()

    if not missing:
        logger.debug("All CI dependencies are available")
        return True

    logger.info(f"Missing CI dependencies: {', '.join(missing)}")

    if not auto_install:
        raise RuntimeError(
            f"Codebase Intelligence requires additional dependencies: {', '.join(missing)}\n\n"
            "Run 'oak init' to auto-install dependencies."
        )

    # Try to install
    if install_ci_dependencies():
        # Verify installation worked
        still_missing = check_ci_dependencies()
        if still_missing:
            logger.warning(
                f"Some dependencies still missing after install: {', '.join(still_missing)}"
            )
            return False
        return True

    return False
