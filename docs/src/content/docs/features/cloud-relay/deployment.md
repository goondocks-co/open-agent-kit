---
title: Deployment
description: How Cloud Relay deploys and manages the Cloudflare Worker that powers the relay.
sidebar:
  order: 3
---

This guide covers the Worker deployment lifecycle — what happens under the hood during `oak ci cloud-init` (or clicking "Start Relay"), re-deployment after upgrades, and manual Worker management.

## Automated Deployment

Cloud Relay uses a **turnkey deployment pipeline** that runs automatically when you click "Start Relay" in the dashboard or run `oak ci cloud-init`. The pipeline has five phases, and it skips any phase that's already complete:

| Phase | What It Does | Skipped When |
|-------|-------------|-------------|
| **Scaffold** | Generates Worker project in `oak/cloud-relay/` | `package.json` and `wrangler.toml` exist |
| **npm install** | Installs Worker dependencies | `node_modules/` exists |
| **Auth check** | Runs `npx wrangler whoami` to verify Cloudflare auth | Never skipped (always verified) |
| **Deploy** | Runs `npx wrangler deploy` to publish the Worker | `worker_url` in config and Worker is reachable |
| **Connect** | Establishes WebSocket from daemon to Worker | Already connected to same URL |

This means:

- **First run**: All five phases execute (~30-60 seconds)
- **Reconnecting**: Only the auth check and connect phases run (~2-3 seconds)
- **After Oak CI upgrade**: Scaffold and deploy re-run with the latest template; tokens are preserved

## Generated Directory Structure

The scaffold phase creates a Cloudflare Worker project at `oak/cloud-relay/` (relative to your project root):

```
oak/cloud-relay/
  src/
    index.ts           # Worker entry point — HTTP routing and CORS
    auth.ts            # Token validation logic
    mcp-handler.ts     # MCP Streamable HTTP request handling
    relay-object.ts    # Durable Object — WebSocket relay and state
    types.ts           # Shared TypeScript interfaces
  wrangler.toml        # Cloudflare config with tokens and bindings
  package.json         # Dependencies (minimal)
  tsconfig.json        # TypeScript config
  .gitignore           # Excludes wrangler.toml, node_modules/, .wrangler/
```

### What's Git-Tracked

The scaffold writes a `.gitignore` inside `oak/cloud-relay/` that excludes secrets and build artifacts:

```
wrangler.toml
node_modules/
.wrangler/
```

This means the Worker source code (`.ts`, `package.json`, `tsconfig.json`) can be committed to version control, while the `wrangler.toml` (which contains authentication tokens) stays local.

### What the Scaffold Does

1. **Generates authentication tokens** — Creates a `relay_token` and `agent_token` using `secrets.token_urlsafe(32)` (256 bits of entropy each)
2. **Writes Worker source** — TypeScript files that implement the MCP relay protocol with CORS support
3. **Renders wrangler.toml** — Injects tokens as secrets, sets up Durable Object bindings and migrations
4. **Updates local config** — Stores tokens and worker name in `.oak/config.yaml`

## Re-Deploying After Oak CI Upgrades

When you upgrade Oak CI, the Worker template may include protocol changes or improvements. To update your deployed Worker:

```bash
oak ci cloud-init --force
```

The `--force` flag re-scaffolds the Worker project with the latest template (overwriting source files), re-installs dependencies, and re-deploys. Your existing tokens are preserved from config unless you want fresh ones (delete `oak/cloud-relay/` first).

From the dashboard, stopping and restarting the relay achieves the same effect if the scaffold directory has been removed.

## Worker Naming

Each project gets a unique Worker name derived from the project directory name:

```
oak-relay-<sanitized-project-name>
```

For example, a project in `~/projects/my-app` gets the Worker name `oak-relay-my-app`. The name is sanitized to comply with Cloudflare's naming rules (lowercase, alphanumeric, hyphens, max 63 characters).

## Custom Domains

By default, Workers are served from `*.workers.dev`. If you have a domain managed by Cloudflare, you can add a custom route:

1. Open the Cloudflare dashboard
2. Navigate to **Workers & Pages > your Worker > Settings > Triggers**
3. Add a custom domain or route (e.g., `relay.yourdomain.com`)

The Worker handles requests from both the custom domain and the `workers.dev` URL.

## Viewing Worker Logs

To view real-time logs from your deployed Worker:

```bash
cd oak/cloud-relay
npx wrangler tail
```

This streams console output from the Worker, useful for debugging authentication failures, connection issues, or unexpected errors. Press `Ctrl+C` to stop.

## Removing a Deployment

To remove a deployed Worker entirely:

```bash
cd oak/cloud-relay
npx wrangler delete
```

This removes the Worker from Cloudflare. Any cloud agents configured to use it will receive errors. The local daemon detects the disconnection and stops attempting to reconnect.

To clean up the local scaffold as well:

```bash
rm -rf oak/cloud-relay
```
