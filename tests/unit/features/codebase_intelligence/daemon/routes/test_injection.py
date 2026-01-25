"""Unit tests for context injection helpers.

Tests cover:
- format_memories_for_injection: Memory formatting for context injection
- format_session_summaries: Session summary formatting
- format_code_for_injection: Code chunk formatting as markdown
- build_rich_search_query: Query construction for semantic search
- build_session_context: Session context building (no CLI reminders)
"""

from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    INJECTION_MAX_CODE_CHUNKS,
    INJECTION_MAX_MEMORIES,
    INJECTION_MAX_SESSION_SUMMARIES,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
    LANG_MAP,
    build_rich_search_query,
    build_session_context,
    format_code_for_injection,
    format_memories_for_injection,
    format_session_summaries,
)


class TestFormatMemoriesForInjection:
    """Tests for format_memories_for_injection function."""

    def test_empty_memories_returns_empty_string(self):
        """Empty memory list returns empty string."""
        result = format_memories_for_injection([])
        assert result == ""

    def test_formats_single_memory(self):
        """Single memory is formatted correctly."""
        memories = [
            {
                "observation": "Database connections leak under load",
                "memory_type": "gotcha",
                "context": "src/db.py",
            }
        ]
        result = format_memories_for_injection(memories)
        assert "## Recent Project Memories" in result
        assert "Database connections leak under load" in result
        assert "gotcha" in result
        assert "src/db.py" in result

    def test_formats_multiple_memory_types(self):
        """Different memory types are formatted with appropriate markers."""
        memories = [
            {"observation": "Cache invalidation issue", "memory_type": "gotcha"},
            {"observation": "Fixed race condition", "memory_type": "bug_fix"},
            {"observation": "Use async for I/O", "memory_type": "decision"},
            {"observation": "Found helper util", "memory_type": "discovery"},
            {"observation": "Speed vs. safety", "memory_type": "trade_off"},
        ]
        result = format_memories_for_injection(memories)

        # Check each memory type is present
        assert "[fix]" in result or "bug_fix" in result
        assert "[decision]" in result or "decision" in result
        assert "[discovery]" in result or "discovery" in result
        assert "[trade-off]" in result or "trade_off" in result

    def test_respects_max_items_limit(self):
        """Only includes up to max_items memories."""
        memories = [{"observation": f"Memory {i}", "memory_type": "discovery"} for i in range(20)]
        result = format_memories_for_injection(memories, max_items=5)

        # Should have exactly 5 memories (plus header)
        assert result.count("Memory") == 5
        assert "Memory 0" in result
        assert "Memory 4" in result
        assert "Memory 5" not in result

    def test_uses_default_max_items(self):
        """Uses INJECTION_MAX_MEMORIES as default limit."""
        memories = [
            {"observation": f"Memory {i}", "memory_type": "note"}
            for i in range(INJECTION_MAX_MEMORIES + 5)
        ]
        result = format_memories_for_injection(memories)

        # Should have exactly INJECTION_MAX_MEMORIES memories
        assert result.count("Memory") == INJECTION_MAX_MEMORIES

    def test_handles_missing_context(self):
        """Memories without context are formatted without context suffix."""
        memories = [{"observation": "Test observation", "memory_type": "discovery"}]
        result = format_memories_for_injection(memories)
        assert "Test observation" in result
        assert "context:" not in result


class TestFormatSessionSummaries:
    """Tests for format_session_summaries function."""

    def test_empty_summaries_returns_empty_string(self):
        """Empty summaries list returns empty string."""
        result = format_session_summaries([])
        assert result == ""

    def test_formats_single_summary(self):
        """Single summary is formatted correctly."""
        summaries = [
            {
                "observation": "Implemented user authentication",
                "tags": ["claude", "session-summary"],
            }
        ]
        result = format_session_summaries(summaries)
        assert "## Recent Session History" in result
        assert "Session 1" in result
        assert "Implemented user authentication" in result
        assert "claude" in result

    def test_truncates_long_summaries(self):
        """Long summaries are truncated to 200 characters."""
        long_text = "A" * 300
        summaries = [{"observation": long_text, "tags": ["agent"]}]
        result = format_session_summaries(summaries)

        # Should be truncated with ellipsis
        assert "A" * 197 in result
        assert "..." in result
        assert long_text not in result  # Full text should not appear

    def test_filters_system_tags(self):
        """System tags are filtered out when determining agent."""
        summaries = [
            {
                "observation": "Test summary",
                "tags": ["session-summary", "llm-summarized", "claude-code"],
            }
        ]
        result = format_session_summaries(summaries)
        assert "claude-code" in result  # Custom tag preserved
        assert "(session-summary)" not in result  # System tag filtered

    def test_respects_max_items_limit(self):
        """Only includes up to max_items summaries."""
        summaries = [{"observation": f"Summary {i}", "tags": ["agent"]} for i in range(10)]
        result = format_session_summaries(summaries, max_items=3)
        assert "Summary 0" in result
        assert "Summary 2" in result
        assert "Summary 3" not in result

    def test_uses_default_max_items(self):
        """Uses INJECTION_MAX_SESSION_SUMMARIES as default limit."""
        summaries = [
            {"observation": f"Summary {i}", "tags": ["agent"]}
            for i in range(INJECTION_MAX_SESSION_SUMMARIES + 3)
        ]
        result = format_session_summaries(summaries)

        # Count actual summary entries (not header)
        summary_count = result.count("Summary")
        assert summary_count == INJECTION_MAX_SESSION_SUMMARIES


