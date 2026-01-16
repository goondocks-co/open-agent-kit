# RFC-001: OAK Codebase Intelligence

**Status:** Draft
**Author:** @sirkirby / Claude
**Created:** 2026-01-05
**Last Updated:** 2026-01-05

---

## Summary

OAK Codebase Intelligence extends Open Agent Kit with semantic understanding of codebases, persistent memory across sessions, and self-optimizing retrieval. This RFC presents the validated technical design integrating research findings with the original product vision.

## Motivation

### The Context Tax
Every AI coding session starts from zero. Developers spend 5-15 minutes per session re-establishing context. Across a 10-person team with 5 sessions per developer per day, this represents 4-12 hours of lost productivity daily.

### The Knowledge Gap
AI assistants hallucinate patterns, invent APIs, and suggest code that contradicts existing architecture because they lack:
- Architectural decisions and their rationale
- Established patterns and conventions
- Historical context ("we tried X, it didn't work because Y")
- Cross-file relationships and dependencies

### The Multi-Agent Reality
Teams use different AI tools (Claude, Cursor, Gemini) - each operates in isolation with no shared understanding.

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              OAK CI ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        AGENT LAYER                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │ Claude Code │  │   Cursor    │  │ Gemini CLI  │               │   │
│  │  │ hooks.json  │  │ hooks.json  │  │ settings.json│              │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │   │
│  │         └────────────────┼────────────────┘                       │   │
│  │                          │                                        │   │
│  │                          ▼                                        │   │
│  │                 ┌─────────────────┐                               │   │
│  │                 │  oak-ci-hook    │  ← Universal hook script      │   │
│  │                 │  (stdin/stdout) │                               │   │
│  │                 └────────┬────────┘                               │   │
│  └──────────────────────────┼────────────────────────────────────────┘   │
│                             │ HTTP                                       │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    OAK CI DAEMON (FastAPI)                        │   │
│  │                       localhost:37800                             │   │
│  │                                                                   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │   │
│  │  │  Session   │ │   Index    │ │  Retrieval │ │   Memory   │    │   │
│  │  │  Manager   │ │  Scheduler │ │   Engine   │ │   Store    │    │   │
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘    │   │
│  │        └──────────────┴──────────────┴──────────────┘            │   │
│  │                             │                                     │   │
│  └─────────────────────────────┼─────────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────┼─────────────────────────────────────┐   │
│  │                    STORAGE LAYER                                   │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       │   │
│  │  │   ChromaDB     │  │    SQLite      │  │    Ollama      │       │   │
│  │  │ .oak/ci/chroma │  │ .oak/ci/oak.db │  │ localhost:11434│       │   │
│  │  │                │  │                │  │                │       │   │
│  │  │ • Code chunks  │  │ • Sessions     │  │ • Embeddings   │       │   │
│  │  │ • Memory       │  │ • Feedback     │  │ • (Optional)   │       │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘       │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Integration with OAK Feature System

Codebase Intelligence will be implemented as a standard OAK feature, leveraging the existing infrastructure:

```yaml
# features/codebase-intelligence/manifest.yaml
name: codebase-intelligence
display_name: "Codebase Intelligence"
description: "Semantic search and persistent memory for AI assistants"
version: "1.0.0"
default_enabled: false  # Opt-in due to external dependency (Ollama)
dependencies:
  - constitution

commands:
  - ci-search
  - ci-status
  - ci-remember

skills:
  - code-search
  - memory-search

hooks:
  on_feature_enabled: codebase-intelligence:initialize
  on_feature_disabled: codebase-intelligence:cleanup
  on_agents_changed: codebase-intelligence:update_agent_hooks
  on_init_complete: codebase-intelligence:ensure_daemon

config_defaults:
  enabled: true
  daemon:
    port: 37800
    auto_start: true
    log_level: info
  embedding:
    provider: ollama
    model: nomic-embed-text
    fallback_provider: fastembed
  indexing:
    auto_index: true
    stale_threshold_minutes: 30
    ignored_patterns:
      - ".git"
      - ".oak"
      - "node_modules"
      - "__pycache__"
      - ".venv"
  retrieval:
    default_limit: 20
    relevance_threshold: 0.3
  memory:
    auto_capture: true
    retention_days: 90
```

### Component Specifications

