"""Transcript parsing utilities for agent transcript files.

Supports multiple transcript formats:
- **JSONL** (Claude Code, VS Code Copilot, SubagentStop): one JSON object per line
- **Plaintext role-marker** (Cursor): ``user:`` / ``assistant:`` section headers
  with markdown content between them
"""

import json
import logging
import re
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    RESPONSE_SUMMARY_MAX_LENGTH,
)

logger = logging.getLogger(__name__)

# Minimum length of assistant text to consider it a substantive response
# (filters out tool-call-only blocks like "[Tool call] Read\n  path: ...")
_MIN_RESPONSE_LENGTH = 40

# Lines that are tool-call / tool-result metadata, not user-facing text
_TOOL_LINE_RE = re.compile(
    r"^\s*\[Tool (call|result)\]|"  # [Tool call] / [Tool result] markers
    r"^\s{2,}\S+:|"  # indented key: value (tool parameters)
    r"^\s*$"  # blank lines
)


def parse_transcript_response(
    transcript_path: str,
    max_length: int = RESPONSE_SUMMARY_MAX_LENGTH,
) -> str | None:
    """Extract the final assistant response from a transcript file.

    Tries JSONL parsing first (Claude Code, VS Code Copilot).  If no JSON
    assistant message is found, falls back to plaintext role-marker parsing
    (Cursor).

    Args:
        transcript_path: Path to the transcript file.
        max_length: Maximum length of returned summary.

    Returns:
        The final assistant response text, or None if not found.
    """
    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        logger.debug(f"Transcript file not found: {transcript_path}")
        return None

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.debug(f"Error reading transcript {transcript_path}: {e}")
        return None

    if not content:
        return None

    # Try JSONL first (Claude Code, VS Code Copilot, SubagentStop)
    result = _parse_jsonl_transcript(content, max_length)
    if result:
        return result

    # Fall back to plaintext role-marker format (Cursor)
    result = _parse_plaintext_transcript(content, max_length)
    if result:
        return result

    logger.debug(f"No assistant message found in transcript: {transcript_path}")
    return None


def _parse_jsonl_transcript(content: str, max_length: int) -> str | None:
    """Parse JSONL transcript (Claude Code, VS Code Copilot, SubagentStop).

    Searches from the end of the file for the last assistant message.
    """
    lines = content.split("\n")

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                continue

            # Claude Code: {"type": "assistant", "message": {"role": "assistant", "content": ...}}
            if msg.get("type") == "assistant":
                inner_msg = msg.get("message", {})
                if inner_msg.get("role") == "assistant":
                    text = _extract_text_from_content(inner_msg.get("content", ""))
                    if text:
                        return text[:max_length]
            # VS Code Copilot: {"type": "assistant.message", "data": {"content": "..."}}
            elif msg.get("type") == "assistant.message":
                data = msg.get("data", {})
                if isinstance(data, dict):
                    text = _extract_text_from_content(data.get("content", ""))
                    if text:
                        return text[:max_length]
            # Simple: {"role": "assistant", "content": ...}
            elif msg.get("role") == "assistant":
                text = _extract_text_from_content(msg.get("content", ""))
                if text:
                    return text[:max_length]
        except json.JSONDecodeError:
            continue

    return None


def _parse_plaintext_transcript(content: str, max_length: int) -> str | None:
    """Parse plaintext role-marker transcript (Cursor).

    Format::

        user:
        <user_query>What is X?</user_query>

        assistant:
        [Tool call] Read
          path: /some/file.py

        [Tool result] Read

        assistant:
        Here is my analysis of X...

    Extracts the last ``assistant:`` block that contains substantive text
    (not just tool calls).  Scans backward so we find the final response
    first.
    """
    lines = content.split("\n")

    # Find all assistant block start indices (lines that are exactly "assistant:")
    assistant_starts: list[int] = []
    for i, line in enumerate(lines):
        if line.strip().lower() == "assistant:":
            assistant_starts.append(i)

    if not assistant_starts:
        return None

    # Walk backward through assistant blocks to find one with substantive text
    for start_idx in reversed(assistant_starts):
        # Collect lines until next role marker or end of file
        block_lines: list[str] = []
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            # Stop at next role marker
            if line.strip().lower() in ("user:", "assistant:", "system:"):
                break
            block_lines.append(line)

        # Filter out tool-call metadata to get just the prose content
        text_lines = [ln for ln in block_lines if not _TOOL_LINE_RE.match(ln)]
        text = "\n".join(text_lines).strip()

        if len(text) >= _MIN_RESPONSE_LENGTH:
            return text[:max_length]

    return None


# Regex to extract file paths from Cursor's <code_selection path="file://..."> tags.
# Example: <code_selection path="file:///Users/chris/.cursor/plans/foo.plan.md" lines="1-149">
_CODE_SELECTION_PATH_RE = re.compile(r'<code_selection\s+[^>]*path="file://([^"]+)"', re.IGNORECASE)


def extract_attached_file_paths(transcript_path: str) -> list[str]:
    """Extract file paths from ``<code_selection>`` tags in a transcript.

    Cursor attaches plan files (and other context) to user messages as
    ``<attached_files><code_selection path="file:///abs/path">`` XML blocks.
    This function parses the transcript JSONL and extracts all such paths,
    returning them in chronological order (most recent last).

    Args:
        transcript_path: Path to the JSONL transcript file.

    Returns:
        List of absolute file paths referenced in code_selection tags.
        Empty list if none found or on any error.
    """
    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        return []

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.debug(f"Error reading transcript {transcript_path}: {e}")
        return []

    if not content:
        return []

    result: list[str] = []
    seen: set[str] = set()

    for line in content.split("\n"):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(msg, dict):
            continue

        # Extract text from all known message formats
        text = ""
        # Cursor JSONL: {"role":"user","message":{"content":[{"type":"text","text":"..."}]}}
        inner_msg = msg.get("message", {})
        if isinstance(inner_msg, dict):
            text = _extract_text_from_content(inner_msg.get("content", ""))
        if not text:
            text = _extract_text_from_content(msg.get("content", ""))

        if not text:
            continue

        # Find all <code_selection path="file://..."> references
        for match in _CODE_SELECTION_PATH_RE.finditer(text):
            file_path = match.group(1)
            if file_path and file_path not in seen:
                seen.add(file_path)
                result.append(file_path)

    return result


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
