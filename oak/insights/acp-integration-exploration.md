# ACP Integration Exploration for Open Agent Kit

*Generated: 2026-02-21 | Scope: Agent Client Protocol (ACP) integration opportunities*

## Executive Summary

The [Agent Client Protocol (ACP)](https://agentclientprotocol.com/) is an open standard that standardizes communication between code editors/IDEs and coding agents — essentially "LSP for AI agents." Oak already uses the Claude Agent SDK for its CI agent executor, and Zed has [open-sourced an ACP adapter](https://github.com/zed-industries/claude-agent-acp) that wraps the Claude Agent SDK for ACP clients. This creates a natural integration path.

This document explores two angles:
1. **Angle 1 — IDE-to-Oak via ACP**: Let developers interact with Oak's agent system directly from editors like Zed, Neovim, and JetBrains IDEs
2. **Angle 2 — Broader platform leverage**: How Oak can use ACP for agent orchestration, multi-agent composition, and expanded reach

### Key Takeaway

Oak is uniquely positioned here. It already manages agent manifests, governance, CI tools, and MCP servers for 7+ agents — it's an *agent platform*, not just an agent. ACP gives Oak a standardized wire protocol to expose that platform directly into developer workflows, rather than only operating through file-based commands and CLI invocations.

---

## Part 1: ACP Protocol Overview

### What ACP Is

ACP is a JSON-RPC 2.0 protocol for bidirectional communication between editors ("clients") and coding agents ("agents"). Transport is stdio for local agents and HTTP/WebSocket for remote agents (remote support is evolving).

**Core lifecycle:**
```
session/initialize  →  Capability negotiation (protocol version, features)
session/new         →  Create a session with unique ID
session/prompt      →  Send user prompt, agent processes it
session/update      →  Agent streams responses (text, diffs, tool calls)
session/cancel      →  Cancel in-flight processing
```

**Key design properties:**
- Bidirectional: both agent and client can initiate requests
- Streaming: agents send partial outputs via notifications for real-time UX
- Content defaults to Markdown
- Reuses MCP JSON representations where possible, adds coding-specific types (diffs, file edits)
- Extension methods supported for custom functionality

### Relationship to MCP

MCP and ACP are complementary:
- **MCP** = the *what* (what data and tools can agents access)
- **ACP** = the *where* (where the agent lives in your workflow)

Oak already uses MCP heavily (CI tools exposed via MCP server). ACP would add the "where" layer.

### Current Ecosystem (as of Feb 2026)

**Editors with ACP support:** Zed, Neovim (CodeCompanion, avante.nvim), JetBrains IDEs (coming), Marimo, Obsidian

**Agents with ACP support:** Claude Code, Gemini CLI, Codex CLI, Goose, Kiro, StackPack, and 30+ others

**SDKs:** Python, TypeScript, Rust, Kotlin

---

## Part 2: Oak's Current Architecture (ACP-Relevant Parts)

### Agent System
- 7 agent manifests in `src/open_agent_kit/agents/` (Claude, Gemini, Cursor, Codex, Copilot, Windsurf, OpenCode)
- `AgentService` handles manifest loading, command installation, capability detection
- Each manifest declares capabilities, MCP config, hooks, governance settings

### CI Agent Executor
- `AgentExecutor` in `features/codebase_intelligence/agents/executor.py`
- Uses `claude-agent-sdk` to run agent tasks
- Template/task pattern: templates define capabilities, tasks define what to do
- Exposes CI tools (search, remember, context, sessions, etc.) via MCP

### API Surface
- FastAPI daemon with 20+ route modules in `features/codebase_intelligence/daemon/routes/`
- Agent routes: list templates/tasks, run tasks, get status, cancel
- MCP server exposed via `mcp_server.py`

### Key Dependency
- `claude-agent-sdk >= 0.1.26` already in `pyproject.toml`
- Zed's [`claude-agent-acp`](https://github.com/zed-industries/claude-agent-acp) adapter wraps this same SDK

---

## Part 3: Angle 1 — IDE-to-Oak via ACP

### The Vision

Today, developers interact with Oak through:
1. CLI commands (`oak init`, `oak rules`, `oak ci`, etc.)
2. Agent-specific file-based commands (`.claude/commands/`, `.cursor/commands/`)
3. MCP tools (agents call `oak_search`, `oak_remember`, etc.)
4. CI daemon REST API

With ACP, Oak could expose an **ACP agent** that lets any ACP-compatible editor (Zed, Neovim, JetBrains) interact with Oak's full capability surface directly — search CI data, run agent tasks, manage rules, create RFCs — all without leaving the editor.

### Integration Approach Options

#### Option A: Oak as an ACP Agent (Primary Recommendation)

Build an ACP agent that wraps Oak's CI daemon and agent system. This would be a Python process that speaks ACP over stdio and proxies to Oak's services.

```
┌──────────────┐     ACP (stdio)     ┌──────────────────┐     HTTP     ┌────────────────┐
│  Zed/Neovim  │ ◄──────────────────► │  oak-acp-agent   │ ◄──────────► │  CI Daemon     │
│  (ACP Client)│                      │  (Python process) │             │  (FastAPI)     │
└──────────────┘                      └──────────────────┘             └────────────────┘
                                            │
                                            ▼
                                      ┌──────────────┐
                                      │ AgentService  │
                                      │ FeatureService│
                                      │ SkillService  │
                                      └──────────────┘
```

**What the ACP agent would expose:**
- **CI search and memory**: Natural language queries against codebase intelligence
- **Agent task execution**: Run documentation, analysis, or custom agent tasks
- **Rules management**: View/add project rules, validate constitution
- **RFC operations**: Create, review, list RFCs
- **Session history**: Browse past agent sessions and their outcomes
- **Project status**: Health checks, activity summaries, feature status

**Why this approach:**
- Uses the ACP Python SDK directly (Pydantic models, async, good fit with Oak's stack)
- Oak's FastAPI daemon already provides the backend; the ACP agent is a thin adapter layer
- Follows the same pattern as Zed's `claude-agent-acp` (adapter wrapping existing SDK)
- Registers as a new agent type in Oak's manifest system

**Implementation sketch:**
```python
from acp import Agent, AgentSideConnection, stdio_streams
from acp import (InitializeRequest, InitializeResponse,
                 NewSessionRequest, NewSessionResponse,
                 PromptRequest, PromptResponse)
from acp import session_notification, update_agent_message, text_block

class OakACPAgent(Agent):
    """ACP agent that exposes Oak's capabilities to any ACP editor."""

    def __init__(self, conn: AgentSideConnection):
        self._conn = conn
        self._daemon_client = OakDaemonClient()  # HTTP client to CI daemon

    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(protocolVersion=params.protocolVersion)

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        return NewSessionResponse(sessionId=str(uuid4()))

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        # Route prompt to appropriate Oak service
        # e.g., "search for authentication code" → oak_search
        # e.g., "run the documentation agent" → agent task execution
        # e.g., "show me recent sessions" → session history
        result = await self._route_and_execute(params)

        chunk = update_agent_message(text_block(result))
        notification = session_notification(params.sessionId, chunk)
        await self._conn.sessionUpdate(notification)

        return PromptResponse(stopReason="end_turn")
```

**Registration in Oak:**
```yaml
# New manifest entry or oak command
# oak acp serve  →  starts the ACP agent on stdio
# Editors configure: { "agent": "oak", "command": "oak acp serve" }
```

#### Option B: ACP Proxy to Claude Agent SDK

Instead of building a separate Oak ACP agent, extend Oak's existing `AgentExecutor` to support ACP as an alternative transport. When an ACP client sends a prompt, Oak routes it through its existing Claude Agent SDK execution pipeline, enriching it with CI tools, governance, and project context.

```
┌──────────────┐     ACP (stdio)     ┌──────────────────┐
│  Zed/Neovim  │ ◄──────────────────► │  Oak ACP Proxy   │
│  (ACP Client)│                      │                  │
└──────────────┘                      └────────┬─────────┘
                                               │
                                    ┌──────────▼─────────┐
                                    │  AgentExecutor     │
                                    │  (claude-agent-sdk) │
                                    │  + CI MCP tools     │
                                    │  + Oak governance   │
                                    │  + Constitution     │
                                    └────────────────────┘
```

**What this means:**
- The user opens Zed, picks "Oak Agent" from the ACP agent list
- Types a prompt like "refactor the authentication module"
- Oak receives it via ACP, enriches with project constitution + CI context, runs it through Claude Agent SDK
- Streams the response (including diffs, tool calls) back via ACP
- All governed by Oak's rules — the agent gets the constitution, allowed tools, and CI tools automatically

**Why this is powerful:**
- Developers get Oak's *governed, context-enriched* Claude experience inside their editor
- Oak controls what the agent can do (permissions, allowed tools, forbidden tools)
- CI tools provide project memory — the agent "knows" the codebase through Oak's index
- This is different from plain Claude Code in Zed: Oak adds the governance layer + codebase intelligence

**Trade-offs vs. Option A:**
- More complex: needs to map ACP's file operations and tool permissions to Oak's governance model
- More powerful: full agentic coding with Oak's guardrails, not just Q&A/search
- The `claude-agent-acp` adapter from Zed is a reference implementation for this pattern

#### Option C: Hybrid (Recommended Long-Term)

Start with Option A (Oak as a lightweight ACP agent for CI, search, rules, and task management), then evolve toward Option B (full agentic coding through Oak's governance layer). This mirrors how Oak already has both:
- Thin CLI commands for quick operations
- Full agent executor for complex tasks

---

## Part 4: Angle 2 — Broader Platform Leverage

### Idea 1: Oak as an ACP Agent Registry

Oak already manages 7 agent manifests. Extend this to include ACP metadata so Oak becomes a **local agent registry** that helps editors discover which ACP agents are available in a project.

```yaml
# In agent manifest (e.g., agents/claude/manifest.yaml)
acp:
  enabled: true
  command: "claude-agent-acp"  # or the binary path
  display_name: "Claude Code (via Oak)"
  capabilities:
    - code_editing
    - file_operations
    - terminal
    - mcp_servers
```

`oak acp list` would enumerate all ACP-capable agents, and `oak acp configure <editor>` could auto-configure an editor's ACP settings file.

**Value:** Developers run `oak init` and their editor immediately discovers all available agents — no manual ACP config.

### Idea 2: ACP-Based Agent Composition

ACP supports the concept of multiple agents serving different purposes in the same editor. Oak could orchestrate specialized agents:

```
Editor (Zed)
  ├── Oak CI Agent (ACP)        → Search, memory, project context
  ├── Claude Code (ACP)         → Full agentic coding
  ├── Documentation Agent (ACP) → Oak's doc agent task via ACP
  └── Review Agent (ACP)        → Code review with governance rules
```

Each of these would be an ACP agent managed by Oak, running as separate processes. The editor presents them as available agents the user can switch between.

**Implementation:** Oak's `AgentRegistry` already has templates (documentation, analysis, product-manager). Each template could optionally run as a standalone ACP agent:

```bash
oak acp serve --template documentation  # Starts doc-focused ACP agent
oak acp serve --template analysis       # Starts analysis-focused ACP agent
oak acp serve                           # Starts the general Oak ACP agent
```

### Idea 3: ACP for Non-IDE Clients

ACP is not limited to IDEs. There are emerging ACP clients for:
- **Obsidian** — note-taking with AI agents
- **Marimo** — Python notebooks
- **Web browsers** — via `@mcpc/acp-ai-provider`
- **Custom applications** — any app that speaks JSON-RPC

Oak could become an ACP backend for any of these. A team lead reviewing project health in Obsidian could query Oak's CI data through ACP. A data scientist in Marimo could invoke Oak agents for code understanding.

### Idea 4: Remote ACP for Cloud/Team Workflows

ACP's remote transport (HTTP/WebSocket, still evolving) opens a path for **shared Oak instances**:

```
┌────────────────┐     ACP (HTTP)     ┌──────────────────┐
│ Developer IDE  │ ◄────────────────► │  Oak Cloud       │
│ (any editor)   │                    │  (shared daemon)  │
└────────────────┘                    │  + shared CI DB   │
                                      │  + team rules     │
┌────────────────┐     ACP (HTTP)     │  + agent registry │
│ Another Dev    │ ◄────────────────► │                  │
│ (any editor)   │                    └──────────────────┘
└────────────────┘
```

This aligns with Oak's existing `cloud-relay` infrastructure. The CI daemon already runs as an HTTP server — adding ACP's remote transport would be a natural extension.

**Value:** Teams share one governed agent environment. Rules, memory, and context are consistent across all team members regardless of their editor choice.

### Idea 5: ACP as a Feature Module

Following Oak's vertical-slice architecture, ACP support could be a new feature:

```
features/
├── acp_integration/
│   ├── manifest.yaml          # Feature metadata, dependencies
│   ├── service.py             # ACP agent logic
│   ├── agent.py               # ACP Agent subclass
│   ├── router.py              # Routes for ACP config management
│   ├── commands/
│   │   ├── acp_serve.py       # oak acp serve
│   │   ├── acp_list.py        # oak acp list
│   │   └── acp_configure.py   # oak acp configure <editor>
│   ├── templates/
│   │   └── acp-config.json    # Editor config templates
│   └── skills/
│       └── acp-setup.md       # Teach agents about ACP
```

This feature would:
- Depend on `codebase-intelligence` (for CI tools and daemon)
- Add `acp` Python SDK as a dependency
- Register CLI commands under `oak acp`
- Optionally auto-start the ACP agent via hooks

---

## Part 5: Architecture Alignment

### Why ACP Fits Oak's Design

| Oak Principle | ACP Alignment |
|---|---|
| Agent-agnostic | ACP is protocol-level — works with any agent |
| Manifest-driven | ACP metadata fits naturally in agent manifests |
| Feature vertical slices | ACP can be a self-contained feature module |
| MCP-first tool exposure | ACP complements MCP; Oak already has the tool layer |
| Governance & rules | ACP agent wraps Oak's governance layer |
| Local-first | ACP stdio transport is process-local |
| CLI + daemon hybrid | ACP agent runs alongside existing daemon |

### What Oak Already Has That ACP Needs

1. **Agent lifecycle management** — `AgentExecutor` handles runs, cancellation, timeouts
2. **Tool registration** — CI MCP tools already packaged as `McpSdkServerConfig`
3. **Governance rules** — Constitution, auto-approval settings, forbidden tools
4. **Streaming infrastructure** — Activity processor handles real-time events
5. **FastAPI backend** — Ready to serve as the "brain" behind an ACP facade

### What Would Need to Be Built

1. **ACP agent process** — Python process speaking ACP over stdio
2. **Prompt routing** — Map natural language prompts to Oak operations
3. **Response formatting** — Convert Oak results to ACP content blocks (Markdown, diffs)
4. **Editor configuration** — Templates for Zed, Neovim, JetBrains ACP settings
5. **Agent manifest extensions** — ACP metadata in manifest.yaml files

---

## Part 6: Prioritized Recommendations

### Phase 1: Oak as ACP Agent (High Value, Moderate Effort)

Build a lightweight ACP agent that exposes Oak's CI and management capabilities. This gives immediate value — developers can search code, query memories, run agent tasks, and manage rules from any ACP editor.

**Dependencies:** `acp` Python SDK, existing CI daemon
**Scope:** New feature module, 3-4 CLI commands, ACP agent class

### Phase 2: ACP Agent Registry (Medium Value, Low Effort)

Add ACP metadata to agent manifests and provide `oak acp configure` to auto-setup editors. Low effort because it's purely declarative — no new runtime code, just manifest extensions and config templates.

**Dependencies:** Phase 1 for the config templates
**Scope:** Manifest schema extension, config generation command

### Phase 3: Governed ACP Proxy (High Value, High Effort)

Route full agentic coding sessions through Oak's governance layer via ACP. This is the "Claude Code in your editor, but with Oak's rules and memory" experience.

**Dependencies:** Phase 1, deeper integration with `claude-agent-sdk` ACP patterns
**Scope:** ACP↔Claude SDK bridge, permission mapping, streaming translation

### Phase 4: Remote ACP + Team Workflows (Medium Value, High Effort)

Enable remote ACP transport for shared team Oak instances. Depends on ACP remote spec maturity.

**Dependencies:** Phase 1-3, ACP remote spec stabilization
**Scope:** HTTP/WebSocket transport, auth layer, multi-tenant CI

---

## Appendix: Key Resources

- [ACP Official Site](https://agentclientprotocol.com/)
- [ACP GitHub (spec + SDKs)](https://github.com/agentclientprotocol/agent-client-protocol)
- [ACP Python SDK](https://deepwiki.com/agentclientprotocol/python-sdk/4.1-agent-client-protocol-overview)
- [Zed's claude-agent-acp adapter](https://github.com/zed-industries/claude-agent-acp)
- [Zed ACP blog post](https://zed.dev/blog/claude-code-via-acp)
- [Goose ACP intro](https://block.github.io/goose/blog/2025/10/24/intro-to-agent-client-protocol-acp/)
- [JetBrains ACP docs](https://www.jetbrains.com/help/ai-assistant/acp.html)
- [ACP AI Provider (web)](https://ai-sdk.dev/providers/community-providers/acp)
