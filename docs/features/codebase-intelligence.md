# Codebase Intelligence

Codebase Intelligence (CI) is OAK's semantic code understanding feature. It provides AI agents with deep, contextual knowledge of your codebase through vector embeddings, AST-aware chunking, and persistent memory.

## Overview

Codebase Intelligence consists of:

- **Background Daemon**: A FastAPI server that manages indexing, search, and memory
- **Vector Index**: ChromaDB-backed semantic storage of code chunks and memories
- **AST-aware Chunking**: Tree-sitter powered code parsing for semantic code units
- **MCP Integration**: Model Context Protocol tools for AI agent access
- **Web Dashboard**: Browser-based UI for configuration and exploration

## Quick Start

```bash
# Enable the feature during init (or add to existing project)
oak init --feature codebase-intelligence

# Or add to an existing OAK project
oak feature add codebase-intelligence

# Start the daemon
oak ci start

# Open the dashboard
open http://localhost:37801/ui  # Port varies by project
```

## CLI Commands

### `oak ci start`

Start the Codebase Intelligence daemon.

```bash
oak ci start              # Interactive - prompts to install missing parsers
oak ci start -i           # Auto-install missing parsers
```

On first start, OAK scans your project and offers to install tree-sitter parsers for detected languages.

### `oak ci stop`

Stop the daemon gracefully.

```bash
oak ci stop
```

### `oak ci restart`

Restart the daemon (useful after configuration changes).

```bash
oak ci restart
```

### `oak ci status`

Show daemon status, index statistics, and provider information.

```bash
oak ci status
```

Example output:
```
Codebase Intelligence Status
✓ Daemon: Running on port 37801 (PID: 12345)
  Uptime: 45 minutes

Index Statistics:
  Status: ready
  Total chunks: 1,247
  Memory observations: 23
  Last indexed: 2025-01-06T10:30:00
```

### `oak ci index`

Trigger codebase indexing manually.

```bash
oak ci index              # Incremental update
oak ci index --force      # Full rebuild (clears existing data)
```

### `oak ci reset`

Clear all indexed data and restart.

```bash
oak ci reset              # Prompts for confirmation
oak ci reset -f           # Skip confirmation
oak ci reset -k           # Keep daemon running (only clear data)
```

### `oak ci logs`

View daemon logs.

```bash
oak ci logs               # Show last 50 lines
oak ci logs -n 100        # Show last 100 lines
oak ci logs -f            # Follow logs in real-time (Ctrl+C to stop)
```

### `oak ci config`

Configure embedding and logging settings.

```bash
oak ci config --show              # Show current configuration
oak ci config --list-models       # List known embedding models

# Configure provider and model
oak ci config -p ollama -m nomic-embed-text
oak ci config -p openai -u http://localhost:1234/v1  # LMStudio

# Configure logging
oak ci config --debug             # Enable debug logging
oak ci config --log-level DEBUG   # Set specific level (DEBUG, INFO, WARNING, ERROR)
```

Environment variables (override config file):
- `OAK_CI_DEBUG=1` - Enable debug logging
- `OAK_CI_LOG_LEVEL=DEBUG` - Set log level

### `oak ci exclude`

Manage directory and file exclusions from indexing. Use this to prevent specific directories or files from being indexed by the CI daemon.

```bash
oak ci exclude                     # Show all exclude patterns
oak ci exclude --show              # Same as above
oak ci exclude -a aiounifi         # Exclude 'aiounifi' directory
oak ci exclude -a "vendor/**"      # Exclude vendor and all subdirectories
oak ci exclude -a lib -a tmp       # Exclude multiple directories
oak ci exclude -r aiounifi         # Remove from exclusions
oak ci exclude --reset             # Reset to default patterns
```

**Pattern Format (fnmatch/glob style):**

| Pattern | Matches |
|---------|---------|
| `dirname` | Directory named `dirname` anywhere in the tree |
| `dirname/**` | Directory and all its contents |
| `**/*.log` | All `.log` files in any directory |
| `*.min.js` | Minified JS files in root only |
| `**/test_*` | Files starting with `test_` anywhere |

**After changing exclusions**, restart the daemon and rebuild the index:

```bash
oak ci restart && oak ci reset -f
```

