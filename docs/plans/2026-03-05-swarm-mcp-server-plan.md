# Swarm MCP Server + Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated `oak-swarm` MCP server (local + remote), a swarm skill, and conditional installation so agents on swarm-connected projects can access cross-project knowledge.

**Architecture:** Two entry points — local daemon MCP (`oak swarm mcp`, stdio + streamable-http) and remote worker MCP (`/mcp` on Cloudflare Worker, streamable-http with separate agent token). A standalone skill teaches agents when to use swarm vs team tools.

**Tech Stack:** Python (FastMCP, httpx, typer), TypeScript (Cloudflare Workers, Durable Objects), YAML (manifest, mcp config), Markdown (skill)

**Design doc:** `docs/plans/2026-03-05-swarm-mcp-server-design.md`

---

### Task 1: Create Swarm Skill

**Files:**
- Create: `src/open_agent_kit/features/swarm/skills/swarm/SKILL.md`
- Modify: `src/open_agent_kit/features/swarm/manifest.yaml`

**Reference:** `src/open_agent_kit/features/team/skills/oak/SKILL.md` for structure and frontmatter format.

**Step 1: Create the skill file**

Create `src/open_agent_kit/features/swarm/skills/swarm/SKILL.md` with this content:

```markdown
---
name: swarm
description: >-
  Search across multiple projects in your organization's swarm.
  Use when you need cross-project patterns, org-level conventions,
  shared decisions, or want to know how other projects solved a problem.
  Complements the oak (team) skill which covers single-project knowledge.
allowed-tools: Bash, Read
user-invocable: true
---

# Swarm

Use MCP tools (`swarm_search`, `swarm_fetch`, `swarm_nodes`, `swarm_call`,
`swarm_broadcast`, `swarm_status`) to access cross-project knowledge from
the swarm — a federation of team nodes across your organization.

## When to Use Swarm vs Team

| Question | Team (`oak-ci`) | Swarm (`oak-swarm`) |
|----------|-----------------|---------------------|
| How does auth work in *this* project? | `oak_search` | |
| How do we handle auth *across* projects? | | `swarm_search` |
| What patterns exist for error handling? | Local patterns | Org-wide conventions |
| What was decided about the API? | Local decisions | Cross-project decisions |
| What depends on this change? | Local impact | Cross-project impact |

**Rule of thumb:** Team = "this project", Swarm = "the organization".

## Quick Start

### Search then Fetch (primary workflow)

```
# 1. Broad search across all projects
swarm_search(query="retry with exponential backoff", search_type="memory")

# 2. Get full details for a specific result
swarm_fetch(ids=["chunk-id-from-search"], project_slug="project-name")
```

Search returns summaries with IDs. Fetch returns full content for the IDs
you care about. This two-step keeps responses focused.

### Discover connected projects

```
swarm_nodes()
```

### Check connectivity

```
swarm_status()
```

## Tool Reference

| MCP Tool | Purpose | Key Args |
|----------|---------|----------|
| `swarm_search` | Search observations, sessions, plans across all nodes | `query`, `search_type` (all/memory/sessions/plans), `limit` |
| `swarm_fetch` | Get full details for search result IDs | `ids` (list), `project_slug` |
| `swarm_nodes` | List connected teams and capabilities | (none) |
| `swarm_call` | Call a tool on a specific team node | `tool_name`, `arguments`, `target_project` |
| `swarm_broadcast` | Call a tool on all team nodes | `tool_name`, `arguments` |
| `swarm_status` | Check swarm connection status | (none) |

### Search Types

- `all` — everything (default)
- `memory` — observations, decisions, gotchas, discoveries
- `sessions` — session summaries
- `plans` — planning documents and decisions

Note: code search is NOT available via swarm. Use `oak_search` (team) for
code search within the current project.

## Common Patterns

### Find org-wide conventions

```
swarm_search(query="error handling conventions", search_type="memory")
```

### Check how other projects solved a problem

```
swarm_search(query="database migration strategy", search_type="all")
# then fetch details for the most relevant result
swarm_fetch(ids=["<id>"], project_slug="<project>")
```

### Discover cross-project dependencies

```
swarm_search(query="shared authentication service", search_type="memory")
```

### Run a tool on a specific project

```
swarm_call(
    tool_name="oak_search",
    arguments='{"query": "payment processing", "search_type": "code"}',
    target_project="billing-service"
)
```
```

