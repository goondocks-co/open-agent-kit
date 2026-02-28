"""Release channel and install-method constants."""

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

# =============================================================================
# Install methods
# =============================================================================

CI_INSTALL_METHOD_HOMEBREW: Final[str] = "homebrew"
CI_INSTALL_METHOD_PIPX: Final[str] = "pipx"
CI_INSTALL_METHOD_UV: Final[str] = "uv"
CI_INSTALL_METHOD_UNKNOWN: Final[str] = "unknown"
