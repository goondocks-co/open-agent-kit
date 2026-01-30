# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Persistent SQLite-backed agent run history with separate UI tabs for history and configuration — [Implement SQLite run history and UI tabs](http://localhost:38283/activity/sessions/08078e63-bd10-4305-8c14-e699679259e0)
- Reusable Activity component for the daemon UI, improving consistency across different views — [Refactor daemon UI and add reusable Activity component](http://localhost:38283/activity/sessions/cf7f051a-3259-48c3-ab21-4ea8658f4c2f)
- "Reprocess Observations" button with hash recompute functionality for memory management — [Add Reprocess Observations Button and Hash Recompute](http://localhost:38283/activity/sessions/e765187d-5f62-4e26-87fa-4f7605e2cd7b)
- Memory threshold strategy and re-processing plan for better memory management — [Implement memory threshold strategy and re-processing plan](http://localhost:38283/activity/sessions/0a3c6a29-341f-43ac-848e-0628b7d6e712)
- Session linking and auto memory observation creation for improved traceability — [Implement session linking and auto memory observation creation](http://localhost:38283/activity/sessions/7d914c67-f0b5-4a8f-a10d-650e2982e8d5)
- Codebase intelligence architecture and roadmap planning — [Plan codebase intelligence architecture and roadmap](http://localhost:38283/activity/sessions/f3283f87-2705-422e-a4ec-f692a2f88282)

### Changed

- Refactored session titles and summary generation logic for better readability — [Refactor session titles and summary generation logic](http://localhost:38283/activity/sessions/34602abe-5553-431a-a569-22b454afb9ee)
- Updated daemon and dashboard session sorting to show latest activity first — [Update daemon and dashboard session sorting to latest activity](http://localhost:38283/activity/sessions/5486fa06-43a5-4056-b488-128038d2dcd5)
- Session lineage card now collapsible with lint cleanup — [Update session lineage card collapsable behavior and lint cleanup](http://localhost:38283/activity/sessions/49b6ce9f-0425-4eb7-ae98-8a7bc5380b26)
- Adjusted agent timeouts and fixed stale hook configuration — [Fix stale hook configuration and adjust agent timeouts](http://localhost:38283/activity/sessions/f0d6a9a7-13b5-4464-bb09-c5c98070cb30)

### Fixed

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
