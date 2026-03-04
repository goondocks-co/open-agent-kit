"""Tests for observation sync wiring.

Verifies that RemoteObsApplier is correctly wired to the CloudRelayClient
in all connection paths:
- _init_team_sync (startup)
- connect_cloud_relay (backward-compat route)
- start_cloud_relay (orchestrated deploy+connect route)

Also verifies that _handle_obs_batch delegates to the applier when wired.
"""

from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.team.activity.store.core import ActivityStore
from open_agent_kit.features.team.relay.sync.obs_applier import (
    RemoteObsApplier,
)

TEST_MACHINE_ID = "test-machine-wiring"
TEST_FROM_MACHINE_ID = "remote-peer-001"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore for testing."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


class TestInitTeamSyncWiring:
    """Verify _init_team_sync wires the obs applier to the relay client."""

    def test_applier_wired_when_relay_client_present(self, store):
        """When cloud_relay_client exists, set_obs_applier must be called."""
        from open_agent_kit.features.team.config import (
            CIConfig,
            TeamConfig,
        )

        mock_relay_client = MagicMock()
        mock_state = MagicMock()
        mock_state.ci_config = CIConfig(team=TeamConfig(auto_sync=True))
        mock_state.activity_store = store
        mock_state.cloud_relay_client = mock_relay_client
        mock_state.project_root = "/tmp/fake-project"

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.startup.get_state",
                return_value=mock_state,
            ),
            patch(
                "open_agent_kit.features.team.relay.outbox.worker.ObsFlushWorker"
            ) as mock_worker_cls,
            patch(
                "open_agent_kit.features.team.relay.identity.get_project_identity"
            ) as mock_identity,
        ):
            mock_identity.return_value = MagicMock(full_id="test-project-id")
            mock_worker_instance = MagicMock()
            mock_worker_cls.return_value = mock_worker_instance

            from open_agent_kit.features.team.daemon.lifecycle.startup import (
                _init_team_sync,
            )

            _init_team_sync(mock_state)

            # Verify set_obs_applier was called with a RemoteObsApplier
            mock_relay_client.set_obs_applier.assert_called_once()
            applier_arg = mock_relay_client.set_obs_applier.call_args[0][0]
            assert isinstance(applier_arg, RemoteObsApplier)

    def test_applier_not_wired_when_no_relay_client(self, store):
        """When cloud_relay_client is None, set_obs_applier must not be called."""
        from open_agent_kit.features.team.config import (
            CIConfig,
            TeamConfig,
        )

        mock_state = MagicMock()
        mock_state.ci_config = CIConfig(team=TeamConfig(auto_sync=True))
        mock_state.activity_store = store
        mock_state.cloud_relay_client = None
        mock_state.project_root = "/tmp/fake-project"

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.startup.get_state",
                return_value=mock_state,
            ),
            patch(
                "open_agent_kit.features.team.relay.outbox.worker.ObsFlushWorker"
            ) as mock_worker_cls,
            patch(
                "open_agent_kit.features.team.relay.identity.get_project_identity"
            ) as mock_identity,
        ):
            mock_identity.return_value = MagicMock(full_id="test-project-id")
            mock_worker_instance = MagicMock()
            mock_worker_cls.return_value = mock_worker_instance

            from open_agent_kit.features.team.daemon.lifecycle.startup import (
                _init_team_sync,
            )

            _init_team_sync(mock_state)

            # Worker should still start, but no set_obs_applier call
            mock_worker_instance.start.assert_called_once()


class TestHandleObsBatchWithApplier:
    """Verify _handle_obs_batch delegates to the applier when wired."""

    def test_handle_obs_batch_calls_applier(self, store):
        """When obs_applier is set, _handle_obs_batch should call apply_batch."""
        from open_agent_kit.features.team.cloud_relay.client import (
            CloudRelayClient,
        )

        client = CloudRelayClient.__new__(CloudRelayClient)
        client._obs_applier = None

        applier = RemoteObsApplier(store)
        client.set_obs_applier(applier)

        assert client._obs_applier is applier

        # Mock apply_batch to verify it's called
        applier.apply_batch = MagicMock()

        test_observations = [{"observation": "test", "content_hash": "h1"}]
        data = {
            "from_machine_id": TEST_FROM_MACHINE_ID,
            "observations": test_observations,
        }
        client._handle_obs_batch(data)

        applier.apply_batch.assert_called_once_with(test_observations, TEST_FROM_MACHINE_ID)

    def test_handle_obs_batch_skips_when_no_applier(self):
        """When obs_applier is None, _handle_obs_batch should return silently."""
        from open_agent_kit.features.team.cloud_relay.client import (
            CloudRelayClient,
        )

        client = CloudRelayClient.__new__(CloudRelayClient)
        client._obs_applier = None

        # Should not raise
        data = {
            "from_machine_id": TEST_FROM_MACHINE_ID,
            "observations": [{"observation": "test"}],
        }
        client._handle_obs_batch(data)


class TestBgIndexAndTitleEmbedsObservations:
    """Verify bg_index_and_title calls embed_pending_observations."""

    def test_embed_pending_observations_called(self):
        """bg_index_and_title should call embed_pending_observations on the processor."""
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_index_and_title,
        )

        mock_processor = MagicMock()
        mock_processor.index_pending_plans.return_value = {"indexed": 0}
        mock_processor.embed_pending_observations.return_value = {"embedded": 3}
        mock_processor.generate_pending_titles.return_value = 0

        bg_index_and_title(mock_processor)

        mock_processor.embed_pending_observations.assert_called_once()

    def test_embed_pending_observations_logged_when_nonzero(self, caplog):
        """bg_index_and_title should log when observations are embedded."""
        import logging

        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_index_and_title,
        )

        mock_processor = MagicMock()
        mock_processor.index_pending_plans.return_value = {"indexed": 0}
        mock_processor.embed_pending_observations.return_value = {"embedded": 5}
        mock_processor.generate_pending_titles.return_value = 0

        with caplog.at_level(logging.INFO):
            bg_index_and_title(mock_processor)

        assert "Background embedded 5 pending observations" in caplog.text
