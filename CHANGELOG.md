# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Upgrade logic for built-in task templates with stable identifier support — [Implement upgrade logic for built‑in task templates](http://localhost:38167/activity/sessions/73094f41-9caa-4c8b-b2ad-5594e21f49b3)
- Filter chips and context indicator for daemon log viewer — [Add filter chips and context indicator to daemon log viewer](http://localhost:38167/activity/sessions/735f34fd-3899-437e-848f-e279228138dd)
- Minimum activity check before generating session titles — [Add minimum activity check before generating session titles](http://localhost:38167/activity/sessions/a812c6a9-27ad-4893-b5ae-17c25f17160e)
- Safe reset all processing state with confirmation dialog — [Implement safe reset all processing state with confirmation](http://localhost:38167/activity/sessions/16d4bd63-87a7-4fc9-88a1-f85fcbc3be4c)
- Python, JavaScript, and TypeScript language support for Oak — [Add Python, JavaScript, TypeScript support to Oak](http://localhost:38167/activity/sessions/73b2cf21-4907-44a9-b646-6bf9d231d23c)
- Row highlight for memory page search results — [Add row highlight for memory page search results](http://localhost:38167/activity/sessions/1076e1bf-b40b-4a19-b733-e2834ddf44dd)
- Collapsible left navigation and pause-scroll logs — [Implement collapsible left navigation and pause‑scroll logs](http://localhost:38167/activity/sessions/d19a3bb8-4b47-4a7a-9ed0-9bb74f7275e6)
- Watchdog timeout for Cloud Agent SDK — [Implement watchdog timeout for Cloud Agent SDK](http://localhost:38167/activity/sessions/9286b1bb-f34c-4911-9d91-e8e2e502d2e9)
- Dynamic agent discovery in Daemon UI — [Configure Daemon UI for Dynamic Agent Discovery](http://localhost:38167/activity/sessions/1ae65963-597b-48fb-ae99-8759116bbdee)
- OpenCode agent integration with CI plugin support — [Add OpenCode agent integration with CI plugin and cleanup](http://localhost:38167/activity/sessions/ca926b8e-eeae-400e-b36f-ace34200ec29)
- Session search endpoint and UI integration for finding sessions — [Implement session search endpoint and UI integration](http://localhost:38167/activity/sessions/4c64eaea-e383-4d26-b914-754b7dab937f)
- User-driven session linking with embedding-based suggestions — [Implement user‑driven session linking with embeddings](http://localhost:38167/activity/sessions/d8fb4448-546d-4cbb-9b86-dd6373d2e6c3)
- Skills subcommand and upgrade detection for Gemini agent — [Add skills subcommand and upgrade detection for Gemini](http://localhost:38167/activity/sessions/838216f8-c53b-40eb-8f26-b071e7f6c0e2)
- Cross-platform hook installation helper for consistent setup — [Implement cross‑platform hook installation helper](http://localhost:38167/activity/sessions/6eefb292-86e2-4f17-934f-90559869a737)
- Deterministic CI daemon port derived from git remote URL — [Implement deterministic CI daemon port via git remote URL](http://localhost:38167/activity/sessions/f58cca10-dd47-494c-8aa1-0bc00de74815)
- Privacy-preserving CI backup identifier using hashed paths — [Implement privacy-preserving CI backup identifier](http://localhost:38167/activity/sessions/2fbfc11c-dcb8-42f4-99b7-854685c6dae6)
- Persistent SQLite-backed agent run history with separate UI tabs for history and configuration — [Implement SQLite run history and UI tabs](http://localhost:38283/activity/sessions/08078e63-bd10-4305-8c14-e699679259e0)
- Reusable Activity component for the daemon UI, improving consistency across different views — [Refactor daemon UI and add reusable Activity component](http://localhost:38283/activity/sessions/cf7f051a-3259-48c3-ab21-4ea8658f4c2f)
- "Reprocess Observations" button with hash recompute functionality for memory management — [Add Reprocess Observations Button and Hash Recompute](http://localhost:38283/activity/sessions/e765187d-5f62-4e26-87fa-4f7605e2cd7b)
- Memory threshold strategy and re-processing plan for better memory management — [Implement memory threshold strategy and re-processing plan](http://localhost:38283/activity/sessions/0a3c6a29-341f-43ac-848e-0628b7d6e712)
- Session linking and auto memory observation creation for improved traceability — [Implement session linking and auto memory observation creation](http://localhost:38283/activity/sessions/7d914c67-f0b5-4a8f-a10d-650e2982e8d5)
- Codebase intelligence architecture and roadmap planning — [Plan codebase intelligence architecture and roadmap](http://localhost:38283/activity/sessions/f3283f87-2705-422e-a4ec-f692a2f88282)

### Changed

- Refactor Agent Instance to Configuration across UI and API — [Refactor Agent Instance to Configuration across UI and API](http://localhost:38167/activity/sessions/9017876a-5cab-4c1c-b5da-89f97cd24ca0)
- Configure plan capture workflow for Claude sessions — [Configure plan capture workflow for Claude sessions](http://localhost:38167/activity/sessions/96d99f2a-0e0f-449d-b3b3-ccd584f944a7)
- Removed unused issue provider functionality — [Refactor codebase: Remove unused issue provider](http://localhost:38167/activity/sessions/479bf687-46dd-4366-a1d6-b7d8163d7396)
- Enabled all CI features by default in Oak — [Refactor Oak to enable all CI features by default](http://localhost:38167/activity/sessions/d284e22a-f111-4439-b5fc-50adc873afff)
- Refactored agent hook installation to manifest-driven approach — [Refactor agent hook installation to manifest‑driven approach](http://localhost:38167/activity/sessions/23385f20-190f-4927-a703-a67a8dbadafc)
- Refactored MCP server installation to cross-platform Python API — [Refactor MCP server installation to cross‑platform Python API](http://localhost:38167/activity/sessions/c33978ff-d0dc-486c-96b1-64f9fe83cfb2)
- Refactored scheduling system to use cron YAML instead of saved_tasks — [Refactor scheduling system: remove saved_tasks and add cron YAML](http://localhost:38167/activity/sessions/e2eebc11-d5d5-4ef0-a986-152ec97fb577)
- Refactored Oak session handling to write directly to database — [Refactor Oak session handling to direct DB writes](http://localhost:38167/activity/sessions/e45f0867-78f1-435e-85bf-b6452b46c921)
- Refactored manifest to isolate CI settings and add plan hooks — [Refactor manifest to isolate CI settings and add plan hooks](http://localhost:38167/activity/sessions/a0e327fb-2101-4085-853b-e9bc36710e07)
- Moved CI history backups into `oak/ci/history` directory — [Refactor CI history backups into oak/ci/history directory](http://localhost:38167/activity/sessions/71bf753a-061f-4bc6-86ff-4cfa9a5cee78)
- Refactored session titles and summary generation logic for better readability — [Refactor session titles and summary generation logic](http://localhost:38283/activity/sessions/34602abe-5553-431a-a569-22b454afb9ee)
- Updated daemon and dashboard session sorting to show latest activity first — [Update daemon and dashboard session sorting to latest activity](http://localhost:38283/activity/sessions/5486fa06-43a5-4056-b488-128038d2dcd5)
- Session lineage card now collapsible with lint cleanup — [Update session lineage card collapsable behavior and lint cleanup](http://localhost:38283/activity/sessions/49b6ce9f-0425-4eb7-ae98-8a7bc5380b26)
- Adjusted agent timeouts and fixed stale hook configuration — [Fix stale hook configuration and adjust agent timeouts](http://localhost:38283/activity/sessions/f0d6a9a7-13b5-4464-bb09-c5c98070cb30)

### Fixed

- Renamed agent tasks now correctly installed during upgrade (name-based lookup replaced with stable identifiers) — [Implement upgrade logic for built‑in task templates](http://localhost:38167/activity/sessions/73094f41-9caa-4c8b-b2ad-5594e21f49b3)
- Fixed Vite configuration causing UI build failure — [Configure minimal Vite config to fix UI build](http://localhost:38167/activity/sessions/c0457435-38b1-4d48-bd53-af22a6ac08ae)
- Fixed UI build error related to dependency injection setup — [Fix UI build error and outline DI plan](http://localhost:38167/activity/sessions/461a8c4d-b772-4f41-8075-f4dd993ea874)
- Fixed filter chips in Logs page clearing entire log list instead of filtering — see [`Logs.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Logs.tsx)
- Fixed `indexStats` variable not defined in Dashboard.tsx causing TypeScript build failure — see [`Dashboard.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Dashboard.tsx)
- Fixed session summary not rendering as Markdown in MemoriesList component — see [`MemoriesList.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/data/MemoriesList.tsx)
- Fixed DevTools maintenance card layout wrapping below header instead of beside it — see [`DevTools.tsx`](src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/DevTools.tsx)
- Fixed Daemon UI bugs and added developer tools — [Fix Daemon UI bugs and add developer tools](http://localhost:38167/activity/sessions/969a6fa5-114f-4340-a403-b3ebed248d48)
- Fixed failing hook import in CI test suite — [Debug failing hook import in CI test suite](http://localhost:38167/activity/sessions/315e7240-ee03-49be-8320-4c403d54e0c7)
- Fixed plan capture workflow for Claude sessions — [Configure plan capture workflow for Claude sessions](http://localhost:38167/activity/sessions/96d99f2a-0e0f-449d-b3b3-ccd584f944a7)
- Fixed MCP upgrade dry run inconsistencies — [Debug MCP Upgrade Dry Run Inconsistencies](http://localhost:38167/activity/sessions/669382b1-4f57-45f0-b833-b55611e53b0c)
- Fixed Claude code causing 100% CPU hang — [Debug Claude code causing 100% CPU hang](http://localhost:38167/activity/sessions/5cc04051-d337-4b53-8156-a2756138cead)
- Fixed agent executor behavior after refactor — [Fix agent executor behavior after refactor](http://localhost:38167/activity/sessions/8adf6c3f-5032-41d1-9e5e-3e873241287b)
- Fixed CLI crash from `AttributeError: 'list' object has no attribute 'items'` caused by `registered_groups` being overwritten with a list during refactoring
- Fixed failing test `test_plan_service.py::test_create_plan_from_issue` by removing call to non-existent issue provider
- Fixed system health card truncating summarization model name by replacing hard-coded slice with CSS `text-overflow: ellipsis`
- Fixed dashboard displaying incorrect session count by using `count_sessions()` instead of recent sessions count
- Fixed orphaned memory entries by adding cascade delete for dependent observations
- Fixed upgrade service leaving empty parent directories after settings file deletion
- Fixed orphan-recovery logic not detecting plans due to `PROMPT_SOURCE_PLAN` constant mismatch
- Fixed CI backup filename leaking full path by using privacy-preserving hash — [Fix CI backup filename privacy bug](http://localhost:38167/activity/sessions/414c1ebe-fff6-40f2-876c-9a7df59ed469)
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
- Fixed CI plan capture and Markdown UI rendering issues — [Fix CI plan capture and Markdown UI rendering](http://localhost:38283/activity/sessions/f388d75b-245d-43e9-9702-590873c80f84)
- Fixed backup and restore feature completion status — [Debug backup and restore feature completion status](http://localhost:38283/activity/sessions/446cb7d6-81a4-4cad-8ff2-df895880b193)
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

### Improved

- Session URLs in changelog now link directly to daemon UI for better traceability
- Executor now uses runtime lookup of daemon port for greater deployment flexibility
- Hook timeout increased to reduce flaky failures during heavy local LLM workloads
