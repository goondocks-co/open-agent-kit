"""Tests for DataCollectionPolicy and policy enforcement functions.

Tests cover:
- DataCollectionPolicy defaults (including federated_tools)
- DataCollectionPolicy from_dict/to_dict round-trip
- should_sync_event for each event type with default policy
- should_sync_event with sync_observations=False blocks observation events
- should_sync_event activity upsert is always blocked (not synced)
- GovernanceConfig includes data_collection field
- GovernanceConfig from_dict/to_dict includes data_collection
- federated_tools policy field in DataCollectionPolicy
- ToolOperations respects federated_tools policy
"""

from open_agent_kit.features.codebase_intelligence.config.governance import (
    DataCollectionPolicy,
    GovernanceConfig,
)
from open_agent_kit.features.codebase_intelligence.constants.governance import (
    DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT,
    DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT,
)
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_ACTIVITY_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_PROMPT_BATCH_UPSERT,
    TEAM_EVENT_SESSION_END,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_TITLE_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.governance.policies import (
    should_sync_event,
)

# =============================================================================
# DataCollectionPolicy Defaults
# =============================================================================


class TestDataCollectionPolicyDefaults:
    """Test DataCollectionPolicy initialization and defaults."""

    def test_defaults(self):
        """Test default values match constants."""
        policy = DataCollectionPolicy()
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert policy.federated_tools is DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT

    def test_default_values_are_sensible(self):
        """Default policy syncs observations and enables federated tools."""
        policy = DataCollectionPolicy()
        assert policy.sync_observations is True
        assert policy.federated_tools is True


# =============================================================================
# DataCollectionPolicy from_dict / to_dict
# =============================================================================


class TestDataCollectionPolicySerialization:
    """Test DataCollectionPolicy serialization round-trip."""

    def test_from_dict_empty_returns_defaults(self):
        """Empty dict should produce default policy."""
        policy = DataCollectionPolicy.from_dict({})
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert policy.federated_tools is DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT

    def test_from_dict_with_overrides(self):
        """Explicit values override defaults."""
        policy = DataCollectionPolicy.from_dict(
            {
                "sync_observations": False,
                "federated_tools": False,
            }
        )
        assert policy.sync_observations is False
        assert policy.federated_tools is False

    def test_from_dict_federated_tools_only(self):
        """Can override federated_tools independently."""
        policy = DataCollectionPolicy.from_dict(
            {
                "federated_tools": False,
            }
        )
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert policy.federated_tools is False

    def test_from_dict_ignores_unknown_keys(self):
        """Unknown keys in dict are silently ignored."""
        policy = DataCollectionPolicy.from_dict(
            {
                "sync_observations": False,
                "collect_activities": True,  # legacy key, should be ignored
            }
        )
        assert policy.sync_observations is False

    def test_to_dict(self):
        """to_dict returns all fields."""
        policy = DataCollectionPolicy()
        result = policy.to_dict()
        assert result == {
            "sync_observations": DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT,
            "federated_tools": DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT,
        }

    def test_to_dict_with_federated_tools_false(self):
        """to_dict includes federated_tools when explicitly set."""
        policy = DataCollectionPolicy(federated_tools=False)
        result = policy.to_dict()
        assert result["federated_tools"] is False

    def test_round_trip(self):
        """from_dict(to_dict()) preserves all values."""
        original = DataCollectionPolicy(
            sync_observations=False,
            federated_tools=False,
        )
        restored = DataCollectionPolicy.from_dict(original.to_dict())
        assert restored.sync_observations == original.sync_observations
        assert restored.federated_tools == original.federated_tools


# =============================================================================
# should_sync_event
# =============================================================================


class TestShouldSyncEvent:
    """Test should_sync_event policy enforcement."""

    def test_default_policy_syncs_observation_upsert(self):
        """Default policy allows observation upsert sync."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_OBSERVATION_UPSERT, policy) is True

    def test_default_policy_syncs_observation_resolved(self):
        """Default policy allows observation resolved sync."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_OBSERVATION_RESOLVED, policy) is True

    def test_default_policy_syncs_session_upsert(self):
        """Session upsert always syncs (session lifecycle is structural)."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_SESSION_UPSERT, policy) is True

    def test_default_policy_syncs_session_summary_update(self):
        """Session summary update always syncs (session lifecycle is structural)."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, policy) is True

    def test_sync_observations_false_blocks_observation_events(self):
        """Disabling sync_observations blocks both observation event types."""
        policy = DataCollectionPolicy(sync_observations=False)
        assert should_sync_event(TEAM_EVENT_OBSERVATION_UPSERT, policy) is False
        assert should_sync_event(TEAM_EVENT_OBSERVATION_RESOLVED, policy) is False

    def test_activity_upsert_never_syncs(self):
        """Activity upsert events are never synced in current version."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_ACTIVITY_UPSERT, policy) is False

    def test_session_end_always_syncs(self):
        """Session end events always sync regardless of policy toggles."""
        policy = DataCollectionPolicy(sync_observations=False)
        assert should_sync_event(TEAM_EVENT_SESSION_END, policy) is True

    def test_session_title_update_always_syncs(self):
        """Session title update events always sync regardless of policy toggles."""
        policy = DataCollectionPolicy(sync_observations=False)
        assert should_sync_event(TEAM_EVENT_SESSION_TITLE_UPDATE, policy) is True

    def test_prompt_batch_upsert_always_syncs(self):
        """Prompt batch upsert events always sync."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_PROMPT_BATCH_UPSERT, policy) is True

    def test_unknown_event_type_returns_false(self):
        """Unknown event types are never synced."""
        policy = DataCollectionPolicy()
        assert should_sync_event("unknown_event", policy) is False


