---
title: Troubleshooting
description: Common issues and solutions when using Cloud Relay.
sidebar:
  order: 7
---

This page covers common issues you may encounter when setting up and using Cloud Relay, with solutions for each.

## Wrangler Issues

### "wrangler: command not found" or "npm not found"

Wrangler or npm is not installed or not in your PATH. The dashboard shows this in the Prerequisites card as a failed check.

**Solution:** Install Node.js (which includes npm), then install wrangler:

```bash
# Preferred: use via npx (no global install needed)
npx wrangler --version

# Or install globally
npm install -g wrangler
```

### "wrangler login" Opens Browser but Auth Fails

The OAuth flow didn't complete or the browser couldn't redirect back.

**Solution:**
1. Check that your browser is not blocking popups from `dash.cloudflare.com`
2. Try an incognito/private window
3. If behind a corporate proxy, try authenticating via API token instead:
   ```bash
   export CLOUDFLARE_API_TOKEN=your-api-token
   ```
   Generate an API token in the Cloudflare dashboard under **My Profile > API Tokens** with the **Edit Cloudflare Workers** template.

### "Wrangler is not authenticated"

The dashboard or CLI reports that wrangler is not authenticated with Cloudflare. This means `npx wrangler whoami` failed.

**Solution:**

```bash
wrangler login
```

Then click "Start Relay" again or re-run `oak ci cloud-init`. The auth check phase runs every time to ensure credentials are still valid.

## Deployment Issues

### "Worker deployment failed"

The `wrangler deploy` phase failed. The dashboard shows the raw wrangler output in a collapsible detail section.

**Common causes:**

**Account not verified:**
Cloudflare requires email verification before Workers can be deployed. Check your email for a verification link.

**Subdomain not set:**
New accounts need to choose a `*.workers.dev` subdomain. Go to **Workers & Pages > Overview** in the Cloudflare dashboard.

**Durable Object migration error:**
On first deploy, Wrangler creates a Durable Object migration. If this fails, ensure the scaffold is intact. Re-scaffold with:
```bash
oak ci cloud-init --force
```

### "npm install failed"

The npm install phase failed. Check the detail output in the dashboard for specific errors.

**Common causes:**
- **Network issues** — npm can't reach the registry
- **Permission errors** — the scaffold directory isn't writable
- **Corrupted node_modules** — delete and retry:
  ```bash
  rm -rf oak/cloud-relay/node_modules
  oak ci cloud-init
  ```

### "Deployment succeeded but could not detect Worker URL"

Wrangler deployed successfully but the output format was unexpected. The URL couldn't be parsed.

**Solution:** Check your Cloudflare dashboard for the Worker URL, then connect manually:

```bash
oak ci cloud-connect https://your-worker.your-subdomain.workers.dev
```

## Connection Issues

### "Connection Refused" or "Could not connect to Worker relay"

The daemon cannot reach the Worker URL.

**Checklist:**
1. Verify the Worker is deployed: `curl https://your-worker.workers.dev/health`
2. Check the URL is correct: `oak ci cloud-url`
3. Ensure your network allows outbound WebSocket connections (wss://)
4. Check that the daemon is running: `oak ci status`

### Instance Shows "Offline" in Cloud Status

The local daemon is not connected to the Worker. Cloud agents see this as the instance being unavailable.

**Causes and solutions:**

| Cause | Solution |
|-------|----------|
| Daemon not running | `oak ci start` |
| Daemon restarting | Wait for auto-reconnect (exponential backoff, up to 60s) |
| Network interruption | Connection auto-recovers when network returns |
| Token mismatch | Re-scaffold: `rm -rf oak/cloud-relay && oak ci cloud-init` |
| Worker not deployed | Click "Start Relay" or run `oak ci cloud-init` |

### WebSocket Disconnects Frequently

If the connection drops repeatedly:

1. **Check network stability** — Unstable networks cause frequent reconnects. The daemon uses exponential backoff and recovers automatically.
2. **Check daemon logs** for errors:
   ```bash
   tail -50 .oak/ci/daemon.log
   ```
3. **Check Worker logs** for server-side issues:
   ```bash
   cd oak/cloud-relay
   npx wrangler tail
   ```

## Authentication Issues

### "Token Invalid" or "Unauthorized"

The token presented does not match what the Worker expects.

**For relay_token (daemon to Worker):**
1. Check `.oak/config.yaml` has the correct `token` under `cloud_relay`
2. Re-scaffold to reset both sides: `rm -rf oak/cloud-relay && oak ci cloud-init`

**For agent_token (cloud agent to Worker):**
1. Verify the token in your cloud agent's MCP server configuration matches the one shown in the dashboard
2. Ensure the Authorization header format is `Bearer <token>` (with the space), or just the raw token
3. Re-scaffold to generate fresh tokens and update the agent config

### Token Lost

The `agent_token` is displayed in the dashboard (Cloud page, when connected) and stored in `.oak/config.yaml`. If you've lost it:

1. Check the dashboard's **Cloud** page — click the reveal button next to the agent token
2. Check `.oak/config.yaml` for the `agent_token` value
3. Check `oak/cloud-relay/wrangler.toml` for the token values
4. If all else fails, re-scaffold: `rm -rf oak/cloud-relay && oak ci cloud-init`

## Timeout Errors

### Cloud Agent Reports Timeout

MCP tool calls take too long and the cloud agent's HTTP request times out.

**Causes:**
- **Large codebase search** — Semantic search on very large codebases can be slow on first run. Subsequent searches use cached embeddings.
- **Network latency** — The request travels: cloud agent -> Worker -> WebSocket -> local daemon -> process -> WebSocket -> Worker -> cloud agent. Each hop adds latency.
- **Daemon under load** — If the local daemon is processing heavy background tasks (indexing, summarization), tool calls may be slower.

**Solutions:**
1. Ensure codebase indexing is complete before using cloud relay (`oak ci status`)
2. Keep the local daemon's workload reasonable — avoid triggering full re-indexes while using cloud relay
3. Check daemon logs for slow queries: `tail -f .oak/ci/daemon.log`

## Checking Logs

### Daemon Logs

The local daemon logs relay activity to `.oak/ci/daemon.log`:

```bash
# Recent cloud relay entries
tail -100 .oak/ci/daemon.log
```

Look for entries containing `cloud`, `relay`, or `websocket` for relay-specific logs.

### Worker Logs

Stream real-time logs from the deployed Worker:

```bash
cd oak/cloud-relay
npx wrangler tail
```

This shows all incoming requests, authentication results, and relay activity. Press `Ctrl+C` to stop.

## Getting Help

If you encounter an issue not covered here:

1. Check the [Oak CI Troubleshooting](/open-agent-kit/troubleshooting/) page for general daemon issues
2. Review daemon logs (`.oak/ci/daemon.log`) and Worker logs (`npx wrangler tail`) for error details
3. Open an issue on [GitHub](https://github.com/goondocks-co/open-agent-kit/issues) with the relevant log output