**Step 2: Update swarm manifest to register the skill**

Open `src/open_agent_kit/features/swarm/manifest.yaml`. Add `skills:` key:

```yaml
name: swarm
display_name: "Swarm"
description: "Cross-project orchestration via Cloudflare Durable Objects"
version: "1.0.0"
default_enabled: false
dependencies:
  - team
  - agent-runtime
skills:
  - swarm
```

**Step 3: Verify skill loads**

Run: `find src/open_agent_kit/features/swarm/skills -name "SKILL.md" -type f`
Expected: `src/open_agent_kit/features/swarm/skills/swarm/SKILL.md`

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/skills/ src/open_agent_kit/features/swarm/manifest.yaml
git commit -m "feat(swarm): Add standalone swarm skill for cross-project knowledge"
```

---

### Task 2: Add `swarm_fetch` Tool to MCP Server

**Files:**
- Modify: `src/open_agent_kit/features/swarm/daemon/mcp_server.py`
- Modify: `src/open_agent_kit/features/swarm/constants.py`

**Reference:** The fetch route already exists at `src/open_agent_kit/features/swarm/daemon/routes/fetch.py` — it broadcasts `oak_fetch` to all nodes. The MCP tool wraps this endpoint.

**Step 1: Add the `swarm_fetch` tool name constant**

Open `src/open_agent_kit/features/swarm/constants.py`. Find the tool name constants section (near `SWARM_TOOL_SEARCH`, around line 180). Add:

```python
SWARM_TOOL_FETCH = "swarm_fetch"
```

Also find `SWARM_DAEMON_API_PATH_FETCH` — it should already exist as `"/api/swarm/fetch"`. Confirm it's there.

**Step 2: Add the fetch tool to mcp_server.py**

Open `src/open_agent_kit/features/swarm/daemon/mcp_server.py`. Add the import for `SWARM_DAEMON_API_PATH_FETCH` and `SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS` to the constants import block (line 26-37):

```python
from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_BROADCAST,
    SWARM_DAEMON_API_PATH_FETCH,
    SWARM_DAEMON_API_PATH_NODES,
    SWARM_DAEMON_API_PATH_SEARCH,
    SWARM_DAEMON_API_PATH_STATUS,
    SWARM_DAEMON_API_PATH_TOOL_CALL,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_DEFAULT_PORT,
    SWARM_DAEMON_PORT_FILE,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
    SWARM_RESPONSE_KEY_ERROR,
)
```

Then add the `swarm_fetch` tool after the `swarm_status` tool (after line 308):

```python
    @mcp.tool()
    def swarm_fetch(
        ids: list[str],
        project_slug: str = "",
    ) -> str:
        """Fetch full details for items found via swarm_search.

        Use this after swarm_search to get the complete content of specific
        results. Pass the chunk IDs and project slug from search results.

        Args:
            ids: List of chunk IDs from swarm_search results.
            project_slug: Project slug from the search result (used for routing).

        Returns:
            JSON string with full content for the requested items.
        """
        if not ids:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: "ids list is required"})

        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_FETCH,
                data={
                    "ids": ids,
                    "project_slug": project_slug,
                },
                timeout=SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS + 2.0,
            )
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})
```

**Step 3: Run linting**

Run: `make lint` (or `ruff check src/open_agent_kit/features/swarm/daemon/mcp_server.py`)
Expected: PASS

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/daemon/mcp_server.py src/open_agent_kit/features/swarm/constants.py
git commit -m "feat(swarm): Add swarm_fetch tool to MCP server for search-then-fetch workflow"
```

---

### Task 3: Add `oak swarm mcp` CLI Command

**Files:**
- Create: `src/open_agent_kit/features/swarm/commands/mcp.py`
- Modify: `src/open_agent_kit/features/swarm/commands/__init__.py`

**Reference:** `src/open_agent_kit/commands/team/mcp.py` for the team MCP CLI command pattern.

**Step 1: Create the CLI command**

Create `src/open_agent_kit/features/swarm/commands/mcp.py`:

