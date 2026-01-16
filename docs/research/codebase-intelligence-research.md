# OAK Codebase Intelligence Research Report

**Date:** 2026-01-05
**Status:** Research Complete
**Author:** Claude (Research Assistant)

---

## Executive Summary

This document captures research findings validating the proposed Codebase Intelligence feature for Open Agent Kit (OAK). The research validates key technical decisions while identifying important optimizations and gaps in the original proposal.

### Key Findings

1. **ADR-003 (Ollama)**: VALIDATED - Excellent choice with recommendations for model selection
2. **ADR-004 (ChromaDB)**: VALIDATED - Suitable with caveats about production deployment
3. **Hook Support**: VALIDATED - All three target agents (Claude, Cursor, Gemini) have comprehensive hook APIs
4. **Architecture Fit**: The existing OAK features system provides an ideal integration pattern

---

## 1. Codebase Analysis

### 1.1 Current OAK Architecture

The open-agent-kit codebase follows a well-structured layered architecture:

```
┌─────────────────────────┐
│   CLI Layer (Typer)     │  ← User interaction (oak/cli.py)
├─────────────────────────┤
│   Command Layer         │  ← src/open_agent_kit/commands/
├─────────────────────────┤
│   Service Layer         │  ← src/open_agent_kit/services/
├─────────────────────────┤
│   Model Layer (Pydantic)│  ← src/open_agent_kit/models/
├─────────────────────────┤
│   Pipeline Layer        │  ← src/open_agent_kit/pipeline/
├─────────────────────────┤
│   Storage Layer         │  ← File system, YAML
└─────────────────────────┘
```

### 1.2 Key Existing Components

| Component | Location | Relevance to Codebase Intelligence |
|-----------|----------|-----------------------------------|
| **Feature System** | `services/feature_service.py` | Perfect pattern for adding CI as a feature |
| **Pipeline Architecture** | `pipeline/` | Extensible for daemon lifecycle |
| **Config Management** | `services/config_service.py` | Ready for CI-specific config |
| **Hook System** | `pipeline/stages/hooks.py` | OAK internal hooks (not agent hooks) |
| **Skill Service** | `services/skill_service.py` | Pattern for MCP tool registration |
| **Template Service** | `services/template_service.py` | Jinja2 rendering for agent-specific commands |

### 1.3 Feature Structure Pattern

Existing features follow this structure:

```
features/<feature-name>/
├── manifest.yaml           # Feature metadata, dependencies, commands
├── commands/               # Agent command templates (Jinja2)
│   └── oak.<command>.md
├── templates/              # Document templates
└── skills/                 # Optional skill definitions
    └── <skill-name>/
        └── SKILL.md
```

**Key manifest fields:**
- `dependencies`: Other features required
- `commands`: List of command names
- `skills`: Skills to auto-install
- `hooks`: Feature lifecycle hooks (OAK internal)
- `config_defaults`: Default configuration values

### 1.4 Current Dependencies

From `pyproject.toml`:
- Python 3.13+
- typer, rich (CLI)
- pydantic, pydantic-settings (models)
- jinja2 (templates)
- httpx (HTTP client - already present!)
- pyyaml (config)

**Missing dependencies for Codebase Intelligence:**
- fastapi, uvicorn (daemon)
- chromadb (vector store)
- tree-sitter + language grammars (AST parsing)
- mcp (MCP server) - may need custom implementation

---

## 2. AI Agent Hook Research

### 2.1 Claude Code Hooks

**Configuration:** `.claude/settings.json` (project) or `~/.claude/settings.json` (user)

**Relevant Lifecycle Events:**

| Event | Use Case for OAK |
|-------|------------------|
| `SessionStart` | Load constitution context, recent files, observations |
| `PostToolUse` | Extract observations from tool outputs |
| `SessionEnd` | Generate session summary, queue GEPA training data |

**Configuration Format:**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [{
          "type": "command",
          "command": "curl -s http://localhost:37800/api/session/start -X POST -d '{\"agent\":\"claude\"}'",
          "timeout": 5
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "oak-ci-hook post-tool",
          "timeout": 3
        }]
      }
    ]
  }
}
```

### 2.2 Cursor Hooks

**Configuration:** `.cursor/hooks.json` (project) or `~/.cursor/hooks.json` (user)

**Relevant Events:**
- `beforeSubmitPrompt` - Inject context
- `afterFileEdit` - Track modifications
- `afterAgentResponse` - Extract observations
- `stop` - Session cleanup

**Format:**
```json
{
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt": [{
      "command": "./oak-ci-hook session-context"
    }]
  }
}
```

### 2.3 Gemini CLI Hooks

**Configuration:** `.gemini/settings.json`

**Relevant Events:**
- `SessionStart`, `SessionEnd`
- `BeforeTool`, `AfterTool`
- `BeforeAgent`, `AfterAgent`

**Format:**
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{
        "name": "oak-ci-context",
        "type": "command",
        "command": "./oak-ci-hook session-start",
        "timeout": 5000
      }]
    }]
  }
}
```

