# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Agent Governance sub-module with observability and optional enforcement — hook-level evaluation of tool calls against configurable rules (e.g., `no-destructive-bash`), audit event logging with session correlation, and deny-mode blocking for high-risk operations. Governance events are now included in team backup/restore for cross-machine consistency — [Implement CI governance sub-module with deny mechanism](http://localhost:38388/activity/sessions/6b834bea-d704-4c79-8657-8f4df1ee5292), [Add governance audit events to backup system](http://localhost:38388/activity/sessions/7858b8e5-204a-4366-a103-b7a78d108fb0)
- Session summary dedicated column — summaries migrated from `memory_observations` to `sessions.summary` column (schema v5→v6), improving query performance and eliminating duplicate embeddings in semantic search. Backup restore now backfills summaries from legacy observation format — [Migrate session summaries to dedicated column](http://localhost:38388/activity/sessions/81153f0c-1729-4fc8-a8ad-6a4d9b743311), [Fix session summary migration and display issues](http://localhost:38388/activity/sessions/d742f4d7-7007-494d-9229-dec8979b12f6)
- Inline session title editing with lineage indicators — session detail page now supports editable titles with a `title_manually_edited` flag to prevent LLM overwrites, plus visual indicators showing parent/child relationships in the session list — [Implement session title editing and lineage indicators](http://localhost:38388/activity/sessions/fee603dd-5009-4fc6-a270-c2cad3f62ac3)
- Cloud MCP Relay with one-click Cloudflare Workers deployment — enables remote MCP server access via WebSocket proxy with automatic worker scaffolding, Wrangler deployment, and in-browser connection status UI — [Implement Cloud MCP Relay with WebSocket proxy on Cloudflare Workers](http://localhost:38388/activity/sessions/442283b6-636c-4994-ad57-6bc941eba4b1), [Implement one-click Cloud MCP Relay deployment](http://localhost:38388/activity/sessions/31ca132b-7ce8-4494-995f-b8431d7196b5)
- Automated custom domain provisioning for Cloud Relay — users can now specify a base domain and Oak automatically generates a subdomain, configures `wrangler.toml` with a `[[routes]]` section, and lets Cloudflare handle DNS and SSL provisioning during deployment (domain zone must be in user's Cloudflare account) — [Implement automated custom domain provisioning for Cloud MCP Relay](http://localhost:38388/activity/sessions/6f574be5-0ab0-40cc-b90f-db430cbf566c), [Implement automated custom domain provisioning with Cloudflare](http://localhost:38388/activity/sessions/70337198-b5cb-44a4-ba4b-7166dc85622c)
- Dynamic session summarization with multi-model support — summaries now adapt to different model providers (Ollama, LM Studio, cloud APIs) with defensive JSON unwrapping to handle context window truncation — [Implement dynamic session summarization for multiple models](http://localhost:38388/activity/sessions/ecd780e8-5f8f-4e0e-a69e-61ecc8cabb19)
- Agent auto-start with daemon readiness polling — agents can now be configured to start automatically when the daemon becomes ready, with polling to detect daemon availability — [Configure Oak agent auto‑start and daemon readiness polling](http://localhost:38388/activity/sessions/fbc5cb52-096f-42f0-ba24-a961373b027c)
- Local Engineering Team Agent with four integrated tasks (build, test, lint, deploy) — unified local-first agent replaces multiple separate agent configurations with a single promptable interface and modal-based task selection — [Implement local Engineering Team Agent with four tasks](http://localhost:38388/activity/sessions/79e5ee7d-4734-4df4-815d-450491e5039a), [Refactor Engineering Agent into unified local-first agent and add prompt modal](http://localhost:38388/activity/sessions/fc959d78-24f0-4692-80b4-922332c0a704)
- User settings page with notification toggle — settings UI allows users to enable/disable desktop notifications for agent completions and other events — [Implement user settings page with notification toggle](http://localhost:38388/activity/sessions/812ec80c-7b1c-4827-8b62-c207879ffd17)
- Resolution event propagation across machines — resolution actions (resolve/supersede) are now persisted in a `resolution_events` table and included in backup/restore operations, ensuring team-wide consistency when observations are resolved — [Implement resolution event propagation and backup integration](http://localhost:38388/activity/sessions/1a06d53e-b53d-4b70-b6e8-bec42f461185), [Implement resolution_events propagation across machines via backup/restore](http://localhost:38388/activity/sessions/df8582bb-8845-4705-9f51-29c3bd495986)
- Context Engineering skill documentation and feature registration — new skill for prompt engineering and context optimization workflows — [Add Context Engineering skill documentation and feature registration](http://localhost:38388/activity/sessions/d3c39bf8-574f-49fc-8c95-2c8f87dedd20)
- Session-aware memory handling with UUIDs — memory submission now includes `sessionId` for improved traceability and efficient prompt handling — [Implement session‑aware memory handling with UUIDs](http://localhost:38388/activity/sessions/6a3a0f7b-871f-4a70-bae8-fa3341460159), [Add sessionId to memory handling for efficient prompt submission](http://localhost:38388/activity/sessions/92dfeea5-bdb1-4ed6-8a70-1d1096e8f014)
- Machine-specific source ID filters for background processing — queries now scope to the local machine's source ID, preventing cross-machine data leakage in multi-machine environments — [Add machine‑specific source ID filters to background processing queries](http://localhost:38388/activity/sessions/ec285403-65e3-4d7f-89fc-8941c10ca852)
- Clear orphan entries functionality in ChromaDB DevTools — UI now provides a dedicated button to identify and remove orphaned embeddings that lack corresponding SQLite records, preventing storage bloat from incomplete cleanup operations — [Add clear orphan entries functionality to ChromaDB DevTools](http://localhost:38388/activity/sessions/697b6645-fcc6-4ff4-b18c-72016c36fec0)
- Power state aware daemon behavior — daemon now scales background processing based on system activity with four states: ACTIVE (full processing), IDLE (maintenance only), SLEEP (minimal I/O), and DEEP_SLEEP (paused). This reduces resource consumption when the user stops coding, allowing macOS to enter proper sleep states. Background tasks like SQLite queries and backups now respect power state transitions — [Implement power state aware daemon behavior](http://localhost:38388/activity/sessions/01735ec6-438a-4950-8a57-4c630f170b24), [Debug idle resource consumption issue](http://localhost:38388/activity/sessions/618dc82e-46a4-48c3-b3a3-fcab14f5ffd5)
- Observation lifecycle management — observations now track status (`active`, `resolved`, `superseded`) with session-type awareness (`planning`, `investigation`, `implementation`, `mixed`), enabling agents to distinguish current knowledge from historical context and filter stale observations from context windows — [Implement observation lifecycle management system](http://localhost:38388/activity/sessions/cc6d1209-222c-4d32-9420-011876a7ee61)
- Personalized session summaries — LLM-generated summaries now use Git/GitHub usernames instead of generic "the user" references, improving searchability and attribution — [Fix date filtering and user identity issues in session summaries](http://localhost:38388/activity/sessions/49e246b5-ded7-483d-abc9-7de56e780caf)
- Memory-observation lineage tracking — observations now link back to their source memory, enabling bidirectional navigation between memories and the observations that created them — [Add memory-observation lineage support across codebase intelligence](http://localhost:38388/activity/sessions/fd23376c-0545-4a31-a433-1a2a5cdfb620)
- Session ID metadata for embedding search — summaries and memories now include `session_id` in embedding metadata, enabling filtered searches scoped to specific sessions — [Add session_id metadata for searchable summaries and memories](http://localhost:38388/activity/sessions/f6fd6830-e260-4603-bc29-41178a7da9b6), [Add sessionId to embedding metadata and database](http://localhost:38388/activity/sessions/4d46f5a6-a2dd-4e13-ae89-19d5c0b07c0d)
- Inline plan detection via response patterns — plans are now detected heuristically from assistant responses when explicit plan hooks are not available, improving plan capture coverage for agents without native plan support — [Add inline plan detection via response patterns](http://localhost:38388/activity/sessions/df16233a-9114-4b6e-a4e2-420e62cd2b47)
- Daemon version mismatch detection and restart UI — when the `oak` CLI is upgraded, the daemon now detects the version difference via a background check (every 60s), displays a banner in the web UI, and offers a one-click "Restart Daemon" button, eliminating manual `oak ci restart` calls — [Implement daemon version mismatch detection and restart UI](http://localhost:38388/activity/sessions/39e12dc7-e79a-40cf-bde2-b74442528f69)
- Self-healing stale installation check — daemon now detects when its package installation becomes stale (e.g., after `uv tool install` overwrites an editable install) and surfaces a warning in the UI, preventing silent failures from misaligned package paths — [Add self‑healing stale installation check to daemon](http://localhost:38388/activity/sessions/1b7f1e8f-2d46-46dc-9cdf-e987cceea56b)
- Self-healing daemon restart logic with watchdog — daemon now automatically restarts after detecting critical failures, with a watchdog process ensuring recovery from crashes — [Implement self‑healing daemon restart logic and watchdog](http://localhost:38388/activity/sessions/2041b3c1-c572-43e9-8c5b-adb79fd41ade)
- Project name displayed in daemon UI browser tab title for better multi-project disambiguation — [Add project name to daemon UI tab title](http://localhost:38388/activity/sessions/6f305703-4383-4f41-8bba-cafa08c2f0e3)
- Local-only hook configuration for all AI agents — hook files are now kept out of version control via `.gitignore` entries and `.local.json` variants, so contributors who clone a repo without Oak installed see no hook errors. A `hooks-local-only` migration applies the change on upgrade — [Configure local‑only GitHub hooks for Oak‑enabled agents](http://localhost:38388/activity/sessions/031fde6b-6250-4dc1-b705-52c454b75271)

### Changed

- Documentation site domain migrated from `oak.goondocks.co` to `openagentkit.app` — updated all domain references in Astro config, README, QUICKSTART, and issue templates — [Map all domain references for Astro docs migration](http://localhost:38388/activity/sessions/83a6665d-d7e5-4c70-85f8-17f5a4235efa), [Update domain references and fix backup restore logic](http://localhost:38388/activity/sessions/48b3ab26-e06c-44e4-9c86-a7ee72b11531)
- Activity detection logic refactored across 56 files — improved hook activity pattern recognition and file change detection strategies — [Refactor activity detection logic across 56 files](http://localhost:38388/activity/sessions/d83040f9-4bad-4b09-b3e2-dbf8ed2183aa)
- Agent architecture refactored to merge prompts into scheduler — agent prompts now flow through the unified scheduler interface rather than separate prompt handling paths, improving consistency and reducing code duplication — [Refactor agent architecture and merge prompts into scheduler](http://localhost:38388/activity/sessions/5c1e4018-1987-4f2d-a6de-a9e817a911ec)
- Obsolete `backend-python-expert` command removed from codebase intelligence feature — dead code cleanup reduces maintenance burden and clarifies the CLI surface — [Remove obsolete backend python expert command from codebase intelligence feature](http://localhost:38388/activity/sessions/2f76aa42-307c-41dc-89c8-fdfc899d9a56), [Remove obsolete backend-python-expert command](http://localhost:38388/activity/sessions/ebe33ad5-8ead-4bd4-8e49-dfd7795598d6)
- DevTools database operations refactored to use store layer — maintenance operations (VACUUM, orphan cleanup) now route through the unified store abstraction instead of raw SQL, improving consistency and testability — [Refactor devtools to use store layer for database operations](http://localhost:38388/activity/sessions/831215be-658e-430c-9077-3fc9e3937441)
- License updated to 2025-2026 date range with business name as copyright holder — [Update license copyright year and holder name](http://localhost:38388/activity/sessions/d01d958e-e24e-4f1a-a611-91e67f06aeba)
- Batch processing performance improved — batch sizes increased from 10 to 50 items per cycle with parallel processing, significantly reducing memory processing time — [Optimize batch processing and database performance](http://localhost:38388/activity/sessions/e54fa8e6-6ce9-4141-91e3-8ca5ca51c3dc)
- Codebase refactored into six parallel build streams for independent testing — core, daemon, indexing, memory, activity, and agents can now be tested and validated separately, reducing CI time and enabling targeted development — [Refactor OAK codebase into six parallel build streams for independent testing](http://localhost:38388/activity/sessions/cebab386-ae4e-4327-8840-15976114029b), [Refactor OAK codebase into six parallel work streams](http://localhost:38388/activity/sessions/666ef8df-666b-482b-a36b-44fa9d63826e)
- Built-in agent task YAMLs no longer copied into `oak/agents/` during installation — the registry now loads built-ins directly from the package, reducing installation footprint and preventing accidental overwrites of user customizations. A cleanup migration removes existing copies on upgrade — [Remove built‑in agent task copies and add cleanup migration](http://localhost:38388/activity/sessions/ea8917a0-aebb-4616-be07-14b5e7843e56), [Refactor installation to remove built‑in agent task copies](http://localhost:38388/activity/sessions/12a1a982-0d3a-401b-b9d0-d38083fafa85)
- `generate_schema_ref.py` relocated from installed skill directory to `src/open_agent_kit/features/codebase_intelligence/scripts/`, keeping the build-time script out of agent skill payloads and reducing installed footprint — [Refactor schema generation script placement to feature source tree](http://localhost:38388/activity/sessions/f0e6bfbe-cee4-431c-848b-10ad9929adb8), [Refactor generate_schema_ref.py relocation to centralized scripts folder](http://localhost:38388/activity/sessions/9e9f814a-1a6b-49ab-a299-ee6632f5b6e0)
- Hooks-reference documentation cleaned for end-user focus — removed Oak contributor sections and added a "not" section to clarify feature boundaries — [Update documentation with Oak‑not section and clean hooks reference](http://localhost:38388/activity/sessions/d46e5c83-ff36-4eea-a77c-ba8bbf9cb74d)

### Fixed

- Fix session lineage auto-linking after plan execution — child sessions now correctly link to parent when executing a plan, resolving orphaned session chains — [Fix session lineage auto-linking in Claude Code](http://localhost:38388/activity/sessions/d63793ec-bfac-4c6c-9230-90247badecd5)
- Fix Cursor plan capture detection — plan files created by Cursor are now properly detected and linked to sessions in the codebase intelligence system — [Fix Cursor plan capture detection in codebase intelligence](http://localhost:38388/activity/sessions/6e8cc386-a148-41a3-9c15-bc0d2bf75774)
- Fix governance hook event casing mismatch — `HOOK_EVENT_PRE_TOOL_USE` constant was kebab-case (`pre-tool-use`) but Claude Code sends PascalCase (`PreToolUse`), causing deny responses to never apply. Now normalizes both sides for comparison — [Implement CI governance sub-module with deny mechanism](http://localhost:38388/activity/sessions/6b834bea-d704-4c79-8657-8f4df1ee5292)
- Fix CLI help text listing `rfc` as a primary command when it's agent-only — help output now accurately reflects the command hierarchy with `oak ci` as the primary CI entrypoint — [Fix CLI help text accuracy and command separation](http://localhost:38388/activity/sessions/070bd34e-f98a-4ae7-96d0-62a259bd143d)
- Fix MCP server plan resolution and tool call handling — plans now show resolved state correctly during polling, and tool call descriptions are clearer for debugging — [Fix plan resolution and tool call handling in MCP server](http://localhost:38388/activity/sessions/399c6996-ffc6-4e91-b8fc-e07ca3639517)
- Fix "today" filter showing incorrect results due to timezone mismatch — date filtering now correctly handles timezone differences between server and client — [Fix date filtering and user identity issues in session summaries](http://localhost:38388/activity/sessions/49e246b5-ded7-483d-abc9-7de56e780caf)
- Fix VS Code Copilot hook crashes — centralized hook formatting and fixed schema validation errors that caused the Copilot integration to crash after recent refactors — [Fix VS Code Copilot crash by centralizing hook formatting](http://localhost:38388/activity/sessions/94f771fb-3afd-41f0-80d5-dbf739a0b146), [Fix VS Code Copilot schema crash after refactor](http://localhost:38388/activity/sessions/d6d3ab1f-2f9f-4b7b-9660-319397875362), [Fix undefined hook error in VS Code Co‑Pilot integration](http://localhost:38388/activity/sessions/70d43b82-ebfc-4f1f-aeb4-04a2e0890983)
- Fix early migration order to refresh agent list — migrations now run in correct order to ensure the agent list is refreshed before the upgrade pipeline processes it — [Fix early migration order to refresh agent list for upgrade pipeline](http://localhost:38388/activity/sessions/ef95084c-ad6b-4c97-9c4e-9d316b0dd9dd)
- Fix Oak daemon upgrade error handling — raw error messages are now hidden from users during upgrades, replaced with user-friendly messaging — [Fix Oak daemon upgrade error handling to hide raw errors](http://localhost:38388/activity/sessions/601316fd-3367-4a83-b12d-3f5b9a4f0953)
- Fix "Compact All" button leaving ChromaDB in locked state — the button now triggers a daemon restart after deleting the collection, ensuring the database is cleanly reopened in a fresh process context without manual intervention — [Fix Compact All button to restart daemon after deletion](http://localhost:38388/activity/sessions/de86fb00-f151-47b2-bbd4-43173fde5a07)
- Fix session summary title generation failing for non-reasoning models — the title extraction regex now handles models that don't emit chain-of-thought reasoning, preventing empty or malformed titles — [Fix session summary title generation for non‑reasoning models](http://localhost:38388/activity/sessions/67ff7cbb-5a62-4c90-af40-9057eb2111a3)
- Fix environment and dependency resolution issues affecting Agents SDK and Oak CLI installations — improved path handling and dependency isolation to prevent conflicts between editable installs and tool installs — [Fix environment and dependency issues for agents SDK and Oak CLI](http://localhost:38388/activity/sessions/9ad12915-99d4-4e32-8d55-902fa35c56d9)
- Fix Homebrew tap build failures and update installation documentation to reflect `brew install goondocks-co/oak/oak-ci` as the recommended macOS install method — [Fix Homebrew tap and update Oak CI installation docs](http://localhost:38388/activity/sessions/45cd3a6f-2589-440c-afa3-97fbf337a8a7)
- Fix daemon self-restart failing after Homebrew upgrade — `sys.executable` pointed to the old deleted Cellar path, causing `FileNotFoundError`. Now uses `/bin/sh -c "sleep N && oak ci restart"` which always resolves to the current version on `$PATH` — [Implement daemon version mismatch detection and recovery](http://localhost:38388/activity/sessions/2b06d520-1f5e-455a-9dd8-84f14348d627)
- Fix Homebrew formula PyPI CDN propagation race condition — `brew install` could fail if the PyPI simple index hadn't propagated the new version yet. Formula `post_install` now retries `pip install` 5 times with 30s backoff, and the tap workflow uses `pip download --no-deps` with 20 retries over 10 minutes — [Fix Homebrew tap and update Oak CI installation docs](http://localhost:38388/activity/sessions/45cd3a6f-2589-440c-afa3-97fbf337a8a7)

### Notes

> **Gotcha**: Governance hook event names use different casing across agents — Claude Code sends `PreToolUse` (PascalCase), but constants may be defined as `pre-tool-use` (kebab-case). The governance engine now normalizes all event names with `.lower().replace("-", "").replace("_", "")` to handle all variants.

> **Gotcha**: Session summaries were previously stored as `memory_observations` with `memory_type='session_summary'`. After the v5→v6 migration, they live in `sessions.summary`. Backup restore includes a backfill function (`_backfill_session_summaries_from_observations`) to handle legacy backup files that still use the old format.

> **Gotcha**: Governance audit events are stored in `governance_audit_events` and are now included in team backups. If restoring a backup from before governance was implemented, the audit table will be empty but functional.

> **Gotcha**: SQLite's VACUUM command cannot run within a transaction context — attempting to do so raises `OperationalError: cannot VACUUM from within a transaction`. DevTools maintenance operations now explicitly close any active transaction before running VACUUM.

> **Gotcha**: ChromaDB delete operations can fail silently and leave orphaned entries. The new "Clear Orphan Entries" button in DevTools identifies embeddings that lack corresponding SQLite records and removes them with retry logic to handle transient failures.

> **Gotcha**: The version mismatch detection writes a stamp file (`.oak/ci/cli_version`) only when the CLI runs, so it adds no overhead to normal operation. However, the `restartDaemon` API call must be awaited before updating the UI — otherwise stale data may be displayed.

> **Gotcha**: When automatic built-in task installation is disabled, any missing built-in task files will cause runtime errors if agents reference them. Ensure required tasks are present in `oak/agents/` before running the pipeline, or rely on the registry's built-in loader.

> **Gotcha**: The project name in the browser tab is sourced from `window.projectName` injected by the server. If this variable is missing or undefined, the title defaults to just the static suffix.

> **Gotcha**: After the `hooks-local-only` migration, hook config files (e.g., `.cursor/hooks.json`, `.windsurf/hooks.json`) are gitignored and exist only on machines with Oak installed. Hooks already degrade gracefully when files are absent, so contributors without Oak are unaffected — but developers must run `oak upgrade` to regenerate local hook files after a fresh clone.

> **Gotcha**: The daemon self-restart route must not use `sys.executable` because Homebrew upgrades delete the old Cellar path. If you see `FileNotFoundError` during restart, verify that the `oak` binary on `$PATH` points to the current version (`which oak`).

> **Gotcha**: The "Compact All" button in DevTools deletes the ChromaDB collection, but ChromaDB holds file locks that persist until the process exits. Without a daemon restart, subsequent re-indexing fails with database lock errors. The fix triggers an automatic restart after deletion to cleanly reopen the database.

> **Gotcha**: VS Code Copilot hook crashes were caused by schema validation running before hook formatting centralization. If you see hook errors after an upgrade, run `oak upgrade` to regenerate hook configurations with the corrected schema handling.

> **Gotcha**: Inline plan detection uses heuristic response patterns (e.g., numbered steps, "Implementation Plan" headers). False positives are possible for assistant responses that resemble plans but aren't. The detector favors recall over precision — plans are better captured twice than missed.

> **Gotcha**: Power state idle detection requires a fallback to `start_time` when `last_hook_activity` is None. Without this, the daemon stays in ACTIVE state forever if no hooks fire after startup (e.g., daemon starts and user walks away). The fix uses `last_activity = daemon_state.last_hook_activity or daemon_state.start_time`.

> **Gotcha**: Resolution events are stored separately from observations in the `resolution_events` table. When backing up/restoring, both tables must be synchronized — if resolution events are missing, observations may incorrectly appear as unresolved on the target machine.

> **Gotcha**: Machine-specific source ID filters in background processing queries prevent cross-machine data leakage but require the `source_machine_id` column to be populated. Observations created before this column existed will have NULL source IDs and may be filtered out unexpectedly.

> **Gotcha**: The `store_resolution_event` helper requires the observation ID and action status to be passed explicitly. Forgetting to provide these arguments leads to silent failures or incorrect event logging.

> **Gotcha**: Observation lifecycle status defaults to `active`. When querying memories via `ci_memories` or `ci_search`, use `status=active` for current knowledge and `include_resolved=true` only for historical documentation (e.g., changelogs). Resolved observations represent what *was* true, not what *is* true.

> **Gotcha**: Session origin types (`planning`, `investigation`, `implementation`, `mixed`) are inferred from file changes and code patterns. Planning-originated observations are more likely to become stale after implementation work completes — the auto-resolve system uses semantic similarity to detect when newer observations supersede older ones.

> **Gotcha**: The batch processing size (now 50 items per cycle) is a magic number that was refactored into a configurable constant. If processing appears slow, check that the batch size hasn't been inadvertently reduced, and ensure parallel processing is enabled to avoid database locking issues.

> **Gotcha**: Ollama often uses a smaller default context window than LM Studio for the same model, causing output format instructions at the end of long prompts to be truncated. This leads models to return JSON (e.g., `{"summary": [...]}`) instead of plain text. The `_unwrap_json_summary()` function in `summaries.py` handles this defensively.

> **Gotcha**: Cloud relay WebSocket connections require an active worker deployment to validate. The connection handler checks for worker availability before establishing the WebSocket, and errors are shown only when new actual errors occur rather than showing transient states.

> **Gotcha**: The `title_manually_edited` flag prevents LLM-generated titles from overwriting user edits. However, if a user clears the title field and saves, the flag remains set — the title won't auto-regenerate until the flag is explicitly cleared.

> **Gotcha**: Custom domain provisioning for Cloud Relay requires the domain zone to reside in the user's Cloudflare account. If the zone is managed elsewhere, automatic DNS/SSL provisioning will fail silently and the worker will fall back to the default `workers.dev` URL.

> **Gotcha**: UI state for saved custom domains is not persisted across page refreshes — users may need to re-save the domain after refreshing the Cloud Relay settings page.

## [1.0.3] - 2026-02-10

### Added

- Homebrew tap (`goondocks-co/oak`) for macOS installation with auto-generated formula and CI workflow to keep the formula in sync with PyPI releases — [Add Homebrew tap for oak‑ci with auto‑generated formula and CI sync](http://localhost:38388/activity/sessions/f39cb49c-b959-41e1-b7d3-321f8d8f8475)
- OAK-managed file tracking in `oak remove` — agent task YAMLs and `daemon.port` are now recorded via `StateService` and automatically cleaned up on removal, while preserving user content (`constitution.md`, RFCs, plans) and backup history — [Implement OAK‑managed file cleanup in oak remove](http://localhost:38388/activity/sessions/c8dc1dcb-4e07-4e0b-bcd7-261cf61b714b)

### Fixed

- Fix `oak/daemon.port` not created on fresh installs when no git remote is defined, causing daemon startup failures — [Fix daemon port creation and enforce Python version requirement](http://localhost:38388/activity/sessions/676be56f-00cf-4b96-8b63-539622365341)
- Fix `oak remove` leaving behind OAK-generated agent task files and `daemon.port`, requiring manual cleanup — [Fix oak remove to delete agent task files and daemon port](http://localhost:38388/activity/sessions/3a41f8b7-02fd-4d2d-950e-5b3cde0d6bd1)
- Enforce Python version requirement in install script and documentation — users installing via `pipx` or `uv` must now specify `--python` to avoid Homebrew defaulting to an unsupported interpreter (e.g., 3.14) — [Fix daemon port creation and enforce Python version requirement](http://localhost:38388/activity/sessions/676be56f-00cf-4b96-8b63-539622365341)

### Notes

> **Gotcha**: Homebrew formula for oak-ci uses `python -m venv` directly (not `virtualenv_create`) because Homebrew's helper passes `--without-pip`. Key details: (1) `venv.pip_install` uses `--no-deps` so deps won't install — the formula uses `system libexec/"bin/pip", "install"` instead, (2) `homebrew-pypi-poet` requires `setuptools<81` on Python 3.13, (3) `bin.install_symlink libexec/"bin/oak"` is needed to expose the binary.

> **Gotcha**: The removal logic now distinguishes between OAK-managed files (agent task YAMLs, `daemon.port`) and user-generated content. If custom files are placed in `oak/agents/` with names matching the `agent-*.yaml` pattern, they may be incorrectly treated as OAK-managed and removed during `oak remove`.

> **Gotcha**: If the `--python` flag is omitted when installing with `pipx` or `uv`, Oak may be installed against an unintended Python interpreter (e.g., Homebrew's Python 3.14), leading to runtime errors from incompatible dependencies like `chromadb` and `pydantic`.

## [1.0.2] - 2026-02-09

### Added

- Published `oak-ci` package to PyPI (v1.0.2) with cross-platform install script supporting macOS, Linux, and Windows PATH detection — [Publish oak-ci 1.0.2 and fix install script](http://localhost:38388/activity/sessions/44aa9400-db40-4db8-971e-5991cf0434b4)
- Concise feature request issue template for GitHub — [Add concise feature request template to repo](http://localhost:38388/activity/sessions/e6d294c4-3847-4b80-ad8c-4489287492b8)
- CI workflow with idempotent install scripts, mypy gating, and custom domain for GitHub Pages documentation — [Configure CI workflow and idempotent install scripts](http://localhost:38388/activity/sessions/019c3f47-583c-79b0-8b7b-9b794c797b5f)

### Changed

- Agent-kit templates refactored for consistent placeholders (`{{ agent_name }}`, `{{ skill_name }}`) with automatic injection during upgrades — [Refactor Oak agent‑kit templates for consistent placeholders and upgrade auto...](http://localhost:38388/activity/sessions/019c4361-2300-7c91-9a72-e41fe2c9fefa)
- Repository history cleaned and squashed for public open-source release — [Refactor repository history for clean public release](http://localhost:38388/activity/sessions/3d44092e-6cb0-433f-a611-d1a06ec6fcb7)
- `.oak/state.yaml` excluded from version control and leftover installer migrations removed for clean first-run experience — [Configure .oak/state.yaml exclusion and remove leftover migrations](http://localhost:38388/activity/sessions/1ec7b4a2-ef29-48db-873b-930c52c5cac2)
- Agent indexer configured to ignore build artifact directories — [Configure agent to ignore build artifact directories](http://localhost:38388/activity/sessions/16b837e8-90d1-4f38-b4f5-2c2c0d0721eb)

### Fixed

- Fix GitHub Pages broken links, `baseurl` configuration, and hard-coded documentation URLs across README, QUICKSTART, and issue templates — [Fix GitHub Pages links, update baseurl, and correct documentation URLs](http://localhost:38388/activity/sessions/248550ba-3db2-4a40-a4f5-fcf4c0235974)
- Fix install script failing to add agent binary to PATH on macOS due to incorrect shell detection logic — [Publish oak-ci 1.0.2 and fix install script](http://localhost:38388/activity/sessions/44aa9400-db40-4db8-971e-5991cf0434b4)

### Improved

- Daemon UI TaskList CPU usage reduced from ~10% to ~2% idle via `React.memo`, `useCallback`, debounced search, and batched API requests — [Refactor TaskList to Reduce CPU Usage in Oak Daemon UI](http://localhost:38388/activity/sessions/cdd818d1-75e4-48ee-9d48-2f59af2dfe53)
- Test suite audited: stale imports removed, test-to-source mapping updated, orphan tests flagged — [Debug test suite audit and stale import cleanup](http://localhost:38388/activity/sessions/c89831a0-e4af-4f79-b8fb-99e6ccea904b)

### Notes

> **Gotcha**: `.oak/state.yaml` tracks applied migration names. If migrations are removed from the codebase but their names remain in state.yaml, the migration runner may attempt to reference non-existent modules, causing `ImportError` or silent failures during startup. After a clean release, ensure state.yaml is reset or excluded from version control.

> **Gotcha**: The install script must handle both user-local and system installations. On macOS, `~/.local/bin` may not be on PATH by default — the installer now appends it to the appropriate shell profile (`.zshrc`, `.bash_profile`), but users with custom shell setups should verify manually.

> **Gotcha**: GitHub issue templates must be placed in `.github/ISSUE_TEMPLATE/` with the `.yml` extension. A missing or misnamed file will silently not appear in the issue creation UI.

## [Previous] - pre-1.0.2

### Added

- Token-based authentication for daemon API and UI with file-backed secrets — [Implement token‑based authentication for API and UI](http://localhost:38388/activity/sessions/b172c7fd-12d6-463b-a540-9b676a173992)
- Automatic backup fallback with configurable interval and UI countdown timer — [Implement automatic backup fallback and UI timer update](http://localhost:38388/activity/sessions/dc927025-655c-4ee0-88c3-8b56a5a8d7e6)
- Unified backup system with user-controlled settings and pre-upgrade hooks — [Configure unified backup system with user‑controlled settings](http://localhost:38388/activity/sessions/96b119d1-819c-4ac0-eed6c53ceb8c)
- Refresh button on Activity plans page with lightweight backend logic — [Add Refresh button to Activity plans page with lightweight backend logic](http://localhost:38388/activity/sessions/5d7633af-e6d5-4e1a-b0b5-adf05d334e29)
- Security hardening roadmap for CI daemon API — [Configure security hardening roadmap for CI daemon API](http://localhost:38388/activity/sessions/b22106f0-bf39-45ec-be1c-414a6d3e60c9)
- `docs-site-sync` agent for Astro documentation build and accessibility validation — [Implement docs-site-sync agent for Astro build and accessibility](http://localhost:38388/activity/sessions/3336230c-6da2-46f3-84ed-00a86c6fcaa3)
- Machine-specific config overlay for Oak CLI with per-host settings — [Implement machine‑specific config overlay for Oak CLI](http://localhost:38388/activity/sessions/f0773bf2-f976-4c75-b306-f3245c90846c)
- Fresh install cleanup logic in migration framework — [Refactor migration framework for fresh install cleanup](http://localhost:38388/activity/sessions/a228c691-9fbc-4ea9-b3b8-9242941eb271)
- Debug tooling for analysis agent build vs upgrade generation workflow — [Debug analysis agent build versus upgrade generation process](http://localhost:38388/activity/sessions/c35d4c25-9567-428d-aef6-8c1f3f231f47)
- Analysis skill for querying Oak CI databases with auto-generated schema references — [Implement analysis skill for Oak CI database queries](http://localhost:38388/activity/sessions/258f9a72-bc62-4c2a-be19-434afcb67492)
- Scheduled backup agent with UI controls for automated CI data protection — [Implement scheduled backup agent with UI controls](http://localhost:38388/activity/sessions/7c4c1f44-e015-46ce-9f6a-b88e24af5a71)
- Root check and daemon cleanup logic to `oak upgrade` command — [Add root check and daemon cleanup to Oak upgrade command](http://localhost:38388/activity/sessions/e66bd091-604e-4f27-927d-d132cb88ac3f)
- CI/CD pipelines and packaging strategy for PyPI release — [Configure CI/CD Pipelines and Packaging Strategy for PyPI Release](http://localhost:38388/activity/sessions/8011e851-634f-46fd-83ca-8796a18c7b3a)
- Machine ID injection across codebase for multi-machine backup disambiguation — [Refactor machine ID injection across codebase](http://localhost:38388/activity/sessions/0de307dc-8600-4c21-bc13-15b533743738)
- Pluggable tunnel sharing for CI daemon with Cloudflare and ngrok providers — [Implement pluggable tunnel abstraction for Oak CI sharing](http://localhost:38388/activity/sessions/b9ea2c92-def1-4e29-894b-25096c2a872c)
- Tunnel configuration UI and sharing help documentation on the Team page — [Add tunnel configuration UI and help docs](http://localhost:38388/activity/sessions/e23391f6-976e-4316-bd16-1ecafb7e26c9)
- Configurable CI backup directory via `OAK_CI_BACKUP_DIR` environment variable — [Configure CI backup directory via environment variable](http://localhost:38388/activity/sessions/13eb1949-dc1a-4105-82ae-f45e69449808)
- `transcript_path` column on sessions for transcript recovery and orphan detection — [Add transcript_file_id column to sessions for recovery](http://localhost:38388/activity/sessions/9ea4399f-779d-41c1-8f5a-ea5914b1dbb2)
- "Complete Session" button on session detail page for manual session completion — [Fix related session links and modal double‑click bug](http://localhost:38388/activity/sessions/cec09d81-d81b-4d79-981f-2d24ecdd2034)
- Database-backed agent schedules with UI management — [Implement database-backed schedules and UI](http://localhost:38388/activity/sessions/a60436e4-9674-4eda-b428-eb3fb6f5da5d)
- Quick-access panel in daemon UI for CLI agent commands — [Configure daemon UI quick‑access panel for CLI agents](http://localhost:38388/activity/sessions/25db97fd-e4a0-41a8-b30a-0fc858699bed)
- Generic agent summary hook with Markdown rendering support — [Implement generic agent summary hook and Markdown rendering](http://localhost:38388/activity/sessions/3a594cc8-1f9a-475a-8062-d1640bbffe50)
- OTLP logging integration for Codex agent — [Implement OTLP logging for Codex integration](http://localhost:38388/activity/sessions/1bf90f3a-9458-4ab5-b297-08cad86473a0)
- Comprehensive Claude Agent SDK documentation covering Ollama and LM Studio local model integration — [Add comprehensive Claude Agent SDK documentation and UI refresh](http://localhost:38388/activity/sessions/35f4f337-2e86-4452-81eb-cb0065f61f76)
- Token usage tracking in executor for cost optimization and resource monitoring — [Audit and outline Claude Agent SDK improvements](http://localhost:38388/activity/sessions/587901c4-7ede-4ab4-ac4c-354954c44c0f)
- OTEL (OpenTelemetry) support with dynamic notify configuration in Oak daemon — [Configure OTEL support and dynamic notify in Oak daemon](http://localhost:38388/activity/sessions/019c2431-0b1a-7023-909b-7c6f7017008d)
- Session summary extraction from transcripts on session stop — [Implement daemon summary extraction for session stop](http://localhost:38388/activity/sessions/e6adaa12-a72c-4fdd-b02d-d34b373213ff)
- OTLP telemetry integration for Codex agent — [Implement OTLP telemetry integration for Codex](http://localhost:38388/activity/sessions/76bc1091-d518-4310-94af-9f6d88392dc4)
- Session change summary logging in daemon — [Update daemon to log session change summaries](http://localhost:38388/activity/sessions/2347a9f5-94d0-4048-9f7f-b1f266861105)
- Dynamic project root discovery for documentation agent tasks — [Implement dynamic project root discovery for documentation tasks](http://localhost:38388/activity/sessions/33cb3952-8095-4f20-9e14-99136f077276)
- `oak ci sync` command for daemon and backup alignment — [Implement oak ci sync for daemon and backup alignment](http://localhost:38388/activity/sessions/2cd610d5-263e-4a11-a170-29ea912baeb4)
- Activity backup and health monitoring via `oak ci sync` — [Update oak ci sync for activity backup and health](http://localhost:38388/activity/sessions/0f87078c-26ce-46a0-a268-d074edadf762)
- Upgrade logic for built-in task templates with stable identifier support — [Implement upgrade logic for built‑in task templates](http://localhost:38388/activity/sessions/73094f41-9caa-4c8b-b2ad-5594e21f49b3)
- Filter chips and context indicator for daemon log viewer — [Add filter chips and context indicator to daemon log viewer](http://localhost:38388/activity/sessions/735f34fd-3899-437e-848f-e279228138dd)
- Minimum activity check before generating session titles — [Add minimum activity check before generating session titles](http://localhost:38388/activity/sessions/a812c6a9-27ad-4893-b5ae-17c25f17160e)
- Safe reset all processing state with confirmation dialog — [Implement safe reset all processing state with confirmation](http://localhost:38388/activity/sessions/16d4bd63-87a7-4fc9-88a1-f85fcbc3be4c)
- Python, JavaScript, and TypeScript language support for Oak — [Add Python, JavaScript, TypeScript support to Oak](http://localhost:38388/activity/sessions/73b2cf21-4907-44a9-b646-6bf9d231d23c)
- Row highlight for memory page search results — [Add row highlight for memory page search results](http://localhost:38388/activity/sessions/1076e1bf-b40b-4a19-b733-e2834ddf44dd)
- Collapsible left navigation and pause-scroll logs — [Implement collapsible left navigation and pause‑scroll logs](http://localhost:38388/activity/sessions/d19a3bb8-4b47-4a7a-9ed0-9bb74f7275e6)
- Watchdog timeout for Cloud Agent SDK — [Implement watchdog timeout for Cloud Agent SDK](http://localhost:38388/activity/sessions/9286b1bb-f34c-4911-9d91-e8e2e502d2e9)
- Dynamic agent discovery in Daemon UI — [Configure Daemon UI for Dynamic Agent Discovery](http://localhost:38388/activity/sessions/1ae65963-597b-48fb-ae99-8759116bbdee)
- OpenCode agent integration with CI plugin support — [Add OpenCode agent integration with CI plugin and cleanup](http://localhost:38388/activity/sessions/ca926b8e-eeae-400e-b36f-ace34200ec29)
- Session search endpoint and UI integration for finding sessions — [Implement session search endpoint and UI integration](http://localhost:38388/activity/sessions/4c64eaea-e383-4d26-b914-754b7dab937f)
- User-driven session linking with embedding-based suggestions — [Implement user‑driven session linking with embeddings](http://localhost:38388/activity/sessions/d8fb4448-546d-4cbb-9b86-dd6373d2e6c3)
- Skills subcommand and upgrade detection for Gemini agent — [Add skills subcommand and upgrade detection for Gemini](http://localhost:38388/activity/sessions/838216f8-c53b-40eb-8f26-b071e7f6c0e2)
- Cross-platform hook installation helper for consistent setup — [Implement cross‑platform hook installation helper](http://localhost:38388/activity/sessions/6eefb292-86e2-4f17-934f-90559869a737)
- Deterministic CI daemon port derived from git remote URL — [Implement deterministic CI daemon port via git remote URL](http://localhost:38388/activity/sessions/f58cca10-dd47-494c-8aa1-0bc00de74815)
- Privacy-preserving CI backup identifier using hashed paths — [Implement privacy-preserving CI backup identifier](http://localhost:38388/activity/sessions/2fbfc11c-dcb8-42f4-99b7-854685c6dae6)
- Persistent SQLite-backed agent run history with separate UI tabs for history and configuration — [Implement SQLite run history and UI tabs](http://localhost:38388/activity/sessions/08078e63-bd10-4305-8c14-e699679259e0)
- Reusable Activity component for the daemon UI, improving consistency across different views — [Refactor daemon UI and add reusable Activity component](http://localhost:38388/activity/sessions/cf7f051a-3259-48c3-ab21-4ea8658f4c2f)
- "Reprocess Observations" button with hash recompute functionality for memory management — [Add Reprocess Observations Button and Hash Recompute](http://localhost:38388/activity/sessions/e765187d-5f62-4e26-87fa-4f7605e2cd7b)
- Memory threshold strategy and re-processing plan for better memory management — [Implement memory threshold strategy and re-processing plan](http://localhost:38388/activity/sessions/0a3c6a29-341f-43ac-848e-0628b7d6e712)
- Session linking and auto memory observation creation for improved traceability — [Implement session linking and auto memory observation creation](http://localhost:38388/activity/sessions/7d914c67-f0b5-4a8f-a10d-650e2982e8d5)
- Codebase intelligence architecture and roadmap planning — [Plan codebase intelligence architecture and roadmap](http://localhost:38388/activity/sessions/f3283f87-2705-422e-a4ec-f692a2f88282)

### Changed

- Documentation Agent refactored to split root files and handle per-directory documentation separately — [Refactor documentation agent to split root files](http://localhost:38388/activity/sessions/1edaa563-6d6e-449a-8ad4-bc6e11ed106f)
- Open Agent Kit skills consolidated into two primary skills (oak and oak-ci) for simpler installation — [Refactor Open Agent Kit into Two Consolidated Skills](http://localhost:38388/activity/sessions/482c8fee-8da0-42cc-9fa6-1f10c2d669b9)
- Backup system redesigned with 3 unified functions (`create_backup()`, `restore_backup()`, `restore_all()`) replacing 4+ code paths — [Add backup/restore feature with new CLI commands](http://localhost:38388/activity/sessions/da0ef20a-b383-4b33-bbe5-4ae08e4b82a0)
- Oak constants refactored to align with flattened directory structure (`oak/` instead of `oak/ci/`) — [Refactor Oak constants to align with flattened directory structure](http://localhost:38388/activity/sessions/f9a71f9f-6c5c-4346-a373-6b9fc2ee6b4a)
- Documentation updated: agents guide, CI models reference, and lifecycle diagrams — [Update Oak documentation: agents, CI models, lifecycle diagrams](http://localhost:38388/activity/sessions/bc023bb9-bae5-4724-9848-1a4f0ad8f061)
- Stale agent capability data removed from configuration — [Refactor config to remove stale agent capability data](http://localhost:38388/activity/sessions/0558da05-c9c6-4014-9322-4ce9468968e6)
- Documentation site migrated to Starlight with updated Makefile and RFC-001 — [Update Oak docs: Starlight site, Makefile, and RFC‑001](http://localhost:38388/activity/sessions/dc540324-197d-4383-ae85-cfb3839aca62)
- Upgrade detection rewritten to manifest-driven hook checks supporting plugin, OTEL, and JSON hook types — [Refactor upgrade detection to manifest‑driven hook checks](http://localhost:38388/activity/sessions/18b1a6ca-4996-41aa-83e2-b827749b3123)
- Tunnel code refactored to eliminate magic literals — [Audit tunnel code for magic literals](http://localhost:38388/activity/sessions/ses_3ceaa4ad5ffeX8YFHfrA9obTc1)
- Refactored terminology from "Instance" to "Task" across codebase for clarity — [Refactor terminology from Instance to Task across codebase](http://localhost:38388/activity/sessions/d7dff207-6683-4fa3-8b27-7b8ff5ef6b18)
- Agent schedules now persisted to database instead of in-memory storage — [Update agent schedules to database persistence](http://localhost:38388/activity/sessions/5b1131f2-d55b-487c-8f8d-b6b5fb83915c)
- Makefile refactored to remove `.venv` dependency for cleaner builds — [Refactor Makefile to remove .venv dependency](http://localhost:38388/activity/sessions/217e9395-812c-4d66-9229-4842ac7dff1b)
- Refactor Agent Instance to Configuration across UI and API — [Refactor Agent Instance to Configuration across UI and API](http://localhost:38388/activity/sessions/9017876a-5cab-4c1c-b5da-89f97cd24ca0)
- Configure plan capture workflow for Claude sessions — [Configure plan capture workflow for Claude sessions](http://localhost:38388/activity/sessions/96d99f2a-0e0f-449d-b3b3-ccd584f944a7)
- Removed unused issue provider functionality — [Refactor codebase: Remove unused issue provider](http://localhost:38388/activity/sessions/479bf687-46dd-4366-a1d6-b7d8163d7396)
- Enabled all CI features by default in Oak — [Refactor Oak to enable all CI features by default](http://localhost:38388/activity/sessions/d284e22a-f111-4439-b5fc-50adc873afff)
- Refactored agent hook installation to manifest-driven approach — [Refactor agent hook installation to manifest‑driven approach](http://localhost:38388/activity/sessions/23385f20-190f-4927-a703-a67a8dbadafc)
- Refactored MCP server installation to cross-platform Python API — [Refactor MCP server installation to cross‑platform Python API](http://localhost:38388/activity/sessions/c33978ff-d0dc-486c-96b1-64f9fe83cfb2)
- Refactored scheduling system to use cron YAML instead of saved_tasks — [Refactor scheduling system: remove saved_tasks and add cron YAML](http://localhost:38388/activity/sessions/e2eebc11-d5d5-4ef0-a986-152ec97fb577)
- Refactored Oak session handling to write directly to database — [Refactor Oak session handling to direct DB writes](http://localhost:38388/activity/sessions/e45f0867-78f1-435e-85bf-b6452b46c921)
- Refactored manifest to isolate CI settings and add plan hooks — [Refactor manifest to isolate CI settings and add plan hooks](http://localhost:38388/activity/sessions/a0e327fb-2101-4085-853b-e9bc36710e07)
- Moved CI history backups into `oak/ci/history` directory — [Refactor CI history backups into oak/ci/history directory](http://localhost:38388/activity/sessions/71bf753a-061f-4bc6-86ff-4cfa9a5cee78)
- Refactored session titles and summary generation logic for better readability — [Refactor session titles and summary generation logic](http://localhost:38388/activity/sessions/34602abe-5553-431a-a569-22b454afb9ee)
- Updated daemon and dashboard session sorting to show latest activity first — [Update daemon and dashboard session sorting to latest activity](http://localhost:38388/activity/sessions/5486fa06-43a5-4056-b488-128038d2dcd5)
- Session lineage card now collapsible with lint cleanup — [Update session lineage card collapsable behavior and lint cleanup](http://localhost:38388/activity/sessions/49b6ce9f-0425-4eb7-ae98-8a7bc5380b26)
- Adjusted agent timeouts and fixed stale hook configuration — [Fix stale hook configuration and adjust agent timeouts](http://localhost:38388/activity/sessions/f0d6a9a7-13b5-4464-bb09-c5c98070cb30)

### Fixed

- Fixed MCP server resilience to daemon restarts with token refresh, guard reset, and 3-attempt retry loop — [Debug CI daemon API hook integration and auth headers](http://localhost:38388/activity/sessions/09493b1b-9ad1-4572-9504-532d28fc6973)
- Fixed UI agent resume button not appearing for CodeX sessions after model name format change to `GPT-5.3/codex` — [Fix UI agent bug and add Gemini resume CLI command](http://localhost:38388/activity/sessions/019c3e4d-e68d-7861-abca-4488873b55dd)
- Fixed Gemini CLI not recognizing `resume` command with space-dash-space variant — [Fix UI agent bug and add Gemini resume CLI command](http://localhost:38388/activity/sessions/019c3e4d-e68d-7861-abca-4488873b55dd)
- Fixed `/backup/last` endpoint returning empty 200 instead of 404 when no backup exists
- Fixed React error #310 in SessionDetail.tsx caused by hooks called after early returns
- Fixed MCP server 401 errors by adding daemon token file reading and Bearer header injection
- Fixed Windsurf agent freeze caused by `show_output` hooks blocking event loop — [Fix Windsurf agent freeze by removing show_output hooks](http://localhost:38388/activity/sessions/ed8ccfe1-46d2-4022-8265-72507c8ac013)
- Fixed ChromaDB session cleanup leaving orphaned embeddings after SQLite deletion — [Add cleanup logic for embedded ChromaDB sessions](http://localhost:38388/activity/sessions/17f9aef8-9615-4631-ad69-c752d3b210e5)
- Fixed `/devtools/compact` endpoint raising `NameError` due to undefined variable reference — [Debug daemon devtools failure after corrupted state cleanup](http://localhost:38388/activity/sessions/0e751f02-2f15-461f-bb54-6b80053e0d91)
- Fixed built-in Oak tasks not flagged as `is_builtin` in agent registry, causing incorrect UI display
- Fixed `prompt_batches` table missing `created_at` column causing query failures
- Fixed cascade assistant infinite loop when `lastSelectedCascadeModel` field is empty in Windsurf settings
- Fixed activity routes missing from FastAPI application causing 404 errors on `/activity/...` endpoints
- Fixed related session links not navigating in daemon UI and link-session modal requiring double-click — [Fix related session links and modal double‑click bug](http://localhost:38388/activity/sessions/cec09d81-d81b-4d79-981f-2d24ecdd2034)
- Fixed sharing configuration placed on wrong page and stabilized flaky async tests — [Fix sharing configuration placement and stabilize test suite](http://localhost:38388/activity/sessions/6ea3f1e3-ec78-4739-a803-00500f8b4e3d)
- Fixed `uv tool install` silently destroying editable installs by detecting PEP 610 `direct_url.json` and conditionally passing `-e` — [Configure CI backup directory via environment variable](http://localhost:38388/activity/sessions/13eb1949-dc1a-4105-82ae-f45e69449808)
- Fixed missing `.oak/agents/` directory after `oak init` causing downstream failures — [Fix missing agents directory after oak init](http://localhost:38388/activity/sessions/f1573859-be5a-4016-8bb9-37005f3cca11)
- Fixed `hooks.py` using `Path.cwd()` instead of project root, causing silent data loss when Claude Code changes working directory — see [`hooks.py`](src/open_agent_kit/commands/ci/hooks.py)
- Fixed `get_backup_dir` resolving relative to cwd instead of project root, causing misplaced backups in tests — see [`backup.py`](src/open_agent_kit/features/codebase_intelligence/activity/store/backup.py)
- Fixed session schema drift: SQL queries referencing renamed `sessions.session_id` and removed `started_at_epoch` columns — see [`sessions.py`](src/open_agent_kit/features/codebase_intelligence/activity/store/sessions.py)
- Fixed `SessionLineage` query running when `sessionId` is undefined after refactor removed `enabled` guard — see [`SessionLineage`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/)
- Renamed agent tasks now correctly installed during upgrade (name-based lookup replaced with stable identifiers) — [Implement upgrade logic for built‑in task templates](http://localhost:38388/activity/sessions/73094f41-9caa-4c8b-b2ad-5594e21f49b3)
- Fixed Vite configuration causing UI build failure — [Configure minimal Vite config to fix UI build](http://localhost:38388/activity/sessions/c0457435-38b1-4d48-bd53-af22a6ac08ae)
- Fixed UI build error related to dependency injection setup — [Fix UI build error and outline DI plan](http://localhost:38388/activity/sessions/461a8c4d-b772-4f41-8075-f4dd993ea874)
- Fixed filter chips in Logs page clearing entire log list instead of filtering — see [`Logs.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Logs.tsx)
- Fixed `indexStats` variable not defined in Dashboard.tsx causing TypeScript build failure — see [`Dashboard.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Dashboard.tsx)
- Fixed session summary not rendering as Markdown in MemoriesList component — see [`MemoriesList.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/data/MemoriesList.tsx)
- Fixed DevTools maintenance card layout wrapping below header instead of beside it — see [`DevTools.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/DevTools.tsx)
- Fixed Daemon UI bugs and added developer tools — [Fix Daemon UI bugs and add developer tools](http://localhost:38388/activity/sessions/969a6fa5-114f-4340-a403-b3ebed248d48)
- Fixed failing hook import in CI test suite — [Debug failing hook import in CI test suite](http://localhost:38388/activity/sessions/315e7240-ee03-49be-8320-4c403d54e0c7)
- Fixed plan capture workflow for Claude sessions — [Configure plan capture workflow for Claude sessions](http://localhost:38388/activity/sessions/96d99f2a-0e0f-449d-b3b3-ccd584f944a7)
- Fixed MCP upgrade dry run inconsistencies — [Debug MCP Upgrade Dry Run Inconsistencies](http://localhost:38388/activity/sessions/669382b1-4f57-45f0-b833-b55611e53b0c)
- Fixed Claude code causing 100% CPU hang — [Debug Claude code causing 100% CPU hang](http://localhost:38388/activity/sessions/5cc04051-d337-4b53-8156-a2756138cead)
- Fixed agent executor behavior after refactor — [Fix agent executor behavior after refactor](http://localhost:38388/activity/sessions/8adf6c3f-5032-41d1-9e5e-3e873241287b)
- Fixed CLI crash from `AttributeError: 'list' object has no attribute 'items'` caused by `registered_groups` being overwritten with a list during refactoring
- Fixed failing test `test_plan_service.py::test_create_plan_from_issue` by removing call to non-existent issue provider
- Fixed system health card truncating summarization model name by replacing hard-coded slice with CSS `text-overflow: ellipsis`
- Fixed dashboard displaying incorrect session count by using `count_sessions()` instead of recent sessions count
- Fixed orphaned memory entries by adding cascade delete for dependent observations
- Fixed upgrade service leaving empty parent directories after settings file deletion
- Fixed orphan-recovery logic not detecting plans due to `PROMPT_SOURCE_PLAN` constant mismatch
- Fixed CI backup filename leaking full path by using privacy-preserving hash — [Fix CI backup filename privacy bug](http://localhost:38388/activity/sessions/414c1ebe-fff6-40f2-876c-9a7df59ed469)
- Fixed agent executor crash on unexpected errors by adding broad exception handling — see [`executor.py`](src/open_agent_kit/features/codebase_intelligence/agents/executor.py)
- Fixed CI process hanging when MCP configuration is missing by adding defensive check and fallback — see [`.mcp.json`](.cursor/mcp.json)
- Fixed macOS hook hang caused by missing `timeout` utility by using portable alternative — see [`oak-ci-hook.sh`](.claude/hooks/oak-ci-hook.sh)
- Fixed startup indexer globbing entire home directory due to unescaped path characters
- Fixed daemon startup failure caused by `sleep` receiving non-numeric argument
- Fixed TypeScript build error from missing `Switch` component export — see [`Schedules.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/agents/Schedules.tsx)
- Fixed duplicate parent suggestions by checking existing linked sessions before proposing
- Fixed `VectorStore.find_similar_sessions` method signature mismatch with call site
- Fixed `rebuild_index` endpoint type error when stores are `None` by adding explicit dependency injection
- Fixed session lineage not displaying by wiring `useSessionLineage` hook result into component render
- Fixed agent removal not cleaning up plugin directory and opencode.json by adding deletion logic to pipeline stages
- Fixed plan file not being captured by adding `postToolUse` hook entry
- Fixed skill upgrade detection only checking first agent by iterating over all configured agents
- Fixed MCP tools endpoint returning empty response due to malformed constant definition — see [`mcp_tools.py`](src/open_agent_kit/features/codebase_intelligence/daemon/mcp_tools.py)
- Fixed upgrade service only reporting Claude hook updates by rewriting detection loop to iterate all agent directories
- Fixed memory listing UI incorrectly showing plan entries by adding type filter
- Fixed UI build failure caused by missing `react-scripts` dependency
- Fixed CI plan capture and Markdown UI rendering issues — [Fix CI plan capture and Markdown UI rendering](http://localhost:38388/activity/sessions/f388d75b-245d-43e9-9702-590873c80f84)
- Fixed backup and restore feature completion status — [Debug backup and restore feature completion status](http://localhost:38388/activity/sessions/446cb7d6-81a4-4cad-8ff2-df895880b193)
- Fixed `/plans` API endpoint returning 500 error when no plans exist by ensuring `get_plans()` always returns a list — see [`store.py`](src/open_agent_kit/features/codebase_intelligence/activity/store.py)
- Fixed session summary endpoint returning empty strings by adding missing `Summarizer.process_session` call
- Fixed `RetrievalEngine` not being exported correctly from its package, causing `ImportError` — see [`retrieval/__init__.py`](src/open_agent_kit/features/codebase_intelligence/retrieval/__init__.py)
- Fixed race condition where concurrent hook calls could corrupt in-memory state by adding thread-safety around state mutations
- Fixed off-by-one error in `PromptBatchActivities.tsx` that skipped rendering the last activity
- Fixed backup process not triggering recomputation of `computed_hash`, leading to stale backups — see [`backup.py`](src/open_agent_kit/features/codebase_intelligence/activity/store/backup.py)
- Fixed `parent_session_id` foreign key not being re-established during backup restore
- Fixed deletion routine causing orphaned Chroma embeddings by reordering operations to delete from Chroma before SQLite commit
- Fixed watcher showing inflated file counts after deletions by adding `watcher_state.reset()` after full rescan — see [`watcher.py`](src/open_agent_kit/features/codebase_intelligence/indexing/watcher.py)
- Fixed batch status being set to 'completed' before patches were applied, causing the loop to skip processing
- Fixed first prompt in session incorrectly marked as plan by checking prompt text against known patterns
- Fixed duplicate plans appearing by adding `session_id` filter to `get_plans` query
- Fixed internal server error caused by missing newline before `ActivityStore` class definition
- Fixed legacy null-check for `source_machine_id` column that caused unnecessary conditional logic in restore
- Fixed summary capture activity and Cursor hook payload handling — [Add summary to capture activity and fix cursor hook](http://localhost:38388/activity/sessions/3a594cc8-1f9a-475a-8062-d1640bbffe50)
- Fixed notification deduplication dropping events due to timestamp suffix in event key — see [`notifications.py`](src/open_agent_kit/features/codebase_intelligence/daemon/routes/notifications.py)
- Fixed Claude Code transcript parsing to handle nested message format (`{type: "assistant", message: {...}}`) — see [`transcript.py`](src/open_agent_kit/features/codebase_intelligence/transcript.py)
- Fixed notification installer guard logic incorrectly skipping script generation — see [`installer.py`](src/open_agent_kit/features/codebase_intelligence/notifications/installer.py)
- Fixed CI command package missing submodule exports causing import failures — see [`ci/__init__.py`](src/open_agent_kit/commands/ci/__init__.py)
- Fixed OTEL route accessing manifest as dict instead of Pydantic model — see [`otel.py`](src/open_agent_kit/features/codebase_intelligence/daemon/routes/otel.py)
- Fixed response summary not captured when user queues a new message while Claude is responding (interrupt bypasses Stop hook) — added fallback capture in `UserPromptSubmit` — see [`hooks.py`](src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py)
- Fixed stale session recovery race condition where resumed sessions were immediately marked stale due to empty prompt batch — see [`sessions.py`](src/open_agent_kit/features/codebase_intelligence/activity/store/sessions.py)
- Fixed backup restoration failing when run from different working directory due to relative path check — see [`backup.py`](src/open_agent_kit/features/codebase_intelligence/activity/store/backup.py)
- Fixed SQL query referencing non-existent `parent_reason` column in sessions table — see [`hooks.py`](src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py)
- Fixed syntax errors in `hooks.py` caused by incomplete edits leaving stray characters — see [`hooks.py`](src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py)
- Fixed notification config template auto-generating unwanted language field — see [`notify_config.toml.j2`](src/open_agent_kit/features/codebase_intelligence/notifications/codex/notify_config.toml.j2)
- Fixed prompt batch finalization logic duplicated across routes by extracting to shared helper — see [`batches.py`](src/open_agent_kit/features/codebase_intelligence/activity/batches.py)

### Improved

- Session URLs in changelog now link directly to daemon UI for better traceability
- Executor now uses runtime lookup of daemon port for greater deployment flexibility
- Hook timeout increased to reduce flaky failures during heavy local LLM workloads
- Session end hook now auto-generates pending titles from session summary for better discoverability
- Codex VS Code extension OTel configuration validated — project-local `.codex/config.toml` is syntactically correct but extension only reads global config — [Configure OTel settings for Codex VS Code extension](http://localhost:38388/activity/sessions/019c3130-4d28-7772-ab84-cbac66f0947a)
- Quality gate (`make check`) cleaned up: removed blocker comments and verified full test suite passes — [Refactor blocker comments and run full quality gate check](http://localhost:38388/activity/sessions/ses_3ceae69a3ffeODOsYvxQrkMLj4)

### Notes

> **Gotcha**: The Codex VS Code extension only reads the global `codex.toml` for OTel settings — project-local `.codex/config.toml` is ignored by the extension. Place OTel configuration in the global file if targeting the extension.

> **Gotcha**: Backup directory paths configured via `OAK_CI_BACKUP_DIR` must be absolute. Relative paths silently resolve to cwd, which can produce unexpected file locations if the process changes directories.

> **Gotcha**: The `uv tool install` commands in `feature_service.py` and `language_service.py` previously destroyed editable installs. If you experience stale daemon assets or `Path(__file__)` resolving to `site-packages`, verify with `oak --python-path -c "import open_agent_kit; print(open_agent_kit.__file__)"` — the path must contain your source tree.

> **Gotcha**: Agent YAML files must be placed in `oak/agents` with the exact same filename as the built-in version; otherwise the registry will not find them and the default task will be used. A missing or renamed file silently falls back to the core definition.

> **Gotcha**: The daemon port file is now expected at `oak/` instead of `oak/ci/`. Documentation or tooling referencing the old path will fail to load runtime configuration.

> **Gotcha**: The `UpgradeService` performs a dry-run check first. Running `oak upgrade` compares template files against the latest version and reports "already up to date" if no differences are found. It does **not** trigger the asset build step — run `oak build` explicitly after modifying skills.

> **Gotcha**: The next auto-backup time is calculated as `last_backup + interval`. If no previous backup exists, an immediate backup is scheduled. This approach avoids cron complexity but may drift if backups take longer than expected.

> **Gotcha**: Astro's `output: 'static'` mode triggers prerendering for all routes without dynamic data. Ensure the docs site has no server-only routes before enabling this optimization.
