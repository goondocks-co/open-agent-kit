"""LLM interaction for activity processing.

Handles API calls, JSON parsing, and fallback extraction.
"""

import json
import logging
import re
import subprocess
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.processor.models import (
    ContextBudget,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.summarization.base import (
        BaseSummarizer,
    )

logger = logging.getLogger(__name__)

# Module-level flag: set to True after the first 400 from json_object format.
# Avoids wasting a failed request on every extraction call when the provider
# (e.g. LM Studio) doesn't support response_format.
_json_format_unsupported = False

# Patterns for reasoning model chain-of-thought tokens.
# These models embed their thinking process in the content field.
# Order matters: try the most specific patterns first.
_REASONING_PATTERNS = [
    # <think>...</think>answer  (DeepSeek, Qwen, GLM, many others)
    re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE),
    # Implicit opening tag: reasoning...</think>answer  (GLM-4.7 observed)
    re.compile(r"^[\s\S]*?</think>\s*", re.IGNORECASE),
    # <reasoning>...</reasoning>answer
    re.compile(r"<reasoning>[\s\S]*?</reasoning>\s*", re.IGNORECASE),
    # <|thinking|>...<|/thinking|>answer
    re.compile(r"<\|thinking\|>[\s\S]*?<\|/thinking\|>\s*", re.IGNORECASE),
]


def strip_reasoning_tokens(text: str) -> str:
    """Strip reasoning/chain-of-thought tokens from LLM response text.

    Reasoning models (DeepSeek, GLM-4.7, Qwen, etc.) embed their thinking
    process in the content field using special tokens like <think>...</think>.
    This function removes that reasoning to extract only the final answer.

    Args:
        text: Raw LLM response content.

    Returns:
        Response with reasoning tokens stripped. Returns original text
        if no reasoning tokens are detected or if stripping would
        produce an empty result.
    """
    if not text:
        return text

    for pattern in _REASONING_PATTERNS:
        stripped = pattern.sub("", text).strip()
        if stripped and stripped != text.strip():
            logger.debug(f"Stripped reasoning tokens ({len(text)} → {len(stripped)} chars)")
            return stripped

    return text


