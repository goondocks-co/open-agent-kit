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

---

## 3. Security Audit

### 3.1 Findings Summary

| Severity | Count |
|----------|-------|
| Critical | 0     |
| High     | 1     |
| Medium   | 4     |
| Low      | 7     |

**No leaked secrets, no hardcoded credentials, no critical vulnerabilities found.**

### 3.2 High-Severity Finding

**H-SEC1. `shell=True` subprocess calls with template-derived commands.**
`src/open_agent_kit/features/codebase_intelligence/mcp/installer.py` lines 190-196, 198-205, 252-259.
Commands are constructed via `.format()` with values from agent manifest YAML files (server name, command strings). No sanitization or allowlist validation. A malicious manifest could inject arbitrary shell commands.
- **Fix:** Refactor to `shell=False` with explicit argument lists, or add strict alphanumeric-plus-hyphens validation on all interpolated values.

### 3.3 Medium-Severity Findings

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| M-SEC1 | No authentication on daemon API | `daemon/server.py`, all routes | Any local process has full access |
| M-SEC2 | Tunnel exposes entire API without auth | `routes/tunnel.py:76-149` | Remote data access/deletion |
| M-SEC3 | Unrestricted DevTools endpoints | `routes/devtools.py` | Data loss operations unprotected |
| M-SEC4 | API key values partially logged | `agents/executor.py:202` | First 20 chars of secrets in daemon.log |

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
- Most subprocess calls use `shell=False` with explicit args
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

### 6.6 User Config Lifecycle

**Creation:**
- `oak ci config --user` opens the user config in `$EDITOR` (creates from template if missing)
- Dashboard Settings page gets a "User Overrides" panel (writes to user config file)
- First-time init could prompt: "Your team uses Ollama for embeddings. Configure your local settings?"

**Discovery:**
- Config loading (`load_ci_config`, `OakConfig.load`) gains a merge step
- Machine ID is already cached at `.oak/ci/machine_id` and resolved via `get_machine_identifier()`
- If `.oak/config.{machine_id}.yaml` exists, deep-merge it on top of the project config

**Backup/Restore:**
- User config is **included** in the machine's backup export (alongside the SQL dump)
- On restore, the user config is placed at the correct machine-ID filename
- This means when a developer moves to a new machine with the same GitHub user, `oak ci restore` reconstitutes both their data and their preferences

### 6.7 .gitignore Changes

```gitignore
# OAK: user/machine-local config overlays (project config stays tracked)
.oak/config.*.yaml
```

This pattern ignores all machine-specific overlays while keeping `.oak/config.yaml` tracked. The `api_key: null` fields in the project config are safe since actual keys live in the user overlay or `.env`.

### 6.8 Implementation Phases

**Phase 1 (Launch):**
- Add `.oak/config.*.yaml` to `.gitignore`
- Implement merge logic in `load_ci_config()` and `OakConfig.load()`
- Add `oak ci config --user` CLI command
- Move the existing project config's `api_key: null` fields, `log_level: DEBUG`, and provider URLs to a user config template
- Reset the tracked `.oak/config.yaml` to sensible project-level defaults

**Phase 2 (Post-Launch):**
- Dashboard "User Overrides" panel
- Include user config in backup/restore
- First-time init user config wizard
- `oak ci config --diff` to show effective merged config with origin annotations

### 6.9 Security Implications

- API keys in user config are gitignored -- eliminates the L-SEC1 finding
- Project config stays clean (no nulled secrets, no debug log levels)
- `.env` remains the escape hatch for CI/CD where you need env-var-based config
- The `${ENV_VAR}` syntax for API keys still works in both project and user config

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
| 4 | Implement user config overlay (Section 6, Phase 1) | Config | 1-2 days |
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
| 24 | Dashboard "User Overrides" panel (Section 6, Phase 2) | Config | 1-2 days |
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
