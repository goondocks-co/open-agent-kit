"""Tests for DataCollectionPolicy and policy enforcement functions.

Tests cover:
- DataCollectionPolicy defaults
- DataCollectionPolicy from_dict/to_dict round-trip
- should_sync_event for each event type with default policy
- should_sync_event with sync_observations=False blocks observation events
- should_sync_event with sync_activities=True enables session events
- should_collect_locally for activities with collect_activities=False
- should_collect_locally for prompts with collect_prompts=False
- GovernanceConfig includes data_collection field
- GovernanceConfig from_dict/to_dict includes data_collection
"""

from open_agent_kit.features.codebase_intelligence.config.governance import (
    DataCollectionPolicy,
    GovernanceConfig,
)
from open_agent_kit.features.codebase_intelligence.constants.governance import (
    DATA_COLLECTION_ALLOW_SERVER_LLM_DEFAULT,
    DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT,
    DATA_COLLECTION_COLLECT_PROMPTS_DEFAULT,
    DATA_COLLECTION_SYNC_ACTIVITIES_DEFAULT,
    DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT,
    DATA_COLLECTION_SYNC_PROMPTS_DEFAULT,
)
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.governance.policies import (
    LOCAL_EVENT_TYPE_ACTIVITY,
    LOCAL_EVENT_TYPE_PROMPT,
    should_collect_locally,
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
        assert policy.collect_activities is DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT
        assert policy.collect_prompts is DATA_COLLECTION_COLLECT_PROMPTS_DEFAULT
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert policy.sync_activities is DATA_COLLECTION_SYNC_ACTIVITIES_DEFAULT
        assert policy.sync_prompts is DATA_COLLECTION_SYNC_PROMPTS_DEFAULT
        assert policy.allow_server_llm is DATA_COLLECTION_ALLOW_SERVER_LLM_DEFAULT

    def test_default_values_are_sensible(self):
        """Default policy collects locally, syncs observations only, no server LLM."""
        policy = DataCollectionPolicy()
        assert policy.collect_activities is True
        assert policy.collect_prompts is True
        assert policy.sync_observations is True
        assert policy.sync_activities is False
        assert policy.sync_prompts is False
        assert policy.allow_server_llm is False


# =============================================================================
# DataCollectionPolicy from_dict / to_dict
# =============================================================================


class TestDataCollectionPolicySerialization:
    """Test DataCollectionPolicy serialization round-trip."""

    def test_from_dict_empty_returns_defaults(self):
        """Empty dict should produce default policy."""
        policy = DataCollectionPolicy.from_dict({})
        assert policy.collect_activities is DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT
        assert policy.allow_server_llm is DATA_COLLECTION_ALLOW_SERVER_LLM_DEFAULT

    def test_from_dict_with_overrides(self):
        """Explicit values override defaults."""
        policy = DataCollectionPolicy.from_dict(
            {
                "collect_activities": False,
                "sync_activities": True,
                "allow_server_llm": True,
            }
        )
        assert policy.collect_activities is False
        assert policy.sync_activities is True
        assert policy.allow_server_llm is True
        # Non-overridden fields keep defaults
        assert policy.collect_prompts is DATA_COLLECTION_COLLECT_PROMPTS_DEFAULT
        assert policy.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT

    def test_to_dict(self):
        """to_dict returns all fields."""
        policy = DataCollectionPolicy()
        result = policy.to_dict()
        assert result == {
            "collect_activities": DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT,
            "collect_prompts": DATA_COLLECTION_COLLECT_PROMPTS_DEFAULT,
            "sync_observations": DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT,
            "sync_activities": DATA_COLLECTION_SYNC_ACTIVITIES_DEFAULT,
            "sync_prompts": DATA_COLLECTION_SYNC_PROMPTS_DEFAULT,
            "allow_server_llm": DATA_COLLECTION_ALLOW_SERVER_LLM_DEFAULT,
        }

    def test_round_trip(self):
        """from_dict(to_dict()) preserves all values."""
        original = DataCollectionPolicy(
            collect_activities=False,
            collect_prompts=False,
            sync_observations=False,
            sync_activities=True,
            sync_prompts=True,
            allow_server_llm=True,
        )
        restored = DataCollectionPolicy.from_dict(original.to_dict())
        assert restored.collect_activities == original.collect_activities
        assert restored.collect_prompts == original.collect_prompts
        assert restored.sync_observations == original.sync_observations
        assert restored.sync_activities == original.sync_activities
        assert restored.sync_prompts == original.sync_prompts
        assert restored.allow_server_llm == original.allow_server_llm


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

    def test_default_policy_blocks_session_upsert(self):
        """Default policy blocks session upsert sync."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_SESSION_UPSERT, policy) is False

    def test_default_policy_blocks_session_summary_update(self):
        """Default policy blocks session summary update sync."""
        policy = DataCollectionPolicy()
        assert should_sync_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, policy) is False

    def test_sync_observations_false_blocks_observation_events(self):
        """Disabling sync_observations blocks both observation event types."""
        policy = DataCollectionPolicy(sync_observations=False)
        assert should_sync_event(TEAM_EVENT_OBSERVATION_UPSERT, policy) is False
        assert should_sync_event(TEAM_EVENT_OBSERVATION_RESOLVED, policy) is False

    def test_sync_activities_true_enables_session_events(self):
        """Enabling sync_activities allows session event types."""
        policy = DataCollectionPolicy(sync_activities=True)
        assert should_sync_event(TEAM_EVENT_SESSION_UPSERT, policy) is True
        assert should_sync_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, policy) is True

    def test_unknown_event_type_returns_false(self):
        """Unknown event types are never synced."""
        policy = DataCollectionPolicy()
        assert should_sync_event("unknown_event", policy) is False


# =============================================================================
# should_collect_locally
# =============================================================================


class TestShouldCollectLocally:
    """Test should_collect_locally policy enforcement."""

    def test_default_policy_collects_activities(self):
        """Default policy collects activities locally."""
        policy = DataCollectionPolicy()
        assert should_collect_locally(LOCAL_EVENT_TYPE_ACTIVITY, policy) is True

    def test_default_policy_collects_prompts(self):
        """Default policy collects prompts locally."""
        policy = DataCollectionPolicy()
        assert should_collect_locally(LOCAL_EVENT_TYPE_PROMPT, policy) is True

    def test_collect_activities_false_blocks_activities(self):
        """Disabling collect_activities blocks local activity recording."""
        policy = DataCollectionPolicy(collect_activities=False)
        assert should_collect_locally(LOCAL_EVENT_TYPE_ACTIVITY, policy) is False

    def test_collect_prompts_false_blocks_prompts(self):
        """Disabling collect_prompts blocks local prompt recording."""
        policy = DataCollectionPolicy(collect_prompts=False)
        assert should_collect_locally(LOCAL_EVENT_TYPE_PROMPT, policy) is False

    def test_observations_always_collected(self):
        """Observations are always collected locally regardless of policy."""
        policy = DataCollectionPolicy(collect_activities=False, collect_prompts=False)
        assert should_collect_locally("observation", policy) is True

    def test_unknown_event_type_collected(self):
        """Unknown local event types default to collected."""
        policy = DataCollectionPolicy()
        assert should_collect_locally("unknown_type", policy) is True


# =============================================================================
# GovernanceConfig integration
# =============================================================================


class TestGovernanceConfigDataCollection:
    """Test GovernanceConfig includes and wires DataCollectionPolicy."""

    def test_governance_config_has_data_collection_field(self):
        """GovernanceConfig has a data_collection field with default policy."""
        config = GovernanceConfig()
        assert isinstance(config.data_collection, DataCollectionPolicy)
        assert (
            config.data_collection.collect_activities is DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT
        )

    def test_governance_config_from_dict_includes_data_collection(self):
        """GovernanceConfig.from_dict() parses data_collection section."""
        config = GovernanceConfig.from_dict(
            {
                "enabled": True,
                "data_collection": {
                    "sync_activities": True,
                    "allow_server_llm": True,
                },
            }
        )
        assert config.enabled is True
        assert config.data_collection.sync_activities is True
        assert config.data_collection.allow_server_llm is True
        # Non-overridden defaults preserved
        assert (
            config.data_collection.collect_activities is DATA_COLLECTION_COLLECT_ACTIVITIES_DEFAULT
        )

    def test_governance_config_from_dict_missing_data_collection(self):
        """GovernanceConfig.from_dict() without data_collection uses defaults."""
        config = GovernanceConfig.from_dict({"enabled": True})
        assert isinstance(config.data_collection, DataCollectionPolicy)
        assert config.data_collection.sync_observations is DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT

    def test_governance_config_to_dict_includes_data_collection(self):
        """GovernanceConfig.to_dict() includes the data_collection section."""
        config = GovernanceConfig(
            data_collection=DataCollectionPolicy(allow_server_llm=True),
        )
        result = config.to_dict()
        assert "data_collection" in result
        assert result["data_collection"]["allow_server_llm"] is True

    def test_governance_config_round_trip(self):
        """GovernanceConfig from_dict/to_dict round-trip preserves data_collection."""
        original = GovernanceConfig(
            enabled=True,
            data_collection=DataCollectionPolicy(
                sync_activities=True,
                sync_prompts=True,
                allow_server_llm=True,
            ),
        )
        restored = GovernanceConfig.from_dict(original.to_dict())
        assert restored.data_collection.sync_activities is True
        assert restored.data_collection.sync_prompts is True
        assert restored.data_collection.allow_server_llm is True
        assert restored.enabled is True
