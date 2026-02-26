"""Tests for team server API key authentication.

Tests cover:
- create_api_key returns properly formatted key
- verify_api_key with valid key
- verify_api_key with invalid key returns None
- verify_api_key with revoked key returns None
- revoke_api_key
- list_api_keys
"""

import sqlite3

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_KEY_PERMISSIONS_MEMBER,
    TEAM_API_KEY_PREFIX,
    TEAM_API_KEY_RANDOM_BYTES,
)
from open_agent_kit.features.codebase_intelligence.team.server.auth import (
    TEAM_API_KEYS_DDL,
    create_api_key,
    list_api_keys,
    revoke_api_key,
    verify_api_key,
)


def _make_db() -> sqlite3.Connection:
    """Create an in-memory database with the team_api_keys table."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(TEAM_API_KEYS_DDL)
    return conn


# =============================================================================
# create_api_key
# =============================================================================


class TestCreateApiKey:
    """Test API key creation."""

    def test_returns_key_id_and_plaintext(self):
        """create_api_key returns a (key_id, plaintext_key) tuple."""
        conn = _make_db()
        key_id, plaintext = create_api_key(conn, "test-key")
        assert isinstance(key_id, str)
        assert len(key_id) > 0
        assert isinstance(plaintext, str)
        assert len(plaintext) > 0

    def test_key_has_correct_prefix(self):
        """Plaintext key starts with the oak_team_ prefix."""
        conn = _make_db()
        _, plaintext = create_api_key(conn, "test-key")
        assert plaintext.startswith(TEAM_API_KEY_PREFIX)

    def test_key_has_correct_length(self):
        """Plaintext key has prefix + 64 hex chars (32 bytes)."""
        conn = _make_db()
        _, plaintext = create_api_key(conn, "test-key")
        hex_part = plaintext[len(TEAM_API_KEY_PREFIX) :]
        assert len(hex_part) == TEAM_API_KEY_RANDOM_BYTES * 2

    def test_key_stored_in_database(self):
        """Key row exists in database after creation."""
        conn = _make_db()
        key_id, _ = create_api_key(conn, "my-key")
        row = conn.execute(
            "SELECT id, name, permissions FROM team_api_keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == key_id
        assert row[1] == "my-key"
        assert row[2] == TEAM_API_KEY_PERMISSIONS_MEMBER

    def test_plaintext_not_stored(self):
        """Plaintext key must NOT be stored -- only the hash."""
        conn = _make_db()
        _, plaintext = create_api_key(conn, "test-key")
        row = conn.execute("SELECT key_hash FROM team_api_keys").fetchone()
        assert row is not None
        assert row[0] != plaintext


# =============================================================================
# verify_api_key
# =============================================================================


class TestVerifyApiKey:
    """Test API key verification."""

    def test_valid_key_returns_info(self):
        """verify_api_key returns ApiKeyInfo for a valid key."""
        conn = _make_db()
        key_id, plaintext = create_api_key(conn, "valid-key")
        info = verify_api_key(conn, plaintext)
        assert info is not None
        assert info.id == key_id
        assert info.name == "valid-key"
        assert info.permissions == TEAM_API_KEY_PERMISSIONS_MEMBER
        assert info.revoked_at is None

    def test_valid_key_updates_last_used(self):
        """verify_api_key updates last_used_at on success."""
        conn = _make_db()
        _, plaintext = create_api_key(conn, "used-key")
        info = verify_api_key(conn, plaintext)
        assert info is not None
        assert info.last_used_at is not None

    def test_invalid_key_returns_none(self):
        """verify_api_key returns None for an unknown key."""
        conn = _make_db()
        result = verify_api_key(conn, "oak_team_nonexistent_key_value")
        assert result is None

    def test_revoked_key_returns_none(self):
        """verify_api_key returns None for a revoked key."""
        conn = _make_db()
        key_id, plaintext = create_api_key(conn, "revoked-key")
        revoke_api_key(conn, key_id)
        result = verify_api_key(conn, plaintext)
        assert result is None


# =============================================================================
# revoke_api_key
# =============================================================================


class TestRevokeApiKey:
    """Test API key revocation."""

    def test_revoke_existing_key(self):
        """revoke_api_key returns True for an existing active key."""
        conn = _make_db()
        key_id, _ = create_api_key(conn, "to-revoke")
        result = revoke_api_key(conn, key_id)
        assert result is True

    def test_revoke_nonexistent_key(self):
        """revoke_api_key returns False for a nonexistent key."""
        conn = _make_db()
        result = revoke_api_key(conn, "nonexistent-id")
        assert result is False

    def test_revoke_already_revoked(self):
        """revoke_api_key returns False for an already-revoked key."""
        conn = _make_db()
        key_id, _ = create_api_key(conn, "double-revoke")
        revoke_api_key(conn, key_id)
        result = revoke_api_key(conn, key_id)
        assert result is False

    def test_revoked_key_has_revoked_at(self):
        """Revoked key has a revoked_at timestamp."""
        conn = _make_db()
        key_id, _ = create_api_key(conn, "check-timestamp")
        revoke_api_key(conn, key_id)
        row = conn.execute(
            "SELECT revoked_at FROM team_api_keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        assert row is not None
        assert row[0] is not None


# =============================================================================
# list_api_keys
# =============================================================================


class TestListApiKeys:
    """Test listing all API keys."""

    def test_empty_database(self):
        """list_api_keys returns empty list for empty database."""
        conn = _make_db()
        result = list_api_keys(conn)
        assert result == []

    def test_returns_all_keys(self):
        """list_api_keys returns all keys including revoked."""
        conn = _make_db()
        key_id_1, _ = create_api_key(conn, "key-1")
        key_id_2, _ = create_api_key(conn, "key-2")
        revoke_api_key(conn, key_id_2)

        result = list_api_keys(conn)
        assert len(result) == 2
        names = {k.name for k in result}
        assert names == {"key-1", "key-2"}

    def test_revoked_key_in_list(self):
        """Revoked keys appear in list with revoked_at set."""
        conn = _make_db()
        key_id, _ = create_api_key(conn, "listed-revoked")
        revoke_api_key(conn, key_id)

        result = list_api_keys(conn)
        assert len(result) == 1
        assert result[0].revoked_at is not None
