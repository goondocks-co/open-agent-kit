"""Tests for power-state-aware background processing cycle.

Covers:
- _evaluate_and_run_cycle(): correct phases run per power state
- _on_power_transition(): logging, backup triggers, file watcher control
- schedule_background_processing(): timer stops on deep sleep
- _trigger_transition_backup(): respects auto_enabled config
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
    ActivityProcessor,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    POWER_ACTIVE_INTERVAL,
    POWER_DEEP_SLEEP_THRESHOLD,
    POWER_IDLE_THRESHOLD,
    POWER_SLEEP_INTERVAL,
    POWER_SLEEP_THRESHOLD,
    POWER_STATE_ACTIVE,
    POWER_STATE_DEEP_SLEEP,
    POWER_STATE_IDLE,
    POWER_STATE_SLEEP,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState


@pytest.fixture()
def mock_stores() -> tuple[MagicMock, MagicMock]:
    """Create mock activity store and vector store."""
    activity_store = MagicMock()
    vector_store = MagicMock()
    return activity_store, vector_store


@pytest.fixture()
def processor(mock_stores: tuple[MagicMock, MagicMock]) -> ActivityProcessor:
    """Create an ActivityProcessor with fully mocked dependencies."""
    activity_store, vector_store = mock_stores
    return ActivityProcessor(
        activity_store=activity_store,
        vector_store=vector_store,
        summarizer=MagicMock(),
        prompt_config=MagicMock(),
        project_root="/test/project",
        context_tokens=4096,
    )


def _make_state(idle_seconds: float | None = None) -> DaemonState:
    """Create a DaemonState with last_hook_activity set to *idle_seconds* ago.

    Also sets ``start_time`` so the fallback path (no hook activity)
    can compute idle duration from daemon startup.
    """
    state = DaemonState()
    state.power_state = POWER_STATE_ACTIVE
    state.start_time = time.time()  # needed for idle fallback
    if idle_seconds is not None:
        state.last_hook_activity = time.time() - idle_seconds
    return state


# ==========================================================================
# _evaluate_and_run_cycle()
# ==========================================================================


class TestEvaluateCycleActive:
    """ACTIVE state: all phases run."""

    def test_evaluate_cycle_active_runs_all_phases(self, processor: ActivityProcessor) -> None:
        """last_hook_activity = now -> returns (ACTIVE, 60) and calls run_background_cycle."""
        state = _make_state(idle_seconds=0)
        accessor = lambda: state  # noqa: E731

        with patch.object(processor, "run_background_cycle") as mock_cycle:
            result_state, interval = processor._evaluate_and_run_cycle(
                accessor, POWER_ACTIVE_INTERVAL
            )

        assert result_state == POWER_STATE_ACTIVE
        assert interval == POWER_ACTIVE_INTERVAL
        mock_cycle.assert_called_once()


class TestEvaluateCycleIdle:
    """IDLE state: maintenance + lightweight indexing (phases 1-2, 5)."""

    def test_evaluate_cycle_idle_runs_maintenance_and_indexing(
        self, processor: ActivityProcessor
    ) -> None:
        """last_hook_activity = 6 min ago -> returns (IDLE, 60) and runs phases 1-2, 5."""
        idle_seconds = POWER_IDLE_THRESHOLD + 60  # 6 minutes
        state = _make_state(idle_seconds=idle_seconds)
        accessor = lambda: state  # noqa: E731

        with (
            patch.object(processor, "run_background_cycle") as mock_full,
            patch.object(processor, "_bg_recover_stuck_data") as mock_phase1,
            patch.object(processor, "_bg_recover_stale_sessions") as mock_phase2,
            patch.object(processor, "_bg_cleanup_and_summarize") as mock_phase3,
            patch.object(processor, "_bg_process_pending") as mock_phase4,
            patch.object(processor, "_bg_index_and_title") as mock_phase5,
        ):
            result_state, interval = processor._evaluate_and_run_cycle(
                accessor, POWER_ACTIVE_INTERVAL
            )

        assert result_state == POWER_STATE_IDLE
        assert interval == POWER_ACTIVE_INTERVAL
        mock_full.assert_not_called()
        mock_phase1.assert_called_once()
        mock_phase2.assert_called_once()
        mock_phase3.assert_not_called()
        mock_phase4.assert_not_called()
        mock_phase5.assert_called_once()


class TestEvaluateCycleSleep:
    """SLEEP state: recovery + lightweight indexing (phases 1, 5)."""

    def test_evaluate_cycle_sleep_runs_recovery_and_indexing(
        self, processor: ActivityProcessor
    ) -> None:
        """last_hook_activity = 35 min ago -> returns (SLEEP, 300) and runs phases 1, 5."""
        idle_seconds = POWER_SLEEP_THRESHOLD + 300  # 35 minutes
        state = _make_state(idle_seconds=idle_seconds)
        accessor = lambda: state  # noqa: E731

        with (
            patch.object(processor, "run_background_cycle") as mock_full,
            patch.object(processor, "_bg_recover_stuck_data") as mock_phase1,
            patch.object(processor, "_bg_recover_stale_sessions") as mock_phase2,
            patch.object(processor, "_bg_index_and_title") as mock_phase5,
        ):
            result_state, interval = processor._evaluate_and_run_cycle(
                accessor, POWER_ACTIVE_INTERVAL
            )

        assert result_state == POWER_STATE_SLEEP
        assert interval == POWER_SLEEP_INTERVAL
        mock_full.assert_not_called()
        mock_phase1.assert_called_once()
        mock_phase2.assert_not_called()
        mock_phase5.assert_called_once()


class TestEvaluateCycleDeepSleep:
    """DEEP_SLEEP state: no work, timer stops."""

    def test_evaluate_cycle_deep_sleep_runs_nothing(self, processor: ActivityProcessor) -> None:
        """last_hook_activity = 100 min ago -> returns (DEEP_SLEEP, 0) and runs no phases."""
        idle_seconds = POWER_DEEP_SLEEP_THRESHOLD + 600  # 100 minutes
        state = _make_state(idle_seconds=idle_seconds)
        accessor = lambda: state  # noqa: E731

        with (
            patch.object(processor, "run_background_cycle") as mock_full,
            patch.object(processor, "_bg_recover_stuck_data") as mock_phase1,
            patch.object(processor, "_bg_recover_stale_sessions") as mock_phase2,
        ):
            result_state, interval = processor._evaluate_and_run_cycle(
                accessor, POWER_ACTIVE_INTERVAL
            )

        assert result_state == POWER_STATE_DEEP_SLEEP
        assert interval == 0
        mock_full.assert_not_called()
        mock_phase1.assert_not_called()
        mock_phase2.assert_not_called()


class TestEvaluateCycleNoStateAccessor:
    """No state accessor -> defaults to ACTIVE."""

    def test_evaluate_cycle_no_state_accessor_defaults_active(
        self, processor: ActivityProcessor
    ) -> None:
        """state_accessor=None -> runs all phases (ACTIVE behavior)."""
        with patch.object(processor, "run_background_cycle") as mock_cycle:
            result_state, interval = processor._evaluate_and_run_cycle(None, POWER_ACTIVE_INTERVAL)

        assert result_state == POWER_STATE_ACTIVE
        assert interval == POWER_ACTIVE_INTERVAL
        mock_cycle.assert_called_once()


class TestEvaluateCycleFallbackToStartTime:
    """When no hooks have fired, idle duration falls back to start_time."""

    def test_evaluate_cycle_no_hook_activity_uses_start_time(
        self, processor: ActivityProcessor
    ) -> None:
        """last_hook_activity=None, start_time=10 min ago -> IDLE (not ACTIVE)."""
        state = DaemonState()
        state.power_state = POWER_STATE_ACTIVE
        state.start_time = time.time() - (POWER_IDLE_THRESHOLD + 300)  # 10 min ago
        # Intentionally do NOT set last_hook_activity
        accessor = lambda: state  # noqa: E731

        with (
            patch.object(processor, "run_background_cycle") as mock_full,
            patch.object(processor, "_bg_recover_stuck_data") as mock_phase1,
            patch.object(processor, "_bg_recover_stale_sessions") as mock_phase2,
            patch.object(processor, "_bg_index_and_title") as mock_phase5,
        ):
            result_state, interval = processor._evaluate_and_run_cycle(
                accessor, POWER_ACTIVE_INTERVAL
            )

        assert result_state == POWER_STATE_IDLE
        assert interval == POWER_ACTIVE_INTERVAL
        mock_full.assert_not_called()
        mock_phase1.assert_called_once()
        mock_phase2.assert_called_once()
        mock_phase5.assert_called_once()


# ==========================================================================
# _on_power_transition()
# ==========================================================================


class TestPowerTransitionLogging:
    """Transition logging."""

    def test_transition_active_to_idle_logged(self, processor: ActivityProcessor) -> None:
        """Assert logger.info called with 'Power state: active -> idle'."""
        state = _make_state(idle_seconds=POWER_IDLE_THRESHOLD + 10)

        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.processor.core.logger"
        ) as mock_logger:
            processor._on_power_transition(state, POWER_STATE_ACTIVE, POWER_STATE_IDLE)

        # Check the info call contains the transition text
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "Power state: active -> idle" in log_message


class TestPowerTransitionBackup:
    """Backup triggers on sleep transitions."""

    def test_transition_to_sleep_triggers_backup(self, processor: ActivityProcessor) -> None:
        """Assert _trigger_transition_backup called on entry to SLEEP."""
        state = _make_state(idle_seconds=POWER_SLEEP_THRESHOLD + 10)

        with patch.object(processor, "_trigger_transition_backup") as mock_backup:
            processor._on_power_transition(state, POWER_STATE_IDLE, POWER_STATE_SLEEP)

        mock_backup.assert_called_once_with(state)

    def test_transition_to_deep_sleep_triggers_backup(self, processor: ActivityProcessor) -> None:
        """Assert _trigger_transition_backup called on entry to DEEP_SLEEP."""
        state = _make_state(idle_seconds=POWER_DEEP_SLEEP_THRESHOLD + 10)

        with patch.object(processor, "_trigger_transition_backup") as mock_backup:
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        mock_backup.assert_called_once_with(state)

    def test_transition_idle_to_active_no_backup(self, processor: ActivityProcessor) -> None:
        """Going back to ACTIVE does NOT trigger backup."""
        state = _make_state(idle_seconds=0)

        with patch.object(processor, "_trigger_transition_backup") as mock_backup:
            processor._on_power_transition(state, POWER_STATE_IDLE, POWER_STATE_ACTIVE)

        mock_backup.assert_not_called()


class TestPowerTransitionFileWatcher:
    """File watcher management on deep sleep transitions."""

    def test_transition_to_deep_sleep_stops_file_watcher(
        self, processor: ActivityProcessor
    ) -> None:
        """Mock file_watcher.stop() -> assert called on entry to DEEP_SLEEP."""
        state = _make_state(idle_seconds=POWER_DEEP_SLEEP_THRESHOLD + 10)
        mock_watcher = MagicMock()
        state.file_watcher = mock_watcher

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        mock_watcher.stop.assert_called_once()

    def test_wake_from_deep_sleep_restarts_file_watcher(self, processor: ActivityProcessor) -> None:
        """Transition DEEP_SLEEP -> ACTIVE -> assert file_watcher.start() called."""
        state = _make_state(idle_seconds=0)
        mock_watcher = MagicMock()
        state.file_watcher = mock_watcher

        processor._on_power_transition(state, POWER_STATE_DEEP_SLEEP, POWER_STATE_ACTIVE)

        mock_watcher.start.assert_called_once()


# ==========================================================================
# _trigger_transition_backup()
# ==========================================================================


class TestTransitionBackupConfig:
    """Backup respects auto_enabled config."""

    def test_transition_backup_respects_auto_enabled(self, processor: ActivityProcessor) -> None:
        """auto_enabled=False -> no backup on transition."""
        state = DaemonState()
        state.project_root = MagicMock()

        mock_config = MagicMock()
        mock_config.backup.auto_enabled = False
        state._ci_config = mock_config

        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.store.backup.create_backup"
        ) as mock_create:
            processor._trigger_transition_backup(state)

        mock_create.assert_not_called()


# ==========================================================================
# schedule_background_processing() timer behavior
# ==========================================================================


class TestScheduleStopsOnDeepSleep:
    """Verify timer is NOT rescheduled when deep sleep is reached."""

    def test_schedule_background_processing_stops_on_deep_sleep(
        self, processor: ActivityProcessor
    ) -> None:
        """When _evaluate_and_run_cycle returns interval=0, no new Timer is created."""
        # Make _evaluate_and_run_cycle return DEEP_SLEEP with interval 0
        with patch.object(
            processor,
            "_evaluate_and_run_cycle",
            return_value=(POWER_STATE_DEEP_SLEEP, 0),
        ):
            with patch("threading.Timer") as MockTimer:
                mock_timer_instance = MagicMock()
                MockTimer.return_value = mock_timer_instance

                processor.schedule_background_processing(
                    interval_seconds=POWER_ACTIVE_INTERVAL,
                    state_accessor=lambda: _make_state(
                        idle_seconds=POWER_DEEP_SLEEP_THRESHOLD + 600
                    ),
                )

                # The initial timer is created by schedule_background_processing
                assert MockTimer.call_count == 1

                # Simulate the timer firing by calling the callback
                callback = MockTimer.call_args[0][1]
                callback()

                # After callback, no NEW timer should be created
                # (still just the 1 initial timer, no second one)
                assert MockTimer.call_count == 1
