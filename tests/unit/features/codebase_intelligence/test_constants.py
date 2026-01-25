"""Tests for constants module.

Tests verify that all required constants are defined with correct types
and values. This ensures the "no magic strings" principle is maintained.
"""

from open_agent_kit.features.codebase_intelligence import constants

# =============================================================================
# Search Types Constants
# =============================================================================


class TestSearchTypeConstants:
    """Test search type constants."""

    def test_search_type_all_defined(self):
        """Test that SEARCH_TYPE_ALL constant exists."""
        assert hasattr(constants, "SEARCH_TYPE_ALL")
        assert constants.SEARCH_TYPE_ALL == "all"

    def test_search_type_code_defined(self):
        """Test that SEARCH_TYPE_CODE constant exists."""
        assert hasattr(constants, "SEARCH_TYPE_CODE")
        assert constants.SEARCH_TYPE_CODE == "code"

    def test_search_type_memory_defined(self):
        """Test that SEARCH_TYPE_MEMORY constant exists."""
        assert hasattr(constants, "SEARCH_TYPE_MEMORY")
        assert constants.SEARCH_TYPE_MEMORY == "memory"

    def test_valid_search_types_tuple(self):
        """Test that VALID_SEARCH_TYPES contains all search types."""
        assert hasattr(constants, "VALID_SEARCH_TYPES")
        assert isinstance(constants.VALID_SEARCH_TYPES, tuple)
        assert constants.SEARCH_TYPE_ALL in constants.VALID_SEARCH_TYPES
        assert constants.SEARCH_TYPE_CODE in constants.VALID_SEARCH_TYPES
        assert constants.SEARCH_TYPE_MEMORY in constants.VALID_SEARCH_TYPES


# =============================================================================
# Embedding Provider Constants
# =============================================================================


class TestEmbeddingProviderConstants:
    """Test embedding provider constants."""

    def test_provider_ollama_defined(self):
        """Test that PROVIDER_OLLAMA constant exists."""
        assert hasattr(constants, "PROVIDER_OLLAMA")
        assert constants.PROVIDER_OLLAMA == "ollama"

    def test_provider_openai_defined(self):
        """Test that PROVIDER_OPENAI constant exists."""
        assert hasattr(constants, "PROVIDER_OPENAI")
        assert constants.PROVIDER_OPENAI == "openai"

    def test_provider_lmstudio_defined(self):
        """Test that PROVIDER_LMSTUDIO constant exists."""
        assert hasattr(constants, "PROVIDER_LMSTUDIO")
        assert constants.PROVIDER_LMSTUDIO == "lmstudio"

    def test_valid_providers_tuple(self):
        """Test that VALID_PROVIDERS contains all providers."""
        assert hasattr(constants, "VALID_PROVIDERS")
        assert isinstance(constants.VALID_PROVIDERS, tuple)
        assert constants.PROVIDER_OLLAMA in constants.VALID_PROVIDERS
        assert constants.PROVIDER_OPENAI in constants.VALID_PROVIDERS
        assert constants.PROVIDER_LMSTUDIO in constants.VALID_PROVIDERS

    def test_default_provider_defined(self):
        """Test that DEFAULT_PROVIDER is defined and valid."""
        assert hasattr(constants, "DEFAULT_PROVIDER")
        assert constants.DEFAULT_PROVIDER in constants.VALID_PROVIDERS

    def test_default_model_defined(self):
        """Test that DEFAULT_MODEL constant exists (empty - user must select)."""
        assert hasattr(constants, "DEFAULT_MODEL")
        assert isinstance(constants.DEFAULT_MODEL, str)
        # Model is empty by default - user must select from discovered models
        assert constants.DEFAULT_MODEL == ""

    def test_default_base_url_defined(self):
        """Test that DEFAULT_BASE_URL constant exists."""
        assert hasattr(constants, "DEFAULT_BASE_URL")
        assert isinstance(constants.DEFAULT_BASE_URL, str)
        assert "http" in constants.DEFAULT_BASE_URL


# =============================================================================
# Index Status Constants
# =============================================================================