#### 1. Daemon (`oak/daemon/`)

**Technology:** FastAPI + Uvicorn (aligns with existing `httpx` dependency)

**Lifecycle Management:**
```python
# Integrated with OAK pipeline system
class DaemonLifecycleStage(BaseStage):
    """Start daemon when CI feature is initialized."""

    name = "daemon_lifecycle"
    applicable_flows = {FlowType.INIT, FlowType.UPDATE}

    def _execute(self, context: PipelineContext) -> StageOutcome:
        if "codebase-intelligence" in context.selections.features:
            daemon_manager.ensure_running()
        return StageOutcome.success("Daemon ready")
```

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/session/start` | POST | Initialize session, return context |
| `/api/session/end` | POST | Finalize session |
| `/api/hook/{event}` | POST | Handle agent hook events |
| `/api/search` | POST | Semantic search |
| `/api/fetch` | POST | Retrieve full content |
| `/api/remember` | POST | Store observation |
| `/api/index/status` | GET | Index statistics |
| `/api/index/build` | POST | Trigger indexing |
| `/ui` | GET | Dashboard (optional) |

#### 2. Embedding Provider (`oak/embeddings/`)

**Provider Interface:**
```python
class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, query: str) -> list[float]: ...
    @property
    def dimensions(self) -> int: ...
```

**Provider Chain:**
```
OllamaProvider (primary)
    └─ FastEmbedProvider (fallback if Ollama unavailable)
        └─ SentenceTransformerProvider (last resort)
```

**Model Selection:**
- Default: `nomic-embed-text` (0.5GB, 8K context, fast)
- High accuracy: `mxbai-embed-large` (1.2GB, better retrieval)
- Code-specific: `nomic-embed-code` (future, when available in Ollama)

#### 3. Code Indexer (`oak/indexing/`)

**AST-Aware Chunking Strategy:**

```python
@dataclass
class CodeChunk:
    id: str                    # Stable hash: filepath:line:content_hash
    content: str               # Actual code
    filepath: str              # Relative path
    language: str              # python, typescript, etc.
    chunk_type: str            # function, class, method, module
    name: str | None           # Function/class name
    start_line: int            # 1-indexed
    end_line: int              # 1-indexed
    parent_id: str | None      # For methods → class relationship
    docstring: str | None      # Extracted docstring
    signature: str | None      # Function/method signature
    token_estimate: int        # ~4 chars/token
```

**Supported Languages (Phase 1):**
- Python (tree-sitter-python)
- TypeScript/JavaScript (tree-sitter-typescript)
- Fallback: Line-based chunking for others

**Indexing Strategy:**
- Full index on first use (not during `oak init`)
- Incremental updates via git-aware change detection
- Background processing to avoid blocking
- Configurable stale threshold (default: 30 minutes)

#### 4. Retrieval Engine (`oak/retrieval/`)

**Progressive Disclosure (3-Layer Pattern):**

```
Layer 1: INDEX      (~50-100 tokens/result)
         ↓
         Agent reviews, selects relevant IDs
         ↓
Layer 2: CONTEXT    (variable tokens)
         ↓
         Agent reviews related chunks
         ↓
Layer 3: FETCH      (~500-1000 tokens/item)
         ↓
         Full content for selected items
```

**Search Response Format:**
```json
{
  "code": [
    {
      "id": "abc123",
      "type": "class",
      "name": "AuthMiddleware",
      "filepath": "src/auth/middleware.py",
      "lines": "15-65",
      "tokens": 450,
      "relevance": 0.89
    }
  ],
  "memory": [
    {
      "id": "mem456",
      "type": "gotcha",
      "summary": "JWT tokens expire silently when Redis down",
      "tokens": 85,
      "relevance": 0.81
    }
  ],
  "total_tokens_available": 535
}
```

#### 5. Memory System (`oak/memory/`)

**Memory Types:**

| Type | Trigger | Example |
|------|---------|---------|
| `gotcha` | Error→fix pattern | "Don't use async in payment callback" |
| `bug_fix` | Debug session completion | "TypeError caused by null user.email" |
| `decision` | Architecture discussion | "Using Redis for session storage" |
| `discovery` | Learning statement | "API returns paginated by default" |
| `trade_off` | Compromise discussion | "Chose speed over memory efficiency" |

**Observation Extraction:**
- Triggered by PostToolUse hook
- Filters: Only capture Write/Edit with explanations, error→fix sequences
- Classification: Rule-based heuristics (fast) or local LLM (accurate)

#### 6. Agent Hook Integration

**Universal Hook Script (`oak-ci-hook`):**
```bash
#!/bin/bash
# Installed to project root, callable by all agents

