# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