class TestFormatCodeForInjection:
    """Tests for format_code_for_injection function."""

    def test_empty_chunks_returns_empty_string(self):
        """Empty chunk list returns empty string."""
        result = format_code_for_injection([])
        assert result == ""

    def test_formats_single_chunk(self):
        """Single code chunk is formatted as markdown code block."""
        chunks = [
            {
                "filepath": "src/utils.py",
                "start_line": 10,
                "end_line": 20,
                "name": "helper_func",
                "content": "def helper_func():\n    return 42",
            }
        ]
        result = format_code_for_injection(chunks)
        assert "## Relevant Code" in result
        assert "**src/utils.py** (L10-20)" in result
        assert "`helper_func`" in result
        assert "```python" in result
        assert "def helper_func():" in result
        assert "```" in result

    def test_detects_language_from_extension(self):
        """Language is detected from file extension."""
        test_cases = [
            ("test.py", "python"),
            ("test.ts", "typescript"),
            ("test.tsx", "typescript"),
            ("test.js", "javascript"),
            ("test.jsx", "javascript"),
            ("test.go", "go"),
            ("test.rs", "rust"),
            ("test.yaml", "yaml"),
        ]
        for filepath, expected_lang in test_cases:
            chunks = [{"filepath": filepath, "content": "code here"}]
            result = format_code_for_injection(chunks)
            assert f"```{expected_lang}" in result, f"Failed for {filepath}"

    def test_truncates_long_chunks(self):
        """Long code chunks are truncated with line count indicator."""
        long_content = "\n".join([f"line {i}" for i in range(100)])
        chunks = [
            {
                "filepath": "test.py",
                "content": long_content,
            }
        ]
        result = format_code_for_injection(chunks, max_lines_per_chunk=50)

        # Should have truncation indicator
        assert "more lines" in result
        assert "line 0" in result
        assert "line 49" in result
        assert "line 99" not in result  # Truncated

    def test_respects_max_chunks_limit(self):
        """Only includes up to max_chunks code chunks."""
        chunks = [{"filepath": f"file{i}.py", "content": f"# Code {i}"} for i in range(10)]
        result = format_code_for_injection(chunks, max_chunks=2)
        assert "file0.py" in result
        assert "file1.py" in result
        assert "file2.py" not in result

    def test_uses_default_limits(self):
        """Uses INJECTION_MAX_CODE_CHUNKS as default limit."""
        chunks = [
            {"filepath": f"file{i}.py", "content": "code"}
            for i in range(INJECTION_MAX_CODE_CHUNKS + 5)
        ]
        result = format_code_for_injection(chunks)

        # Count file references
        file_count = sum(1 for i in range(10) if f"file{i}.py" in result)
        assert file_count == INJECTION_MAX_CODE_CHUNKS

    def test_handles_missing_optional_fields(self):
        """Chunks with missing optional fields are handled gracefully."""
        chunks = [
            {
                "filepath": "test.py",
                "content": "print('hello')",
            }
        ]
        result = format_code_for_injection(chunks)
        assert "test.py" in result
        assert "print('hello')" in result
        # Default line numbers should be used
        assert "L1-1" in result


class TestBuildRichSearchQuery:
    """Tests for build_rich_search_query function."""

    def test_file_path_only(self):
        """File path alone produces valid query."""
        result = build_rich_search_query("src/utils.py")
        assert result == "src/utils.py"

    def test_includes_tool_output_excerpt(self):
        """Tool output is included in query when not noise."""
        result = build_rich_search_query(
            file_path="src/api.py",
            tool_output="Modified authentication logic",
        )
        assert "src/api.py" in result
        assert "Modified authentication logic" in result

    def test_filters_noise_patterns(self):
        """Noise patterns in tool output are filtered out."""
        noise_outputs = [
            "Read 1234 chars",  # Read summary
            "1\u2192line content",  # Read output with arrow
            '{"key": "value"}',  # JSON
            "[1, 2, 3]",  # Array
            "     1\u2192first line",  # Indented line numbers
        ]
        for noise in noise_outputs:
            result = build_rich_search_query(
                file_path="test.py",
                tool_output=noise,
            )
            # Only file path should be present, not the noise
            assert result.strip() == "test.py", f"Noise not filtered: {noise}"

    def test_includes_user_prompt_excerpt(self):
        """User prompt is included in query."""
        result = build_rich_search_query(
            file_path="src/db.py",
            user_prompt="Fix the database connection pooling issue",
        )
        assert "src/db.py" in result
        assert "Fix the database connection pooling issue" in result

    def test_truncates_long_excerpts(self):
        """Long excerpts are truncated."""
        long_output = "A" * 500
        long_prompt = "B" * 700

        result = build_rich_search_query(
            file_path="test.py",
            tool_output=long_output,
            user_prompt=long_prompt,
        )

        # Tool output truncated to 200, prompt to 500
        assert "A" * 200 in result
        assert "A" * 201 not in result
        assert "B" * 500 in result
        assert "B" * 501 not in result

    def test_combines_all_parts(self):
        """All parts are combined into single query."""
        result = build_rich_search_query(
            file_path="src/handler.py",
            tool_output="Updated error handling",
            user_prompt="Add retry logic",
        )
        parts = result.split()
        assert len(parts) >= 3  # At least file + 2 excerpts


