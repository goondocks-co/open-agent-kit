"""Tests for power-state-aware team subsystem lifecycle.

Covers:
- on_power_transition(): team sync worker stop/start on sleep/wake
- on_power_transition(): cloud relay disconnect/reconnect on deep sleep/wake
- keep_relay_alive=True bypasses team subsystem suspension
- Credential cache/clear round-trip
- _disconnect_relay_for_power(): caches credentials before disconnect
- _restart_team_subsystems_on_wake(): restarts worker + relay from cache
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.team.constants import (
    POWER_STATE_ACTIVE,
    POWER_STATE_DEEP_SLEEP,
    POWER_STATE_SLEEP,
)
from open_agent_kit.features.team.constants.team import (
    TEAM_LOG_KEEP_RELAY_ALIVE,
    TEAM_LOG_RELAY_POWER_DISCONNECT,
    TEAM_LOG_SYNC_WORKER_POWER_STOP,
)
from open_agent_kit.features.team.daemon.state import (
    DaemonState,
    RelayCredentials,
)


@pytest.fixture()
def mock_stores() -> tuple[MagicMock, MagicMock]:
    """Create mock activity store and vector store."""
    activity_store = MagicMock()
    vector_store = MagicMock()
    return activity_store, vector_store


@pytest.fixture()
def processor(mock_stores: tuple[MagicMock, MagicMock]):
    """Create an ActivityProcessor with fully mocked dependencies."""
    from open_agent_kit.features.team.activity.processor.core import (
        ActivityProcessor,
    )

    activity_store, vector_store = mock_stores
    return ActivityProcessor(
        activity_store=activity_store,
        vector_store=vector_store,
        summarizer=MagicMock(),
        prompt_config=MagicMock(),
        project_root="/test/project",
        context_tokens=4096,
    )


def _make_state(
    idle_seconds: float = 0,
    keep_relay_alive: bool = False,
) -> DaemonState:
    """Create a DaemonState with configurable idle duration and team config.

    Sets ``project_root`` to a dummy path so the ``ci_config`` property
    returns the mock (the property short-circuits to None when project_root
    is unset).  ``_ci_config_mtime`` stays at the default 0.0, which matches
    ``_get_config_mtime()`` for a non-existent path, preventing a reload.
    """
    state = DaemonState()
    state.power_state = POWER_STATE_ACTIVE
    state.start_time = time.time()
    state.last_hook_activity = time.time() - idle_seconds

    # project_root must be set for ci_config property to return _ci_config
    state.project_root = Path("/test/project")

    # Set up a mock ci_config with keep_relay_alive
    mock_config = MagicMock()
    mock_config.team.keep_relay_alive = keep_relay_alive
    mock_config.backup.auto_enabled = False
    mock_config.governance.enabled = False
    state._ci_config = mock_config
    # _ci_config_mtime=0.0 matches _get_config_mtime() for non-existent path

    return state


# ==========================================================================
# Entering SLEEP — team sync worker
# ==========================================================================


class TestSleepStopsTeamSyncWorker:
    """SLEEP stops the team sync worker (unless keep_relay_alive)."""

    def test_sleep_stops_sync_worker(self, processor) -> None:
        """Transition to SLEEP calls team_sync_worker.stop()."""
        state = _make_state()
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_ACTIVE, POWER_STATE_SLEEP)

        mock_worker.stop.assert_called_once()

    def test_sleep_does_not_disconnect_relay(self, processor) -> None:
        """Transition to SLEEP does NOT disconnect the cloud relay."""
        state = _make_state()
        mock_client = MagicMock()
        state.cloud_relay_client = mock_client

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_ACTIVE, POWER_STATE_SLEEP)

        # Relay client should still be set (not disconnected)
        assert state.cloud_relay_client is mock_client

    def test_sleep_skips_worker_stop_when_keep_relay_alive(self, processor) -> None:
        """keep_relay_alive=True skips stopping the sync worker on SLEEP."""
        state = _make_state(keep_relay_alive=True)
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        with (
            patch.object(processor, "_trigger_transition_backup"),
            patch("open_agent_kit.features.team.activity.processor.power.logger") as mock_logger,
        ):
            processor._on_power_transition(state, POWER_STATE_ACTIVE, POWER_STATE_SLEEP)

        mock_worker.stop.assert_not_called()
        # Should log the keep_relay_alive message
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any(TEAM_LOG_KEEP_RELAY_ALIVE in msg for msg in log_messages)


# ==========================================================================
# Entering DEEP_SLEEP — both subsystems
# ==========================================================================


class TestDeepSleepStopsTeamSubsystems:
    """DEEP_SLEEP stops both sync worker and cloud relay."""

    def test_deep_sleep_stops_sync_worker(self, processor) -> None:
        """Transition to DEEP_SLEEP calls team_sync_worker.stop()."""
        state = _make_state()
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        mock_worker.stop.assert_called_once()

    def test_deep_sleep_disconnects_relay(self, processor) -> None:
        """Transition to DEEP_SLEEP disconnects cloud relay and sets it to None."""
        state = _make_state()
        mock_client = MagicMock()
        mock_client._worker_url = "https://relay.example.com"
        mock_client._token = "test-token"
        mock_client._daemon_port = 8080
        mock_client._machine_id = "test-machine"
        state.cloud_relay_client = mock_client

        with (
            patch.object(processor, "_trigger_transition_backup"),
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future"),
        ):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        assert state.cloud_relay_client is None

    def test_deep_sleep_caches_credentials_before_disconnect(self, processor) -> None:
        """Relay credentials are cached before disconnecting on DEEP_SLEEP."""
        state = _make_state()
        mock_client = MagicMock()
        mock_client._worker_url = "https://relay.example.com"
        mock_client._token = "test-token"
        mock_client._daemon_port = 9090
        mock_client._machine_id = "machine-42"
        state.cloud_relay_client = mock_client

        with (
            patch.object(processor, "_trigger_transition_backup"),
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future"),
        ):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        assert state._relay_credentials is not None
        assert state._relay_credentials.worker_url == "https://relay.example.com"
        assert state._relay_credentials.token == "test-token"
        assert state._relay_credentials.daemon_port == 9090
        assert state._relay_credentials.machine_id == "machine-42"

    def test_deep_sleep_skips_both_when_keep_relay_alive(self, processor) -> None:
        """keep_relay_alive=True skips stopping worker AND disconnecting relay."""
        state = _make_state(keep_relay_alive=True)
        mock_worker = MagicMock()
        mock_client = MagicMock()
        state.team_sync_worker = mock_worker
        state.cloud_relay_client = mock_client

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        mock_worker.stop.assert_not_called()
        assert state.cloud_relay_client is mock_client  # not disconnected

    def test_deep_sleep_still_stops_file_watcher_even_with_keep_relay_alive(
        self, processor
    ) -> None:
        """File watcher is stopped on DEEP_SLEEP regardless of keep_relay_alive."""
        state = _make_state(keep_relay_alive=True)
        mock_watcher = MagicMock()
        state.file_watcher = mock_watcher

        with patch.object(processor, "_trigger_transition_backup"):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        mock_watcher.stop.assert_called_once()


# ==========================================================================
# Waking from SLEEP — restart sync worker only
# ==========================================================================


class TestWakeFromSleep:
    """Waking from SLEEP restarts the sync worker."""

    def test_wake_from_sleep_restarts_sync_worker(self, processor) -> None:
        """Transition SLEEP -> ACTIVE restarts team_sync_worker."""
        state = _make_state()
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_ACTIVE)

        mock_worker.start.assert_called_once()

    def test_wake_from_sleep_does_not_restart_relay(self, processor) -> None:
        """Transition SLEEP -> ACTIVE does NOT touch relay (it was never stopped)."""
        state = _make_state()
        state.cloud_relay_client = None  # no client, as expected

        with patch.object(state, "_restart_team_subsystems_on_wake") as mock_restart:
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_ACTIVE)

        mock_restart.assert_not_called()

    def test_wake_from_sleep_skips_restart_when_keep_relay_alive(self, processor) -> None:
        """keep_relay_alive=True skips restarting worker on wake from SLEEP."""
        state = _make_state(keep_relay_alive=True)
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_ACTIVE)

        mock_worker.start.assert_not_called()


# ==========================================================================
# Waking from DEEP_SLEEP — full restart
# ==========================================================================


class TestWakeFromDeepSleep:
    """Waking from DEEP_SLEEP restarts both subsystems."""

    def test_wake_from_deep_sleep_calls_restart_team_subsystems(self, processor) -> None:
        """Transition DEEP_SLEEP -> ACTIVE calls _restart_team_subsystems_on_wake()."""
        state = _make_state()

        with patch.object(state, "_restart_team_subsystems_on_wake") as mock_restart:
            processor._on_power_transition(state, POWER_STATE_DEEP_SLEEP, POWER_STATE_ACTIVE)

        mock_restart.assert_called_once()

    def test_wake_from_deep_sleep_skips_restart_when_keep_relay_alive(self, processor) -> None:
        """keep_relay_alive=True skips _restart_team_subsystems_on_wake() on wake."""
        state = _make_state(keep_relay_alive=True)

        with patch.object(state, "_restart_team_subsystems_on_wake") as mock_restart:
            processor._on_power_transition(state, POWER_STATE_DEEP_SLEEP, POWER_STATE_ACTIVE)

        mock_restart.assert_not_called()


# ==========================================================================
# _restart_team_subsystems_on_wake() direct tests
# ==========================================================================


class TestRestartTeamSubsystemsOnWake:
    """Direct tests for DaemonState._restart_team_subsystems_on_wake()."""

    def test_restarts_sync_worker(self) -> None:
        """Sync worker's start() is called."""
        state = DaemonState()
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        state._restart_team_subsystems_on_wake()

        mock_worker.start.assert_called_once()

    def test_reconnects_relay_with_cached_credentials(self) -> None:
        """Cloud relay is reconnected using cached credentials."""
        state = DaemonState()
        state.cache_relay_credentials(
            worker_url="https://relay.example.com",
            token="secret-token",
            daemon_port=8080,
            machine_id="machine-1",
        )
        assert state.cloud_relay_client is None

        with (
            patch("open_agent_kit.features.team.cloud_relay.client.CloudRelayClient") as MockClient,
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future") as mock_ensure,
        ):
            mock_instance = MagicMock()
            MockClient.return_value = mock_instance

            state._restart_team_subsystems_on_wake()

        assert state.cloud_relay_client is mock_instance
        mock_ensure.assert_called_once()

    def test_no_reconnect_without_cached_credentials(self) -> None:
        """No relay reconnect if no credentials are cached."""
        state = DaemonState()
        state.cloud_relay_client = None
        # No credentials cached

        with patch(
            "open_agent_kit.features.team.cloud_relay.client.CloudRelayClient"
        ) as MockClient:
            state._restart_team_subsystems_on_wake()

        MockClient.assert_not_called()

    def test_no_reconnect_if_client_already_exists(self) -> None:
        """No relay reconnect if cloud_relay_client is already set."""
        state = DaemonState()
        state.cache_relay_credentials("url", "token", 8080, "machine")
        existing_client = MagicMock()
        state.cloud_relay_client = existing_client

        with patch(
            "open_agent_kit.features.team.cloud_relay.client.CloudRelayClient"
        ) as MockClient:
            state._restart_team_subsystems_on_wake()

        MockClient.assert_not_called()
        assert state.cloud_relay_client is existing_client


