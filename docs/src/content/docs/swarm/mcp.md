---
title: MCP
description: Swarm MCP tools and cloud agent configuration for the Swarm relay.
sidebar:
  order: 2
---

When connected to a swarm, the Swarm Worker exposes cross-project MCP tools through a Streamable HTTP endpoint. Any AI agent that supports MCP can connect — the same clients that work with the [Team MCP](/team/mcp/) work here too.

## What You Need

After deploying the swarm Worker (`oak swarm deploy -n <name>`), you need two values:

- **MCP Server URL**: `https://<swarm-worker>.workers.dev/mcp`
- **Agent Token**: Stored in the swarm config file (`~/.oak/swarms/<name>/config.json`)

The Worker scaffold is stored under `~/.oak/swarms/<name>/worker/` (including `wrangler.toml`).

## MCP Config File

Many MCP-compatible clients read project MCP configuration files (JSON or TOML):

```json
{
  "mcpServers": {
    "oak-swarm": {
      "url": "https://<swarm-worker>.workers.dev/mcp",
      "headers": {
        "Authorization": "Bearer <swarm_agent_token>"
      }
    }
  }
}
```

Use project-scoped config so Team and Swarm server entries stay tied to this repository.

| Client | Config File Location |
|--------|---------------------|
| **Claude Code** | `.mcp.json` |
| **Cursor** | `.cursor/mcp.json` |
| **Codex** | `.codex/config.toml` |
| **Gemini CLI** | `.gemini/settings.json` |
| **OpenCode** | `opencode.json` |
| **VS Code Copilot** | `.vscode/mcp.json` |

## Cloud Agent Setup

The setup process is the same as for Team MCP — add the swarm URL and token to your cloud agent's MCP configuration. See [Team MCP](/team/mcp/) for step-by-step instructions per client (Claude.ai, ChatGPT, mcp.json, etc.).

## Agent Token

The **agent token** authenticates cloud AI agents to the Swarm Worker's MCP endpoint.

- Generated automatically during swarm deployment (`oak swarm deploy -n <name>`)
- Stored in `~/.oak/swarms/<name>/config.json` and the Worker's secrets (encrypted at rest on Cloudflare)
- Requires `Authorization: Bearer <token>`

To rotate the token, re-deploy: `oak swarm deploy -n <name> --force`

## Testing with curl

```bash
# List available tools
curl -X POST https://<swarm-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

### Test a Tool Call

```bash
# Search across all connected projects
curl -X POST https://<swarm-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"swarm_search","arguments":{"query":"retry backoff"}},"id":2}'
```

---

## Tools

The Swarm MCP server exposes the following tools for **cross-project** queries. While [Team tools](/team/mcp/#tools) fan out to nodes on the *same* project, Swarm tools fan out to *different* projects connected to the same swarm.

| Tool | Purpose |
|------|---------|
| [`swarm_search`](#swarm_search) | Search across all swarm-connected projects |
| [`swarm_fetch`](#swarm_fetch) | Fetch full details for items found via `swarm_search` |
| [`swarm_nodes`](#swarm_nodes) | List swarm teams and their status |
| [`swarm_status`](#swarm_status) | Show swarm connection status |

:::note[Team vs Swarm]
Both can be active simultaneously — use Team federation (`include_network=true`) for within-project knowledge and Swarm tools for cross-project knowledge.
:::

---

## swarm_search

Search across all connected projects in the swarm. Returns results from multiple codebases with project attribution.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Natural language search query |
| `search_type` | string | No | `"all"` | Search scope: `"all"`, `"memory"`, `"sessions"`, or `"plans"` |
| `limit` | integer | No | `10` | Maximum results to return (1–50) |

### Response

Returns ranked results from all connected projects. Each result includes project attribution (project slug) so you can identify which project the result came from.

### Example

```json
{
  "query": "retry backoff pattern",
  "search_type": "memory",
  "limit": 10
}
```

---

## swarm_fetch

Fetch full details for items found via `swarm_search`. Pass the chunk IDs and project slug from search results to retrieve complete content.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ids` | array of strings | Yes | — | Chunk IDs from `swarm_search` results |
| `project_slug` | string | No | — | Project slug from search results. If omitted, broadcasts to all projects. |

### Response

Returns full content for each requested chunk, including file path, line range, and complete code text, attributed to the source project.

### Example

```json
{
  "ids": ["chunk_abc123", "chunk_def456"],
  "project_slug": "my-api-service"
}
```

---

## swarm_nodes

List all projects currently connected to the swarm. Returns project slugs, connection status, and capabilities.

### Parameters

This tool takes no parameters.

### Response

Returns a list of connected projects with:
- Project slug
- Connection status
- Capabilities
- Node count
- OAK version

### Example

```json
{}
```

---

## swarm_status

Check the current swarm connectivity status. Returns whether this node is connected, the swarm ID, and the number of peer nodes.

### Parameters

This tool takes no parameters.

### Response

Returns swarm connection information:
- Connected status
- Swarm ID
- Swarm URL
- Number of peer nodes

### Example

```json
{}
```
