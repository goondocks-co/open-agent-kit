"""CI history query commands: memories, sessions, test."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from open_agent_kit.features.codebase_intelligence.constants import (
    HTTP_TIMEOUT_QUICK,
    HTTP_TIMEOUT_STANDARD,
    OBSERVATION_STATUS_ACTIVE,
    VALID_OBSERVATION_STATUSES,
)
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


@ci_app.command("memories")
def ci_memories(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of memories to show"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    memory_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type: gotcha, bug_fix, decision, discovery, trade_off, session_summary",
    ),
    exclude_sessions: bool = typer.Option(
        False, "--exclude-sessions", "-x", help="Exclude session summaries"
    ),
    status: str = typer.Option(
        OBSERVATION_STATUS_ACTIVE,
        "--status",
        help="Filter by status: 'active', 'resolved', or 'superseded'",
    ),
    include_resolved: bool = typer.Option(
        False, "--include-resolved", help="Include all statuses regardless of --status filter"
    ),
    format_output: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """List stored memories and session summaries.

    Browse all observations, decisions, gotchas, and session summaries stored
    by CI. Unlike search, this lists memories without semantic matching.

    Examples:
        oak ci memories                        # List recent active memories
        oak ci memories --type gotcha          # Filter by type
        oak ci memories --status resolved      # Show resolved memories
        oak ci memories --include-resolved     # Show all statuses
        oak ci memories -n 50                  # Show more results
        oak ci memories --type session_summary # List session summaries only
        oak ci memories -x                     # Exclude session summaries
        oak ci memories -f json                # JSON output for scripting
    """
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    # Validate memory type if provided
    valid_types = ["gotcha", "bug_fix", "decision", "discovery", "trade_off", "session_summary"]
    if memory_type and memory_type not in valid_types:
        print_error(
            f"Invalid memory type '{memory_type}'. Must be one of: {', '.join(valid_types)}"
        )
        raise typer.Exit(code=1)

    # Validate status if provided
    if status not in VALID_OBSERVATION_STATUSES:
        print_error(
            f"Invalid status '{status}'. Must be one of: "
            f"{', '.join(VALID_OBSERVATION_STATUSES)}"
        )
        raise typer.Exit(code=1)

    try:
        params: dict[str, str | int] = {
            "limit": min(max(1, limit), 100),
            "offset": max(0, offset),
            "status": status,
        }
        if memory_type:
            params["memory_type"] = memory_type
        if exclude_sessions:
            params["exclude_sessions"] = "true"
        if include_resolved:
            params["include_resolved"] = "true"

        with httpx.Client(timeout=HTTP_TIMEOUT_STANDARD) as client:
            response = client.get(
                f"http://localhost:{manager.port}/api/memories",
                params=params,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                # Human-readable format
                memories = result.get("memories", [])
                total = result.get("total", 0)

                if not memories:
                    print_info("No memories found.")
                    return

                # Memory type icons
                type_icons = {
                    "gotcha": "⚠️",
                    "bug_fix": "🐛",
                    "decision": "📐",
                    "discovery": "💡",
                    "trade_off": "⚖️",
                    "session_summary": "📋",
                }

                print_header(f"Memories ({len(memories)} of {total})")
                for mem in memories:
                    mem_type = mem.get("memory_type", "discovery")
                    icon = type_icons.get(mem_type, "•")
                    observation = mem.get("observation", "")
                    created = mem.get("created_at", "")
                    mem_status = mem.get("status", OBSERVATION_STATUS_ACTIVE)

                    # Truncate long observations
                    if len(observation) > 100:
                        observation = observation[:97] + "..."

                    # Show status indicator for non-active memories
                    status_suffix = ""
                    if mem_status != OBSERVATION_STATUS_ACTIVE:
                        status_suffix = f" [dim]({mem_status})[/dim]"

                    console.print(
                        f"\n{icon} [bold][{mem_type}][/bold] {observation}{status_suffix}"
                    )
                    if created:
                        # Format datetime if present
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            formatted = dt.strftime("%Y-%m-%d %H:%M")
                            console.print(f"  [dim]{formatted}[/dim]")
                        except (ValueError, AttributeError, TypeError) as e:
                            logger.debug(f"Failed to parse created timestamp: {e}")
                            console.print(f"  [dim]{created}[/dim]")

                    context = mem.get("context")
                    if context:
                        console.print(f"  Context: {context}", style="dim")

                    tags = mem.get("tags", [])
                    if tags:
                        console.print(f"  Tags: {', '.join(tags)}", style="dim")

                # Pagination info
                if total > len(memories):
                    next_offset = offset + limit
                    console.print()
                    print_info(f"Page {offset // limit + 1} of {(total + limit - 1) // limit}")
                    if next_offset < total:
                        print_info(f"  Next page: oak ci memories -n {limit} -o {next_offset}")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to list memories: {e}")
        raise typer.Exit(code=1)


@ci_app.command("sessions")
def ci_sessions(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show"),
    format_output: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """List recent session summaries.

    Shortcut for 'oak ci memories --type session_summary'.
    Shows LLM-generated summaries from past coding sessions.

    Examples:
        oak ci sessions          # List last 10 session summaries
        oak ci sessions -n 5     # Show fewer
        oak ci sessions -f json  # JSON output
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
        query_params: dict[str, str | int] = {
            "limit": min(max(1, limit), 100),
            "memory_type": "session_summary",
        }

        with httpx.Client(timeout=HTTP_TIMEOUT_STANDARD) as client:
            response = client.get(
                f"http://localhost:{manager.port}/api/memories",
                params=query_params,
            )
            response.raise_for_status()
            result = response.json()

            if format_output == "json":
                console.print(json.dumps(result, indent=2))
            else:
                memories = result.get("memories", [])
                total = result.get("total", 0)

                if not memories:
                    print_info("No session summaries found.")
                    print_info("Sessions are summarized when you end a coding session.")
                    return

                print_header(f"Session Summaries ({len(memories)} of {total})")
                for i, mem in enumerate(memories, 1):
                    observation = mem.get("observation", "")
                    created = mem.get("created_at", "")
                    tags = mem.get("tags", [])

                    # Format datetime
                    time_str = ""
                    if created:
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            time_str = dt.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, AttributeError, TypeError) as e:
                            logger.debug(f"Failed to parse session timestamp: {e}")
                            time_str = created

                    console.print(f"\n[bold]Session {i}[/bold] - {time_str}")

                    # Show agent if in tags
                    agent = next((t for t in tags if t not in ["session", "llm-summarized"]), None)
                    if agent:
                        console.print(f"  Agent: {agent}", style="dim")

                    # Show summary (may be multi-line)
                    console.print(f"  {observation}")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to list sessions: {e}")
        raise typer.Exit(code=1)


