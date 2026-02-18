---
title: Cloudflare Setup
description: Create a free Cloudflare account and install the wrangler CLI for Cloud Relay deployment.
sidebar:
  order: 2
---

Cloud Relay runs on Cloudflare Workers. This guide walks through creating a free account and installing the `wrangler` CLI — the tool used to deploy and manage Workers.

## Create a Cloudflare Account

1. Go to [cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up)
2. Enter your email and create a password
3. Verify your email address

No credit card is required. The Workers free tier includes everything Cloud Relay needs.

## Install Wrangler

Wrangler is Cloudflare's CLI for managing Workers. You can use it via `npx` (no global install) or install it globally:

```bash
# Option 1: Use via npx (recommended — no global install needed)
npx wrangler --version

# Option 2: Global install
npm install -g wrangler
wrangler --version
```

:::tip
Using `npx wrangler` is the simplest approach — it always uses the latest version and doesn't require a global install. All commands in this documentation use `npx wrangler` for consistency.
:::

## Authenticate Wrangler

Wrangler needs access to your Cloudflare account to deploy Workers:

```bash
npx wrangler login
```

This opens your browser for an OAuth flow. Grant the requested permissions and return to the terminal. Wrangler stores credentials locally in `~/.wrangler/`.

Verify authentication:

```bash
npx wrangler whoami
```

You should see your account name and ID displayed.

### Permissions Granted

The `wrangler login` OAuth flow grants these permissions:

- **Workers Scripts** — Deploy and manage Worker code
- **Workers KV** — Read/write KV namespaces (not used by Cloud Relay, but part of the default scope)
- **Durable Objects** — Create and manage Durable Objects (used by Cloud Relay for WebSocket state)
- **Account Settings** — Read account metadata

These permissions are scoped to the Wrangler CLI on your machine. You can revoke them at any time from the Cloudflare dashboard under **My Profile > API Tokens**.

## Workers.dev Subdomain

Every Cloudflare account gets a free `*.workers.dev` subdomain. Your deployed Workers are accessible at:

```
https://<worker-name>.<your-subdomain>.workers.dev
```

For example, if your subdomain is `alice` and you name your Worker `oak-relay`, the URL would be:

```
https://oak-relay.alice.workers.dev
```

You can find or change your subdomain in the Cloudflare dashboard under **Workers & Pages > Overview**.

### Custom Domains (Optional)

If you have a domain on Cloudflare, you can route a custom domain to your Worker instead of using the `workers.dev` subdomain. This is entirely optional — the `workers.dev` URL works for all Cloud Relay functionality.

## Free Tier Limits

The Cloudflare Workers free tier provides generous limits for Cloud Relay:

| Resource | Free Limit | What It Means |
|----------|------------|---------------|
| **Worker requests** | 100,000/day | Each MCP tool call from a cloud agent is one request. Typical usage is 500-2,000/day. |
| **Worker CPU time** | 10ms/request | Cloud Relay uses ~2-5ms per request (routing only, no heavy computation). |
| **Durable Object requests** | 100,000/day | Each WebSocket message and HTTP relay is one DO request. Matches Worker request count. |
| **Durable Object storage** | 1 GB | Cloud Relay stores < 1 KB (connection state only). |
| **WebSocket messages** | Unlimited | All relay communication between daemon and Worker. |
| **Egress bandwidth** | Free | All outbound data transfer from Workers is free. |

For a typical developer workflow, free tier usage stays well under 5% of the daily limits.

## Verify Setup

You can verify your setup from the terminal or the dashboard.

**Terminal:**

```bash
# Check Node.js version (v18+ required)
node --version

# Check wrangler is available
npx wrangler --version

# Check authentication
npx wrangler whoami
```

All three commands should succeed without errors.

**Dashboard:**

Open the Oak CI dashboard and navigate to the **Cloud** page. The **Prerequisites** card at the bottom shows live checks for npm, wrangler, and authentication status — including your Cloudflare account name when authenticated.

## Next Steps

With your Cloudflare account and wrangler ready, proceed to **[Getting Started](/open-agent-kit/features/cloud-relay/getting-started/)** to deploy your first Cloud Relay.