**Default exclusions** include: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.oak`, lock files, and minified assets.

### `oak ci languages`

Show supported languages and AST parsing status.

```bash
oak ci languages
```

Example output:
```
Supported Languages

✓ AST-based chunking (semantic):
  python
    .py  .pyi
  javascript
    .js  .jsx  .mjs  .cjs

Line-based chunking (no AST parser installed):
  ruby
  php
```

### `oak ci install-parsers`

Install tree-sitter language parsers.

```bash
oak ci install-parsers            # Auto-detect and install needed parsers
oak ci install-parsers --all      # Install all supported parsers
oak ci install-parsers --dry-run  # Preview what would be installed
```

### `oak ci port`

Show the port assigned to this project.

```bash
oak ci port
```

Each project gets a unique port (37800-47800 range) derived from its path hash, allowing multiple CI daemons to run simultaneously.

### `oak ci dev`

Run the daemon in development mode with hot reload.

```bash
oak ci dev                # Auto-assigned port
oak ci dev -p 8000        # Specific port
```

## Agent Commands

These commands are designed for AI agents to interact with Codebase Intelligence. They output JSON by default for easy parsing.

### `oak ci search`

Search the codebase and memories using semantic similarity.

```bash
oak ci search "authentication middleware"        # Search all
oak ci search "error handling" --type code       # Code only
oak ci search "past decisions" --type memory     # Memories only
oak ci search "database" -n 20                   # Increase limit
oak ci search "api patterns" -f text             # Human-readable output
```

### `oak ci remember`

Store an observation, decision, or learning for future sessions.

```bash
oak ci remember "The auth module requires Redis" -t discovery
oak ci remember "Always call cleanup() first" -t gotcha -c src/db.py
oak ci remember "Chose SQLite for simplicity" -t decision
oak ci remember "Fixed race condition with lock" -t bug_fix
oak ci remember "Traded memory for speed" -t trade_off
```

Memory types:
- `gotcha` - Non-obvious behaviors that could trip someone up
- `bug_fix` - How a bug was resolved
- `decision` - Design choices with rationale
- `discovery` - Learned facts about the codebase
- `trade_off` - Compromises and why they were made

### `oak ci context`

Get relevant context for your current task.

```bash
oak ci context "implementing user logout"
oak ci context "fixing auth bug" -f src/auth.py
oak ci context "adding migration" -f models.py -f db.py -m 4000
```

Returns curated context including:
- Relevant code patterns and similar implementations
- Past decisions and gotchas about this area
- Project guidelines that apply

### `oak ci test`

Run integration tests to verify CI is working correctly.

```bash
oak ci test               # Run all tests
oak ci test -v            # Verbose output
```

### `oak ci mcp`

Run the MCP protocol server for native tool discovery.

```bash
oak ci mcp                              # stdio transport (for agents)
oak ci mcp -t streamable-http -p 8080   # HTTP transport (for web)
```

## Configuration

Configuration is stored in `.oak/config.yaml` under the `codebase_intelligence` key:

```yaml
codebase_intelligence:
  embedding:
    provider: ollama          # ollama, openai, or fastembed
    model: nomic-embed-text   # Embedding model name
    base_url: http://localhost:11434
    dimensions: null          # Auto-detect from model
    api_key: null             # For OpenAI or API key auth
    fallback_enabled: true    # Fall back to FastEmbed if primary fails
    context_tokens: null      # Max input tokens (auto-detect)
    max_chunk_chars: null     # Max chars per chunk (auto-scales with context)
  index_on_startup: true      # Index when daemon starts
  watch_files: true           # Watch for file changes
  log_level: INFO             # DEBUG, INFO, WARNING, ERROR
  exclude_patterns:           # Directories/files to exclude from indexing
    - '**/.git/**'
    - '**/node_modules/**'
    - '**/__pycache__/**'
    - 'aiounifi'              # Example: exclude a specific directory
    - 'vendor/**'             # Example: exclude vendor and subdirs
