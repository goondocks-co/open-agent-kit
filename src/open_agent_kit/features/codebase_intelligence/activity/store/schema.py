"""Database schema for activity store.

Contains schema version and SQL for creating the database schema.
"""

# Schema version for migrations
# v4: Added source_type to prompt_batches (user, agent_notification, plan, system)
# v5: Added plan_file_path to prompt_batches (for plan source type)
# v6: Added plan_content to prompt_batches (store actual plan content in DB)
# v7: Added plan_embedded to prompt_batches (track ChromaDB indexing status for plans)
# v8: Added composite indexes for common query patterns (performance optimization)
# v9: Added title column to sessions (LLM-generated short session title)
# v10: Added indexes for memory filtering (type, context, created_at) + FTS5 for search
# v11: Added content_hash columns for multi-machine backup deduplication
# v12: Added parent_session_id/reason for session linking, source_plan_batch_id for plan tracking
# v13: Added source_machine_id for origin tracking (enables efficient team backups)
# v14: Added agent_runs table for CI agent execution tracking
# v15: Added saved_tasks table for reusable task templates
# v16: Updated source_machine_id to privacy-preserving format (github_username_hash)
# v17: Added suggested_parent_dismissed to sessions, session_link_events table for analytics
# v18: Added session_relationships table for many-to-many semantic session relationships
# v19: Added agent_schedules table for cron scheduling runtime state
# v20: Added idx_sessions_created_at for dashboard sorting performance
# v21: Added response_summary to prompt_batches for capturing agent responses
SCHEMA_VERSION = 21

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Memory observations table (source of truth for extracted memories)
-- ChromaDB is just a search index over this data
CREATE TABLE IF NOT EXISTS memory_observations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    prompt_batch_id INTEGER,
    observation TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    context TEXT,
    tags TEXT,  -- Comma-separated tags
    importance INTEGER DEFAULT 5,
    file_path TEXT,
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL,
    embedded BOOLEAN DEFAULT FALSE,  -- Has this been added to ChromaDB?
    content_hash TEXT,  -- Hash for cross-machine deduplication (v11)
    source_machine_id TEXT,  -- Machine that originated this record (v13)
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (prompt_batch_id) REFERENCES prompt_batches(id)
);

-- Index for finding unembedded observations (for rebuilding ChromaDB)
CREATE INDEX IF NOT EXISTS idx_memory_observations_embedded ON memory_observations(embedded);
CREATE INDEX IF NOT EXISTS idx_memory_observations_session ON memory_observations(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_observations_hash ON memory_observations(content_hash);

-- Indexes for memory filtering and browsing (v10)
CREATE INDEX IF NOT EXISTS idx_memory_observations_type ON memory_observations(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_observations_context ON memory_observations(context);
CREATE INDEX IF NOT EXISTS idx_memory_observations_created ON memory_observations(created_at_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_memory_observations_type_created ON memory_observations(memory_type, created_at_epoch DESC);

-- FTS5 virtual table for full-text search on memories (v10)
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    observation,
    context,
    content='memory_observations',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync with memory_observations (v10)
CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memory_observations BEGIN
    INSERT INTO memories_fts(rowid, observation, context) VALUES (NEW.rowid, NEW.observation, NEW.context);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memory_observations BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, observation, context) VALUES ('delete', OLD.rowid, OLD.observation, OLD.context);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memory_observations BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, observation, context) VALUES ('delete', OLD.rowid, OLD.observation, OLD.context);
    INSERT INTO memories_fts(rowid, observation, context) VALUES (NEW.rowid, NEW.observation, NEW.context);
END;

-- Sessions table (Claude Code session - from launch to exit)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    project_root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',  -- active, completed, abandoned
    prompt_count INTEGER DEFAULT 0,
    tool_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,  -- Has background processor handled this?
    summary TEXT,  -- LLM-generated session summary
    title TEXT,  -- LLM-generated short session title (10-20 words)
    created_at_epoch INTEGER NOT NULL,
    parent_session_id TEXT,  -- Session this was derived from (v12)
    parent_session_reason TEXT,  -- Why linked: 'clear', 'compact', 'inferred' (v12)
    source_machine_id TEXT  -- Machine that originated this record (v13)
);