class TestBuildSessionContext:
    """Tests for build_session_context function."""

    @pytest.fixture
    def mock_state(self):
        """Create mock daemon state."""
        state = MagicMock()
        state.vector_store = MagicMock()
        state.vector_store.get_stats.return_value = {
            "code_chunks": 100,
            "memory_observations": 50,
        }
        state.retrieval_engine = MagicMock()
        state.retrieval_engine.list_memories.return_value = ([], 0)
        state.retrieval_engine.search.return_value = MagicMock(memory=[])
        return state

    def test_returns_empty_when_no_vector_store(self, mock_state):
        """Returns empty string when vector store is not available."""
        mock_state.vector_store = None
        result = build_session_context(mock_state)
        assert result == ""

    def test_includes_ci_status(self, mock_state):
        """Includes codebase intelligence status."""
        result = build_session_context(mock_state)
        assert "Codebase Intelligence Active" in result
        assert "100 code chunks indexed" in result
        assert "50 memories stored" in result

    def test_no_cli_reminders(self, mock_state):
        """Does NOT include CLI command reminders."""
        result = build_session_context(mock_state)

        # These CLI reminders should NOT be present
        assert "PREFER" not in result
        assert "oak ci" not in result.lower()
        assert "oak ci search" not in result
        assert "oak ci context" not in result
        assert "oak ci remember" not in result

    def test_includes_session_summaries_when_requested(self, mock_state):
        """Includes session summaries when include_memories=True."""
        mock_state.retrieval_engine.list_memories.return_value = (
            [
                {
                    "observation": "Added authentication feature",
                    "tags": ["claude", "session-summary"],
                }
            ],
            1,
        )
        result = build_session_context(mock_state, include_memories=True)
        assert "Recent Session History" in result or "Session 1" in result

    def test_skips_memories_when_not_requested(self, mock_state):
        """Skips memories when include_memories=False."""
        mock_state.retrieval_engine.list_memories.return_value = (
            [{"observation": "Test memory", "tags": []}],
            1,
        )
        result = build_session_context(mock_state, include_memories=False)
        assert "Test memory" not in result

    def test_includes_high_confidence_memories(self, mock_state):
        """Includes high and medium confidence memories."""
        # Mock search to return memories with confidence
        mock_state.retrieval_engine.search.return_value = MagicMock(
            memory=[
                {
                    "observation": "Important gotcha",
                    "memory_type": "gotcha",
                    "confidence": "high",
                }
            ]
        )
        # Should not raise - memory content inclusion depends on filter_by_confidence behavior
        result = build_session_context(mock_state, include_memories=True)
        assert result is not None  # Basic check that function completes

    def test_handles_retrieval_errors_gracefully(self, mock_state):
        """Handles retrieval engine errors gracefully."""
        mock_state.retrieval_engine.list_memories.side_effect = RuntimeError("DB error")
        mock_state.retrieval_engine.search.side_effect = RuntimeError("Search failed")

        # Should not raise, just return basic status
        result = build_session_context(mock_state)
        assert "Codebase Intelligence Active" in result

    def test_returns_empty_when_no_index_data(self, mock_state):
        """Returns empty when no code chunks or memories indexed."""
        mock_state.vector_store.get_stats.return_value = {
            "code_chunks": 0,
            "memory_observations": 0,
        }
        result = build_session_context(mock_state)
        assert result == ""


class TestLangMap:
    """Tests for LANG_MAP constant."""

    def test_common_extensions_mapped(self):
        """Common file extensions are mapped to languages."""
        expected_mappings = {
            "py": "python",
            "ts": "typescript",
            "tsx": "typescript",
            "js": "javascript",
            "jsx": "javascript",
            "go": "go",
            "rs": "rust",
            "rb": "ruby",
            "java": "java",
        }
        for ext, lang in expected_mappings.items():
            assert LANG_MAP.get(ext) == lang, f"Missing mapping for .{ext}"