```

### Exclude Patterns

Control which directories and files are excluded from indexing. User-configured patterns are combined with built-in defaults.

**Via CLI (recommended):**
```bash
oak ci exclude -a aiounifi          # Add exclusion
oak ci exclude -r aiounifi          # Remove exclusion
oak ci exclude --show               # View all patterns
```

**Via config file:** Edit `.oak/ci/config.yaml` directly:
```yaml
exclude_patterns:
  - '**/.git/**'           # Built-in defaults...
  - '**/node_modules/**'
  - '**/__pycache__/**'
  - '**/venv/**'
  - '**/.venv/**'
  - '**/dist/**'
  - '**/build/**'
  - 'aiounifi'             # Your custom exclusions
  - 'third_party/**'
```

**After editing**, restart and rebuild:
```bash
oak ci restart && oak ci reset -f
```

### Logging Configuration

Control log verbosity via config or environment variables:

| Method | Example | Priority |
|--------|---------|----------|
| Environment: `OAK_CI_DEBUG=1` | Quick debug mode | Highest |
| Environment: `OAK_CI_LOG_LEVEL` | `DEBUG`, `INFO`, etc. | High |
| Config file: `log_level` | Persistent setting | Normal |
| Default | `INFO` | Lowest |

**Log file location:** `.oak/ci/daemon.log`

**Debug logging example output:**
```
14:32:15 [DEBUG] server:930 - Post-tool-use: Edit | input=True | output=True (1234 chars)
14:32:15 [DEBUG] server:992 -   Agent: claude
14:32:15 [DEBUG] server:999 -   Tool input:
  {"file_path": "/src/auth.py", "old_string": "...", "new_string": "..."}
14:32:15 [DEBUG] server:807 -   Auto-capture analyzing: tool=Edit, input_keys=['file_path'...]
14:32:15 [DEBUG] server:831 -   Matched fix keywords in Edit: ['fix']
14:32:15 [INFO] server:1023 - Auto-captured observation: Applied fix to /src/auth.py...
```

### Embedding Providers

| Provider | Description | Configuration |
|----------|-------------|---------------|
| **ollama** | Local Ollama instance | `base_url: http://localhost:11434` |
| **openai** | OpenAI API or compatible (LMStudio, vLLM) | `base_url: http://localhost:1234/v1` |
| **fastembed** | Local CPU-based (fallback) | No external service needed |

### Recommended Models

| Model | Provider | Dimensions | Context | Best For |
|-------|----------|------------|---------|----------|
| `nomic-embed-text` | ollama | 768 | 8K | General code |
| `nomic-embed-code` | ollama/lmstudio | 768 | 32K | Large files |
| `text-embedding-3-small` | openai | 1536 | 8K | High quality |
| `BAAI/bge-small-en-v1.5` | fastembed | 384 | 512 | Fast fallback |

### Auto-scaling Chunk Size

When `context_tokens` is set but `max_chunk_chars` is not, the chunk size auto-scales:

```
max_chunk_chars = context_tokens × 1.5
```

For a 32K context model: 32,768 × 1.5 = **49,152 chars** per chunk.

## Web Dashboard

Access the dashboard at `http://localhost:{port}/ui`

### Features

- **Status Cards**: Files indexed, chunks, memories, provider status
- **Semantic Search**: Search code and memories with natural language
- **Memory Management**: Add observations and context manually
- **Configuration**: Test and apply embedding settings
- **Logs**: View daemon activity

### Search Tab

Enter natural language queries to find relevant code:

```
"authentication middleware"
"database connection handling"
"error handling patterns"
```

Results show:
- File path and line numbers
- Relevance score (0-100%)
- Code preview
- Chunk type (function, class, method, module)

### Settings Tab

- **Provider**: Select embedding provider (Ollama, OpenAI-compatible)
- **Base URL**: API endpoint for the provider
- **Model**: Select from detected models
- **Context Length**: Override model's token limit
- **Max Chunk**: Override auto-calculated chunk size
- **Test Connection**: Validate settings before applying
- **Save & Apply**: Persist changes and reload

## API Reference

The daemon exposes a REST API at `http://localhost:{port}/api/`

### Health & Status

```
GET  /api/health         # Basic health check
GET  /api/status         # Detailed status with stats
GET  /api/logs           # Recent log entries
```

### Search

```
GET  /api/search?query=...&limit=20&search_type=all
POST /api/search         # Body: {"query": "...", "limit": 20}
POST /api/fetch          # Fetch full content by chunk IDs
POST /api/remember       # Store an observation
```