```python
"""``oak swarm mcp`` — run the swarm MCP server."""

import logging
import sys

import typer

logger = logging.getLogger(__name__)


def mcp_command(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type (stdio, sse, streamable-http).",
    ),
    name: str = typer.Option(
        "",
        "--name",
        "-n",
        help="Swarm name. Auto-detected from ~/.oak/swarms/ if omitted.",
    ),
    port: int = typer.Option(
        0,
        "--port",
        "-p",
        help="HTTP port for streamable-http transport.",
    ),
) -> None:
    """Run the swarm MCP server for AI agent integration."""
    from open_agent_kit.features.swarm.daemon.mcp_server import (
        MCPTransport,
        run_mcp_server,
    )

    # For stdio transport, force logging to stderr to preserve stdout for JSON-RPC
    if transport == "stdio":
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)

    run_mcp_server(transport=MCPTransport(transport))
```

**Step 2: Register the subcommand**

Open `src/open_agent_kit/features/swarm/commands/__init__.py`. Add the mcp command registration after the existing commands (after line 305):

```python
@swarm_app.command("mcp")
def swarm_mcp(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type.",
    ),
    name: str = typer.Option(
        "",
        "--name",
        "-n",
        help="Swarm name.",
    ),
    port: int = typer.Option(
        0,
        "--port",
        "-p",
        help="HTTP port for streamable-http transport.",
    ),
) -> None:
    """Run the swarm MCP server."""
    from open_agent_kit.features.swarm.commands.mcp import mcp_command

    mcp_command(transport=transport, name=name, port=port)
```

**Step 3: Verify CLI registration**

Run: `oak-dev swarm --help`
Expected: Should show `mcp` in the list of commands.

Run: `oak-dev swarm mcp --help`
Expected: Should show transport, name, port options.

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/commands/mcp.py src/open_agent_kit/features/swarm/commands/__init__.py
git commit -m "feat(swarm): Add oak swarm mcp CLI command"
```

---

### Task 4: Create Swarm MCP Config and Installer API

**Files:**
- Create: `src/open_agent_kit/features/swarm/mcp/__init__.py`
- Create: `src/open_agent_kit/features/swarm/mcp/mcp.yaml`

**Reference:** `src/open_agent_kit/features/team/mcp/__init__.py` and `src/open_agent_kit/features/team/mcp/mcp.yaml`

**Step 1: Create the mcp.yaml**

Create `src/open_agent_kit/features/swarm/mcp/mcp.yaml`:

```yaml
name: oak-swarm
description: "OAK Swarm - cross-project search and federation for AI assistants"
command: "{oak-cli-command} swarm mcp"
capabilities:
  tools:
    - swarm_search
    - swarm_fetch
    - swarm_nodes
    - swarm_call
    - swarm_broadcast
    - swarm_status
```

**Step 2: Create the installer API module**

Create `src/open_agent_kit/features/swarm/mcp/__init__.py`:

```python
"""Swarm MCP server installation API.

Delegates to the shared MCPInstaller from the team feature,
parameterized with swarm-specific server name and command.
"""

from open_agent_kit.features.team.mcp import (
    install_mcp_server,
    remove_mcp_server,
)

__all__ = [
    "install_mcp_server",
    "remove_mcp_server",
]
```

**Step 3: Commit**

```bash
git add src/open_agent_kit/features/swarm/mcp/
git commit -m "feat(swarm): Add swarm MCP config and installer API"
```

---

### Task 5: Conditional Swarm MCP Installation in Pipeline

**Files:**
- Modify: `src/open_agent_kit/features/team/service.py` (the `update_mcp_servers` and `install_mcp_server` methods)

**Reference:** `src/open_agent_kit/features/team/service.py:606-656` for the existing `install_mcp_server` method.

The `ReconcileMcpServersStage` already calls `execute_hook("update_mcp_servers", ...)` which delegates to `TeamService.update_mcp_servers()`. We extend `update_mcp_servers` to also install the swarm MCP server when swarm config exists.

**Step 1: Add swarm config detection helper**

In `src/open_agent_kit/features/team/service.py`, add a method to `TeamService` (near the `install_mcp_server` method):

```python
    def _is_swarm_joined(self) -> bool:
        """Check if this project has joined a swarm.

        Returns True if swarm URL and token are configured in .oak/config.yaml.
        """
        try:
            config_file = self.project_root / ".oak" / "config.yaml"
            if not config_file.is_file():
                return False
            import yaml

            config = yaml.safe_load(config_file.read_text()) or {}
            swarm = config.get("swarm", {})
            return bool(swarm.get("url") and swarm.get("token"))
        except Exception:
            return False