def call_llm(
    prompt: str,
    summarizer: "BaseSummarizer",
    context_budget: ContextBudget,
) -> dict[str, Any]:
    """Call LLM for observation extraction.

    Args:
        prompt: Rendered prompt.
        summarizer: LLM summarizer instance.
        context_budget: Context budget for token limits.

    Returns:
        Dictionary with success, observations, summary, and raw_response.
    """
    logger.debug("[LLM] _call_llm invoked")

    if not summarizer:
        logger.debug("[LLM] No summarizer configured")
        return {"success": False, "error": "No summarizer configured"}

    try:
        # Use the summarizer's API directly
        from open_agent_kit.features.codebase_intelligence.summarization import (
            OpenAICompatSummarizer,
        )

        if not isinstance(summarizer, OpenAICompatSummarizer):
            logger.debug("[LLM] Unsupported summarizer type")
            return {"success": False, "error": "Unsupported summarizer type"}

        # Determine if this is an extraction prompt (expects JSON)
        is_extraction = "observations" in prompt.lower()

        # Calculate max_tokens based on context budget
        # Reserve ~25% of context for output, minimum 2000 tokens
        max_output_tokens = max(2000, context_budget.context_tokens // 4)

        request_body: dict[str, Any] = {
            "model": summarizer._resolved_model or summarizer.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_output_tokens,
        }

        # Request JSON format for extraction prompts (OpenAI compatible).
        # Skip if we already know the provider doesn't support it (cached
        # after first 400) to avoid a wasted round-trip on every call.
        global _json_format_unsupported  # noqa: PLW0603
        use_json_format = is_extraction and not _json_format_unsupported

        if use_json_format:
            request_body["response_format"] = {"type": "json_object"}

        # Use warmup-aware post method to handle model loading timeouts
        logger.debug(
            f"[LLM] Making request to {summarizer.base_url} "
            f"model={request_body.get('model')} is_extraction={is_extraction}"
        )
        response = summarizer.post_chat_completion(request_body)
        logger.debug(f"[LLM] Response status: {response.status_code}")

        # If response_format is not supported, cache that fact and retry without it
        if response.status_code == 400 and use_json_format:
            error_text = response.text.lower()
            if "response_format" in error_text or "json_object" in error_text:
                _json_format_unsupported = True
                logger.info(
                    "[LLM] Provider doesn't support json_object format — "
                    "caching for future calls and retrying without it"
                )
                del request_body["response_format"]
                response = summarizer.post_chat_completion(request_body)
                logger.debug(f"[LLM] Retry response status: {response.status_code}")

        if response.status_code != 200:
            logger.warning(f"[LLM] API error: {response.status_code} - {response.text[:500]}")
            return {"success": False, "error": f"API returned {response.status_code}"}

        data = response.json()
        raw_response = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not raw_response:
            return {"success": False, "error": "Empty LLM response"}

        # Strip reasoning/chain-of-thought tokens from reasoning models
        # (e.g. GLM-4.7, DeepSeek) before any downstream processing
        raw_response = strip_reasoning_tokens(raw_response)

        logger.debug(f"LLM response ({len(raw_response)} chars): {raw_response[:300]}")

        # For classification prompts, just return raw response
        if not is_extraction:
            return {
                "success": True,
                "raw_response": raw_response,
                "observations": [],
            }

        # Try to extract JSON for extraction prompts
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_match = re.search(r"\{[\s\S]*\}", raw_response)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = raw_response.strip()

        result = json.loads(json_str)

        return {
            "success": True,
            "observations": result.get("observations", []),
            "summary": result.get("summary", ""),
            "raw_response": raw_response,
        }

    except json.JSONDecodeError as e:
        logger.debug(f"JSON parse error: {e}")

        # Attempt to repair truncated JSON from LLM
        observations = extract_observations_fallback(
            json_str if "json_str" in dir() else raw_response
        )
        if observations:
            logger.info(f"Recovered {len(observations)} observations via fallback parsing")
            return {
                "success": True,
                "observations": observations,
                "raw_response": raw_response if "raw_response" in dir() else "",
            }

        return {
            "success": True,
            "observations": [],
            "raw_response": raw_response if "raw_response" in dir() else "",
        }
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def extract_observations_fallback(raw_text: str) -> list[dict[str, Any]]:
    """Extract observations from malformed/truncated JSON using regex.

    LLMs sometimes produce truncated JSON. This attempts to extract
    individual observation objects that are complete.

    Args:
        raw_text: Raw LLM response text.

    Returns:
        List of observation dicts that could be parsed.
    """
    observations = []

    # Pattern to match individual observation objects
    # Looking for: {"type": "...", "observation": "...", ...}
    obs_pattern = re.compile(
        r'\{\s*"type"\s*:\s*"([^"]+)"\s*,\s*"observation"\s*:\s*"((?:[^"\\]|\\.)*)"\s*'
        r'(?:,\s*"importance"\s*:\s*"([^"]+)")?\s*'
        r'(?:,\s*"context"\s*:\s*"((?:[^"\\]|\\.)*)")?\s*\}',
        re.DOTALL,
    )

    for match in obs_pattern.finditer(raw_text):
        try:
            obs_type = match.group(1)
            obs_text = match.group(2)
            importance = match.group(3) or "medium"
            context = match.group(4)

            # Unescape JSON string escapes
            obs_text = obs_text.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
            if context:
                context = context.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")

            observations.append(
                {
                    "type": obs_type,
                    "observation": obs_text,
                    "importance": importance,
                    "context": context,
                }
            )
        except (ValueError, KeyError, AttributeError, TypeError, IndexError) as e:
            logger.debug(f"Failed to parse observation match: {e}")
            continue

    return observations


def get_oak_ci_context(
    files_read: list[str],
    files_modified: list[str],
    files_created: list[str],
    classification: str,
    project_root: str | None,
) -> str:
    """Get relevant context from oak ci for the prompt.

    Calls oak ci search/context to inject related code into the prompt.

    Args:
        files_read: Files that were read.
        files_modified: Files that were modified.
        files_created: Files that were created.
        classification: Session classification.
        project_root: Project root for oak ci commands.

    Returns:
        Context string to inject into prompt, or empty string.
    """
    if not project_root:
        return ""

    context_parts = []

    try:
        # For modified files, get related code context
        key_files = files_modified[:3] or files_created[:3] or files_read[:3]

        for file_path in key_files:
            # Use oak ci search to find related code
            query = f"code related to {file_path}"
            result = run_oak_ci_command(["search", query, "--limit", "3"], project_root)
            if result:
                context_parts.append(f"### Related to {file_path}\n{result[:1000]}")

        # For debugging sessions, search for error patterns
        if classification == "debugging":
            result = run_oak_ci_command(
                ["search", "error handling", "--type", "memory", "--limit", "3"],
                project_root,
            )
            if result:
                context_parts.append(f"### Previous error learnings\n{result[:500]}")

    except (OSError, subprocess.TimeoutExpired) as e:
        logger.debug(f"Failed to get oak ci context: {e}")

    return "\n\n".join(context_parts)


def run_oak_ci_command(args: list[str], project_root: str | None) -> str | None:
    """Run an oak ci command and return output.

    Args:
        args: Command arguments (e.g., ["search", "query"]).
        project_root: Project root directory.

    Returns:
        Command output or None on error.
    """
    if not project_root:
        return None

    try:
        result = subprocess.run(
            ["oak", "ci"] + args,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug(f"oak ci command failed: {e}")
        return None
