"""Background cycle scheduling for the ActivityProcessor.

Manages timer-based periodic processing with power-state awareness.
The scheduler evaluates idle duration and adjusts which phases run
and how long to sleep before the next cycle.
"""

import logging
import threading
from typing import TYPE_CHECKING

from open_agent_kit.features.team.constants import (
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from open_agent_kit.features.team.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.team.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def schedule_background_processing(
    processor: "ActivityProcessor",
    interval_seconds: int = POWER_ACTIVE_INTERVAL,
    state_accessor: "Callable[[], DaemonState] | None" = None,
) -> threading.Timer:
    """Schedule periodic background processing with power-state awareness.

    When *state_accessor* is provided the timer callback evaluates idle
    duration and adjusts which phases run and how long to sleep before
    the next cycle.  When the daemon reaches deep sleep the timer is
    **not** rescheduled -- the wake-from-deep-sleep path in
    ``DaemonState.record_hook_activity`` restarts it.

    Args:
        processor: The ActivityProcessor instance.
        interval_seconds: Base interval between processing runs.
        state_accessor: Optional callable returning the current DaemonState.

    Returns:
        Timer object (can be cancelled).
    """

    def run_and_reschedule() -> None:
        _new_state, next_interval = evaluate_and_run_cycle(
            processor, state_accessor, interval_seconds
        )
        if next_interval > 0:
            timer = threading.Timer(next_interval, run_and_reschedule)
            timer.daemon = True
            timer.start()

    timer = threading.Timer(interval_seconds, run_and_reschedule)
    timer.daemon = True
    timer.start()

    logger.info(f"Scheduled background activity processing every {interval_seconds}s")
    return timer


def evaluate_and_run_cycle(
    processor: "ActivityProcessor",
    state_accessor: "Callable[[], DaemonState] | None",
    base_interval: int,
) -> tuple[str, int]:
    """Evaluate power state, run appropriate phases, return (state, interval).

    Logic:
    - ACTIVE: full ``run_background_cycle()`` (phases 0-5)
    - IDLE: maintenance + indexing (phases 1-2, 5), same interval
    - SLEEP: recovery + indexing (phases 1, 5), longer interval
    - DEEP_SLEEP: no work, interval 0 (timer stops)

    Phase 5 (plan indexing + title generation) runs in IDLE/SLEEP because
    it is lightweight (embedding + ChromaDB upsert, no LLM calls) and plans
    are often created at the end of a session just before idle begins.

    Args:
        processor: The ActivityProcessor instance.
        state_accessor: Optional callable returning the current DaemonState.
        base_interval: The base interval in seconds.

    Returns:
        Tuple of (power_state_name, next_interval_seconds).
        An interval of 0 means the timer should NOT be rescheduled.
    """
    import time

    daemon_state: DaemonState | None = None
    if state_accessor is not None:
        daemon_state = state_accessor()

    # Determine idle duration -- use last hook activity if available,
    # otherwise fall back to daemon start time so the idle clock ticks
    # even when no hooks have ever fired (e.g. daemon starts, user walks away).
    idle_seconds: float | None = None
    if daemon_state is not None:
        last_activity = daemon_state.last_hook_activity or daemon_state.start_time
        if last_activity is not None:
            idle_seconds = time.time() - last_activity

    # Determine target power state
    if idle_seconds is None or idle_seconds < POWER_IDLE_THRESHOLD:
        target_state = POWER_STATE_ACTIVE
    elif idle_seconds < POWER_SLEEP_THRESHOLD:
        target_state = POWER_STATE_IDLE
    elif idle_seconds < POWER_DEEP_SLEEP_THRESHOLD:
        target_state = POWER_STATE_SLEEP
    else:
        target_state = POWER_STATE_DEEP_SLEEP

    # Handle state transition (call through processor method for test-patchability)
    if daemon_state is not None:
        old_state = daemon_state.power_state
        if old_state != target_state:
            processor._on_power_transition(daemon_state, old_state, target_state)

    # Run phases based on target state (call through processor methods
    # so that test patches on processor._bg_* are respected)
    if target_state == POWER_STATE_ACTIVE:
        processor.run_background_cycle()
        return target_state, base_interval

    if target_state == POWER_STATE_IDLE:
        processor._bg_recover_stuck_data()  # Phase 1
        processor._bg_recover_stale_sessions()  # Phase 2
        processor._bg_index_and_title()  # Phase 5 (lightweight, no LLM)
        return target_state, base_interval

    if target_state == POWER_STATE_SLEEP:
        processor._bg_recover_stuck_data()  # Phase 1
        processor._bg_index_and_title()  # Phase 5 (lightweight, no LLM)
        return target_state, POWER_SLEEP_INTERVAL

    # DEEP_SLEEP: run nothing, do not reschedule
    return target_state, 0