**Search Types**: `code`, `memory`, `all`

### Index Management

```
GET  /api/index/status   # Index statistics
POST /api/index/build    # Trigger indexing (body: {"full_rebuild": false})
POST /api/index/rebuild  # Full rebuild shortcut
```

### Configuration

```
GET  /api/config                    # Current configuration
GET  /api/config/models             # Known embedding models
GET  /api/providers/models          # Models from provider
POST /api/config/test               # Test configuration
POST /api/restart                   # Apply configuration changes
```

### Agent Hooks

For AI agent integration via hooks:

```
POST /api/hook/session-start    # Initialize session context
POST /api/hook/post-tool-use    # Auto-capture observations from tool output
POST /api/hook/before-prompt    # Inject relevant context (Cursor)
POST /api/hook/stop             # Finalize session
```

## Agent Integration (Hooks)

Codebase Intelligence integrates with AI agents through **hooks** that automatically capture learnings and provide context. This is the recommended integration method for most use cases.

### How Hooks Work

When you enable CI for a project, hooks are automatically installed that:

1. **Session Start**: Retrieves recent memories and project context
2. **Post Tool Use**: Analyzes tool outputs to auto-capture errors, fixes, and learnings
3. **Session End**: Creates a session summary

### Supported Agents

| Agent | Hook Support | Auto-Capture | Notes |
|-------|--------------|--------------|-------|
| **Claude Code** | Full | ✓ Yes | JSON payload via stdin with `tool_name`, `tool_input`, `tool_response` |
| **Gemini CLI** | Full | ✓ Yes | Same JSON structure as Claude Code |
| **Cursor** | Partial | Limited | Event-based hooks, no tool output access |
| **Codex** | Via Skills | No | Use CLI commands via skills |

### Auto-Capture

The daemon automatically extracts and stores observations from tool outputs:

| Pattern | Memory Type | Example |
|---------|-------------|---------|
| Error keywords | `gotcha` | "Error: connection refused" → stored |
| Fix keywords in Edit/Write | `bug_fix` | Editing with "fix" in input → stored |
| Test results | `discovery`/`gotcha` | "3 passed, 1 failed" → stored |

**Debug auto-capture:**
```bash
# Enable debug logging to see what's being captured
OAK_CI_DEBUG=1 oak ci restart
oak ci logs -f

# Output shows pattern matching decisions:
# Post-tool-use: Edit | input=True | output=True (1234 chars)
#   Matched fix keywords in Edit: ['fix']
#   Extracted 1 observation(s)
# Auto-captured observation: Applied fix to src/auth.py...
```

### Hook Installation

Hooks are installed automatically when you add the CI feature:

```bash
oak feature add codebase-intelligence
```

Hook files are placed in:
- Claude Code: `.claude/settings.json`
- Cursor: `.cursor/hooks.json`
- Gemini CLI: `.gemini/settings.json`

### Hook Auto-Start

Hooks include auto-start logic - if the daemon isn't running when a hook fires, it starts automatically:

```bash
# Hook command pattern:
(curl -sf http://localhost:PORT/api/health || oak ci start --quiet) && curl ...
```

### Manual Hook Testing

Test hooks without an agent:

```bash
# Test session start
curl -X POST http://localhost:$(oak ci port)/api/hook/session-start \
  -H "Content-Type: application/json" \
  -d '{"agent": "test"}'

# Test post-tool-use with auto-capture
curl -X POST http://localhost:$(oak ci port)/api/hook/post-tool-use \
  -H "Content-Type: application/json" \
  -d '{"agent": "test", "tool_name": "Bash", "tool_input": {"command": "pytest"}, "tool_output": "FAILED: 1 error"}'

# Or use the built-in test
oak ci test -v
```

## Hook Lifecycle (Detailed)

This section provides a detailed technical explanation of how hooks work throughout a coding session.