EVENT=$1
INPUT=$(cat)  # JSON from stdin

# Ensure daemon is running
oak ci daemon ensure >/dev/null 2>&1

# Call daemon API
curl -s -X POST "http://localhost:37800/api/hook/$EVENT" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"$OAK_CI_AGENT\", \"input\": $INPUT}"
```

**Agent-Specific JSON Templates:**

Claude Code (`.claude/settings.json`):
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "OAK_CI_AGENT=claude ./oak-ci-hook session-start",
        "timeout": 5
      }]
    }],
    "PostToolUse": [{
      "matcher": "Edit|Write|Bash",
      "hooks": [{
        "type": "command",
        "command": "OAK_CI_AGENT=claude ./oak-ci-hook post-tool-use",
        "timeout": 3
      }]
    }],
    "SessionEnd": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "OAK_CI_AGENT=claude ./oak-ci-hook session-end",
        "timeout": 5
      }]
    }]
  }
}
```

### Directory Structure

```
open-agent-kit/
├── src/open_agent_kit/
│   ├── features/                      # Feature implementations
│   │   └── codebase_intelligence/
│   │       ├── __init__.py
│   │       ├── daemon/
│   │       │   ├── __init__.py
│   │       │   ├── server.py          # FastAPI application
│   │       │   ├── session.py         # Session management
│   │       │   └── hooks.py           # Hook handlers
│   │       ├── embeddings/
│   │       │   ├── __init__.py
│   │       │   ├── base.py            # Provider interface
│   │       │   ├── ollama.py          # Ollama provider
│   │       │   └── fastembed.py       # Fallback provider
│   │       ├── indexing/
│   │       │   ├── __init__.py
│   │       │   ├── chunker.py         # AST-aware chunking
│   │       │   ├── watcher.py         # Git-aware file watching
│   │       │   └── scheduler.py       # Index orchestration
│   │       ├── retrieval/
│   │       │   ├── __init__.py
│   │       │   └── engine.py          # Progressive disclosure
│   │       ├── memory/
│   │       │   ├── __init__.py
│   │       │   ├── observation.py     # Extraction logic
│   │       │   └── store.py           # ChromaDB wrapper
│   │       └── service.py             # CI feature service
│   │
│   ├── pipeline/stages/
│   │   └── codebase_intelligence.py   # CI-specific pipeline stages
│   │
│   └── commands/
│       └── ci_cmd.py                  # oak ci [command]
│
├── features/
│   └── codebase-intelligence/
│       ├── manifest.yaml
│       ├── commands/
│       │   ├── oak.ci-search.md
│       │   ├── oak.ci-status.md
│       │   └── oak.ci-remember.md
│       ├── skills/
│       │   ├── code-search/
│       │   │   └── SKILL.md
│       │   └── memory-search/
│       │       └── SKILL.md
│       └── hooks/
│           ├── oak-ci-hook            # Universal hook script
│           ├── claude.settings.json.j2
│           ├── cursor.hooks.json.j2
│           └── gemini.settings.json.j2
│
└── tests/
    └── features/
        └── codebase_intelligence/
            ├── test_chunker.py
            ├── test_retrieval.py
            ├── test_daemon.py
            └── fixtures/
```

### Configuration Schema

Addition to `.oak/config.yaml`:
```yaml
# Codebase Intelligence configuration
codebase_intelligence:
  enabled: true

  daemon:
    port: 37800
    auto_start: true
    log_level: info

  embedding:
    provider: ollama        # ollama, fastembed, sentence-transformers
    model: nomic-embed-text
    ollama_url: http://localhost:11434
    dimensions: 768

  indexing:
    auto_index: true
    stale_threshold_minutes: 30
    ignored_patterns:
      - ".git"
      - ".oak"
      - "node_modules"
      - "__pycache__"
      - ".venv"
      - "*.pyc"
      - "*.min.js"

  retrieval:
    default_limit: 20
    max_context_tokens: 2000
    relevance_threshold: 0.3

  memory:
    auto_capture: true
    observation_types:
      - gotcha
      - bug_fix
      - decision
      - discovery
    retention_days: 90
```

### Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies
]

[project.optional-dependencies]
# ... existing optional deps

codebase-intelligence = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "chromadb>=0.5.0",
    "tree-sitter>=0.21.0",
    "tree-sitter-python>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "fastembed>=0.3.0",
]
```

## Implementation Plan

### Phase 1A: Core Infrastructure (Foundation)

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Feature manifest and structure | `features/codebase-intelligence/` |
| 1.2 | Daemon skeleton with FastAPI | `features/ci/daemon/server.py` |
| 1.3 | Embedding provider interface | `features/ci/embeddings/` |
| 1.4 | ChromaDB integration | `features/ci/memory/store.py` |
| 1.5 | Basic chunker (line-based first) | `features/ci/indexing/chunker.py` |
| 1.6 | Search API endpoints | `features/ci/daemon/server.py` |
| 1.7 | CLI commands (`oak ci`) | `commands/ci_cmd.py` |
| 1.8 | Unit tests | `tests/features/codebase_intelligence/` |

**Success Criteria:**
- `oak feature add codebase-intelligence` installs feature
- `oak ci status` shows daemon/index status
- `oak ci search "query"` returns results
- Tests pass with >80% coverage

### Phase 1B: Hook Integration (Proactive)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Universal hook script | `features/ci/hooks/oak-ci-hook` |
| 2.2 | Agent JSON templates (Jinja2) | `features/ci/hooks/*.j2` |
| 2.3 | Hook installer in feature service | `features/ci/service.py` |
| 2.4 | Session management | `features/ci/daemon/session.py` |
| 2.5 | Context generation | `features/ci/daemon/hooks.py` |
| 2.6 | Integration tests | `tests/integration/` |

**Success Criteria:**
- Hooks installed for configured agents
- SessionStart injects constitution + recent context
- PostToolUse logs events

### Phase 1C: Memory & AST (Polish)

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | AST chunker (Python) | `features/ci/indexing/chunker.py` |
| 3.2 | AST chunker (TypeScript/JS) | `features/ci/indexing/chunker.py` |
| 3.3 | Observation extraction | `features/ci/memory/observation.py` |
| 3.4 | MCP tools (`oak_search`, etc.) | `features/ci/daemon/mcp.py` |
| 3.5 | Agent command templates | `features/ci/commands/` |
| 3.6 | Documentation | `docs/features/codebase-intelligence.md` |

**Success Criteria:**
- Python/JS files chunked semantically
- Observations captured from tool outputs
- MCP tools work in Claude/Cursor

### Phase 2: Self-Optimization (GEPA Integration)

**Key Insight:** GEPA's Generic RAG Adapter already provides ChromaDB + Ollama support out-of-box. We leverage this rather than building custom infrastructure.

#### What GEPA RAG Adapter Provides

| Capability | GEPA | OAK Needs | Fit |
|------------|------|-----------|-----|
| ChromaDB support | Native | Using ChromaDB | Perfect |
| Ollama embeddings | `nomic-embed-text` | Same default | Perfect |
| Prompt optimization | Generation prompts | Query rewriting | Good fit |
| Retrieval metrics | Built-in | Need this | Perfect |
| Training/validation | Configurable | From feedback | Perfect |

#### OAK-Specific Extensions Needed

| Requirement | GEPA Default | Our Customization |
|-------------|--------------|-------------------|
| Code-specific retrieval | Generic RAG | Add `file_match`, `function_match` metrics |
| Multi-collection search | Single collection | Search `oak_code` and `oak_memory` |
| Progressive disclosure | Standard RAG | Optimize Layer 1→2→3 thresholds |
| Feedback sources | Manual examples | Implicit signals from tool logs |

#### Phase 2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 2: GEPA INTEGRATION                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              gepa.examples.rag_adapter                      │     │
│  │                                                              │     │
│  │  • ChromaDB integration (use directly)                      │     │
│  │  • Ollama embedding support (same as our default)           │     │
│  │  • Evolutionary prompt optimization                         │     │
│  │  • Training/validation framework                            │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│                              │ Configure                             │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              OAK GEPA Configuration                         │     │
│  │                                                              │     │
│  │  • Point to OAK's ChromaDB collections                      │     │
│  │  • Configure code-specific evaluation metrics               │     │
│  │  • Set up feedback → training task pipeline                │     │
│  │  • Define optimization targets                              │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│                              │ Extend                                │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              OAK-Specific Extensions                        │     │
│  │                                                              │     │
│  │  oak/optimization/metrics.py                                │     │
│  │  • CodeRetrievalMetric (file_match, function_match)        │     │
│  │  • MemoryRelevanceMetric                                    │     │
│  │  • TokenEfficiencyMetric                                    │     │
│  │                                                              │     │
│  │  oak/optimization/training.py                               │     │
│  │  • Convert tool logs → training examples                   │     │
│  │  • Extract implicit signals (search→fetch patterns)        │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Implementation Tasks

| Task | Description | Approach |
|------|-------------|----------|
| 4.1 | Feedback infrastructure | Collect search→fetch patterns from tool logs |
| 4.2 | Training data generator | Convert feedback to GEPA training format |
| 4.3 | GEPA configuration | Point to `.oak/ci/chroma/`, configure collections |
| 4.4 | Code-specific metrics | Extend GEPA scoring for `file_match`, `function_match` |
| 4.5 | CLI wrapper | `oak ci optimize run` calls GEPA with OAK config |
| 4.6 | Scheduling | Background daemon task for periodic optimization |

#### Example: Using GEPA RAG Adapter

```python
# oak/optimization/runner.py
from gepa.examples.rag_adapter.generic_rag_adapter import GenericRAGAdapter
from gepa import optimize

class OAKOptimizer:
    def run(self, max_iterations: int = 10) -> dict:
        # Prepare training data from feedback logs
        train_data, val_data = self.prepare_training_data()

        # Configure GEPA with OAK's ChromaDB
        adapter = GenericRAGAdapter(
            vector_store="chromadb",
            chroma_persist_directory=str(self.chroma_path),
            collection_name="oak_code",
            embedding_model="ollama/nomic-embed-text:latest",
        )

        # Run optimization
        result = optimize(
            adapter=adapter,
            trainset=train_data,
            valset=val_data,
            max_iterations=max_iterations,
            model="ollama/qwen2.5-coder:7b",  # Local code model
        )

        # Apply if improved
        if result.best_score > result.initial_score:
            self._apply_optimized_config(result.best_candidate)

        return result
```

#### Dependencies for Phase 2

```toml
[project.optional-dependencies]
optimization = [
    "gepa>=0.1.0",
    "litellm>=1.0.0",  # GEPA's LLM abstraction
]
```

**Success Criteria:**
- `oak ci optimize run` executes GEPA optimization
- Retrieval quality improves by >20% after 50 sessions
- Optimized prompts/thresholds auto-deployed

**Effort Reduction:** ~40% of original Phase 2 scope by leveraging existing GEPA infrastructure.

## Drawbacks

1. **External dependency**: Ollama required for optimal experience
2. **Storage overhead**: ChromaDB adds disk usage (~100MB-1GB depending on codebase)
3. **Complexity**: Daemon adds operational complexity
4. **Feature creep risk**: Memory system could grow unbounded

## Alternatives

1. **No daemon (CLI-only)**: Simpler but loses proactive context injection
2. **Cloud embeddings**: Better quality but privacy/cost concerns
3. **File-based storage**: Simpler than ChromaDB but loses semantic search
4. **Single-agent focus**: Simpler but doesn't address multi-agent reality

## Unresolved Questions

1. **Memory cleanup policy**: Auto-expire after N days? User-managed?
2. **Multi-project sharing**: Share daemon across projects or isolated?
3. **Observation confidence**: How to handle uncertain classifications?
4. **Upgrade path**: How to migrate existing users?

## References

- [Research Report](../docs/research/codebase-intelligence-research.md)
- [Claude Code Hooks](https://docs.claude.com/en/docs/claude-code/hooks)
- [Cursor Hooks](https://cursor.com/docs/agent/hooks)
- [Gemini CLI Hooks](https://geminicli.com/docs/hooks/)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [Ollama Embedding Models](https://ollama.com/blog/embedding-models)
- [GEPA Generic RAG Adapter](https://github.com/gepa-ai/gepa/tree/main/examples/rag_adapter) - Phase 2 optimization
