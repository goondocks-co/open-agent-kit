"""Transcript parsing utilities for agent JSONL files.

Supports Claude Code and SubagentStop transcript formats.
"""

import json
import logging
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    RESPONSE_SUMMARY_MAX_LENGTH,
)

logger = logging.getLogger(__name__)


def parse_transcript_response(
    transcript_path: str,
    max_length: int = RESPONSE_SUMMARY_MAX_LENGTH,
) -> str | None:
    """Extract the final assistant response from a transcript file.

    Supports Claude Code and SubagentStop transcript formats (JSONL).
    Searches from the end of the file for the last assistant message.

    Args:
        transcript_path: Path to the JSONL transcript file.
        max_length: Maximum length of returned summary.

    Returns:
        The final assistant response text, or None if not found.
    """
    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        logger.debug(f"Transcript file not found: {transcript_path}")
        return None

    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")

        # Search from end for last assistant message with text content
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)

                # Handle Claude Code transcript format: {"type": "assistant", "message": {...}}
                # The message object contains role, content, etc.
                if msg.get("type") == "assistant":
                    inner_msg = msg.get("message", {})
                    if inner_msg.get("role") == "assistant":
                        content = inner_msg.get("content", "")
                        text = _extract_text_from_content(content)
                        if text:
                            return text[:max_length]
                # Handle simple format: {"role": "assistant", "content": ...}
                elif msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    text = _extract_text_from_content(content)
                    if text:
                        return text[:max_length]
            except json.JSONDecodeError:
                continue

        logger.debug(f"No assistant message found in transcript: {transcript_path}")
        return None
    except OSError as e:
        logger.debug(f"Error reading transcript {transcript_path}: {e}")
        return None


def _extract_text_from_content(content: str | list | dict) -> str:
    """Extract text from various content formats.

    Claude Code transcripts may have content as:
    - A plain string
    - A list of content blocks (text, tool_use, etc.)
    - A dict with a "text" field

    Args:
        content: The content field from a message.

    Returns:
        Extracted text string.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    if isinstance(content, dict):
        text_value = content.get("text", "")
        return str(text_value) if text_value else ""

    return ""