class TestIndexStatusConstants:
    """Test index status constants."""

    def test_index_status_idle_defined(self):
        """Test that INDEX_STATUS_IDLE constant exists."""
        assert hasattr(constants, "INDEX_STATUS_IDLE")
        assert constants.INDEX_STATUS_IDLE == "idle"

    def test_index_status_indexing_defined(self):
        """Test that INDEX_STATUS_INDEXING constant exists."""
        assert hasattr(constants, "INDEX_STATUS_INDEXING")
        assert constants.INDEX_STATUS_INDEXING == "indexing"

    def test_index_status_ready_defined(self):
        """Test that INDEX_STATUS_READY constant exists."""
        assert hasattr(constants, "INDEX_STATUS_READY")
        assert constants.INDEX_STATUS_READY == "ready"

    def test_index_status_error_defined(self):
        """Test that INDEX_STATUS_ERROR constant exists."""
        assert hasattr(constants, "INDEX_STATUS_ERROR")
        assert constants.INDEX_STATUS_ERROR == "error"

    def test_index_status_updating_defined(self):
        """Test that INDEX_STATUS_UPDATING constant exists."""
        assert hasattr(constants, "INDEX_STATUS_UPDATING")
        assert constants.INDEX_STATUS_UPDATING == "updating"


# =============================================================================
# Daemon Status Constants
# =============================================================================


class TestDaemonStatusConstants:
    """Test daemon status constants."""

    def test_daemon_status_running_defined(self):
        """Test that DAEMON_STATUS_RUNNING constant exists."""
        assert hasattr(constants, "DAEMON_STATUS_RUNNING")
        assert constants.DAEMON_STATUS_RUNNING == "running"

    def test_daemon_status_stopped_defined(self):
        """Test that DAEMON_STATUS_STOPPED constant exists."""
        assert hasattr(constants, "DAEMON_STATUS_STOPPED")
        assert constants.DAEMON_STATUS_STOPPED == "stopped"

    def test_daemon_status_healthy_defined(self):
        """Test that DAEMON_STATUS_HEALTHY constant exists."""
        assert hasattr(constants, "DAEMON_STATUS_HEALTHY")
        assert constants.DAEMON_STATUS_HEALTHY == "healthy"

    def test_daemon_status_unhealthy_defined(self):
        """Test that DAEMON_STATUS_UNHEALTHY constant exists."""
        assert hasattr(constants, "DAEMON_STATUS_UNHEALTHY")
        assert constants.DAEMON_STATUS_UNHEALTHY == "unhealthy"


# =============================================================================
# Agent Name Constants
# =============================================================================


class TestAgentNameConstants:
    """Test agent name constants."""

    def test_agent_claude_defined(self):
        """Test that AGENT_CLAUDE constant exists."""
        assert hasattr(constants, "AGENT_CLAUDE")
        assert constants.AGENT_CLAUDE == "claude"

    def test_agent_cursor_defined(self):
        """Test that AGENT_CURSOR constant exists."""
        assert hasattr(constants, "AGENT_CURSOR")
        assert constants.AGENT_CURSOR == "cursor"

    def test_agent_gemini_defined(self):
        """Test that AGENT_GEMINI constant exists."""
        assert hasattr(constants, "AGENT_GEMINI")
        assert constants.AGENT_GEMINI == "gemini"

    def test_supported_hook_agents_tuple(self):
        """Test that SUPPORTED_HOOK_AGENTS contains all agents."""
        assert hasattr(constants, "SUPPORTED_HOOK_AGENTS")
        assert isinstance(constants.SUPPORTED_HOOK_AGENTS, tuple)
        assert constants.AGENT_CLAUDE in constants.SUPPORTED_HOOK_AGENTS
        assert constants.AGENT_CURSOR in constants.SUPPORTED_HOOK_AGENTS
        assert constants.AGENT_GEMINI in constants.SUPPORTED_HOOK_AGENTS


# =============================================================================
# File Names and Paths Constants
# =============================================================================