# ==========================================================================
# Credential cache/clear round-trip
# ==========================================================================


class TestRelayCredentialCaching:
    """Tests for cache_relay_credentials / clear_relay_credentials."""

    def test_cache_stores_credentials(self) -> None:
        """cache_relay_credentials stores all four fields."""
        state = DaemonState()
        state.cache_relay_credentials("https://w.com", "tok", 9090, "m-1")

        creds = state._relay_credentials
        assert creds is not None
        assert creds.worker_url == "https://w.com"
        assert creds.token == "tok"
        assert creds.daemon_port == 9090
        assert creds.machine_id == "m-1"

    def test_clear_removes_credentials(self) -> None:
        """clear_relay_credentials sets _relay_credentials to None."""
        state = DaemonState()
        state.cache_relay_credentials("url", "tok", 8080, "m")
        assert state._relay_credentials is not None

        state.clear_relay_credentials()
        assert state._relay_credentials is None

    def test_reset_clears_credentials(self) -> None:
        """DaemonState.reset() clears cached relay credentials."""
        state = DaemonState()
        state.cache_relay_credentials("url", "tok", 8080, "m")
        state.reset()
        assert state._relay_credentials is None

    def test_relay_credentials_dataclass_fields(self) -> None:
        """RelayCredentials has all expected fields."""
        creds = RelayCredentials(
            worker_url="https://example.com",
            token="abc123",
            daemon_port=7777,
            machine_id="host-1",
        )
        assert creds.worker_url == "https://example.com"
        assert creds.token == "abc123"
        assert creds.daemon_port == 7777
        assert creds.machine_id == "host-1"


