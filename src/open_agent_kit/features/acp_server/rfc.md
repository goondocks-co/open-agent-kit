# RFC: Agent Client Protocol (ACP) Integration

**Status:** Implemented (Phase 1)
**Author:** OAK Core Team
**Feature Slice:** `src/open_agent_kit/features/acp_server/`

## 1. Summary

This RFC proposes implementing the [Agent Client Protocol (ACP)](https://agentclientprotocol.com/) within the Open Agent Kit (OAK). This integration will transition OAK from a strictly "fire-and-forget" CLI tool into a stateful, interactive agent server capable of real-time streaming to modern AI-native IDEs and editors. Furthermore, it establishes ACP as the internal standard for multi-agent orchestration within OAK.

Phase 1 is implemented using the official `agent-client-protocol` Python SDK, which provides protocol types, transport helpers, and update builders (`text_block`, `update_agent_message`, `start_tool_call`). This eliminates the need for hand-rolled protocol models and ensures compatibility with the evolving ACP specification.

## 2. Motivation

Currently, OAK executes commands, runs CI gates, updates files, and exits. While MCP (Model Context Protocol) allows external agents to use OAK's tools, OAK itself cannot easily stream its internal thought processes, multi-step tool executions, or sub-agent handoffs to a user interface.

By implementing ACP, we achieve two major breakthroughs:
1.  **First-Class Editor Integration:** Editors can connect to OAK (via `stdio` or HTTP) and spawn interactive agent sessions. The user sees the agent's real-time thoughts, tool usage, and file modifications directly in their IDE.
2.  **Standardized Agent Orchestration:** OAK currently contains multiple specialized agents (e.g., engineering, maintenance) built on the Claude SDK. By adopting ACP internally, OAK can act as an ACP client to its own sub-agents, standardizing routing, handoffs, and state management.

## 3. Architecture & Design

Following OAK's `constitution.md` rules, this will be implemented as a Vertical Slice Feature.

### 3.1. Transport Layer
ACP transport is implemented in phases, mirroring the evolution of MCP:
*   **Phase 1 (`stdio`) -- COMPLETE:** The initial implementation supports standard input/output transport via `acp.serve_stdio()`. This is highly reliable for local editor extensions and avoids port conflicts.
*   **Phase 2 (Streamable HTTP / SSE) -- Planned:** Once the core protocol bindings are stable, we will add support for Streamable HTTP (Server-Sent Events) to enable remote execution and broader client compatibility.

### 3.2. CLI Integration (Golden Path)
A new idempotent command exposes the server:
*   `oak acp serve`
*   Flags: `--transport stdio` (default, Phase 1) or `--transport http --port 8080` (Phase 2, planned)

### 3.3. Agent Registry Mapping
OAK's existing `AgentService` (`src/open_agent_kit/services/agent_service.py`) will be mapped to the ACP `list_agents` endpoint.
When an editor queries the OAK ACP server, it will receive the list of available agents (e.g., `gemini`, `engineering`, `maintenance`) and their respective capabilities/manifests.

### 3.4. Memory and State Management
Unlike standard CI runs, ACP sessions are stateful and interactive. To adhere to OAK's local-first and data-evolution rules:
*   **Authoritative State:** Session data, prompt histories, and tool execution logs will be written to OAK CI's existing SQLite database (`.oak/ci/activities.db`).
*   **Semantic Memory:** Long-term context retrieval will interface with OAK CI's ChromaDB instance (`.oak/ci/chroma/`).
*   This ensures that an ACP session can be resumed, audited, or converted into a standard OAK insight report later.

### 3.5. Multi-Agent Orchestration
Inside `src/open_agent_kit/features/codebase_intelligence/agents/`, OAK will utilize ACP to route tasks:
1.  A "Router" agent receives the primary ACP stream from the user.
2.  The Router decides to delegate a task to the `engineering` sub-agent.
3.  The Router acts as an ACP client, spinning up a run on the `engineering` agent and passing the SQLite session ID.
4.  The `engineering` agent's stream is piped back through the Router to the IDE.

### 3.6. Single Agent Model

OAK presents itself as a **single agent** named `oak` to ACP-connected editors. Internally, OAK may orchestrate multiple specialized sub-agents (engineering, maintenance, etc.), but the ACP client always interacts with one unified agent identity. This simplifies the editor integration -- the user sees one agent with consistent capabilities rather than needing to choose between multiple agents.

The `OakAcpAgent` class implements all required ACP Agent protocol methods (`initialize`, `new_session`, `prompt`, `cancel`, etc.) and acts as the single entry point. Future multi-agent routing (Phase 4) will happen behind this facade.

### 3.7. Claude SDK Bridge

The `AcpBridge` module (`bridge.py`) translates between Claude Agent SDK message types and ACP session update payloads. This is a stateless mapping layer:

| Claude SDK Type | ACP Update |
|---|---|
| `TextBlock` in `AssistantMessage` | `update_agent_message(text_block(...))` |
| `ToolUseBlock` in `AssistantMessage` | `start_tool_call(id, name, kind=...)` |
| `ResultMessage` | _(ignored -- internal cost tracking)_ |

Tool calls are classified into ACP `ToolKind` categories (`read`, `edit`, `execute`) based on the Claude SDK tool name, allowing editors to display appropriate UI affordances (e.g., showing a diff view for edit tools, a terminal view for command tools).

## 4. Implementation Plan

1.  **Phase 1: Foundation & `stdio` Transport -- COMPLETE**
    *   Created feature slice `acp_server/` with `constants.py`, `session.py`, `context.py`, `bridge.py`, `agent.py`.
    *   Using official `agent-client-protocol` SDK for protocol types and transport.
    *   Implemented `stdio` server via `acp.serve_stdio()`.
    *   Added `oak acp serve` CLI command.
    *   Claude SDK bridge translates streaming messages to ACP updates.
    *   Unit tests cover session management, context builder, bridge mapping, and agent lifecycle.
2.  **Phase 2: Agent Mapping & Execution -- Planned**
    *   Map `AgentService` to ACP endpoints.
    *   Expose multiple OAK agents via ACP agent registry.
3.  **Phase 3: Stateful Memory Integration -- Planned**
    *   Integrate ACP session initialization with `.oak/ci/activities.db`.
    *   Ensure each ACP "turn" saves context to SQLite.
4.  **Phase 4: Internal Orchestration -- Planned**
    *   Implement the internal ACP client for sub-agent routing behind the single-agent facade.
5.  **Phase 5: Streamable HTTP -- Planned**
    *   Add HTTP/SSE transport layer using FastAPI/Starlette (aligning with OAK daemon patterns).

## 5. Open Questions

### Resolved
*   **Schema Sync:** Resolved by adopting the official `agent-client-protocol` SDK. OAK tracks the upstream package version rather than maintaining custom Pydantic models.
*   **CLI Command:** Confirmed as `oak acp serve` with `--transport` flag.

### Open
*   **HTTP Authentication:** When we move to Streamable HTTP (Phase 5), how should we handle local authentication? (e.g., a generated token stored in `.oak/ci/daemon.port`?).
*   **Sub-Agent Handoffs:** Does ACP natively support a "yield to agent" primitive, or do we need to build a custom tool for OAK's router agent to invoke other agents?
*   **Session Persistence:** Phase 1 uses in-memory session storage. Phase 3 will migrate to SQLite -- should we preserve backward compatibility with in-memory sessions for testing?