@ci_app.command("resolve")
def ci_resolve(
    memory_id: str | None = typer.Argument(None, help="Observation ID to resolve"),
    session: str | None = typer.Option(
        None, "--session", "-s", help="Resolve all observations from this session"
    ),
    status: str = typer.Option(
        "resolved", "--status", help="Target status: 'resolved' or 'superseded'"
    ),
    reason: str | None = typer.Option(None, "--reason", "-r", help="Reason for resolution"),
    format_output: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'"
    ),
) -> None:
    """Mark observation(s) as resolved or superseded.

    Resolve a single observation by ID, or all observations from a session.

    Examples:
        oak ci resolve abc-123                       # Resolve by ID
        oak ci resolve abc-123 --status superseded   # Mark as superseded
        oak ci resolve --session sess-456            # Bulk resolve by session
        oak ci resolve abc-123 -r "Fixed in PR #42"  # With reason
    """
    import httpx

    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    if not memory_id and not session:
        print_error("Provide either a memory ID or --session to resolve.")
        raise typer.Exit(code=1)

    # Validate status
    valid_resolve_statuses = ("resolved", "superseded")
    if status not in valid_resolve_statuses:
        print_error(
            f"Invalid status '{status}'. Must be one of: {', '.join(valid_resolve_statuses)}"
        )
        raise typer.Exit(code=1)

    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        print_error("CI daemon not running. Start with: oak ci start")
        raise typer.Exit(code=1)

    try:
        base_url = f"http://localhost:{manager.port}"

        with httpx.Client(timeout=HTTP_TIMEOUT_STANDARD) as client:
            if memory_id:
                # Single resolve via PUT
                data: dict[str, Any] = {"status": status}
                if reason:
                    data["reason"] = reason
                response = client.put(
                    f"{base_url}/api/memories/{memory_id}/status",
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

                if format_output == "json":
                    console.print(json.dumps(result, indent=2))
                else:
                    if result.get("updated"):
                        print_success(f"Memory {memory_id} marked as {status}.")
                    else:
                        print_warning(f"Memory {memory_id} was not updated.")
            else:
                # Bulk resolve by session via POST
                data = {
                    "session_id": session,
                    "status": status,
                }
                if reason:
                    data["reason"] = reason
                response = client.post(
                    f"{base_url}/api/memories/bulk-resolve",
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

                if format_output == "json":
                    console.print(json.dumps(result, indent=2))
                else:
                    count = result.get("updated_count", 0)
                    if count > 0:
                        print_success(f"Resolved {count} observation(s) from session {session}.")
                    else:
                        print_warning(f"No observations found for session {session}.")

    except httpx.ConnectError:
        print_error("Cannot connect to CI daemon. Is it running?")
        raise typer.Exit(code=1)
    except httpx.HTTPStatusError as e:
        print_error(f"Failed to resolve: {e.response.text}")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to resolve observation: {e}")
        raise typer.Exit(code=1)


@ci_app.command("test")
def ci_test(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Test Codebase Intelligence integration.

    Runs a series of tests to verify hooks, search, and memory are working.
    """
    project_root = Path.cwd()
    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    import httpx

    print_header("Codebase Intelligence Integration Test")

    manager = get_daemon_manager(project_root)
    port = manager.port
    base_url = f"http://localhost:{port}"

    tests_passed = 0
    tests_failed = 0

    def test(name: str, func: Callable[[], Any]) -> bool:
        nonlocal tests_passed, tests_failed
        try:
            result = func()
            if result:
                print_success(f"✓ {name}")
                if verbose and isinstance(result, dict):
                    console.print(f"  {result}")
                tests_passed += 1
                return True
            else:
                print_error(f"✗ {name}: No result")
                tests_failed += 1
                return False
        except Exception as e:
            print_error(f"✗ {name}: {e}")
            tests_failed += 1
            return False

    # Test 1: Daemon health
    def test_health() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.get(f"{base_url}/api/health")
            return r.status_code == 200

    test("Daemon health check", test_health)

    # Test 2: Index status
    def test_index() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.get(f"{base_url}/api/index/status")
            data = r.json()
            return data.get("status") in ["ready", "indexing"]

    test("Index status", test_index)

    # Test 3: Session start hook
    def test_session_start() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.post(f"{base_url}/api/hook/session-start", json={"agent": "test"})
            data = r.json()
            return data.get("status") == "ok" and "session_id" in data

    test("Session start hook", test_session_start)

    # Test 4: Search API
    def test_search() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_STANDARD) as client:
            r = client.post(f"{base_url}/api/search", json={"query": "main function", "limit": 3})
            data = r.json()
            return "code" in data or "memory" in data

    test("Semantic search", test_search)

    # Test 5: Remember API
    def test_remember() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.post(
                f"{base_url}/api/remember",
                json={
                    "observation": "Test observation from CI test",
                    "memory_type": "discovery",
                    "context": "ci_test",
                },
            )
            data = r.json()
            return data.get("stored") is True

    test("Memory storage", test_remember)

    # Test 6: MCP tools listing
    def test_mcp_tools() -> bool:
        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.get(f"{base_url}/api/mcp/tools")
            data = r.json()
            tools = [t["name"] for t in data.get("tools", [])]
            return "oak_search" in tools and "oak_remember" in tools

    test("MCP tools available", test_mcp_tools)

    # Test 7: Auto-capture via post-tool-use hook
    def test_auto_capture() -> bool:
        import base64

        # Simulate an error output that should trigger auto-capture
        error_output = "Error: Failed to connect to database\nTraceback: connection refused"
        tool_input = {"command": "pytest tests/"}
        output_b64 = base64.b64encode(error_output.encode()).decode()

        with httpx.Client(timeout=HTTP_TIMEOUT_QUICK) as client:
            r = client.post(
                f"{base_url}/api/hook/post-tool-use",
                json={
                    "agent": "test",
                    "tool_name": "Bash",
                    "tool_input": tool_input,
                    "tool_output_b64": output_b64,
                },
            )
            data = r.json()
            # Should have captured at least one observation due to error keywords
            status_ok = data.get("status") == "ok"
            has_observations = int(data.get("observations_captured", 0)) > 0
            return status_ok and has_observations

    test("Auto-capture from tool output", test_auto_capture)

    # Test 8: Check hook files exist
    def test_hook_files() -> bool:
        claude_hooks = project_root / ".claude" / "settings.json"
        cursor_hooks = project_root / ".cursor" / "hooks.json"
        # At least one should exist
        return claude_hooks.exists() or cursor_hooks.exists()

    test("Agent hook files installed", test_hook_files)

    # Summary
    console.print()
    total = tests_passed + tests_failed
    if tests_failed == 0:
        print_success(f"All {total} tests passed!")
    else:
        print_warning(f"{tests_passed}/{total} tests passed, {tests_failed} failed")

    if tests_failed > 0:
        raise typer.Exit(code=1)
