"""Power states, background processing, batching, and scheduler constants."""

from typing import Final

# =============================================================================
# Power States (idle performance tuning)
# =============================================================================

# Power states
POWER_STATE_ACTIVE: Final[str] = "active"
POWER_STATE_IDLE: Final[str] = "idle"
POWER_STATE_SLEEP: Final[str] = "sleep"
POWER_STATE_DEEP_SLEEP: Final[str] = "deep_sleep"

# Thresholds (seconds since last hook activity)
POWER_IDLE_THRESHOLD: Final[int] = 300  # 5 minutes
POWER_SLEEP_THRESHOLD: Final[int] = 1800  # 30 minutes
POWER_DEEP_SLEEP_THRESHOLD: Final[int] = 5400  # 90 minutes

# Cycle intervals per state (seconds)
POWER_ACTIVE_INTERVAL: Final[int] = 60  # Normal 60s cycle
POWER_IDLE_INTERVAL: Final[int] = 60  # Same frequency, reduced work
POWER_SLEEP_INTERVAL: Final[int] = 300  # 5 min between checks

# =============================================================================
# Batching and Performance
# =============================================================================

DEFAULT_EMBEDDING_BATCH_SIZE: Final[int] = 100
DEFAULT_INDEXING_BATCH_SIZE: Final[int] = 50

# Timeout for indexing operations (1 hour default - large codebases need time)
DEFAULT_INDEXING_TIMEOUT_SECONDS: Final[float] = 3600.0

# =============================================================================
# Agent Scheduler/Executor Configuration
# =============================================================================

# Scheduler interval: how often the scheduler checks for due schedules
DEFAULT_SCHEDULER_INTERVAL_SECONDS: Final[int] = 60
MIN_SCHEDULER_INTERVAL_SECONDS: Final[int] = 10
MAX_SCHEDULER_INTERVAL_SECONDS: Final[int] = 3600

# Executor cache size: max runs to keep in memory
DEFAULT_EXECUTOR_CACHE_SIZE: Final[int] = 100
MIN_EXECUTOR_CACHE_SIZE: Final[int] = 10
MAX_EXECUTOR_CACHE_SIZE: Final[int] = 1000

# Background processing: batch size, parallelism, and interval
DEFAULT_BACKGROUND_PROCESSING_BATCH_SIZE: Final[int] = 50
DEFAULT_BACKGROUND_PROCESSING_WORKERS: Final[int] = 2
MIN_BACKGROUND_PROCESSING_WORKERS: Final[int] = 1
MAX_BACKGROUND_PROCESSING_WORKERS: Final[int] = 16

# Background processing interval: how often activity processor runs
DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 60
MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 10
MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 600