### Lifecycle Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SESSION LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ SESSION      │    │ PROMPT       │    │ POST-TOOL    │   (repeats)  │
│  │ START        │───▶│ SUBMIT       │───▶│ USE          │──────┐       │
│  └──────────────┘    └──────────────┘    └──────────────┘      │       │
│         │                   │                   │               │       │
│         ▼                   ▼                   ▼               │       │
│   Inject session      Inject task-        Auto-capture         │       │
│   summaries +         relevant            observations         │       │
│   recent memories     memories            from tool output     │       │
│                                                                 │       │
│                       ◀─────────────────────────────────────────┘       │
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ SESSION      │◀── User exits / stops / Ctrl+C                        │
│  │ END          │                                                       │
│  └──────────────┘                                                       │
│         │                                                               │
│         ▼                                                               │
│   🤖 LLM CALL: Summarize session                                        │
│   Store observations + session summary                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Session Start Hook

**Endpoint**: `POST /api/oak/ci/session-start`

**When called**: When a new coding session begins (agent startup, resume, clear context)

**What it does**:
1. Creates a session tracking object (stores session_id, agent, start time)
2. Builds injection context based on `source` parameter:
   - `startup` or `clear` → Full context injection
   - `resume` or `compact` → Minimal injection (avoids duplicate context)

**Context injection includes**:

```markdown
**Codebase Intelligence Active**: 1,234 code chunks indexed, 56 memories stored.
Use `oak ci search '<query>'` for semantic code search...

## Recent Session History
**Session 1** (claude-code): Implemented authentication feature, fixed JWT validation bug...
**Session 2** (claude-code): Refactored database layer...

## Recent Project Memories
- ⚠️ **gotcha**: Always check for null before calling cleanup()
- 📐 **decision**: Using SQLite over PostgreSQL for simplicity
- 💡 **discovery**: The auth module requires Redis for sessions
```

**LLM call**: ❌ None - reads from ChromaDB only

**Implementation**: `hooks.py:hook_session_start()` calls `_build_session_context()` which:
- Fetches last 5 session summaries via `list_memories(memory_types=["session_summary"])`
- Searches recent memories via `search_memory(query="important gotchas decisions bugs")`
- Formats and returns as `injected_context` in the response

---

### 2. Prompt Submit Hook

**Endpoint**: `POST /api/oak/ci/prompt-submit`

**When called**: Each time the user submits a prompt to the agent

**What it does**:
1. Takes the user's prompt text
2. **Semantic search** against the memories collection using the prompt as query
3. Returns relevant memories (threshold 0.4 for relevance)

**Example injection**:

```markdown
**Relevant memories for this task:**
- [gotcha] The config file must be in YAML format, not JSON
- [bug_fix] Fixed race condition by adding mutex in auth.py
```

**LLM call**: ❌ None - embedding-based vector search only

**Implementation**: `hooks.py:hook_prompt_submit()` calls `search_memory()` with the user's prompt, returning memories above 0.4 relevance threshold.

---

### 3. Post-Tool-Use Hook

**Endpoint**: `POST /api/oak/ci/post-tool-use`

**When called**: After every tool execution (Bash, Read, Edit, Write, etc.)

**What it does**:

#### A. Track session activity

Records which files were read/modified/created and commands run in the session object.

#### B. Auto-capture observations (rule-based, no LLM)

| Tool | What it captures | Memory Type | Confidence |
|------|-----------------|-------------|------------|
| **Bash** | Command errors (stderr) | `gotcha` | 0.9 |
| **Bash** | Fatal errors (`command not found`, `permission denied`, etc.) | `gotcha` | 0.85 |
| **Bash** | Test failures | `gotcha` | 0.9 |
| **Bash** | Test passes | `discovery` | 0.8 |
| **Read** | File not found errors | `gotcha` | 0.9 |
| **Edit** | Bug fixes (keywords: fix, patch, resolve, bug) | `bug_fix` | 0.8 |
| **Edit** | Config file changes (.yaml, .json, .toml, etc.) | `decision` | 0.7 |
| **Edit** | New functions/classes added | `discovery` | 0.7 |
| **Write** | New source file creation | `discovery` | 0.75 |
| **Write** | New documentation file | `discovery` | 0.7 |
| **Write** | New config file | `decision` | 0.7 |

Only observations with confidence ≥ 0.7 are stored.

#### C. Inject file-specific memories

When you Read/Edit/Write a file, searches for existing memories about that specific file:

```markdown
**Memories about src/auth.py:**
⚠️ GOTCHA: Always call cleanup() before disconnect
[bug_fix] Fixed null pointer exception in line 42
```

