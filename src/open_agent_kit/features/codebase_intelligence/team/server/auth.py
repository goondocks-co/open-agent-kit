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
    TEAM_JOIN_STATUS_APPROVED,
    TEAM_JOIN_STATUS_PENDING,
    TEAM_JOIN_STATUS_REJECTED,
    TEAM_LOG_JOIN_PENDING_KEY_VERIFY,
)

logger = logging.getLogger(__name__)

# ---- DDL ----

TEAM_API_KEYS_DDL = """
CREATE TABLE IF NOT EXISTS team_api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    machine_id TEXT,
    display_name TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    approved_at TEXT,
    permissions TEXT DEFAULT 'member'
);
"""

# Migration guard for existing DBs that lack the new columns.
TEAM_API_KEYS_MIGRATION_APPROVED_AT = "ALTER TABLE team_api_keys ADD COLUMN approved_at TEXT"
TEAM_API_KEYS_MIGRATION_DISPLAY_NAME = "ALTER TABLE team_api_keys ADD COLUMN display_name TEXT"

# ---- Data class ----


@dataclass
class ApiKeyInfo:
    """Information about a team API key (never contains the plaintext key)."""

    id: str
    name: str
    machine_id: str | None
    display_name: str | None
    created_at: str
    last_used_at: str | None
    revoked_at: str | None
    approved_at: str | None
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
    """Create a new API key (auto-approved).

    Used for loopback keys and manually-created keys. Sets ``approved_at``
    immediately so the key is usable without an approval step.

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
        "INSERT INTO team_api_keys "
        "(id, name, key_hash, created_at, approved_at, permissions) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key_id, name, key_hash, now, now, TEAM_API_KEY_PERMISSIONS_MEMBER),
    )
    conn.commit()
    return key_id, plaintext_key


def verify_api_key(conn: sqlite3.Connection, key: str) -> ApiKeyInfo | None:
    """Verify an API key and return its info.

    Updates ``last_used_at`` on success. Returns ``None`` for pending
    (not yet approved) keys, but logs distinctly from truly invalid keys.

    Args:
        conn: SQLite connection with team_api_keys table.
        key: Plaintext API key to verify.

    Returns:
        ApiKeyInfo if valid, approved, and not revoked; None otherwise.
    """
    key_hash = _hash_key(key)
    row = conn.execute(
        "SELECT id, name, machine_id, display_name, created_at, "
        "last_used_at, revoked_at, approved_at, permissions "
        "FROM team_api_keys WHERE key_hash = ?",
        (key_hash,),
    ).fetchone()

    if row is None:
        return None

    (
        key_id,
        name,
        machine_id,
        display_name,
        created_at,
        last_used_at,
        revoked_at,
        approved_at,
        permissions,
    ) = row

    if revoked_at is not None:
        return None

    # Pending keys are not yet approved — reject but log distinctly
    if approved_at is None:
        logger.info(TEAM_LOG_JOIN_PENDING_KEY_VERIFY.format(key_id=key_id))
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
        display_name=display_name,
        created_at=created_at,
        last_used_at=now,
        revoked_at=revoked_at,
        approved_at=approved_at,
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


def revoke_keys_by_name(conn: sqlite3.Connection, name: str) -> int:
    """Revoke all active keys with the given name.

    Useful for cleaning up loopback keys when server mode is toggled.

    Args:
        conn: SQLite connection with team_api_keys table.
        name: The key name to match (e.g. "_loopback").

    Returns:
        Number of keys revoked.
    """
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "UPDATE team_api_keys SET revoked_at = ? WHERE name = ? AND revoked_at IS NULL",
        (now, name),
    )
    conn.commit()
    return cursor.rowcount


def delete_revoked_keys_by_name(conn: sqlite3.Connection, name: str) -> int:
    """Permanently delete all revoked keys with the given name.

    Loopback keys have no audit value once revoked — delete them to
    prevent unbounded table growth.

    Args:
        conn: SQLite connection with team_api_keys table.
        name: The key name to match (e.g. "_loopback").

    Returns:
        Number of rows deleted.
    """
    cursor = conn.execute(
        "DELETE FROM team_api_keys WHERE name = ? AND revoked_at IS NOT NULL",
        (name,),
    )
    conn.commit()
    return cursor.rowcount


def list_api_keys(conn: sqlite3.Connection) -> list[ApiKeyInfo]:
    """List all API keys (active and revoked).

    Args:
        conn: SQLite connection with team_api_keys table.

    Returns:
        List of ApiKeyInfo for all keys.
    """
    rows = conn.execute(
        "SELECT id, name, machine_id, display_name, created_at, "
        "last_used_at, revoked_at, approved_at, permissions "
        "FROM team_api_keys ORDER BY created_at"
    ).fetchall()

    return [
        ApiKeyInfo(
            id=row[0],
            name=row[1],
            machine_id=row[2],
            display_name=row[3],
            created_at=row[4],
            last_used_at=row[5],
            revoked_at=row[6],
            approved_at=row[7],
            permissions=row[8],
        )
        for row in rows
    ]


# ---- Pending key CRUD (join request flow) ----


def create_pending_key(
    conn: sqlite3.Connection,
    name: str,
    key_hash: str,
    machine_id: str,
    display_name: str,
) -> str:
    """Create a pending (unapproved) API key from a join request.

    The key hash is provided by the client -- we never see the plaintext.

    Args:
        conn: SQLite connection with team_api_keys table.
        name: Human-readable name for this key.
        key_hash: SHA-256 hex digest of the plaintext key.
        machine_id: Requesting machine's identifier.
        display_name: Human-readable display name for the requester.

    Returns:
        The generated key_id.
    """
    key_id = _generate_key_id()
    now = datetime.now(UTC).isoformat()

    conn.execute(
        "INSERT INTO team_api_keys "
        "(id, name, key_hash, machine_id, display_name, created_at, permissions) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (key_id, name, key_hash, machine_id, display_name, now, TEAM_API_KEY_PERMISSIONS_MEMBER),
    )
    conn.commit()
    return key_id


def approve_key(conn: sqlite3.Connection, key_id: str) -> bool:
    """Approve a pending join request by setting ``approved_at``.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_id: The key ID to approve.

    Returns:
        True if the key was found and approved, False otherwise.
    """
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "UPDATE team_api_keys SET approved_at = ? "
        "WHERE id = ? AND approved_at IS NULL AND revoked_at IS NULL",
        (now, key_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def reject_key(conn: sqlite3.Connection, key_id: str) -> bool:
    """Reject a pending join request by revoking the key.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_id: The key ID to reject.

    Returns:
        True if the key was found and rejected, False otherwise.
    """
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "UPDATE team_api_keys SET revoked_at = ? " "WHERE id = ? AND revoked_at IS NULL",
        (now, key_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_pending_keys(conn: sqlite3.Connection) -> list[ApiKeyInfo]:
    """List all pending (unapproved, non-revoked) API keys.

    Args:
        conn: SQLite connection with team_api_keys table.

    Returns:
        List of ApiKeyInfo for pending keys.
    """
    rows = conn.execute(
        "SELECT id, name, machine_id, display_name, created_at, "
        "last_used_at, revoked_at, approved_at, permissions "
        "FROM team_api_keys "
        "WHERE approved_at IS NULL AND revoked_at IS NULL "
        "ORDER BY created_at"
    ).fetchall()

    return [
        ApiKeyInfo(
            id=row[0],
            name=row[1],
            machine_id=row[2],
            display_name=row[3],
            created_at=row[4],
            last_used_at=row[5],
            revoked_at=row[6],
            approved_at=row[7],
            permissions=row[8],
        )
        for row in rows
    ]


def find_key_by_hash(conn: sqlite3.Connection, key_hash: str) -> ApiKeyInfo | None:
    """Look up any API key by its hash (including pending/revoked).

    Unlike ``verify_api_key``, this returns the key regardless of status.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_hash: SHA-256 hex digest of the plaintext key.

    Returns:
        ApiKeyInfo if found, None otherwise.
    """
    row = conn.execute(
        "SELECT id, name, machine_id, display_name, created_at, "
        "last_used_at, revoked_at, approved_at, permissions "
        "FROM team_api_keys WHERE key_hash = ?",
        (key_hash,),
    ).fetchone()

    if row is None:
        return None

    return ApiKeyInfo(
        id=row[0],
        name=row[1],
        machine_id=row[2],
        display_name=row[3],
        created_at=row[4],
        last_used_at=row[5],
        revoked_at=row[6],
        approved_at=row[7],
        permissions=row[8],
    )


def get_key_by_id(conn: sqlite3.Connection, key_id: str) -> ApiKeyInfo | None:
    """Look up an API key by its ID.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_id: The key ID to look up.

    Returns:
        ApiKeyInfo if found, None otherwise.
    """
    row = conn.execute(
        "SELECT id, name, machine_id, display_name, created_at, "
        "last_used_at, revoked_at, approved_at, permissions "
        "FROM team_api_keys WHERE id = ?",
        (key_id,),
    ).fetchone()

    if row is None:
        return None

    return ApiKeyInfo(
        id=row[0],
        name=row[1],
        machine_id=row[2],
        display_name=row[3],
        created_at=row[4],
        last_used_at=row[5],
        revoked_at=row[6],
        approved_at=row[7],
        permissions=row[8],
    )


def get_key_join_status(conn: sqlite3.Connection, key_id: str) -> str | None:
    """Get the join status for a key by ID.

    Args:
        conn: SQLite connection with team_api_keys table.
        key_id: The key ID to check.

    Returns:
        One of ``"pending"``, ``"approved"``, ``"rejected"``, or ``None``
        if not found.
    """
    row = conn.execute(
        "SELECT approved_at, revoked_at FROM team_api_keys WHERE id = ?",
        (key_id,),
    ).fetchone()

    if row is None:
        return None

    approved_at, revoked_at = row
    if revoked_at is not None:
        return TEAM_JOIN_STATUS_REJECTED
    if approved_at is not None:
        return TEAM_JOIN_STATUS_APPROVED
    return TEAM_JOIN_STATUS_PENDING


def migrate_api_keys_table(conn: sqlite3.Connection) -> None:
    """Add new columns to existing team_api_keys tables.

    Safe to call multiple times -- checks for column existence first.
    """
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(team_api_keys)").fetchall()
    }

    if "approved_at" not in existing_columns:
        conn.execute(TEAM_API_KEYS_MIGRATION_APPROVED_AT)
        # Auto-approve all existing keys (backward compatibility)
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE team_api_keys SET approved_at = ? WHERE approved_at IS NULL",
            (now,),
        )
        conn.commit()
        logger.info("Migrated team_api_keys: added approved_at column")

    if "display_name" not in existing_columns:
        conn.execute(TEAM_API_KEYS_MIGRATION_DISPLAY_NAME)
        conn.commit()
        logger.info("Migrated team_api_keys: added display_name column")


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
