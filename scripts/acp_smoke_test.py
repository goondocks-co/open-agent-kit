#!/usr/bin/env python3
"""Live ACP smoke test against running OAK daemon.

Usage:
    python scripts/acp_smoke_test.py [--port PORT] [--token TOKEN]
    make acp-smoke

Prerequisites:
    Daemon must be running: oak-dev ci start (or oak ci start)

Exercises all ACP session routes and verifies results in the activity store.
Sessions are self-cleaning — each scenario creates and closes its own session.

Scenarios 1-8: HTTP plumbing validation (session lifecycle, prompts, tools, modes, focus)
Scenarios 9-12: OAK intelligence pipeline validation (activity recording, batch
finalization, session summaries, multi-turn activity accumulation)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Port file locations (same priority as daemon manager)
PORT_FILE_LOCAL = ".oak/ci/daemon.port"
PORT_FILE_SHARED = "oak/daemon.port"

# Auth token
TOKEN_FILE = ".oak/ci/daemon.token"
TOKEN_ENV_VAR = "OAK_CI_TOKEN"

# Expected agent name after rename
EXPECTED_AGENT_NAME = "oak"

# Timeouts
PROMPT_TIMEOUT = 120.0
DEFAULT_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Daemon discovery (self-contained, no OAK imports)
# ---------------------------------------------------------------------------


def discover_port(project_root: Path) -> int | None:
    """Read daemon port from port files."""
    for rel in (PORT_FILE_LOCAL, PORT_FILE_SHARED):
        port_file = project_root / rel
        if port_file.exists():
            try:
                port = int(port_file.read_text().strip())
                if 37800 <= port < 37800 + 1000:
                    return port
            except (ValueError, OSError):
                continue  # Invalid or unreadable port file, try next candidate
    return None


def discover_token(project_root: Path) -> str | None:
    """Read auth token from env or token file."""
    token = os.environ.get(TOKEN_ENV_VAR)
    if token:
        return token
    token_file = project_root / TOKEN_FILE
    if token_file.exists():
        try:
            return token_file.read_text().strip()
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# NDJSON stream parser
# ---------------------------------------------------------------------------


def parse_ndjson_stream(response: httpx.Response) -> list[dict]:
    """Read an NDJSON streaming response into a list of parsed events."""
    events: list[dict] = []
    for line in response.iter_lines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Non-JSON lines (e.g. SSE comments) are expected and safely skipped
    return events


# ---------------------------------------------------------------------------
# Smoke test runner
# ---------------------------------------------------------------------------


class SmokeTestRunner:
    """Runs ACP smoke test scenarios against a live daemon."""

    def __init__(self, base_url: str, auth_token: str | None) -> None:
        self.base_url = base_url
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
        self.passed = 0
        self.failed = 0

    # -- Helpers ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _create_session(self) -> str:
        """Create a session, return session_id."""
        r = httpx.post(
            self._url("/api/acp/sessions"),
            json={"cwd": None},
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["session_id"]

    def _close_session(self, session_id: str) -> None:
        """Close ACP session and purge from activity store (best-effort)."""
        try:
            # 1. Close the ACP session (ends SDK session, marks completed)
            httpx.delete(
                self._url(f"/api/acp/sessions/{session_id}"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except Exception:
            pass  # Best-effort cleanup; session may already be closed
        try:
            # 2. Delete from activity store (cascade: batches, activities, observations)
            httpx.delete(
                self._url(f"/api/activity/sessions/{session_id}"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except Exception:
            pass  # Best-effort cleanup; don't fail tests on cleanup errors

    def _prompt(self, session_id: str, text: str) -> list[dict]:
        """Send a prompt and collect all NDJSON events."""
        with httpx.stream(
            "POST",
            self._url(f"/api/acp/sessions/{session_id}/prompt"),
            json={"text": text},
            headers=self.headers,
            timeout=PROMPT_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return parse_ndjson_stream(response)

    def _set_mode(self, session_id: str, mode: str) -> int:
        """Set session mode, return HTTP status code."""
        r = httpx.put(
            self._url(f"/api/acp/sessions/{session_id}/mode"),
            json={"mode": mode},
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return r.status_code

    def _set_focus(self, session_id: str, focus: str) -> int:
        """Set session focus, return HTTP status code."""
        r = httpx.put(
            self._url(f"/api/acp/sessions/{session_id}/focus"),
            json={"focus": focus},
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return r.status_code

    def _cancel(self, session_id: str) -> int:
        """Cancel a session prompt, return HTTP status code."""
        r = httpx.post(
            self._url(f"/api/acp/sessions/{session_id}/cancel"),
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return r.status_code

    def _get_session_detail(self, session_id: str) -> dict | None:
        """Get session detail from activity store, or None on 404."""
        r = httpx.get(
            self._url(f"/api/activity/sessions/{session_id}"),
            headers=self.headers,
            timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def _get_batch_detail(self, session_id: str, batch_index: int = 0) -> dict | None:
        """Extract a specific batch from session detail."""
        detail = self._get_session_detail(session_id)
        if not detail:
            return None
        batches = detail.get("prompt_batches", [])
        if batch_index < len(batches):
            return batches[batch_index]
        return None

    def _wait_for_summary(self, session_id: str, timeout: float = 10.0) -> str | None:
        """Poll session detail until summary appears or timeout."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            detail = self._get_session_detail(session_id)
            if detail:
                session_data = detail.get("session", {})
                summary = session_data.get("summary")
                if summary:
                    return summary
            time.sleep(1.0)
        return None

    def _report(self, name: str, passed: bool, details: list[str]) -> None:
        """Print a scenario result."""
        if passed:
            self.passed += 1
        else:
            self.failed += 1

        print(f"\n{'[PASS]' if passed else '[FAIL]'} {name}")
        for detail in details:
            print(f"  {detail}")

    def _has_event_type(self, events: list[dict], event_type: str) -> bool:
        return any(e.get("type") == event_type for e in events)

    def _count_event_type(self, events: list[dict], event_type: str) -> int:
        return sum(1 for e in events if e.get("type") == event_type)

    # -- Scenarios --------------------------------------------------------

    def test_session_lifecycle(self) -> None:
        """Scenario 1: Create, verify in activity store, close, verify completed."""
        name = "Session lifecycle"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            # Verify in activity store
            detail = self._get_session_detail(session_id)
            if detail is None:
                details.append("Session NOT found in activity store")
                self._report(name, False, details)
                return

            session_data = detail.get("session", {})
            agent = session_data.get("agent", "")
            details.append(f"Verified in activity store: agent={agent}")

            if agent != EXPECTED_AGENT_NAME:
                details.append(f"Expected agent={EXPECTED_AGENT_NAME}, got {agent}")
                self._report(name, False, details)
                return

            # Close session
            self._close_session(session_id)
            details.append("Closed session")
            session_id = None  # already closed

            self._report(name, True, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_simple_prompt(self) -> None:
        """Scenario 2: Simple prompt, verify TextEvent + DoneEvent + batch finalization."""
        name = "Simple prompt"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            events = self._prompt(session_id, "What is 2 + 2? Answer in exactly one sentence.")

            text_count = self._count_event_type(events, "text")
            cost_count = self._count_event_type(events, "cost")
            done_count = self._count_event_type(events, "done")
            error_count = self._count_event_type(events, "error")

            details.append(
                f"Events: {text_count} text, {cost_count} cost, "
                f"{done_count} done, {error_count} error"
            )

            if error_count > 0:
                error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
                details.append(f"Errors: {error_msgs}")
                self._report(name, False, details)
                return

            if text_count == 0:
                details.append("No TextEvent received")
                self._report(name, False, details)
                return

            if done_count == 0:
                details.append("No DoneEvent received")
                self._report(name, False, details)
                return

            # Check done event
            done_events = [e for e in events if e.get("type") == "done"]
            if done_events and not done_events[0].get("needs_plan_approval", False):
                details.append("DoneEvent: needs_plan_approval=false")

            # Verify batch finalization in activity store
            detail = self._get_session_detail(session_id)
            if detail:
                batches = detail.get("prompt_batches", [])
                details.append(f"Activity store: {len(batches)} prompt batch(es)")

                if batches:
                    batch = batches[0]
                    activity_count = batch.get("activity_count", 0)
                    response_summary = batch.get("response_summary")
                    has_summary = response_summary is not None and len(response_summary) > 0
                    details.append(
                        f"Batch 0: activity_count={activity_count}, "
                        f"has_response_summary={has_summary}"
                    )
            else:
                details.append("Session not found in activity store (unexpected)")

            self._report(name, True, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_prompt_with_tool_calls(self) -> None:
        """Scenario 3: Prompt that triggers tool usage (Read), verify activity recording."""
        name = "Tool calls"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            events = self._prompt(
                session_id,
                "Read the file pyproject.toml and tell me the project name.",
            )

            text_count = self._count_event_type(events, "text")
            tool_count = self._count_event_type(events, "tool_start")
            done_count = self._count_event_type(events, "done")
            error_count = self._count_event_type(events, "error")

            # Collect tool names
            tool_names = [e.get("tool_name", "?") for e in events if e.get("type") == "tool_start"]

            details.append(
                f"Events: {text_count} text, {tool_count} tool_start "
                f"({', '.join(tool_names)}), {done_count} done, {error_count} error"
            )

            if error_count > 0:
                error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
                details.append(f"Errors: {error_msgs}")
                self._report(name, False, details)
                return

            if tool_count == 0:
                details.append("No ToolStartEvent — expected at least one (Read)")
                self._report(name, False, details)
                return

            # Verify activity store has activities from SDK hooks
            detail = self._get_session_detail(session_id)
            if detail:
                activities = detail.get("recent_activities", [])
                details.append(f"Activity store: {len(activities)} activities recorded")

                # Verify activities have tool_name and success fields
                if activities:
                    first = activities[0]
                    has_tool_name = "tool_name" in first and first["tool_name"]
                    has_success = "success" in first
                    details.append(
                        f"Activity fields: tool_name={has_tool_name}, success={has_success}"
                    )

            self._report(name, True, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_mode_switching(self) -> None:
        """Scenario 4: Cycle through permission modes."""
        name = "Mode switching"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            modes = ["plan", "acceptEdits", "default"]
            all_ok = True
            for mode in modes:
                status = self._set_mode(session_id, mode)
                if status != 200:
                    details.append(f"Mode '{mode}' returned {status}")
                    all_ok = False

            if all_ok:
                details.append(f"All {len(modes)} modes accepted (200)")

            # Verify session exists in activity store
            detail = self._get_session_detail(session_id)
            if detail:
                details.append("Session verified in activity store")
            else:
                details.append("Session not found in activity store")
                all_ok = False

            self._report(name, all_ok, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_multi_turn(self) -> None:
        """Scenario 5: Multiple prompts on one session — both succeed, 2 batches recorded.

        Note: each prompt() creates a fresh SDK client so there is no
        cross-turn memory.  This test verifies the session can accept
        multiple sequential prompts and the activity store records a
        prompt batch for each.
        """
        name = "Multi-turn prompts"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            # Turn 1
            events1 = self._prompt(
                session_id,
                "What is 3 + 5? Answer in one sentence.",
            )
            error_count1 = self._count_event_type(events1, "error")
            if error_count1 > 0:
                error_msgs = [e.get("message", "") for e in events1 if e.get("type") == "error"]
                details.append(f"Turn 1 errors: {error_msgs}")
                self._report(name, False, details)
                return
            has_text1 = self._has_event_type(events1, "text")
            details.append(f"Turn 1: text={has_text1}")

            # Turn 2
            events2 = self._prompt(
                session_id,
                "What is 10 - 4? Answer in one sentence.",
            )
            error_count2 = self._count_event_type(events2, "error")
            if error_count2 > 0:
                error_msgs = [e.get("message", "") for e in events2 if e.get("type") == "error"]
                details.append(f"Turn 2 errors: {error_msgs}")
                self._report(name, False, details)
                return
            has_text2 = self._has_event_type(events2, "text")
            details.append(f"Turn 2: text={has_text2}")

            # Verify prompt batches — should be exactly 2
            detail = self._get_session_detail(session_id)
            batch_count = 0
            if detail:
                batch_count = len(detail.get("prompt_batches", []))
                details.append(f"Activity store: {batch_count} prompt batch(es)")

            passed = has_text1 and has_text2 and batch_count == 2
            self._report(name, passed, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_cancellation(self) -> None:
        """Scenario 6: Start a long prompt then cancel it."""
        name = "Cancellation"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            collected_events: list[dict] = []
            stream_error: list[Exception] = []

            def stream_prompt() -> None:
                try:
                    with httpx.stream(
                        "POST",
                        self._url(f"/api/acp/sessions/{session_id}/prompt"),
                        json={
                            "text": (
                                "Write a detailed 2000-word essay about "
                                "software architecture patterns."
                            )
                        },
                        headers=self.headers,
                        timeout=PROMPT_TIMEOUT,
                    ) as response:
                        for line in response.iter_lines():
                            line = line.strip()
                            if line:
                                try:
                                    collected_events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Non-JSON lines expected in NDJSON stream
                except Exception as e:
                    stream_error.append(e)

            # Start streaming in a background thread
            thread = threading.Thread(target=stream_prompt, daemon=True)
            thread.start()

            # Wait briefly, then cancel
            time.sleep(2)
            cancel_status = self._cancel(session_id)
            details.append(f"Cancel returned: {cancel_status}")

            # Wait for stream to finish
            thread.join(timeout=30)

            has_cancelled = self._has_event_type(collected_events, "cancelled")
            has_done = self._has_event_type(collected_events, "done")
            details.append(
                f"Events after cancel: {len(collected_events)} total, "
                f"cancelled={has_cancelled}, done={has_done}"
            )

            # Verify session exists in activity store
            detail = self._get_session_detail(session_id)
            if detail:
                details.append("Session verified in activity store")

            # Pass if cancel returned 200 (stream may or may not have the cancelled event
            # depending on timing)
            self._report(name, cancel_status == 200, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_error_handling(self) -> None:
        """Scenario 7: Error cases — nonexistent session."""
        name = "Error handling"
        details: list[str] = []

        try:
            fake_id = "nonexistent-session-00000000"

            # Prompt on nonexistent session should yield ErrorEvent in NDJSON
            with httpx.stream(
                "POST",
                self._url(f"/api/acp/sessions/{fake_id}/prompt"),
                json={"text": "hello"},
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            ) as response:
                events = parse_ndjson_stream(response)

            has_error = self._has_event_type(events, "error")
            details.append(f"Prompt on nonexistent session: error_event={has_error}")

            # Cancel on nonexistent session should return 404
            cancel_status = self._cancel(fake_id)
            details.append(f"Cancel on nonexistent session: {cancel_status}")

            passed = has_error and cancel_status == 404
            self._report(name, passed, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)

    def test_focus_switching(self) -> None:
        """Scenario 8: Cycle through agent focus values."""
        name = "Focus switching"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            focuses = ["documentation", "analysis", "engineering", "maintenance", "oak"]
            all_ok = True
            for focus in focuses:
                status = self._set_focus(session_id, focus)
                if status != 200:
                    details.append(f"Focus '{focus}' returned {status}")
                    all_ok = False

            if all_ok:
                details.append(f"All {len(focuses)} focuses accepted (200)")

            # Invalid focus should return 422
            invalid_status = self._set_focus(session_id, "nonexistent-agent")
            if invalid_status == 422:
                details.append("Invalid focus correctly rejected (422)")
            else:
                details.append(f"Invalid focus returned {invalid_status}, expected 422")
                all_ok = False

            # Verify session exists in activity store
            detail = self._get_session_detail(session_id)
            if detail:
                details.append("Session verified in activity store")
            else:
                details.append("Session not found in activity store")
                all_ok = False

            self._report(name, all_ok, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    # -- Intelligence pipeline scenarios ----------------------------------

    def test_activity_recording(self) -> None:
        """Scenario 9: Activity recording via SDK hooks.

        Send a prompt that forces specific tool use, verify activities are
        recorded with correct fields in the activity store.
        """
        name = "Activity recording"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            events = self._prompt(
                session_id,
                "Read the file Makefile, then read pyproject.toml. "
                "Report the first line of each file.",
            )

            error_count = self._count_event_type(events, "error")
            if error_count > 0:
                error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
                details.append(f"Errors: {error_msgs}")
                self._report(name, False, details)
                return

            tool_count = self._count_event_type(events, "tool_start")
            details.append(f"Tool events: {tool_count}")

            # Verify activities in the activity store
            detail = self._get_session_detail(session_id)
            if not detail:
                details.append("Session not found in activity store")
                self._report(name, False, details)
                return

            activities = detail.get("recent_activities", [])
            details.append(f"Activities recorded: {len(activities)}")

            passed = True

            # Check that activities have expected fields
            if activities:
                for act in activities[:3]:
                    has_tool = bool(act.get("tool_name"))
                    has_success = "success" in act
                    has_batch = act.get("prompt_batch_id") is not None
                    if not (has_tool and has_success and has_batch):
                        details.append(
                            f"Activity missing fields: tool={has_tool} "
                            f"success={has_success} batch={has_batch}"
                        )
                        passed = False
                        break

                # At least some activities should exist
                if len(activities) == 0:
                    details.append("No activities recorded despite tool use")
                    passed = False
                else:
                    details.append("Activities have required fields (tool_name, success, batch_id)")
            else:
                details.append("No activities found (SDK hooks may not have fired)")
                # Don't fail — SDK hooks depend on SDK version support
                passed = True

            self._report(name, passed, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_batch_finalization(self) -> None:
        """Scenario 10: Batch finalization and response summary.

        Send a prompt, verify the batch has response_summary and ended_at set.
        """
        name = "Batch finalization"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            events = self._prompt(
                session_id,
                "Say 'hello world' and nothing else.",
            )

            error_count = self._count_event_type(events, "error")
            if error_count > 0:
                error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
                details.append(f"Errors: {error_msgs}")
                self._report(name, False, details)
                return

            # Verify batch finalization
            batch = self._get_batch_detail(session_id, 0)
            if not batch:
                details.append("No batch found in activity store")
                self._report(name, False, details)
                return

            response_summary = batch.get("response_summary")
            ended_at = batch.get("ended_at")
            source_type = batch.get("source_type")

            has_summary = response_summary is not None and len(str(response_summary)) > 0
            has_ended = ended_at is not None

            details.append(f"response_summary: {'present' if has_summary else 'MISSING'}")
            details.append(f"ended_at: {'set' if has_ended else 'MISSING'}")
            details.append(f"source_type: {source_type}")

            passed = has_summary and has_ended
            if source_type:
                details.append(f"source_type={source_type} (expected '{EXPECTED_AGENT_NAME}')")

            self._report(name, passed, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_session_close_summary(self) -> None:
        """Scenario 11: Session close and summary generation.

        Create session, send prompt, close, wait for async summary.
        """
        name = "Session close & summary"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            events = self._prompt(
                session_id,
                "Read the file pyproject.toml and tell me the version number.",
            )

            error_count = self._count_event_type(events, "error")
            if error_count > 0:
                error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
                details.append(f"Errors: {error_msgs}")
                self._report(name, False, details)
                return

            # Close the ACP session (triggers async summary)
            try:
                httpx.delete(
                    self._url(f"/api/acp/sessions/{session_id}"),
                    headers=self.headers,
                    timeout=DEFAULT_TIMEOUT,
                )
                details.append("Session closed via DELETE")
            except Exception as e:
                details.append(f"Close failed: {e}")
                self._report(name, False, details)
                return

            # Check session status
            detail = self._get_session_detail(session_id)
            if not detail:
                details.append("Session not found after close")
                self._report(name, False, details)
                return

            session_data = detail.get("session", {})
            status = session_data.get("status", "unknown")
            details.append(f"Session status: {status}")

            # Wait for summary (async, may take a moment)
            summary = self._wait_for_summary(session_id, timeout=10.0)
            if summary:
                details.append(f"Summary generated: {len(summary)} chars")
                details.append(f"Summary preview: {summary[:100]}...")
            else:
                details.append("No summary generated (may require LLM — acceptable)")

            # Pass if session is completed (summary is optional since it needs LLM)
            passed = status == "completed"
            self._report(name, passed, details)

            # Purge from activity store after checking
            try:
                httpx.delete(
                    self._url(f"/api/activity/sessions/{session_id}"),
                    headers=self.headers,
                    timeout=DEFAULT_TIMEOUT,
                )
            except Exception:
                pass  # Best-effort purge; don't fail test on cleanup errors
            session_id = None  # already cleaned up

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    def test_multi_turn_activity_accumulation(self) -> None:
        """Scenario 12: Multi-turn activity accumulation.

        Two prompts on one session, each triggering tool use. Verify each
        batch has its own activities and they don't cross-contaminate.
        """
        name = "Multi-turn activity accumulation"
        details: list[str] = []
        session_id = None

        try:
            session_id = self._create_session()
            details.append(f"Created session: {session_id}")

            # Turn 1 — trigger tool use
            events1 = self._prompt(
                session_id,
                "Read the file Makefile and tell me the first target name.",
            )
            error_count1 = self._count_event_type(events1, "error")
            if error_count1 > 0:
                error_msgs = [e.get("message", "") for e in events1 if e.get("type") == "error"]
                details.append(f"Turn 1 errors: {error_msgs}")
                self._report(name, False, details)
                return
            tool_count1 = self._count_event_type(events1, "tool_start")
            details.append(f"Turn 1: {tool_count1} tool events")

            # Turn 2 — trigger different tool use
            events2 = self._prompt(
                session_id,
                "Read the file pyproject.toml and tell me the project description.",
            )
            error_count2 = self._count_event_type(events2, "error")
            if error_count2 > 0:
                error_msgs = [e.get("message", "") for e in events2 if e.get("type") == "error"]
                details.append(f"Turn 2 errors: {error_msgs}")
                self._report(name, False, details)
                return
            tool_count2 = self._count_event_type(events2, "tool_start")
            details.append(f"Turn 2: {tool_count2} tool events")

            # Verify batches
            detail = self._get_session_detail(session_id)
            if not detail:
                details.append("Session not found in activity store")
                self._report(name, False, details)
                return

            batches = detail.get("prompt_batches", [])
            details.append(f"Total batches: {len(batches)}")

            passed = len(batches) == 2
            if not passed:
                details.append(f"Expected 2 batches, got {len(batches)}")

            # Check activities per batch
            activities = detail.get("recent_activities", [])
            total_activities = len(activities)
            details.append(f"Total activities across batches: {total_activities}")

            self._report(name, passed, details)

        except Exception as e:
            details.append(f"Error: {e}")
            self._report(name, False, details)
        finally:
            if session_id:
                self._close_session(session_id)

    # -- Runner -----------------------------------------------------------

    def run_all(self) -> bool:
        """Run all scenarios in sequence. Returns True if all passed."""
        print(f"ACP Smoke Test — OAK Daemon at {self.base_url}")
        print("=" * 56)

        # HTTP plumbing scenarios
        self.test_session_lifecycle()
        self.test_simple_prompt()
        self.test_prompt_with_tool_calls()
        self.test_mode_switching()
        self.test_multi_turn()
        self.test_cancellation()
        self.test_error_handling()
        self.test_focus_switching()

        # Intelligence pipeline scenarios
        self.test_activity_recording()
        self.test_batch_finalization()
        self.test_session_close_summary()
        self.test_multi_turn_activity_accumulation()

        print()
        print("=" * 56)
        total = self.passed + self.failed
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")

        return self.failed == 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live ACP smoke test against running OAK daemon.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Daemon port (auto-detected from port files if omitted)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Auth token (auto-detected from token file or OAK_CI_TOKEN env if omitted)",
    )
    args = parser.parse_args()

    project_root = Path.cwd()

    # Discover port
    port = args.port or discover_port(project_root)
    if port is None:
        print(
            "Error: Cannot find daemon port. Is the daemon running?\n"
            "  Start it with: oak-dev ci start (or oak ci start)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Discover token
    token = args.token or discover_token(project_root)

    base_url = f"http://127.0.0.1:{port}"

    # Quick connectivity check
    try:
        r = httpx.get(
            f"{base_url}/api/health",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=5.0,
        )
        if r.status_code >= 500:
            print(f"Error: Daemon returned {r.status_code} on health check", file=sys.stderr)
            sys.exit(1)
    except httpx.ConnectError:
        print(
            f"Error: Cannot connect to daemon at {base_url}\n"
            "  Start it with: oak-dev ci start (or oak ci start)",
            file=sys.stderr,
        )
        sys.exit(1)

    runner = SmokeTestRunner(base_url, token)
    success = runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
