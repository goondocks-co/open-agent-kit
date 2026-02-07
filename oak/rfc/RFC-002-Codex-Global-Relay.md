# RFC-002: Global Codex Relay for Project-Aware CI Routing

**Author:** Chris Kirby + AI Refinements
**Date:** 2026-02-06
**Status:** Draft
**Tags:** codex, otel, notify, daemon, routing, proxy

---

## Summary

Codex can emit OpenTelemetry (OTEL) events and `notify` callbacks. OAK currently routes both to a project-specific daemon port, which is inconvenient when Codex configuration is global and per-project ports differ.

This RFC proposes a **global OAK relay** on a fixed local port (`38100`) that receives Codex OTEL + notify traffic and forwards each event to the correct project daemon.

Core idea:

1. Use `notify` payload `cwd` + `thread-id` as the authoritative thread-to-project mapping.
2. Buffer early OTEL events until mapping is known.
3. Resolve destination daemon port from OAK project port rules (`.oak/ci/daemon.port` > `oak/daemon.port` > derived).

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
- Verified in OAK: `AGENT_NOTIFY_FIELD_CWD` is defined in constants.

### 2. Codex OTEL does **not** include `cwd`/project path

Current Codex OTEL events include identifiers like `conversation.id` (mapped to `session_id` in OAK) but no project path/cwd attribute is emitted in the traced event payloads.

Source:

- `codex-rs/otel/src/traces/otel_manager.rs`

### 3. Port Conflict Potential

The current CI daemon port range is `37800-38799`. The proposed relay port `38100` falls within this range. To prevent a project from being assigned the relay port, OAK's port resolution logic must explicitly reserve/exclude it.

### 4. Lack of Global State Directory

OAK is currently project-centric. Implementing a persistent mapping cache requires establishing a standard global directory (e.g., `~/.oak/`).

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
   - Fixed localhost port: `38100` (Reserved in `manager.py`).
   - Endpoints:
     - `POST /v1/logs` (OTEL)
     - `POST /api/oak/ci/notify` (notify)
     - `GET /api/relay/status` (Diagnostics)

2. **Thread Router**
   - Maintains mapping: `thread_id -> project_root`.
   - Populated from notify payload (`cwd`, `thread-id`).
   - Persistent store: `~/.oak/ci/relay/mappings.db` (SQLite).

3. **Event Buffer**
   - Stores OTEL events keyed by `thread_id` until mapping exists.
   - TTL (default 5 min) + max-size (1000 events) bounded.
   - Replays buffered OTEL events *immediately before* forwarding the `notify` callback.

4. **Project Daemon Resolver**
   - Reuses OAK `get_project_port(...)` behavior.
   - Uses `DaemonManager.ensure_running()` to start target daemon if needed.

5. **Lifecycle Manager**
   - New command group: `oak ci relay [start|stop|status]`.
   - PID and logs stored in `~/.oak/ci/relay/`.

### Data Flow

1. Codex sends OTEL to relay.
2. Relay extracts `conversation.id` (thread/session key).
3. If thread mapped: forward immediately to project daemon.
4. If thread unmapped: buffer OTEL event.
5. Codex sends notify with `cwd` and `thread-id` at turn end.
6. Relay records mapping, flushes buffered OTEL events for that thread (in order), then forwards the notify callback.

---

## Discovery Strategy

### Recommended: Mapping-first (no broad daemon scan)

Do not try to infer project from HTTP source or brute-force pinging many daemons for each event.

Instead:

- Wait for authoritative mapping from notify (`cwd` + `thread-id`).
- Then resolve and start target daemon using project-root-based port rules.

### Local mapping cache

Persist recent `thread_id -> project_root` mappings in `~/.oak/ci/relay/mappings.db` to survive relay restarts and reduce warm-up drops. Entries should have a TTL (e.g., 24 hours).

---

## Handling the "notify arrives late" gap

Policy:

- Buffer OTEL events for unknown thread IDs.
- Bound with:
  - max events: 1000
  - max bytes: 10MB
  - max age (TTL): 5 minutes
- On overflow/expiry, drop oldest and increment metrics/counters visible in `/api/relay/status`.

---

## Failure Modes and Mitigations

1. **Notify never arrives**
   - Keep buffered OTEL until TTL (5 min), then drop with explicit log counters.

2. **Daemon not running for mapped project**
   - Start daemon on demand using `DaemonManager`.

3. **Project moved/renamed**
   - If `cwd` no longer exists, reject mapping and log clear diagnostic.

4. **Thread ID collision across long time windows**
   - Use TTL-limited mapping entries and periodic cleanup in the persistent store.

---

## Security Considerations

- Bind relay to loopback only (`127.0.0.1`).
- Reject non-localhost callers by default.
- Validate `cwd` path normalization and ensure it is a valid directory before use.
- Restricted forwarding: only to local ports resolved via OAK's internal logic.

---

## Rollout Plan

1. **Phase 1 (MVP)**
   - Global relay process + mapping + bounded OTEL buffer.
   - `oak ci relay` command group.
   - Reserve port `38100` in OAK core.
2. **Phase 2**
   - Persistent mapping cache in `~/.oak/`.
   - Relay health/status endpoint and diagnostics.
3. **Phase 3**
   - Tooling command (`oak ci relay setup`) to automatically update global `~/.codex/config.toml` to point to the relay.

---

## Open Questions (Answered)

1. **Should relay run as part of each `oak ci start`, or as a separate singleton?**
   - It should be a singleton managed by `oak ci relay [start|stop]`. `oak ci start` can optionally ensure it is running if configured.
2. **Should relay accept both `38100` fixed default and configurable override?**
   - Start with `38100` fixed but allow environment variable override (`OAK_RELAY_PORT`).
3. **Should buffered OTEL be replayed in strict order with notify?**
   - Yes, OTEL events must be replayed first, then notify passthrough, to ensure context is available before turn completion logic.

---

## Recommendation

Proceed with a relay MVP using `notify` as authoritative project identity and OTEL buffering for early events. This is the most reliable path with current Codex signal availability and avoids fragile inference from HTTP source metadata. Establishing a global OAK home directory for this purpose also paves the way for future global features.