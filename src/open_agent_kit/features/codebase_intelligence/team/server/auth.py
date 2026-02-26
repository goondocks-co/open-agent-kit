"""Team server API key authentication.

Provides multi-key API key management for team server access.
Keys are stored as SHA-256 hashes -- plaintext is returned only at creation time.
"""

import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus

from fastapi import Request

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_KEY_PERMISSIONS_MEMBER,
    TEAM_API_KEY_PREFIX,
    TEAM_API_KEY_RANDOM_BYTES,
    TEAM_AUTH_ERROR_INVALID_KEY,
    TEAM_AUTH_ERROR_INVALID_SCHEME,
    TEAM_AUTH_ERROR_MISSING,
    TEAM_AUTH_HEADER_NAME,
    TEAM_AUTH_SCHEME_BEARER,
)

logger = logging.getLogger(__name__)

# ---- DDL ----

TEAM_API_KEYS_DDL = """
CREATE TABLE IF NOT EXISTS team_api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    machine_id TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    permissions TEXT DEFAULT 'member'
);
"""

# ---- Data class ----


@dataclass
class ApiKeyInfo:
    """Information about a team API key (never contains the plaintext key)."""

    id: str
    name: str
    machine_id: str | None
    created_at: str
    last_used_at: str | None
    revoked_at: str | None
    permissions: str


# ---- Key helpers ----


def _hash_key(key: str) -> str:
    """SHA-256 hash a plaintext API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def _generate_key_id() -> str:
    """Generate a short unique key ID."""
    return secrets.token_hex(8)


# ---- CRUD operations ----


def create_api_key(conn: sqlite3.Connection, name: str) -> tuple[str, str]:
    """Create a new API key.

    Args:
        conn: SQLite connection with team_api_keys table.
        name: Human-readable name for this key.

    Returns:
        Tuple of (key_id, plaintext_key). The plaintext key is only
        available at creation time.
    """
    key_id = _generate_key_id()
    plaintext_key = f"{TEAM_API_KEY_PREFIX}{secrets.token_hex(TEAM_API_KEY_RANDOM_BYTES)}"
    key_hash = _hash_key(plaintext_key)
    now = datetime.now(UTC).isoformat()

    conn.execute(
        "INSERT INTO team_api_keys (id, name, key_hash, created_at, permissions) "
        "VALUES (?, ?, ?, ?, ?)",
        (key_id, name, key_hash, now, TEAM_API_KEY_PERMISSIONS_MEMBER),
    )
    conn.commit()
    return key_id, plaintext_key


def verify_api_key(conn: sqlite3.Connection, key: str) -> ApiKeyInfo | None:
    """Verify an API key and return its info.

    Updates ``last_used_at`` on success.

    Args:
        conn: SQLite connection with team_api_keys table.
        key: Plaintext API key to verify.

    Returns:
        ApiKeyInfo if valid and not revoked, None otherwise.
    """
    key_hash = _hash_key(key)
    row = conn.execute(
        "SELECT id, name, machine_id, created_at, last_used_at, revoked_at, permissions "
        "FROM team_api_keys WHERE key_hash = ?",
        (key_hash,),
    ).fetchone()

    if row is None:
        return None

    key_id, name, machine_id, created_at, last_used_at, revoked_at, permissions = row

    if revoked_at is not None:
        return None

    # Update last_used_at
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE team_api_keys SET last_used_at = ? WHERE id = ?",
        (now, key_id),
    )
    conn.commit()

    return ApiKeyInfo(
        id=key_id,
        name=name,
        machine_id=machine_id,
        created_at=created_at,
        last_used_at=now,
        revoked_at=revoked_at,
        permissions=permissions,
    )


def revoke_api_key(conn: sqlite3.Connection, key_id: str) -> bool:
    """Revoke an API key by ID.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_id: The key ID to revoke.

    Returns:
        True if the key was found and revoked, False otherwise.
    """
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "UPDATE team_api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
        (now, key_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_api_keys(conn: sqlite3.Connection) -> list[ApiKeyInfo]:
    """List all API keys (active and revoked).

    Args:
        conn: SQLite connection with team_api_keys table.

    Returns:
        List of ApiKeyInfo for all keys.
    """
    rows = conn.execute(
        "SELECT id, name, machine_id, created_at, last_used_at, revoked_at, permissions "
        "FROM team_api_keys ORDER BY created_at"
    ).fetchall()

    return [
        ApiKeyInfo(
            id=row[0],
            name=row[1],
            machine_id=row[2],
            created_at=row[3],
            last_used_at=row[4],
            revoked_at=row[5],
            permissions=row[6],
        )
        for row in rows
    ]


# ---- FastAPI dependency ----


def _get_team_db_conn() -> sqlite3.Connection:
    """Get the team server SQLite connection from daemon state.

    Returns:
        SQLite connection for team server tables.

    Raises:
        RuntimeError: If the daemon state or activity store is not available.
    """
    from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

    state = get_state()
    if state.activity_store is None:
        raise RuntimeError("Activity store not initialized")
    return state.activity_store._get_connection()


async def verify_team_token(request: Request) -> str:
    """FastAPI dependency: extract and verify team API key from Bearer token.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The machine_id associated with the API key (or key_id if no
        machine_id is bound).

    Raises:
        HTTPException-like: Returns 401 JSON response on failure.
    """
    auth_value = request.headers.get(TEAM_AUTH_HEADER_NAME)

    if not auth_value:
        return _raise_auth_error(TEAM_AUTH_ERROR_MISSING)

    parts = auth_value.split(None, 1)
    if len(parts) != 2 or parts[0] != TEAM_AUTH_SCHEME_BEARER:
        return _raise_auth_error(TEAM_AUTH_ERROR_INVALID_SCHEME)

    token = parts[1]
    conn = _get_team_db_conn()
    info = verify_api_key(conn, token)

    if info is None:
        return _raise_auth_error(TEAM_AUTH_ERROR_INVALID_KEY)

    # Return machine_id if bound, otherwise use key_id as identity
    return info.machine_id or info.id


def _raise_auth_error(detail: str) -> str:
    """Raise an HTTP 401 error via FastAPI's HTTPException.

    Args:
        detail: Error detail message.

    Raises:
        HTTPException: Always raised.
    """
    from fastapi import HTTPException

    raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=detail)
