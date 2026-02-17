"""Tests for additional_prompt in agent schedules.

Covers:
- Migration v3 -> v4 (adding additional_prompt column)
- Schedule CRUD with additional_prompt
- Scheduler prompt composition with assignment
- Route request/response model validation
"""

import sqlite3
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.migrations import (
    _migrate_v3_to_v4,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.schedules import (
    ScheduleCreateRequest,
    ScheduleStatusResponse,
    ScheduleUpdateRequest,
)

# =============================================================================
# Migration Tests
# =============================================================================


class TestMigrateV3ToV4:
    """Tests for _migrate_v3_to_v4 adding additional_prompt to agent_schedules."""

    @staticmethod
    def _create_v3_table(conn: sqlite3.Connection) -> None:
        """Create the agent_schedules table at v3 (no additional_prompt)."""
        conn.execute("""
            CREATE TABLE agent_schedules (
                task_name TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                cron_expression TEXT,
                description TEXT,
                trigger_type TEXT DEFAULT 'cron',
                last_run_at TEXT,
                last_run_at_epoch INTEGER,
                last_run_id TEXT,
                next_run_at TEXT,
                next_run_at_epoch INTEGER,
                created_at TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_at_epoch INTEGER NOT NULL,
                source_machine_id TEXT
            )
        """)

    def test_adds_additional_prompt_column(self) -> None:
        """Migration should add additional_prompt column to agent_schedules."""
        conn = sqlite3.connect(":memory:")
        self._create_v3_table(conn)

        _migrate_v3_to_v4(conn)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_schedules)").fetchall()}
        assert "additional_prompt" in columns
        conn.close()

    def test_idempotent_when_column_exists(self) -> None:
        """Migration should not fail if additional_prompt column already exists."""
        conn = sqlite3.connect(":memory:")
        self._create_v3_table(conn)

        # Run twice — second should be a no-op
        _migrate_v3_to_v4(conn)
        _migrate_v3_to_v4(conn)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_schedules)").fetchall()}
        assert "additional_prompt" in columns
        conn.close()

    def test_existing_rows_get_null(self) -> None:
        """Existing schedule rows should have NULL additional_prompt after migration."""
        conn = sqlite3.connect(":memory:")
        self._create_v3_table(conn)
        conn.execute(
            "INSERT INTO agent_schedules (task_name, created_at, created_at_epoch, updated_at, updated_at_epoch) "
            "VALUES ('test-task', '2026-01-01T00:00:00', 1735689600, '2026-01-01T00:00:00', 1735689600)"
        )

        _migrate_v3_to_v4(conn)

        row = conn.execute(
            "SELECT additional_prompt FROM agent_schedules WHERE task_name = 'test-task'"
        ).fetchone()
        assert row[0] is None
        conn.close()


# =============================================================================
# Schedule CRUD Tests (via mock store)
# =============================================================================


