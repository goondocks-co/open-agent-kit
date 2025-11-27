"""Tests for constants module.

Tests verify that all required constants are defined with correct types
and values. This ensures the "no magic strings" principle is maintained.

Uses parameterized tests to keep the file concise while covering every constant.
"""

import pytest

from open_agent_kit.features.codebase_intelligence import constants

# =============================================================================
# String Constants — verify name, value, and membership in group tuples
# =============================================================================

_STRING_CONSTANTS = [
    # (attr_name, expected_value)
    ("SEARCH_TYPE_ALL", "all"),
    ("SEARCH_TYPE_CODE", "code"),
    ("SEARCH_TYPE_MEMORY", "memory"),
    ("PROVIDER_OLLAMA", "ollama"),
    ("PROVIDER_OPENAI", "openai"),
    ("PROVIDER_LMSTUDIO", "lmstudio"),
    ("INDEX_STATUS_IDLE", "idle"),
    ("INDEX_STATUS_INDEXING", "indexing"),
    ("INDEX_STATUS_READY", "ready"),
    ("INDEX_STATUS_ERROR", "error"),
    ("INDEX_STATUS_UPDATING", "updating"),
    ("DAEMON_STATUS_RUNNING", "running"),
    ("DAEMON_STATUS_STOPPED", "stopped"),
    ("DAEMON_STATUS_HEALTHY", "healthy"),
    ("DAEMON_STATUS_UNHEALTHY", "unhealthy"),
    ("AGENT_CLAUDE", "claude"),
    ("AGENT_CURSOR", "cursor"),
    ("AGENT_GEMINI", "gemini"),
    ("CHUNK_TYPE_FUNCTION", "function"),
    ("CHUNK_TYPE_CLASS", "class"),
    ("CHUNK_TYPE_METHOD", "method"),
    ("CHUNK_TYPE_MODULE", "module"),
    ("CHUNK_TYPE_UNKNOWN", "unknown"),
    ("LOG_LEVEL_DEBUG", "DEBUG"),
    ("LOG_LEVEL_INFO", "INFO"),
    ("LOG_LEVEL_WARNING", "WARNING"),
    ("LOG_LEVEL_ERROR", "ERROR"),
]


@pytest.mark.parametrize(
    "attr,expected",
    _STRING_CONSTANTS,
    ids=[c[0] for c in _STRING_CONSTANTS],
)
def test_string_constant_value(attr: str, expected: str):
    """Verify string constant exists and has the expected value."""
    assert getattr(constants, attr) == expected


# =============================================================================
# Group tuples — verify they contain the expected members
# =============================================================================

_GROUP_TUPLES = [
    # (tuple_attr, expected_member_attrs)
    (
        "VALID_SEARCH_TYPES",
        ["SEARCH_TYPE_ALL", "SEARCH_TYPE_CODE", "SEARCH_TYPE_MEMORY"],
    ),
    (
        "VALID_PROVIDERS",
        ["PROVIDER_OLLAMA", "PROVIDER_OPENAI", "PROVIDER_LMSTUDIO"],
    ),
    (
        "SUPPORTED_HOOK_AGENTS",
        ["AGENT_CLAUDE", "AGENT_CURSOR", "AGENT_GEMINI"],
    ),
    (
        "VALID_LOG_LEVELS",
        ["LOG_LEVEL_DEBUG", "LOG_LEVEL_INFO", "LOG_LEVEL_WARNING", "LOG_LEVEL_ERROR"],
    ),
]


@pytest.mark.parametrize(
    "tuple_attr,member_attrs",
    _GROUP_TUPLES,
    ids=[g[0] for g in _GROUP_TUPLES],
)
def test_group_tuple_contains_members(tuple_attr: str, member_attrs: list[str]):
    """Verify group tuples contain all their expected member constants."""
    group = getattr(constants, tuple_attr)
    assert isinstance(group, tuple)
    for member_attr in member_attrs:
        assert getattr(constants, member_attr) in group


# =============================================================================
# Positive integer constants — verify type and range
# =============================================================================

_POSITIVE_INT_CONSTANTS = [
    "DEFAULT_SEARCH_LIMIT",
    "MAX_SEARCH_LIMIT",
    "DEFAULT_CONTEXT_LIMIT",
    "DEFAULT_MAX_CONTEXT_TOKENS",
    "CHARS_PER_TOKEN_ESTIMATE",
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "DEFAULT_INDEXING_BATCH_SIZE",
    "MAX_QUERY_LENGTH",
    "MIN_QUERY_LENGTH",
    "MAX_OBSERVATION_LENGTH",
]


@pytest.mark.parametrize("attr", _POSITIVE_INT_CONSTANTS)
def test_positive_int_constant(attr: str):
    """Verify integer constant exists and is positive."""
    value = getattr(constants, attr)
    assert isinstance(value, int)
    assert value > 0


# =============================================================================
# Other typed constants — verify type (not value-sensitive)
# =============================================================================

_STRING_TYPE_CONSTANTS = [
    "CI_DATA_DIR",
    "CI_CHROMA_DIR",
    "CI_LOG_FILE",
    "CI_PID_FILE",
    "CI_PORT_FILE",
    "DEFAULT_BASE_URL",
    "TAG_AUTO_CAPTURED",
    "TAG_SESSION_SUMMARY",
    "HOOK_EVENT_SESSION_START",
    "HOOK_EVENT_SESSION_END",
    "HOOK_EVENT_POST_TOOL_USE",
    "HOOK_EVENT_BEFORE_PROMPT",
    "HOOK_EVENT_STOP",
]


@pytest.mark.parametrize("attr", _STRING_TYPE_CONSTANTS)
def test_string_type_constant(attr: str):
    """Verify string-typed constant exists and is a non-empty string."""
    value = getattr(constants, attr)
    assert isinstance(value, str)
    assert len(value) > 0


def test_default_model_is_empty_string():
    """DEFAULT_MODEL is empty by default — user must select from discovered models."""
    assert isinstance(constants.DEFAULT_MODEL, str)
    assert constants.DEFAULT_MODEL == ""


def test_default_provider_is_valid():
    """DEFAULT_PROVIDER must be one of VALID_PROVIDERS."""
    assert constants.DEFAULT_PROVIDER in constants.VALID_PROVIDERS


def test_max_search_limit_gte_default():
    """MAX_SEARCH_LIMIT must be >= DEFAULT_SEARCH_LIMIT."""
    assert constants.MAX_SEARCH_LIMIT >= constants.DEFAULT_SEARCH_LIMIT


def test_default_context_memory_limit_is_int():
    """DEFAULT_CONTEXT_MEMORY_LIMIT must be an integer."""
    assert isinstance(constants.DEFAULT_CONTEXT_MEMORY_LIMIT, int)