**LLM call**: ❌ None - all rule-based pattern matching

**Implementation**: `hooks.py:hook_post_tool_use()` calls `_extract_observations()` which:
- Parses tool output as JSON
- Runs tool-specific extractors (`_extract_bash_error`, `_extract_test_result`, `_extract_edit_observation`, `_extract_write_observation`)
- Each extractor uses pattern matching to identify meaningful events
- Stores observations with `["tool_name", "auto-captured"]` tags

---

### 4. Session End Hook

**Endpoint**: `POST /api/oak/ci/session-end` or `/api/oak/ci/stop`

**When called**: When the coding session ends (user exits, Ctrl+C, explicit stop)

**What it does**:

#### A. Gather session data

Collects from the session tracking object:
- Files created/modified/read
- Commands run
- Duration
- Already-captured observations

#### B. 🤖 **LLM Summarization** (the only LLM call in the lifecycle)

If summarization is enabled in config, calls the local LLM (e.g., `qwen2.5:3b`, `phi4`):

**Input to LLM**:
```
Summarize this coding session:
- Duration: 45 minutes
- Files created: src/new_feature.py, tests/test_feature.py
- Files modified: src/main.py, config.yaml
- Commands run: pytest tests/, git status, npm install

Extract:
1. Key discoveries about the codebase
2. Gotchas or warnings for future sessions
3. Architectural decisions made
4. Brief session summary
```

**Output from LLM** (structured JSON):
```json
{
  "observations": [
    {"type": "discovery", "observation": "The project uses pytest with fixtures in conftest.py"},
    {"type": "gotcha", "observation": "Tests require Redis to be running locally"},
    {"type": "decision", "observation": "Added feature flag for gradual rollout"}
  ],
  "session_summary": "Implemented new authentication feature with JWT tokens..."
}
```

#### C. Store extracted observations

Each LLM-extracted observation is stored in ChromaDB with tags `["llm-summarized", agent]`.

#### D. Store session summary

The session summary itself is stored as a `session_summary` memory type with tags `["session", "llm-summarized", agent]`. This gets injected at the start of future sessions.

**LLM call**: ✅ Yes - one call at session end

**Implementation**: `hooks.py:hook_session_end()` calls `create_summarizer_from_config()` to get a summarizer, then `summarizer.summarize_session()` which makes the LLM call.

---

### Summary: When LLM is Called

| Hook | LLM Called? | Purpose | Performance |
|------|-------------|---------|-------------|
| Session Start | ❌ No | Reads from ChromaDB | ~50-100ms |
| Prompt Submit | ❌ No | Embedding-based vector search | ~100-200ms |
| Post-Tool-Use | ❌ No | Rule-based pattern matching | ~10-50ms |
| Session End | ✅ **Yes** | Summarize session, extract insights | ~2-5 seconds |

The design is **deliberately token-efficient**:
- Most hooks use fast vector search or rule-based extraction
- LLM is only called once per session (at the end)
- Uses small, fast models like `qwen2.5:3b` (~3B params) for quick summarization

---

### Data Flow Diagram

```
Session Start                    During Session                    Session End
     │                                │                                 │
     ▼                                ▼                                 ▼
┌─────────────┐              ┌─────────────────┐              ┌─────────────────┐
│ ChromaDB    │              │ Tool Execution  │              │ Local LLM       │
│ (read)      │              │                 │              │ (qwen2.5:3b)    │
└─────────────┘              └─────────────────┘              └─────────────────┘
     │                                │                                 │
     ▼                                ▼                                 ▼
┌─────────────┐              ┌─────────────────┐              ┌─────────────────┐
│ Format &    │              │ Pattern Match   │              │ Parse JSON      │
│ Inject      │              │ (no LLM)        │              │ Response        │
└─────────────┘              └─────────────────┘              └─────────────────┘
     │                                │                                 │
     ▼                                ▼                                 ▼
┌─────────────┐              ┌─────────────────┐              ┌─────────────────┐
│ Agent sees  │              │ Store in        │              │ Store in        │
│ context     │              │ ChromaDB        │              │ ChromaDB        │
└─────────────┘              └─────────────────┘              └─────────────────┘
```

---

### Memory Types

