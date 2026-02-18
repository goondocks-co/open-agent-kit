---
title: Getting Started
description: Deploy your first Cloud Relay and connect a cloud AI agent in one command.
sidebar:
  order: 1
---

This quickstart walks you through deploying a Cloud Relay and connecting it to a cloud AI agent. The entire process is handled by a single command.

## Prerequisites

Before you begin, make sure you have:

- [ ] **Oak CI** installed and the daemon running (`oak ci start`)
- [ ] **Cloudflare account** created and wrangler authenticated — see [Cloudflare Setup](/open-agent-kit/features/cloud-relay/cloudflare-setup/)
- [ ] **Node.js v18+** installed (provides `npm` and `npx`)

## Option A: Dashboard (Recommended)

Open the Oak CI dashboard and navigate to the **Cloud** page. Click **Start Relay** — the button orchestrates the entire pipeline:

1. Scaffolds a Cloudflare Worker project in `oak/cloud-relay/`
2. Runs `npm install` for dependencies
3. Verifies Cloudflare authentication via `wrangler whoami`
4. Deploys the Worker with `npx wrangler deploy`
5. Connects the daemon over WebSocket

A green status dot and your MCP Server URL appear when the relay is active. The page also shows your agent token (masked by default, with reveal and copy buttons) and registration instructions for cloud agents.

If any phase fails, the dashboard shows a targeted error message with a suggested fix (e.g., "Run `wrangler login` to authenticate") and a collapsible detail section with the raw subprocess output.

## Option B: CLI

Run `cloud-init` from your project directory:

```bash
oak ci cloud-init
```

This runs the same five-phase pipeline as the dashboard button. On success, it prints:

- **Worker URL** — the deployed Cloudflare Worker endpoint
- **MCP Endpoint** — the URL cloud agents connect to (`<worker-url>/mcp`)
- **Agent Token** — the token cloud agents use to authenticate

```
✓ Connected to cloud relay: https://oak-relay-myproject.you.workers.dev
  Worker URL: https://oak-relay-myproject.you.workers.dev
  MCP endpoint: https://oak-relay-myproject.you.workers.dev/mcp
  Agent token: abc123...xyz
  Save this token — you'll need it when registering cloud agents.
```

:::tip
If the relay was previously set up, `cloud-init` skips completed phases (scaffold, install, deploy) and just reconnects the WebSocket.
:::

## Register a Cloud Agent

Once the relay is active, give your cloud AI agent the MCP endpoint and agent token:

- **MCP Server URL**: `https://<your-worker>.workers.dev/mcp`
- **Agent Token**: The value from `cloud-init` output or the dashboard

For Claude.ai, add an MCP server in your settings with these values. See [Cloud Agents](/open-agent-kit/features/cloud-relay/cloud-agents/) for detailed instructions per agent.

## Verify with curl

```bash
curl -X POST https://<your-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

A successful response returns a JSON-RPC result with the list of MCP tools available from your local daemon.

## What Happens Next

Once connected, cloud agents can call any MCP tool registered with your local Oak CI daemon — code search, memory queries, context retrieval, and more. The relay handles all the plumbing transparently.

Your local daemon maintains the WebSocket connection in the background. If the connection drops (network change, daemon restart), it automatically reconnects with exponential backoff.

## Stopping and Restarting

**Stop** the relay from the dashboard (click "Stop Relay") or CLI:

```bash
oak ci cloud-disconnect
```

Stopping disconnects the WebSocket but leaves the Worker deployed on Cloudflare. To reconnect later, click "Start Relay" again or run `oak ci cloud-init` — it skips the deploy phase since the Worker is already live.

## Next Steps

- **[Cloud Agents](/open-agent-kit/features/cloud-relay/cloud-agents/)** — Per-agent registration instructions (Claude.ai, ChatGPT, MCP config files)
- **[Authentication](/open-agent-kit/features/cloud-relay/authentication/)** — Understanding the two-token security model
- **[Troubleshooting](/open-agent-kit/features/cloud-relay/troubleshooting/)** — Common issues and solutions