-- Prompt batches table (activities between user prompts - the unit of processing)
CREATE TABLE IF NOT EXISTS prompt_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    prompt_number INTEGER NOT NULL,  -- Sequence number within session
    user_prompt TEXT,  -- Full user prompt (up to 10K chars) for context
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT DEFAULT 'active',  -- active, completed
    activity_count INTEGER DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,  -- Has background processor handled this?
    classification TEXT,  -- LLM classification: exploration, implementation, debugging, refactoring
    source_type TEXT DEFAULT 'user',  -- user, agent_notification, plan, system, derived_plan
    plan_file_path TEXT,  -- Path to plan file (for source_type='plan')
    plan_content TEXT,  -- Full plan content (stored for self-contained CI)
    plan_embedded INTEGER DEFAULT 0,  -- Has plan been indexed in ChromaDB? (v7)
    created_at_epoch INTEGER NOT NULL,
    content_hash TEXT,  -- Hash for cross-machine deduplication (v11)
    source_plan_batch_id INTEGER,  -- Link to plan batch being implemented (v12)
    source_machine_id TEXT,  -- Machine that originated this record (v13)
    response_summary TEXT,  -- Agent's final response/summary (v21)
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (source_plan_batch_id) REFERENCES prompt_batches(id)
);

-- Activities table (raw tool executions)
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    prompt_batch_id INTEGER,  -- Links to the prompt batch (for prompt-level processing)
    tool_name TEXT NOT NULL,
    tool_input TEXT,  -- JSON of input params (sanitized)
    tool_output_summary TEXT,  -- Brief summary, not full output
    file_path TEXT,  -- Primary file affected (if any)
    files_affected TEXT,  -- JSON array of all files
    duration_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    timestamp TEXT NOT NULL,
    timestamp_epoch INTEGER NOT NULL,
    processed BOOLEAN DEFAULT FALSE,  -- Has this activity been processed?
    observation_id TEXT,  -- Link to extracted observation (if any)
    content_hash TEXT,  -- Hash for cross-machine deduplication (v11)
    source_machine_id TEXT,  -- Machine that originated this record (v13)
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (prompt_batch_id) REFERENCES prompt_batches(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_activities_session ON activities(session_id);
CREATE INDEX IF NOT EXISTS idx_activities_prompt_batch ON activities(prompt_batch_id);
CREATE INDEX IF NOT EXISTS idx_activities_tool ON activities(tool_name);
CREATE INDEX IF NOT EXISTS idx_activities_processed ON activities(processed);
CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON activities(timestamp_epoch);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_processed ON sessions(processed);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_session ON prompt_batches(session_id);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_processed ON prompt_batches(processed);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_hash ON prompt_batches(content_hash);
CREATE INDEX IF NOT EXISTS idx_activities_hash ON activities(content_hash);

-- Indexes for source_machine_id filtering (v13 - origin tracking for efficient backups)
CREATE INDEX IF NOT EXISTS idx_sessions_source_machine ON sessions(source_machine_id);
CREATE INDEX IF NOT EXISTS idx_prompt_batches_source_machine ON prompt_batches(source_machine_id);
CREATE INDEX IF NOT EXISTS idx_memory_observations_source_machine ON memory_observations(source_machine_id);
CREATE INDEX IF NOT EXISTS idx_activities_source_machine ON activities(source_machine_id);

-- FTS5 virtual table for full-text search across activities
CREATE VIRTUAL TABLE IF NOT EXISTS activities_fts USING fts5(
    tool_name,
    tool_input,
    tool_output_summary,
    file_path,
    error_message,
    content='activities',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS activities_ai AFTER INSERT ON activities BEGIN
    INSERT INTO activities_fts(rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES (new.id, new.tool_name, new.tool_input, new.tool_output_summary, new.file_path, new.error_message);
END;

CREATE TRIGGER IF NOT EXISTS activities_ad AFTER DELETE ON activities BEGIN
    INSERT INTO activities_fts(activities_fts, rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES ('delete', old.id, old.tool_name, old.tool_input, old.tool_output_summary, old.file_path, old.error_message);
END;

CREATE TRIGGER IF NOT EXISTS activities_au AFTER UPDATE ON activities BEGIN
    INSERT INTO activities_fts(activities_fts, rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES ('delete', old.id, old.tool_name, old.tool_input, old.tool_output_summary, old.file_path, old.error_message);
    INSERT INTO activities_fts(rowid, tool_name, tool_input, tool_output_summary, file_path, error_message)
    VALUES (new.id, new.tool_name, new.tool_input, new.tool_output_summary, new.file_path, new.error_message);
END;

-- Agent runs table (CI agent executions via claude-code-sdk) (v14)
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled, timeout

    -- Timing
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL,
    started_at TEXT,
    started_at_epoch INTEGER,
    completed_at TEXT,
    completed_at_epoch INTEGER,

    -- Results
    result TEXT,  -- Final output/summary from the agent
    error TEXT,  -- Error message if failed
    turns_used INTEGER DEFAULT 0,
    cost_usd REAL,

    -- Files modified (JSON arrays)
    files_created TEXT,  -- JSON array of file paths
    files_modified TEXT,  -- JSON array of file paths
    files_deleted TEXT,  -- JSON array of file paths

    -- Configuration snapshot (for reproducibility)
    project_config TEXT,  -- JSON of project config at run time
    system_prompt_hash TEXT,  -- Hash of system prompt used

    -- Machine tracking
    source_machine_id TEXT
);

-- Indexes for agent_runs
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_created ON agent_runs(agent_name, created_at_epoch DESC);

-- Session link events table (v17 - analytics for user-driven linking)
CREATE TABLE IF NOT EXISTS session_link_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- auto_linked, suggestion_accepted, suggestion_rejected, manual_linked, unlinked
    old_parent_id TEXT,
    new_parent_id TEXT,
    suggested_parent_id TEXT,
    suggestion_confidence REAL,
    link_reason TEXT,
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL
);

-- Indexes for session_link_events
CREATE INDEX IF NOT EXISTS idx_session_link_events_session ON session_link_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_link_events_type ON session_link_events(event_type);
CREATE INDEX IF NOT EXISTS idx_session_link_events_created ON session_link_events(created_at_epoch DESC);

-- Session relationships table (v18 - many-to-many semantic relationships)
-- Complements parent-child (temporal continuity) with semantic relationships
CREATE TABLE IF NOT EXISTS session_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_a_id TEXT NOT NULL,
    session_b_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  -- 'related'
    similarity_score REAL,            -- Vector similarity when created
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL,
    created_by TEXT NOT NULL,         -- 'suggestion', 'manual'

    FOREIGN KEY (session_a_id) REFERENCES sessions(id),
    FOREIGN KEY (session_b_id) REFERENCES sessions(id),
    UNIQUE(session_a_id, session_b_id)  -- Prevent duplicates (a->b only, not b->a)
);

-- Indexes for session_relationships
CREATE INDEX IF NOT EXISTS idx_session_relationships_a ON session_relationships(session_a_id);
CREATE INDEX IF NOT EXISTS idx_session_relationships_b ON session_relationships(session_b_id);
CREATE INDEX IF NOT EXISTS idx_session_relationships_type ON session_relationships(relationship_type);

-- Agent schedules table (v19 - runtime state for cron scheduling)
-- YAML defines schedule (cron + description), DB tracks runtime state
CREATE TABLE IF NOT EXISTS agent_schedules (
    instance_name TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 1,
    last_run_at TEXT,
    last_run_at_epoch INTEGER,
    last_run_id TEXT,
    next_run_at TEXT,
    next_run_at_epoch INTEGER,
    created_at TEXT NOT NULL,
    created_at_epoch INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch INTEGER NOT NULL
);

-- Index for finding due schedules
CREATE INDEX IF NOT EXISTS idx_agent_schedules_enabled_next
    ON agent_schedules(enabled, next_run_at_epoch);
"""
