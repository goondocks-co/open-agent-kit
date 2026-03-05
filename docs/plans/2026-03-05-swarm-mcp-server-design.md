# Swarm MCP Server + Skill Design

**Date:** 2026-03-05
**Status:** Approved
**Branch:** feat/swarm-mode

## Problem

The swarm feature has federation plumbing in place (search, tool calls, broadcast across team nodes), but agents coding on a swarm-connected project have no way to access cross-project knowledge. The team MCP server (`oak-ci`) provides local project intelligence; we need a parallel `oak-swarm` MCP server for org-level intelligence, plus a skill that teaches agents when to use each.

## Design

### Architecture Overview

```
Agent (Claude Code, Cursor, etc.)
  |
  +-- oak-ci MCP server (local project knowledge)
  |     stdio / streamable-http via team relay
  |
  +-- oak-swarm MCP server (cross-project knowledge)
        stdio (local daemon) / streamable-http (swarm worker)
```

Two independent MCP servers, two independent skills. An agent with both installed naturally checks team for local context and swarm for org-wide patterns.

### MCP Server: Two Entry Points

| Entry Point | Transport | Auth | Use Case |
|---|---|---|---|
| `oak swarm mcp` (local) | stdio + streamable-http | Swarm daemon bearer token | Local agents |
| Swarm Worker `/mcp` (remote) | streamable-http | Agent token (separate from swarm token) | Cloud coding agents |

#### Local Daemon MCP (`oak swarm mcp`)

The existing `features/swarm/daemon/mcp_server.py` provides a stdio MCP server with 5 tools. Changes:

- Add streamable-http transport support (mirror `oak team mcp` implementation)
- Add `swarm_fetch` tool (search-then-fetch two-step pattern)
- Add auto-daemon startup if swarm daemon isn't running
- Add retry logic for daemon restarts (ConnectError handling)

#### Worker MCP Endpoint (`/mcp` on Cloudflare Worker)

Mirror the team relay pattern:

- New `/mcp` route in `worker_template/src/index.ts`
- Streamable-http MCP transport
- Auth via `AGENT_TOKEN` env var (NOT the `SWARM_TOKEN`)
  - `SWARM_TOKEN`: worker-to-worker auth (team registration, heartbeats, tool routing)
  - `AGENT_TOKEN`: cloud agent auth (`Authorization: Bearer <agent-token>`)
- Agent token generated during scaffold/deploy, stored in `wrangler.toml`
- Displayed in swarm UI for copy/paste setup
- Proxies tool calls through the Durable Object

### Tool Surface (6 Tools)

| Tool | Purpose | Pattern |
|---|---|---|
| `swarm_search` | Search across all nodes: observations, session summaries, plans | Browse (broad results with IDs) |
| `swarm_fetch` | Get full details for a specific search result | Detail (single asset, full content) |
| `swarm_nodes` | List connected teams with status and capabilities | Discovery |
| `swarm_call` | Call a specific tool on a targeted team node | Action (targeted) |
| `swarm_broadcast` | Call a tool on all connected nodes | Action (fan-out) |
| `swarm_status` | Check swarm connectivity | Status |

**Search-then-fetch workflow** (primary agent pattern):
1. `swarm_search("retry patterns", search_type="memory")` -> summaries + IDs across projects
2. `swarm_fetch(chunk_id="abc123")` -> full observation/session/plan detail

**Search types:** `all`, `memory`, `sessions`, `plans`. No `code` search type — code search is team-node-only via `oak_search`.

### CLI Entry Point

New command added to swarm commands:

```
oak swarm mcp [--transport stdio|streamable-http] [--port PORT] [--name SWARM_NAME]
```

File: `src/open_agent_kit/features/swarm/commands/mcp.py`

Behavior:
- Discovers swarm daemon port from `~/.oak/swarms/*/daemon.port`
- Auto-starts swarm daemon if not running
- Validates swarm config exists before starting
- Stderr-safe logging for stdio transport (preserves stdout for JSON-RPC)

### Conditional Installation

**Gate:** Project must have swarm config (`swarm.url` + `swarm.token` in `.oak/config.yaml`).

**Flow:**
1. User joins a swarm via the team daemon UI (writes swarm config to `.oak/config.yaml`)
2. Team daemon shows hint: "Run `{cli} init` to install the swarm MCP server"
3. User runs `oak init` (or any team member does)
4. `ReconcileMcpServersStage` detects swarm config -> installs `oak-swarm` MCP server
5. `.mcp.json` is committed to git -> all team members get the server automatically

