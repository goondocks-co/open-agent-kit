"""CI indexing commands: index, install-parsers, languages."""

import subprocess
import sys
from pathlib import Path

import typer

from open_agent_kit.constants import SKIP_DIRECTORIES
from open_agent_kit.features.codebase_intelligence.constants import HTTP_TIMEOUT_LONG
from open_agent_kit.utils import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    ci_app,
    console,
    get_daemon_manager,
    logger,
)


@ci_app.command("index")
def ci_index(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force full reindex (clear existing data first)"
    ),
) -> None:
    """Trigger codebase indexing.

    Tells the daemon to index (or re-index) the project.
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)

    if not manager.is_running():
        print_error("Daemon is not running. Start it first with 'oak ci start'.")
        raise typer.Exit(code=1)

    print_info("Triggering codebase indexing...")

    try:
        import httpx

        with httpx.Client(timeout=HTTP_TIMEOUT_LONG) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/index/build",
                json={"full_rebuild": force},
            )

            if response.status_code == 200:
                result = response.json()
                print_success(
                    f"Indexing complete: {result.get('files_processed', 0)} files processed"
                )
                if result.get("chunks_indexed"):
                    print_info(f"  Chunks indexed: {result['chunks_indexed']}")
            else:
                print_error(f"Indexing failed: {response.text}")
                raise typer.Exit(code=1)

    except httpx.TimeoutException:
        print_warning("Indexing request timed out. The daemon may still be processing.")
        print_info("Check status with 'oak ci status'.")
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        logger.error(f"Failed to trigger indexing: {e}")
        print_error(f"Failed to trigger indexing: {e}")
        raise typer.Exit(code=1)


@ci_app.command("install-parsers")
def ci_install_parsers(
    all_languages: bool = typer.Option(
        False, "--all", "-a", help="Install parsers for all supported languages"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would be installed without installing"
    ),
) -> None:
    """Install tree-sitter language parsers for better code understanding.

    By default, scans your project and installs only the parsers needed
    for languages detected in your codebase.

    Examples:
        oak ci install-parsers           # Auto-detect and install
        oak ci install-parsers --all     # Install all supported parsers
        oak ci install-parsers --dry-run # Preview what would be installed
    """
    from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
        LANGUAGE_MAP,
        TREE_SITTER_PACKAGES,
        CodeChunker,
    )

    project_root = Path.cwd()

    # Get currently installed parsers
    chunker = CodeChunker()
    installed = chunker._available_languages

    if all_languages:
        # Install all supported parsers
        languages_to_install = set(TREE_SITTER_PACKAGES.keys()) - installed
        print_info("Installing all supported language parsers...")
    else:
        # Detect languages in project
        print_info("Scanning project for languages...")
        detected_languages: set[str] = set()

        for filepath in project_root.rglob("*"):
            if not filepath.is_file():
                continue
            # Skip common non-code directories
            path_str = str(filepath)
            if any(skip in path_str for skip in SKIP_DIRECTORIES):
                continue

            suffix = filepath.suffix.lower()
            if suffix in LANGUAGE_MAP:
                lang = LANGUAGE_MAP[suffix]
                if lang in TREE_SITTER_PACKAGES:
                    detected_languages.add(lang)

        if not detected_languages:
            print_info("No supported languages detected in project.")
            return

        print_info(f"Detected languages: {', '.join(sorted(detected_languages))}")
        languages_to_install = detected_languages - installed

    if not languages_to_install:
        print_success("All needed parsers are already installed!")
        return

    # Map languages to pip packages
    packages_to_install = []
    for lang in languages_to_install:
        pkg = TREE_SITTER_PACKAGES.get(lang)
        if pkg:
            # Convert module name to pip package name (tree_sitter_python -> tree-sitter-python)
            pip_pkg = pkg.replace("_", "-")
            packages_to_install.append(pip_pkg)

    if dry_run:
        print_header("Would install:")
        for pkg in sorted(packages_to_install):
            console.print(f"  {pkg}")
        return

    print_info(f"Installing {len(packages_to_install)} parser(s)...")

    # Try uv first, fall back to pip
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        install_cmd = ["uv", "pip", "install"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        install_cmd = [sys.executable, "-m", "pip", "install"]

    try:
        cmd = install_cmd + packages_to_install
        console.print(f"  Running: {' '.join(cmd)}", style="dim")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print_success(f"Installed {len(packages_to_install)} parser(s) successfully!")

        # Show what was installed
        for pkg in sorted(packages_to_install):
            console.print(f"  [green]✓[/green] {pkg}")

        console.print()
        print_info("Restart the daemon to use new parsers:")
        print_info("  oak ci restart")

    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install parsers: {e.stderr}")
        raise typer.Exit(code=1)


@ci_app.command("languages")
def ci_languages() -> None:
    """Show supported programming languages and AST parsing status.

    Displays which languages have tree-sitter parsers installed for
    better semantic chunking vs line-based fallback.
    """
    from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
        LANGUAGE_MAP,
        CodeChunker,
    )

    print_header("Supported Languages")

    chunker = CodeChunker()
    available_ast = chunker._available_languages

    # Group by AST support
    ast_supported = []
    line_based = []

    for ext, lang in sorted(LANGUAGE_MAP.items(), key=lambda x: x[1]):
        if lang in available_ast:
            ast_supported.append((ext, lang))
        else:
            line_based.append((ext, lang))

    if ast_supported:
        print_success("AST-based chunking (semantic):")
        current_lang = None
        for ext, lang in ast_supported:
            if lang != current_lang:
                if current_lang:
                    console.print()
                current_lang = lang
                console.print(f"  {lang}", style="bold")
            console.print(f"    {ext}", style="dim")

    console.print()

    if line_based:
        print_info("Line-based chunking (no AST parser installed):")
        current_lang = None
        for _ext, lang in line_based:
            if lang != current_lang:
                current_lang = lang
                console.print(f"  {lang}", style="dim")

    console.print()
    print_info("Install tree-sitter parsers for better code understanding:")
    print_info("  pip install tree-sitter-python tree-sitter-javascript tree-sitter-c-sharp")