```

**Step 2: Extend `update_mcp_servers` to install swarm MCP**

In the `update_mcp_servers` method (line ~447), after the existing `self.install_mcp_server(agents)` call, add the swarm MCP installation:

```python
    def update_mcp_servers(self, agents: list[str]) -> dict:
        """Update MCP servers for all agents.

        Installs both the team MCP server (always) and the swarm MCP server
        (only when the project has joined a swarm).
        """
        results = self.install_mcp_server(agents)

        # Conditionally install swarm MCP server
        if self._is_swarm_joined():
            swarm_results = self._install_swarm_mcp_server(agents)
            results["swarm"] = swarm_results

        return results
```

**Step 3: Add `_install_swarm_mcp_server` method**

Add this method to `TeamService`, modeled on `install_mcp_server`:

```python
    def _install_swarm_mcp_server(self, agents: list[str]) -> dict[str, str]:
        """Install swarm MCP server for agents that support MCP.

        Only called when the project has joined a swarm.
        """
        from open_agent_kit.features.team.mcp import install_mcp_server

        swarm_mcp_yaml = (
            Path(__file__).resolve().parent.parent
            / "swarm"
            / "mcp"
            / "mcp.yaml"
        )
        if not swarm_mcp_yaml.is_file():
            return dict.fromkeys(agents, "skipped (swarm mcp config not found)")

        import yaml

        mcp_config = yaml.safe_load(swarm_mcp_yaml.read_text()) or {}
        server_name = mcp_config.get("name", "oak-swarm")
        command = mcp_config.get("command", f"{MCP_CLI_COMMAND_PLACEHOLDER} swarm mcp")
        command = command.replace(
            MCP_CLI_COMMAND_PLACEHOLDER,
            resolve_ci_cli_command(self.project_root),
        )

        results = {}
        for agent in agents:
            if not self._get_agent_has_mcp(agent):
                results[agent] = "skipped (no MCP support)"
                continue

            result = install_mcp_server(
                project_root=self.project_root,
                agent=agent,
                server_name=server_name,
                command=command,
            )

            if result.success:
                results[agent] = "installed"
                logger.info(f"Installed swarm MCP server for {agent} via {result.method}")
            else:
                results[agent] = f"error: {result.message}"
                logger.warning(f"Failed swarm MCP install for {agent}: {result.message}")

        return results
```

**Step 4: Verify imports**

Ensure `MCP_CLI_COMMAND_PLACEHOLDER` and `resolve_ci_cli_command` are already imported in `service.py`. They should be — they're used by the existing `install_mcp_server` method.

**Step 5: Run linting**

Run: `make lint`
Expected: PASS

**Step 6: Commit**

```bash
git add src/open_agent_kit/features/team/service.py
git commit -m "feat(swarm): Conditional swarm MCP installation during oak init"
```

---

### Task 6: Add Swarm Join Hint

**Files:**
- Modify: `src/open_agent_kit/features/team/daemon/routes/swarm_config.py`
- Modify: `src/open_agent_kit/features/swarm/constants.py`

**Step 1: Add hint message constant**

Open `src/open_agent_kit/features/swarm/constants.py`. Add near the other message constants:

```python
SWARM_MESSAGE_MCP_HINT = (
    "To install the swarm MCP server for your agents, "
    "run: {cli_command} init"
)
```

**Step 2: Add hint to join response**

Open `src/open_agent_kit/features/team/daemon/routes/swarm_config.py`. In the join endpoint handler, after the successful join response is built, add the hint. Find the success return (around line 168) and add an `mcp_hint` field to the response:

```python
        return {
            "joined": True,
            "swarm_url": request.swarm_url,
            "mcp_hint": "Run 'oak init' to install the swarm MCP server for your agents.",
        }
