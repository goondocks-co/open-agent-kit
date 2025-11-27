"""Database migration functions for activity store.

Contains all migration logic for upgrading database schema versions.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def apply_migrations(conn: sqlite3.Connection, from_version: int) -> None:
    """Apply schema migrations from current version to latest.

    Args:
        conn: Database connection (within transaction).
        from_version: Current schema version.
    """
    # No migrations needed for v1.0 (initial release).
    # Add new migrations here for post-release schema upgrades.
    pass
