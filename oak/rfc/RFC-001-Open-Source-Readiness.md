# RFC-001: Open Agent Kit -- Open-Source Launch Readiness

**Author:** AI Review (Claude)
**Date:** 2026-02-06
**Status:** Draft
**Tags:** open-source, launch, code-quality, security, distribution

---

## Summary

This RFC captures a comprehensive pre-launch review of Open Agent Kit (OAK) across six dimensions: Python code quality, frontend code quality, security posture, distribution strategy, documentation/website planning, and pre-open-source chores. It provides prioritized, actionable findings to bring OAK to open-source readiness.

**Overall Assessment:** The codebase is in strong shape for an alpha/beta open-source launch. The Python backend is well-architected with good service layer patterns, and the frontend demonstrates exceptional TypeScript discipline (zero `any` types, strict mode). The main blockers are: (1) no PyPI publishing, (2) a few security fixes needed before public exposure, and (3) documentation gaps. None of these are architectural -- they are all execution items.

---

## Table of Contents

1. [Python Code Quality](#1-python-code-quality)
2. [Frontend / TypeScript Code Quality](#2-frontend--typescript-code-quality)
3. [Security Audit](#3-security-audit)
4. [Distribution Strategy](#4-distribution-strategy)
5. [Documentation & Website](#5-documentation--website)
6. [Configuration Architecture](#6-configuration-architecture-project-config-vs-user-config)
7. [Pre-Open-Source Chores](#7-pre-open-source-chores)
8. [Launch Phases & Prioritized Action Items](#8-launch-phases--prioritized-action-items)

---

## 1. Python Code Quality

**173 source files, ~80 test files reviewed.**

### 1.1 Severity Summary

| Severity | Count |
|----------|-------|
| High     | 4     |
| Medium   | 13    |
| Low      | 8     |
| **Total** | **25 issues** |

### 1.2 High-Severity Findings

**H-PY1. 1074-line CI constants file with dual constant systems.**
`src/open_agent_kit/features/codebase_intelligence/constants.py` covers 15+ domains. A parallel `daemon/constants.py` duplicates many values using a different representation (flat `Final` vs. namespace classes). Code imports from both interchangeably, creating a maintenance hazard.
- **Fix:** Split into domain-specific modules (`tunnel/constants.py`, `agents/constants.py`, etc.). Eliminate `daemon/constants.py` by importing from the split modules.

**H-PY2. 350-line `lifespan` function in `server.py` (lines 377-728).**
This single async context manager initializes and shuts down the entire daemon: config, logging, tunnels, embedding providers, vector store, indexer, activity store, processor, agent subsystem. A failure in any subsystem is entangled with all others.
- **Fix:** Decompose into `_init_embedding_provider()`, `_init_vector_store()`, `_init_activity_system()`, `_init_agent_subsystem()`, `_graceful_shutdown()`.

**H-PY3. 1909-line activity routes file.**
`daemon/routes/activity.py` handles session CRUD, lineage, linking, suggestions, relationships, plans, activities, reprocessing, and summary regeneration. The identical `except HTTPException: raise / except (OSError, ValueError, RuntimeError, AttributeError) as e: ...` pattern appears 24 times.
- **Fix:** Split into `routes/sessions.py`, `routes/plans.py`, `routes/relationships.py`. Add shared exception-handling middleware.

**H-PY4. Duplicated doc_type weighting logic in RetrievalEngine.**
`retrieval/engine.py` lines ~421-434 and ~642-650 contain identical `apply_doc_type_weights` blocks. The same file also has four near-identical confidence-enrichment loops for code, memory, plans, and sessions.
- **Fix:** Extract `_apply_doc_type_weights()` and `_enrich_results_with_confidence()` helpers.

### 1.3 Medium-Severity Findings (Selected)

| ID | Finding | Location |
|----|---------|----------|
| M-PY1 | Bare `except Exception` in VectorStore | `memory/store/core.py:160` |
| M-PY2 | Silent `pass` blocks swallow 4 exception types | `memory/store/core.py:155-156, 197-201` |
| M-PY3 | Namespace classes instead of `StrEnum` | `daemon/constants.py:22-71` |
| M-PY4 | Module-level singleton instead of FastAPI `Depends()` | `daemon/state.py:397-408` |
| M-PY5 | DaemonState mixes state container + business logic | `daemon/state.py:289-370` |
| M-PY6 | Async routes call synchronous code without `run_in_executor` | `daemon/routes/search.py` |
| M-PY7 | Raw SQL in route handlers bypasses store layer | `routes/activity.py:720-748, 1287-1293` |
| M-PY8 | Duplicated HNSW config dict | `memory/store/core.py:87-91, 210-214` |
| M-PY9 | Near-identical directory traversal in `file_utils.py` | `utils/file_utils.py:419-485` |
| M-PY10 | `os.chdir()` in test fixture (not thread-safe for xdist) | `tests/conftest.py:20-26` |
| M-PY11 | AgentService mixes manifest, filesystem, and constitution concerns | `services/agent_service.py` |
| M-PY12 | Magic number `3` instead of `MIN_SESSION_ACTIVITIES` | `routes/activity.py:1872` |
| M-PY13 | Three `"utf-8"` constants in one file | `constants.py:307, 401, 723` |

### 1.4 Positives

- **VectorStore delegation pattern**: Clean facade delegating to focused submodules (`code_ops`, `memory_ops`, `search`, `management`, `session_ops`).
- **RetrievalEngine as single entry point**: All retrieval paths use one engine with consistent confidence scoring.
- **Pydantic response models on every route**: Automatic validation, serialization, and OpenAPI docs.
- **Consistent `typing.Final` usage**: All 1074 constants use `Final[type]` annotations.
- **Well-structured OakConfig**: `Field` descriptions, YAML serialization with custom inline list dumper, migration logic.

### 1.5 Resolution Status

**Section 1 is complete.** All high-severity and actionable medium-severity findings have been resolved (2026-02-06). Implementation was done in 5 phases:

| Phase | Finding(s) | Resolution |
|-------|-----------|------------|
| 1A | M-PY8 | Extracted duplicated HNSW config to shared constants and helper |
| 1B | M-PY12 | Replaced magic number `3` with `MIN_SESSION_ACTIVITIES` constant |
| 1C | M-PY7 | Moved raw SQL from route handlers into store layer methods |
| 2 | H-PY4 | Extracted `_apply_doc_type_weights()` helper in RetrievalEngine |
| 3A | H-PY3 (partial) | Created `handle_route_errors` decorator, eliminating 24 duplicated try/except blocks |
| 3B | H-PY3 (complete) | Split `activity.py` (1868 lines) into 4 domain files: `activity.py` (757), `activity_sessions.py` (557), `activity_relationships.py` (294), `activity_management.py` (174) |
| 4 | H-PY2 | Decomposed 353-line `lifespan()` into 7 focused helpers (~65-line orchestrator) |
| 5 | H-PY1, M-PY3 | Eliminated `daemon/constants.py` (245 lines); migrated to main `constants.py` using `Final[str]` pattern |

Medium-severity items M-PY1, M-PY2, M-PY4, M-PY5, M-PY6, M-PY9, M-PY10, M-PY11, M-PY13 were evaluated and determined to be already resolved, intentionally designed, or acceptable as-is (see implementation plan for disposition details).

---

## 2. Frontend / TypeScript Code Quality

**53 source files (React + TypeScript + Tailwind + Vite) reviewed.**

### 2.1 Ratings by Category

| Category | Rating | Top Finding |
|----------|--------|-------------|
| TypeScript | Very Good | Zero `any` types, full `strict: true`. Add runtime validation for API data. |
| Tailwind CSS | Good | Proper theming, `cn()` utility. Fix hard-coded `prose-invert`, inconsistent form inputs. |
| React Patterns | Good | Solid React Query v5, proper hooks. Extract duplicated pagination pattern. |
| Component Structure | Good | Clean layout. Split `config-components.tsx`, migrate dialogs to Radix Dialog. |
| API Integration | Very Good | Centralized typed client. Add request cancellation, enforce endpoint constants. |
| Build Config | Very Good | Maximal strictness. |
| Dependencies | Very Good | Lean and purposeful. Audit `framer-motion` and `js-yaml` necessity. |
| **Accessibility** | **Needs Improvement** | Dialogs lack ARIA, focus trap, keyboard dismissal. Icon buttons lack `aria-label`. |
| Code Organization | Good | Constants-first discipline. Split monolithic `constants.ts` (1315 lines). |

### 2.2 Critical Issues

**A11y is the primary gap.** The three custom dialog components (`ContentDialog`, `ConfirmDialog`, `SessionPickerDialog`) are built with plain `<div>` overlays. They lack:
- `role="dialog"` and `aria-modal="true"`
- `aria-labelledby` / `aria-describedby`
- Focus trapping (Tab cycles behind backdrop)
- Keyboard dismissal (Escape key only on `ConfirmDialog`)

The project already depends on `@radix-ui/react-checkbox` and `@radix-ui/react-label`. Migrating to `@radix-ui/react-dialog` provides all of the above automatically.

### 2.3 Other Notable Issues

- **Debug `console.log` in production**: `Config.tsx` lines 224, 250 log config values. Remove before launch.
- **Duplicated session title derivation**: `session.title || session.first_tool || "Session #" + session.session_id.slice(0,8)` repeated in 4-5 components.
- **Duplicated "load more" pagination**: Identical offset/loaded/handleLoadMore pattern in `SessionList`, `MemoriesList`, `PlansList`. Extract a `usePaginatedList` hook.
- **Missing `useEffect` cleanup**: `setTimeout` in `ContentDialog` and `TeamSharing` has no cleanup on unmount.
- **Unused animations**: Tailwind config defines `accordion-down`/`accordion-up` keyframes but no accordion component exists.

### 2.4 Resolution Status

**Section 2 is complete.** All critical issues have been resolved (2026-02-06). Implementation was done in 2 phases:
| Phase | Finding(s) | Resolution |
|-------|-----------|------------|
| 1 | A11y | Migrated custom dialogs to `@radix-ui/react-dialog` |
| 2 | Debug `console.log` | Removed `console.log` from `Config.tsx` |
| 3 | Duplicated session title derivation | Extracted `get_session_title()` helper |
| 4 | Duplicated "load more" pagination | Extracted `usePaginatedList` hook |

---

## 3. Security Audit

### 3.1 Findings Summary

| Severity | Count | Resolved |
|----------|-------|----------|
| Critical | 0     | --       |
| High     | 1     | 1        |
| Medium   | 5     | 2        |
| Low      | 7     | 0        |

**No leaked secrets, no hardcoded credentials, no critical vulnerabilities found.**

### 3.2 High-Severity Finding

**H-SEC1. `shell=True` subprocess calls with template-derived commands.** **RESOLVED**
`src/open_agent_kit/features/codebase_intelligence/mcp/installer.py`.
Commands are constructed via `.format()` with values from agent manifest YAML files (server name, command strings).
- **Fix applied:** Refactored all 3 `subprocess.run()` calls from `shell=True` to `shell=False` with `shlex.split()`. Added defense-in-depth `_validate_cli_value()` with conservative alphanumeric allowlist that runs BEFORE `.format()`. Malicious inputs are rejected with `ValueError` before any subprocess is spawned.
- **Tests:** `tests/unit/features/codebase_intelligence/mcp/test_installer.py` (17 tests: validation allowlist, shell=False verification, shlex.split correctness, injection blocking)

### 3.3 Medium-Severity Findings

| ID | Finding | Location | Impact | Status |
|----|---------|----------|--------|--------|
| M-SEC1 | No authentication on daemon API | `daemon/server.py`, all routes | Any local process has full access | Open |
| M-SEC2 | Tunnel exposes entire API without auth | `routes/tunnel.py:76-149` | Remote data access/deletion | Open |
| M-SEC3 | Unrestricted DevTools endpoints | `routes/devtools.py` | Data loss operations unprotected | Open |
| M-SEC4 | API key values partially logged | `agents/executor.py:202` | First 20 chars of secrets in daemon.log | **RESOLVED** |
| M-SEC5 | No secrets redaction on prompt/activity storage | `activity/store/models.py`, `batches.py` | Raw API keys, tokens in SQLite/ChromaDB | **RESOLVED** |

**M-SEC4 resolution:** Removed `value[:20]` from debug log — key name alone is sufficient for debugging. Test in `test_executor.py::TestApplyProviderEnv`.

**M-SEC5 resolution:** Created `utils/redact.py` — a reusable secrets redaction utility that loads high-confidence patterns from [secrets-patterns-db](https://github.com/mazen160/secrets-patterns-db) (MIT, cached locally for 7 days) with 10 hardcoded fallback patterns. Integrated at the storage layer: 3 `to_row()` methods in `models.py` + 3 direct UPDATE paths in `batches.py`. Initialized at daemon startup in `server.py:lifespan()`. Tests in `test_redact.py` (16 tests: pattern coverage, dict recursion, fallback loading).

### 3.4 Low-Severity Findings

| ID | Finding | Location |
|----|---------|----------|
| L-SEC1 | `api_key` fields and `log_level: DEBUG` in tracked config | Resolved by user config overlay (Section 6) |
| L-SEC2 | SQL queries use f-string formatting (safe but fragile) | Multiple store files |
| L-SEC3 | CORS allows wildcard methods/headers | `server.py:788-794` |
| L-SEC4 | Search queries logged at INFO level | `routes/search.py:98` |
| L-SEC5 | Dependencies use `>=` only (no upper bounds) | `pyproject.toml` |
| L-SEC6 | User prompt content stored unencrypted | `.oak/ci/activities.db` |
| L-SEC7 | `log_level: DEBUG` in tracked config | `.oak/config.yaml:175` |

### 3.5 Positive Security Practices

- Daemon binds to `127.0.0.1` only (no remote access by default)
- SSRF protection on provider URLs (validates localhost-only for outbound HTTP)
- Path traversal protection on backups (`resolve()` + `is_relative_to()`)
- No `eval()`, `exec()`, `pickle.load()`, `yaml.unsafe_load()` anywhere
- All subprocess calls use `shell=False` with explicit args (H-SEC1 resolved remaining cases)
- Timeouts on all subprocess calls
- Runtime data (`.oak/ci/`) excluded from git
- Pydantic validation on all API request bodies
- No tracked `.env` files
- MIT license with compatible dependencies

---

## 4. Distribution Strategy

### 4.1 Current State

The only install path is `uv tool install --python 3.13 git+...`, which requires:
1. Knowing about `uv`
2. Knowing to pass `--python 3.13`
3. GitHub access (SSH or HTTPS)
4. Full repo clone (~50+ MB) for every install

### 4.2 Recommended Strategy (Ranked by Impact)

| Rank | Channel | Effort | Reach | Blockers |
|------|---------|--------|-------|----------|
| **1** | **PyPI publish** | Low-Medium | Very High | Add `pypi-publish` step to release.yml, register on PyPI |
| **2** | **Relax Python to >=3.12** | Medium | Doubles user base | Audit code for 3.12 compat, update CI matrix |
| **3** | **pipx install** (via PyPI) | Trivial | High | Depends on #1 |
| **4** | **Install script** (`curl \| bash`) | Low | Medium | Download latest wheel from GitHub Release |
| **5** | **Homebrew tap** | Medium | macOS/Linux | Depends on #1 |
| **6** | **Docker image** | Medium | DevOps/eval | Limited for primary use due to MCP/hooks |
| **7** | **npm wrapper** | High | Node.js | Not recommended; complexity vs. benefit |

### 4.3 PyPI Readiness Gaps

The `pyproject.toml` is ~80% ready. Missing items:
- **No PyPI publish step in CI** (biggest blocker) -- need `pypa/gh-action-pypi-publish@release/v1`
- Incomplete classifiers (only 4; add `Topic::Software Development`, `Environment::Console`, etc.)
- No `license-files` field (PEP 639)
- No `Changelog` URL in `[project.urls]`
- No `npm ci && npm run build` step in release workflow before `python -m build`

### 4.4 Python Version Constraint

`requires-python = ">=3.13,<3.14"` is extremely narrow. No 3.13-specific features (`type` statement aliases, 3.13-specific stdlib) were observed in the codebase. The pin appears conservative rather than necessary.
- Relaxing to `>=3.12` roughly doubles the addressable user base.
- Relaxing to `>=3.11` covers ~80-85% of active Python developers.
- **Recommendation:** At minimum remove the `<3.14` upper bound. Ideally relax to `>=3.12`.

### 4.5 Frontend Asset Bundling Issue

Pre-built static assets are committed to git (content-hashed filenames like `index-BHzm-YC-.css`). The release workflow does NOT run `npm build` -- it ships whatever was last committed. If a developer forgets `make ui-build` before tagging, stale UI assets ship.
- **Fix:** Add `npm ci && npm run build` to the release workflow before `python -m build`.

### 4.6 Claude Code Marketplace / MCP Packaging

The project has strong MCP infrastructure (`mcp_server.py` with `oak_search`, `oak_remember`, `oak_context`). `oak init --agent claude` already writes the MCP config to `.claude/settings.json`. Until a formal Claude Code marketplace exists, the current approach is correct. If a marketplace emerges, OAK could publish a thin MCP descriptor listing `oak` as a prerequisite.

**Key blocker:** The MCP server requires the full daemon (ChromaDB, SQLite, file watchers). A lightweight "MCP-only" package isn't feasible without refactoring.

---

## 5. Documentation & Website

### 5.1 README Assessment

**Score: 6.5/10 for open-source readiness.**

| Strength | Gap |
|----------|-----|
| Strong tagline: "The Intelligence Layer for AI Agents" | Information architecture inverted (install before features) |
| Thorough CLI reference | Two duplicate `## Quick Start` headings |
| Good multi-agent support docs | No GIF/video demonstration |
| Troubleshooting section | Too long at 500+ lines (full CLI ref belongs in docs site) |
| | No architecture diagram in README |
| | Dashboard screenshot referenced but not embedded |

**Recommended README structure (target ~200 lines):**
1. Title + badges + one-liner
2. Hero screenshot or GIF
3. Why OAK? (3 bullets)
4. 30-second Quick Start
5. How It Works (architecture diagram)
6. Features (table, links to docs)
7. Supported Agents (icon row)
8. Installation (brief)
9. Docs website link
10. Contributing + License

Everything else (full command reference, config details, troubleshooting) moves to the docs website.

### 5.2 Website Outline

**Recommended stack: Astro Starlight** on GitHub Pages.
- Custom landing page with hero, value props, demo GIF, agent compatibility row
- Starlight docs layout for all documentation pages
- Built-in Mermaid rendering (OAK docs already use Mermaid extensively)
- Pagefind search (zero-config, client-side, works on GitHub Pages)
- Dark mode default matches OAK dashboard aesthetic

**Estimated effort: 2-3 days** (scaffolding + content migration + landing page + GitHub Actions deployment).

**Full site map:**

```
/                          Landing page (hero, value props, quick start, features)
/docs/getting-started/     5-minute setup guide
/docs/features/
  codebase-intelligence/   8 sub-pages (overview, memory, dashboard, hooks, etc.)
  rules-management/        Constitution workflow
  strategic-planning/      RFC workflow
/docs/agents/              Per-agent setup guides (6 pages)
/docs/api/                 REST endpoints, MCP tools, hooks API
/docs/architecture/        System design + diagrams
/docs/cli/                 Full CLI reference (migrated from README)
/docs/configuration/       Config reference
/docs/troubleshooting/     FAQ + common issues
/contributing/             Contributing guide
/blog/                     Changelog + release notes
```

### 5.3 Missing Documentation (Blocking for Launch)

1. **`docs/architecture.md`** -- Referenced by README and CONTRIBUTING.md but does not exist. Content exists scattered across research docs.
2. **`docs/README.md`** (Documentation Index) -- Referenced by README but missing.
3. **MCP Tools Reference** -- Three MCP tools mentioned but no parameter/response documentation.
4. **`docs/development/features.md`** -- Referenced by CONTRIBUTING.md but entire `docs/development/` directory is missing.
5. **`docs/development/releasing.md`** -- Referenced by README but does not exist.
6. **Real security contact** -- `SECURITY.md` line 24 uses placeholder `opensource@example.com`. **Must** be replaced.

### 5.4 Key Differentiators for Marketing

| Differentiator | Marketing Angle |
|----------------|----------------|
| Agent-agnostic with deep, normalized integration | "One memory for your whole team, regardless of AI tool" |
| Automatic observation capture (zero-effort memory) | "Your AI learns from every session automatically" |
| Local-first / privacy-first architecture | "Your code never leaves your machine" |
| AST-aware semantic search (not text-level RAG) | "Finds `authenticate_user` when you search for 'auth middleware'" |
| Built-in web dashboard | "See what your AI knows" |
| Team knowledge sharing via git | "When one developer's AI learns a gotcha, the whole team benefits" |
| Constitution-driven development | "Formalize your engineering standards for consistent AI behavior" |

---

## 6. Configuration Architecture: Project Config vs. User Config

### 6.1 Problem Statement

`.oak/config.yaml` is tracked in git and serves dual purposes today:
- **Project-level settings** that the team agrees on (agents, skills, languages, RFC config, exclude patterns, session quality thresholds)
- **Machine-local settings** that vary per developer (embedding provider/model/URL, summarization provider/model/URL, API keys, tunnel provider/paths, log level, daemon port)

Currently, `.env` support exists (`python-dotenv` loaded at CLI startup, plus `${ENV_VAR}` syntax for API keys), and the documented priority hierarchy is: env vars > config.yaml > manifest defaults > hardcoded defaults. But this is cumbersome for everyday use -- developers don't want to manage a growing list of `OAK_CI_*` env vars for routine preferences like switching their embedding model.

### 6.2 Decision: Machine-ID-Based User Config (NOT .gitignore)

**The original RFC recommended adding `.oak/config.yaml` to `.gitignore`. This is rejected** -- the project config should remain in source control so teams share a common baseline.

Instead, introduce a **user config overlay** that:
- Uses the existing `source_machine_id` (`{github_user}_{6_char_hash}`) as the identifier
- Is stored at `.oak/config.{machine_id}.yaml` (e.g., `.oak/config.octocat_a7b3c2.yaml`)
- Is gitignored by pattern (`.oak/config.*.yaml`)
- Merges on top of the project config at load time (user values win)
- Participates in the backup/restore system (exported/imported alongside the machine's SQL backup)

### 6.3 Classification: Project vs. User Settings

| Setting Path | Classification | Rationale |
|-------------|---------------|-----------|
| `agents` | **Project** | Team agrees on which agents are supported |
| `agent_capabilities` | **Project** | Shared understanding of agent features |
| `rfc.*` | **Project** | Shared RFC workflow |
| `constitution.*` | **Project** | Shared standards |
| `languages.installed` | **Project** | Parsers needed for the repo's languages |
| `skills.*` | **Project** | Skills the whole team uses |
| `codebase_intelligence.embedding.provider` | **User** | Dev A uses Ollama, Dev B uses LM Studio |
| `codebase_intelligence.embedding.model` | **User** | Model availability varies by machine |
| `codebase_intelligence.embedding.base_url` | **User** | Local server URLs vary |
| `codebase_intelligence.embedding.api_key` | **User** | Personal API keys |
| `codebase_intelligence.embedding.dimensions` | **Project** | Must match for shared vector DB compatibility |
| `codebase_intelligence.embedding.context_tokens` | **Project** | Affects chunking strategy for shared index |
| `codebase_intelligence.summarization.*` | **User** | Provider, model, URL, key are all machine-local |
| `codebase_intelligence.agents.provider_type` | **User** | Cloud vs. local varies per dev |
| `codebase_intelligence.agents.provider_base_url` | **User** | Local server URLs vary |
| `codebase_intelligence.agents.provider_model` | **User** | Model availability varies |
| `codebase_intelligence.agents.max_turns` | **Project** | Team-wide guard on agent run length |
| `codebase_intelligence.agents.timeout_seconds` | **Project** | Team-wide timeout |
| `codebase_intelligence.agents.scheduler_interval_seconds` | **Project** | Team-wide scheduling |
| `codebase_intelligence.session_quality.*` | **Project** | Team-wide quality thresholds |
| `codebase_intelligence.tunnel.provider` | **User** | Dev's tunnel preference |
| `codebase_intelligence.tunnel.auto_start` | **User** | Personal preference |
| `codebase_intelligence.tunnel.*_path` | **User** | Binary locations vary |
| `codebase_intelligence.index_on_startup` | **Project** | Team-wide behavior |
| `codebase_intelligence.watch_files` | **Project** | Team-wide behavior |
| `codebase_intelligence.exclude_patterns` | **Project** | Team-wide ignore list |
| `codebase_intelligence.log_level` | **User** | Personal debugging preference |
| `codebase_intelligence.log_rotation.*` | **User** | Machine-local log management |

### 6.4 Priority Hierarchy (Updated)

```
1. Environment variables (OAK_CI_*, .env file)      ← Highest: escape hatch / CI override
2. User config (.oak/config.{machine_id}.yaml)       ← Machine-local preferences
3. Project config (.oak/config.yaml)                  ← Team baseline (git-tracked)
4. Feature manifest defaults                          ← Sensible out-of-box
5. Hardcoded defaults                                 ← Lowest: last resort
```

### 6.5 Merge Semantics

The user config file contains **only the keys the user wants to override** -- it is a sparse overlay, not a full copy. Merge rules:

| Type | Behavior |
|------|----------|
| Scalar (string, int, bool) | User value replaces project value |
| Dict (object) | Deep merge -- user keys override, project keys preserved |
| List | User value **replaces** project value (no list merge -- too unpredictable) |

Example: If the project config has `embedding.provider: ollama` and `embedding.model: bge-m3`, and the user config has `embedding.provider: lmstudio`, the merged result is `embedding.provider: lmstudio, embedding.model: bge-m3`.

### 6.6 UX Model: Who Writes What, How

There are three actors that write config, each with a distinct interface:

| Actor | Interface | Reads/Writes | Notes |
|-------|-----------|-------------|-------|
| **Human user** | Dashboard Settings page | Both project and user config | Primary UI. Routing is automatic based on classification table. |
| **AI agent** | `oak ci config` CLI | Both project and user config | Agent-facing utility invoked by skills. Humans rarely call it directly. |
| **Team lead / CI** | `oak ci config --project` | Project config only | Explicit flag for team-wide settings. Also usable in CI pipelines. |

**Dashboard (primary interface):**
The existing Dashboard Settings page already allows users to configure embedding providers, summarization models, tunnel settings, and log levels via `save_ci_config()`. The change is that `save_ci_config()` gains **scope routing**: it inspects the key being written and routes user-classified settings to `.oak/config.{machine_id}.yaml` and project-classified settings to `.oak/config.yaml`. From the user's perspective, nothing changes -- they use the same UI, and their personal settings simply stop polluting the tracked config.

**`oak ci config` (agent-facing utility):**
This command already accepts flags that map cleanly to user-classified settings (`--provider`, `--model`, `--base-url`, `--debug`, `--log-level`, `--sum-provider`, `--sum-model`, `--sum-url`). The change: calls through `save_ci_config()` with scope routing, so agent-invoked config changes automatically land in the correct file. No new `--user` flag needed -- the classification table decides.

A new `--project` flag is added for the team-lead case: `oak ci config --project --provider ollama --model bge-m3` forces all keys to the project config regardless of classification.

A new `--show` flag is added: `oak ci config --show` prints the effective merged config with origin annotations (e.g., `[project]`, `[user]`, `[env]`, `[default]`). Useful for debugging.

**New `modifying-oak-configuration` skill:**
A config skill does not exist yet. Following the project's gerund naming convention (cf. `finding-related-code`, `analyzing-code-change-impacts`):

- **Name:** `modifying-oak-configuration`
- **Location:** `src/open_agent_kit/features/codebase_intelligence/skills/modifying-oak-configuration/SKILL.md`
- **Manifest entry:** Add to `features/codebase_intelligence/manifest.yaml` under `skills:` (alongside `finding-related-code` and `analyzing-code-change-impacts`)
- **`user-invocable: true`** — agents and users can invoke it explicitly

The SKILL.md teaches agents how to use `oak ci config` to adjust settings — e.g., "I notice your embedding provider is unreachable, would you like me to switch to a different one?" It should document the classification table (which settings are user vs. project), the `--project` flag for team-wide overrides, and the `--show` flag for diagnostics.

**Installation for existing projects:** The `ReconcileSkillsStage` runs on every `oak init` and `oak upgrade`, calling `refresh_skills()` which is idempotent — it installs any skills present in feature manifests but missing from agent skill directories. So adding this skill to the CI manifest is sufficient; the next `oak init` or `oak upgrade` run auto-installs it. No separate skill migration is needed.

### 6.7 Migration via `oak upgrade`

Migration uses the existing `oak upgrade` migration system (tracked in `.oak/state.yaml`). No first-run prompts.

**New migration: `2026.xx.xx_split_user_config`**

Added to `get_migrations()` in `src/open_agent_kit/services/migrations.py`:

```python
def _migrate_split_user_config(project_dir: Path) -> None:
    """Move user-classified values from project config to user config overlay."""
    config_path = project_dir / ".oak" / "config.yaml"
    if not config_path.exists():
        return

    config = yaml.safe_load(config_path.read_text())
    ci = config.get("codebase_intelligence", {})
    if not ci:
        return

    # Resolve machine ID (reuse existing function)
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )
    machine_id = get_machine_identifier()
    user_config_path = project_dir / f".oak/config.{machine_id}.yaml"

    # Extract user-classified keys that have non-default values
    user_overlay = {}
    USER_KEYS = {
        ("embedding", "provider"), ("embedding", "model"),
        ("embedding", "base_url"), ("embedding", "api_key"),
        ("summarization", "enabled"), ("summarization", "provider"),
        ("summarization", "model"), ("summarization", "base_url"),
        ("summarization", "api_key"), ("summarization", "timeout"),
        ("agents", "provider_type"), ("agents", "provider_base_url"),
        ("agents", "provider_model"),
        ("tunnel", "provider"), ("tunnel", "auto_start"),
        ("tunnel", "cloudflared_path"), ("tunnel", "ngrok_path"),
        ("log_level",), ("log_rotation", "enabled"),
        ("log_rotation", "max_size_mb"), ("log_rotation", "backup_count"),
    }

    for key_path in USER_KEYS:
        value = ci
        for k in key_path:
            value = value.get(k, _SENTINEL) if isinstance(value, dict) else _SENTINEL
            if value is _SENTINEL:
                break
        if value is not _SENTINEL and value is not None:
            # Build nested dict in user_overlay
            target = user_overlay.setdefault("codebase_intelligence", {})
            for k in key_path[:-1]:
                target = target.setdefault(k, {})
            target[key_path[-1]] = value

    if not user_overlay:
        return

    # Write user config
    user_config_path.write_text(yaml.dump(user_overlay, default_flow_style=False))

    # Strip user-classified keys from project config and reset to project defaults
    PROJECT_DEFAULTS = {
        "log_level": "INFO",
    }
    for key_path in USER_KEYS:
        target = ci
        for k in key_path[:-1]:
            target = target.get(k, {}) if isinstance(target, dict) else {}
        if isinstance(target, dict) and key_path[-1] in target:
            del target[key_path[-1]]

    for k, v in PROJECT_DEFAULTS.items():
        ci[k] = v

    config_path.write_text(yaml.dump(config, default_flow_style=False))
```

This migration:
1. Reads the current `.oak/config.yaml`
2. Extracts all user-classified values that have non-default/non-null values
3. Writes them to `.oak/config.{machine_id}.yaml`
4. Strips those keys from the project config and sets project defaults (e.g., `log_level: INFO`)
5. Is idempotent -- re-running on a project that already has a user config is a no-op (no user-classified keys remain in project config)

### 6.8 Config Loading Changes

**`load_ci_config()` merge step:**

```python
def load_ci_config() -> CIConfig:
    project = _load_yaml(".oak/config.yaml").get("codebase_intelligence", {})

    machine_id = get_machine_identifier()
    user_path = f".oak/config.{machine_id}.yaml"
    user = _load_yaml(user_path).get("codebase_intelligence", {}) if Path(user_path).exists() else {}

    merged = _deep_merge(project, user)   # user wins on conflict
    # env vars still override everything (existing behavior)
    return CIConfig.from_dict(merged)
```

**`save_ci_config()` scope routing:**

```python
# Classification lookup (static table derived from Section 6.3)
_USER_CLASSIFIED_KEYS = {"provider", "model", "base_url", "api_key", ...}

def save_ci_config(updates: dict, *, force_project: bool = False) -> None:
    if force_project:
        _write_to_config(".oak/config.yaml", updates)
    else:
        user_updates, project_updates = _split_by_classification(updates)
        if user_updates:
            _write_to_config(f".oak/config.{get_machine_identifier()}.yaml", user_updates)
        if project_updates:
            _write_to_config(".oak/config.yaml", project_updates)
```

The Dashboard routes call `save_ci_config(updates)` -- no changes needed at the route level. The `--project` flag maps to `force_project=True`.

### 6.9 .gitignore Changes

```gitignore
# OAK: user/machine-local config overlays (project config stays tracked)
.oak/config.*.yaml
```

This pattern ignores all machine-specific overlays while keeping `.oak/config.yaml` tracked. The `api_key: null` fields in the project config are safe since actual keys live in the user overlay or `.env`.

### 6.10 Backup/Restore Integration

User config is **included** in the machine's backup export (alongside the SQL dump):
- `BackupManager.export()` copies `.oak/config.{machine_id}.yaml` into `oak/ci/history/` alongside `{machine_id}.sql`
- `BackupManager.restore()` places the user config at `.oak/config.{machine_id}.yaml`
- On a new machine with the same GitHub user, `oak ci restore` reconstitutes both data and preferences

### 6.11 Implementation Phases

**Phase 1 (Launch -- Section 6 core):**
- Add `.oak/config.*.yaml` to `.gitignore`
- Implement `_deep_merge()` in config loading
- Add scope routing to `save_ci_config()`
- Add `--project` and `--show` flags to `oak ci config`
- Add `_migrate_split_user_config` to `oak upgrade` migrations
- Auto-create user config on first user-classified write (no empty template)
- Reset tracked `.oak/config.yaml` to project-level defaults

**Phase 2 (Post-Launch):**
- Dashboard UI: add origin badge indicators showing `[project]` / `[user]` / `[env]` next to each setting
- Create `modifying-oak-configuration` skill + add to CI feature manifest
- Include user config in backup/restore exports
- `oak ci config --diff` to show effective merged config with origin annotations

### 6.12 Security Implications

- API keys in user config are gitignored -- eliminates the L-SEC1 finding
- Project config stays clean (no nulled secrets, no debug log levels)
- `.env` remains the escape hatch for CI/CD where you need env-var-based config
- The `${ENV_VAR}` syntax for API keys still works in both project and user config
- Migration is non-destructive -- original values are preserved in the user overlay, not deleted

---

## 7. Pre-Open-Source Chores

### 7.1 Git History

- 50 commits on the current branch
- Plan to flatten history is sound -- use `git checkout --orphan` on the new public repo
- Deleted files in history include old feature structures, hook scripts, research docs -- confirms the need for a clean squash

### 7.2 Files to Fix Before Public

| File | Issue | Action |
|------|-------|--------|
| `SECURITY.md:24` | Placeholder `opensource@example.com` | Replace with real email |
| `.oak/config.yaml:175` | `log_level: DEBUG` is a user pref, not project | Move to user config; set project default to `INFO` |
| `.oak/config.yaml:72,81` | `api_key: null` fields in tracked config | Move to user config template; remove from project config |
| `oak/ci/daemon.port` | Runtime port tracked in git | Add to `.gitignore` |
| `CHANGELOG.md` | Contains `localhost:38283` links | Replace with plain text descriptions |
| `pyproject.toml:103` | GitHub URL points to `sirkirby/open-agent-kit` | Verify this is the intended public repo name |

### 7.3 Licensing

- MIT License is in place and properly referenced in `pyproject.toml`
- All Python dependencies are MIT/BSD/Apache 2.0 compatible
- Frontend dependencies (React, Radix, Tailwind, Vite) are all MIT compatible
- **No copyleft conflicts detected.**

### 7.4 CI/CD for the Public Repo

- PR check workflow is solid (lint, format, typecheck, tests, integration tests, version check)
- Release workflow needs: (a) `npm ci && npm run build` before Python build, (b) PyPI publish step
- Consider adding: OSSF Scorecard, dependency review action, CodeQL scanning

---

## 8. Launch Phases & Prioritized Action Items

### Phase 0: Blockers (Must Complete Before Public)

| # | Item | Category | Effort |
|---|------|----------|--------|
| 1 | Replace `opensource@example.com` in SECURITY.md | Chore | 5 min |
| 2 | Fix `shell=True` in `mcp/installer.py` (H-SEC1) | Security | 1-2 hrs |
| 3 | Remove env var value logging in `executor.py:202` (M-SEC4) | Security | 15 min |
| 4 | Implement user config overlay + `oak upgrade` migration (Section 6, Phase 1) | Config | 1-2 days |
| 5 | Remove debug `console.log` from `Config.tsx` | Frontend | 15 min |
| 6 | Add `oak/ci/daemon.port` to `.gitignore` | Chore | 5 min |
| 7 | Create `docs/architecture.md` (consolidate research docs) | Docs | 2-4 hrs |
| 8 | Create `docs/README.md` (documentation index) | Docs | 1 hr |
| 9 | Flatten git history onto new public repo | Chore | 1 hr |

### Phase 1: Launch Week

| # | Item | Category | Effort |
|---|------|----------|--------|
| 10 | Add PyPI publish to release workflow | Distribution | 2-4 hrs |
| 11 | Add `npm ci && npm run build` to release workflow | Distribution | 1 hr |
| 12 | Restructure README (200 lines, link to docs) | Docs | 3-4 hrs |
| 13 | Create terminal recording GIF for README + website | Docs | 2-3 hrs |
| 14 | Scaffold Astro Starlight docs site on GitHub Pages | Docs | 4-8 hrs |
| 15 | Migrate 8 CI docs + QUICKSTART + CLI ref to website | Docs | 4-6 hrs |

### Phase 2: First Month

| # | Item | Category | Effort |
|---|------|----------|--------|
| 16 | Relax Python requirement to `>=3.12` | Distribution | 1-2 days |
| 17 | Split CI constants file into domain modules (H-PY1) | Code Quality | 4-6 hrs |
| 18 | Decompose `lifespan` function (H-PY2) | Code Quality | 3-4 hrs |
| 19 | Split activity routes file (H-PY3) | Code Quality | 4-6 hrs |
| 20 | Migrate custom dialogs to `@radix-ui/react-dialog` | Frontend | 3-4 hrs |
| 21 | Extract duplicated pagination hook (`usePaginatedList`) | Frontend | 2-3 hrs |
| 22 | Add daemon API authentication (M-SEC1, M-SEC2) | Security | 1-2 days |
| 23 | Gate devtools behind config flag (M-SEC3) | Security | 2-4 hrs |
| 24 | Dashboard origin badge indicators + `modifying-oak-configuration` skill (Section 6, Phase 2) | Config | 1-2 days |
| 25 | Create per-agent setup guide pages (6 agents) | Docs | 3-4 hrs |
| 26 | Create MCP tools reference docs | Docs | 2-3 hrs |
| 27 | Create feature development guide | Docs | 3-4 hrs |
| 28 | Homebrew tap formula | Distribution | 4-6 hrs |

### Phase 3: Growth

| # | Item | Category | Effort |
|---|------|----------|--------|
| 29 | Replace broad `except Exception` catches | Code Quality | 2-3 hrs |
| 30 | Extract RetrievalEngine helpers (H-PY4) | Code Quality | 2-3 hrs |
| 31 | Convert namespace classes to `StrEnum` | Code Quality | 2-3 hrs |
| 32 | Add runtime API validation (zod/valibot) to frontend | Frontend | 4-6 hrs |
| 33 | A11y audit: skip-nav, icon labels, focus management | Frontend | 1-2 days |
| 34 | `oak ci config --diff` (show merged config with origins) | Config | 4-6 hrs |
| 35 | Docker image for evaluation/CI | Distribution | 4-6 hrs |
| 36 | Install script (`curl \| bash`) | Distribution | 2-3 hrs |
| 37 | Comparison pages (OAK vs. Greptile, Continue.dev, etc.) | Docs | 4-6 hrs |
| 38 | Video demo / tutorial | Docs | 1-2 days |
| 39 | Optional encryption at rest for activity DB | Security | 2-3 days |

---

## Approval

| Approver | Role | Status | Date |
|----------|------|--------|------|
| Chris Kirby | Project Lead | Pending | -- |

---

## References

- `oak/constitution.md` -- Project constitution and engineering standards
- `docs/codebase-intelligence/` -- Existing CI documentation (8 files)
- `docs/research/RFC-001-Codebase-Intelligence.md` -- Original CI research RFC
- `QUICKSTART.md` -- Current getting-started guide
- `CONTRIBUTING.md` -- Current contributing guide
- `SECURITY.md` -- Current security policy

---

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-06 | 0.1 | Initial draft -- comprehensive pre-launch review | AI Review (Claude) |
| 2026-02-06 | 0.2 | Added Section 6: machine-ID-based user config overlay design; replaced `.gitignore` config recommendation with proper project/user split | AI Review (Claude) |
| 2026-02-06 | 0.3 | Rewrote Section 6.6-6.12: Dashboard as primary config UI, `oak ci config` as agent-facing utility, migration via `oak upgrade`, scope routing in `save_ci_config()`, backup/restore integration | AI Review (Claude) |
| 2026-02-06 | 0.4 | Renamed config skill to `modifying-oak-configuration` per naming conventions; added skill location, manifest entry, and auto-install details via ReconcileSkillsStage | AI Review (Claude) |