```

**Step 3: Commit**

```bash
git add src/open_agent_kit/features/team/daemon/routes/swarm_config.py src/open_agent_kit/features/swarm/constants.py
git commit -m "feat(swarm): Add MCP install hint after swarm join"
```

---

### Task 7: Worker Template — Add Agent Token Auth

**Files:**
- Modify: `src/open_agent_kit/features/swarm/worker_template/src/types.ts`
- Modify: `src/open_agent_kit/features/swarm/worker_template/src/auth.ts`
- Modify: `src/open_agent_kit/features/swarm/worker_template/wrangler.toml.j2`

**Reference:** `src/open_agent_kit/features/team/cloud_relay/worker_template/src/auth.ts` for the `validateAgentToken` pattern.

**Step 1: Add AGENT_TOKEN to Env type**

Open `src/open_agent_kit/features/swarm/worker_template/src/types.ts`. Find the `Env` interface and add `AGENT_TOKEN`:

```typescript
export interface Env {
  SWARM: DurableObjectNamespace;
  SWARM_TOKEN: string;
  AGENT_TOKEN: string;
}
```

**Step 2: Add `validateAgentToken` to auth.ts**

Open `src/open_agent_kit/features/swarm/worker_template/src/auth.ts`. Add the agent token validation function after the existing `validateSwarmToken`:

```typescript
/**
 * Validate a cloud agent request against the configured agent token.
 *
 * Returns null on success, or a 401 Response on failure.
 */
