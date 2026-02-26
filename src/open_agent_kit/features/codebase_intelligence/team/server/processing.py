"""Skeleton schema for Mode 2 server-side processing queue.

This is groundwork only — no implementation. The queue will hold
raw session data from thin clients that delegate LLM processing
to the team server.
"""

TEAM_PROCESSING_QUEUE_DDL = """
CREATE TABLE IF NOT EXISTS team_processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_team_processing_queue_status
    ON team_processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_team_processing_queue_machine
    ON team_processing_queue(machine_id);
"""