class TestFileNamesConstants:
    """Test file name and path constants."""

    def test_hook_filename_defined(self):
        """Test that HOOK_FILENAME constant exists."""
        assert hasattr(constants, "HOOK_FILENAME")
        assert constants.HOOK_FILENAME == "hooks.json"

    def test_settings_filename_defined(self):
        """Test that SETTINGS_FILENAME constant exists."""
        assert hasattr(constants, "SETTINGS_FILENAME")
        assert constants.SETTINGS_FILENAME == "settings.json"

    def test_ci_data_dir_defined(self):
        """Test that CI_DATA_DIR constant exists."""
        assert hasattr(constants, "CI_DATA_DIR")
        assert isinstance(constants.CI_DATA_DIR, str)

    def test_ci_chroma_dir_defined(self):
        """Test that CI_CHROMA_DIR constant exists."""
        assert hasattr(constants, "CI_CHROMA_DIR")
        assert isinstance(constants.CI_CHROMA_DIR, str)

    def test_ci_log_file_defined(self):
        """Test that CI_LOG_FILE constant exists."""
        assert hasattr(constants, "CI_LOG_FILE")
        assert isinstance(constants.CI_LOG_FILE, str)

    def test_ci_pid_file_defined(self):
        """Test that CI_PID_FILE constant exists."""
        assert hasattr(constants, "CI_PID_FILE")
        assert isinstance(constants.CI_PID_FILE, str)

    def test_ci_port_file_defined(self):
        """Test that CI_PORT_FILE constant exists."""
        assert hasattr(constants, "CI_PORT_FILE")
        assert isinstance(constants.CI_PORT_FILE, str)


# =============================================================================
# API Defaults Constants
# =============================================================================


class TestAPIDefaultsConstants:
    """Test API default constants."""

    def test_default_search_limit_defined(self):
        """Test that DEFAULT_SEARCH_LIMIT constant exists."""
        assert hasattr(constants, "DEFAULT_SEARCH_LIMIT")
        assert isinstance(constants.DEFAULT_SEARCH_LIMIT, int)
        assert constants.DEFAULT_SEARCH_LIMIT > 0

    def test_max_search_limit_defined(self):
        """Test that MAX_SEARCH_LIMIT constant exists."""
        assert hasattr(constants, "MAX_SEARCH_LIMIT")
        assert isinstance(constants.MAX_SEARCH_LIMIT, int)
        assert constants.MAX_SEARCH_LIMIT >= constants.DEFAULT_SEARCH_LIMIT

    def test_default_context_limit_defined(self):
        """Test that DEFAULT_CONTEXT_LIMIT constant exists."""
        assert hasattr(constants, "DEFAULT_CONTEXT_LIMIT")
        assert isinstance(constants.DEFAULT_CONTEXT_LIMIT, int)
        assert constants.DEFAULT_CONTEXT_LIMIT > 0

    def test_default_context_memory_limit_defined(self):
        """Test that DEFAULT_CONTEXT_MEMORY_LIMIT constant exists."""
        assert hasattr(constants, "DEFAULT_CONTEXT_MEMORY_LIMIT")
        assert isinstance(constants.DEFAULT_CONTEXT_MEMORY_LIMIT, int)

    def test_default_max_context_tokens_defined(self):
        """Test that DEFAULT_MAX_CONTEXT_TOKENS constant exists."""
        assert hasattr(constants, "DEFAULT_MAX_CONTEXT_TOKENS")
        assert isinstance(constants.DEFAULT_MAX_CONTEXT_TOKENS, int)
        assert constants.DEFAULT_MAX_CONTEXT_TOKENS > 0

    def test_chars_per_token_estimate_defined(self):
        """Test that CHARS_PER_TOKEN_ESTIMATE constant exists."""
        assert hasattr(constants, "CHARS_PER_TOKEN_ESTIMATE")
        assert isinstance(constants.CHARS_PER_TOKEN_ESTIMATE, int)
        assert constants.CHARS_PER_TOKEN_ESTIMATE > 0


# =============================================================================
# Chunk Types Constants
# =============================================================================


