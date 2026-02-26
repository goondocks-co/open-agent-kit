"""CI config top-level section keys."""

from typing import Final

# =============================================================================
# CI Config Top-Level Section Keys
# =============================================================================
# These constants name each top-level section inside
# ``codebase_intelligence:`` in .oak/config.yaml.  Used by
# CIConfig.from_dict / to_dict, get_config_origins, and daemon config routes.
#
# NOTE: BACKUP_CONFIG_KEY, AUTO_RESOLVE_CONFIG_KEY, CI_CONFIG_KEY_TUNNEL,
# and CI_CONFIG_KEY_CLI_COMMAND are defined in their respective domain
# sections and are also valid section keys.
CI_CONFIG_KEY_EMBEDDING: Final[str] = "embedding"
CI_CONFIG_KEY_SUMMARIZATION: Final[str] = "summarization"
CI_CONFIG_KEY_AGENTS: Final[str] = "agents"
CI_CONFIG_KEY_SESSION_QUALITY: Final[str] = "session_quality"
CI_CONFIG_KEY_INDEX_ON_STARTUP: Final[str] = "index_on_startup"
CI_CONFIG_KEY_WATCH_FILES: Final[str] = "watch_files"
CI_CONFIG_KEY_EXCLUDE_PATTERNS: Final[str] = "exclude_patterns"
CI_CONFIG_KEY_LOG_LEVEL: Final[str] = "log_level"
CI_CONFIG_KEY_LOG_ROTATION: Final[str] = "log_rotation"
CI_CONFIG_KEY_GOVERNANCE: Final[str] = "governance"
