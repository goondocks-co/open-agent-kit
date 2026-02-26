"""Data collection policy enforcement.

These functions gate what data is collected locally and what syncs
to the team server based on the DataCollectionPolicy configuration.
"""

from open_agent_kit.features.codebase_intelligence.config.governance import DataCollectionPolicy
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)

# Local collection event type identifiers (used by should_collect_locally)
LOCAL_EVENT_TYPE_ACTIVITY = "activity"
LOCAL_EVENT_TYPE_PROMPT = "prompt"


def should_sync_event(event_type: str, policy: DataCollectionPolicy) -> bool:
    """Check if an event type should be synced to team server per policy.

    Args:
        event_type: The team event type constant.
        policy: Current data collection policy.

    Returns:
        True if the event should be synced.
    """
    if event_type in (TEAM_EVENT_OBSERVATION_UPSERT, TEAM_EVENT_OBSERVATION_RESOLVED):
        return policy.sync_observations
    if event_type in (TEAM_EVENT_SESSION_UPSERT, TEAM_EVENT_SESSION_SUMMARY_UPDATE):
        # Sessions sync is controlled by sync_activities (sessions are activity data)
        return policy.sync_activities
    # Unknown event types: don't sync by default
    return False


def should_collect_locally(event_type: str, policy: DataCollectionPolicy) -> bool:
    """Check if an event should be recorded locally per policy.

    This gates the local ActivityStore writes, not outbox writes.

    Args:
        event_type: A descriptive string like "activity", "prompt", "observation".
        policy: Current data collection policy.

    Returns:
        True if the data should be collected locally.
    """
    if event_type == LOCAL_EVENT_TYPE_ACTIVITY:
        return policy.collect_activities
    if event_type == LOCAL_EVENT_TYPE_PROMPT:
        return policy.collect_prompts
    # Observations are always collected locally (they're the core value)
    return True
