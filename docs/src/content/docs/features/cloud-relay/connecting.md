---
title: Connecting
description: Connection lifecycle, auto-reconnect, and advanced connection management for Cloud Relay.
sidebar:
  order: 4
---

When you use `oak ci cloud-init` or click "Start Relay" in the dashboard, the connection is established automatically as the final phase of the deployment pipeline. This page covers what happens under the hood and the lower-level CLI commands available for advanced use.

## How Connection Works

1. The daemon reads the Worker URL and relay token from `.oak/config.yaml`
2. It opens a WebSocket connection to `wss://<worker-url>/ws`
3. The relay token is sent in the `Sec-WebSocket-Protocol` header for authentication
4. The Worker's Durable Object validates the token and accepts the connection
5. MCP tool calls from cloud agents are relayed over this WebSocket

The connection is **outbound only** — your daemon connects to the Worker, not the other way around. No inbound ports or firewall rules are needed.

## Checking Status

### Dashboard

The **Cloud** page in the Oak CI dashboard shows real-time connection status:

- **Green dot** — Relay is active and connected
- **Gray dot** — Relay is inactive

When connected, the page displays the Cloudflare account name, MCP Server URL (with copy button), and agent token.

### CLI

```bash
oak ci cloud-status
```

Shows connection state, Worker URL, connected-at timestamp, last heartbeat, and reconnect attempts (if any).

For scripting, retrieve just the Worker URL with no formatting:

```bash
oak ci cloud-url
```

This prints the Worker URL to stdout — useful in shell scripts:

```bash
oak ci cloud-url | pbcopy
```

## Disconnecting

### Dashboard

Click **Stop Relay** on the Cloud page. This disconnects the WebSocket but leaves the Worker deployed on Cloudflare.

### CLI

```bash
oak ci cloud-disconnect
```

This closes the WebSocket connection. Cloud agents see the relay instance as offline. The Worker remains deployed — you can reconnect later.

## Auto-Reconnect

If the WebSocket connection drops (network interruption, daemon restart, Worker re-deployment), the daemon automatically reconnects using exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1st | 1 second |
| 2nd | 2 seconds |
| 3rd | 4 seconds |
| 4th | 8 seconds |
| ... | up to 60 seconds max |

The backoff resets to 1 second after a successful reconnection. During reconnection attempts, cloud agents see the relay instance as temporarily offline.

## Daemon Restart Behavior

When the Oak CI daemon restarts (manually or after a machine reboot), the cloud relay does **not** auto-reconnect on startup. To re-establish the connection:

- Click **Start Relay** in the dashboard, or
- Run `oak ci cloud-init` (skips deploy, just reconnects)

## What Cloud Agents See When Offline

When the local daemon is not connected to the Worker:

- The Worker's `/health` endpoint reports the instance as offline
- MCP requests from cloud agents receive an error response indicating the local instance is unavailable
- No tool calls are queued — the relay is real-time only

Once the daemon reconnects, tool calls resume immediately.

## Advanced CLI Commands

These lower-level commands are available for power users and scripting. For most users, `cloud-init` and the dashboard handle everything.

| Command | Description |
|---------|-------------|
| `oak ci cloud-init` | Full pipeline: scaffold, install, deploy, connect |
| `oak ci cloud-init --force` | Re-scaffold and re-deploy (fresh template, tokens preserved) |
| `oak ci cloud-connect [url]` | Connect to a specific Worker URL (skips scaffold/deploy) |
| `oak ci cloud-disconnect` | Disconnect the WebSocket |
| `oak ci cloud-status` | Show connection state and details |
| `oak ci cloud-url` | Print Worker URL (for scripting) |

## Configuration

The cloud relay configuration lives in `.oak/config.yaml`:

```yaml
cloud_relay:
  worker_url: https://oak-relay-myproject.you.workers.dev
  token: <relay_token>
  agent_token: <agent_token>
  worker_name: oak-relay-myproject
  custom_domain: relay.example.com  # optional
```

These values are populated automatically during `cloud-init`. You generally don't need to edit them manually.

### Custom Domain

If you configure a custom domain for your Worker in the Cloudflare dashboard, set `custom_domain` so the MCP endpoint uses your domain instead of the `workers.dev` URL. Enter just the hostname (optionally with port) — no protocol or path.

You can set this in the dashboard under **Cloud > Settings**, or directly in `.oak/config.yaml`. Set to `null` or remove the key to revert to the default `workers.dev` URL.

## Monitoring

```bash
# Quick status check
oak ci cloud-status

# Watch daemon logs for relay activity
tail -f .oak/ci/daemon.log | grep cloud
```

The Oak CI dashboard's **Cloud** page provides real-time status with polling every 30 seconds.
