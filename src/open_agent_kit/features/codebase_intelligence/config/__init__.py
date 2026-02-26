"""Configuration management for Codebase Intelligence.

This package provides configuration classes with validation for the CI feature.
Configuration follows a priority hierarchy:
1. Environment variables (OAK_CI_*)
2. Project config (.oak/config.yaml)
3. Feature manifest defaults
4. Hardcoded defaults in this module

All public names are re-exported here so existing imports continue to work:
    from open_agent_kit.features.codebase_intelligence.config import CIConfig, load_ci_config
"""

# --- Agents ---
from open_agent_kit.features.codebase_intelligence.config.agents import AgentConfig

# --- CIConfig (top-level assembler) ---
from open_agent_kit.features.codebase_intelligence.config.ci_config import CIConfig

# --- Embedding ---
from open_agent_kit.features.codebase_intelligence.config.embedding import (
    DEFAULT_EMBEDDING_CONFIG,
    DEFAULT_EMBEDDING_CONTEXT_TOKENS,
    EmbeddingConfig,
    ProviderType,
)

# --- Governance ---
from open_agent_kit.features.codebase_intelligence.config.governance import (
    GovernanceConfig,
    GovernanceRule,
)

# --- Infrastructure ---
from open_agent_kit.features.codebase_intelligence.config.infrastructure import (
    BackupConfig,
    CloudRelayConfig,
    LogRotationConfig,
    TunnelConfig,
)

# --- I/O and classification ---
from open_agent_kit.features.codebase_intelligence.config.io import (
    DEFAULT_EXCLUDE_PATTERNS,
    USER_CLASSIFIED_PATHS,
    _deep_merge,
    _split_by_classification,
    _user_config_path,
    _write_yaml_config,
    get_config_origins,
    load_ci_config,
    save_ci_config,
)

# --- Session ---
# Validation constants re-exported for backward compatibility
from open_agent_kit.features.codebase_intelligence.config.session import (
    MAX_SESSION_ACTIVITY_THRESHOLD,
    MAX_STALE_SESSION_TIMEOUT,
    MIN_SESSION_ACTIVITY_THRESHOLD,
    MIN_STALE_SESSION_TIMEOUT,
    AutoResolveConfig,
    SessionQualityConfig,
)

# --- Summarization ---
from open_agent_kit.features.codebase_intelligence.config.summarization import (
    DEFAULT_CONTEXT_TOKENS,
    SummarizationConfig,
)

__all__ = [
    # Dataclass configs
    "AgentConfig",
    "AutoResolveConfig",
    "BackupConfig",
    "CIConfig",
    "CloudRelayConfig",
    "EmbeddingConfig",
    "GovernanceConfig",
    "GovernanceRule",
    "LogRotationConfig",
    "SessionQualityConfig",
    "SummarizationConfig",
    "TunnelConfig",
    # Type aliases
    "ProviderType",
    # Constants
    "DEFAULT_CONTEXT_TOKENS",
    "DEFAULT_EMBEDDING_CONFIG",
    "DEFAULT_EMBEDDING_CONTEXT_TOKENS",
    "DEFAULT_EXCLUDE_PATTERNS",
    "MAX_SESSION_ACTIVITY_THRESHOLD",
    "MAX_STALE_SESSION_TIMEOUT",
    "MIN_SESSION_ACTIVITY_THRESHOLD",
    "MIN_STALE_SESSION_TIMEOUT",
    "USER_CLASSIFIED_PATHS",
    # I/O functions
    "get_config_origins",
    "load_ci_config",
    "save_ci_config",
    # Internal helpers (used by tests)
    "_deep_merge",
    "_split_by_classification",
    "_user_config_path",
    "_write_yaml_config",
]
