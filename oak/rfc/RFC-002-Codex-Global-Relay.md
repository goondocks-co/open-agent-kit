# RFC-002: Global Codex Relay for Project-Aware CI Routing

**Author:** Chris Kirby + AI Draft  
**Date:** 2026-02-06  
**Status:** Draft  
**Tags:** codex, otel, notify, daemon, routing, proxy

---

## Summary

Codex can emit OpenTelemetry (OTEL) events and `notify` callbacks. OAK currently routes both to a project-specific daemon port, which is inconvenient when Codex configuration is global and per-project ports differ.

This RFC proposes a **global OAK relay** on a fixed local port (example: `38100`) that receives Codex OTEL + notify traffic and forwards each event to the correct project daemon.

Core idea:

1. Use `notify` payload `cwd` + `thread-id` as the authoritative thread-to-project mapping.
2. Buffer early OTEL events until mapping is known.
3. Resolve destination daemon port from OAK project port rules (`.oak/ci/daemon.port` > `oak/ci/daemon.port` > derived).

---

## Problem

Per-project daemon ports are correct for local isolation, but they force per-project Codex OTEL endpoint configuration. For users with many repos, global Codex config is preferred.

Today:

- OTEL endpoint in Codex config points to one port.
- OAK daemons are project-scoped and bind to different ports.
- `notify` runs at turn completion, so mapping arrives late relative to early OTEL events.

---

## Investigation Findings

### 1. Codex `notify` includes `cwd` (usable for routing)

Codex core serializes this payload:

- `type = "agent-turn-complete"`
- `thread-id`
- `turn-id`
- `cwd`
- `input-messages`
- `last-assistant-message`

Source:

- `codex-rs/core/src/hooks/user_notification.rs` (`AgentTurnComplete` includes `cwd`)

### 2. Codex OTEL does **not** include `cwd`/project path

Current Codex OTEL events include identifiers like:

- `event.name`
- `conversation.id`
- `model`
- `slug`
- `approval_policy`
- `sandbox_policy`
- `mcp_servers`

No project path/cwd attribute is emitted in the traced event payloads.

Source:

- `codex-rs/otel/src/traces/otel_manager.rs`

### 3. HTTP request origin is not enough

From relay HTTP request metadata, we can reliably get only network-level sender info (typically loopback IP + ephemeral source port). This is not a stable project identity. Headers are not guaranteed to include project/workspace identity.

### 4. OAK already has project-port resolution logic

OAK already resolves project daemon ports deterministically via project files and derivation rules. This can be reused by relay routing.

---

## Goals

- Allow a **single global Codex config** to work across multiple repos.
- Preserve project-isolated storage and daemon behavior.
- Avoid losing early-turn OTEL data before notify arrives.
- Keep behavior idempotent and safe on daemon restarts.

## Non-Goals

- Merging project daemons into one shared data store.
- Replacing per-project port assignment.
- Adding remote/networked routing beyond localhost.

---

## Proposed Architecture

### Components

1. **Relay Listener (global)**
   - Fixed localhost port (default candidate: `38100`).
   - Endpoints:
     - `POST /v1/logs` (OTEL)
     - `POST /api/oak/ci/notify` (notify)

2. **Thread Router**
   - Maintains mapping: `thread_id -> project_root`.
   - Populated from notify payload (`cwd`, `thread-id`).

3. **Event Buffer**
   - Stores OTEL events keyed by `thread_id` until mapping exists.
   - TTL + max-size bounded.
   - Flushes buffered OTEL events when mapping is learned.

4. **Project Daemon Resolver**
   - Reuses OAK `get_project_port(...)` behavior.
   - Ensures daemon is running before forward.

### Data Flow

1. Codex sends OTEL to relay.
2. Relay extracts `conversation.id` (thread/session key).
3. If thread mapped: forward immediately to project daemon.
4. If thread unmapped: buffer OTEL event.
5. Codex sends notify with `cwd` and `thread-id` at turn end.
6. Relay records mapping, flushes buffered OTEL events for that thread, forwards notify.

---

## Discovery Strategy

### Recommended: Mapping-first (no broad daemon scan)

Do not try to infer project from HTTP source or brute-force pinging many daemons for each event.

Instead:

- Wait for authoritative mapping from notify (`cwd` + `thread-id`).
- Then resolve and start target daemon using project-root-based port rules.

### Optional Enhancement: Local mapping cache

Persist recent `thread_id -> project_root` mappings in a small local cache to survive relay restarts and reduce warm-up drops.

---

## Handling the "notify arrives late" gap

Policy:

- Buffer OTEL events for unknown thread IDs.
- Bound with:
  - max events
  - max bytes
  - max age (TTL)
- On overflow/expiry, drop oldest and increment metrics/counters.

This preserves most of the turn while preventing unbounded memory growth.

---

## Failure Modes and Mitigations

1. **Notify never arrives**
   - Keep buffered OTEL until TTL, then drop with explicit log counters.

2. **Daemon not running for mapped project**
   - Start daemon on demand (same as existing notify path behavior).

3. **Project moved/renamed**
   - If `cwd` no longer exists, reject mapping and log clear diagnostic.

4. **Thread ID collision across long time windows**
   - Use TTL-limited mapping entries and periodic cleanup.

---

## Security Considerations

- Bind relay to loopback only.
- Reject non-localhost callers by default.
- Validate `cwd` path normalization before use.
- Avoid forwarding to arbitrary hosts; only local project daemons.

---

## Rollout Plan

1. **Phase 1 (MVP)**
   - Global relay process + mapping + bounded OTEL buffer.
   - Manual opt-in in OAK config.
2. **Phase 2**
   - Persistent mapping cache.
   - Relay health/status endpoint and diagnostics.
3. **Phase 3**
   - Tooling command to configure Codex global OTEL+notify target to relay automatically.

---

## Open Questions

1. Should relay run as part of each `oak ci start`, or as a separate singleton command (`oak ci relay start`)?
2. Should relay accept both `38100` fixed default and configurable override?
3. Should buffered OTEL be replayed in strict order with notify, or OTEL-first then notify passthrough?

---

## Recommendation

Proceed with a relay MVP using `notify` as authoritative project identity and OTEL buffering for early events.  
This is the most reliable path with current Codex signal availability and avoids fragile inference from HTTP source metadata.

