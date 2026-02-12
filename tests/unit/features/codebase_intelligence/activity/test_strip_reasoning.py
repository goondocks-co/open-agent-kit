"""Tests for strip_reasoning_tokens() — reasoning model chain-of-thought removal."""

from open_agent_kit.features.codebase_intelligence.activity.processor.llm import (
    strip_reasoning_tokens,
)


class TestStripReasoningTokens:
    """Tests for stripping reasoning/chain-of-thought from LLM responses."""

    # -- No-op cases (should return input unchanged) --

    def test_empty_string(self) -> None:
        assert strip_reasoning_tokens("") == ""

    def test_none_passthrough(self) -> None:
        # None is technically invalid but the function guards against it
        assert strip_reasoning_tokens(None) is None  # type: ignore[arg-type]

    def test_plain_text_unchanged(self) -> None:
        text = "refactoring"
        assert strip_reasoning_tokens(text) == "refactoring"

    def test_normal_summary_unchanged(self) -> None:
        text = (
            "- **User intent**: Fix the stale config bug\n"
            "- **Key actions**: Updated config accessor pattern\n"
            "- **Outcomes**: Config changes now take effect immediately"
        )
        assert strip_reasoning_tokens(text) == text

    def test_json_response_unchanged(self) -> None:
        text = '{"observations": [{"type": "discovery", "observation": "found bug"}]}'
        assert strip_reasoning_tokens(text) == text

    # -- <think>...</think> pattern (standard, used by DeepSeek/Qwen/GLM) --

    def test_think_tags_standard(self) -> None:
        text = "<think>Let me analyze this step by step...</think>refactoring"
        assert strip_reasoning_tokens(text) == "refactoring"

    def test_think_tags_multiline(self) -> None:
        text = (
            "<think>\n"
            "1. Analyze the request\n"
            "2. Check the files\n"
            "3. Determine classification\n"
            "</think>\n"
            "implementation"
        )
        assert strip_reasoning_tokens(text) == "implementation"

    def test_think_tags_with_markdown(self) -> None:
        text = (
            "<think>\n"
            "**Step 1**: Read the code\n"
            "**Step 2**: Identify patterns\n"
            "</think>\n"
            "- User intent: Migrate from pipx to uv\n"
            "- Key actions: Updated Makefile\n"
        )
        result = strip_reasoning_tokens(text)
        assert result.startswith("- User intent: Migrate from pipx to uv")
        assert "<think>" not in result
        assert "</think>" not in result

    def test_think_tags_case_insensitive(self) -> None:
        text = "<Think>Some reasoning</Think>exploration"
        assert strip_reasoning_tokens(text) == "exploration"

    def test_think_tags_with_json_answer(self) -> None:
        text = (
            "<think>I need to extract observations from this session.</think>"
            '{"observations": [{"type": "gotcha", "observation": "test"}]}'
        )
        result = strip_reasoning_tokens(text)
        assert result.startswith('{"observations"')
        assert "<think>" not in result

    # -- Implicit opening tag (GLM-4.7 observed pattern) --

    def test_implicit_think_open_tag_classification(self) -> None:
        """Real-world GLM-4.7 pattern: reasoning without <think>, ends with </think>."""
        text = (
            "1.  **Analyze the Request:**\n"
            "    *   Selection: refactoring\n"
            "</think>refactoring"
        )
        assert strip_reasoning_tokens(text) == "refactoring"

    def test_implicit_think_open_tag_long_reasoning(self) -> None:
        """GLM-4.7 style: long numbered analysis followed by </think>answer."""
        text = (
            "1.  **Analyze the Request:** The user wants classification.\n"
            "2.  **Analyze the Summary:** Duration 15.7 min.\n"
            "3.  **Analyze the Log:** Multiple reads and edits.\n"
            "4.  **Synthesize:** This is refactoring.\n"
            "5.  **Final Check:** Confirmed.\n"
            "6.  **Construct Output:** refactoring\n"
            "</think>refactoring"
        )
        assert strip_reasoning_tokens(text) == "refactoring"

    def test_implicit_think_with_summary_answer(self) -> None:
        """GLM-4.7 style with a multi-line actual answer after </think>."""
        text = (
            "1. Analyze the request: summarize the session\n"
            "2. Key elements: user intent, actions, outcomes\n"
            "</think>\n"
            "- **User intent**: Fix authentication bug\n"
            "- **Key actions**: Updated middleware\n"
            "- **Outcomes**: Auth now works correctly"
        )
        result = strip_reasoning_tokens(text)
        assert result.startswith("- **User intent**: Fix authentication bug")
        assert "Analyze the request" not in result

    # -- <reasoning>...</reasoning> pattern --

    def test_reasoning_tags(self) -> None:
        text = "<reasoning>Step 1: analyze. Step 2: classify.</reasoning>debugging"
        assert strip_reasoning_tokens(text) == "debugging"

    def test_reasoning_tags_multiline(self) -> None:
        text = (
            "<reasoning>\n"
            "The session shows error handling patterns.\n"
            "Classification: debugging\n"
            "</reasoning>\n"
            "debugging"
        )
        assert strip_reasoning_tokens(text) == "debugging"

    # -- <|thinking|>...<|/thinking|> pattern --

    def test_thinking_pipe_tags(self) -> None:
        text = "<|thinking|>analysis here<|/thinking|>exploration"
        assert strip_reasoning_tokens(text) == "exploration"

    # -- Edge cases --

    def test_only_reasoning_returns_original(self) -> None:
        """If stripping would produce empty, return original."""
        text = "<think>This is all reasoning with no answer</think>"
        # The strip produces empty string, so the original should be returned
        assert strip_reasoning_tokens(text) == text

    def test_whitespace_after_think_close(self) -> None:
        text = "<think>reasoning</think>   \n  actual answer"
        assert strip_reasoning_tokens(text) == "actual answer"

    def test_preserves_internal_html_tags(self) -> None:
        """HTML tags that aren't reasoning tokens should be preserved."""
        text = "Use <code>make check</code> to validate"
        assert strip_reasoning_tokens(text) == text

    def test_real_world_glm_classification(self) -> None:
        """Verbatim from the reported GLM-4.7 output (abbreviated)."""
        text = (
            "1.  **Analyze the Request:** The user wants me to classify.\n\n"
            "2.  **Analyze the Activity Summary:**\n"
            "    *   Duration: 15.7 minutes.\n"
            "    *   Tools: Read, Grep, Edit, TaskUpdate, SubagentStop.\n\n"
            "3.  **Analyze the Activity Log:**\n"
            "    1.  `SubagentStop`: Stopping subprocess.\n"
            "    2.  `Read`: Reading `server.py`.\n\n"
            "4.  **Synthesize and Classify:**\n"
            "    *   refactoring.\n\n"
            "5.  **Final Check:** Confirmed refactoring.\n\n"
            "6.  **Construct Output:**\n"
            "    *   Selection: refactoring</think>refactoring"
        )
        assert strip_reasoning_tokens(text) == "refactoring"

    def test_real_world_glm_summary(self) -> None:
        """Simulated GLM-4.7 summary output with reasoning prefix."""
        text = (
            "1.  **Analyze the Request:**\n"
            "    *   **Goal:** Summarize a coding session.\n"
            "    *   **Format:** Plain text, bulleted list.\n"
            "</think>\n"
            "- **User intent** - The user wanted to add daemon-version mismatch detection.\n"
            "- **Key actions** - Implemented version check in CLI startup.\n"
            "- **Outcomes** - Daemon auto-restarts on version mismatch."
        )
        result = strip_reasoning_tokens(text)
        assert result.startswith("- **User intent**")
        assert "Analyze the Request" not in result