# ==========================================================================
# _disconnect_relay_for_power() direct tests
# ==========================================================================


class TestDisconnectRelayForPower:
    """Direct tests for _disconnect_relay_for_power helper."""

    def test_caches_credentials_from_client(self) -> None:
        """Reads client attributes and caches them before disconnect."""
        from open_agent_kit.features.team.activity.processor.power import (
            _disconnect_relay_for_power,
        )

        state = DaemonState()
        mock_client = MagicMock()
        mock_client._worker_url = "https://relay.test"
        mock_client._token = "t"
        mock_client._daemon_port = 1234
        mock_client._machine_id = "m"
        state.cloud_relay_client = mock_client

        with (
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future"),
        ):
            _disconnect_relay_for_power(state)

        assert state._relay_credentials is not None
        assert state._relay_credentials.worker_url == "https://relay.test"
        assert state.cloud_relay_client is None

    def test_noop_when_no_client(self) -> None:
        """Does nothing if cloud_relay_client is None."""
        from open_agent_kit.features.team.activity.processor.power import (
            _disconnect_relay_for_power,
        )

        state = DaemonState()
        state.cloud_relay_client = None

        _disconnect_relay_for_power(state)

        assert state._relay_credentials is None

    def test_skips_caching_when_client_has_no_url(self) -> None:
        """Does not cache if client._worker_url is None."""
        from open_agent_kit.features.team.activity.processor.power import (
            _disconnect_relay_for_power,
        )

        state = DaemonState()
        mock_client = MagicMock()
        mock_client._worker_url = None
        mock_client._token = "t"
        mock_client._daemon_port = 1234
        mock_client._machine_id = "m"
        state.cloud_relay_client = mock_client

        with (
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future"),
        ):
            _disconnect_relay_for_power(state)

        assert state._relay_credentials is None
        assert state.cloud_relay_client is None


