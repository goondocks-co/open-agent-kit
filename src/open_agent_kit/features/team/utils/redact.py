"""Secrets redaction utility for activity and prompt capture.

Redacts known secret patterns (API keys, tokens, credentials) from text
before it is persisted to SQLite or indexed in ChromaDB.

Pattern source: secrets-patterns-db (MIT licensed) filtered to high-confidence
patterns, with hardcoded fallbacks for resilience.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REDACTED_PLACEHOLDER = "[REDACTED]"

# Remote pattern source (MIT licensed)
_PATTERNS_URL = (
    "https://raw.githubusercontent.com/mazen160/secrets-patterns-db/master/db/rules-stable.yml"
)
_PATTERNS_CACHE_FILENAME = "redaction-patterns.yml"
_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days
_FETCH_TIMEOUT_SECONDS = 5

# Module-level compiled patterns: list of (name, compiled_regex)
_compiled_patterns: list[tuple[str, re.Pattern[str]]] = []

# Hardcoded fallback patterns (high confidence, common secret formats)
_FALLBACK_PATTERNS: list[tuple[str, str]] = [
    ("AWS Access Key ID", r"AKIA[0-9A-Z]{16}"),
    ("GitHub Personal Access Token", r"ghp_[A-Za-z0-9_]{36,}"),
    ("GitHub Fine-Grained PAT", r"github_pat_[A-Za-z0-9_]{22,}"),
    ("Bearer Token", r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    ("JSON Web Token", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("OpenAI / Anthropic SK Key", r"sk-[A-Za-z0-9]{20,}"),
    ("Slack Bot Token", r"xoxb-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{20,}"),
    ("Password in URL", r"://[^:/?#\s]+:[^@/?#\s]{8,}@"),
    ("PEM Private Key Header", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    (
        "Generic Secret Assignment",
        r"""(?i)(?:api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\s*[=:]\s*['"][A-Za-z0-9\-._~+/]{16,}['"]""",
    ),
]


def _load_from_cache(cache_path: Path) -> list[tuple[str, str]] | None:
    """Load patterns from local cache if fresh enough.

    Returns:
        List of (name, regex_str) pairs, or None if cache is missing/stale.
    """
    if not cache_path.exists():
        return None

    age = time.time() - cache_path.stat().st_mtime
    if age > _CACHE_MAX_AGE_SECONDS:
        return None

    return _parse_yaml_patterns(cache_path)


def _fetch_and_cache(cache_path: Path) -> list[tuple[str, str]] | None:
    """Fetch patterns from remote, cache locally.

    Returns:
        List of (name, regex_str) pairs, or None if fetch fails.
    """
    import urllib.request

    try:
        with urllib.request.urlopen(_PATTERNS_URL, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
            data = resp.read()

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(data)
        logger.info(f"Fetched redaction patterns to {cache_path}")
        return _parse_yaml_patterns(cache_path)
    except (OSError, ValueError, TimeoutError) as e:
        logger.warning(f"Failed to fetch redaction patterns: {e}")
        return None


def _parse_yaml_patterns(path: Path) -> list[tuple[str, str]]:
    """Parse rules-stable.yml and filter to high-confidence patterns.

    Returns:
        List of (name, regex_str) pairs.
    """
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"Failed to parse redaction patterns YAML: {e}")
        return []

    if not isinstance(data, dict):
        return []

    patterns: list[tuple[str, str]] = []
    for entry in data.get("patterns", []):
        pattern_info = entry.get("pattern", {})
        if not isinstance(pattern_info, dict):
            continue

        confidence = pattern_info.get("confidence", "").lower()
        if confidence != "high":
            continue

        name = pattern_info.get("name", "unknown")
        regex_str = pattern_info.get("regex", "")
        if regex_str:
            patterns.append((name, regex_str))

    return patterns


def _compile_patterns(
    raw_patterns: list[tuple[str, str]],
) -> list[tuple[str, re.Pattern[str]]]:
    """Compile regex patterns, skipping invalid ones.

    Returns:
        List of (name, compiled_pattern) pairs.
    """
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for name, regex_str in raw_patterns:
        try:
            compiled.append((name, re.compile(regex_str)))
        except re.error as e:
            logger.debug(f"Skipping invalid redaction pattern {name!r}: {e}")
    return compiled


def load_patterns(cache_dir: Path) -> list[tuple[str, re.Pattern[str]]]:
    """Load patterns from cache (fetching if stale). Returns compiled (name, regex) pairs."""
    cache_path = cache_dir / _PATTERNS_CACHE_FILENAME

    # Try cache first
    raw = _load_from_cache(cache_path)

    # Fetch if cache miss
    if raw is None:
        raw = _fetch_and_cache(cache_path)

    # Fall back to hardcoded patterns
    if not raw:
        logger.info("Using hardcoded fallback redaction patterns")
        raw = list(_FALLBACK_PATTERNS)
    else:
        # Merge: remote patterns + any fallbacks not already covered by name
        remote_names = {name.lower() for name, _ in raw}
        for name, regex_str in _FALLBACK_PATTERNS:
            if name.lower() not in remote_names:
                raw.append((name, regex_str))

    return _compile_patterns(raw)


def redact_secrets(
    text: str, extra_patterns: list[tuple[str, re.Pattern[str]]] | None = None
) -> str:
    """Redact known secret patterns from text using loaded patterns.

    Args:
        text: Text to redact.
        extra_patterns: Optional additional patterns to apply.

    Returns:
        Text with secrets replaced by [REDACTED].
    """
    if not text:
        return text

    patterns = _compiled_patterns
    if extra_patterns:
        patterns = patterns + extra_patterns

    for _name, pattern in patterns:
        text = pattern.sub(REDACTED_PLACEHOLDER, text)

    return text


def redact_secrets_in_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact string values in a dict.

    Args:
        d: Dictionary to redact (not mutated; returns a new dict).

    Returns:
        New dictionary with string values redacted.
    """
    result: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, str):
            result[key] = redact_secrets(value)
        elif isinstance(value, dict):
            result[key] = redact_secrets_in_dict(value)
        else:
            result[key] = value
    return result


def initialize(cache_dir: Path) -> None:
    """Called at daemon startup to load/refresh patterns.

    Args:
        cache_dir: Directory for caching downloaded patterns (e.g., .oak/ci/).
    """
    global _compiled_patterns  # noqa: PLW0603
    _compiled_patterns = load_patterns(cache_dir)
    logger.info(f"Loaded {len(_compiled_patterns)} redaction patterns")
