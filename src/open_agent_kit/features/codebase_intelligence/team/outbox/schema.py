"""Database schema for team sync outbox tables."""

TEAM_OUTBOX_DDL = """
CREATE TABLE IF NOT EXISTS team_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    source_machine_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_team_outbox_status
    ON team_outbox(status);
CREATE INDEX IF NOT EXISTS idx_team_outbox_created
    ON team_outbox(created_at);
"""

TEAM_PULL_CURSOR_DDL = """
CREATE TABLE IF NOT EXISTS team_pull_cursor (
    server_url TEXT PRIMARY KEY,
    cursor_value TEXT,
    updated_at TEXT NOT NULL
);
"""
