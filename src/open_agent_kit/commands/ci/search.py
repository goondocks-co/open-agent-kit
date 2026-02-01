"""CI AI-facing commands: search, remember, context."""

import json
from pathlib import Path
from typing import Any

import typer

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
)


@ci_app.command("search")
def ci_search(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return"),
    search_type: str = typer.Option(
        "all", "--type", "-t", help="Search type: 'all', 'code', 'memory', or 'plans'"
    ),
    format_output: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
    no_weight: bool = typer.Option(
        False,
        "--no-weight",
        "-w",
        help="Disable doc_type weighting (useful for translation searches)",
    ),
) -> None:
    """Search the codebase, memories, and plans using semantic similarity.

    Find relevant code implementations, past decisions, gotchas, learnings, and plans.
    Results are ranked by relevance score. By default, i18n/config files are
    down-weighted; use --no-weight to disable this for translation searches.

    Examples:
        oak ci search "authentication middleware"
        oak ci search "error handling patterns" --type code
        oak ci search "database connection" -n 5 -f text
        oak ci search "translation strings" --no-weight
        oak ci search "design goals" --type plans
    """
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/search",
                json={
                    "query": query,
                    "search_type": search_type,
                    "limit": min(max(1, limit), 50),
                    "apply_doc_type_weights": not no_weight,
                },
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                code_results = result.get("code", [])
                memory_results = result.get("memory", [])
                plan_results = result.get("plans", [])

                if code_results:
                    print_header(f"Code Results ({len(code_results)})")
                    for item in code_results:
                        score = item.get("score", 0)
                        filepath = item.get("file_path", "?")
                        chunk_type = item.get("chunk_type", "?")
                        name = item.get("name", "")
                        lines = item.get("start_line", "?")
                        console.print(f"\n[bold]{filepath}:{lines}[/bold] ({chunk_type}: {name})")
                        console.print(f"  Score: {score:.1%}", style="dim")
                        preview = item.get("content", "")[:200]
                        if preview:
                            console.print(f"  {preview}...", style="dim")

                if memory_results:
                    console.print()
                    print_header(f"Memory Results ({len(memory_results)})")
                    for item in memory_results:
                        score = item.get("score", 0)
                        memory_type = item.get("memory_type", "?")
                        observation = item.get("observation", "")
                        console.print(f"\n[bold][{memory_type}][/bold] {observation[:100]}")
                        console.print(f"  Score: {score:.1%}", style="dim")

                if plan_results:
                    console.print()
                    print_header(f"Plan Results ({len(plan_results)})")
                    for item in plan_results:
                        confidence = item.get("confidence", "medium")
                        title = item.get("title", "Untitled Plan")
                        preview = item.get("preview", "")[:100]
                        # Color code confidence levels
                        confidence_style = {
                            "high": "green",
                            "medium": "yellow",
                            "low": "red",
                        }.get(confidence, "dim")
                        console.print(
                            f"\n[{confidence_style}]{confidence.upper()}[/{confidence_style}] "
                            f"[bold]{title}[/bold]"
                        )
                        if preview:
                            console.print(f"  {preview}...", style="dim")

                if not code_results and not memory_results and not plan_results:
                    print_warning("No results found.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Search failed: {e}")
        raise typer.Exit(code=1)


@ci_app.command("remember")
def ci_remember(
    observation: str = typer.Argument(..., help="The observation or learning to store"),
    memory_type: str = typer.Option(
        "discovery",
        "--type",
        "-t",
        help="Type: 'gotcha', 'bug_fix', 'decision', 'discovery', 'trade_off'",
    ),
    context: str = typer.Option(
        None, "--context", "-c", help="Related file path or additional context"
    ),
    format_output: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """Store an observation, decision, or learning for future sessions.

    Use this when you discover something important about the codebase that
    would help in future work. Memories persist across sessions.

    Memory Types:
        gotcha     - Non-obvious behavior or quirk that could trip someone up
        bug_fix    - Solution to a bug, including root cause
        decision   - Architectural or design decision with rationale
        discovery  - General insight or learning about the codebase
        trade_off  - Trade-off that was made and why

    Examples:
        oak ci remember "The auth module requires Redis for sessions" -t discovery
        oak ci remember "Always call cleanup() before disconnect" -t gotcha -c src/db.py
        oak ci remember "Chose SQLite over PostgreSQL for simplicity" -t decision
    """
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    valid_types = ["gotcha", "bug_fix", "decision", "discovery", "trade_off"]
    if memory_type not in valid_types:
        print_error(
            f"Invalid memory type '{memory_type}'. Must be one of: {', '.join(valid_types)}"
        )
        raise typer.Exit(code=1)

    try:
        data = {
            "observation": observation,
            "memory_type": memory_type,
        }
        if context:
            data["context"] = context

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/remember",
                json=data,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                if result.get("stored"):
                    print_success("Memory stored successfully.")
                    if result.get("id"):
                        print_info(f"  ID: {result['id']}")
                else:
                    print_warning("Memory was not stored.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to store memory: {e}")
        raise typer.Exit(code=1)


@ci_app.command("context")
def ci_context(
    task: str = typer.Argument(..., help="Description of the task you're working on"),
    files: list[str] = typer.Option(
        None, "--file", "-f", help="Files currently being viewed/edited (can specify multiple)"
    ),
    max_tokens: int = typer.Option(
        2000, "--max-tokens", "-m", help="Maximum tokens of context to return"
    ),
    format_output: str = typer.Option("json", "--format", help="Output format: 'json' or 'text'"),
    no_weight: bool = typer.Option(
        False, "--no-weight", "-w", help="Disable doc_type weighting (useful for non-code tasks)"
    ),
) -> None:
    """Get relevant context for your current task.

    Call this when starting work on something to retrieve related code,
    past decisions, and applicable project guidelines. By default,
    i18n/config files are down-weighted; use --no-weight to disable this.

    Examples:
        oak ci context "implementing user logout"
        oak ci context "fixing authentication bug" -f src/auth.py
        oak ci context "adding database migration" -f models.py -f db.py -m 4000
        oak ci context "updating translation strings" --no-weight
    """
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        data: dict[str, Any] = {
            "task": task,
            "max_tokens": max_tokens,
            "apply_doc_type_weights": not no_weight,
        }
        if files:
            data["current_files"] = list(files)

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"http://localhost:{manager.port}/api/context",
                json=data,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                code_context = result.get("code", [])
                memory_context = result.get("memories", [])
                guidelines = result.get("guidelines", [])

                if guidelines:
                    print_header("Guidelines")
                    for g in guidelines:
                        console.print(f"  • {g}")

                if memory_context:
                    console.print()
                    print_header("Relevant Memories")
                    for mem in memory_context:
                        mem_type = mem.get("memory_type", "?")
                        obs = mem.get("observation", "")
                        console.print(f"  [{mem_type}] {obs}")

                if code_context:
                    console.print()
                    print_header("Related Code")
                    for code in code_context:
                        filepath = code.get("file_path", "?")
                        chunk_type = code.get("chunk_type", "?")
                        name = code.get("name", "")
                        console.print(f"  {filepath} ({chunk_type}: {name})")

                if not code_context and not memory_context and not guidelines:
                    print_info("No relevant context found for this task.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to get context: {e}")
        raise typer.Exit(code=1)
