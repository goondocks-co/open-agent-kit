# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

- Refactored scheduling system to use cron YAML instead of saved_tasks — [Refactor scheduling system: remove saved_tasks and add cron YAML](http://localhost:38167/activity/sessions/e2eebc11-d5d5-4ef0-a986-152ec97fb577)
- Refactored Oak session handling to write directly to database — [Refactor Oak session handling to direct DB writes](http://localhost:38167/activity/sessions/e45f0867-78f1-435e-85bf-b6452b46c921)
- Refactored manifest to isolate CI settings and add plan hooks — [Refactor manifest to isolate CI settings and add plan hooks](http://localhost:38167/activity/sessions/a0e327fb-2101-4085-853b-e9bc36710e07)
- Moved CI history backups into `oak/ci/history` directory — [Refactor CI history backups into oak/ci/history directory](http://localhost:38167/activity/sessions/71bf753a-061f-4bc6-86ff-4cfa9a5cee78)
- Refactored session titles and summary generation logic for better readability — [Refactor session titles and summary generation logic](http://localhost:38283/activity/sessions/34602abe-5553-431a-a569-22b454afb9ee)
- Updated daemon and dashboard session sorting to show latest activity first — [Update daemon and dashboard session sorting to latest activity](http://localhost:38283/activity/sessions/5486fa06-43a5-4056-b488-128038d2dcd5)
- Session lineage card now collapsible with lint cleanup — [Update session lineage card collapsable behavior and lint cleanup](http://localhost:38283/activity/sessions/49b6ce9f-0425-4eb7-ae98-8a7bc5380b26)
- Adjusted agent timeouts and fixed stale hook configuration — [Fix stale hook configuration and adjust agent timeouts](http://localhost:38283/activity/sessions/f0d6a9a7-13b5-4464-bb09-c5c98070cb30)

### Fixed

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