# ==========================================================================
# _stop_team_sync_worker() direct tests
# ==========================================================================


class TestStopTeamSyncWorker:
    """Direct tests for _stop_team_sync_worker helper."""

    def test_calls_stop_on_worker(self) -> None:
        """Calls worker.stop() when worker is set."""
        from open_agent_kit.features.team.activity.processor.power import (
            _stop_team_sync_worker,
        )

        state = DaemonState()
        mock_worker = MagicMock()
        state.team_sync_worker = mock_worker

        _stop_team_sync_worker(state)

        mock_worker.stop.assert_called_once()

    def test_noop_when_no_worker(self) -> None:
        """Does nothing if team_sync_worker is None."""
        from open_agent_kit.features.team.activity.processor.power import (
            _stop_team_sync_worker,
        )

        state = DaemonState()
        state.team_sync_worker = None

        _stop_team_sync_worker(state)  # should not raise

    def test_handles_worker_stop_error(self) -> None:
        """Catches RuntimeError from worker.stop() without raising."""
        from open_agent_kit.features.team.activity.processor.power import (
            _stop_team_sync_worker,
        )

        state = DaemonState()
        mock_worker = MagicMock()
        mock_worker.stop.side_effect = RuntimeError("already stopped")
        state.team_sync_worker = mock_worker

        _stop_team_sync_worker(state)  # should not raise


# ==========================================================================
# Power transition logging
# ==========================================================================


class TestPowerTransitionTeamLogging:
    """Verify team-related log messages during transitions."""

    def test_sleep_logs_sync_worker_stop(self, processor) -> None:
        """Entering SLEEP logs the sync worker stop message."""
        state = _make_state()
        state.team_sync_worker = MagicMock()

        with (
            patch.object(processor, "_trigger_transition_backup"),
            patch("open_agent_kit.features.team.activity.processor.power.logger") as mock_logger,
        ):
            processor._on_power_transition(state, POWER_STATE_ACTIVE, POWER_STATE_SLEEP)

        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any(TEAM_LOG_SYNC_WORKER_POWER_STOP in msg for msg in log_messages)

    def test_deep_sleep_logs_relay_disconnect(self, processor) -> None:
        """Entering DEEP_SLEEP logs the relay disconnect message."""
        state = _make_state()
        mock_client = MagicMock()
        mock_client._worker_url = "https://r.com"
        mock_client._token = "t"
        mock_client._daemon_port = 8080
        mock_client._machine_id = "m"
        state.cloud_relay_client = mock_client

        with (
            patch.object(processor, "_trigger_transition_backup"),
            patch("asyncio.get_event_loop"),
            patch("asyncio.ensure_future"),
            patch("open_agent_kit.features.team.activity.processor.power.logger") as mock_logger,
        ):
            processor._on_power_transition(state, POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP)

        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any(TEAM_LOG_RELAY_POWER_DISCONNECT in msg for msg in log_messages)