class TestChunkTypeConstants:
    """Test chunk type constants."""

    def test_chunk_type_function_defined(self):
        """Test that CHUNK_TYPE_FUNCTION constant exists."""
        assert hasattr(constants, "CHUNK_TYPE_FUNCTION")
        assert constants.CHUNK_TYPE_FUNCTION == "function"

    def test_chunk_type_class_defined(self):
        """Test that CHUNK_TYPE_CLASS constant exists."""
        assert hasattr(constants, "CHUNK_TYPE_CLASS")
        assert constants.CHUNK_TYPE_CLASS == "class"

    def test_chunk_type_method_defined(self):
        """Test that CHUNK_TYPE_METHOD constant exists."""
        assert hasattr(constants, "CHUNK_TYPE_METHOD")
        assert constants.CHUNK_TYPE_METHOD == "method"

    def test_chunk_type_module_defined(self):
        """Test that CHUNK_TYPE_MODULE constant exists."""
        assert hasattr(constants, "CHUNK_TYPE_MODULE")
        assert constants.CHUNK_TYPE_MODULE == "module"

    def test_chunk_type_unknown_defined(self):
        """Test that CHUNK_TYPE_UNKNOWN constant exists."""
        assert hasattr(constants, "CHUNK_TYPE_UNKNOWN")
        assert constants.CHUNK_TYPE_UNKNOWN == "unknown"


# =============================================================================
# Memory Types Constants
# =============================================================================
# NOTE: Memory type constants (MEMORY_TYPE_*) were removed in favor of
# schema-driven types defined in features/codebase-intelligence/schema.yaml.
# The MemoryType enum in daemon/models.py now serves as the API validation layer.


# =============================================================================
# Auto-Capture Keywords Constants
# =============================================================================
# NOTE: Keyword constants (ERROR_KEYWORDS, FIX_KEYWORDS, TEST_*_KEYWORDS) were
# removed when pattern-based extraction was replaced with LLM-based classification.


# =============================================================================
# Tool Names Constants
# =============================================================================
# NOTE: Tool name constants (TOOL_EDIT, TOOL_WRITE, TOOL_BASH) were removed
# as they were only used by the pattern-based extractors.


# =============================================================================
# Batching and Performance Constants
# =============================================================================


class TestBatchingConstants:
    """Test batching and performance constants."""

    def test_default_embedding_batch_size_defined(self):
        """Test that DEFAULT_EMBEDDING_BATCH_SIZE constant exists."""
        assert hasattr(constants, "DEFAULT_EMBEDDING_BATCH_SIZE")
        assert isinstance(constants.DEFAULT_EMBEDDING_BATCH_SIZE, int)
        assert constants.DEFAULT_EMBEDDING_BATCH_SIZE > 0

    def test_default_indexing_batch_size_defined(self):
        """Test that DEFAULT_INDEXING_BATCH_SIZE constant exists."""
        assert hasattr(constants, "DEFAULT_INDEXING_BATCH_SIZE")
        assert isinstance(constants.DEFAULT_INDEXING_BATCH_SIZE, int)
        assert constants.DEFAULT_INDEXING_BATCH_SIZE > 0


# =============================================================================
# Logging Constants
# =============================================================================


class TestLoggingConstants:
    """Test logging constants."""

    def test_log_level_debug_defined(self):
        """Test that LOG_LEVEL_DEBUG constant exists."""
        assert hasattr(constants, "LOG_LEVEL_DEBUG")
        assert constants.LOG_LEVEL_DEBUG == "DEBUG"

    def test_log_level_info_defined(self):
        """Test that LOG_LEVEL_INFO constant exists."""
        assert hasattr(constants, "LOG_LEVEL_INFO")
        assert constants.LOG_LEVEL_INFO == "INFO"

    def test_log_level_warning_defined(self):
        """Test that LOG_LEVEL_WARNING constant exists."""
        assert hasattr(constants, "LOG_LEVEL_WARNING")
        assert constants.LOG_LEVEL_WARNING == "WARNING"

    def test_log_level_error_defined(self):
        """Test that LOG_LEVEL_ERROR constant exists."""
        assert hasattr(constants, "LOG_LEVEL_ERROR")
        assert constants.LOG_LEVEL_ERROR == "ERROR"

    def test_valid_log_levels_tuple(self):
        """Test that VALID_LOG_LEVELS contains all log levels."""
        assert hasattr(constants, "VALID_LOG_LEVELS")
        assert isinstance(constants.VALID_LOG_LEVELS, tuple)
        assert constants.LOG_LEVEL_DEBUG in constants.VALID_LOG_LEVELS
        assert constants.LOG_LEVEL_INFO in constants.VALID_LOG_LEVELS
        assert constants.LOG_LEVEL_WARNING in constants.VALID_LOG_LEVELS
        assert constants.LOG_LEVEL_ERROR in constants.VALID_LOG_LEVELS


