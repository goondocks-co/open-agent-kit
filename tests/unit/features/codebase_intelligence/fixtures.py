"""Test fixtures for Codebase Intelligence unit tests."""

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITY_SCHEMA_VERSION,
    CI_SESSION_COLUMN_TRANSCRIPT_PATH,
)
from open_agent_kit.features.codebase_intelligence.daemon.constants import SessionStatus

# Schema
TEST_SCHEMA_VERSION = CI_ACTIVITY_SCHEMA_VERSION

# Agents and sessions
TEST_AGENT_CLAUDE = "claude"
TEST_SESSION_ID = "test-123"
TEST_SESSION_ID_S1 = "s1"
TEST_SESSION_ID_ONE = "test-session-1"
TEST_SESSION_ID_TWO = "test-session-2"
TEST_SESSION_ID_THREE = "test-session-3"

# Paths and timestamps
TEST_PROJECT_ROOT = "/tmp/project"
TEST_PROJECT_ROOT_SHORT = "/tmp"
TEST_PROJECT_ROOT_MISSING = "/nonexistent/path"
TEST_TRANSCRIPT_PATH = "/home/user/.claude/projects/abc/test-123.jsonl"
TEST_TRANSCRIPT_PATH_ONE = "/home/user/.claude/projects/abc/test-session-1.jsonl"
TEST_TRANSCRIPT_PATH_GENERIC = "/path/to/transcript.jsonl"
TEST_TRANSCRIPT_PATH_S1 = "/path/to/s1.jsonl"
TEST_STARTED_AT = "2026-01-01T00:00:00"
TEST_CREATED_AT_EPOCH = 1735689600

# SQLite
SQLITE_MEMORY_URI = ":memory:"

# Session status
TEST_SESSION_STATUS_COMPLETED = SessionStatus.COMPLETED

# Session columns
TEST_SESSION_COLUMN_TRANSCRIPT_PATH = CI_SESSION_COLUMN_TRANSCRIPT_PATH

# SQL statements
SQL_SESSIONS_TABLE_WITH_TRANSCRIPT = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    project_root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',
    prompt_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,
    summary TEXT,
    title TEXT,
    created_at_epoch INTEGER NOT NULL,
    parent_session_id TEXT,
    parent_session_reason TEXT,
    source_machine_id TEXT,
    transcript_path TEXT
)
"""

SQL_SESSIONS_TABLE_NO_TRANSCRIPT = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    project_root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',
    prompt_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,
    summary TEXT,
    title TEXT,
    created_at_epoch INTEGER NOT NULL,
    parent_session_id TEXT,
    parent_session_reason TEXT,
    source_machine_id TEXT
)
"""

SQL_INSERT_SESSION_WITH_TRANSCRIPT = (
    "INSERT INTO sessions (id, agent, project_root, started_at, created_at_epoch, transcript_path) "
    "VALUES ('{session_id}', '{agent}', '{project_root}', '{started_at}', {created_at_epoch}, '{path}')"
)

SQL_INSERT_SESSION_NO_TRANSCRIPT = (
    "INSERT INTO sessions (id, agent, project_root, started_at, created_at_epoch) "
    "VALUES ('{session_id}', '{agent}', '{project_root}', '{started_at}', {created_at_epoch})"
)

SQL_SELECT_SESSION_BY_ID = "SELECT * FROM sessions WHERE id = '{session_id}'"
SQL_SELECT_TRANSCRIPT_PATH_BY_ID = "SELECT transcript_path FROM sessions WHERE id = '{session_id}'"