| Type | Icon | Description | Source |
|------|------|-------------|--------|
| `gotcha` | ⚠️ | Non-obvious behaviors that could trip someone up | Auto-capture, LLM |
| `bug_fix` | 🐛 | How a bug was resolved | Auto-capture, LLM |
| `decision` | 📐 | Design choices with rationale | Auto-capture, LLM, Manual |
| `discovery` | 💡 | Learned facts about the codebase | Auto-capture, LLM, Manual |
| `trade_off` | ⚖️ | Compromises and why they were made | LLM, Manual |
| `session_summary` | 📋 | LLM-generated session summaries | LLM only |

---

### Viewing Memories

**CLI**:
```bash
oak ci memories                         # List all memories
oak ci memories --type gotcha           # Filter by type
oak ci memories -x                      # Exclude session summaries
oak ci sessions                         # List session summaries only
```

**UI**: Navigate to the **Memories** tab in the dashboard to browse, filter, and add memories.

**API**:
```bash
curl "http://localhost:$(oak ci port)/api/memories?limit=20"
curl "http://localhost:$(oak ci port)/api/memories?memory_type=gotcha"
```

## MCP Integration

Codebase Intelligence provides MCP (Model Context Protocol) tools for AI agents. While agents can use CI via CLI commands (works everywhere), MCP provides native tool discovery for tighter integration.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `oak_search` | Semantic search across code and memories |
| `oak_remember` | Store observations and learnings |
| `oak_context` | Get relevant context for current task |

### Prerequisites

Before configuring MCP, ensure:
1. The CI daemon is running: `oak ci start`
2. Note your project's port: `oak ci port`

### Claude Code Setup

Claude Code provides a built-in command to add MCP servers.

**Option 1: CLI Command (Recommended)**

```bash
# Add for current project only
claude mcp add oak-codebase-intelligence oak ci mcp

# Or add globally (available in all projects)
claude mcp add oak-codebase-intelligence oak ci mcp --global
```

**Option 2: Manual Configuration**

If you prefer manual setup, create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"]
    }
  }
}
```

Or add globally to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"]
    }
  }
}
```

**Verification:**

```bash
# List configured MCP servers
claude mcp list

# In Claude Code, check tools are available
/mcp
# Should list oak_search, oak_remember, oak_context
```

**Remove if needed:**

```bash
claude mcp remove oak-codebase-intelligence
```

### Cursor Setup

Cursor supports MCP via workspace settings.

**Step 1:** Open Cursor Settings (`Cmd/Ctrl + ,`)

**Step 2:** Search for "MCP" or navigate to Features > MCP Servers

**Step 3:** Add server configuration:

```json
{
  "mcp.servers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

**Alternative: settings.json**

Add to `.vscode/settings.json` or Cursor's settings:

```json
{
  "mcp.servers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"]
    }
  }
}
```

**Verification:**

In Cursor's chat, the CI tools should appear in the available tools list.

### Gemini CLI Setup

Gemini CLI supports MCP via configuration file.

**Step 1:** Create or edit `~/.gemini/mcp_config.json`:

```json
{
  "servers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"],
      "env": {}
    }
  }
}
```

**Step 2:** Restart Gemini CLI to load the new configuration.

**Verification:**

```bash
gemini mcp list
# Should show oak-codebase-intelligence server
```

### Windsurf / Continue / Other MCP Clients

For other MCP-compatible agents, use the standard stdio configuration:

```json
{
  "mcpServers": {
    "oak-codebase-intelligence": {
      "command": "oak",
      "args": ["ci", "mcp"],
      "transport": "stdio"
    }
  }
}
```

### HTTP Transport (Advanced)

For web-based integrations or debugging, use HTTP transport:

```bash
# Start MCP server with HTTP transport
oak ci mcp --transport streamable-http --port 8080
```

Then connect to: `http://localhost:8080/mcp`

### Troubleshooting MCP

**Tools not appearing:**
```bash
# Verify daemon is running
oak ci status

# Test MCP server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | oak ci mcp
```

**Connection errors:**
```bash
# Check if daemon port is accessible
curl http://localhost:$(oak ci port)/api/health
```

**Permission issues:**
Ensure `oak` is in your PATH and executable:
```bash
which oak
oak --version
```

