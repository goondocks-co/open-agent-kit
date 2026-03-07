"""Release channel constants."""

from typing import Final

# =============================================================================
# Release channels
# =============================================================================

CI_CHANNEL_STABLE: Final[str] = "stable"
CI_CHANNEL_BETA: Final[str] = "beta"

# =============================================================================
# API paths
# =============================================================================

CI_CHANNEL_API_PATH: Final[str] = "/api/channel"
CI_CHANNEL_SWITCH_API_PATH: Final[str] = "/api/channel/switch"