export function validateAgentToken(
  request: Request,
  env: Env,
): Response | null {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return new Response(
      JSON.stringify({
        error: "missing Authorization header",
        hint: "Set header: Authorization: Bearer <agent-token>",
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  const [scheme, token] = authHeader.split(" ", 2);
  if (scheme !== "Bearer" || !token) {
    return new Response(
      JSON.stringify({ error: "invalid Authorization header format" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!env.AGENT_TOKEN) {
    return new Response(
      JSON.stringify({ error: "agent token not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!timingSafeEqual(token, env.AGENT_TOKEN)) {
    return new Response(
      JSON.stringify({ error: "invalid agent token" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  return null;
}
```

Ensure `timingSafeEqual` is already defined in `auth.ts` (it should be — used by `validateSwarmToken`). Update the `Env` import if needed.

**Step 3: Add AGENT_TOKEN to wrangler.toml.j2**

Open `src/open_agent_kit/features/swarm/worker_template/wrangler.toml.j2`. Add the `AGENT_TOKEN` variable in the `[vars]` section alongside `SWARM_TOKEN`:

```toml
[vars]
SWARM_TOKEN = "{{ swarm_token }}"
AGENT_TOKEN = "{{ agent_token }}"
```

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/worker_template/
git commit -m "feat(swarm): Add agent token auth to worker template"
```

---

### Task 8: Worker Template — Add `/mcp` Route and Handler

**Files:**
- Create: `src/open_agent_kit/features/swarm/worker_template/src/mcp-handler.ts`
- Modify: `src/open_agent_kit/features/swarm/worker_template/src/index.ts`

**Reference:** `src/open_agent_kit/features/team/cloud_relay/worker_template/src/mcp-handler.ts` for the JSON-RPC pattern.

**Step 1: Create mcp-handler.ts**

Create `src/open_agent_kit/features/swarm/worker_template/src/mcp-handler.ts`:

```typescript
/**
 * MCP Streamable HTTP protocol handler for the Swarm Worker.
 *
 * Handles MCP JSON-RPC requests from cloud agents at POST /mcp.
 * Supports:
 *   - initialize       — returns server capabilities
 *   - tools/list       — returns swarm tool definitions
 *   - tools/call       — proxied to Durable Object for federation
 */

const SERVER_NAME = "oak-swarm";
const PROTOCOL_VERSION = "2025-03-26";
const DEFAULT_TIMEOUT_MS = 30_000;

// ---------------------------------------------------------------------------
// JSON-RPC types
// ---------------------------------------------------------------------------

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

// ---------------------------------------------------------------------------
// Tool definitions (static, returned by tools/list)
// ---------------------------------------------------------------------------

const SWARM_TOOLS = [
  {
    name: "swarm_search",
    description:
      "Search across all projects in the swarm for observations, sessions, and plans.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Natural language search query." },
        search_type: {
          type: "string",
          enum: ["all", "memory", "sessions", "plans"],
          default: "all",
          description: "Search scope.",
        },
        limit: {
          type: "integer",
          default: 10,
          minimum: 1,
          maximum: 50,
          description: "Maximum results.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "swarm_fetch",
    description:
      "Fetch full details for items found via swarm_search. Pass chunk IDs from search results.",
    inputSchema: {
      type: "object",
      properties: {
        ids: {
          type: "array",
          items: { type: "string" },
          description: "Chunk IDs from swarm_search results.",
        },
        project_slug: {
          type: "string",
          default: "",
          description: "Project slug from search results.",
        },
      },
      required: ["ids"],
    },
  },
  {
    name: "swarm_nodes",
    description: "List all teams in the swarm with their connection status.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "swarm_call",
    description: "Call a tool on a specific project in the swarm.",
    inputSchema: {
      type: "object",
      properties: {
        tool_name: { type: "string", description: "Tool to invoke (e.g., oak_search)." },
        arguments: { type: "string", default: "{}", description: "JSON string of tool arguments." },
        target_project: { type: "string", description: "Project slug to route the call to." },
      },
      required: ["tool_name", "target_project"],
    },
  },
  {
    name: "swarm_broadcast",
    description: "Broadcast a tool call to all projects in the swarm.",
    inputSchema: {
      type: "object",
      properties: {
        tool_name: { type: "string", description: "Tool to invoke." },
        arguments: { type: "string", default: "{}", description: "JSON string of tool arguments." },
      },
      required: ["tool_name"],
    },
  },
  {
    name: "swarm_status",
    description: "Get swarm connection status.",
    inputSchema: { type: "object", properties: {} },
  },
];

// ---------------------------------------------------------------------------
// Tool name to swarm API endpoint mapping
// ---------------------------------------------------------------------------

const TOOL_ENDPOINTS: Record<string, { path: string; method: string }> = {
  swarm_search: { path: "/api/swarm/search", method: "POST" },
  swarm_fetch: { path: "/api/swarm/fetch", method: "POST" },
  swarm_nodes: { path: "/api/swarm/nodes", method: "GET" },
  swarm_call: { path: "/api/swarm/tool-call", method: "POST" },
  swarm_broadcast: { path: "/api/swarm/broadcast", method: "POST" },
  swarm_status: { path: "/api/swarm/status", method: "GET" },
};

// ---------------------------------------------------------------------------
// Public handler
// ---------------------------------------------------------------------------

export async function handleMcpRequest(
  body: unknown,
  doStub: DurableObjectStub,
): Promise<JsonRpcResponse> {
  const req = body as JsonRpcRequest;

  if (!req || req.jsonrpc !== "2.0" || !req.method) {
    return jsonRpcError(
      req?.id ?? (null as unknown as number),
      -32600,
      "invalid JSON-RPC request",
    );
  }

  switch (req.method) {
    case "initialize":
      return handleInitialize(req);
    case "tools/list":
      return handleToolsList(req);
    case "tools/call":
      return handleToolsCall(req, doStub);
    default:
      return jsonRpcError(req.id, -32601, `method not found: ${req.method}`);
  }
}

// ---------------------------------------------------------------------------
// Method handlers
// ---------------------------------------------------------------------------

function handleInitialize(req: JsonRpcRequest): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id: req.id,
    result: {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {
        tools: { listChanged: false },
      },
      serverInfo: {
        name: SERVER_NAME,
        version: "1.0.0",
      },
    },
  };
}

function handleToolsList(req: JsonRpcRequest): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id: req.id,
    result: { tools: SWARM_TOOLS },
  };
}

async function handleToolsCall(
  req: JsonRpcRequest,
  doStub: DurableObjectStub,
): Promise<JsonRpcResponse> {
  const params = req.params ?? {};
  const toolName = params.name as string | undefined;

  if (!toolName) {
    return jsonRpcError(req.id, -32602, "missing required parameter: name");
  }

  const endpoint = TOOL_ENDPOINTS[toolName];
  if (!endpoint) {
    return jsonRpcError(req.id, -32602, `unknown tool: ${toolName}`);
  }

  const args = (params.arguments as Record<string, unknown>) ?? {};

  // Forward to the Durable Object which handles the actual API routing
  const result = await forwardToDo(doStub, endpoint, args);

  if (result.error) {
    return jsonRpcError(req.id, -32000, result.error);
  }

  return {
    jsonrpc: "2.0",
    id: req.id,
    result: {
      content: [{ type: "text", text: JSON.stringify(result.result) }],
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface DoResponse {
  result?: unknown;
  error?: string;
}

async function forwardToDo(
  doStub: DurableObjectStub,
  endpoint: { path: string; method: string },
  args: Record<string, unknown>,
): Promise<DoResponse> {
  const url = `https://swarm${endpoint.path}`;
  const fetchOpts: RequestInit =
    endpoint.method === "GET"
      ? { method: "GET" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(args),
        };

  try {
    const response = await doStub.fetch(url, fetchOpts);
    const data = await response.json();
    return { result: data };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

function jsonRpcError(
  id: string | number,
  code: number,
  message: string,
): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id,
    error: { code, message },
  };
}
```

**Step 2: Add /mcp route to index.ts**

Open `src/open_agent_kit/features/swarm/worker_template/src/index.ts`. Add the import at the top:

```typescript
import { validateAgentToken } from "./auth";
import { handleMcpRequest } from "./mcp-handler";
```

Add the `/mcp` route in the `fetch` handler, before the existing swarm API routes (before the `/api/swarm/` block). The route should use `validateAgentToken`:

```typescript
    // ----- POST /mcp — cloud agent tool calls -----
    if (path === "/mcp" && request.method === "POST") {
      const authErr = validateAgentToken(request, env);
      if (authErr) return authErr;

      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return new Response(
          JSON.stringify({ error: "invalid JSON body" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }

      const doId = env.SWARM.idFromName(DO_ID_KEY);
      const doStub = env.SWARM.get(doId);
      const result = await handleMcpRequest(body, doStub);
      return Response.json(result);
    }
```

Note: `DO_ID_KEY` should already be defined in `index.ts` (it's `"singleton"`). Find where it's used for other routes and place the `/mcp` route nearby.

**Step 3: Commit**

```bash
git add src/open_agent_kit/features/swarm/worker_template/src/
git commit -m "feat(swarm): Add /mcp endpoint to swarm worker with agent token auth"
```

---

### Task 9: Scaffold — Generate Agent Token

**Files:**
- Modify: `src/open_agent_kit/features/swarm/scaffold.py`
- Modify: `src/open_agent_kit/features/swarm/commands/__init__.py` (deploy command)

**Reference:** `src/open_agent_kit/features/team/cloud_relay/scaffold.py:120` for how team relay passes `agent_token`.

**Step 1: Update `render_worker_template` to accept agent_token**

Open `src/open_agent_kit/features/swarm/scaffold.py`. Find the `render_worker_template` function signature. Add `agent_token` parameter:

```python
def render_worker_template(
    output_dir: Path,
    swarm_token: str,
    worker_name: str,
    custom_domain: str | None = None,
    agent_token: str = "",
    force: bool = False,
) -> Path:
```

In the Jinja2 context dict where template vars are passed (look for `"swarm_token": swarm_token`), add:

```python
    "agent_token": agent_token,
```

Also update `render_wrangler_config` if it exists (it re-renders just `wrangler.toml`) with the same `agent_token` parameter.

**Step 2: Generate agent_token during deploy**

Open `src/open_agent_kit/features/swarm/commands/__init__.py`. In the `swarm_deploy` command (around line 60), after `swarm_token = config[CI_CONFIG_SWARM_KEY_TOKEN]`, add agent token generation:

```python
    # Generate agent token for MCP endpoint
    agent_token = config.get("agent_token")
    if not agent_token:
        agent_token = generate_token()
        config["agent_token"] = agent_token
```

Then pass `agent_token` to `render_worker_template`:

```python
    render_worker_template(
        output_dir=scaffold_dir,
        swarm_token=swarm_token,
        worker_name=worker_name,
        agent_token=agent_token,
        force=force,
    )
```

The agent token gets persisted to `config.json` via the existing `save_swarm_config(name, config)` call at the end of deploy.

Also update the deploy route in `src/open_agent_kit/features/swarm/daemon/routes/deploy.py` — the `deploy_scaffold` handler similarly calls `render_worker_template`. Add `agent_token` there too, reading from state or config.

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/scaffold.py src/open_agent_kit/features/swarm/commands/__init__.py src/open_agent_kit/features/swarm/daemon/routes/deploy.py
git commit -m "feat(swarm): Generate and pass agent token during scaffold/deploy"
```

---

### Task 10: Swarm UI — MCP Settings Panel

**Files:**
- Modify: Swarm daemon UI components (under `src/open_agent_kit/features/swarm/daemon/ui/`)

**Reference:** Team daemon UI connectivity panel that shows relay MCP endpoint and token.

**Step 1: Add API endpoint for agent token retrieval**

Add a route to `src/open_agent_kit/features/swarm/daemon/routes/config.py` (or create a new `mcp_config.py` route file) that returns the agent token and MCP endpoint URL:

```python
@router.get("/api/config/mcp")
async def get_mcp_config() -> dict:
    """Get MCP endpoint configuration for cloud agents."""
    state = get_swarm_state()
    config = load_swarm_config(state.swarm_id) if state.swarm_id else {}

    swarm_url = os.environ.get("OAK_SWARM_URL", "")
    agent_token = config.get("agent_token", "")

    return {
        "mcp_endpoint": f"{swarm_url}/mcp" if swarm_url else "",
        "agent_token": agent_token,
        "has_agent_token": bool(agent_token),
    }
```

**Step 2: Add UI component**

In the swarm daemon UI (React), add an MCP configuration section to the Settings or Deploy page. This should show:
- MCP Endpoint URL (read-only, with copy button)
- Agent Token (masked by default, with reveal + copy buttons)
- Brief connection instructions

Model after the team relay's connectivity panel. The exact React component structure depends on the existing UI patterns in `src/open_agent_kit/features/swarm/daemon/ui/`.

**Step 3: Build UI assets**

Run the UI build command (check the swarm daemon's `package.json` for the build script):

```bash
cd src/open_agent_kit/features/swarm/daemon/ui && npm run build
```

**Step 4: Commit**

```bash
git add src/open_agent_kit/features/swarm/daemon/
git commit -m "feat(swarm): Add MCP settings panel to swarm UI"
```

---

### Task 11: Integration Testing and Quality Gate

**Step 1: Run the full quality gate**

Run: `make check`
Expected: PASS

**Step 2: Manual smoke test — local MCP**

```bash
# Start swarm daemon
oak-dev swarm start --name test-swarm

# Test MCP server via stdio
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | oak-dev swarm mcp

# Verify tools list
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | oak-dev swarm mcp
```

Expected: JSON-RPC responses with server info and 6 tools.

**Step 3: Manual smoke test — conditional installation**

```bash
# In a project NOT joined to a swarm
oak-dev init
# Verify .mcp.json does NOT contain oak-swarm

# Join a swarm (via team daemon UI or API)
# Then re-run init
oak-dev init
# Verify .mcp.json now contains oak-swarm
```

**Step 4: Final commit and cleanup**

```bash
git add -A
git commit -m "test(swarm): Verify swarm MCP integration"
```

---

## Summary of Commits

| Task | Commit Message |
|------|---------------|
| 1 | `feat(swarm): Add standalone swarm skill for cross-project knowledge` |
| 2 | `feat(swarm): Add swarm_fetch tool to MCP server` |
| 3 | `feat(swarm): Add oak swarm mcp CLI command` |
| 4 | `feat(swarm): Add swarm MCP config and installer API` |
| 5 | `feat(swarm): Conditional swarm MCP installation during oak init` |
| 6 | `feat(swarm): Add MCP install hint after swarm join` |
| 7 | `feat(swarm): Add agent token auth to worker template` |
| 8 | `feat(swarm): Add /mcp endpoint to swarm worker` |
| 9 | `feat(swarm): Generate and pass agent token during scaffold/deploy` |
| 10 | `feat(swarm): Add MCP settings panel to swarm UI` |
| 11 | `test(swarm): Verify swarm MCP integration` |

## Task Dependencies

```
Task 1 (Skill) ——————————————————— independent, do first
Task 2 (Fetch tool) ————————————— independent
Task 3 (CLI command) ————————————— depends on Task 2 (fetch tool in server)
Task 4 (MCP config) ————————————— independent
Task 5 (Conditional install) ———— depends on Task 4 (mcp.yaml must exist)
Task 6 (Join hint) ————————————— independent
Task 7 (Worker auth) ————————————— independent
Task 8 (Worker /mcp route) ———— depends on Task 7 (auth functions)
Task 9 (Scaffold agent token) ——— depends on Task 7 (wrangler.toml has AGENT_TOKEN)
Task 10 (UI panel) ————————————— depends on Task 9 (agent token in config)
Task 11 (Integration test) ———— depends on all above
```

Parallelizable groups:
- **Group A** (Python, local): Tasks 1, 2, 4, 6 (all independent)
- **Group B** (TypeScript, worker): Tasks 7 → 8
- **Group C** (Python, depends on A): Tasks 3, 5
- **Group D** (Python + TS, depends on B): Task 9 → 10
- **Final**: Task 11
