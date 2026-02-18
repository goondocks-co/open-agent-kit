---
title: Authentication
description: How Cloud Relay secures communication between cloud agents, the Worker, and your local daemon.
sidebar:
  order: 6
---

Cloud Relay uses a **two-token authentication model** to secure both sides of the relay — the connection from your local daemon to the Worker, and the connection from cloud agents to the Worker. Each token serves a distinct purpose and is stored differently.

## Token Overview

| Token | Purpose | Used By | Transport |
|-------|---------|---------|-----------|
| `relay_token` | Authenticates the local daemon to the Worker | Local Oak CI daemon | WebSocket `Sec-WebSocket-Protocol` header |
| `agent_token` | Authenticates cloud AI agents to the Worker | Claude.ai, ChatGPT, etc. | HTTP `Authorization: Bearer` header |

Both tokens are generated automatically during `oak ci cloud-init` (or the dashboard "Start Relay" flow) and must match between the Worker deployment and the connecting client.

## relay_token

The **relay token** secures the WebSocket connection between your local Oak CI daemon and the Cloudflare Worker. Only a client presenting the correct relay token can establish the persistent WebSocket link that carries tool calls and results.

**How it's used:**

1. During `cloud-init`, a token is generated using `secrets.token_urlsafe(32)`
2. The token is stored in both:
   - Your local config (`.oak/config.yaml`) for the daemon to read
   - The Worker's `wrangler.toml` as a secret for server-side validation
3. When the daemon connects, it sends the token in the `Sec-WebSocket-Protocol` header
4. The Worker's Durable Object validates the token before accepting the connection

## agent_token

The **agent token** secures the MCP endpoint that cloud AI agents connect to. Any agent presenting a valid agent token can invoke MCP tools through the relay.

**How it's used:**

1. Generated alongside the relay token during `cloud-init`
2. Stored in the Worker's `wrangler.toml` as a secret
3. Stored in `.oak/config.yaml` so the dashboard can display it (masked with reveal/copy)
4. Cloud agents include it as a Bearer token in HTTP requests:
   ```
   Authorization: Bearer <agent_token>
   ```
5. The Worker validates the token before forwarding requests to the Durable Object

The Worker accepts the token in two formats for flexibility:
- `Authorization: Bearer <token>` (standard)
- `Authorization: <token>` (raw — for clients that don't add the Bearer prefix)

**You provide this token when registering the MCP server** with your cloud AI agent (Claude.ai settings, mcp.json config, etc.). See [Cloud Agents](/open-agent-kit/features/cloud-relay/cloud-agents/) for setup instructions per agent.

## Token Storage

| Location | Contains | Access |
|----------|----------|--------|
| `.oak/config.yaml` | Both tokens | Local filesystem (user-controlled) |
| Worker `wrangler.toml` | Both tokens as env vars | Local filesystem during deploy; encrypted at rest on Cloudflare |
| Cloudflare Workers secrets | Both tokens | Encrypted at rest; only accessible by your Worker code |

The `wrangler.toml` file is excluded from version control by the scaffold's `.gitignore`. Keep a copy of the agent token to register with cloud agents, or view it in the dashboard (Cloud page, when connected).

## Token Rotation

To rotate tokens (e.g., if a token is compromised or you want to revoke access):

1. **Remove the existing scaffold** to force regeneration:
   ```bash
   rm -rf oak/cloud-relay
   ```
2. **Re-run `cloud-init`** to generate fresh tokens and re-deploy:
   ```bash
   oak ci cloud-init
   ```
3. **Update cloud agents** with the new agent token

Both the old relay connection and any agent sessions using the previous tokens are immediately invalidated when the Worker is re-deployed with new secrets.

## Security Considerations

**No inbound ports.** The local daemon initiates the WebSocket connection outward. Your machine never accepts incoming connections, eliminating an entire class of network-level attacks.

**Tokens are opaque.** Both tokens are generated with `secrets.token_urlsafe(32)`, producing 256 bits of entropy. They carry no embedded claims or metadata.

**Transport encryption.** All connections use TLS — HTTPS for the MCP endpoint, WSS for the WebSocket link. Cloudflare terminates TLS at the edge.

**CORS support.** The Worker includes CORS headers to support browser-based MCP clients. Cross-origin requests are allowed with proper `Authorization` headers.

**Blast radius.** Each project has its own Worker with its own token pair. Compromising one project's tokens does not affect others.
