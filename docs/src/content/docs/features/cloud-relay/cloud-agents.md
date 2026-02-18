---
title: Cloud Agents
description: Register cloud AI agents to use your Oak CI tools through Cloud Relay.
sidebar:
  order: 5
---

Once Cloud Relay is deployed and connected, you can register cloud AI agents to call your local Oak CI tools. Any agent that supports MCP Streamable HTTP can connect.

## What You Need

After starting the relay (via the dashboard or `oak ci cloud-init`), you need two pieces of information:

- **MCP Server URL**: `https://<your-worker>.workers.dev/mcp`
- **Agent Token**: Displayed in the dashboard (masked with reveal/copy buttons) or printed by `cloud-init`

Both values are also available on the dashboard's **Cloud** page when the relay is active.

## MCP Config File (mcp.json)

Many MCP-compatible clients — Claude Code, Cursor, Windsurf, VS Code Copilot — read configuration from a `mcp.json` file. Add Oak CI as a server:

```json
{
  "mcpServers": {
    "oak-ci": {
      "url": "https://<your-worker>.workers.dev/mcp",
      "headers": {
        "Authorization": "Bearer <agent_token>"
      }
    }
  }
}
```

Place the file in your project root for per-project config, or in your home directory for global config.

| Client | Config File Location |
|--------|---------------------|
| **Claude Code** | `.claude/mcp.json` |
| **Cursor** | `.cursor/mcp.json` |
| **Windsurf** | `.windsurf/mcp.json` |
| **VS Code Copilot** | `.vscode/mcp.json` |

:::tip
The dashboard generates this JSON config block with your actual URL and token pre-filled. Click the copy button to grab it.
:::

## Claude.ai

Claude.ai supports MCP servers natively. To add your Cloud Relay:

1. Open Claude.ai and go to **Settings**
2. Navigate to the **MCP Servers** section
3. Click **Add MCP Server**
4. Enter:
   - **Name**: A descriptive label (e.g., "My Project - Oak CI")
   - **URL**: `https://<your-worker>.workers.dev/mcp`
   - **Authentication**: Bearer token — paste your `agent_token`
5. Save the configuration

Claude.ai will connect to your relay and discover available tools. You can verify by asking Claude to list available tools or run a code search.

## ChatGPT

ChatGPT's MCP integration follows a similar pattern. When configuring MCP servers:

1. Open ChatGPT and go to **Settings** > **Connected Tools**
2. Click **Add Tool** and select MCP
3. Enter the MCP server URL: `https://<your-worker>.workers.dev/mcp`
4. Authenticate using your agent token when prompted

Refer to OpenAI's documentation for the current MCP configuration interface, as it may change.

## Other MCP-Compatible Agents

Any AI agent that supports the MCP Streamable HTTP transport can connect. The configuration pattern is the same:

| Setting | Value |
|---------|-------|
| **URL** | `https://<your-worker>.workers.dev/mcp` |
| **Transport** | Streamable HTTP (POST) |
| **Auth header** | `Authorization: Bearer <agent_token>` |
| **Content-Type** | `application/json` |

## Testing with curl

Verify the relay is working before registering with a cloud agent:

```bash
# List available tools
curl -X POST https://<your-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

A successful response returns a JSON-RPC result with the list of MCP tools available from your local daemon. If the local daemon is not connected, you'll receive an error indicating the instance is offline.

### Test a Tool Call

```bash
# Search your codebase
curl -X POST https://<your-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"oak_search","arguments":{"query":"authentication"}},"id":2}'
```

### MCP Inspector

For interactive testing, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) — a visual tool for browsing and calling MCP server tools. Point it at your MCP endpoint and provide your agent token for authentication.

## What Tools Are Exposed

Cloud Relay exposes all MCP tools registered with your local Oak CI daemon. The exact set depends on your project configuration, but typically includes:

| Tool | Description |
|------|-------------|
| `oak_search` | Semantic code search across your codebase |
| `oak_context` | Task-relevant context aggregation |
| `oak_remember` | Store observations and learnings |
| `oak_resolve_memory` | Mark observations as resolved |

These are the same tools available to local agents — cloud agents get identical capabilities through the relay.

## Multiple Agents

You can register the same Cloud Relay with multiple cloud agents simultaneously. All agents share the same `agent_token` and have access to the same set of tools. The Worker handles concurrent requests from multiple agents transparently.

## Revoking Agent Access

To revoke access for all cloud agents, re-generate tokens and re-deploy:

```bash
# Remove existing scaffold and re-deploy with fresh tokens
rm -rf oak/cloud-relay
oak ci cloud-init
```

This generates new tokens and deploys a fresh Worker. Update any agents you want to keep connected with the new agent token.

Since all agents share the same token, rotating the token revokes access for all agents at once.