### 2.4 Unified Hook Architecture

All three agents share common patterns:
1. JSON configuration files
2. stdin/stdout JSON communication
3. Exit code 0 = success, 2 = blocking error
4. Tool/event matchers (regex supported)
5. Timeout configuration

**Recommended Hook Script Strategy:**

Rather than three separate implementations, create a single universal script:

```bash
#!/bin/bash
# oak-ci-hook - Universal hook handler

EVENT=$1
AGENT=${OAK_AGENT:-$(basename $(pwd))}  # Detect from context

# Read JSON input from stdin
INPUT=$(cat)

# Call daemon with event and input
curl -s -X POST "http://localhost:37800/api/hook/$EVENT" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"$AGENT\", \"input\": $INPUT}"
```

---

## 3. Embedding Provider Research

### 3.1 Ollama Models Recommendation

| Model | Use Case | MTEB Score | Memory |
|-------|----------|-----------|--------|
| `nomic-embed-text` | **Default** - best speed/memory | 53.01 | 0.5GB |
| `mxbai-embed-large` | Higher accuracy | 64.68 | 1.2GB |
| `nomic-embed-code` | Code-specific (via HF) | Best for code | ~8GB |

**Recommended Default:** `nomic-embed-text`
- 8,192 token context (good for code files)
- 12,450 tokens/sec on RTX 4090
- Surpasses OpenAI ada-002

**Future Option:** `nomic-embed-code`
- State-of-the-art on CodeSearchNet
- Not yet in Ollama, but available on HuggingFace
- Consider adding as optional provider

### 3.2 ChromaDB Validation

**Strengths:**
- Embedded mode perfect for local-first
- 2025 Rust rewrite: 4x faster
- HNSW index with configurable parameters
- Good for up to ~10M vectors

**Production Recommendations:**
1. Use **server mode** (not library mode) when daemon is long-running
2. Configure HNSW for code search:
   ```python
   collection = client.create_collection(
       name="oak_code",
       metadata={
           "hnsw:space": "cosine",
           "hnsw:construction_ef": 200,
           "hnsw:M": 16
       }
   )
   ```

### 3.3 Alternative: FastEmbed as Fallback

If Ollama is unavailable, `fastembed` provides:
- No GPU required
- ONNX runtime (no PyTorch)
- Works in serverless (AWS Lambda)
- Maintained by Qdrant

```python
from fastembed import TextEmbedding
embedding_model = TextEmbedding()
embeddings = list(embedding_model.embed(documents))
```

---

## 4. Gap Analysis & Optimizations

### 4.1 Architecture Gaps

| Gap | Original PRD | Recommendation |
|-----|-------------|----------------|
| **Daemon lifecycle** | Manual start/stop | Integrate with OAK pipeline system |
| **Hook installation** | Separate templates | Unified script + agent-specific JSON |
| **MCP Server** | Separate process | Embed in daemon (same port) |
| **Feature integration** | New code paths | Use existing FeatureService pattern |

### 4.2 Technical Optimizations

1. **Embedding Fallback Chain:**
   ```
   Ollama (primary) → FastEmbed (fallback) → Sentence-Transformers (last resort)
   ```

2. **Progressive Indexing:**
   - Index on first use (not during `oak init`)
   - Background incremental updates
   - Configurable stale threshold

3. **Session Context Caching:**
   - Cache constitution reference
   - Pre-compute recent file summaries
   - Lazy-load observations

4. **Hook Installation Simplification:**
   - Single `oak-ci-hook` binary/script
   - Agent-specific JSON wrappers
   - Auto-detect daemon availability

### 4.3 Feature System Integration

Rather than creating parallel infrastructure, integrate deeply:

```yaml
# features/codebase-intelligence/manifest.yaml
name: codebase-intelligence
display_name: "Codebase Intelligence"
description: "Semantic search and persistent memory for AI assistants"
version: "1.0.0"
default_enabled: false  # Opt-in due to Ollama dependency
dependencies: [constitution]

commands:
  - ci-search
  - ci-remember
  - ci-status

skills:
  - code-search
  - memory-management

hooks:
  on_feature_enabled: codebase-intelligence:start_daemon
  on_feature_disabled: codebase-intelligence:stop_daemon
  on_agents_changed: codebase-intelligence:update_hooks

config_defaults:
  daemon_port: 37800
  auto_start: true
  embedding_model: nomic-embed-text
  stale_threshold_minutes: 30
```

### 4.4 Storage Directory Structure

```
.oak/
├── config.yaml                    # Add codebase-intelligence section
├── ci/                            # New CI-specific storage
│   ├── chroma/                    # ChromaDB persistence
│   ├── daemon.pid                 # Daemon process ID
│   ├── daemon.log                 # Daemon logs
│   └── sessions/                  # Session data (SQLite or JSON)
└── features/
    └── codebase-intelligence/     # Feature-specific templates (if any)
```

