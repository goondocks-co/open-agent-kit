"""Tests for secrets redaction utility (M-SEC5).

Validates that:
- Known secret patterns are correctly redacted
- Normal text passes through unchanged
- Dict redaction works recursively
- Fallback patterns work without remote fetch
"""

from __future__ import annotations

import re
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.utils.redact import (
    _FALLBACK_PATTERNS,
    REDACTED_PLACEHOLDER,
    _compile_patterns,
    redact_secrets,
    redact_secrets_in_dict,
)

# Pre-compile fallback patterns for testing (simulates initialized state)
_test_patterns = _compile_patterns(_FALLBACK_PATTERNS)


def _redact(text: str) -> str:
    """Helper: redact using fallback patterns (no daemon init needed)."""
    return redact_secrets(text, extra_patterns=_test_patterns)


class TestRedactSecrets:
    """Tests for redact_secrets with various secret pattern types."""

    def test_aws_access_key(self) -> None:
        text = "Use key AKIAIOSFODNN7EXAMPLE for access"
        result = _redact(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_github_pat(self) -> None:
        text = "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = _redact(text)
        assert "ghp_" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_github_fine_grained_pat(self) -> None:
        text = "Token: github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZab"
        result = _redact(text)
        assert "github_pat_" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_bearer_token(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        result = _redact(text)
        assert "Bearer" not in result or "eyJ" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_jwt_token(self) -> None:
        text = "Set token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = _redact(text)
        assert "eyJhbGci" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_sk_key(self) -> None:
        text = "Use key sk-test1234567890abcdef1234 for API access"
        result = _redact(text)
        assert "sk-test1234567890abcdef1234" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_password_in_url(self) -> None:
        text = "Connect to postgres://admin:supersecretpassword@db.host.com:5432/mydb"
        result = _redact(text)
        assert "supersecretpassword" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_pem_private_key(self) -> None:
        text = "Found key: -----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        result = _redact(text)
        assert "BEGIN RSA PRIVATE KEY" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_generic_secret_assignment(self) -> None:
        text = """config has api_key="sk_live_abcdef1234567890abcdef" set"""
        result = _redact(text)
        assert "sk_live_abcdef1234567890abcdef" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_normal_text_unchanged(self) -> None:
        text = "This is a normal commit message with no secrets"
        result = _redact(text)
        assert result == text

    def test_empty_string_unchanged(self) -> None:
        assert _redact("") == ""

    def test_multiple_secrets_all_redacted(self) -> None:
        text = (
            "AWS: AKIAIOSFODNN7EXAMPLE, "
            "GitHub: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij, "
            "SK: sk-test1234567890abcdef1234"
        )
        result = _redact(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "ghp_" not in result
        assert "sk-test1234567890abcdef1234" not in result
        assert result.count(REDACTED_PLACEHOLDER) >= 3

    def test_extra_patterns_applied(self) -> None:
        custom = [("custom", re.compile(r"CUSTOM-[0-9]{6}"))]
        text = "Code: CUSTOM-123456 found"
        result = redact_secrets(text, extra_patterns=custom)
        assert "CUSTOM-123456" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_slack_bot_token(self) -> None:
        text = "Slack: xoxb-1234567890-1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZab"
        result = _redact(text)
        assert "xoxb-" not in result
        assert REDACTED_PLACEHOLDER in result


class TestRedactSecretsInDict:
    """Tests for recursive dict redaction."""

    def test_string_values_redacted(self) -> None:
        d = {"key": "Use AKIAIOSFODNN7EXAMPLE here", "count": 42}
        # Use extra_patterns since module-level _compiled_patterns may be empty
        import open_agent_kit.features.codebase_intelligence.utils.redact as redact_mod

        original = redact_mod._compiled_patterns
        try:
            redact_mod._compiled_patterns = _test_patterns
            result = redact_secrets_in_dict(d)
        finally:
            redact_mod._compiled_patterns = original

        assert "AKIAIOSFODNN7EXAMPLE" not in result["key"]
        assert result["count"] == 42

    def test_nested_dicts_handled(self) -> None:
        d = {"outer": {"inner": "key sk-test1234567890abcdef1234"}}
        import open_agent_kit.features.codebase_intelligence.utils.redact as redact_mod

        original = redact_mod._compiled_patterns
        try:
            redact_mod._compiled_patterns = _test_patterns
            result = redact_secrets_in_dict(d)
        finally:
            redact_mod._compiled_patterns = original

        assert "sk-test1234567890abcdef1234" not in result["outer"]["inner"]

    def test_empty_dict_returns_empty(self) -> None:
        assert redact_secrets_in_dict({}) == {}

    def test_non_string_values_preserved(self) -> None:
        d = {"flag": True, "count": 42, "items": [1, 2, 3]}
        import open_agent_kit.features.codebase_intelligence.utils.redact as redact_mod

        original = redact_mod._compiled_patterns
        try:
            redact_mod._compiled_patterns = _test_patterns
            result = redact_secrets_in_dict(d)
        finally:
            redact_mod._compiled_patterns = original

        assert result["flag"] is True
        assert result["count"] == 42
        assert result["items"] == [1, 2, 3]


class TestLoadPatterns:
    """Tests for pattern loading and caching."""

    def test_load_patterns_returns_fallbacks_on_missing_cache(self, tmp_path: Path) -> None:
        from open_agent_kit.features.codebase_intelligence.utils.redact import load_patterns

        patterns = load_patterns(tmp_path)
        assert len(patterns) >= len(_FALLBACK_PATTERNS)
        # Verify they are compiled
        for _name, pat in patterns:
            assert isinstance(pat, re.Pattern)
