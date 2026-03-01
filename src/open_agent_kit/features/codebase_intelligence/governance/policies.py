"""Data collection policy enforcement.

These functions gate what data syncs to the team relay based on the
DataCollectionPolicy configuration.
"""

from open_agent_kit.features.codebase_intelligence.config.governance import DataCollectionPolicy
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_ACTIVITY_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_STATUS_UPDATE,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_PROMPT_BATCH_UPSERT,
    TEAM_EVENT_SESSION_END,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_TITLE_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)


def should_sync_event(event_type: str, policy: DataCollectionPolicy) -> bool:
    """Check if an event type should be synced to team relay per policy.

    Args:
        event_type: The team event type constant.
        policy: Current data collection policy.

    Returns:
        True if the event should be synced.
    """
    # Session lifecycle + prompt batches: always sync (structural envelope)
    if event_type in (
        TEAM_EVENT_SESSION_UPSERT,
        TEAM_EVENT_SESSION_END,
        TEAM_EVENT_SESSION_TITLE_UPDATE,
        TEAM_EVENT_SESSION_SUMMARY_UPDATE,
        TEAM_EVENT_PROMPT_BATCH_UPSERT,
    ):
        return True
    # Observations: gated by sync_observations
    if event_type in (
        TEAM_EVENT_OBSERVATION_UPSERT,
        TEAM_EVENT_OBSERVATION_RESOLVED,
        TEAM_EVENT_OBSERVATION_STATUS_UPDATE,
    ):
        return policy.sync_observations
    # Activities (tool calls, file changes): not synced in current version
    if event_type == TEAM_EVENT_ACTIVITY_UPSERT:
        return False
    return False