# =============================================================================
# Input Validation Constants
# =============================================================================


class TestInputValidationConstants:
    """Test input validation constants."""

    def test_max_query_length_defined(self):
        """Test that MAX_QUERY_LENGTH constant exists."""
        assert hasattr(constants, "MAX_QUERY_LENGTH")
        assert isinstance(constants.MAX_QUERY_LENGTH, int)
        assert constants.MAX_QUERY_LENGTH > 0

    def test_min_query_length_defined(self):
        """Test that MIN_QUERY_LENGTH constant exists."""
        assert hasattr(constants, "MIN_QUERY_LENGTH")
        assert isinstance(constants.MIN_QUERY_LENGTH, int)
        assert constants.MIN_QUERY_LENGTH > 0

    def test_max_observation_length_defined(self):
        """Test that MAX_OBSERVATION_LENGTH constant exists."""
        assert hasattr(constants, "MAX_OBSERVATION_LENGTH")
        assert isinstance(constants.MAX_OBSERVATION_LENGTH, int)
        assert constants.MAX_OBSERVATION_LENGTH > 0


# =============================================================================
# Hook Event Constants
# =============================================================================


class TestHookEventConstants:
    """Test hook event constants."""

    def test_hook_event_session_start_defined(self):
        """Test that HOOK_EVENT_SESSION_START constant exists."""
        assert hasattr(constants, "HOOK_EVENT_SESSION_START")
        assert isinstance(constants.HOOK_EVENT_SESSION_START, str)

    def test_hook_event_session_end_defined(self):
        """Test that HOOK_EVENT_SESSION_END constant exists."""
        assert hasattr(constants, "HOOK_EVENT_SESSION_END")
        assert isinstance(constants.HOOK_EVENT_SESSION_END, str)

    def test_hook_event_post_tool_use_defined(self):
        """Test that HOOK_EVENT_POST_TOOL_USE constant exists."""
        assert hasattr(constants, "HOOK_EVENT_POST_TOOL_USE")
        assert isinstance(constants.HOOK_EVENT_POST_TOOL_USE, str)

    def test_hook_event_before_prompt_defined(self):
        """Test that HOOK_EVENT_BEFORE_PROMPT constant exists."""
        assert hasattr(constants, "HOOK_EVENT_BEFORE_PROMPT")
        assert isinstance(constants.HOOK_EVENT_BEFORE_PROMPT, str)

    def test_hook_event_stop_defined(self):
        """Test that HOOK_EVENT_STOP constant exists."""
        assert hasattr(constants, "HOOK_EVENT_STOP")
        assert isinstance(constants.HOOK_EVENT_STOP, str)


# =============================================================================
# Tag Constants
# =============================================================================


class TestTagConstants:
    """Test tag constants."""

    def test_tag_auto_captured_defined(self):
        """Test that TAG_AUTO_CAPTURED constant exists."""
        assert hasattr(constants, "TAG_AUTO_CAPTURED")
        assert isinstance(constants.TAG_AUTO_CAPTURED, str)

    def test_tag_session_summary_defined(self):
        """Test that TAG_SESSION_SUMMARY constant exists."""
        assert hasattr(constants, "TAG_SESSION_SUMMARY")
        assert isinstance(constants.TAG_SESSION_SUMMARY, str)