### CLI vs MCP: When to Use Each

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Quick setup | CLI | Works immediately, no config |
| Skill-based agents | CLI | Skills guide CLI usage |
| Native tool discovery | MCP | Tools appear automatically |
| Multiple projects | CLI | Port-per-project handled automatically |
| IDE integration | MCP | Tighter integration |

Both approaches use the same backend - choose based on your workflow preference.

## AST-aware Chunking

Codebase Intelligence uses tree-sitter parsers to extract semantic code units:

### Supported Languages (with AST)

- Python (`.py`, `.pyi`)
- JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`)
- TypeScript (`.ts`, `.tsx`)
- Go (`.go`)
- Rust (`.rs`)
- C# (`.cs`)
- Java (`.java`)

### Chunk Types

| Type | Description |
|------|-------------|
| `function` | Standalone functions |
| `class` | Class definitions |
| `method` | Methods within classes |
| `module` | File-level chunks (fallback) |
| `type` | Type definitions (Go) |
| `impl` | Implementation blocks (Rust) |
| `struct` | Struct definitions |
| `interface` | Interface definitions |

### Installing Parsers

```bash
# Install specific parsers
pip install tree-sitter-python tree-sitter-javascript

# Or let OAK detect and install
oak ci install-parsers
```

### AST Statistics

After indexing, the daemon logs AST usage:

```
Chunking stats: 45 AST, 3 AST fallback, 12 line-based (total: 60 files)
```

- **AST**: Files parsed with semantic chunking
- **AST fallback**: Parser available but fell back to lines (e.g., parse error)
- **Line-based**: No parser installed for language

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent (Claude, etc.)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                    MCP Tools │ Hooks
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CI Daemon (FastAPI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Search  │  │  Memory  │  │  Index   │  │  Config  │    │
│  │  Router  │  │  Router  │  │  Router  │  │  Router  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └─────────────┴─────────────┴─────────────┘          │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────┐       │
│  │              Embedding Provider Chain            │       │
│  │   Ollama ──► OpenAI-compat ──► FastEmbed        │       │
│  └─────────────────────────────────────────────────┘       │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────┐       │
│  │                Vector Store (ChromaDB)           │       │
│  │        code_chunks │ memory_observations         │       │
│  └─────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                    File System Watcher
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Project Codebase                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│   │  Code    │  │  Chunker │  │  AST     │                 │
│   │  Files   │──│ (split)  │──│ Parser   │                 │
│   └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Project Support

Each project gets its own:

- **Port**: Deterministic port based on project path hash (37800-47800)
- **Data Directory**: `.oak/ci/` contains ChromaDB and logs
- **Configuration**: `.oak/config.yaml` with project-specific settings

Run multiple daemons simultaneously:

```bash
# Terminal 1: Project A
cd ~/projects/project-a && oak ci start
# Daemon started at http://localhost:37823

# Terminal 2: Project B
cd ~/projects/project-b && oak ci start
# Daemon started at http://localhost:41056
```

## Troubleshooting

### Daemon won't start

```bash
# Check if port is in use
oak ci port
lsof -i :37801

# Check logs
oak ci logs

# Reset and restart
oak ci reset -f
```

### Embedding provider not connecting

```bash
# Test configuration
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:1234/v1/models  # LMStudio

# Use the UI to test
oak ci start && open http://localhost:37801/ui
# Go to Settings > Test Connection
```

### Index not updating

```bash
# Check file watcher status
oak ci status

# Force full rebuild
oak ci index --force

# Or reset everything
oak ci reset -f
```

### AST not working for my language

```bash
# Check installed parsers
oak ci languages

# Install missing parsers
oak ci install-parsers

# Restart daemon
oak ci restart
```

### Unwanted directories being indexed

```bash
# Check current exclusions
oak ci exclude --show

# Add exclusion for a directory
oak ci exclude -a unwanted-folder

# Or for a pattern
oak ci exclude -a "third_party/**"

# Rebuild index to apply
oak ci restart && oak ci reset -f
```

**Common exclusion patterns:**
- `aiounifi` - Exclude a specific directory by name
- `vendor/**` - Exclude vendor folder and all contents
- `**/generated/**` - Exclude any `generated` folder anywhere
- `*.generated.ts` - Exclude generated TypeScript files