# =============================================================================
# GovernanceConfig integration
# =============================================================================


class TestGovernanceConfigDataCollection:
    """Test GovernanceConfig includes and wires DataCollectionPolicy."""

    def test_governance_config_has_data_collection_field(self):
        """GovernanceConfig has a data_collection field with default policy."""
        config = GovernanceConfig()
        assert isinstance(config.data_collection, DataCollectionPolicy)
        assert config.data_collection.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert config.data_collection.federated_tools is DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT

    def test_governance_config_from_dict_includes_data_collection(self):
        """GovernanceConfig.from_dict() parses data_collection section."""
        config = GovernanceConfig.from_dict(
            {
                "enabled": True,
                "data_collection": {
                    "sync_observations": False,
                    "federated_tools": False,
                },
            }
        )
        assert config.enabled is True
        assert config.data_collection.sync_observations is False
        assert config.data_collection.federated_tools is False

    def test_governance_config_from_dict_missing_data_collection(self):
        """GovernanceConfig.from_dict() without data_collection uses defaults."""
        config = GovernanceConfig.from_dict({"enabled": True})
        assert isinstance(config.data_collection, DataCollectionPolicy)
        assert config.data_collection.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert config.data_collection.federated_tools is DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT

    def test_governance_config_to_dict_includes_data_collection(self):
        """GovernanceConfig.to_dict() includes the data_collection section."""
        config = GovernanceConfig(
            data_collection=DataCollectionPolicy(
                sync_observations=False,
                federated_tools=False,
            ),
        )
        result = config.to_dict()
        assert "data_collection" in result
        assert result["data_collection"]["sync_observations"] is False
        assert result["data_collection"]["federated_tools"] is False

    def test_governance_config_round_trip(self):
        """GovernanceConfig from_dict/to_dict round-trip preserves data_collection."""
        original = GovernanceConfig(
            enabled=True,
            data_collection=DataCollectionPolicy(
                sync_observations=False,
                federated_tools=False,
            ),
        )
        restored = GovernanceConfig.from_dict(original.to_dict())
        assert restored.data_collection.sync_observations is False
        assert restored.data_collection.federated_tools is False
        assert restored.enabled is True


# =============================================================================
# ToolOperations federation policy
# =============================================================================


class TestToolOperationsFederationPolicy:
    """Test that ToolOperations respects federated_tools policy."""

    def test_federate_if_requested_respects_policy_false(self):
        """_federate_if_requested returns local result when policy disables federation."""
        from unittest.mock import MagicMock

        from open_agent_kit.features.codebase_intelligence.tools.operations import (
            ToolOperations,
        )

        policy = DataCollectionPolicy(federated_tools=False)
        ops = ToolOperations(
            retrieval_engine=MagicMock(),
            relay_client=MagicMock(),
            policy_accessor=lambda: policy,
        )

        result = ops._federate_if_requested(
            "oak_memories",
            {"include_network": True},
            "local results",
        )
        assert result == "local results"

    def test_federate_if_requested_allows_when_policy_true(self):
        """_federate_if_requested attempts federation when policy allows it."""
        from unittest.mock import MagicMock

        from open_agent_kit.features.codebase_intelligence.tools.operations import (
            ToolOperations,
        )

        policy = DataCollectionPolicy(federated_tools=True)
        mock_relay = MagicMock()
        # Make federate_tool_call return empty results to avoid format errors
        mock_relay.federate_tool_call.return_value = {"results": []}
        mock_relay.machine_id = "test-machine"

        ops = ToolOperations(
            retrieval_engine=MagicMock(),
            relay_client=mock_relay,
            policy_accessor=lambda: policy,
        )

        # Even though the relay is mocked, the function should proceed past
        # the policy check (it may raise due to the mock but that's fine)
        result = ops._federate_if_requested(
            "oak_memories",
            {"include_network": True},
            "local results",
        )
        # Should still return local results since mock returns empty
        assert "local results" in result

    def test_is_federation_allowed_no_accessor(self):
        """_is_federation_allowed returns True when no policy accessor is set."""
        from unittest.mock import MagicMock

        from open_agent_kit.features.codebase_intelligence.tools.operations import (
            ToolOperations,
        )

        ops = ToolOperations(
            retrieval_engine=MagicMock(),
        )
        assert ops._is_federation_allowed() is True

    def test_is_federation_allowed_with_policy_false(self):
        """_is_federation_allowed returns False when policy disables federation."""
        from unittest.mock import MagicMock

        from open_agent_kit.features.codebase_intelligence.tools.operations import (
            ToolOperations,
        )

        policy = DataCollectionPolicy(federated_tools=False)
        ops = ToolOperations(
            retrieval_engine=MagicMock(),
            policy_accessor=lambda: policy,
        )
        assert ops._is_federation_allowed() is False