### 4.5 Non-Goals Reaffirmed

The following should remain out of scope for Phase 1:
- Real-time collaboration
- Cloud-hosted index
- Code generation/modification
- External knowledge bases
- Non-hook agents as first-class (MCP/CLI as fallbacks only)

---

## 5. Revised Implementation Strategy

### 5.1 Phase 1A: Core Infrastructure (MVP)

**Goal:** Working daemon with basic search, no hooks yet

1. Create feature manifest and directory structure
2. Implement daemon with FastAPI (health check, status)
3. Integrate ChromaDB in server mode
4. Add Ollama embedding provider with fallback
5. Implement basic AST chunker (Python first)
6. Build search API (`/api/search`, `/api/fetch`)
7. Add CLI commands (`oak ci status`, `oak ci search`)

**Dependencies to add:**
```toml
dependencies = [
    # ... existing
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "chromadb>=0.5.0",
    "tree-sitter>=0.21.0",
    "tree-sitter-python>=0.21.0",
]

[project.optional-dependencies]
codebase-intelligence = [
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
]
```

### 5.2 Phase 1B: Hook Integration

**Goal:** Proactive context injection

1. Create universal hook script (`oak-ci-hook`)
2. Generate agent-specific JSON configurations
3. Implement session management APIs
4. Add hook installer to feature pipeline
5. Build context generation (constitution + recent files + observations)

### 5.3 Phase 1C: Memory & Observation

**Goal:** Persistent cross-session memory

1. Implement observation extraction from PostToolUse
2. Add memory collection in ChromaDB
3. Build `oak_remember` MCP tool
4. Create memory browsing UI endpoint

### 5.4 Phase 2: Optimization (GEPA) - REVISED

**Goal:** Self-improving retrieval via GEPA's Generic RAG Adapter

**Key Discovery:** GEPA's Generic RAG Adapter already provides ChromaDB + Ollama support out-of-box. This reduces Phase 2 scope by ~60%.

**What GEPA RAG Adapter provides:**
- ChromaDB vector store integration (use directly)
- Ollama embedding support (`nomic-embed-text`)
- Evolutionary prompt optimization loop
- Training/validation framework

**OAK-specific work needed:**
1. Build feedback → training data converter
2. Configure GEPA to use OAK's ChromaDB collections
3. Add code-specific metrics (`file_match`, `function_match`)
4. Create CLI wrapper (`oak ci optimize run`)
5. Schedule periodic optimization in daemon

---

## 6. Risk Mitigations (Updated)

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Ollama not installed | High | FastEmbed fallback + clear error messaging |
| Large codebase slow | Medium | Background indexing + progress indicator |
| Hook format changes | Medium | Version detection + graceful degradation |
| ChromaDB corruption | Low | Rebuild command + periodic backups |
| Daemon crashes | Low | Auto-restart via feature lifecycle hooks |
| Token context overflow | Medium | Progressive disclosure (validated approach) |

---

## 7. Open Questions (Updated)

1. **Memory TTL**: How long to retain observations? Suggest: configurable, default 90 days
2. **Multi-project**: One daemon per project or shared? Suggest: per-project for isolation
3. **Team sharing**: Future consideration - out of scope for Phase 1
4. **API embeddings**: Should we support OpenAI/Voyage as premium option? Suggest: Phase 2
5. **Privacy controls**: File exclusion patterns? Suggest: respect `.gitignore` + custom `.oakignore`

---

## 8. Success Metrics (Validated)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Setup time | < 5 min | Time from `oak init` to first search |
| Index time (10K files) | < 5 min | Automated benchmark |
| Search latency | < 500ms | API timing |
| Precision@10 | > 80% | User study |
| Token efficiency | 10x reduction | Before/after comparison |
| Context setup time | < 30 sec | User feedback |

---

## 9. Recommended Next Steps

1. **Review this document** with stakeholders
2. **Create RFC** using the validated findings
3. **Set up feature scaffold** (`features/codebase-intelligence/`)
4. **Implement Phase 1A** (core infrastructure)
5. **Iterate based on feedback**

---

## Appendix A: Sources

### Hook Documentation
- Claude Code: https://docs.claude.com/en/docs/claude-code/hooks
- Cursor: https://cursor.com/docs/agent/hooks
- Gemini CLI: https://geminicli.com/docs/hooks/

### Embedding Models
- Ollama nomic-embed-text: https://ollama.com/library/nomic-embed-text
- Nomic Embed Code: https://www.nomic.ai/blog/posts/introducing-state-of-the-art-nomic-embed-code
- FastEmbed: https://github.com/qdrant/fastembed

### Vector Databases
- ChromaDB: https://docs.trychroma.com/
- ChromaDB Performance: https://cookbook.chromadb.dev/running/performance-tips/

### Optimization
- GEPA Generic RAG Adapter: https://github.com/gepa-ai/gepa/tree/main/examples/rag_adapter

### Benchmarks
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