class TestScheduleCrudAdditionalPrompt:
    """Tests for additional_prompt flowing through schedule CRUD functions."""

    @staticmethod
    def _make_store() -> MagicMock:
        """Create a mock ActivityStore with an in-memory SQLite database."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_SQL)

        store = MagicMock()
        store._get_connection.return_value = conn
        store.machine_id = "test_abc123"

        # Wire _transaction to return the same connection as a context manager
        class FakeTransaction:
            def __enter__(self):
                return conn

            def __exit__(self, *args):
                conn.commit()

        store._transaction.return_value = FakeTransaction()
        return store

    def test_create_schedule_with_additional_prompt(self) -> None:
        """create_schedule should store additional_prompt."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_schedule,
        )

        store = self._make_store()
        create_schedule(
            store,
            task_name="test-task",
            cron_expression="0 0 * * MON",
            description="Weekly run",
            additional_prompt="Focus on the backup module",
        )

        schedule = get_schedule(store, "test-task")
        assert schedule is not None
        assert schedule["additional_prompt"] == "Focus on the backup module"

    def test_create_schedule_without_additional_prompt(self) -> None:
        """create_schedule without additional_prompt should store NULL."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_schedule,
        )

        store = self._make_store()
        create_schedule(store, task_name="test-task", cron_expression="0 0 * * *")

        schedule = get_schedule(store, "test-task")
        assert schedule is not None
        assert schedule["additional_prompt"] is None

    def test_update_schedule_sets_additional_prompt(self) -> None:
        """update_schedule should set additional_prompt."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_schedule,
            update_schedule,
        )

        store = self._make_store()
        create_schedule(store, task_name="test-task", cron_expression="0 0 * * *")
        update_schedule(store, "test-task", additional_prompt="Review auth module")

        schedule = get_schedule(store, "test-task")
        assert schedule is not None
        assert schedule["additional_prompt"] == "Review auth module"

    def test_update_schedule_clears_additional_prompt(self) -> None:
        """update_schedule with empty string should clear additional_prompt to NULL."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_schedule,
            update_schedule,
        )

        store = self._make_store()
        create_schedule(
            store,
            task_name="test-task",
            cron_expression="0 0 * * *",
            additional_prompt="Original assignment",
        )
        update_schedule(store, "test-task", additional_prompt="")

        schedule = get_schedule(store, "test-task")
        assert schedule is not None
        assert schedule["additional_prompt"] is None

    def test_list_schedules_includes_additional_prompt(self) -> None:
        """list_schedules should include additional_prompt in returned dicts."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            list_schedules,
        )

        store = self._make_store()
        create_schedule(
            store, task_name="task-a", cron_expression="0 0 * * *", additional_prompt="Focus A"
        )
        create_schedule(store, task_name="task-b", cron_expression="0 0 * * *")

        schedules = list_schedules(store)
        by_name = {s["task_name"]: s for s in schedules}
        assert by_name["task-a"]["additional_prompt"] == "Focus A"
        assert by_name["task-b"]["additional_prompt"] is None

    def test_get_due_schedules_includes_additional_prompt(self) -> None:
        """get_due_schedules should include additional_prompt in returned dicts."""
        from datetime import datetime, timedelta

        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_due_schedules,
            update_schedule,
        )

        store = self._make_store()
        create_schedule(
            store,
            task_name="due-task",
            cron_expression="0 0 * * *",
            additional_prompt="Check tests",
        )
        # Set next_run to the past so it's "due"
        past = datetime.now() - timedelta(hours=1)
        update_schedule(store, "due-task", next_run_at=past)

        due = get_due_schedules(store)
        assert len(due) == 1
        assert due[0]["additional_prompt"] == "Check tests"

    def test_upsert_schedule_creates_with_additional_prompt(self) -> None:
        """upsert_schedule should create with additional_prompt when schedule doesn't exist."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            get_schedule,
            upsert_schedule,
        )

        store = self._make_store()
        upsert_schedule(
            store,
            task_name="new-task",
            cron_expression="0 0 * * *",
            additional_prompt="New assignment",
        )

        schedule = get_schedule(store, "new-task")
        assert schedule is not None
        assert schedule["additional_prompt"] == "New assignment"

    def test_upsert_schedule_updates_additional_prompt(self) -> None:
        """upsert_schedule should update additional_prompt when schedule exists."""
        from open_agent_kit.features.codebase_intelligence.activity.store.schedules import (
            create_schedule,
            get_schedule,
            upsert_schedule,
        )

        store = self._make_store()
        create_schedule(
            store,
            task_name="existing-task",
            cron_expression="0 0 * * *",
            additional_prompt="Old",
        )
        upsert_schedule(
            store,
            task_name="existing-task",
            cron_expression="0 0 * * *",
            additional_prompt="Updated",
        )

        schedule = get_schedule(store, "existing-task")
        assert schedule is not None
        assert schedule["additional_prompt"] == "Updated"


# =============================================================================
# Scheduler Prompt Composition Tests
# =============================================================================


class TestSchedulerPromptComposition:
    """Tests for the prompt composition logic used in run_scheduled_agent."""

    @staticmethod
    def _compose_prompt(default_task: str, additional_prompt: str | None) -> str:
        """Mirror the composition logic from scheduler.run_scheduled_agent."""
        task_prompt = default_task
        if additional_prompt:
            task_prompt = f"## Assignment\n{additional_prompt}\n\n---\n\n{default_task}"
        return task_prompt

    def test_no_additional_prompt_uses_default(self) -> None:
        """Without additional_prompt, default_task is used unchanged."""
        default_task = "Review architecture."

        result = self._compose_prompt(default_task, None)

        assert result == default_task

    def test_additional_prompt_prepends_assignment(self) -> None:
        """With additional_prompt, Assignment section is prepended."""
        default_task = "Hunt for bugs."
        additional = "Focus on the backup module."

        result = self._compose_prompt(default_task, additional)

        assert result.startswith("## Assignment\n")
        assert additional in result
        assert "---" in result
        assert result.endswith(default_task)

    def test_empty_additional_prompt_uses_default(self) -> None:
        """Empty string additional_prompt should use default_task unchanged."""
        default_task = "Review architecture."

        result = self._compose_prompt(default_task, "")

        assert result == default_task


# =============================================================================
# Route Model Tests
# =============================================================================


class TestScheduleRouteModels:
    """Tests for additional_prompt in schedule request/response models."""

    def test_status_response_default_none(self) -> None:
        """ScheduleStatusResponse should default additional_prompt to None."""
        response = ScheduleStatusResponse(
            task_name="test",
            has_definition=True,
            has_db_record=True,
        )

        assert response.additional_prompt is None

    def test_status_response_with_additional_prompt(self) -> None:
        """ScheduleStatusResponse should accept additional_prompt."""
        response = ScheduleStatusResponse(
            task_name="test",
            has_definition=True,
            has_db_record=True,
            additional_prompt="Focus here",
        )

        assert response.additional_prompt == "Focus here"

    def test_create_request_default_none(self) -> None:
        """ScheduleCreateRequest should default additional_prompt to None."""
        request = ScheduleCreateRequest(task_name="test")

        assert request.additional_prompt is None

    def test_create_request_with_additional_prompt(self) -> None:
        """ScheduleCreateRequest should accept additional_prompt."""
        request = ScheduleCreateRequest(
            task_name="test",
            additional_prompt="Focus on auth",
        )

        assert request.additional_prompt == "Focus on auth"

    def test_create_request_max_length(self) -> None:
        """ScheduleCreateRequest should reject additional_prompt exceeding max_length."""
        with pytest.raises(ValueError):
            ScheduleCreateRequest(
                task_name="test",
                additional_prompt="x" * 10001,
            )

    def test_update_request_default_none(self) -> None:
        """ScheduleUpdateRequest should default additional_prompt to None."""
        request = ScheduleUpdateRequest()

        assert request.additional_prompt is None

    def test_update_request_with_additional_prompt(self) -> None:
        """ScheduleUpdateRequest should accept additional_prompt."""
        request = ScheduleUpdateRequest(additional_prompt="New focus")

        assert request.additional_prompt == "New focus"

    def test_update_request_empty_string_clears(self) -> None:
        """ScheduleUpdateRequest should accept empty string to clear."""
        request = ScheduleUpdateRequest(additional_prompt="")

        assert request.additional_prompt == ""