**No dead servers:** If swarm config doesn't exist, the MCP server entry is never created.

**MCP config file:** `features/swarm/mcp/mcp.yaml`

```yaml
name: oak-swarm
command: "{oak-cli-command} swarm mcp"
```

**Installer:** Reuse `MCPInstaller` from `team/mcp/installer.py` — already parameterized by `server_name` and `command`. The swarm feature just provides its own `mcp.yaml` and the reconcile stage calls the installer with swarm-specific params when the gate passes.

### Swarm Skill

New skill at `features/swarm/skills/swarm/SKILL.md`.

**Decision framework** (the core value of the skill):

| Question | Use Team (`oak-ci`) | Use Swarm (`oak-swarm`) |
|---|---|---|
| "How does auth work in this project?" | Yes | |
| "How do we handle auth across projects?" | | Yes |
| "What patterns exist for error handling?" | Local patterns | Org-wide conventions |
| "What was decided about the API?" | Local decisions | Cross-project decisions |
| "What depends on this change?" | Local impact | Cross-project impact |

**Content:**
- Quick start with MCP tool examples
- Search-then-fetch workflow documentation
- Tool reference for all 6 tools
- Common patterns for coding agents
- When to prefer team vs swarm

**Registered in:** `features/swarm/manifest.yaml` under `skills:` key.

### Worker Template Changes

Files modified in `worker_template/`:

| File | Change |
|---|---|
| `src/types.ts` | Add `AGENT_TOKEN` to env bindings |
| `src/index.ts` | Add `/mcp` route with agent token auth |
| `src/auth.ts` | Add `validateAgentRequest()` (mirror team relay pattern) |
| `wrangler.toml.j2` | Add `AGENT_TOKEN` env var |

Scaffold changes (`features/swarm/scaffold.py`):
- Generate `agent_token` during scaffold
- Pass to Jinja2 template rendering
- Store in swarm config for UI retrieval

### Swarm UI Changes

Settings or Deploy page shows:
- MCP endpoint URL (the worker URL + `/mcp`)
- Agent token (for copy/paste into agent config)
- Connection instructions (same pattern as team relay UI)

## File Inventory

### New Files

| File | Purpose |
|---|---|
| `features/swarm/commands/mcp.py` | `oak swarm mcp` CLI command |
| `features/swarm/mcp/__init__.py` | MCP install/remove public API |
| `features/swarm/mcp/mcp.yaml` | Server identity and tool docs |
| `features/swarm/skills/swarm/SKILL.md` | Swarm skill for agents |
| `worker_template/src/auth.ts` | Agent token validation (new or extend existing) |

### Modified Files

| File | Change |
|---|---|
| `features/swarm/daemon/mcp_server.py` | Add streamable-http, swarm_fetch tool |
| `features/swarm/manifest.yaml` | Add skills, mcp config |
| `features/swarm/scaffold.py` | Generate + pass agent_token |
| `features/swarm/commands/__init__.py` | Register mcp subcommand |
| `worker_template/src/index.ts` | Add `/mcp` route |
| `worker_template/src/types.ts` | Add `AGENT_TOKEN` binding |
| `worker_template/wrangler.toml.j2` | Add `AGENT_TOKEN` env var |
| Pipeline `ReconcileMcpServersStage` | Conditional swarm MCP install |
| Team daemon swarm_config routes | Add "run init" hint after join |

## Implementation Sequence

1. **Skill** — highest impact, lowest effort. Even with current stdio MCP, teaches agents how to use swarm tools.
2. **`oak swarm mcp` CLI + mcp.yaml + installer** — makes the local MCP server installable.
3. **Streamable-http on daemon MCP** — adds HTTP transport to local server.
4. **Conditional installation in ReconcileMcpServersStage** — auto-detects swarm config, installs on `oak init`.
5. **`swarm_fetch` tool** — completes the search-then-fetch workflow.
6. **Worker `/mcp` endpoint + agent token** — remote MCP via Cloudflare worker.
7. **Swarm UI: MCP settings panel** — shows endpoint URL + agent token.

## Non-Goals

- Code search via swarm (stays team-node-only)
- Swarm autonomous agents (separate effort, scaffolding exists)
- Changes to team MCP server
- MCP server for projects not joined to a swarm
