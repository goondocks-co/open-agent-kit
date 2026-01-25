-- OAK Codebase Intelligence History Backup
-- Exported: 2026-01-25T11:00:40.469253
-- Schema version: 10

-- sessions (15 records)
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-23T22:55:22.705192', '2026-01-24T01:33:53.843361', 'completed', 21, 351, 1, NULL, 'Refactor codebase: eliminate duplicate constants and code smells', 1769226922);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('7f6d3606-8125-435f-829c-9edc0ff00627', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T09:34:37.954005', '2026-01-24T09:35:19.381495', 'completed', 0, 0, 0, NULL, NULL, 1769265277);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('2f667b6d-2eef-4a44-b622-eef08f97a6cc', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T09:35:25.158984', '2026-01-24T10:44:31.723856', 'completed', 3, 38, 0, NULL, 'Debug oak-ci MCP server connection error for Claude', 1769265325);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T09:47:58.426836', '2026-01-24T10:26:47.682298', 'completed', 2, 105, 0, NULL, 'Debug missing file edit capture in CI session', 1769266078);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('0d4820af-3ceb-4063-bf7e-fab36ee3e933', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T10:26:47.720878', '2026-01-24T11:39:17.063454', 'completed', 1, 63, 0, NULL, 'Add missing hooks and Copilot support for CI', 1769268407);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('b82ca70d-639b-427b-bb34-dec7756b80fb', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T16:15:08.925540', '2026-01-24T17:15:55.870247', 'completed', 11, 169, 0, NULL, 'Debug test and detect for embedding and summarization models', 1769289308);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('7ad9ce17-52f0-4ca6-8956-23573232993e', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T17:15:59.955672', '2026-01-24T17:34:42.607254', 'completed', 1, 57, 0, NULL, 'Add infrequent background task to daemon', 1769292959);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('550a7072-b6ee-420c-beb3-34a7fb891c87', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T17:34:42.645852', '2026-01-24T18:40:04.676978', 'completed', 1, 24, 0, NULL, 'Implement auto-delete empty sessions on stale recovery', 1769294082);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('f4c052d2-2753-49d2-966a-0d989a9366b4', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T17:47:20.314767', '2026-01-25T10:16:28.334558', 'completed', 1, 84, 0, NULL, 'Refactor codebase_intelligence activity module files', 1769294840);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('23a3b5d1-4021-425d-9b63-812aefc12ccd', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T17:53:41.360047', '2026-01-25T09:56:03.729616', 'completed', 2, 68, 0, NULL, 'Refactor intelligence hooks context injection', 1769295221);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('91eddd37-f8e7-460b-9915-1dedc774cf74', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T18:06:20.097373', '2026-01-24T18:37:26.358671', 'completed', 8, 124, 0, NULL, 'Debug Memorization Tab 500 Error and Card Truncation', 1769295980);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('e675ea0c-3acb-4411-b69e-92f901786a15', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-24T18:37:26.411637', '2026-01-25T09:51:29.639238', 'completed', 3, 73, 0, NULL, 'Implement dedicated Plans tab to separate from Memories', 1769297846);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('db06f42f-8d00-4c8c-a4c2-2a77a4535e5f', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-25T09:56:03.764504', NULL, 'active', 2, 75, 0, NULL, 'Implement automatic context injection for code snippets', 1769352963);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('21480a13-f486-47d0-8ab4-65b997828049', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-25T10:16:28.371347', NULL, 'active', 1, 58, 0, NULL, 'Refactor activity store modules into focused components', 1769354188);
INSERT INTO sessions (id, agent, project_root, started_at, ended_at, status, prompt_count, tool_count, processed, summary, title, created_at_epoch) VALUES ('ec07161c-37c0-454b-9b52-07ed47adadb8', 'claude', '/Users/chris/Repos/open-agent-kit', '2026-01-25T10:57:13.558733', '2026-01-25T10:59:35.775707', 'completed', 0, 0, 0, NULL, NULL, 1769356633);

-- prompt_batches (57 records)
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (1, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 1, '<task-notification>
<task-id>ac58e5f</task-id>
<status>completed</status>
<summary>Agent "Scan for duplicate constants" completed</summary>
<result>Now I have enough information to compile the comprehensive report. Here is my analysis:

---

# Duplicate Constants and Magic Strings Audit Report

## Summary

This report identifies violations of the "no magic literals" rule from `oak/constitution.md`. Issues are categorized by severity and type.

---

## 1. DUPLICATE STATUS VALUE DEFINITIONS

### Issue 1.1: Index Status Values Defined in Multiple Places

**Duplicated values:** `"idle"`, `"indexing"`, `"ready"`, `"error"`, `"completed"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 66-70 | `INDEX_STATUS_IDLE`, `INDEX_STATUS_INDEXING`, `INDEX_STATUS_READY`, `INDEX_STATUS_ERROR` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/constants.py` | 34-37 | `IndexStatus.IDLE`, `IndexStatus.INDEXING`, `IndexStatus.COMPLETED`, `IndexStatus.FAILED` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/state.py` | 62, 74, 83 | Hardcoded `"indexing"`, `"ready"`, `"error"` strings |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py`

---

### Issue 1.2: Daemon Status Values Defined in Multiple Places

**Duplicated values:** `"healthy"`, `"running"`, `"stopped"`, `"error"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 76-79 | `DAEMON_STATUS_RUNNING`, `DAEMON_STATUS_STOPPED`, `DAEMON_STATUS_HEALTHY`, `DAEMON_STATUS_UNHEALTHY` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/constants.py` | 25-28 | `DaemonStatus.HEALTHY`, `DaemonStatus.RUNNING`, `DaemonStatus.STOPPED`, `DaemonStatus.ERROR` |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py`

---

### Issue 1.3: Session/Batch Status Values Defined in Multiple Places

**Duplicated values:** `"active"`, `"completed"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/constants.py` | 48-49, 55-56 | `SessionStatus.ACTIVE`, `SessionStatus.COMPLETED`, `BatchStatus.ACTIVE`, `BatchStatus.COMPLETED` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py` | 244, 331 | Hardcoded `status: str = "active"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py` | 926, 936 | Hardcoded `"completed"`, `"active"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/index.py` | 88 | Hardcoded `status="completed"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/backup.py` | 116, 158 | Hardcoded `"status": "completed"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/devtools.py` | 164 | Hardcoded `"status": "completed"` |

**Canonical location:** Should use constants from `daemon/constants.py`

---

### Issue 1.4: Log Level Values Defined in Multiple Places

**Duplicated values:** `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 191-200 | `LOG_LEVEL_DEBUG`, `LOG_LEVEL_INFO`, `LOG_LEVEL_WARNING`, `LOG_LEVEL_ERROR`, `VALID_LOG_LEVELS` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/constants.py` | 67-72 | `LogLevels.DEBUG`, `LogLevels.INFO`, etc. |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/state.py` | 297, 524 | Hardcoded `log_level: str = "INFO"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/config.py` | 457 | Hardcoded `valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]` |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py`

---

## 2. DUPLICATE FILE PATH CONSTANTS

### Issue 2.1: Daemon File Names Defined in Multiple Places

**Duplicated values:** `"daemon.pid"`, `"daemon.port"`, `"daemon.log"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 107, 109, 110 | `CI_LOG_FILE`, `CI_PID_FILE`, `CI_PORT_FILE` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/manager.py` | 31-33 | `PID_FILE = "daemon.pid"`, `PORT_FILE = "daemon.port"`, `LOG_FILE = "daemon.log"` |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py`

---

### Issue 2.2: `.oak` Directory String Used Instead of Constant

**Duplicated value:** `".oak"`

| Location | Line(s) |
|----------|---------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/migrations.py` | 171, 213, 275 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/upgrade_service.py` | 863, 1225, 1232, 1259, 1268 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/skill_service.py` | 743 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/commands/skill_cmd.py` | 274 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/utils/file_utils.py` | 435 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/utils/command_decorators.py` | 39 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/pipeline/context.py` | 107 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/rules_management/constitution.py` | 467, 613 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/config.py` | 425 |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/constants.py` | 42 |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/config/paths.py` (line 12: `OAK_DIR = ".oak"`)

---

### Issue 2.3: Agent Directory Strings Used Instead of Constants

**Duplicated values:** `".claude"`, `".cursor"`, `".gemini"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/migrations.py` | 142, 249 | `".claude"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/upgrade_service.py` | 882, 894, 905 | `".claude"`, `".cursor"`, `".gemini"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/commands/ci_cmd.py` | 2064, 2065 | `".claude"`, `".cursor"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/service.py` | 501, 546, 606, 712, 754, 798 | `".claude"`, `".cursor"`, `".gemini"` |

**Note:** No canonical constants exist for agent directory names. They are partially defined in `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/config/paths.py` as part of file paths (e.g., `CLAUDE_SETTINGS_FILE = ".claude/settings.local.json"`).

---

## 3. DUPLICATE PROVIDER/URL CONSTANTS

### Issue 3.1: Embedding Provider Names Defined but Not Used Consistently

**Duplicated values:** `"ollama"`, `"openai"`, `"lmstudio"`, `"fastembed"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 45-54 | `PROVIDER_OLLAMA`, `PROVIDER_OPENAI`, `PROVIDER_LMSTUDIO`, `PROVIDER_FASTEMBED` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/config.py` | 48 | Hardcoded `Literal["ollama", "openai", "fastembed"]` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/embeddings/provider_chain.py` | 40, 47, 58, 68 | Hardcoded string comparisons: `if provider_type == "ollama"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/config.py` | 576, 638, 696, 705, 725, 727, 779, 811, 849, 1191, 1235, 1287, 1404 | Multiple hardcoded `"ollama"` strings |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/commands/ci_cmd.py` | 711 | Hardcoded `if emb_config.provider == "ollama"` |

**Canonical location:** `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py`

---

### Issue 3.2: Default Provider URLs Defined in Multiple Places

**Duplicated values:** `"http://localhost:11434"`, `"http://localhost:1234"`

| Location | Line(s) | Value |
|----------|---------|-------|
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py` | 60, 291 | `DEFAULT_BASE_URL`, `DEFAULT_SUMMARIZATION_BASE_URL` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/config.py` | 39-41, 706, 810, 1236, 1289, 1405 | `DEFAULT_PROVIDER_URLS` dict and hardcoded defaults in function params |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/embeddings/provider_chain.py` | 90 | Hardcoded `ollama_url: str = "http://localhost:11434"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/embeddings/ollama.py` | 34 | Hardcoded `base_url: str = "http://localhost:11434"` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/embeddings/lmstudio.py` | 35, 49 | Hardcoded `http://localhost:1234` |
| `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/embeddings/openai_compat.py` | 55 | Hardcoded `base_url: str = "http://localhost:1234/v1"` |', '2026-01-23T22:57:25.533140', '2026-01-23T22:58:59.023886', 'completed', 3, 1, 'agent_work', 'agent_notification', NULL, NULL, 1769227045, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (2, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 2, '<task-notification>
<task-id>aa94bd2</task-id>
<status>completed</status>
<summary>Agent "Scan for code smells" completed</summary>
<result>Based on my comprehensive analysis of the codebase against `oak/constitution.md` rules, here is my **Code Smell and Architectural Issues Report**:

---

# Code Smell and Architectural Issues Report

## 1. GOD CLASSES / SERVICES

### 1.1 `src/open_agent_kit/commands/ci_cmd.py` (~2190 lines)

**Description:** This command file is a mega-module containing 30+ command handlers (status, start, stop, restart, reset, logs, index, install-parsers, languages, config, exclude, debug, port, dev, mcp, search, remember, context, memories, sessions, test, backup, restore, and more).

**Why it''s a problem:** The file is difficult to navigate, test in isolation, and maintain. Changes to one command risk unintended side effects on others. The sheer size suggests it has accumulated responsibilities beyond what a command module should have.

**Constitution rule violated:** Section 3.3 "Extend, Don''t Patch" states: "Avoid growing god-services and mega-constants files. Refactor early."

---

### 1.2 `src/open_agent_kit/services/upgrade_service.py` (~1304 lines)

**Description:** UpgradeService handles: command template upgrades, agent settings management, skill installation/removal, hook management across multiple agents, MCP server management, gitignore updates, structural repairs, and migrations.

**Why it''s a problem:** This service has accumulated too many distinct responsibilities. It manages templates, hooks, MCP servers, skills, agent settings, and structural repairs all in one class. Each of these could be a separate focused service.

**Constitution rule violated:** Section 3.3 "Extend, Don''t Patch" states: "Prefer new service + registration or new strategy rather than modifying unrelated code paths. Avoid growing god-services."

---

### 1.3 `src/open_agent_kit/features/codebase_intelligence/service.py` (~1049 lines)

**Description:** CodebaseIntelligenceService handles: hook installation/removal for multiple agents, daemon lifecycle management, MCP server installation/removal, and overall CI feature orchestration.

**Why it''s a problem:** The service mixes hook management, daemon control, and MCP configuration. These are three distinct concerns that could be separate services with clear boundaries.

**Constitution rule violated:** Section 3.3 "Extend, Don''t Patch" - the service has grown to handle too many distinct responsibilities.

---

### 1.4 `src/open_agent_kit/features/codebase_intelligence/memory/store.py` (~1144 lines)

**Description:** VectorStore class manages ChromaDB collections for both code chunks and memory observations, plus plan observations. It handles embedding generation, collection management, CRUD operations for multiple data types, and search functionality.

**Why it''s a problem:** The class conflates storage operations for three different entity types (code, memories, plans) into one mega-class. Each could be a separate store with shared base infrastructure.

**Constitution rule violated:** Section 3.3 - god-service that has grown beyond a single focused responsibility.

---

## 2. LAYERING VIOLATIONS (Commands Containing Business Logic)

### 2.1 `src/open_agent_kit/commands/ci_cmd.py` - Parser Detection Logic

**Description:** The `_check_missing_parsers()` function in the command module performs business logic - scanning project files, detecting languages, checking installed parsers, and determining what needs to be installed.

**Why it''s a problem:** This is domain logic that belongs in a service layer, not the command layer. Commands should parse inputs, call services, and render output - not implement detection algorithms.

**Constitution rule violated:** Section 2.3 states: "Commands should remain thin: parse inputs, call services, render output. Services own business logic."

---

### 2.2 `src/open_agent_kit/commands/ci_cmd.py` - Parser Installation Logic

**Description:** The `install_parsers` command contains logic for determining which parsers to install, checking existing installations, and orchestrating the installation process inline.

**Why it''s a problem:** Installation orchestration logic is business logic that should reside in a ParserService or similar, not embedded in command handlers.

**Constitution rule violated:** Section 2.3 and Section 3.1 layering rules.

---

### 2.3 `src/open_agent_kit/commands/ci_cmd.py` - Embedding Provider Validation

**Description:** Commands directly interact with embedding providers to validate connectivity and discover models, rather than delegating to a service.

**Why it''s a problem:** Provider validation and model discovery are service-layer concerns. The command layer is doing too much work.

**Constitution rule violated:** Section 2.3 - commands should be thin wrappers.

---

## 3. TYPE SAFETY ISSUES (Dataclasses Instead of Pydantic)

### 3.1 `src/open_agent_kit/features/codebase_intelligence/memory/store.py`

**Description:** Uses `@dataclass` for `CodeChunk`, `MemoryObservation`, and `PlanObservation` instead of Pydantic models.

**Why it''s a problem:** These data structures cross boundaries (storage layer to service layer to API responses). Pydantic provides validation, serialization, and better type coercion. Dataclasses lack runtime validation.

**Constitution rule violated:** Section 4.2 states: "Prefer Pydantic models and enums over raw dicts and string lists. If a value crosses a boundary (CLI to config to storage to templates), it must be centralized and typed."

---

### 3.2 `src/open_agent_kit/features/codebase_intelligence/activity/store.py`

**Description:** Uses `@dataclass` for `Activity`, `PromptBatch`, `Session`, and `StoredObservation`.

**Why it''s a problem:** These models represent data that moves between storage, services, and API responses. They would benefit from Pydantic''s validation and serialization capabilities.

**Constitution rule violated:** Section 4.2 - prefer Pydantic models for data that crosses boundaries.

---

### 3.3 `src/open_agent_kit/features/codebase_intelligence/daemon/state.py`

**Description:** Uses `@dataclass` for `DaemonState`, `IndexStatus`, `SessionInfo`, and `ToolExecution`.

**Why it''s a problem:** These are state objects shared across the daemon. While dataclasses are typed, Pydantic would provide validation when deserializing from storage or API calls.

**Constitution rule violated:** Section 4.2 - Pydantic preferred for typed data structures.

---

### 3.4 `src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py`

**Description:** Uses `@dataclass` for `RetrievalConfig`, `SearchResult`, `FetchResult`, and `ContextResult`.

**Why it''s a problem:** These result types are returned to callers and may be serialized to JSON for API responses. Pydantic models would provide better serialization and validation.

**Constitution rule violated:** Section 4.2 - prefer Pydantic models.

---

### 3.5 `src/open_agent_kit/services/upgrade_service.py`

**Description:** Uses numerous `TypedDict` definitions for upgrade plan structures instead of Pydantic models.

**Why it''s a problem:** TypedDict provides type hints but no runtime validation. These plan structures drive upgrade operations and would benefit from Pydantic''s validation.

**Constitution rule violated:** Section 4.2 - prefer Pydantic models over raw dicts.

---

## 4. MISSING ABSTRACTIONS (Duplicated Logic)

### 4.1 `src/open_agent_kit/features/codebase_intelligence/service.py` - Agent-Specific Hook Methods

**Description:** The service has six nearly identical methods following the pattern:
- `_update_claude_hooks()`, `_update_cursor_hooks()`, `_update_gemini_hooks()`
- `_remove_claude_hooks()`, `_remove_cursor_hooks()`, `_remove_gemini_hooks()`

**Why it''s a problem:** This is repeated logic that could be abstracted into a single parameterized method or a strategy pattern. Adding a new agent requires adding two more methods with the same structure.

**Constitution rule violated:** Section 3.3 "Extend, Don''t Patch" - prefer new strategy over code duplication. Also violates DRY principle.

---

### 4.2 `src/open_agent_kit/services/upgrade_service.py` - Hook Management Duplication

**Description:** Similar to the CI service, upgrade_service has agent-specific hook upgrade methods that share significant structure.

**Why it''s a problem:** Adding a new agent requires updating multiple places with similar logic. A unified hook management abstraction is missing.

**Constitution rule violated:** Section 2.2 "Add a New Agent" suggests implementing like existing agents, but the current structure makes this tedious and error-prone.

---

## 5. INCONSISTENT PATTERNS

### 5.1 Model Definition Approach Inconsistency

**Description:** Some parts of the codebase use Pydantic models (e.g., `src/open_agent_kit/models/`), while the CI feature predominantly uses dataclasses. This creates inconsistency within the same project.

**Why it''s a problem:** Contributors must learn two different patterns. It''s unclear when to use which approach. The constitution explicitly prefers Pydantic.

**Constitution rule violated:** Section 4.2 establishes Pydantic as the preferred approach, but it''s not consistently applied.

---

### 5.2 Command Structure Inconsistency

**Description:** `skill_cmd.py` (~287 lines) follows the thin-command pattern well - it delegates to SkillService. However, `ci_cmd.py` (~2190 lines) embeds significant business logic.

**Why it''s a problem:** There''s no consistent standard being followed. New contributors might copy either pattern, leading to further inconsistency.

**Constitution rule violated:** Section 2.3 defines the pattern, but `ci_cmd.py` doesn''t follow it while `skill_cmd.py` does.

---

### 5.3 Return Type Inconsistency in Retrieval Engine

**Description:** Some methods in `retrieval/engine.py` return dataclass instances while others return raw dictionaries.

**Why it''s a problem:** ', '2026-01-23T22:58:59.092624', '2026-01-23T23:09:09.275459', 'completed', 31, 1, 'agent_work', 'agent_notification', NULL, NULL, 1769227139, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (3, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 3, '<task-notification>
<task-id>a5236f8</task-id>
<status>completed</status>
<summary>Agent "Scan for dead code" completed</summary>
<result>Now I have enough information to produce the comprehensive dead code analysis. Let me compile the report.

---

# Dead Code Analysis Report

## Directories Analyzed
- `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/`
- `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/services/`
- `/Users/chris/Repos/open-agent-kit/src/open_agent_kit/commands/`

---

## 1. UNUSED CONSTANTS

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/constants.py

| Line | Constant | Confidence | Notes |
|------|----------|------------|-------|
| 38 | `COLLECTION_CODE` | HIGH | Defined but never imported or used anywhere in the codebase. The actual collection names `CODE_COLLECTION = "oak_code"` and `MEMORY_COLLECTION = "oak_memory"` are defined locally in `memory/store.py` instead. |
| 39 | `COLLECTION_MEMORY` | HIGH | Same as above - defined but not used. |

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/config.py

| Line | Constant | Confidence | Notes |
|------|----------|------------|-------|
| 65 | `DEFAULT_EMBEDDING_MAX_CHUNK_CHARS` | HIGH | Defined but never referenced. `EmbeddingConfig.get_max_chunk_chars()` calculates from `context_tokens` or uses a hardcoded fallback, not this constant. |
| 66 | `DEFAULT_EMBEDDING_DIMENSIONS` | HIGH | Defined but never used anywhere. Dimensions are auto-detected from the embedding provider. |

---

## 2. UNUSED TYPE ALIASES

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/config.py

| Line | Type | Confidence | Notes |
|------|------|------------|-------|
| 48 | `ProviderType = Literal["ollama", "openai", "fastembed"]` | MEDIUM | This type alias is only used in the TypeScript UI (`config-components.tsx`), not in the Python code where it''s defined. The Python code uses string comparisons against `VALID_PROVIDERS` tuple instead. |

---

## 3. UNUSED FUNCTIONS/METHODS

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py

| Line | Function/Method | Confidence | Notes |
|------|-----------------|------------|-------|
| 232-264 | `RetrievalEngine.get_confidence_stats()` | HIGH | Static method defined but never called anywhere in the codebase. Described as "useful for debugging and UI display" but not actually used. |
| 638-706 | `RetrievalEngine.search_index()` | HIGH | Part of "Layer 1" progressive disclosure pattern but never called. The `search()` method is used instead. |
| 708-780 | `RetrievalEngine.get_chunk_context()` | HIGH | Part of "Layer 2" progressive disclosure pattern but never called anywhere. |
| 782-833 | `RetrievalEngine.fetch_full()` | HIGH | Part of "Layer 3" progressive disclosure pattern but never called. The `fetch()` method is used instead. |

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/memory/store.py

| Line | Property | Confidence | Notes |
|------|----------|------------|-------|
| 163-165 | `CodeChunk.short_path` property | HIGH | Property defined but never accessed outside the class. The `get_short_path()` helper function is also defined (line 115-128) but only called by this unused property. |
| 115-128 | `get_short_path()` function | HIGH | Only called by the unused `short_path` property above. |

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/indexing/chunker.py

| Line | Function | Confidence | Notes |
|------|----------|------------|-------|
| 668-679 | `chunk_file()` standalone function | HIGH | Convenience function defined at module level but never imported or called anywhere. All callers use `CodeChunker().chunk_file()` instance method instead. |

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py

| Line | Class | Confidence | Notes |
|------|-------|------------|-------|
| 91-97 | `RetrievalConfig` dataclass | MEDIUM | This class is defined and instantiated as a default in `RetrievalEngine.__init__()`, but no caller ever passes a custom `RetrievalConfig` - they all rely on the defaults. The class itself is not directly unused, but its customization capability is never leveraged. |

---

## 4. UNUSED IMPORTS

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py

| Line | Import | Confidence | Notes |
|------|--------|------------|-------|
| 15 | `from datetime import datetime` | HIGH | Imported but never used in the file. The `remember()` method uses `datetime.now()` but gets `datetime` via the `MemoryObservation` dataclass which has its own import. |

---

## 5. POTENTIALLY UNUSED CODE (Lower Confidence)

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/config.py

| Line | Item | Confidence | Notes |
|------|------|------------|-------|
| 574-580 | `CIConfig.get_user_exclude_patterns()` method | LOW | Method exists but I found no calls to it in the codebase search. However, it may be used for display purposes in UI routes not analyzed. |

### /Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/indexing/chunker.py

| Line | Item | Confidence | Notes |
|------|------|------------|-------|
| 262-269 | `CodeChunker.reset_stats()` method | LOW | Method exists but no external callers found. May be intended for future use or testing. |

---

## Summary

| Category | High Confidence | Medium Confidence | Low Confidence |
|----------|-----------------|-------------------|----------------|
| Unused Constants | 4 | 0 | 0 |
| Unused Type Aliases | 0 | 1 | 0 |
| Unused Functions/Methods | 7 | 1 | 2 |
| Unused Imports | 1 | 0 | 0 |
| **Total** | **12** | **2** | **2** |

---

## Notes

1. **Progressive Disclosure Methods**: The `search_index()`, `get_chunk_context()`, and `fetch_full()` methods in `RetrievalEngine` appear to be part of a planned "3-layer progressive disclosure" pattern (documented in the class docstring) that was never fully implemented. The simpler `search()` and `fetch()` methods are used instead.

2. **Collection Name Constants**: The `COLLECTION_CODE` and `COLLECTION_MEMORY` constants in `constants.py` suggest an intent to centralize collection names, but the actual values (`"oak_code"` and `"oak_memory"`) are hardcoded in `memory/store.py` instead.

3. **No Commented-Out Code Blocks**: I did not find significant commented-out code blocks in the analyzed files. The codebase appears clean in this regard.</result>
</task-notification>
Full transcript available at: /private/tmp/claude/-Users-chris-Repos-open-agent-kit/tasks/a5236f8.output', '2026-01-23T23:09:09.377745', '2026-01-23T23:09:15.902101', 'completed', 0, 1, NULL, 'agent_notification', NULL, NULL, 1769227749, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (4, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'can you verify that this index file count and chunks (approximate) are accurate. meaning, its ignoring what it should and indexing what it should. the file count is higher than expected. also ensure that that the ui is showing accurate numbers and they are updated as they change. related to that, ensure the file watcher is doing what it should be as well', '2026-01-23T23:15:47.489568', '2026-01-23T23:27:44.943446', 'completed', 50, 1, 'exploration', 'user', NULL, NULL, 1769228147, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (5, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'excellent. i see the indexing is still running but the UI states "ready", are we sure the ui is updating correctly based on indexer and file watcher activity on the dashboard?', '2026-01-23T23:31:05.497512', NULL, 'completed', 20, 1, 'implementation', 'user', NULL, NULL, 1769229065, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (6, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'excellent, and how about the file watcher, which shows pending files on the dashboard, really all real-time updates in the ui, just checking for accuracy, but especially want file operations to be accurate', '2026-01-23T23:36:28.575265', '2026-01-23T23:38:57.899630', 'completed', 12, 1, 'exploration', 'user', NULL, NULL, 1769229388, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (7, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'sounds good. i''m looking for ways to improve the memories ux. its functional, but as memories grow, its hard to manage. shoudl there be filters? perhaps by hash tag? i know we have search as well, but memories pulls from sqllite, and we should ensure that we have good indexes on in sqllite to keep things performant. propose some ideas for improvement', '2026-01-23T23:45:34.473150', '2026-01-23T23:46:42.651031', 'completed', 8, 1, 'exploration', 'user', NULL, NULL, 1769229934, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (8, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'yes, excellent suggestions, build a todo so they can be tracked and i''m assuming for the db indexes and other updates, that we''ll support proper migrations for new and upgraded instances. approved for the full 1-7', '2026-01-23T23:48:37.232591', NULL, 'completed', 20, 1, 'refactoring', 'user', NULL, NULL, 1769230117, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (9, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'yes, of course. complete the remaining work', '2026-01-24T00:01:30.526840', NULL, 'completed', 10, 1, 'implementation', 'user', NULL, NULL, 1769230890, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (10, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'i''m not seeing the changes. i ram make ui-build and oak ci restart, but it looks the same to me', '2026-01-24T00:14:58.577550', NULL, 'completed', 10, 1, 'exploration', 'user', NULL, NULL, 1769231698, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (11, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 11, 'i''ve done a hard refresh, no change', '2026-01-24T00:18:02.099433', NULL, 'completed', 0, 1, 'exploration', 'user', NULL, NULL, 1769231882, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (12, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 12, 'how could that be, not supposed to be possible.. make setup and make tool-reinstall .. so what happened?', '2026-01-24T00:21:51.484106', '2026-01-24T00:23:33.111189', 'completed', 3, 1, 'exploration', 'user', NULL, NULL, 1769232111, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (13, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 13, 'ok, we never want any make command that isn''t for local developmnt, its the only reason it exists.. actual users of oak will us uv install git url.. this just keeps happening and its driving me crazy, so we need to get it right', '2026-01-24T00:25:20.841861', '2026-01-24T00:26:07.017473', 'completed', 6, 1, 'implementation', 'user', NULL, NULL, 1769232320, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (14, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 14, 'well now the oak command is now found', '2026-01-24T00:26:51.646579', '2026-01-24T00:26:57.198788', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769232411, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (15, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 15, 'i use the oak command to start and restart.. the make command just do the editible oak install, what am i missing?', '2026-01-24T00:27:34.007661', '2026-01-24T00:27:53.834758', 'completed', 1, 1, 'exploration', 'user', NULL, NULL, 1769232454, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (16, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 16, 'which oak
/Users/chris/Repos/open-agent-kit/.venv/bin/oak ,, but then i try: oak ci
zsh: command not found: oak', '2026-01-24T00:29:04.775884', '2026-01-24T00:29:12.640847', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769232544, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (17, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 17, 'that did not work.. what the hell is going on? this has not happened before', '2026-01-24T00:29:50.970233', '2026-01-24T00:30:11.713804', 'completed', 1, 1, 'exploration', 'user', NULL, NULL, 1769232590, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (18, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 18, 'done it several times, still doesn''t change anything', '2026-01-24T00:31:12.903795', '2026-01-24T00:31:56.349597', 'completed', 1, 1, 'exploration', 'user', NULL, NULL, 1769232672, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (19, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 19, 'isn''t the virual env activated or its not, why would the different terminal windows matter?', '2026-01-24T00:32:45.038479', '2026-01-24T00:32:57.047371', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769232765, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (20, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 20, 'i''m not looking for a quick fix, i just want it fixed', '2026-01-24T00:33:01.588478', '2026-01-24T00:33:29.694749', 'completed', 2, 1, 'exploration', 'user', NULL, NULL, 1769232781, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (21, '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 21, 'ok so what is the dev loop then moving forward?', '2026-01-24T00:34:19.897705', '2026-01-24T00:34:27.742596', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769232859, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (22, '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 1, 'lets figure out why the oak-ci mcp server configured for claude is not working. we are dogfooding oak ci in this project and i see that claude code give me a failed to connect error. lets confirm the mcp server is configured correctly @src/open_agent_kit/features/codebase_intelligence/mcp/ and which then gets installed @.claude/settings.json ', '2026-01-24T09:38:36.828960', '2026-01-24T09:41:31.537242', 'completed', 30, 1, 'implementation', 'user', NULL, NULL, 1769265516, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (23, '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 2, 'ok, so when i run oak init, and then install the ci feature, which then is supposed to install the additional dependencies that oak ci requires, that sould now work properly, right?', '2026-01-24T09:42:10.887625', '2026-01-24T09:42:59.305761', 'completed', 6, 1, 'exploration', 'user', NULL, NULL, 1769265730, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (24, '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 3, 'for development, i never run uv or pip directly, only my makefile commands', '2026-01-24T09:43:30.106472', '2026-01-24T09:43:51.728554', 'completed', 2, 1, 'exploration', 'user', NULL, NULL, 1769265810, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (25, '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 1, 'I''ve notice that for session 2f667b6d-2eef-4a44-b622-eef08f97a6cc in oak ci, there was activity that we did not capture that could be valuable. for example, none of the file edits were capture via hooks and i would like to understand why. we have a post tool hook. you can query the sqllite database foro that sesssion to see what we captured and recorded via hooks and here is the complete claude code sessoin transcript:                                                                                                     
⏺ I''ll investigate the MCP server configuration for oak-ci. Let me look at the relevant files.      
                                                                                                    
⏺ Search(pattern: ".claude/**/*.json")                                                              
  ⎿  Found 2 files (ctrl+o to expand)                                                               
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ Search(pattern: "src/open_agent_kit/features/codebase_intelligence/mcp/claude/*")                 
  ⎿  Found 2 files (ctrl+o to expand)                                                               
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ Search(pattern: "**/.mcp.json")                                                                   
  ⎿  Found 1 file (ctrl+o to expand)                                                                
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ Bash(claude mcp list 2>&1)                                                                        
  ⎿  Checking MCP server health...                                                                  
                                                                                                    
     plugin:context7:context7: npx -y @upstash/context7-mcp - ✓ Connected                           
     … +4 lines (ctrl+o to expand)                                                                  
  ⎿  Running PostToolUse hooks… (0/2 done)                                                          
                                                                                                    
⏺ The configuration looks correct. The .mcp.json is properly configured, but the server is failing  
  to connect. Let me verify the oak command is available and test the MCP server directly.          
                                                                                                    
⏺ Bash(oak ci mcp --project /Users/chris/Repos/open-agent-kit --help 2>&1 || echo "Exit code: $?")  
  ⎿   Usage: oak ci mcp [OPTIONS]                                                                   
                                                                                                    
      Run the MCP protocol server for native tool discovery.                                        
     … +27 lines (ctrl+o to expand)                                                                 
  ⎿  Running PostToolUse hooks… (0/2 done)                                                          
                                                                                                    
⏺ The help message reveals the issue: "The MCP server requires the CI daemon to be running (oak ci  
  start)." Let me check if the daemon is running.                                                   
                                                                                                    
⏺ Bash(curl -sf http://localhost:38283/api/health 2>&1 || echo "Daemon not responding on port       
      38283")                                                                                       
  ⎿  {                                                                                              
       "status": "healthy",                                                                         
       "version": "1.0.0",                                                                          
     … +3 lines (ctrl+o to expand)                                                                  
  ⎿  Running PostToolUse hooks… (0/2 done)                                                          
                                                                                                    
⏺ The daemon is running and healthy. The issue must be with the MCP server initialization. Let me   
  test running the MCP server directly to see what error occurs.                                    
                                                                                                    
⏺ Bash(timeout 5 oak ci mcp --project /Users/chris/Repos/open-agent-kit 2>&1 || echo "Exit code:    
      $?")                                                                                          
  ⎿  (eval):1: command not found: timeout                                                           
     Exit code: 127                                                                                 
  ⎿  Running PostToolUse hooks… (0/2 done)                                                          
                                                                                                    
⏺ Bash((oak ci mcp --project /Users/chris/Repos/open-agent-kit &) && sleep 2 && kill $! 2>/dev/null;
       echo "done")                                                                                 
  ⎿  Error: Exit code 144                                                                           
     ✗ MCP server not available: No module named ''mcp''                                              
     ℹ Install the mcp package: pip install mcp                                                     
                                                                                                    
⏺ Found the issue. The MCP server requires the mcp Python package which is not installed in the oak 
  environment. Let me verify the installation setup.                                                
                                                                                                    
⏺ Read(pyproject.toml)                                                                              
  ⎿  Read 100 lines                                                                                 
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ Search(pattern: "mcp", path: "pyproject.toml", output_mode: "content")                            
  ⎿  Found 1 line (ctrl+o to expand)                                                                
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ Bash(/Users/chris/Repos/open-agent-kit/.venv/bin/python -c "import mcp; print(mcp.__version__)"   
      2>&1)                                                                                         
  ⎿  Error: Exit code 1                                                                             
     Traceback (most recent call last):                                                             
       File "<string>", line 1, in <module>                                                         
         import mcp; print(mcp.__version__)                                                         
         ^^^^^^^^^^                                                                                 
     ModuleNotFoundError: No module named ''mcp''                                                     
                                                                                                    
⏺ The mcp package is missing from the codebase-intelligence dependency group. Let me check the      
  correct package name and version requirement.                                                     
                                                                                                    
⏺ Bash(pip index versions mcp 2>&1 | head -10 || pip search mcp 2>&1 | head -10)                    
  ⎿ (eval):1: /opt/homebrew/bin/pip: bad interpreter: /opt/homebrew/opt/python@3.11/bin/python3     
    .11: no such file or directory                                                                  
                                                                                                    
  ⎿  Running PostToolUse hooks… (0/2 done)                                                          
                                                                                                    
⏺ Read(src/open_agent_kit/features/codebase_intelligence/daemon/mcp_server.py)                      
  ⎿  Read 60 lines                                                                                  
  ⎿  Running PostToolUse hooks… (0/3 done)                                                          
                                                                                                    
⏺ You''re right. The mcp package is used by the CI feature (mcp_server.py imports from               
  mcp.server.fastmcp import FastMCP), so it should be included in the codebase-intelligence optional
   dependency group. It''s missing.                                                                  
                                                                                   ', '2026-01-24T09:51:17.516035', '2026-01-24T09:53:32.109021', 'completed', 18, 1, 'exploration', 'user', NULL, NULL, 1769266277, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (26, '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 2, 'yes, we should definitely add those to our @src/open_agent_kit/features/codebase_intelligence/hooks/ config and install, then we can update this project and test. you say though that the file edits were capture, but in the daemon ui, i don''t see them .. after verification vs what is stored and then what is viewed, lets plan out the work to add the additional hooks', '2026-01-24T09:58:16.075690', '2026-01-24T10:26:47.681951', 'completed', 87, 1, 'plan', 'plan', '/Users/chris/.claude/plans/ancient-churning-flurry.md', '# Plan: Add Missing Hooks and Copilot Support for CI Activity Capture

## Summary

**Phase 1: Add new hook events** (PostToolUseFailure, SubagentStart, SubagentStop)
**Phase 2: Add full Copilot support** (new agent, full hook configuration)
**Phase 3: UI enhancements** (better failure visualization, subagent grouping)

## Agent Hook Support Matrix

| Event | Claude | Cursor | Gemini | Copilot |
|-------|--------|--------|--------|---------|
| SessionStart | ✓ | ✓ | ✓ | ✓ (NEW) |
| UserPromptSubmit | ✓ | ✓ | ❌ | ✓ (NEW) |
| PostToolUse | ✓ | ✓ | ✓ | ✓ (NEW) |
| **PostToolUseFailure** | **ADD** | **ADD** | ❌ | ✓ (NEW) |
| **SubagentStart** | **ADD** | **ADD** | ❌ | ❌ |
| **SubagentStop** | **ADD** | **ADD** | ❌ | ❌ |
| Stop | ✓ | ✓ | ✓ | ❌ |
| SessionEnd | ✓ | ✓ | ✓ | ✓ (NEW) |

Notes:
- Gemini doesn''t have failure or subagent events
- Copilot has "Error Occurred" which maps to our failure tracking
- Copilot doesn''t have subagent events

---

## Phase 1: New Hook Events

### Files to Modify

#### 1.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add after line 212:
```python
HOOK_EVENT_POST_TOOL_USE_FAILURE: Final[str] = "post-tool-use-failure"
HOOK_EVENT_SUBAGENT_START: Final[str] = "subagent-start"
HOOK_EVENT_SUBAGENT_STOP: Final[str] = "subagent-stop"
```

Add after line 229:
```python
HOOK_FIELD_AGENT_ID: Final[str] = "agent_id"
HOOK_FIELD_AGENT_TYPE: Final[str] = "agent_type"
HOOK_FIELD_AGENT_TRANSCRIPT_PATH: Final[str] = "agent_transcript_path"
HOOK_FIELD_STOP_HOOK_ACTIVE: Final[str] = "stop_hook_active"
```

#### 1.2 Route Handlers (`src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py`)

Add 3 new route handlers following existing patterns:

**Route 1: `/api/oak/ci/post-tool-use-failure`**
- Mirror `hook_post_tool_use` but always `success=False`
- Log prominently: `[TOOL-FAILURE] {tool_name}`

**Route 2: `/api/oak/ci/subagent-start`**
- Track subagent spawn (agent_id, agent_type)
- Log: `[SUBAGENT-START] type={agent_type}`

**Route 3: `/api/oak/ci/subagent-stop`**
- Track subagent completion (agent_id, agent_transcript_path)
- Log: `[SUBAGENT-STOP] type={agent_type}`

#### 1.3 Claude Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/claude/hooks.json`)

Add after "SessionEnd" block:
```json
"PostToolUseFailure": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), tool_name: .tool_name, tool_input: .tool_input, tool_use_id: .tool_use_id, hook_event_name: \"PostToolUseFailure\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/post-tool-use-failure -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStart": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_type: .agent_type, hook_event_name: \"SubagentStart\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-start -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStop": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_transcript_path: .agent_transcript_path, stop_hook_active: .stop_hook_active, hook_event_name: \"SubagentStop\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-stop -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 15
    }]
  }
]
```

#### 1.4 Cursor Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/hooks.json`)

Add new hook entries for:
- `postToolUseFailure` → `/api/oak/ci/post-tool-use-failure`
- `subagentStart` → `/api/oak/ci/subagent-start`
- `subagentStop` → `/api/oak/ci/subagent-stop`

#### 1.5 Cursor Hook Script (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/oak-ci-hook.sh`)

Add cases:
```bash
postToolUseFailure)
  # POST to /api/oak/ci/post-tool-use-failure with tool_name, tool_input, error_message
  ;;
subagentStart)
  # POST to /api/oak/ci/subagent-start with agent_id, agent_type (subagent_type)
  ;;
subagentStop)
  # POST to /api/oak/ci/subagent-stop with agent_id, agent_transcript_path, status
  ;;
```

---

## Phase 2: Full Copilot Support (NEW AGENT)

### Files to Create/Modify

#### 2.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add to `SUPPORTED_HOOK_AGENTS`:
```python
AGENT_COPILOT: Final[str] = "copilot"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
    AGENT_COPILOT,  # NEW
)
```

#### 2.2 New Hooks Directory

Create: `src/open_agent_kit/features/codebase_intelligence/hooks/copilot/`

**hooks.json** (Copilot format - different from Claude/Cursor):
```json
{
  "$comment": "Codebase Intelligence hooks for GitHub Copilot. {{PORT}} and {{PROJECT_ROOT}} are replaced.",
  "hooks": {
    "session_start": {
      "command": "{{PROJECT_ROOT}}/.copilot/hooks/oak-ci-hook.sh session_start"
    },
    "session_end": {
      "command": "{{PROJECT_ROOT}}/.copilot/hooks/oak-ci-hook.sh session_end"
    },
    "user_prompt_submitted": {
      "command": "{{PROJECT_ROOT}}/.copilot/hooks/oak-ci-hook.sh user_prompt_submitted"
    },
    "post_tool_use": {
      "command": "{{PROJECT_ROOT}}/.copilot/hooks/oak-ci-hook.sh post_tool_use"
    },
    "error_occurred": {
      "command": "{{PROJECT_ROOT}}/.copilot/hooks/oak-ci-hook.sh error_occurred"
    }
  }
}
```

**oak-ci-hook.sh** (script to dispatch to CI daemon):
```bash
#!/bin/bash
EVENT="${1:-unknown}"
INPUT="$(cat || true)"
PORT="{{PORT}}"
PROJECT_ROOT="{{PROJECT_ROOT}}"
# ... similar pattern to cursor hook script
```

#### 2.3 Service Updates (`src/open_agent_kit/features/codebase_intelligence/service.py`)

Add Copilot installation methods:
- `_update_copilot_settings()`
- `_remove_copilot_hooks()`
- Install to `.copilot/hooks/` directory

---

## Phase 3: UI Enhancements (Deferred)

The current UI already handles failures (red icons, error messages). Future enhancements:

1. **Failure Filter** - Add toggle to show only failed activities
2. **Subagent Grouping** - Show subagent activities nested under parent
3. **Subagent Badge** - Visual indicator for subagent-related activities
4. **Transcript Link** - Link to subagent transcript file

**Note:** Defer UI changes to a follow-up PR to keep this PR focused on hook infrastructure.

---

## Implementation Order

1. **constants.py** - Add new constants and AGENT_COPILOT (~5 mins)
2. **hooks.py** - Add 3 route handlers (~30 mins)
3. **hooks/claude/hooks.json** - Add 3 hook configs (~10 mins)
4. **hooks/cursor/** - Update hooks.json + oak-ci-hook.sh (~15 mins)
5. **hooks/copilot/** - Create new directory with hooks.json + oak-ci-hook.sh (~20 mins)
6. **service.py** - Add Copilot installation methods (~20 mins)
7. **Test** - Enable hooks and verify across agents (~30 mins)

---

## Verification

### 1. Hook installation
```bash
# Re-install hooks for this project
oak ci enable --force

# Verify Claude hooks (should show 8 events)
cat .claude/settings.json | jq ''.hooks | keys''

# Verify Cursor hooks
cat .cursor/hooks.json | jq ''.hooks | keys''
```

### 2. Integration test
```bash
# Start new session, trigger:
# - Tool failure (read non-existent file)
# - Subagent (use Task tool with Explore)

# Check logs
tail -50 .oak/ci/hooks.log | grep -E "(TOOL-FAILURE|SUBAGENT)"

# Query database
sqlite3 .oak/ci/activities.db "SELECT tool_name, success FROM activities ORDER BY id DESC LIMIT 20"
```

### 3. Daemon UI
- Open http://localhost:38283
- Check Timeline shows failed activities with red indicators
- Verify new activity types appear

---

## Risk Assessment

**Low risk:**
- Adding new routes and hook configs doesn''t affect existing hooks
- New hooks fail gracefully (curl errors suppressed)
- No database schema changes (activities table already has `success` field)
- Copilot is additive (new agent, doesn''t modify existing)

---

## Non-goals (defer to future PRs)

- **PreToolUse** - Requires permission decision UI
- **PreCompact** - Complex conversation state handling
- **Notification** - Lower value for CI analysis
- **Transcript parsing** - SubagentStop could read transcripts, defer
- **UI enhancements** - Keep this PR focused on hook infrastructure
', 1769266696, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (27, '0d4820af-3ceb-4063-bf7e-fab36ee3e933', 1, 'Implement the following plan:

# Plan: Add Missing Hooks and Copilot Support for CI Activity Capture

## Summary

**Phase 1: Add new hook events** (PostToolUseFailure, SubagentStart, SubagentStop)
**Phase 2: Add full Copilot support** (new agent, full hook configuration)
**Phase 3: UI enhancements** (better failure visualization, subagent grouping)

## Agent Hook Support Matrix

| Event | Claude | Cursor | Gemini | Copilot |
|-------|--------|--------|--------|---------|
| SessionStart | ✓ | ✓ | ✓ | ✓ (NEW) |
| UserPromptSubmit | ✓ | ✓ | ❌ | ✓ (NEW) |
| PostToolUse | ✓ | ✓ | ✓ | ✓ (NEW) |
| **PostToolUseFailure** | **ADD** | **ADD** | ❌ | ✓ (NEW) |
| **SubagentStart** | **ADD** | **ADD** | ❌ | ❌ |
| **SubagentStop** | **ADD** | **ADD** | ❌ | ❌ |
| Stop | ✓ | ✓ | ✓ | ❌ |
| SessionEnd | ✓ | ✓ | ✓ | ✓ (NEW) |

Notes:
- Gemini doesn''t have failure or subagent events
- Copilot has "Error Occurred" which maps to our failure tracking
- Copilot doesn''t have subagent events

---

## Phase 1: New Hook Events

### Files to Modify

#### 1.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add after line 212:
```python
HOOK_EVENT_POST_TOOL_USE_FAILURE: Final[str] = "post-tool-use-failure"
HOOK_EVENT_SUBAGENT_START: Final[str] = "subagent-start"
HOOK_EVENT_SUBAGENT_STOP: Final[str] = "subagent-stop"
```

Add after line 229:
```python
HOOK_FIELD_AGENT_ID: Final[str] = "agent_id"
HOOK_FIELD_AGENT_TYPE: Final[str] = "agent_type"
HOOK_FIELD_AGENT_TRANSCRIPT_PATH: Final[str] = "agent_transcript_path"
HOOK_FIELD_STOP_HOOK_ACTIVE: Final[str] = "stop_hook_active"
```

#### 1.2 Route Handlers (`src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py`)

Add 3 new route handlers following existing patterns:

**Route 1: `/api/oak/ci/post-tool-use-failure`**
- Mirror `hook_post_tool_use` but always `success=False`
- Log prominently: `[TOOL-FAILURE] {tool_name}`

**Route 2: `/api/oak/ci/subagent-start`**
- Track subagent spawn (agent_id, agent_type)
- Log: `[SUBAGENT-START] type={agent_type}`

**Route 3: `/api/oak/ci/subagent-stop`**
- Track subagent completion (agent_id, agent_transcript_path)
- Log: `[SUBAGENT-STOP] type={agent_type}`

#### 1.3 Claude Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/claude/hooks.json`)

Add after "SessionEnd" block:
```json
"PostToolUseFailure": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), tool_name: .tool_name, tool_input: .tool_input, tool_use_id: .tool_use_id, hook_event_name: \"PostToolUseFailure\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/post-tool-use-failure -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStart": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_type: .agent_type, hook_event_name: \"SubagentStart\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-start -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStop": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_transcript_path: .agent_transcript_path, stop_hook_active: .stop_hook_active, hook_event_name: \"SubagentStop\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-stop -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 15
    }]
  }
]
```

#### 1.4 Cursor Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/hooks.json`)

Add new hook entries for:
- `postToolUseFailure` → `/api/oak/ci/post-tool-use-failure`
- `subagentStart` → `/api/oak/ci/subagent-start`
- `subagentStop` → `/api/oak/ci/subagent-stop`

#### 1.5 Cursor Hook Script (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/oak-ci-hook.sh`)

Add cases:
```bash
postToolUseFailure)
  # POST to /api/oak/ci/post-tool-use-failure with tool_name, tool_input, error_message
  ;;
subagentStart)
  # POST to /api/oak/ci/subagent-start with agent_id, agent_type (subagent_type)
  ;;
subagentStop)
  # POST to /api/oak/ci/subagent-stop with agent_id, agent_transcript_path, status
  ;;
```

---

## Phase 2: Full Copilot Support (NEW AGENT)

Copilot hooks are stored in `.github/hooks/*.json` per GitHub docs:
https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/use-hooks

### Files to Create/Modify

#### 2.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add to `SUPPORTED_HOOK_AGENTS`:
```python
AGENT_COPILOT: Final[str] = "copilot"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
    AGENT_COPILOT,  # NEW
)
```

Add Copilot-specific constants:
```python
# Copilot hooks directory (under .github/)
COPILOT_HOOKS_DIRNAME: Final[str] = "hooks"
COPILOT_HOOK_CONFIG_FILENAME: Final[str] = "oak-ci-hooks.json"
COPILOT_HOOK_SCRIPT_NAME: Final[str] = "oak-ci-hook.sh"
```

#### 2.2 Update Copilot Agent Manifest

**File:** `src/open_agent_kit/agents/copilot/manifest.yaml`

Add `hooks:` section to existing manifest (after `mcp:` section):
```yaml
hooks:
  # CI hooks installation config
  # Copilot hooks are stored in .github/hooks/ per GitHub docs
  config_dir: ".github/hooks"
  config_file: "oak-ci-hooks.json"
  script_file: "oak-ci-hook.sh"
  template_dir: "codebase_intelligence/hooks/copilot"
```

#### 2.3 New Hooks Directory

Create: `src/open_agent_kit/features/codebase_intelligence/hooks/copilot/`

**hooks.json** (Copilot format with bash/powershell fields):
```json
{
  "$comment": "Codebase Intelligence hooks for GitHub Copilot. {{PORT}} and {{PROJECT_ROOT}} are replaced during installation. Installed to .github/hooks/",
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh sessionStart",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 30
      }
    ],
    "sessionEnd": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh sessionEnd",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 15
      }
    ],
    "userPromptSubmitted": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh userPromptSubmitted",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 15
      }
    ],
    "postToolUse": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh postToolUse",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 5
      }
    ],
    "errorOccurred": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh errorOccurred",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 5,
        "comment": "Maps to post-tool-use-failure endpoint"
      }
    ]
  }
}
```

**oak-ci-hook.sh** (script to dispatch to CI daemon, mirrors Cursor pattern):
```bash
#!/bin/bash
# Codebase Intelligence hooks for GitHub Copilot
# Installed by: oak ci enable
# Template placeholders replaced: {{PORT}}, {{PROJECT_ROOT}}

EVENT="${1:-unknown}"
INPUT="$(cat || true)"

PORT="{{PORT}}"
PROJECT_ROOT="{{PROJECT_ROOT}}"
HOOK_LOG="${PROJECT_ROOT}/.oak/ci/hooks.log"

SAFE_INPUT="$(printf "%s" "${INPUT}" | jq -c . 2>/dev/null || echo "{}")"
SESSION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.session_id // .conversation_id // empty'')"
CONVERSATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.conversation_id // empty'')"
HOOK_ORIGIN="copilot_config"

echo "[${EVENT}] $(date ''+%Y-%m-%d %H:%M:%S'') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1

case "${EVENT}" in
  sessionStart)
    SOURCE="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.source // "startup"'')"
    (curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1 || oak ci start --quiet >/dev/null 2>&1 || true)
    RESPONSE="$(jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg source "${SOURCE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, source: $source, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-start" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c ''if .context.injected_context then {additional_context: .context.injected_context} else {} end'' 2>/dev/null || echo "{}"
    ;;
  sessionEnd)
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-end" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  userPromptSubmitted)
    PROMPT="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.prompt // ""'')"
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg prompt "${PROMPT}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $a', '2026-01-24T10:26:48.583661', '2026-01-24T10:39:08.064472', 'completed', 63, 1, 'plan', 'plan', NULL, '# Plan: Add Missing Hooks and Copilot Support for CI Activity Capture

## Summary

**Phase 1: Add new hook events** (PostToolUseFailure, SubagentStart, SubagentStop)
**Phase 2: Add full Copilot support** (new agent, full hook configuration)
**Phase 3: UI enhancements** (better failure visualization, subagent grouping)

## Agent Hook Support Matrix

| Event | Claude | Cursor | Gemini | Copilot |
|-------|--------|--------|--------|---------|
| SessionStart | ✓ | ✓ | ✓ | ✓ (NEW) |
| UserPromptSubmit | ✓ | ✓ | ❌ | ✓ (NEW) |
| PostToolUse | ✓ | ✓ | ✓ | ✓ (NEW) |
| **PostToolUseFailure** | **ADD** | **ADD** | ❌ | ✓ (NEW) |
| **SubagentStart** | **ADD** | **ADD** | ❌ | ❌ |
| **SubagentStop** | **ADD** | **ADD** | ❌ | ❌ |
| Stop | ✓ | ✓ | ✓ | ❌ |
| SessionEnd | ✓ | ✓ | ✓ | ✓ (NEW) |

Notes:
- Gemini doesn''t have failure or subagent events
- Copilot has "Error Occurred" which maps to our failure tracking
- Copilot doesn''t have subagent events

---

## Phase 1: New Hook Events

### Files to Modify

#### 1.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add after line 212:
```python
HOOK_EVENT_POST_TOOL_USE_FAILURE: Final[str] = "post-tool-use-failure"
HOOK_EVENT_SUBAGENT_START: Final[str] = "subagent-start"
HOOK_EVENT_SUBAGENT_STOP: Final[str] = "subagent-stop"
```

Add after line 229:
```python
HOOK_FIELD_AGENT_ID: Final[str] = "agent_id"
HOOK_FIELD_AGENT_TYPE: Final[str] = "agent_type"
HOOK_FIELD_AGENT_TRANSCRIPT_PATH: Final[str] = "agent_transcript_path"
HOOK_FIELD_STOP_HOOK_ACTIVE: Final[str] = "stop_hook_active"
```

#### 1.2 Route Handlers (`src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py`)

Add 3 new route handlers following existing patterns:

**Route 1: `/api/oak/ci/post-tool-use-failure`**
- Mirror `hook_post_tool_use` but always `success=False`
- Log prominently: `[TOOL-FAILURE] {tool_name}`

**Route 2: `/api/oak/ci/subagent-start`**
- Track subagent spawn (agent_id, agent_type)
- Log: `[SUBAGENT-START] type={agent_type}`

**Route 3: `/api/oak/ci/subagent-stop`**
- Track subagent completion (agent_id, agent_transcript_path)
- Log: `[SUBAGENT-STOP] type={agent_type}`

#### 1.3 Claude Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/claude/hooks.json`)

Add after "SessionEnd" block:
```json
"PostToolUseFailure": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), tool_name: .tool_name, tool_input: .tool_input, tool_use_id: .tool_use_id, hook_event_name: \"PostToolUseFailure\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/post-tool-use-failure -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStart": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_type: .agent_type, hook_event_name: \"SubagentStart\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-start -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 5
    }]
  }
],
"SubagentStop": [
  {
    "matcher": "*",
    "hooks": [{
      "type": "command",
      "command": "INPUT=$(cat); SAFE_INPUT=$(printf \"%s\" \"$INPUT\" | jq -c . 2>/dev/null || echo \"{}\"); printf \"%s\" \"$SAFE_INPUT\" | jq -c ''{agent: \"claude\", session_id: (.session_id // .conversation_id), agent_id: .agent_id, agent_transcript_path: .agent_transcript_path, stop_hook_active: .stop_hook_active, hook_event_name: \"SubagentStop\"}'' | curl -s -X POST http://localhost:{{PORT}}/api/oak/ci/subagent-stop -H ''Content-Type: application/json'' -d @- >/dev/null || true; echo ''{}''",
      "timeout": 15
    }]
  }
]
```

#### 1.4 Cursor Hooks (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/hooks.json`)

Add new hook entries for:
- `postToolUseFailure` → `/api/oak/ci/post-tool-use-failure`
- `subagentStart` → `/api/oak/ci/subagent-start`
- `subagentStop` → `/api/oak/ci/subagent-stop`

#### 1.5 Cursor Hook Script (`src/open_agent_kit/features/codebase_intelligence/hooks/cursor/oak-ci-hook.sh`)

Add cases:
```bash
postToolUseFailure)
  # POST to /api/oak/ci/post-tool-use-failure with tool_name, tool_input, error_message
  ;;
subagentStart)
  # POST to /api/oak/ci/subagent-start with agent_id, agent_type (subagent_type)
  ;;
subagentStop)
  # POST to /api/oak/ci/subagent-stop with agent_id, agent_transcript_path, status
  ;;
```

---

## Phase 2: Full Copilot Support (NEW AGENT)

Copilot hooks are stored in `.github/hooks/*.json` per GitHub docs:
https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/use-hooks

### Files to Create/Modify

#### 2.1 Constants (`src/open_agent_kit/features/codebase_intelligence/constants.py`)

Add to `SUPPORTED_HOOK_AGENTS`:
```python
AGENT_COPILOT: Final[str] = "copilot"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
    AGENT_COPILOT,  # NEW
)
```

Add Copilot-specific constants:
```python
# Copilot hooks directory (under .github/)
COPILOT_HOOKS_DIRNAME: Final[str] = "hooks"
COPILOT_HOOK_CONFIG_FILENAME: Final[str] = "oak-ci-hooks.json"
COPILOT_HOOK_SCRIPT_NAME: Final[str] = "oak-ci-hook.sh"
```

#### 2.2 Update Copilot Agent Manifest

**File:** `src/open_agent_kit/agents/copilot/manifest.yaml`

Add `hooks:` section to existing manifest (after `mcp:` section):
```yaml
hooks:
  # CI hooks installation config
  # Copilot hooks are stored in .github/hooks/ per GitHub docs
  config_dir: ".github/hooks"
  config_file: "oak-ci-hooks.json"
  script_file: "oak-ci-hook.sh"
  template_dir: "codebase_intelligence/hooks/copilot"
```

#### 2.3 New Hooks Directory

Create: `src/open_agent_kit/features/codebase_intelligence/hooks/copilot/`

**hooks.json** (Copilot format with bash/powershell fields):
```json
{
  "$comment": "Codebase Intelligence hooks for GitHub Copilot. {{PORT}} and {{PROJECT_ROOT}} are replaced during installation. Installed to .github/hooks/",
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh sessionStart",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 30
      }
    ],
    "sessionEnd": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh sessionEnd",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 15
      }
    ],
    "userPromptSubmitted": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh userPromptSubmitted",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 15
      }
    ],
    "postToolUse": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh postToolUse",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 5
      }
    ],
    "errorOccurred": [
      {
        "type": "command",
        "bash": "{{PROJECT_ROOT}}/.github/hooks/oak-ci-hook.sh errorOccurred",
        "cwd": "{{PROJECT_ROOT}}",
        "timeoutSec": 5,
        "comment": "Maps to post-tool-use-failure endpoint"
      }
    ]
  }
}
```

**oak-ci-hook.sh** (script to dispatch to CI daemon, mirrors Cursor pattern):
```bash
#!/bin/bash
# Codebase Intelligence hooks for GitHub Copilot
# Installed by: oak ci enable
# Template placeholders replaced: {{PORT}}, {{PROJECT_ROOT}}

EVENT="${1:-unknown}"
INPUT="$(cat || true)"

PORT="{{PORT}}"
PROJECT_ROOT="{{PROJECT_ROOT}}"
HOOK_LOG="${PROJECT_ROOT}/.oak/ci/hooks.log"

SAFE_INPUT="$(printf "%s" "${INPUT}" | jq -c . 2>/dev/null || echo "{}")"
SESSION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.session_id // .conversation_id // empty'')"
CONVERSATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.conversation_id // empty'')"
HOOK_ORIGIN="copilot_config"

echo "[${EVENT}] $(date ''+%Y-%m-%d %H:%M:%S'') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1

case "${EVENT}" in
  sessionStart)
    SOURCE="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.source // "startup"'')"
    (curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1 || oak ci start --quiet >/dev/null 2>&1 || true)
    RESPONSE="$(jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg source "${SOURCE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, source: $source, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-start" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c ''if .context.injected_context then {additional_context: .context.injected_context} else {} end'' 2>/dev/null || echo "{}"
    ;;
  sessionEnd)
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-end" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  userPromptSubmitted)
    PROMPT="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.prompt // ""'')"
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg prompt "${PROMPT}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, prompt: $prompt, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/prompt-submit" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  postToolUse)
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.tool_name // ""'')"
    TOOL_USE_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.tool_use_id // empty'')"
    printf "%s" "${SAFE_INPUT}" | jq -c --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg tool_use_id "${TOOL_USE_ID}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, tool_use_id: $tool_use_id, tool_name: .tool_name, tool_input: .tool_input, tool_output_b64: ((.tool_response // "") | tostring | @base64)}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  errorOccurred)
    # Maps to post-tool-use-failure endpoint
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.tool_name // "unknown"'')"
    ERROR_MSG="$(printf "%s" "${SAFE_INPUT}" | jq -r ''.error.message // .error // ""'')"
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg tool_name "${TOOL_NAME}" --arg error_message "${ERROR_MSG}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" ''{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, tool_name: $tool_name, error_message: $error_message, hook_origin: $hook_origin, hook_event_name: $hook_event_name}'' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use-failure" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  *)
    echo "{}"
    ;;
esac
```

#### 2.4 Service Updates (`src/open_agent_kit/features/codebase_intelligence/service.py`)

**Add to update_agent_hooks() dispatch (around line 444):**
```python
elif agent == "copilot":
    self._update_copilot_hooks()
    results[agent] = "updated"
```

**Add `_update_copilot_hooks()` method (mirrors Cursor pattern):**
```python
def _update_copilot_hooks(self) -> None:
    """Update GitHub Copilot hooks with CI hooks.

    Copilot hooks are stored in .github/hooks/ per GitHub docs.
    Uses script dispatch pattern similar to Cursor.
    """
    hooks_dir = self.project_root / ".github" / "hooks"
    hooks_file = hooks_dir / COPILOT_HOOK_CONFIG_FILENAME
    hooks_script_path = hooks_dir / COPILOT_HOOK_SCRIPT_NAME

    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Load existing hooks or create new
    if hooks_file.exists():
        with open(hooks_file) as f:
            hooks = json.load(f)
    else:
        hooks = {"version": 1, "hooks": {}}

    # Ensure hooks key exists
    if "hooks" not in hooks:
        hooks["hooks"] = {}

    # Load CI hooks from template
    template = self._load_hook_template("copilot")
    if not template:
        logger.error("Failed to load Copilot hooks template")
        return

    ci_hooks = template.get("hooks", {})

    # Replace CI hooks (remove old OAK hooks, add new ones)
    for event, new_hooks in ci_hooks.items():
        if event not in hooks["hooks"]:
            hooks["hooks"][event] = []

        # Remove existing OAK-managed hooks for this event
        hooks["hooks"][event] = [
            h for h in hooks["hooks"][event]
            if not self._is_oak_managed_hook(h, "copilot")
        ]

        # Add new CI hooks
        hooks["hooks"][event].extend(new_hooks)

    # Install hook script
    hook_script_template = HOOKS_TEMPLATE_DIR / "copilot" / COPILOT_HOOK_SCRIPT_NAME
    if not hook_script_template.exists():
        logger.error(f"Copilot hook script template missing: {hook_script_template}")
        return

    hooks_script_path.write_text(
        hook_script_template.read_text()
        .replace("{{PORT}}", str(self.port))
        .replace("{{PROJECT_ROOT}}", str(self.project_root))
    )
    hooks_script_path.chmod(0o755)

    with open(hooks_file, "w") as f:
        json.dump(hooks, f, indent=2)

    logger.info(f"Updated Copilot hooks at {hooks_file}")
```

**Add to _remove_agent_hooks() dispatch (around line 673):**
```python
elif agent == "copilot":
    self._remove_copilot_hooks()
    results[agent] = "removed"
```

**Add `_remove_copilot_hooks()` method:**
```python
def _remove_copilot_hooks(self) -> None:
    """Remove CI hooks from GitHub Copilot."""
    hooks_dir = self.project_root / ".github" / "hooks"
    hooks_file = hooks_dir / COPILOT_HOOK_CONFIG_FILENAME
    hooks_script_path = hooks_dir / COPILOT_HOOK_SCRIPT_NAME

    if not hooks_file.exists():
        return

    with open(hooks_file) as f:
        hooks = json.load(f)

    if "hooks" not in hooks:
        return

    # Remove OAK-managed hooks from each event
    for event in list(hooks["hooks"].keys()):
        hooks["hooks"][event] = [
            h for h in hooks["hooks"][event]
            if not self._is_oak_managed_hook(h, "copilot")
        ]
        # Remove empty event lists
        if not hooks["hooks"][event]:
            del hooks["hooks"][event]

    with open(hooks_file, "w") as f:
        json.dump(hooks, f, indent=2)

    # Remove hook script if it exists
    if hooks_script_path.exists():
        hooks_script_path.unlink()

    # Cleanup empty config file
    self._cleanup_empty_config_file(
        hooks_file,
        [{}, {"version": 1}, {"hooks": {}}, {"version": 1, "hooks": {}}]
    )

    logger.info(f"Removed Copilot hooks from {hooks_file}")
```

**Update `_is_oak_managed_hook()` to handle Copilot (around line 488):**
```python
elif agent_type == "copilot":
    # Copilot: {bash: "...", powershell: "..."} structure
    command = hook.get("bash", "") or hook.get("powershell", "")
```

---

## Phase 3: UI Enhancements (Deferred)

The current UI already handles failures (red icons, error messages). Future enhancements:

1. **Failure Filter** - Add toggle to show only failed activities
2. **Subagent Grouping** - Show subagent activities nested under parent
3. **Subagent Badge** - Visual indicator for subagent-related activities
4. **Transcript Link** - Link to subagent transcript file

**Note:** Defer UI changes to a follow-up PR to keep this PR focused on hook infrastructure.

---

## Implementation Order

1. **constants.py** - Add new hook event constants, field constants, and AGENT_COPILOT
2. **hooks.py** - Add 3 new route handlers (post-tool-use-failure, subagent-start, subagent-stop)
3. **hooks/claude/hooks.json** - Add PostToolUseFailure, SubagentStart, SubagentStop
4. **hooks/cursor/** - Update hooks.json + oak-ci-hook.sh for new events
5. **hooks/copilot/** - Create new directory with hooks.json + oak-ci-hook.sh
6. **agents/copilot/manifest.yaml** - Add hooks section for installer integration
7. **service.py** - Add `_update_copilot_hooks()`, `_remove_copilot_hooks()`, update dispatchers

---

## Verification

### 1. Hook installation
```bash
# Re-install hooks for this project
oak ci enable --force

# Verify Claude hooks (should show 8 events)
cat .claude/settings.json | jq ''.hooks | keys''
# Expected: ["PostToolUse", "PostToolUseFailure", "SessionEnd", "SessionStart", "Stop", "SubagentStart", "SubagentStop", "UserPromptSubmit"]

# Verify Cursor hooks
cat .cursor/hooks.json | jq ''.hooks | keys''
# Expected includes: postToolUseFailure, subagentStart, subagentStop

# Verify Copilot hooks
cat .github/hooks/oak-ci-hooks.json | jq ''.hooks | keys''
# Expected: ["errorOccurred", "postToolUse", "sessionEnd", "sessionStart", "userPromptSubmitted"]
ls -la .github/hooks/oak-ci-hook.sh
# Should be executable
```

### 2. Integration test
```bash
# Start new session, trigger:
# - Tool failure (read non-existent file)
# - Subagent (use Task tool with Explore)

# Check logs
tail -50 .oak/ci/hooks.log | grep -E "(TOOL-FAILURE|SUBAGENT|errorOccurred)"

# Query database
sqlite3 .oak/ci/activities.db "SELECT tool_name, success, error_message FROM activities ORDER BY id DESC LIMIT 20"
```

### 3. Daemon UI
- Open http://localhost:38283 (or configured port)
- Check Timeline shows failed activities with red indicators
- Verify new activity types appear (subagent start/stop when using Task tool)

---

## Risk Assessment

**Low risk:**
- Adding new routes and hook configs doesn''t affect existing hooks
- New hooks fail gracefully (curl errors suppressed)
- No database schema changes (activities table already has `success` field)
- Copilot is additive (new agent, doesn''t modify existing)

---

## Non-goals (defer to future PRs)

- **PreToolUse** - Requires permission decision UI
- **PreCompact** - Complex conversation state handling
- **Notification** - Lower value for CI analysis
- **Transcript parsing** - SubagentStop could read transcripts, defer
- **UI enhancements** - Keep this PR focused on hook infrastructure


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/85c00c56-5acf-4ff4-90f9-cd4b7b616a73.jsonl', 1769268408, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (28, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 1, 'having an issue wth test and detect for lm studio, it no longer working for embedding models or summariation models. test and detect must populate dimentions, chunk, and context window for embedding models and context for summarization models. we also don''t enable the save botton at the bottom until test and detect works, however, i believe that is too rigid, if the values have been entered manully, then you should be able to save. there is a risk that the values will be incorrect, so it should be discouraged, but should be possible. take and look and lets see whats going on', '2026-01-24T16:18:47.206216', '2026-01-24T16:23:41.522728', 'completed', 42, 1, 'exploration', 'user', NULL, NULL, 1769289527, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (29, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 2, 'well, we still must have validation, we need all fields populated on the config in order to save. Also, why is lmstudio unreliable, are you sure, has this been researched?', '2026-01-24T16:25:14.516117', '2026-01-24T16:26:22.194322', 'completed', 3, 1, 'exploration', 'user', NULL, NULL, 1769289914, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (30, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 3, 'this is what lm studio supports', '2026-01-24T16:26:38.633893', '2026-01-24T16:26:52.069908', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769289998, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (31, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 4, 'lets add some help to the ui then, these models have standard context window sizes, so perhaps an easy way to allow the user to select it, we still want the text box though, so lets come up with someting.. maybe a selector that populates, or we do some kind of autocomplete on the text box, thoughts?', '2026-01-24T16:28:50.737830', '2026-01-24T16:29:07.727825', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769290130, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (32, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 5, 'yes, and lets do this for both embedding and summarization. lets also ensure we ensure the user cant save until all values are populated, which should be in place', '2026-01-24T16:30:57.306755', '2026-01-24T16:33:00.993499', 'completed', 15, 1, 'refactoring', 'user', NULL, NULL, 1769290257, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (33, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 6, 'so perhaps a slight miscalculation with the chips, ollama for this qwen embedding model has a context fo 40960, not 4096, so is this just a calc problem, is that the same context?', '2026-01-24T16:43:28.509628', '2026-01-24T16:44:15.430455', 'completed', 3, 1, 'implementation', 'user', NULL, NULL, 1769291008, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (34, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 7, 'lets now examine our frontend code and ensure we are in a good place and consistent with established patterns. looking for code smells, potential maintenance issues, etc. take a look and let me know', '2026-01-24T16:53:25.440712', '2026-01-24T16:55:14.805984', 'completed', 11, 1, 'exploration', 'user', NULL, NULL, 1769291605, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (35, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 8, 'yes, please proceed with this plan', '2026-01-24T16:56:11.990612', '2026-01-24T17:01:22.882269', 'completed', 25, 1, 'refactoring', 'user', NULL, NULL, 1769291771, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (36, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 9, 'how is our typescript linting? are we set up for that to ensure good quality and patterns', '2026-01-24T17:07:00.221670', '2026-01-24T17:07:50.878754', 'completed', 6, 0, NULL, 'user', NULL, NULL, 1769292420, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (37, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 10, 'yes, work through the remaining fixes', '2026-01-24T17:08:17.458690', '2026-01-24T17:12:46.668812', 'completed', 50, 0, NULL, 'user', NULL, NULL, 1769292497, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (38, 'b82ca70d-639b-427b-bb34-dec7756b80fb', 11, 'lets get a makefile command so that an easily run the linter for the frontend', '2026-01-24T17:13:51.064455', '2026-01-24T17:14:25.588793', 'completed', 6, 0, NULL, 'user', NULL, NULL, 1769292831, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (39, '7ad9ce17-52f0-4ca6-8956-23573232993e', 1, 'the daemon runs background processes that do several tasks, like memories, session naming, several things. I to add another task, that doesn''t need to run that often and perhaps it can just be part of our automatic session closing, which i believe will mark the session as completed after 60 mins of no activity. what we need to add to this is if the session is completely empty, meaning no prompt batches, then we should just remove the session and write a log entry that we did it. this happens when you, for example, just launch claude code, or open a tab in curor, where the session start hook will fire, but if you did a "/resume" in claude, it would then load anothe session, leaving tha new session abandoned. if in cursor, you may have never typed in a prompt.. and if you did eventually, maybe the next day, then we would have deleted it, but when the prompt hook fires, we would should re-create it and mark it as active. that should be double checked becuase i know it will reactivate the session if it exist, but it may not recreate it. this happens often enough where manual cleanup could be a daily occurence.', '2026-01-24T17:20:33.192559', '2026-01-24T17:34:42.607178', 'completed', 57, 1, 'plan', 'plan', '/Users/chris/.claude/plans/warm-churning-hollerith.md', '# Plan: Auto-Delete Empty Sessions on Stale Recovery

## Problem Statement

When Claude Code or Cursor launches, the session start hook fires and creates a session. However, if:
- User does `/resume` in Claude (loads a different session, abandoning the new one)
- User opens Cursor tab but never types a prompt
- User closes without any interaction

...the session remains empty (0 prompt batches) and clutters the database. Currently, these empty sessions are marked as ''completed'' after 60 minutes of inactivity, but they should be **deleted** instead since they contain no useful data.

Additionally, if a prompt later arrives for a deleted session (e.g., user returns the next day), it should seamlessly recreate the session.

## Implementation Approach

### 1. Modify `recover_stale_sessions()` in `activity/store.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Lines:** ~1444-1503

Current behavior:
- Finds active sessions with no activity > 60 minutes
- Marks them all as ''completed''
- Returns list of recovered session IDs

New behavior:
- For each stale session, check prompt batch count
- If count == 0: DELETE the session (use existing `delete_session()`)
- If count > 0: Mark as ''completed'' (existing behavior)
- Return tuple: `(recovered_ids: list[str], deleted_ids: list[str])`

```python
def recover_stale_sessions(self, timeout_seconds: int = 3600) -> tuple[list[str], list[str]]:
    """Auto-end or delete sessions that have been inactive for too long.

    Sessions with prompt batches are marked as ''completed''.
    Empty sessions (no prompt batches) are deleted entirely.

    Returns:
        Tuple of (recovered_ids, deleted_ids) for state synchronization.
    """
```

### 2. Update Background Processor in `activity/processor/core.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/processor/core.py`
**Lines:** ~657-676

Current behavior:
```python
recovered_session_ids = self.activity_store.recover_stale_sessions(...)
for session_id in recovered_session_ids:
    self.process_session_summary(session_id)
```

New behavior:
```python
recovered_ids, deleted_ids = self.activity_store.recover_stale_sessions(...)
# Only generate summaries for recovered (non-empty) sessions
for session_id in recovered_ids:
    self.process_session_summary(session_id)
# Log deleted empty sessions
if deleted_ids:
    logger.info(f"Deleted {len(deleted_ids)} empty stale sessions: {[s[:8] for s in deleted_ids]}")
```

### 3. Ensure Session Recreation on Prompt for Deleted Sessions

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Method:** `create_prompt_batch()` (lines ~1178-1240)

Currently calls `reactivate_session_if_needed()` which only handles completed sessions. Need to also handle deleted sessions.

**Option A (Recommended):** Extend logic before insert
```python
def create_prompt_batch(self, session_id: str, ...):
    # Reactivate if completed (existing)
    self.reactivate_session_if_needed(session_id)

    # NEW: Ensure session exists (handles deleted sessions)
    self._ensure_session_exists(session_id)

    # ... rest of method
```

Add helper method:
```python
def _ensure_session_exists(self, session_id: str, agent: str = "unknown") -> bool:
    """Create session if it doesn''t exist (for deleted session recovery).

    Returns True if session was created, False if already existed.
    """
    conn = self._get_connection()
    cursor = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if cursor.fetchone():
        return False

    # Session was deleted - recreate minimally
    self.create_session(session_id, agent, project_root=str(self.db_path.parent.parent.parent))
    logger.info(f"Recreated deleted session {session_id} for new prompt")
    return True
```

**Issue:** `create_prompt_batch` doesn''t receive agent name. Need to also pass agent to make recreation complete.

**Option B (Alternative):** Modify signature of `create_prompt_batch` to accept optional `agent` parameter for session recreation.

### 4. Files to Modify

| File | Changes |
|------|---------|
| `activity/store.py` | `recover_stale_sessions()` - return tuple, delete empty sessions |
| `activity/store.py` | Add `_ensure_session_exists()` helper |
| `activity/store.py` | `create_prompt_batch()` - call ensure helper |
| `activity/processor/core.py` | Handle tuple return, log deleted sessions |

### 5. Testing Verification

1. **Unit test for empty session deletion:**
   - Create a session with no prompt batches
   - Call `recover_stale_sessions()` with a short timeout
   - Verify session is deleted (not just completed)

2. **Unit test for non-empty session recovery:**
   - Create a session with 1+ prompt batches
   - Call `recover_stale_sessions()`
   - Verify session is marked ''completed'' (not deleted)

3. **Integration test for session recreation:**
   - Create a session, then delete it
   - Call `create_prompt_batch()` for that session_id
   - Verify session is recreated and batch is created successfully

4. **Manual verification:**
   - Launch Claude Code, immediately do `/resume`
   - Wait for background processing (or trigger manually)
   - Check that the abandoned session was deleted, not just completed
   - Start a new prompt - verify it works normally

## Summary

This change ensures empty abandoned sessions are automatically cleaned up, reducing database clutter. Sessions are only preserved when they contain actual user interactions (prompt batches). If a prompt arrives for a previously-deleted session, it''s seamlessly recreated.
', 1769293233, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (40, '550a7072-b6ee-420c-beb3-34a7fb891c87', 1, 'Implement the following plan:

# Plan: Auto-Delete Empty Sessions on Stale Recovery

## Problem Statement

When Claude Code or Cursor launches, the session start hook fires and creates a session. However, if:
- User does `/resume` in Claude (loads a different session, abandoning the new one)
- User opens Cursor tab but never types a prompt
- User closes without any interaction

...the session remains empty (0 prompt batches) and clutters the database. Currently, these empty sessions are marked as ''completed'' after 60 minutes of inactivity, but they should be **deleted** instead since they contain no useful data.

Additionally, if a prompt later arrives for a deleted session (e.g., user returns the next day), it should seamlessly recreate the session.

## Implementation Approach

### 1. Modify `recover_stale_sessions()` in `activity/store.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Lines:** ~1444-1503

Current behavior:
- Finds active sessions with no activity > 60 minutes
- Marks them all as ''completed''
- Returns list of recovered session IDs

New behavior:
- For each stale session, check prompt batch count
- If count == 0: DELETE the session (use existing `delete_session()`)
- If count > 0: Mark as ''completed'' (existing behavior)
- Return tuple: `(recovered_ids: list[str], deleted_ids: list[str])`

```python
def recover_stale_sessions(self, timeout_seconds: int = 3600) -> tuple[list[str], list[str]]:
    """Auto-end or delete sessions that have been inactive for too long.

    Sessions with prompt batches are marked as ''completed''.
    Empty sessions (no prompt batches) are deleted entirely.

    Returns:
        Tuple of (recovered_ids, deleted_ids) for state synchronization.
    """
```

### 2. Update Background Processor in `activity/processor/core.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/processor/core.py`
**Lines:** ~657-676

Current behavior:
```python
recovered_session_ids = self.activity_store.recover_stale_sessions(...)
for session_id in recovered_session_ids:
    self.process_session_summary(session_id)
```

New behavior:
```python
recovered_ids, deleted_ids = self.activity_store.recover_stale_sessions(...)
# Only generate summaries for recovered (non-empty) sessions
for session_id in recovered_ids:
    self.process_session_summary(session_id)
# Log deleted empty sessions
if deleted_ids:
    logger.info(f"Deleted {len(deleted_ids)} empty stale sessions: {[s[:8] for s in deleted_ids]}")
```

### 3. Ensure Session Recreation on Prompt for Deleted Sessions

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Method:** `create_prompt_batch()` (lines ~1178-1240)

Currently calls `reactivate_session_if_needed()` which only handles completed sessions. Need to also handle deleted sessions.

**Approach:** Add optional `agent` parameter to `create_prompt_batch()` and ensure session exists before insert.

```python
def create_prompt_batch(
    self,
    session_id: str,
    user_prompt: str,
    source_type: str = "user",
    plan_file_path: str | None = None,
    plan_content: str | None = None,
    agent: str | None = None,  # NEW: For session recreation
) -> PromptBatch:
    # Reactivate if completed (existing)
    self.reactivate_session_if_needed(session_id)

    # NEW: Ensure session exists (handles deleted sessions)
    if agent:
        self._ensure_session_exists(session_id, agent)

    # ... rest of method
```

Add helper method:
```python
def _ensure_session_exists(self, session_id: str, agent: str) -> bool:
    """Create session if it doesn''t exist (for deleted session recovery).

    Called when a prompt arrives for a session that was previously deleted
    (e.g., empty abandoned session cleaned up by recover_stale_sessions).

    Args:
        session_id: Session ID to check/create.
        agent: Agent name for session creation.

    Returns:
        True if session was created, False if already existed.
    """
    conn = self._get_connection()
    cursor = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if cursor.fetchone():
        return False

    # Session was deleted - recreate with minimal info
    # project_root derived from db_path: .oak/ci/activities.db -> project root
    project_root = str(self.db_path.parent.parent.parent)
    self.create_session(session_id, agent, project_root)
    logger.info(f"Recreated deleted session {session_id} for new prompt (agent={agent})")
    return True
```

Update caller in `hooks.py` (line ~445):
```python
# In hook_prompt_submit, pass agent to create_prompt_batch
# Note: ''agent'' is already extracted from body at line 346
batch = state.activity_store.create_prompt_batch(
    session_id=session_id,
    user_prompt=prompt,
    source_type=source_type,
    plan_content=plan_content,
    agent=agent,  # NEW - already available in scope
)
```

**Hook configurations already pass agent field:**
- Claude: `{agent: "claude", ...}` in hooks.json
- Cursor: `--arg agent "cursor"` in oak-ci-hook.sh
- Copilot: `--arg agent "copilot"` in oak-ci-hook.sh
- Gemini: No prompt-submit hook (only uses other hooks)

### 4. Files to Modify

| File | Changes |
|------|---------|
| `activity/store.py` | `recover_stale_sessions()` - return tuple, delete empty sessions |
| `activity/store.py` | Add `_ensure_session_exists()` helper method |
| `activity/store.py` | `create_prompt_batch()` - add `agent` param, call ensure helper |
| `activity/processor/core.py` | Handle tuple return, log deleted sessions |
| `daemon/routes/hooks.py` | Pass `agent` to `create_prompt_batch()` call (line ~445) |

**No hook configuration changes needed** - all agents already pass `agent` field.

### 5. Testing Verification

1. **Unit test for empty session deletion:**
   - Create a session with no prompt batches
   - Call `recover_stale_sessions()` with a short timeout
   - Verify session is deleted (not just completed)

2. **Unit test for non-empty session recovery:**
   - Create a session with 1+ prompt batches
   - Call `recover_stale_sessions()`
   - Verify session is marked ''completed'' (not deleted)

3. **Integration test for session recreation:**
   - Create a session, then delete it
   - Call `create_prompt_batch()` for that session_id
   - Verify session is recreated and batch is created successfully

4. **Manual verification:**
   - Launch Claude Code, immediately do `/resume`
   - Wait for background processing (or trigger manually)
   - Check that the abandoned session was deleted, not just completed
   - Start a new prompt - verify it works normally

## Summary

This change ensures empty abandoned sessions are automatically cleaned up, reducing database clutter. Sessions are only preserved when they contain actual user interactions (prompt batches). If a prompt arrives for a previously-deleted session, it''s seamlessly recreated.


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/7ad9ce17-52f0-4ca6-8956-23573232993e.jsonl', '2026-01-24T17:34:42.755301', '2026-01-24T17:39:34.193224', 'completed', 24, 1, 'plan', 'plan', NULL, '# Plan: Auto-Delete Empty Sessions on Stale Recovery

## Problem Statement

When Claude Code or Cursor launches, the session start hook fires and creates a session. However, if:
- User does `/resume` in Claude (loads a different session, abandoning the new one)
- User opens Cursor tab but never types a prompt
- User closes without any interaction

...the session remains empty (0 prompt batches) and clutters the database. Currently, these empty sessions are marked as ''completed'' after 60 minutes of inactivity, but they should be **deleted** instead since they contain no useful data.

Additionally, if a prompt later arrives for a deleted session (e.g., user returns the next day), it should seamlessly recreate the session.

## Implementation Approach

### 1. Modify `recover_stale_sessions()` in `activity/store.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Lines:** ~1444-1503

Current behavior:
- Finds active sessions with no activity > 60 minutes
- Marks them all as ''completed''
- Returns list of recovered session IDs

New behavior:
- For each stale session, check prompt batch count
- If count == 0: DELETE the session (use existing `delete_session()`)
- If count > 0: Mark as ''completed'' (existing behavior)
- Return tuple: `(recovered_ids: list[str], deleted_ids: list[str])`

```python
def recover_stale_sessions(self, timeout_seconds: int = 3600) -> tuple[list[str], list[str]]:
    """Auto-end or delete sessions that have been inactive for too long.

    Sessions with prompt batches are marked as ''completed''.
    Empty sessions (no prompt batches) are deleted entirely.

    Returns:
        Tuple of (recovered_ids, deleted_ids) for state synchronization.
    """
```

### 2. Update Background Processor in `activity/processor/core.py`

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/processor/core.py`
**Lines:** ~657-676

Current behavior:
```python
recovered_session_ids = self.activity_store.recover_stale_sessions(...)
for session_id in recovered_session_ids:
    self.process_session_summary(session_id)
```

New behavior:
```python
recovered_ids, deleted_ids = self.activity_store.recover_stale_sessions(...)
# Only generate summaries for recovered (non-empty) sessions
for session_id in recovered_ids:
    self.process_session_summary(session_id)
# Log deleted empty sessions
if deleted_ids:
    logger.info(f"Deleted {len(deleted_ids)} empty stale sessions: {[s[:8] for s in deleted_ids]}")
```

### 3. Ensure Session Recreation on Prompt for Deleted Sessions

**File:** `src/open_agent_kit/features/codebase_intelligence/activity/store.py`
**Method:** `create_prompt_batch()` (lines ~1178-1240)

Currently calls `reactivate_session_if_needed()` which only handles completed sessions. Need to also handle deleted sessions.

**Approach:** Add optional `agent` parameter to `create_prompt_batch()` and ensure session exists before insert.

```python
def create_prompt_batch(
    self,
    session_id: str,
    user_prompt: str,
    source_type: str = "user",
    plan_file_path: str | None = None,
    plan_content: str | None = None,
    agent: str | None = None,  # NEW: For session recreation
) -> PromptBatch:
    # Reactivate if completed (existing)
    self.reactivate_session_if_needed(session_id)

    # NEW: Ensure session exists (handles deleted sessions)
    if agent:
        self._ensure_session_exists(session_id, agent)

    # ... rest of method
```

Add helper method:
```python
def _ensure_session_exists(self, session_id: str, agent: str) -> bool:
    """Create session if it doesn''t exist (for deleted session recovery).

    Called when a prompt arrives for a session that was previously deleted
    (e.g., empty abandoned session cleaned up by recover_stale_sessions).

    Args:
        session_id: Session ID to check/create.
        agent: Agent name for session creation.

    Returns:
        True if session was created, False if already existed.
    """
    conn = self._get_connection()
    cursor = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if cursor.fetchone():
        return False

    # Session was deleted - recreate with minimal info
    # project_root derived from db_path: .oak/ci/activities.db -> project root
    project_root = str(self.db_path.parent.parent.parent)
    self.create_session(session_id, agent, project_root)
    logger.info(f"Recreated deleted session {session_id} for new prompt (agent={agent})")
    return True
```

Update caller in `hooks.py` (line ~445):
```python
# In hook_prompt_submit, pass agent to create_prompt_batch
# Note: ''agent'' is already extracted from body at line 346
batch = state.activity_store.create_prompt_batch(
    session_id=session_id,
    user_prompt=prompt,
    source_type=source_type,
    plan_content=plan_content,
    agent=agent,  # NEW - already available in scope
)
```

**Hook configurations already pass agent field:**
- Claude: `{agent: "claude", ...}` in hooks.json
- Cursor: `--arg agent "cursor"` in oak-ci-hook.sh
- Copilot: `--arg agent "copilot"` in oak-ci-hook.sh
- Gemini: No prompt-submit hook (only uses other hooks)

### 4. Files to Modify

| File | Changes |
|------|---------|
| `activity/store.py` | `recover_stale_sessions()` - return tuple, delete empty sessions |
| `activity/store.py` | Add `_ensure_session_exists()` helper method |
| `activity/store.py` | `create_prompt_batch()` - add `agent` param, call ensure helper |
| `activity/processor/core.py` | Handle tuple return, log deleted sessions |
| `daemon/routes/hooks.py` | Pass `agent` to `create_prompt_batch()` call (line ~445) |

**No hook configuration changes needed** - all agents already pass `agent` field.

### 5. Testing Verification

1. **Unit test for empty session deletion:**
   - Create a session with no prompt batches
   - Call `recover_stale_sessions()` with a short timeout
   - Verify session is deleted (not just completed)

2. **Unit test for non-empty session recovery:**
   - Create a session with 1+ prompt batches
   - Call `recover_stale_sessions()`
   - Verify session is marked ''completed'' (not deleted)

3. **Integration test for session recreation:**
   - Create a session, then delete it
   - Call `create_prompt_batch()` for that session_id
   - Verify session is recreated and batch is created successfully

4. **Manual verification:**
   - Launch Claude Code, immediately do `/resume`
   - Wait for background processing (or trigger manually)
   - Check that the abandoned session was deleted, not just completed
   - Start a new prompt - verify it works normally

## Summary

This change ensures empty abandoned sessions are automatically cleaned up, reducing database clutter. Sessions are only preserved when they contain actual user interactions (prompt batches). If a prompt arrives for a previously-deleted session, it''s seamlessly recreated.


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/7ad9ce17-52f0-4ca6-8956-23573232993e.jsonl', 1769294082, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (41, 'f4c052d2-2753-49d2-966a-0d989a9366b4', 1, 'in our new codebase intelligence feature, development is far along, however its created some very long and arguably unmanagemtn files. our @src/open_agent_kit/features/codebase_intelligence/activity/store.py is massive and our @src/open_agent_kit/features/codebase_intelligence/memory/store.py is not far behind. I think its time to decompose this files so that we can better manage them moving forward as the feature continues to grow. lets plan this out to ensure its done properly', '2026-01-24T17:50:02.804663', NULL, 'completed', 77, 1, 'plan', 'plan', '/Users/chris/.claude/plans/valiant-painting-lake.md', '# Store Module Decomposition Plan

## Summary

Decompose two large store modules in the codebase intelligence feature:
- `activity/store.py` (2,937 lines) → 12 focused files
- `memory/store.py` (1,309 lines) → 9 focused files

Following existing OAK patterns from `activity/processor/` and `strategic_planning/plan/`.

---

## Part 1: activity/store.py Decomposition

### New Directory Structure

```
activity/store/
├── __init__.py          # Re-exports for backward compatibility
├── schema.py            # SCHEMA_VERSION, SCHEMA_SQL (~200 lines)
├── migrations.py        # All migration methods (~400 lines)
├── models.py            # Activity, PromptBatch, Session, StoredObservation (~270 lines)
├── core.py              # ActivityStore class + connection management (~150 lines)
├── sessions.py          # Session CRUD operations (~220 lines)
├── batches.py           # Prompt batch operations + plan embedding (~350 lines)
├── activities.py        # Activity CRUD and FTS5 search (~250 lines)
├── observations.py      # Memory observation storage (~250 lines)
├── stats.py             # Statistics and caching (~300 lines)
├── backup.py            # SQL export/import (~160 lines)
└── delete.py            # Cascade delete operations (~180 lines)
```

### Design Approach

**Function delegation pattern** (not mixins):
- Keep `ActivityStore` as a single class in `core.py`
- Each operation module exports standalone functions that take `store` as first param
- `ActivityStore` methods delegate to these functions
- Simpler than mixins, better IDE navigation, easier testing

Example in `core.py`:
```python
from . import sessions, batches, activities

class ActivityStore:
    def create_session(self, session_id: str, agent: str, project_root: str) -> Session:
        return sessions.create_session(self, session_id, agent, project_root)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `schema.py` | `SCHEMA_VERSION=10`, `SCHEMA_SQL` constant |
| `migrations.py` | `apply_migrations()`, 7 `migrate_vX_to_vY()` functions |
| `models.py` | 4 dataclasses with `to_row()`/`from_row()` methods |
| `core.py` | `ActivityStore.__init__`, connection mgmt, `_transaction()`, `optimize_database()` |
| `sessions.py` | 11 session methods (create, get, end, reactivate, stats) |
| `batches.py` | 17 batch methods (CRUD, recovery, plan embedding) |
| `activities.py` | 8 activity methods (add, buffer, search FTS5) |
| `observations.py` | 10 observation methods (store, embed tracking) |
| `stats.py` | 6 stats methods (caching, bulk queries) |
| `backup.py` | `export_to_sql()`, `import_from_sql()` |
| `delete.py` | 6 cascade delete methods |

---

## Part 2: memory/store.py Decomposition

### New Directory Structure

```
memory/store/
├── __init__.py          # Re-exports for backward compatibility
├── constants.py         # CODE_COLLECTION, MEMORY_COLLECTION (~20 lines)
├── classification.py    # DOC_TYPE_*, classify_doc_type(), get_short_path() (~100 lines)
├── models.py            # CodeChunk, MemoryObservation, PlanObservation (~170 lines)
├── core.py              # VectorStore class + ChromaDB init (~250 lines)
├── code_ops.py          # Code indexing operations (~200 lines)
├── memory_ops.py        # Memory/plan add/delete (~120 lines)
├── search.py            # search_code(), search_memory(), get_by_ids() (~100 lines)
└── management.py        # Stats, listing, archiving, cleanup (~350 lines)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `constants.py` | Collection name constants |
| `classification.py` | Doc type patterns, `classify_doc_type()`, `get_short_path()` |
| `models.py` | 3 dataclasses with embedding/metadata methods |
| `core.py` | `VectorStore.__init__`, ChromaDB setup, dimension handling |
| `code_ops.py` | `add_code_chunks()`, `add_code_chunks_batched()`, `delete_code_by_filepath()` |
| `memory_ops.py` | `add_memory()`, `add_plan()`, `delete_memories()` |
| `search.py` | Semantic search functions |
| `management.py` | Archive, tags, listing, stats, cleanup |

---

## Part 3: Implementation Order

### Phase 1: Activity Store Models (Low Risk)
1. Create `activity/store/` directory
2. Create `activity/store/models.py` - extract 4 dataclasses
3. Create `activity/store/schema.py` - extract constants
4. Create `activity/store/__init__.py` - re-export from models/schema + old store
5. Run tests: `pytest tests/unit/features/codebase_intelligence/test_activity.py -v`

### Phase 2: Activity Store Operations
6. Create `activity/store/migrations.py` - extract migration functions
7. Create `activity/store/sessions.py` - extract session operations
8. Create `activity/store/batches.py` - extract batch operations
9. Create `activity/store/activities.py` - extract activity operations
10. Create `activity/store/observations.py` - extract observation operations
11. Create `activity/store/stats.py` - extract stats operations
12. Create `activity/store/backup.py` - extract backup operations
13. Create `activity/store/delete.py` - extract delete operations
14. Refactor `activity/store/core.py` - keep only core class with delegation
15. Update `activity/store/__init__.py` - re-export from all modules
16. Run full test suite

### Phase 3: Memory Store
17. Create `memory/store/` directory
18. Create `memory/store/constants.py`
19. Create `memory/store/classification.py`
20. Create `memory/store/models.py`
21. Create `memory/store/__init__.py` - re-export + old store
22. Create `memory/store/code_ops.py`
23. Create `memory/store/memory_ops.py`
24. Create `memory/store/search.py`
25. Create `memory/store/management.py`
26. Refactor `memory/store/core.py`
27. Update `memory/store/__init__.py`
28. Run full test suite

### Phase 4: Cleanup
29. Delete `activity/store.py` (original file)
30. Delete `memory/store.py` (original file)
31. Update `activity/__init__.py` if needed
32. Update `memory/__init__.py` if needed
33. Run `make check`

---

## Part 4: Backward Compatibility

### Import Preservation

All existing imports will continue working via `__init__.py` re-exports:

```python
# These imports work unchanged:
from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity, ActivityStore, PromptBatch, Session, StoredObservation
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    VectorStore, CodeChunk, MemoryObservation, PlanObservation
)
```

### Affected Modules (No Changes Required)

**activity/store.py consumers (11+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`, `titles.py`
- `daemon/state.py`, `daemon/routes/backup.py`, `daemon/routes/activity.py`
- `service.py`, `commands/ci_cmd.py`

**memory/store.py consumers (13+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`
- `daemon/state.py`, `daemon/server.py`
- `indexing/indexer.py`, `retrieval/engine.py`
- `memory/__init__.py`

---

## Part 5: Verification

### After Each Phase
```bash
# Run unit tests
pytest tests/unit/features/codebase_intelligence/ -v

# Run feature tests
pytest tests/features/codebase_intelligence/ -v
```

### Final Verification
```bash
# Full quality gate
make check

# Verify imports still work
python -c "from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore, Activity, Session, PromptBatch"
python -c "from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore, CodeChunk"
```

---

## Critical Files

| File | Action |
|------|--------|
| `src/.../activity/store.py` | Source (2,937 lines) → decompose → delete |
| `src/.../memory/store.py` | Source (1,309 lines) → decompose → delete |
| `src/.../activity/processor/__init__.py` | Pattern to follow |
| `tests/.../test_activity.py` | Verify no regressions |
| `tests/.../test_memory_store.py` | Verify no regressions |
', 1769295002, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (42, '23a3b5d1-4021-425d-9b63-812aefc12ccd', 1, 'lets look at our codebase intellignce feature, specifically hooks and what we inject back to the agent. I wast to ensure this is valuable. i believe we inject some context to remind the agemnt about our oak ci cli commands. what i''ve found is that this is not very effective, perhaps 1 in 20+ sessions have i seen the agent do that. I have seen a bit more success with the agent using the skills and using the mcp server, both of which we install and configure for agents that support it. for injection, i think we continue to focus on doig a search and injecting relevent files and memories, which we are also doing. so what I would like is a complete analysis of what we are doing now, and hten we can discuss potential improvements', '2026-01-24T17:56:59.603603', '2026-01-24T17:58:32.159061', 'completed', 17, 0, NULL, 'user', NULL, NULL, 1769295419, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (43, '23a3b5d1-4021-425d-9b63-812aefc12ccd', 2, 'Yes, i agree, it is failing. If we do remind at all, we could remind about the skills, though the agent already has the title and description of thos skills loaded, so its not really necessary. lets remove the reminders. 2. agreed. 3. yes, we should and could be quite valuable. i assume that when we inject code references, we do give the filename, but the relevant chunk could take it to the next level. 4. for memory relevance, i''m curious about this too, for tool calls, i don''t know how much we have to search with, wich will directly effect the quality and relevance of our search. we also now have plans adn we store and embed, which could also be helpful. lets jump into plan mode and dig in', '2026-01-24T18:06:10.292215', NULL, 'completed', 45, 0, NULL, 'user', NULL, NULL, 1769295970, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (44, '91eddd37-f8e7-460b-9915-1dedc774cf74', 1, 'it seems we have a bug in our daemon ui where our memoris tab in the data exploer is no longer loading. getting a 500 error from teh api and i see this in the daemon.log File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/fastapi/routing.py", line 115, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/fastapi/routing.py", line 101, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/fastapi/routing.py", line 355, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "/Users/chris/Repos/open-agent-kit/.venv/lib/python3.13/site-packages/fastapi/routing.py", line 243, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/search.py", line 292, in list_memories
    memory_type=MemoryType(mem.get("memory_type", "discovery")),
                ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.11_1/Frameworks/Python.framework/Versions/3.13/lib/python3.13/enum.py", line 726, in __call__
    return cls.__new__(cls, value)
           ~~~~~~~~~~~^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.11_1/Frameworks/Python.framework/Versions/3.13/lib/python3.13/enum.py", line 1203, in __new__
    raise ve_exc
ValueError: ''plan'' is not a valid MemoryType .. please dig in and lets figure out what is going on so that we can address it', '2026-01-24T18:08:29.306918', '2026-01-24T18:09:12.962566', 'completed', 9, 0, NULL, 'user', NULL, NULL, 1769296109, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (45, '91eddd37-f8e7-460b-9915-1dedc774cf74', 2, 'ok, its loading now, but the cards are way too big and must be truncated, and then we should do a view full memory button to view the rest in a model, just like we do with activities and plans when looking at sessions data.', '2026-01-24T18:11:38.343334', '2026-01-24T18:13:58.125869', 'completed', 16, 0, NULL, 'user', NULL, NULL, 1769296298, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (46, '91eddd37-f8e7-460b-9915-1dedc774cf74', 3, 'ui looks much better. now looking at these plans, and one is categorized as a decision, what is going on here. it looks like have duplicates as well', '2026-01-24T18:16:10.702858', '2026-01-24T18:18:28.085318', 'completed', 11, 0, NULL, 'user', NULL, NULL, 1769296570, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (47, '91eddd37-f8e7-460b-9915-1dedc774cf74', 4, 'i tried to deleted one of the duplicates, but got an error', '2026-01-24T18:23:58.041260', '2026-01-24T18:25:33.871795', 'completed', 9, 0, NULL, 'user', NULL, NULL, 1769297038, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (48, '91eddd37-f8e7-460b-9915-1dedc774cf74', 5, 'so it deletes from sqllite then deletes from chroma? sice chroma is just the embedded version', '2026-01-24T18:26:27.704197', '2026-01-24T18:26:40.482641', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769297187, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (49, '91eddd37-f8e7-460b-9915-1dedc774cf74', 6, 'I supposed i don''t understand, so how are plans stored in sqlite then?', '2026-01-24T18:27:19.716833', '2026-01-24T18:27:34.685157', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769297239, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (50, '91eddd37-f8e7-460b-9915-1dedc774cf74', 7, 'so why are we showing plans in memories then?', '2026-01-24T18:28:22.912927', '2026-01-24T18:28:36.996698', 'completed', 0, 1, NULL, 'user', NULL, NULL, 1769297302, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (51, '91eddd37-f8e7-460b-9915-1dedc774cf74', 8, 'yes, i like the plans as a separate tab, so we create a dedicated viewing experience. though plans are part of prompt batches which are part of sessions, so it should be able to link back to the session where it originated. it does not belong in memories those are llm generated observations based on agent activity. we decided to index plans in chroma because it may be useful to agents when searching, however how well is searching for plans supported across the cli, via search, or via mcp tools, and finally via our skills that we install for agents. so lets plan this out to ensure we get it right', '2026-01-24T18:32:15.729043', '2026-01-24T18:37:26.358584', 'completed', 75, 1, 'plan', 'plan', '/Users/chris/.claude/plans/gleaming-swimming-hennessy.md', '# Plan: Separate Plans from Memories with Dedicated Plans Tab

## Problem Statement
Plans are currently shown in the Memories list, but they don''t belong there:
- **Memories** = LLM-generated observations based on agent activity (stored in `memory_observations`)
- **Plans** = Design documents from prompt_batches (stored in `prompt_batches` table)

Plans are indexed in ChromaDB for semantic search, but should have their own dedicated viewing experience in the Data Explorer.

## Goals
1. Remove plans from the Memories list
2. Create a dedicated "Plans" tab in Data Explorer
3. Plans should link back to their originating session
4. Maintain plan search functionality across CLI, API, MCP tools, and UI search

---

## Implementation Plan

### 1. Filter Plans Out of Memories List

**File:** `daemon/routes/search.py` (lines 254-307)

The API already supports `exclude_types` parameter through to VectorStore. Modify the `list_memories` endpoint:

```python
# Add default exclusion of plans from memory list
exclude_types_list = ["plan"]  # Always exclude plans from memories view
if exclude_sessions:
    exclude_types_list.append("session_summary")
```

**Also update frontend constants:**
- Remove "plan" from `MEMORY_TYPE_FILTER_OPTIONS` in `constants.ts` (line 589)
- Keep "plan" in `MEMORY_TYPES` and `MEMORY_TYPE_BADGE_CLASSES` for search results display

---

### 2. Create Plans API Endpoint

**File:** `daemon/routes/activity.py` (new endpoint)

Create `GET /api/activity/plans` that queries `prompt_batches` directly:

```python
@router.get("/api/activity/plans", response_model=PlansListResponse)
async def list_plans(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None, description="Filter by session"),
) -> PlansListResponse:
    """List plans from prompt_batches (direct SQLite, not ChromaDB)."""
```

**New response models in `daemon/models.py`:**

```python
class PlanListItem(BaseModel):
    id: int  # batch_id
    title: str  # extracted from file path or first heading
    session_id: str
    created_at: datetime
    file_path: str | None
    preview: str  # first 200 chars of plan_content
    plan_embedded: bool  # indexed in ChromaDB?

class PlansListResponse(BaseModel):
    plans: list[PlanListItem]
    total: int
    limit: int
    offset: int
```

**New ActivityStore method in `activity/store.py`:**

```python
def get_plans(
    self,
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None
) -> tuple[list[PromptBatch], int]:
    """Get plan batches from prompt_batches table."""
    # SELECT * FROM prompt_batches
    # WHERE source_type = ''plan'' AND plan_content IS NOT NULL
    # ORDER BY created_at_epoch DESC
    # LIMIT ? OFFSET ?
```

---

### 3. Create Plans Tab Component

**New file:** `daemon/ui/src/components/data/PlansList.tsx`

Component features:
- Fetch plans via new `usePlans()` hook
- Card grid layout (similar to MemoriesList)
- Show: title, file_path, created date, preview
- Link to session: "View Session" button → `/data/sessions/{session_id}`
- "View Full Plan" button → ContentDialog with full plan_content
- Delete plan functionality (removes from ChromaDB index, marks unembedded)
- Pagination with "Load more"

**New hook:** `daemon/ui/src/hooks/use-plans.ts`

```typescript
export function usePlans(options: { limit: number; offset: number; sessionId?: string }) {
    return useQuery({
        queryKey: ["plans", options],
        queryFn: () => fetchJson(`/api/activity/plans?${params}`),
    });
}
```

---

### 4. Add Plans Tab to Data Explorer

**File:** `daemon/ui/src/pages/DataExplorer.tsx`

```typescript
import { FileText } from "lucide-react";

const tabs = [
    { id: "sessions", label: "Sessions", path: "/data/sessions", icon: FolderGit2 },
    { id: "plans", label: "Plans", path: "/data/plans", icon: FileText },  // NEW
    { id: "memories", label: "Memories", path: "/data/memories", icon: Cpu },
];
```

**File:** `daemon/ui/src/router.tsx`

```typescript
{
    path: "data",
    element: <DataExplorer />,
    children: [
        { index: true, element: <Navigate to="sessions" replace /> },
        { path: "sessions", element: <SessionList /> },
        { path: "plans", element: <PlansList /> },  // NEW
        { path: "memories", element: <MemoriesList /> },
    ]
}
```

---

### 5. Update Frontend Constants

**File:** `daemon/ui/src/lib/constants.ts`

```typescript
// Add new API endpoint
export const API_ENDPOINTS = {
    // ... existing
    ACTIVITY_PLANS: "/api/activity/plans",
};

// Remove plan from memory filter options (keep in MEMORY_TYPES for search display)
export const MEMORY_TYPE_FILTER_OPTIONS = [
    { value: "all", label: "All Types" },
    { value: MEMORY_TYPES.GOTCHA, label: MEMORY_TYPE_LABELS.gotcha },
    { value: MEMORY_TYPES.DISCOVERY, label: MEMORY_TYPE_LABELS.discovery },
    { value: MEMORY_TYPES.BUG_FIX, label: MEMORY_TYPE_LABELS.bug_fix },
    { value: MEMORY_TYPES.DECISION, label: MEMORY_TYPE_LABELS.decision },
    { value: MEMORY_TYPES.TRADE_OFF, label: MEMORY_TYPE_LABELS.trade_off },
    { value: MEMORY_TYPES.SESSION_SUMMARY, label: MEMORY_TYPE_LABELS.session_summary },
    // REMOVED: { value: MEMORY_TYPES.PLAN, label: MEMORY_TYPE_LABELS.plan },
] as const;
```

---

## Files to Modify

| File | Change |
|------|--------|
| `daemon/routes/search.py` | Exclude plans from memories list by default |
| `daemon/routes/activity.py` | Add `/api/activity/plans` endpoint |
| `daemon/models.py` | Add `PlanListItem`, `PlansListResponse` models |
| `activity/store.py` | Add `get_plans()` method |
| `daemon/ui/src/pages/DataExplorer.tsx` | Add Plans tab |
| `daemon/ui/src/router.tsx` | Add plans route |
| `daemon/ui/src/components/data/PlansList.tsx` | NEW - Plans list component |
| `daemon/ui/src/hooks/use-plans.ts` | NEW - Plans data hook |
| `daemon/ui/src/lib/constants.ts` | Add endpoint, remove plan from memory filters |

---

## Search Functionality (No Changes Needed)

Plans will continue to appear in search results because:
- `RetrievalEngine.search()` already handles `search_type=''plans''` separately
- `VectorStore.search_memory(memory_types=[''plan''])` works correctly
- MCP tools (`oak_search`) already support `search_type=''plans''`
- UI Search page already displays `PlanResult` items

---

## Verification

1. **Memories list**: Should no longer show plan-type items
2. **Plans tab**: Shows all plans from prompt_batches with session links
3. **Search**: Plans still appear when searching (search_type=all or plans)
4. **Delete plan**: Removes from ChromaDB, marks unembedded in SQLite
5. **Link to session**: Clicking session link navigates to session detail
6. **MCP tools**: `oak_search` with `search_type=''plans''` still returns plans
7. **Build**: `npm run build` succeeds, daemon restarts cleanly
', 1769297535, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (52, 'e675ea0c-3acb-4411-b69e-92f901786a15', 1, 'Implement the following plan:

# Plan: Separate Plans from Memories with Dedicated Plans Tab

## Problem Statement
Plans are currently shown in the Memories list, but they don''t belong there:
- **Memories** = LLM-generated observations based on agent activity (stored in `memory_observations`)
- **Plans** = Design documents from prompt_batches (stored in `prompt_batches` table)

Plans are indexed in ChromaDB for semantic search, but should have their own dedicated viewing experience in the Data Explorer.

## Goals
1. Remove plans from the Memories list
2. Create a dedicated "Plans" tab in Data Explorer
3. Plans should link back to their originating session
4. Maintain plan search functionality across CLI, API, MCP tools, and UI search

---

## Implementation Plan

### 1. Filter Plans Out of Memories List

**File:** `daemon/routes/search.py` (lines 254-307)

The API already supports `exclude_types` parameter through to VectorStore. Modify the `list_memories` endpoint:

```python
# Add default exclusion of plans from memory list
exclude_types_list = ["plan"]  # Always exclude plans from memories view
if exclude_sessions:
    exclude_types_list.append("session_summary")
```

**Also update frontend constants:**
- Remove "plan" from `MEMORY_TYPE_FILTER_OPTIONS` in `constants.ts` (line 589)
- Keep "plan" in `MEMORY_TYPES` and `MEMORY_TYPE_BADGE_CLASSES` for search results display

---

### 2. Create Plans API Endpoint

**File:** `daemon/routes/activity.py` (new endpoint)

Create `GET /api/activity/plans` that queries `prompt_batches` directly:

```python
@router.get("/api/activity/plans", response_model=PlansListResponse)
async def list_plans(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None, description="Filter by session"),
) -> PlansListResponse:
    """List plans from prompt_batches (direct SQLite, not ChromaDB)."""
```

**New response models in `daemon/models.py`:**

```python
class PlanListItem(BaseModel):
    id: int  # batch_id
    title: str  # extracted from file path or first heading
    session_id: str
    created_at: datetime
    file_path: str | None
    preview: str  # first 200 chars of plan_content
    plan_embedded: bool  # indexed in ChromaDB?

class PlansListResponse(BaseModel):
    plans: list[PlanListItem]
    total: int
    limit: int
    offset: int
```

**New ActivityStore method in `activity/store.py`:**

```python
def get_plans(
    self,
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None
) -> tuple[list[PromptBatch], int]:
    """Get plan batches from prompt_batches table."""
    # SELECT * FROM prompt_batches
    # WHERE source_type = ''plan'' AND plan_content IS NOT NULL
    # ORDER BY created_at_epoch DESC
    # LIMIT ? OFFSET ?
```

---

### 3. Create Plans Tab Component

**New file:** `daemon/ui/src/components/data/PlansList.tsx`

Component features:
- Fetch plans via new `usePlans()` hook
- Card grid layout (similar to MemoriesList)
- Show: title, file_path, created date, preview
- Link to session: "View Session" button → `/data/sessions/{session_id}`
- "View Full Plan" button → ContentDialog with full plan_content
- Delete plan functionality (removes from ChromaDB index, marks unembedded)
- Pagination with "Load more"

**New hook:** `daemon/ui/src/hooks/use-plans.ts`

```typescript
export function usePlans(options: { limit: number; offset: number; sessionId?: string }) {
    return useQuery({
        queryKey: ["plans", options],
        queryFn: () => fetchJson(`/api/activity/plans?${params}`),
    });
}
```

---

### 4. Add Plans Tab to Data Explorer

**File:** `daemon/ui/src/pages/DataExplorer.tsx`

```typescript
import { FileText } from "lucide-react";

const tabs = [
    { id: "sessions", label: "Sessions", path: "/data/sessions", icon: FolderGit2 },
    { id: "plans", label: "Plans", path: "/data/plans", icon: FileText },  // NEW
    { id: "memories", label: "Memories", path: "/data/memories", icon: Cpu },
];
```

**File:** `daemon/ui/src/router.tsx`

```typescript
{
    path: "data",
    element: <DataExplorer />,
    children: [
        { index: true, element: <Navigate to="sessions" replace /> },
        { path: "sessions", element: <SessionList /> },
        { path: "plans", element: <PlansList /> },  // NEW
        { path: "memories", element: <MemoriesList /> },
    ]
}
```

---

### 5. Update Frontend Constants

**File:** `daemon/ui/src/lib/constants.ts`

```typescript
// Add new API endpoint
export const API_ENDPOINTS = {
    // ... existing
    ACTIVITY_PLANS: "/api/activity/plans",
};

// Remove plan from memory filter options (keep in MEMORY_TYPES for search display)
export const MEMORY_TYPE_FILTER_OPTIONS = [
    { value: "all", label: "All Types" },
    { value: MEMORY_TYPES.GOTCHA, label: MEMORY_TYPE_LABELS.gotcha },
    { value: MEMORY_TYPES.DISCOVERY, label: MEMORY_TYPE_LABELS.discovery },
    { value: MEMORY_TYPES.BUG_FIX, label: MEMORY_TYPE_LABELS.bug_fix },
    { value: MEMORY_TYPES.DECISION, label: MEMORY_TYPE_LABELS.decision },
    { value: MEMORY_TYPES.TRADE_OFF, label: MEMORY_TYPE_LABELS.trade_off },
    { value: MEMORY_TYPES.SESSION_SUMMARY, label: MEMORY_TYPE_LABELS.session_summary },
    // REMOVED: { value: MEMORY_TYPES.PLAN, label: MEMORY_TYPE_LABELS.plan },
] as const;
```

---

## Files to Modify

| File | Change |
|------|--------|
| `daemon/routes/search.py` | Exclude plans from memories list by default |
| `daemon/routes/activity.py` | Add `/api/activity/plans` endpoint |
| `daemon/models.py` | Add `PlanListItem`, `PlansListResponse` models |
| `activity/store.py` | Add `get_plans()` method |
| `daemon/ui/src/pages/DataExplorer.tsx` | Add Plans tab |
| `daemon/ui/src/router.tsx` | Add plans route |
| `daemon/ui/src/components/data/PlansList.tsx` | NEW - Plans list component |
| `daemon/ui/src/hooks/use-plans.ts` | NEW - Plans data hook |
| `daemon/ui/src/lib/constants.ts` | Add endpoint, remove plan from memory filters |

---

## Search Functionality (No Changes Needed)

Plans will continue to appear in search results because:
- `RetrievalEngine.search()` already handles `search_type=''plans''` separately
- `VectorStore.search_memory(memory_types=[''plan''])` works correctly
- MCP tools (`oak_search`) already support `search_type=''plans''`
- UI Search page already displays `PlanResult` items

---

## Verification

1. **Memories list**: Should no longer show plan-type items
2. **Plans tab**: Shows all plans from prompt_batches with session links
3. **Search**: Plans still appear when searching (search_type=all or plans)
4. **Delete plan**: Removes from ChromaDB, marks unembedded in SQLite
5. **Link to session**: Clicking session link navigates to session detail
6. **MCP tools**: `oak_search` with `search_type=''plans''` still returns plans
7. **Build**: `npm run build` succeeds, daemon restarts cleanly


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/91eddd37-f8e7-460b-9915-1dedc774cf74.jsonl', '2026-01-24T18:37:26.556841', '2026-01-24T18:44:21.119504', 'completed', 43, 1, 'plan', 'plan', NULL, '# Plan: Separate Plans from Memories with Dedicated Plans Tab

## Problem Statement
Plans are currently shown in the Memories list, but they don''t belong there:
- **Memories** = LLM-generated observations based on agent activity (stored in `memory_observations`)
- **Plans** = Design documents from prompt_batches (stored in `prompt_batches` table)

Plans are indexed in ChromaDB for semantic search, but should have their own dedicated viewing experience in the Data Explorer.

## Goals
1. Remove plans from the Memories list
2. Create a dedicated "Plans" tab in Data Explorer
3. Plans should link back to their originating session
4. Maintain plan search functionality across CLI, API, MCP tools, and UI search

---

## Implementation Plan

### 1. Filter Plans Out of Memories List

**File:** `daemon/routes/search.py` (lines 254-307)

The API already supports `exclude_types` parameter through to VectorStore. Modify the `list_memories` endpoint:

```python
# Add default exclusion of plans from memory list
exclude_types_list = ["plan"]  # Always exclude plans from memories view
if exclude_sessions:
    exclude_types_list.append("session_summary")
```

**Also update frontend constants:**
- Remove "plan" from `MEMORY_TYPE_FILTER_OPTIONS` in `constants.ts` (line 589)
- Keep "plan" in `MEMORY_TYPES` and `MEMORY_TYPE_BADGE_CLASSES` for search results display

---

### 2. Create Plans API Endpoint

**File:** `daemon/routes/activity.py` (new endpoint)

Create `GET /api/activity/plans` that queries `prompt_batches` directly:

```python
@router.get("/api/activity/plans", response_model=PlansListResponse)
async def list_plans(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None, description="Filter by session"),
) -> PlansListResponse:
    """List plans from prompt_batches (direct SQLite, not ChromaDB)."""
```

**New response models in `daemon/models.py`:**

```python
class PlanListItem(BaseModel):
    id: int  # batch_id
    title: str  # extracted from file path or first heading
    session_id: str
    created_at: datetime
    file_path: str | None
    preview: str  # first 200 chars of plan_content
    plan_embedded: bool  # indexed in ChromaDB?

class PlansListResponse(BaseModel):
    plans: list[PlanListItem]
    total: int
    limit: int
    offset: int
```

**New ActivityStore method in `activity/store.py`:**

```python
def get_plans(
    self,
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None
) -> tuple[list[PromptBatch], int]:
    """Get plan batches from prompt_batches table."""
    # SELECT * FROM prompt_batches
    # WHERE source_type = ''plan'' AND plan_content IS NOT NULL
    # ORDER BY created_at_epoch DESC
    # LIMIT ? OFFSET ?
```

---

### 3. Create Plans Tab Component

**New file:** `daemon/ui/src/components/data/PlansList.tsx`

Component features:
- Fetch plans via new `usePlans()` hook
- Card grid layout (similar to MemoriesList)
- Show: title, file_path, created date, preview
- Link to session: "View Session" button → `/data/sessions/{session_id}`
- "View Full Plan" button → ContentDialog with full plan_content
- Delete plan functionality (removes from ChromaDB index, marks unembedded)
- Pagination with "Load more"

**New hook:** `daemon/ui/src/hooks/use-plans.ts`

```typescript
export function usePlans(options: { limit: number; offset: number; sessionId?: string }) {
    return useQuery({
        queryKey: ["plans", options],
        queryFn: () => fetchJson(`/api/activity/plans?${params}`),
    });
}
```

---

### 4. Add Plans Tab to Data Explorer

**File:** `daemon/ui/src/pages/DataExplorer.tsx`

```typescript
import { FileText } from "lucide-react";

const tabs = [
    { id: "sessions", label: "Sessions", path: "/data/sessions", icon: FolderGit2 },
    { id: "plans", label: "Plans", path: "/data/plans", icon: FileText },  // NEW
    { id: "memories", label: "Memories", path: "/data/memories", icon: Cpu },
];
```

**File:** `daemon/ui/src/router.tsx`

```typescript
{
    path: "data",
    element: <DataExplorer />,
    children: [
        { index: true, element: <Navigate to="sessions" replace /> },
        { path: "sessions", element: <SessionList /> },
        { path: "plans", element: <PlansList /> },  // NEW
        { path: "memories", element: <MemoriesList /> },
    ]
}
```

---

### 5. Update Frontend Constants

**File:** `daemon/ui/src/lib/constants.ts`

```typescript
// Add new API endpoint
export const API_ENDPOINTS = {
    // ... existing
    ACTIVITY_PLANS: "/api/activity/plans",
};

// Remove plan from memory filter options (keep in MEMORY_TYPES for search display)
export const MEMORY_TYPE_FILTER_OPTIONS = [
    { value: "all", label: "All Types" },
    { value: MEMORY_TYPES.GOTCHA, label: MEMORY_TYPE_LABELS.gotcha },
    { value: MEMORY_TYPES.DISCOVERY, label: MEMORY_TYPE_LABELS.discovery },
    { value: MEMORY_TYPES.BUG_FIX, label: MEMORY_TYPE_LABELS.bug_fix },
    { value: MEMORY_TYPES.DECISION, label: MEMORY_TYPE_LABELS.decision },
    { value: MEMORY_TYPES.TRADE_OFF, label: MEMORY_TYPE_LABELS.trade_off },
    { value: MEMORY_TYPES.SESSION_SUMMARY, label: MEMORY_TYPE_LABELS.session_summary },
    // REMOVED: { value: MEMORY_TYPES.PLAN, label: MEMORY_TYPE_LABELS.plan },
] as const;
```

---

## Files to Modify

| File | Change |
|------|--------|
| `daemon/routes/search.py` | Exclude plans from memories list by default |
| `daemon/routes/activity.py` | Add `/api/activity/plans` endpoint |
| `daemon/models.py` | Add `PlanListItem`, `PlansListResponse` models |
| `activity/store.py` | Add `get_plans()` method |
| `daemon/ui/src/pages/DataExplorer.tsx` | Add Plans tab |
| `daemon/ui/src/router.tsx` | Add plans route |
| `daemon/ui/src/components/data/PlansList.tsx` | NEW - Plans list component |
| `daemon/ui/src/hooks/use-plans.ts` | NEW - Plans data hook |
| `daemon/ui/src/lib/constants.ts` | Add endpoint, remove plan from memory filters |

---

## Search Functionality (No Changes Needed)

Plans will continue to appear in search results because:
- `RetrievalEngine.search()` already handles `search_type=''plans''` separately
- `VectorStore.search_memory(memory_types=[''plan''])` works correctly
- MCP tools (`oak_search`) already support `search_type=''plans''`
- UI Search page already displays `PlanResult` items

---

## Verification

1. **Memories list**: Should no longer show plan-type items
2. **Plans tab**: Shows all plans from prompt_batches with session links
3. **Search**: Plans still appear when searching (search_type=all or plans)
4. **Delete plan**: Removes from ChromaDB, marks unembedded in SQLite
5. **Link to session**: Clicking session link navigates to session detail
6. **MCP tools**: `oak_search` with `search_type=''plans''` still returns plans
7. **Build**: `npm run build` succeeds, daemon restarts cleanly


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/91eddd37-f8e7-460b-9915-1dedc774cf74.jsonl', 1769297846, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (53, 'e675ea0c-3acb-4411-b69e-92f901786a15', 2, 'this is looking good, now for session 91eddd37-f8e7-460b-9915-1dedc774cf74 , and it looks like all sessions given the screen shots, we have duplicate plans on the new plans tab. i know there is only one plan, so lets figure out what''s going on', '2026-01-25T09:38:27.047063', '2026-01-25T09:41:08.990010', 'completed', 7, 0, NULL, 'user', NULL, NULL, 1769351907, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (54, 'e675ea0c-3acb-4411-b69e-92f901786a15', 3, 'i don''t want to require a file path, that may not be consistent across agents', '2026-01-25T09:41:09.300209', NULL, 'completed', 10, 0, NULL, 'user', NULL, NULL, 1769352069, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (55, 'db06f42f-8d00-4c8c-a4c2-2a77a4535e5f', 1, 'Implement the following plan:

# Plan: Improve Codebase Intelligence Context Injection

## Summary

Remove ineffective CLI command reminders, enhance automatic context injection with code snippets and richer search queries, and refactor hooks.py for maintainability.

**Problem**: CLI reminders ("PREFER `oak ci`...") rarely drive agent behavior (~1/20 sessions). Code chunks are indexed but not injected. Post-tool-use searches use narrow file-path-only queries. hooks.py is 1,357 lines and growing.

**Solution**:
1. Extract context-building helpers to `injection.py`
2. Remove CLI reminders
3. Add code snippet injection at prompt-submit
4. Enhance post-tool-use with richer queries

---

## Phase 1: Extract Context Helpers to injection.py

**Create**: `src/open_agent_kit/features/codebase_intelligence/daemon/routes/injection.py`

Move these helpers from hooks.py:
- `_format_memories_for_injection()` (lines 79-113)
- `_format_session_summaries()` (lines 115-143)
- `_build_session_context()` (lines 146-212)

Add new helpers in injection.py:
- `_format_code_for_injection()` - Format code chunks as markdown
- `_build_rich_search_query()` - Build semantic search query from context

**Update**: `hooks.py`
- Import helpers from injection.py
- Remove moved code (~140 lines)

---

## Phase 2: Remove CLI Command Reminders

**File**: `injection.py` (after move)

**Location 1 - `_build_session_context()`**:
```python
# CURRENT (remove the CLI commands):
parts.append(
    f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
    f"{memory_count} memories stored.\n\n"
    "**PREFER** `oak ci` over grep/read for code discovery:\n"
    "- `oak ci search ''<query>''` - Semantic search...\n"
    ...
)

# REPLACE WITH (simple status only):
parts.append(
    f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
    f"{memory_count} memories stored."
)
```

**File**: `hooks.py`

**Location 2 - `hook_post_tool_use()` (lines 775-788)**: Delete entire block that injects "TIP: `oak ci search`" after 3+ Grep/Glob uses.

---

## Phase 3: Add Code Snippet Injection at Prompt-Submit

**File**: `injection.py`

```python
def format_code_for_injection(
    code_chunks: list[dict],
    max_chunks: int = 3,
    max_lines_per_chunk: int = 50,
) -> str:
    """Format code chunks as markdown for context injection."""
    if not code_chunks:
        return ""

    parts = ["## Relevant Code\n"]
    for chunk in code_chunks[:max_chunks]:
        filepath = chunk.get("filepath", "unknown")
        start_line = chunk.get("start_line", 1)
        end_line = chunk.get("end_line", start_line)
        name = chunk.get("name", "")
        content = chunk.get("content", "")

        # Truncate long chunks
        lines = content.split("\n")
        if len(lines) > max_lines_per_chunk:
            content = "\n".join(lines[:max_lines_per_chunk]) + f"\n... ({len(lines) - max_lines_per_chunk} more lines)"

        # Detect language from extension
        ext = filepath.rsplit(".", 1)[-1] if "." in filepath else ""
        lang_map = {"py": "python", "ts": "typescript", "js": "javascript", "tsx": "typescript"}
        lang = lang_map.get(ext, ext)

        header = f"**{filepath}** (L{start_line}-{end_line})"
        if name:
            header += f" - `{name}`"
        parts.append(f"{header}\n```{lang}\n{content}\n```\n")

    return "\n".join(parts)
```

**File**: `hooks.py` - Modify `hook_prompt_submit()` (after line 509):
```python
    # Search for relevant code based on prompt
    if state.retrieval_engine:
        try:
            code_result = state.retrieval_engine.search(
                query=prompt,
                search_type="code",
                limit=10,
            )
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                code_result.code, min_confidence="high"
            )
            if high_confidence_code:
                code_text = format_code_for_injection(high_confidence_code[:3])
                if code_text:
                    if "injected_context" in context:
                        context["injected_context"] = f"{code_text}\n\n{context[''injected_context'']}"
                    else:
                        context["injected_context"] = code_text
                    logger.info(f"Injecting {min(3, len(high_confidence_code))} code chunks for prompt")
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search code for prompt: {e}")
```

---

## Phase 4: Enhance Post-Tool-Use Search Queries

**File**: `injection.py`

```python
def build_rich_search_query(
    file_path: str,
    tool_output: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Build search query from file path + context for richer semantic matching."""
    parts = [file_path]

    # Add tool output excerpt (skip noise patterns like file content)
    if tool_output:
        noise_prefixes = ("Read ", "1→", "{", "[")
        if not any(tool_output.strip().startswith(p) for p in noise_prefixes):
            excerpt = tool_output[:200].strip()
            if excerpt:
                parts.append(excerpt)

    # Add user prompt excerpt
    if user_prompt:
        parts.append(user_prompt[:150].strip())

    return " ".join(parts)
```

**File**: `hooks.py` - Modify `hook_post_tool_use()` memory search:
```python
    if tool_name in ("Read", "Edit", "Write") and state.retrieval_engine:
        file_path = tool_input.get("file_path", "")
        if file_path:
            try:
                # Get user prompt for richer context
                user_prompt = None
                if session and session.current_prompt_batch_id and state.activity_store:
                    batch = state.activity_store.get_prompt_batch(session.current_prompt_batch_id)
                    if batch:
                        user_prompt = batch.user_prompt

                # Build rich query (not just file path)
                search_query = build_rich_search_query(
                    file_path=file_path,
                    tool_output=tool_output if tool_name != "Read" else None,
                    user_prompt=user_prompt,
                )

                search_res = state.retrieval_engine.search(
                    query=search_query,  # Was: f"file:{file_path}"
                    search_type="memory",
                    limit=8,
                )
                # ... rest unchanged (confidence filtering, formatting)
```

---

## Files Summary

| File | Action |
|------|--------|
| `daemon/routes/injection.py` | **CREATE** - Context building helpers |
| `daemon/routes/hooks.py` | **MODIFY** - Import from injection.py, remove CLI reminders, add code/query logic |
| `constants.py` | **MODIFY** (optional) - Add injection limit constants |

**Net effect on hooks.py**: ~1,357 lines → ~1,250 lines (extract ~140, add ~40)

---

## Verification

1. **Unit tests**: Add `tests/unit/.../daemon/routes/test_injection.py`
   - `test_format_code_for_injection()` - verify formatting, truncation
   - `test_build_rich_search_query()` - verify query construction
   - `test_build_session_context()` - verify no CLI reminders

2. **Manual test**:
   - Start daemon (`oak ci start`)
   - Trigger hooks via Claude Code session
   - Verify no CLI reminders at session start
   - Verify code snippets appear for relevant prompts
   - Check daemon logs for injection messages

3. **Run quality gate**: `make check`


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/23a3b5d1-4021-425d-9b63-812aefc12ccd.jsonl', '2026-01-25T09:56:03.962874', '2026-01-25T10:08:17.170742', 'completed', 65, 1, 'plan', 'plan', NULL, '# Plan: Improve Codebase Intelligence Context Injection

## Summary

Remove ineffective CLI command reminders, enhance automatic context injection with code snippets and richer search queries, and refactor hooks.py for maintainability.

**Problem**: CLI reminders ("PREFER `oak ci`...") rarely drive agent behavior (~1/20 sessions). Code chunks are indexed but not injected. Post-tool-use searches use narrow file-path-only queries. hooks.py is 1,357 lines and growing.

**Solution**:
1. Extract context-building helpers to `injection.py`
2. Remove CLI reminders
3. Add code snippet injection at prompt-submit
4. Enhance post-tool-use with richer queries

---

## Phase 1: Extract Context Helpers to injection.py

**Create**: `src/open_agent_kit/features/codebase_intelligence/daemon/routes/injection.py`

Move these helpers from hooks.py:
- `_format_memories_for_injection()` (lines 79-113)
- `_format_session_summaries()` (lines 115-143)
- `_build_session_context()` (lines 146-212)

Add new helpers in injection.py:
- `_format_code_for_injection()` - Format code chunks as markdown
- `_build_rich_search_query()` - Build semantic search query from context

**Update**: `hooks.py`
- Import helpers from injection.py
- Remove moved code (~140 lines)

---

## Phase 2: Remove CLI Command Reminders

**File**: `injection.py` (after move)

**Location 1 - `_build_session_context()`**:
```python
# CURRENT (remove the CLI commands):
parts.append(
    f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
    f"{memory_count} memories stored.\n\n"
    "**PREFER** `oak ci` over grep/read for code discovery:\n"
    "- `oak ci search ''<query>''` - Semantic search...\n"
    ...
)

# REPLACE WITH (simple status only):
parts.append(
    f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
    f"{memory_count} memories stored."
)
```

**File**: `hooks.py`

**Location 2 - `hook_post_tool_use()` (lines 775-788)**: Delete entire block that injects "TIP: `oak ci search`" after 3+ Grep/Glob uses.

---

## Phase 3: Add Code Snippet Injection at Prompt-Submit

**File**: `injection.py`

```python
def format_code_for_injection(
    code_chunks: list[dict],
    max_chunks: int = 3,
    max_lines_per_chunk: int = 50,
) -> str:
    """Format code chunks as markdown for context injection."""
    if not code_chunks:
        return ""

    parts = ["## Relevant Code\n"]
    for chunk in code_chunks[:max_chunks]:
        filepath = chunk.get("filepath", "unknown")
        start_line = chunk.get("start_line", 1)
        end_line = chunk.get("end_line", start_line)
        name = chunk.get("name", "")
        content = chunk.get("content", "")

        # Truncate long chunks
        lines = content.split("\n")
        if len(lines) > max_lines_per_chunk:
            content = "\n".join(lines[:max_lines_per_chunk]) + f"\n... ({len(lines) - max_lines_per_chunk} more lines)"

        # Detect language from extension
        ext = filepath.rsplit(".", 1)[-1] if "." in filepath else ""
        lang_map = {"py": "python", "ts": "typescript", "js": "javascript", "tsx": "typescript"}
        lang = lang_map.get(ext, ext)

        header = f"**{filepath}** (L{start_line}-{end_line})"
        if name:
            header += f" - `{name}`"
        parts.append(f"{header}\n```{lang}\n{content}\n```\n")

    return "\n".join(parts)
```

**File**: `hooks.py` - Modify `hook_prompt_submit()` (after line 509):
```python
    # Search for relevant code based on prompt
    if state.retrieval_engine:
        try:
            code_result = state.retrieval_engine.search(
                query=prompt,
                search_type="code",
                limit=10,
            )
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                code_result.code, min_confidence="high"
            )
            if high_confidence_code:
                code_text = format_code_for_injection(high_confidence_code[:3])
                if code_text:
                    if "injected_context" in context:
                        context["injected_context"] = f"{code_text}\n\n{context[''injected_context'']}"
                    else:
                        context["injected_context"] = code_text
                    logger.info(f"Injecting {min(3, len(high_confidence_code))} code chunks for prompt")
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search code for prompt: {e}")
```

---

## Phase 4: Enhance Post-Tool-Use Search Queries

**File**: `injection.py`

```python
def build_rich_search_query(
    file_path: str,
    tool_output: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Build search query from file path + context for richer semantic matching."""
    parts = [file_path]

    # Add tool output excerpt (skip noise patterns like file content)
    if tool_output:
        noise_prefixes = ("Read ", "1→", "{", "[")
        if not any(tool_output.strip().startswith(p) for p in noise_prefixes):
            excerpt = tool_output[:200].strip()
            if excerpt:
                parts.append(excerpt)

    # Add user prompt excerpt
    if user_prompt:
        parts.append(user_prompt[:150].strip())

    return " ".join(parts)
```

**File**: `hooks.py` - Modify `hook_post_tool_use()` memory search:
```python
    if tool_name in ("Read", "Edit", "Write") and state.retrieval_engine:
        file_path = tool_input.get("file_path", "")
        if file_path:
            try:
                # Get user prompt for richer context
                user_prompt = None
                if session and session.current_prompt_batch_id and state.activity_store:
                    batch = state.activity_store.get_prompt_batch(session.current_prompt_batch_id)
                    if batch:
                        user_prompt = batch.user_prompt

                # Build rich query (not just file path)
                search_query = build_rich_search_query(
                    file_path=file_path,
                    tool_output=tool_output if tool_name != "Read" else None,
                    user_prompt=user_prompt,
                )

                search_res = state.retrieval_engine.search(
                    query=search_query,  # Was: f"file:{file_path}"
                    search_type="memory",
                    limit=8,
                )
                # ... rest unchanged (confidence filtering, formatting)
```

---

## Files Summary

| File | Action |
|------|--------|
| `daemon/routes/injection.py` | **CREATE** - Context building helpers |
| `daemon/routes/hooks.py` | **MODIFY** - Import from injection.py, remove CLI reminders, add code/query logic |
| `constants.py` | **MODIFY** (optional) - Add injection limit constants |

**Net effect on hooks.py**: ~1,357 lines → ~1,250 lines (extract ~140, add ~40)

---

## Verification

1. **Unit tests**: Add `tests/unit/.../daemon/routes/test_injection.py`
   - `test_format_code_for_injection()` - verify formatting, truncation
   - `test_build_rich_search_query()` - verify query construction
   - `test_build_session_context()` - verify no CLI reminders

2. **Manual test**:
   - Start daemon (`oak ci start`)
   - Trigger hooks via Claude Code session
   - Verify no CLI reminders at session start
   - Verify code snippets appear for relevant prompts
   - Check daemon logs for injection messages

3. **Run quality gate**: `make check`


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/23a3b5d1-4021-425d-9b63-812aefc12ccd.jsonl', 1769352963, 1);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (56, 'db06f42f-8d00-4c8c-a4c2-2a77a4535e5f', 2, 'lets use this info, allong with all of the other hooks functionality and create a new document in @docs/ which exactly how they work, what hooks, the lifecycle, what we capture, and what we inject, so we can move foward with a solid reference doc', '2026-01-25T10:10:15.669247', '2026-01-25T10:13:50.848770', 'completed', 9, 0, NULL, 'user', NULL, NULL, 1769353815, 0);
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, ended_at, status, activity_count, processed, classification, source_type, plan_file_path, plan_content, created_at_epoch, plan_embedded) VALUES (57, '21480a13-f486-47d0-8ab4-65b997828049', 1, 'Implement the following plan:

# Store Module Decomposition Plan

## Summary

Decompose two large store modules in the codebase intelligence feature:
- `activity/store.py` (3,042 lines) → 12 focused files
- `memory/store.py` (1,309 lines) → 9 focused files

Following existing OAK patterns from `activity/processor/` and `strategic_planning/plan/`.

---

## Part 1: activity/store.py Decomposition

### New Directory Structure

```
activity/store/
├── __init__.py          # Re-exports for backward compatibility
├── schema.py            # SCHEMA_VERSION, SCHEMA_SQL (~200 lines)
├── migrations.py        # All migration methods (~400 lines)
├── models.py            # Activity, PromptBatch, Session, StoredObservation (~270 lines)
├── core.py              # ActivityStore class + connection management (~150 lines)
├── sessions.py          # Session CRUD operations (~220 lines)
├── batches.py           # Prompt batch operations + plan embedding (~350 lines)
├── activities.py        # Activity CRUD and FTS5 search (~250 lines)
├── observations.py      # Memory observation storage (~250 lines)
├── stats.py             # Statistics and caching (~300 lines)
├── backup.py            # SQL export/import (~160 lines)
└── delete.py            # Cascade delete operations (~180 lines)
```

### Design Approach

**Function delegation pattern** (not mixins):
- Keep `ActivityStore` as a single class in `core.py`
- Each operation module exports standalone functions that take `store` as first param
- `ActivityStore` methods delegate to these functions
- Simpler than mixins, better IDE navigation, easier testing

Example in `core.py`:
```python
from . import sessions, batches, activities

class ActivityStore:
    def create_session(self, session_id: str, agent: str, project_root: str) -> Session:
        return sessions.create_session(self, session_id, agent, project_root)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `schema.py` | `SCHEMA_VERSION=10`, `SCHEMA_SQL` constant |
| `migrations.py` | `apply_migrations()`, 7 `migrate_vX_to_vY()` functions |
| `models.py` | 4 dataclasses with `to_row()`/`from_row()` methods |
| `core.py` | `ActivityStore.__init__`, connection mgmt, `_transaction()`, `optimize_database()` |
| `sessions.py` | 11 session methods (create, get, end, reactivate, stats) |
| `batches.py` | 18 batch methods (CRUD, recovery, plan embedding incl. mark_plan_unembedded) |
| `activities.py` | 8 activity methods (add, buffer, search FTS5) |
| `observations.py` | 10 observation methods (store, embed tracking) |
| `stats.py` | 6 stats methods (caching, bulk queries) |
| `backup.py` | `export_to_sql()`, `import_from_sql()` |
| `delete.py` | 6 cascade delete methods |

---

## Part 2: memory/store.py Decomposition

### New Directory Structure

```
memory/store/
├── __init__.py          # Re-exports for backward compatibility
├── constants.py         # CODE_COLLECTION, MEMORY_COLLECTION (~20 lines)
├── classification.py    # DOC_TYPE_*, classify_doc_type(), get_short_path() (~100 lines)
├── models.py            # CodeChunk, MemoryObservation, PlanObservation (~170 lines)
├── core.py              # VectorStore class + ChromaDB init (~250 lines)
├── code_ops.py          # Code indexing operations (~200 lines)
├── memory_ops.py        # Memory/plan add/delete (~120 lines)
├── search.py            # search_code(), search_memory(), get_by_ids() (~100 lines)
└── management.py        # Stats, listing, archiving, cleanup (~350 lines)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `constants.py` | Collection name constants |
| `classification.py` | Doc type patterns, `classify_doc_type()`, `get_short_path()` |
| `models.py` | 3 dataclasses with embedding/metadata methods |
| `core.py` | `VectorStore.__init__`, ChromaDB setup, dimension handling |
| `code_ops.py` | `add_code_chunks()`, `add_code_chunks_batched()`, `delete_code_by_filepath()` |
| `memory_ops.py` | `add_memory()`, `add_plan()`, `delete_memories()` |
| `search.py` | Semantic search functions |
| `management.py` | Archive, tags, listing, stats, cleanup |

---

## Part 3: Implementation Order

### Phase 1: Activity Store Models (Low Risk)
1. Create `activity/store/` directory
2. Create `activity/store/models.py` - extract 4 dataclasses
3. Create `activity/store/schema.py` - extract constants
4. Create `activity/store/__init__.py` - re-export from models/schema + old store
5. Run tests: `pytest tests/unit/features/codebase_intelligence/test_activity.py -v`

### Phase 2: Activity Store Operations
6. Create `activity/store/migrations.py` - extract migration functions
7. Create `activity/store/sessions.py` - extract session operations
8. Create `activity/store/batches.py` - extract batch operations
9. Create `activity/store/activities.py` - extract activity operations
10. Create `activity/store/observations.py` - extract observation operations
11. Create `activity/store/stats.py` - extract stats operations
12. Create `activity/store/backup.py` - extract backup operations
13. Create `activity/store/delete.py` - extract delete operations
14. Refactor `activity/store/core.py` - keep only core class with delegation
15. Update `activity/store/__init__.py` - re-export from all modules
16. Run full test suite

### Phase 3: Memory Store
17. Create `memory/store/` directory
18. Create `memory/store/constants.py`
19. Create `memory/store/classification.py`
20. Create `memory/store/models.py`
21. Create `memory/store/__init__.py` - re-export + old store
22. Create `memory/store/code_ops.py`
23. Create `memory/store/memory_ops.py`
24. Create `memory/store/search.py`
25. Create `memory/store/management.py`
26. Refactor `memory/store/core.py`
27. Update `memory/store/__init__.py`
28. Run full test suite

### Phase 4: Cleanup
29. Delete `activity/store.py` (original file)
30. Delete `memory/store.py` (original file)
31. Update `activity/__init__.py` if needed
32. Update `memory/__init__.py` if needed
33. Run `make check`

---

## Part 4: Backward Compatibility

### Import Preservation

All existing imports will continue working via `__init__.py` re-exports:

```python
# These imports work unchanged:
from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity, ActivityStore, PromptBatch, Session, StoredObservation
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    VectorStore, CodeChunk, MemoryObservation, PlanObservation
)
```

### Affected Modules (No Changes Required)

**activity/store.py consumers (11+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`, `titles.py`
- `daemon/state.py`, `daemon/routes/backup.py`, `daemon/routes/activity.py`
- `service.py`, `commands/ci_cmd.py`

**memory/store.py consumers (13+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`
- `daemon/state.py`, `daemon/server.py`
- `indexing/indexer.py`, `retrieval/engine.py`
- `memory/__init__.py`

---

## Part 5: Verification

### After Each Phase
```bash
# Run unit tests
pytest tests/unit/features/codebase_intelligence/ -v

# Run feature tests
pytest tests/features/codebase_intelligence/ -v
```

### Final Verification
```bash
# Full quality gate
make check

# Verify imports still work
python -c "from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore, Activity, Session, PromptBatch"
python -c "from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore, CodeChunk"
```

---

## Critical Files

| File | Action |
|------|--------|
| `src/.../activity/store.py` | Source (2,937 lines) → decompose → delete |
| `src/.../memory/store.py` | Source (1,309 lines) → decompose → delete |
| `src/.../activity/processor/__init__.py` | Pattern to follow |
| `tests/.../test_activity.py` | Verify no regressions |
| `tests/.../test_memory_store.py` | Verify no regressions |


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/f4c052d2-2753-49d2-966a-0d989a9366b4.jsonl', '2026-01-25T10:16:28.561553', '2026-01-25T10:32:17.800779', 'completed', 58, 1, 'plan', 'plan', NULL, '# Store Module Decomposition Plan

## Summary

Decompose two large store modules in the codebase intelligence feature:
- `activity/store.py` (3,042 lines) → 12 focused files
- `memory/store.py` (1,309 lines) → 9 focused files

Following existing OAK patterns from `activity/processor/` and `strategic_planning/plan/`.

---

## Part 1: activity/store.py Decomposition

### New Directory Structure

```
activity/store/
├── __init__.py          # Re-exports for backward compatibility
├── schema.py            # SCHEMA_VERSION, SCHEMA_SQL (~200 lines)
├── migrations.py        # All migration methods (~400 lines)
├── models.py            # Activity, PromptBatch, Session, StoredObservation (~270 lines)
├── core.py              # ActivityStore class + connection management (~150 lines)
├── sessions.py          # Session CRUD operations (~220 lines)
├── batches.py           # Prompt batch operations + plan embedding (~350 lines)
├── activities.py        # Activity CRUD and FTS5 search (~250 lines)
├── observations.py      # Memory observation storage (~250 lines)
├── stats.py             # Statistics and caching (~300 lines)
├── backup.py            # SQL export/import (~160 lines)
└── delete.py            # Cascade delete operations (~180 lines)
```

### Design Approach

**Function delegation pattern** (not mixins):
- Keep `ActivityStore` as a single class in `core.py`
- Each operation module exports standalone functions that take `store` as first param
- `ActivityStore` methods delegate to these functions
- Simpler than mixins, better IDE navigation, easier testing

Example in `core.py`:
```python
from . import sessions, batches, activities

class ActivityStore:
    def create_session(self, session_id: str, agent: str, project_root: str) -> Session:
        return sessions.create_session(self, session_id, agent, project_root)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `schema.py` | `SCHEMA_VERSION=10`, `SCHEMA_SQL` constant |
| `migrations.py` | `apply_migrations()`, 7 `migrate_vX_to_vY()` functions |
| `models.py` | 4 dataclasses with `to_row()`/`from_row()` methods |
| `core.py` | `ActivityStore.__init__`, connection mgmt, `_transaction()`, `optimize_database()` |
| `sessions.py` | 11 session methods (create, get, end, reactivate, stats) |
| `batches.py` | 18 batch methods (CRUD, recovery, plan embedding incl. mark_plan_unembedded) |
| `activities.py` | 8 activity methods (add, buffer, search FTS5) |
| `observations.py` | 10 observation methods (store, embed tracking) |
| `stats.py` | 6 stats methods (caching, bulk queries) |
| `backup.py` | `export_to_sql()`, `import_from_sql()` |
| `delete.py` | 6 cascade delete methods |

---

## Part 2: memory/store.py Decomposition

### New Directory Structure

```
memory/store/
├── __init__.py          # Re-exports for backward compatibility
├── constants.py         # CODE_COLLECTION, MEMORY_COLLECTION (~20 lines)
├── classification.py    # DOC_TYPE_*, classify_doc_type(), get_short_path() (~100 lines)
├── models.py            # CodeChunk, MemoryObservation, PlanObservation (~170 lines)
├── core.py              # VectorStore class + ChromaDB init (~250 lines)
├── code_ops.py          # Code indexing operations (~200 lines)
├── memory_ops.py        # Memory/plan add/delete (~120 lines)
├── search.py            # search_code(), search_memory(), get_by_ids() (~100 lines)
└── management.py        # Stats, listing, archiving, cleanup (~350 lines)
```

### File Responsibilities

| File | Contents |
|------|----------|
| `constants.py` | Collection name constants |
| `classification.py` | Doc type patterns, `classify_doc_type()`, `get_short_path()` |
| `models.py` | 3 dataclasses with embedding/metadata methods |
| `core.py` | `VectorStore.__init__`, ChromaDB setup, dimension handling |
| `code_ops.py` | `add_code_chunks()`, `add_code_chunks_batched()`, `delete_code_by_filepath()` |
| `memory_ops.py` | `add_memory()`, `add_plan()`, `delete_memories()` |
| `search.py` | Semantic search functions |
| `management.py` | Archive, tags, listing, stats, cleanup |

---

## Part 3: Implementation Order

### Phase 1: Activity Store Models (Low Risk)
1. Create `activity/store/` directory
2. Create `activity/store/models.py` - extract 4 dataclasses
3. Create `activity/store/schema.py` - extract constants
4. Create `activity/store/__init__.py` - re-export from models/schema + old store
5. Run tests: `pytest tests/unit/features/codebase_intelligence/test_activity.py -v`

### Phase 2: Activity Store Operations
6. Create `activity/store/migrations.py` - extract migration functions
7. Create `activity/store/sessions.py` - extract session operations
8. Create `activity/store/batches.py` - extract batch operations
9. Create `activity/store/activities.py` - extract activity operations
10. Create `activity/store/observations.py` - extract observation operations
11. Create `activity/store/stats.py` - extract stats operations
12. Create `activity/store/backup.py` - extract backup operations
13. Create `activity/store/delete.py` - extract delete operations
14. Refactor `activity/store/core.py` - keep only core class with delegation
15. Update `activity/store/__init__.py` - re-export from all modules
16. Run full test suite

### Phase 3: Memory Store
17. Create `memory/store/` directory
18. Create `memory/store/constants.py`
19. Create `memory/store/classification.py`
20. Create `memory/store/models.py`
21. Create `memory/store/__init__.py` - re-export + old store
22. Create `memory/store/code_ops.py`
23. Create `memory/store/memory_ops.py`
24. Create `memory/store/search.py`
25. Create `memory/store/management.py`
26. Refactor `memory/store/core.py`
27. Update `memory/store/__init__.py`
28. Run full test suite

### Phase 4: Cleanup
29. Delete `activity/store.py` (original file)
30. Delete `memory/store.py` (original file)
31. Update `activity/__init__.py` if needed
32. Update `memory/__init__.py` if needed
33. Run `make check`

---

## Part 4: Backward Compatibility

### Import Preservation

All existing imports will continue working via `__init__.py` re-exports:

```python
# These imports work unchanged:
from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity, ActivityStore, PromptBatch, Session, StoredObservation
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    VectorStore, CodeChunk, MemoryObservation, PlanObservation
)
```

### Affected Modules (No Changes Required)

**activity/store.py consumers (11+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`, `titles.py`
- `daemon/state.py`, `daemon/routes/backup.py`, `daemon/routes/activity.py`
- `service.py`, `commands/ci_cmd.py`

**memory/store.py consumers (13+):**
- `activity/processor/core.py`, `handlers.py`, `summaries.py`, `observation.py`, `indexing.py`
- `daemon/state.py`, `daemon/server.py`
- `indexing/indexer.py`, `retrieval/engine.py`
- `memory/__init__.py`

---

## Part 5: Verification

### After Each Phase
```bash
# Run unit tests
pytest tests/unit/features/codebase_intelligence/ -v

# Run feature tests
pytest tests/features/codebase_intelligence/ -v
```

### Final Verification
```bash
# Full quality gate
make check

# Verify imports still work
python -c "from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore, Activity, Session, PromptBatch"
python -c "from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore, CodeChunk"
```

---

## Critical Files

| File | Action |
|------|--------|
| `src/.../activity/store.py` | Source (2,937 lines) → decompose → delete |
| `src/.../memory/store.py` | Source (1,309 lines) → decompose → delete |
| `src/.../activity/processor/__init__.py` | Pattern to follow |
| `tests/.../test_activity.py` | Verify no regressions |
| `tests/.../test_memory_store.py` | Verify no regressions |


If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at: /Users/chris/.claude/projects/-Users-chris-Repos-open-agent-kit/f4c052d2-2753-49d2-966a-0d989a9366b4.jsonl', 1769354188, 1);

-- memory_observations (173 records)
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('05f21812-861f-4ca3-89ed-c405f7f224ef', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The indexing pipeline reports 373 indexable files, but only 364 are successfully chunked. The discrepancy is mainly due to nine empty files that are counted as indexable but produce zero chunks. These empty files are listed in the "Empty files" section of the indexing output.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/indexing/indexer.py & watcher.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:21:52.597390', 1769228512, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('db0d085e-5219-4d6c-81d5-5cc38e8a3dc8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The file watcher currently ignores deletions of files that are not in the managed paths list (derived from agent manifests). As a result, when a file is removed from the project root but not part of a managed path, the index still contains stale chunks until a full reindex is triggered.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/indexing/watcher.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:21:52.742042', 1769228512, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c455f559-d976-4acb-9fc3-0bbcf489adfd', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The UI displays the total number of chunks by querying the `oak_code` collection directly. The displayed count is updated only when the watcher emits a `file_changed` event and the state is refreshed. If the watcher fails to emit an event (e.g., due to a missed file system notification), the UI number lags behind the actual index content.', 'discovery', 'UI components consuming state from oak_code collection', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:21:52.825494', 1769228512, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('3e418f25-b79a-4a11-adf4-4504067b1885', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The indexing configuration does not currently honor the `.gitignore` file. Files that are ignored by Git (e.g., in `.oak/ci/`) are still scanned and counted as indexable, which inflates the file count. This is why the index shows more files than expected when a fresh clone contains many ignored files.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/config.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:21:52.906118', 1769228512, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('4ec277a6-0d78-495c-b709-86d55a410d61', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The watcher uses a background thread to poll the file system rather than relying on OS‑level inotify events. This design choice simplifies cross‑platform support but introduces a latency of up to the polling interval (default 5 s). Consequently, the UI may show stale counts for a brief period after a file change.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/indexing/watcher.py', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-23T23:21:52.970030', 1769228512, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('bd22a408-ebb9-4264-a185-af9a44fc5e44', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The decision to keep empty files in the indexable list was made to simplify the scanning logic, but it leads to a small over‑count. A future refactor could filter out files with size 0 before chunking.', 'decision', 'src/open_agent_kit/features/codebase_intelligence/indexing/indexer.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:21:53.030529', 1769228513, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('a82ba5eb-776c-4646-9a03-9b78ffc26979', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The indexer loads exclusion patterns from two sources: the project’s .gitignore and the config.py file.  The config file contains a default list of patterns (e.g., .git, node_modules) plus a CI‑managed list that is added at runtime.  Adding the CI exclusions increased the indexed file count by 8, which shows that those files were previously excluded by the config but not by .gitignore alone.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/config.py & indexer.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:28:17.160595', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('4935d2b9-5a17-4db5-b5ae-cd24591c9632', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'Files that are empty or too small produce 0 chunks.  They are still counted in the "Files indexed" total but contribute nothing to the chunk count.  This inflates the file count and can mislead users into thinking the index is larger than it actually is.', 'gotcha', 'indexer.py & chunking logic', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:28:17.238968', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('99e690ce-10fc-4fba-9331-661dbf51da0b', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The UI displays the file count and chunk count separately.  Because 0‑chunk files are included in the file count but not in the chunk count, the two numbers can diverge.  Users should be aware that a high file count does not necessarily mean a proportional number of chunks.', 'gotcha', 'UI component that shows index statistics', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:28:17.299333', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('172f3f59-cfc9-4ef5-bb4d-9030490e7e4f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The file watcher runs in a background thread and updates the index as soon as a file is added, modified, or deleted.  Log entries such as "Status: indexing" and "Indexing: True" confirm that the watcher is active.  The UI only switches to "Status: ready" after the indexing operation completes, ensuring that the displayed numbers are up‑to‑date.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/indexing/watcher.py & UI status indicator', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:28:17.363414', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('e0fce1d0-7611-4e8b-9504-0b9396f75323', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'Agent manifests declare "managed paths" (e.g., .agent/skills, .claude/commands).  Files under these paths are always indexed even if they would otherwise be ignored by .gitignore or the config exclusions.  This can cause the indexed file count to be higher than expected if the manifests include many files.', 'gotcha', 'agent manifests & indexer inclusion logic', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:28:17.430591', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('1522b361-d172-4350-9c49-a234bdaaf7e8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 4, 'The indexer uses a simple glob traversal and linear scans to build the index.  This approach is straightforward and works well for the current repository size (~370 files), but it may become a bottleneck for larger codebases.  The trade‑off was simplicity over performance, which is acceptable for the current use case.', 'discovery', 'indexer.py implementation', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-23T23:28:17.494830', 1769228897, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('91e01f03-a44d-4ed2-ba17-d9118d2f2126', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Implemented a dedicated background thread for the indexing process and file watcher, keeping the FastAPI event loop free for handling HTTP requests. This isolates long‑running I/O from the request handling path.', 'decision', 'Codebase Intelligence Daemon', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-23T23:36:43.723819', 1769229403, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('5f08e5a0-7610-4b7d-baf1-30d5466c97e0', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Chose a simple JSON polling endpoint for UI status instead of a WebSocket or Server‑Sent Events stream. The trade‑off is reduced real‑time latency in exchange for lower complexity and easier deployment.', 'discovery', 'Dashboard UI', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-23T23:36:43.786314', 1769229403, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('cd049a0f-409f-4a13-978a-01008d779aa9', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'The UI displays "ready" while indexing is still running because the `indexing` flag was only set to `True` after the indexing coroutine started, not before. This caused a race where the status endpoint returned the stale value.', 'gotcha', 'Codebase Intelligence Daemon', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-23T23:36:43.840600', 1769229403, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c765fcae-fa49-40fb-9469-14ce39501155', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Added an explicit `state.set_indexing(True)` call immediately before launching the indexing thread, ensuring the status endpoint reflects the true state during indexing.', 'bug_fix', 'Codebase Intelligence Daemon', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-23T23:36:43.912064', 1769229403, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('034c846c-59ca-44b6-924f-0d2be77b301e', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Used a thread‑safe `State` object with a re‑entrant lock to guard shared attributes (`status`, `indexing`, `files`, `chunks`). This prevents race conditions between the indexing thread and HTTP request handlers.', 'decision', 'Codebase Intelligence Daemon', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-23T23:36:43.967375', 1769229403, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6d21f8b1-a620-4b04-a75a-e46b2226c102', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Persisted state only in memory rather than to disk; this keeps the daemon lightweight but means the state is lost on restart. The decision was made because the daemon is expected to run as a short‑lived service.', 'discovery', 'Codebase Intelligence Daemon', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-23T23:36:44.025447', 1769229404, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6d023c8d-3015-4208-a304-e4836c28a493', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'The server’s health endpoint was cached by the browser, so rapid status changes were not reflected in the UI. Disabled caching headers for the health route to ensure fresh data on each poll.', 'gotcha', 'Dashboard UI', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-23T23:36:44.083217', 1769229404, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('50c432db-6383-4340-abce-b431f4e40f38', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Used `asyncio.run` inside the indexing thread to execute the async indexing logic. This avoids having to run an event loop in the main thread but can block the thread if not managed carefully.', 'discovery', 'Codebase Intelligence Daemon', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-23T23:36:44.196723', 1769229404, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8df859a0-0dde-4fc6-970f-c22f14a1460d', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 5, 'Exceptions raised during indexing were not caught, causing the daemon to crash silently. Wrapped the indexing logic in a try/except block and set `state.status` to "error" on failure.', 'gotcha', 'Codebase Intelligence Daemon', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-23T23:36:44.253462', 1769229404, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('edbb87ce-5513-4c1c-84e5-b20a3a805ac8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'The watcher module uses the watchdog library’s Observer and a custom FileSystemEventHandler to monitor the project root for file create, modify, and delete events. It then updates a shared state object that the API exposes via a `/status` endpoint.', 'discovery', 'watcher.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:39:10.036584', 1769229550, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('487d3dd1-5c92-431f-8b38-38e2521e62d4', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'File system events are debounced: the watcher waits a short period (default ~0.5 s) after the last event before marking the system as ready to index. This prevents a burst of rapid edits from triggering multiple indexing jobs.', 'gotcha', 'watcher.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:39:10.103943', 1769229550, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('de5d7b19-c3ee-4774-aaed-f0b8627458e3', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'The pending_changes counter is incremented on every event but only decremented after the indexing worker finishes. If indexing fails or is interrupted, the counter can become stale, leading the dashboard to display a non‑zero pending count indefinitely.', 'gotcha', 'watcher.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:39:10.181875', 1769229550, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6be540a3-13a3-44af-953d-c7a1bf4e9ef8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'Indexing is performed in a separate thread rather than an async task to avoid blocking the watchdog event loop. This simplifies concurrency but introduces a small context‑switch overhead and requires careful locking around shared state.', 'discovery', 'watcher.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:39:10.254509', 1769229550, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('16a1cfe0-f619-4ef4-838c-a02d05e41fbf', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 6, 'The dashboard does not use WebSocket or Server‑Sent Events for real‑time updates; instead it polls the `/status` endpoint every few seconds. This keeps the UI simple but can introduce a lag of up to the polling interval.', 'discovery', 'watcher.py', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-23T23:39:10.327113', 1769229550, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8efc13ce-cc8e-4dff-b725-3ec67971d373', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The current MemoriesList.tsx component fetches all memories in a single API call and renders them all at once. There is no client‑side pagination or lazy loading, which will cause UI jank as the number of memories grows.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/data/MemoriesList.tsx', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:19.414860', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ab9c0d46-c6bf-4155-a88d-0bae8a10f30d', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The SQLite store defined in activity/store.py uses a single table with columns for id, memory_type, content, created_at, and a JSON blob for tags. No indexes are created on any of these columns, so queries that filter by memory_type, tags, or date range will perform a full table scan.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:19.480763', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b1422e41-13ee-4c7d-9a74-ccd51815d5fe', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'SQLite connections are not thread‑safe by default. The current implementation opens a new connection per request but does not enforce a connection pool or pragma settings (e.g., journal_mode=WAL). Without WAL, concurrent reads/writes can block each other, leading to latency spikes when the UI triggers frequent fetches.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:19.605256', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('bdcb0ebc-a1d5-4183-bcad-98f4b8066671', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The search route in daemon/routes/search.py performs a simple LIKE query on the content column. This is inefficient for large datasets and does not support full‑text search or relevance ranking. SQLite’s FTS5 virtual table could be leveraged to provide faster, more accurate semantic search.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/routes/search.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:19.731288', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('423d9aab-bec8-4d26-aea6-5c425424cb3d', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The project opts for SQLite for persistence, which simplifies deployment and is sufficient for a single‑user or low‑traffic scenario. However, this choice limits scalability and concurrent write performance compared to a server‑based database like PostgreSQL. The current design trades off scalability for simplicity and zero‑config deployment.', 'discovery', 'Overall architecture', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:19.853394', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b70d0ef4-9f2a-437e-aca7-15fc17ec1f11', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'FastAPI’s dependency injection is used to provide a shared MemoryStore instance to route handlers. This centralizes data access but also means that any change to the store implementation (e.g., adding indexes) must be reflected in the dependency provider.', 'decision', 'src/open_agent_kit/features/codebase_intelligence/daemon/routes/__init__.py', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-23T23:47:19.978311', 1769230039, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('a247c98f-523b-41c1-adbc-94a92e3493fa', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The SQLite store defines a single `memories` table with columns: `id`, `memory_type`, `content`, `tags` (stored as a JSON string), and `created_at`.', 'discovery', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:31.305214', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c08c5580-0084-4406-95e0-12136f933189', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The `tags` column is a JSON string and is not normalized or indexed, meaning any tag‑based filtering requires a full table scan.', 'gotcha', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:31.370775', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9f426cc3-27f1-4110-91da-2320912de908', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The `memory_type` column is also not indexed, so queries that filter by type (e.g., discovery vs. reminder) will become slow as the table grows.', 'gotcha', '/Users/chris/Repos/open-agent- kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:31.443345', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('1e5b8399-6c85-4f13-826b-0cb0a00d57f4', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, '`MemoriesList.tsx` fetches all memories on component mount and renders them in a plain list without pagination or virtualization, which can lead to UI lag when the number of memories is large.', 'discovery', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/data/MemoriesList.tsx', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:31.516715', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b00b386e-d276-4266-ac23-f448c6fdf6bc', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The API route `/search/list` (defined in `search.py`) returns the entire `memories` table without any limit/offset or cursor support, producing potentially huge payloads.', 'gotcha', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/search.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:31.589609', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('275c4e0c-a88f-46d5-bbf2-1e331aab216f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'SQLite was chosen for persistence because of its zero‑dependency, file‑based nature, which simplifies deployment for single‑user scenarios but may not scale to multi‑user or high‑write workloads.', 'discovery', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:31.650493', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('7977bc18-df72-428f-81ea-39f4219ce8fc', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The vector store stores embeddings as BLOBs in SQLite and performs semantic similarity search in memory; this keeps the implementation simple but limits scalability and query speed for large embedding sets.', 'discovery', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:31.721221', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('5e98ffa6-3815-48bc-85f1-4f2e93d3cbd0', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The search API supports semantic search via the vector store but does not expose any filtering by `tags`, `memory_type`, or date ranges, limiting the ability to narrow results in the UI.', 'discovery', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/routes/search.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:31.792980', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c1148926-e45f-4cb6-a29b-45216cfbf89e', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'The UI does not use a virtualized list or infinite scroll; all items are rendered at once, which is acceptable for small data sets but will degrade performance as the memory count grows.', 'decision', '/Users/chris/Repos/open-agent-kit/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/data/MemoriesList.tsx', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-23T23:47:31.867458', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('70d0eac8-2db9-425a-bc25-dca6a8dfef48', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'Proposed improvement: create a separate `tags` table with a many‑to‑many relationship to `memories` and add indexes on `tag_name`, `memory_id`, and `memory_type` to accelerate filtering.', 'discovery', 'store.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:31.939579', 1769230051, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('63a8dfdb-2528-495c-acee-61532b46e71d', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'Proposed improvement: add pagination (limit/offset or cursor) to the `/search/list` endpoint and implement corresponding pagination controls in `MemoriesList.tsx` to avoid large payloads and UI freezes.', 'discovery', 'search.py & MemoriesList.tsx', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-23T23:47:32.010815', 1769230052, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8372be2a-38b9-4651-9c95-4eede26f0e77', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 7, 'Proposed improvement: extend the UI with filter controls for tags, memory type, and date range, and expose these as query parameters to the API to provide a richer, more manageable memory browsing experience.', 'discovery', 'MemoriesList.tsx', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-23T23:47:32.084844', 1769230052, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('377b8e93-1b74-48f9-9ac3-bd44b5a8505f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'SQLite was chosen as the persistence engine for the activity store to keep the deployment lightweight and avoid external database dependencies, making it ideal for a single‑user or local development environment.', 'decision', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.349258', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('a13e73c9-b5d1-4cd0-9570-8d55c9d5b9ee', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Schema migrations are handled automatically on store initialization by comparing the in‑code schema version with the version stored in the database and applying incremental SQL scripts. This ensures new and upgraded instances are brought up to date without manual intervention.', 'decision', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.411980', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6e3b5672-dcbe-4e88-9406-01646d55fa62', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Using SQLite limits concurrent write performance and scalability compared to a server‑based database like PostgreSQL, but the simplicity and zero‑configuration nature of SQLite outweigh these concerns for the current use case.', 'discovery', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:47.469957', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('460c3b3b-67a6-4b29-8209-569250c80b19', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'The FTS5 virtual table used for full‑text search requires the SQLite FTS5 extension to be compiled in; on systems where it is missing the table creation will fail, so the code must guard against this and provide a fallback or error message.', 'gotcha', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.526656', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('7001bf9c-c9e3-4516-b009-c082bfea03bb', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Index creation statements can fail if the index already exists; the migration logic must check for existence or use "IF NOT EXISTS" syntax to avoid errors during repeated migrations.', 'gotcha', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:47.597467', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('fb2d710d-9947-4c21-b978-2c509391c15d', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Composite indexes were added for the most common query patterns (e.g., filtering by memory type, session, and embedded status) to significantly speed up read queries.', 'decision', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.653881', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('08b55ee2-1279-4e72-9db6-b8298941e28f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Adding many indexes improves read performance but increases write overhead and storage size; the decision was to add only the indexes that provide the biggest performance benefit for the expected query load.', 'discovery', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:47.711351', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6f32b082-a68d-42ff-8bf6-d6d02bab6fda', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Migration scripts must be idempotent; applying the same change twice can cause errors. The implementation includes checks to skip already applied steps and logs the migration progress.', 'gotcha', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.769151', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('4bd581be-b2ad-43d9-9a56-aab9096b7eae', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'A dedicated schema_version column in the activity store database is used to track the current schema version, simplifying migration logic and avoiding the need for a separate migration table.', 'decision', 'Activity Store', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-23T23:54:47.839010', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('565a88d4-5f58-4b68-bff1-e676246823f0', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'Manual migration scripts were chosen over an automated migration framework to keep the codebase lightweight and to allow fine‑grained control over the SQL executed during each version bump.', 'discovery', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:47.896161', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2000df9f-4e7d-4eb8-916b-60e3b75a60b8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'After a migration, the daemon must be restarted to load the new schema; the code triggers a graceful restart and logs the action to avoid stale connections.', 'gotcha', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:47.953246', 1769230487, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('3c870c12-06b9-47cb-9528-ef4488603b8c', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 8, 'The activity store is isolated in its own module to keep codebase intelligence concerns separate from other application features, facilitating independent evolution and testing.', 'decision', 'Activity Store', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-23T23:54:48.010326', 1769230488, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('f8d465c3-3b5d-456b-bea6-057bbbfce5c8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Implemented a date‑range filter for the memories API and UI to allow users to query memories created within a specific period. The filter is added as optional query parameters (`start_date` and `end_date`) on the FastAPI route, passed through the store and retrieval engine, and exposed via the React hook and component.', 'decision', 'Codebase Intelligence – Memory filtering', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T00:07:10.391636', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9d8b5ebb-9f9c-48f0-9011-c5820e77eb54', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Chose to keep the date‑range logic in the SQLite store rather than delegating it to the application layer to reduce data transfer and leverage SQL’s date comparison capabilities. This trades off a small increase in query complexity for lower memory usage and faster response times.', 'discovery', 'Codebase Intelligence – Memory storage', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:07:10.455177', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('7a22fcb6-2be9-42c0-81b1-b0310d52ba14', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Added a new FTS5 virtual table for memory search to improve full‑text search performance across large memory datasets. The virtual table mirrors the main memory table and is updated via triggers, ensuring consistency without manual sync.', 'decision', 'Codebase Intelligence – Retrieval engine', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T00:07:10.527907', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('442e6cd9-3854-4fe2-8a9f-a472d3bfc916', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Opted for SQLite’s FTS5 instead of an external search engine (e.g., ElasticSearch) to keep the deployment lightweight and avoid external dependencies. The trade‑off is limited scalability for very large memory sets, but sufficient for the expected single‑user or small‑team use cases.', 'discovery', 'Codebase Intelligence – Retrieval engine', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:07:10.592627', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6f54043c-87cd-43a7-be08-421a724e6ffd', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Date parsing in the API must handle ISO‑8601 strings and default to UTC if no timezone is provided. Failure to normalize dates can lead to off‑by‑one errors in filtering results.', 'gotcha', 'Codebase Intelligence – API route', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:07:10.655979', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('363ea0c2-6264-4609-b927-675fac2c6131', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'The UI date picker component must enforce that the start date is not after the end date; otherwise the API receives an invalid range and returns an empty result set. Validation is performed client‑side and the hook falls back to the last successful range if validation fails.', 'gotcha', 'Codebase Intelligence – UI hook', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:07:10.728351', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('3ceab853-c0f7-4a2e-94a7-f4fb63c8cd96', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Introduced a constants file (`constants.ts`) to centralize date format strings and default date range values, ensuring consistency across the hook, component, and API documentation.', 'decision', 'Codebase Intelligence – UI constants', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T00:07:10.785000', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('eb888ff9-f10e-43b5-8027-6f561875ef43', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Used React’s `useEffect` to trigger data fetching on date range changes, which simplifies state management but can cause unnecessary network requests if the user rapidly changes dates. Debouncing could be added later for performance tuning.', 'discovery', 'Codebase Intelligence – UI hook', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T00:07:10.840887', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('aa1ea0d8-d612-47e4-830c-0dfa1f6ef561', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'When no memories exist for a given date range, the UI must gracefully display an empty state rather than a loading spinner. The component now checks for an empty array and renders a message accordingly.', 'gotcha', 'Codebase Intelligence – MemoriesList component', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T00:07:10.896760', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('f7d13116-20dc-44a7-93db-161210e60a43', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 9, 'Updated the `list_memories` method in both the store and retrieval engine to accept optional `start_date` and `end_date` parameters, defaulting to `None` to preserve backward compatibility with existing callers.', 'decision', 'Codebase Intelligence – Store & Retrieval', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:07:10.954928', 1769231230, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0935a0f0-c202-4f76-8d0e-5df61f48340e', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'The UI build script in package.json runs `tsc -b && vite build`, which compiles TypeScript and bundles the UI with Vite, outputting the final assets to a `dist/` folder.', 'discovery', 'package.json build script', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:20:35.268345', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('e1b28bfa-976d-402c-b260-ff8fbca14274', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'Running `oak ci restart` only restarts the CI environment; it does not automatically redeploy the newly built UI assets. The server may still be pointing to the old static files or a stale cache.', 'gotcha', 'CI restart command', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:20:35.327079', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('15246473-a67e-44e8-b270-3fb6ff2c9cd9', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'Even after a successful build, the browser may still serve cached assets, hiding the new changes. A hard reload or clearing the browser cache is often required to see updates.', 'gotcha', 'Browser caching', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:20:35.381152', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('1312eb12-cd56-47bd-9596-80009dc5fd80', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'The project separates the UI and daemon into distinct modules. The UI is built independently and its output must be copied or served by the daemon’s static file handler.', 'discovery', 'Project structure', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:20:35.437739', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('26b9bf5e-4f6a-4351-84c1-2398ad04d3ba', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'The team chose Vite for its fast dev server and HMR, accepting the trade‑off that a separate production build step is needed for deployment.', 'decision', 'Build tooling choice', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T00:20:35.491794', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b6680ee3-33c5-4f8d-8e66-a9c19c937ca5', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 10, 'Using Vite speeds up development but requires manual deployment of the `dist/` folder; an alternative would be to bundle UI assets directly into the daemon binary, simplifying deployment but slowing dev feedback.', 'discovery', 'Build process trade‑off', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T00:20:35.547541', 1769232035, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('de67c702-4e01-4f9c-bb5c-6077ebfb9e41', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 12, 'The Makefile defines a separate `venv` target that creates a virtual environment, but the `setup` target only runs `pip install -e .` without ensuring the venv is activated. If a developer runs `make setup` without first running `make venv`, the packages are installed globally, which can lead to permission errors or conflicts with system packages. This is a non‑obvious dependency that can trip up newcomers.', 'gotcha', 'Makefile', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:23:43.125176', 1769232223, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('bf618576-a4a7-4556-a4e7-f11e9191a3d2', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 12, 'There is a `tool-reinstall` target that removes all installed tools (via `pip uninstall -y -r requirements.txt`) and then reinstalls them. This target is useful for resetting the development environment, but it also deletes any locally built wheels or editable installs, so it should be used with caution.', 'discovery', 'Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:23:43.197897', 1769232223, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('aea810b3-ed5c-409f-a2e8-fe93d04dd9e1', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 13, 'The Makefile has been trimmed to include only local development targets, removing all commands that are meant for end‑user installation or deployment. This aligns the build tool with the intended audience—developers working on the project—while preventing confusion for users who should install via `uv install git+url`.', 'decision', 'Makefile local development', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T00:26:17.512937', 1769232377, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('5ebc1285-2c36-4590-acbf-9453472d5136', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 13, 'By eliminating non‑dev targets, we reduce the learning curve and potential for misuse, but we also lose the convenience of quick one‑liner setup for contributors who might otherwise rely on `make setup` or similar. Contributors will need to manually run the equivalent shell commands or use the new `uv` installation approach.', 'discovery', 'Makefile local development', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T00:26:17.574622', 1769232377, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('14f8fdbc-00e3-48f5-b789-9c276075d486', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 13, 'Removing targets can inadvertently break CI pipelines or automated scripts that expect those commands to exist. It is essential to update any external documentation or CI configurations that referenced the removed targets to avoid build failures.', 'gotcha', 'Makefile local development', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T00:26:17.636147', 1769232377, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ed59827b-af3f-4683-8e34-2245ced0a867', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 15, 'The `oak` CLI is not found because the virtual environment is not activated; after running `make install` the executable is installed into the virtual environment’s `bin` directory, which is not on the system PATH unless the environment is activated or the bin directory is added to PATH.', 'gotcha', 'bash shell, virtual environment', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:28:10.303968', 1769232490, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('1bca33f1-7504-42b8-9c9f-051b8e185f21', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 15, 'The Makefile contains only an `install` target that performs an editable pip install (`pip install -e .`). There is no target for running or restarting the application; the user must invoke the `oak` command manually after installation.', 'discovery', 'Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:28:10.373534', 1769232490, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('3b546f84-bd22-4fc8-ba1b-541e83d95b77', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 15, 'The `oak` package provides a CLI entry point defined in its `setup.cfg`/`pyproject.toml`. To use it, one must activate the virtual environment (e.g., `source .venv/bin/activate`) or use a tool like `pipx` to run the command without manual PATH manipulation.', 'discovery', 'Python package entry point', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:28:10.443293', 1769232490, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6f073694-d44a-4036-a739-ff255361834c', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 17, 'The bash check for the oak binary reports a path in the .venv/bin directory but the script does not proceed further – likely due to missing execution permissions or an incorrect shebang line, causing the binary to be non‑executable in the current environment.', 'gotcha', 'Bash check for oak binary', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:30:20.980992', 1769232620, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b442f2c4-1e70-4c76-9107-45652b352fd8', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 17, 'The oak binary is bundled within the project''s virtual environment under .venv/bin, suggesting that the project relies on a local Python environment for its tooling rather than a system‑wide installation.', 'discovery', 'Project structure', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T00:30:21.045652', 1769232621, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8d1bbe1b-d25a-4783-ba07-c36a1c3783ce', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 18, 'The open-agent-kit CLI prints a version string that includes the semantic version, a development suffix, a commit hash, and a date stamp (e.g., 0.5.2.dev9+gaa8f6093c.d20260124).', 'discovery', 'CLI version command', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:32:06.449272', 1769232726, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('48bfec6f-90ab-4fab-823e-6376daad35a1', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 20, 'The ''oak'' executable in the user''s local bin is a symlink to the virtual environment''s oak binary located at /Users/chris/Repos/open-agent-kit/.venv/bin/oak.', 'discovery', '/Users/chris/.local/bin/oak', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T00:33:37.252291', 1769232817, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6214909b-187a-4dd2-a979-43127b80262f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', 20, 'The project version is a dev build (0.5.2.dev9+gaa8f6093c.d20260124), indicating it includes a Git commit hash and a date stamp.', 'discovery', 'Project version output', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T00:33:37.317154', 1769232817, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0475f6bb-33cd-497e-aba1-68e66f0f6ea5', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Implemented pagination for memory listing to prevent loading all memories into memory at once, improving performance and reducing API payload size.', 'decision', 'memory/store.py, retrieval/engine.py, search.py, use-memories.ts, MemoriesList.tsx', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T01:35:11.087771', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('5450a2b3-d6cc-4961-8cbe-a9cacedd8178', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Chose SQLite with FTS5 for full-text search instead of a dedicated search engine or external database to keep deployment lightweight and avoid additional dependencies.', 'discovery', 'memory/store.py, search.py', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T01:35:11.245399', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('30857cd6-56d3-43ae-953a-14bda294f590', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Added a set of memory type constants in constants.ts to replace magic strings, enabling type safety and easier refactoring across the codebase.', 'decision', 'constants.ts, use-memories.ts, search.py', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T01:35:11.338251', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('d36fcaf8-9748-4d08-b9e8-3be505383256', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'SQL query construction in list_memories uses string interpolation for WHERE clauses; if any user-provided value is not properly sanitized, it could lead to SQL injection vulnerabilities.', 'gotcha', 'memory/store.py', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T01:35:11.427567', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ecbb2e21-5e03-457d-8d0c-96551ab38bb9', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Introduced date range filtering (start_date and end_date) to allow users to narrow memory results by creation time, improving search relevance.', 'decision', 'memory/store.py, search.py, MemoriesList.tsx', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T01:35:11.514849', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ef527ab6-c5be-4bac-885a-480fb76cb452', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Defaulted sorting to descending by created_at to show the newest memories first; while this is intuitive for most use cases, it may not be optimal for very large datasets where a different sort order could reduce query cost.', 'discovery', 'memory/store.py', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T01:35:11.606602', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8c7d3b15-6ec1-4c37-80d4-eb72083b07f2', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Defined a DEFAULT_PAGE_SIZE constant to standardize pagination limits across the API and UI, simplifying configuration and reducing hard‑coded values.', 'decision', 'constants.ts, search.py, use-memories.ts', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T01:35:11.705621', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('74b12395-1392-48f8-a7d9-be52ac0e3981', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'The FastAPI route in search.py relies on dependency injection for the database connection; if the dependency is misconfigured, the endpoint will raise a 500 error instead of a graceful failure.', 'gotcha', 'search.py', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T01:35:11.794729', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9e9f0259-c633-4499-9dd1-104435d7c66f', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Created a custom React hook (use-memories) to encapsulate API fetching, pagination state, and error handling, promoting reuse across components.', 'decision', 'use-memories.ts', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T01:35:11.881604', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('eab08e97-4337-4115-bbd5-7c1c5e91781c', '6ae18596-2b31-4f20-8e4f-7a9541ef7dcb', NULL, 'Implemented manual table pagination controls in MemoriesList.tsx rather than infinite scrolling; this simplifies the UI but may lead to higher load times for very long lists.', 'discovery', 'MemoriesList.tsx', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T01:35:11.966575', 1769236511, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('16bfcb84-a8ab-41ae-b67b-8e82fc6c12d4', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'Added MCP feature dependencies to pyproject.toml to auto‑install when the Codebase Intelligence feature is enabled, simplifying onboarding for developers using oak ci.', 'decision', 'Codebase Intelligence MCP feature', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T09:41:51.974702', 1769265711, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('949f44f7-5db0-4350-a61c-1e4d20ca28a2', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'Auto‑installing MCP dependencies increases build time and may introduce version conflicts, but was chosen for developer convenience and to avoid manual pip installs.', 'discovery', 'Codebase Intelligence MCP feature', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.048700', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0ee0a7b6-1b89-478e-9178-f580f58fc3e7', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'MCP server process exits early because the expected virtual environment pip binary is missing: "/Users/chris/Repos/open-agent-kit/.venv/bin/pip" not found. The server cannot install or run dependencies without a valid venv.', 'gotcha', 'MCP server startup', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T09:41:52.125377', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('e5d8d3a7-57fa-456f-909b-efe8f70a1662', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'The pip script used by the server references a Python interpreter that no longer exists: "/opt/homebrew/opt/python@3.11/bin/python3.11". This bad interpreter path causes pip to fail before the server starts.', 'gotcha', 'MCP server startup', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T09:41:52.202316', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('eb8ef82b-e180-42df-b486-dc3ef2d2f4e9', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'MCP server relies on Node.js plugins (e.g., @upstash/context7-mcp) accessed via npx. If Node or npm is missing or misconfigured, the server will fail to connect to the context plugin, leading to a failed health check.', 'gotcha', 'MCP server startup', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.280757', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('864ab98a-b8bb-4c00-a288-6c7c305842a3', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'The server health check expects a JSON RPC endpoint to be reachable. If the server process crashes before binding to the port (e.g., due to missing dependencies), the health check reports "MCP server not running - checking for output".', 'gotcha', 'MCP server health check', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.360085', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('387664d9-4c23-4c6a-9775-50d0c082b809', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'The MCP server is designed to run as a separate process, providing isolation from the main oak ci process and allowing independent scaling and monitoring.', 'decision', 'MCP server architecture', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.435755', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0eadb3e7-3772-4f0b-85aa-d3ec7c48cd14', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'Configuration for the MCP server is read from ".claude/settings.json" and ".claude/settings.local.json". If these files are missing or contain incorrect values (e.g., wrong project_root), the server may start with invalid settings and exit.', 'gotcha', 'MCP configuration', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.504274', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('bddf37e7-b132-44b6-835b-bade1096d82f', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'Using a separate MCP server process allows for easier debugging and health monitoring, but adds complexity in ensuring the correct environment (Python, Node, dependencies) is available at runtime.', 'discovery', 'MCP server deployment', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T09:41:52.571167', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('37c81ca5-93f1-474a-9e73-6b80c92d39e3', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 22, 'The MCP server logs show it starts on port 38283, but the exit message "MCP server exited early" indicates a crash before the server fully initializes. This could be due to missing compiled libraries (e.g., cffi, cryptography) that fail to import in the current environment.', 'gotcha', 'MCP server startup', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T09:41:52.645750', 1769265712, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('cb43f170-9245-40aa-8307-549257e91f68', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 23, 'Feature definitions are stored in YAML manifests (e.g., /src/open_agent_kit/features/codebase_intelligence/manifest.yaml). Each manifest lists a feature name, description, and a "dependencies" section that can reference other features or external packages.', 'discovery', 'Feature manifest files', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:43:10.771549', 1769265790, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2eba40d4-bf20-4670-928b-fea56afbc78c', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 23, 'The FeatureService loads all manifests into a registry and resolves dependencies recursively before installation. It checks for already-installed packages by attempting to import them, which means missing imports will trigger a pip install.', 'discovery', 'src/open_agent_kit/services/feature_service.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:43:10.841589', 1769265790, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('53ad85b1-2c3e-4556-bf64-502766758ad6', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 23, 'Feature names use hyphens (e.g., "codebase-intelligence"), but the internal code refers to them with underscores or camelCase. This mismatch can cause lookup failures if the name is not normalized correctly.', 'gotcha', 'FeatureService name handling', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:43:10.913596', 1769265790, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('908df6d0-78ef-41c9-a951-648eb0e42a14', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 23, 'The constants module defines a global FEATURE_FLAGS dictionary that maps feature names to a "default_enabled" flag. This flag determines whether a feature is automatically enabled when the package is first installed.', 'discovery', 'src/open_agent_kit/constants.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:43:10.982691', 1769265790, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('7d2c42b4-ae51-4187-b8b6-34414588b20e', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 23, 'Installing a feature that has external package dependencies triggers a subprocess call to pip. If the environment lacks a virtual environment or pip is not in PATH, the installation silently fails and the feature remains marked as installed, leading to runtime errors later.', 'gotcha', 'FeatureService pip installation', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:43:11.058988', 1769265791, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('fe334d74-98b7-4410-b412-225087c67626', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The Makefile defines a `setup` target that installs project dependencies by invoking `uv pip install -r requirements.txt` followed by `uv sync` to generate and use a lock file. This centralizes dependency resolution and ensures reproducible environments.', 'discovery', 'Makefile', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:44:10.425881', 1769265850, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('4690556f-0ebb-447f-bb06-784fd22d88a3', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The Makefile assumes that the `uv` tool is already installed on the system. If `uv` is missing, any `make` command that relies on it will fail, so developers must install `uv` separately before using the Makefile.', 'gotcha', 'Makefile', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:44:10.504172', 1769265850, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2fb66d54-04f9-444d-a6f6-ee25a8fcfd44', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The project opts to use `uv` instead of the standard `pip` for installing and syncing dependencies, likely for its faster resolution and built‑in lock file support. This choice simplifies the Makefile and speeds up setup.', 'decision', 'Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:44:10.628442', 1769265850, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0121776a-1664-4307-aff4-4076a0dce935', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'Other Makefile targets such as `test` or `run` delegate to `uv run` to execute scripts or tests, keeping the command invocation consistent and avoiding direct calls to `python -m` or `pytest`.', 'discovery', 'Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:44:10.753497', 1769265850, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('e8701d6f-68e1-4850-9521-7073b5f0bd0b', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The Makefile centralizes all development tooling, so developers never invoke uv or pip directly; instead, commands like `make setup`, `make dev`, or `make test` internally call uv to create a virtual environment and install dependencies.', 'discovery', '/Users/chris/Repos/open-agent-kit/Makefile', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:44:16.950634', 1769265856, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9c5b3e14-69d8-4ec2-b47a-4009dc018cec', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'If uv is not installed globally, the Makefile may fail during the `make setup` step with a cryptic error because it assumes uv is available; the Makefile does not provide a fallback to pip or a clear installation message.', 'gotcha', '/Users/chris/Repos/open-agent-kit/Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:44:17.020260', 1769265857, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('dd740bda-1eb7-442e-9fb7-ff15839d51d4', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The Makefile defines a `.venv` directory (or similar) for the virtual environment and uses `uv sync` or `uv pip install -r requirements.txt` to populate it, ensuring that every developer uses the same dependency set.', 'discovery', '/Users/chris/Repos/open-agent-kit/Makefile', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:44:17.103856', 1769265857, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2a73b888-7bdd-4075-8e24-080bdba98faa', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'Relying on the Makefile for all tooling reduces friction for developers but couples the project to Unix-like shell environments; Windows users may need to use WSL or adjust the Makefile for PowerShell compatibility.', 'discovery', '/Users/chris/Repos/open-agent-kit/Makefile', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:44:17.195879', 1769265857, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6cf0a541-f842-4437-92ac-28563af5d5f6', '2f667b6d-2eef-4a44-b622-eef08f97a6cc', 24, 'The Makefile may use shell-specific syntax (e.g., `$(shell ...)` or backticks) that behaves differently across shells, potentially causing subtle bugs when running `make` on different platforms or CI environments.', 'gotcha', '/Users/chris/Repos/open-agent-kit/Makefile', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T09:44:17.260455', 1769265857, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ab355889-989b-4464-a53e-17107332e7ba', '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 25, 'The PostToolUse hook system only triggers for tools that are registered in the tool registry and that emit a result via the standard tool‑execution path. The built‑in "Edit" tool is not part of that registry; it calls ActivityStore.record_edit() directly, bypassing the hook mechanism. Consequently, file edits are logged in the SQLite activity table but never reach the PostToolUse hooks.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/daemon/routes/hooks.py & activity/store.py', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T09:53:45.909609', 1769266425, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('a23ba91a-28ab-4ce9-8297-d5c2e1b27d39', '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 25, 'ActivityStore.record_edit() is invoked directly by the Edit tool implementation, which explains why edits appear in the activity database but not in the hook logs. The hook system is designed for external tool integrations (e.g., Bash, Search) rather than internal state‑changing actions like file edits.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/activity/store.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T09:53:46.076100', 1769266426, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('93f3de4b-f94b-4a45-bbb5-1ae11a30c6df', '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 26, 'Plan: Plan: Add Missing Claude Code Hooks for CI Activity Capture

# Plan: Add Missing Claude Code Hooks for CI Activity Capture

## Summary

Add three valuable hook events that are currently not captured:
1. **PostToolUseFailure** - Capture tool execution failures (errors are learning opportunities)
2. **SubagentStart** - Track when Task agents (Explore, Plan, Bash, etc.) spawn
3. **SubagentStop** - Capture subagent completion with transcript paths

**Note:** These hooks are Claude-specific. Cursor doesn''t have equivalent events.

## Current State

**Hooks Con...', 'decision', '/Users/chris/.claude/plans/ancient-churning-flurry.md', 'auto-extracted,plan,agent:claude,importance:high', 8, NULL, '2026-01-24T10:03:21.450090', 1769267001, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('22c8a2af-8394-42e4-be56-5d3349f4d293', '85c00c56-5acf-4ff4-90f9-cd4b7b616a73', 26, 'Plan: Plan: Add Missing Hooks and Copilot Support for CI Activity Capture

# Plan: Add Missing Hooks and Copilot Support for CI Activity Capture

## Summary

**Phase 1: Add new hook events** (PostToolUseFailure, SubagentStart, SubagentStop)
**Phase 2: Add full Copilot support** (new agent, full hook configuration)
**Phase 3: UI enhancements** (better failure visualization, subagent grouping)

## Agent Hook Support Matrix

| Event | Claude | Cursor | Gemini | Copilot |
|-------|--------|--------|--------|---------|
| SessionStart | ✓ | ✓ | ✓ | ✓ (NEW) |
| UserPromptSubm...', 'decision', '/Users/chris/.claude/plans/ancient-churning-flurry.md', 'auto-extracted,plan,agent:claude,importance:high', 8, NULL, '2026-01-24T10:26:47.689754', 1769268407, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('be43537d-be77-411a-beaa-8dbf72ed3576', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'The Config page disables the Save button until the Test & Detect operation succeeds, enforcing that all required fields (dimensions, chunk size, context window for embeddings; context for summarization) are populated automatically. This design prioritizes configuration correctness over user flexibility.', 'decision', 'Config.tsx / config.py', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T16:24:34.760009', 1769289874, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('813776ec-851e-42f4-9e2e-ffa2e5233f8a', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'Strict validation (disabling Save until Test & Detect) trades off user convenience for reduced risk of misconfiguration. The current implementation discourages manual entry of critical parameters, potentially frustrating users who need to override defaults.', 'discovery', 'Config.tsx', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:34.901755', 1769289874, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('cdb5c292-1f60-4b61-b054-87caf455a3e0', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'Test & Detect relies on the _discover helper in config.py to fetch model metadata. LM Studio models may not expose the expected metadata fields, causing the endpoint to return incomplete data and leaving UI fields empty.', 'gotcha', 'config.py / _discover function', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T16:24:35.037067', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b736325f-4e80-409b-8099-599b4a8f5a40', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'In Config.tsx, the fields for dimensions, chunk size, and context window are rendered read‑only until Test & Detect succeeds. This prevents manual editing of those values, even if the user has already entered valid numbers.', 'gotcha', 'Config.tsx', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:35.160835', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('fefd5b67-f5c4-485c-a52e-aa21720f85c9', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'The Test & Detect endpoint may be called with an incorrect model identifier for LM Studio models, due to a mismatch between the UI’s model name and the name expected by the _discover function. This causes the endpoint to return 200 with empty payloads.', 'bug_fix', 'config.py / test_detect route', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T16:24:35.297699', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('909911f1-aa6c-433d-a9ae-7cb54d5a31db', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'A single Test & Detect API route is used for both embedding and summarization models, with logic branching on the model type. This simplifies routing but can lead to missing fields if the branching logic does not handle all model families.', 'decision', 'config.py', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:35.432686', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9256ff2e-f974-4435-9e5a-b20cd55110fe', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'The UI’s state management uses a flag (e.g., `testDetectSuccess`) to enable the Save button. If this flag is never set due to a silent API failure, the button remains disabled even when the user has manually entered all required values.', 'gotcha', 'Config.tsx', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:35.557071', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c079ca57-4707-4cf8-a840-a2ed8af0c566', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'Auto‑population of fields from model metadata reduces manual entry errors but sacrifices the ability to override values. The current design leans heavily on auto‑population, which may not be suitable for all deployment scenarios.', 'discovery', 'config.py / _discover + Config.tsx', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:35.689956', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8c95d43d-7cc8-44e8-bb66-684b35654d9f', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'Error handling for Test & Detect is minimal; the UI does not display detailed error messages when the endpoint fails, making it hard for users to diagnose why the fields are not populated.', 'gotcha', 'Config.tsx / test_detect handler', 'auto-extracted,importance:low,session:implementation', 3, NULL, '2026-01-24T16:24:35.821561', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ae3bc7e3-7920-432f-857b-48cae4755bf4', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 28, 'FastAPI’s Depends is used to inject shared state into the Test & Detect route, ensuring consistent access to configuration data across the daemon. This choice simplifies dependency management but requires careful handling of shared mutable state.', 'decision', 'config.py', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:24:35.958411', 1769289875, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('e44fabc5-efa5-4fcc-898f-1f7542dcb6dd', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 29, 'The configuration objects in the project are defined as Pydantic BaseModel subclasses, which enforce that all declared fields must be present and correctly typed before an instance can be persisted. Attempting to save a config with missing or invalid fields triggers a validation error that prevents the write operation.', 'discovery', 'src/open_agent_kit/features/configuration/models.py (Pydantic BaseModel definitions)', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T16:26:39.660505', 1769289999, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2dc95630-d5f7-4221-a62f-85d4dcd7d70e', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 29, 'LMStudio’s local model server endpoint is known to be flaky; the client library occasionally receives connection timeouts or unexpected status codes. The codebase contains a retry wrapper around LMStudio calls, but the retry count is low (2 attempts) and the back‑off strategy is exponential with a hard cap of 5 seconds, which may still be insufficient for intermittent network hiccups. This unreliability is documented in the README but not enforced in the production code path.', 'gotcha', 'src/open_agent_kit/features/model_inference/lmstudio_client.py', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:26:39.722271', 1769289999, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('86845a0c-a99c-436c-ac63-83d5f29eed37', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'Implemented a unified configuration form that handles both embedding and summarization settings in a single React component to reduce duplication and simplify state management.', 'decision', 'Config page (Config.tsx) and config-components.tsx', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T16:33:17.511098', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('96714e3b-b5c6-4d94-89f4-7751630c578a', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'Chose to disable the Save button until all required fields are populated rather than allowing submission and displaying inline validation errors. This prioritizes a smoother UX but requires additional state tracking for form completeness.', 'discovery', 'Config form validation', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T16:33:17.571009', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('10c7711c-d281-47fb-a657-a6ac3e73d97e', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'The useConfig hook performs an asynchronous fetch on mount; if the fetch fails or returns incomplete data, the form fields default to empty strings, which can mislead users into thinking the values are unset. A fallback default was added to avoid this edge case.', 'gotcha', 'use-config hook', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T16:33:17.642866', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8d947485-6928-4e3d-a2e9-f409fc827753', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'Used React Hook Form (or a custom useForm hook) to manage form state and validation, enabling easy detection of missing values and automatic disabling of the Save button.', 'decision', 'Form implementation', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T16:33:17.708631', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('10227bde-1e0b-41cc-aa19-30e2be763dd1', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'Opted for client‑side validation only for the presence of values, deferring deeper semantic validation (e.g., valid API keys) to the backend upon submission. This keeps the UI responsive but may allow some invalid configurations to be sent.', 'discovery', 'Validation strategy', 'auto-extracted,importance:low,session:refactoring', 3, NULL, '2026-01-24T16:33:17.780008', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('214fdc7b-9f54-472b-bc6e-cdf5f7fb9d86', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 32, 'When the user attempts to save with incomplete fields, the UI previously allowed the request to be sent, resulting in a 400 error from the server. Adding a disabled state prevented this race condition.', 'gotcha', 'Save action', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T16:33:17.837461', 1769290397, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2c76040c-e838-4426-8cef-a3eacfa45e49', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 33, 'The Qwen embedding model’s context length is 40960 tokens, not 4096. Using the smaller 4096 value is a miscalculation and will truncate inputs that exceed 4096 tokens, leading to incomplete embeddings.', 'gotcha', 'Qwen embedding usage', 'auto-extracted,importance:high,session:implementation', 8, NULL, '2026-01-24T16:44:34.864028', 1769291074, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('f6741fe7-170f-4366-a517-e6b72d83f616', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 33, 'Choosing the full 40960‑token context allows longer documents to be embedded in a single pass, but it increases memory consumption and inference latency. The developer must balance the need for longer context against resource constraints.', 'discovery', 'Qwen embedding configuration', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:44:34.947219', 1769291074, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ad56a38f-3d9b-40ff-812a-f346fefa1b01', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 33, 'The implementation opts to use the Qwen model with its full 40960‑token context to support larger codebases in the codebase intelligence feature, accepting the higher resource usage as a necessary trade‑off for comprehensive embeddings.', 'decision', 'Codebase intelligence daemon UI', 'auto-extracted,importance:medium,session:implementation', 5, NULL, '2026-01-24T16:44:35.028541', 1769291075, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('f9f0ff4c-630f-4e6d-a239-38056dc70260', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The `use-config` hook fetches the configuration from the backend using a plain `fetch` call inside a `useEffect` with an empty dependency array. It does not handle HTTP errors, does not abort the request on component unmount, and does not provide any loading or error state to the consuming component.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/hooks/use-config.ts', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T16:55:58.063279', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c552d434-351b-4e1b-bd66-d5faa9b90b85', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The `Config` page renders a large form using uncontrolled inputs (e.g., `<input>` elements without `value`/`onChange` bindings). This can lead to stale state, inconsistent validation, and makes it difficult to reset or pre-fill the form from the fetched configuration.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Config.tsx', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T16:55:58.191911', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('fdf89737-cdf1-4234-a0a6-2bd3697a0a83', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'All configuration keys are defined as string constants in `constants.ts`, but they are not typed as a TypeScript enum or a discriminated union. This allows accidental typos in key names that will only surface at runtime.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/lib/constants.ts', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:55:58.313424', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('b7a07d70-e387-493e-b726-cbf2c64734fd', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The `use-config` hook returns a `setConfig` function that is recreated on every render because it is not wrapped in `useCallback`. Components that consume this hook will re-render unnecessarily when the hook is called, impacting performance for large forms.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/hooks/use-config.ts', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:55:58.416079', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('46c91e30-e70c-4734-8bf4-2db94126a27b', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The `config-components.tsx` file contains several UI components that are tightly coupled to the configuration schema. They are not generic enough to be reused elsewhere and lack proper TypeScript typings for their props, which can lead to runtime errors when the schema evolves.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/ui/config-components.tsx', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:55:58.508063', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('07761c7f-c6f6-4dd9-acf0-3de415857efe', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The custom `Button` component concatenates class names manually and accepts a `className` prop, but it does not expose a `variant` or `size` prop. This makes styling inconsistent across the application and forces developers to duplicate CSS logic in each usage.', 'gotcha', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/ui/button.tsx', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T16:55:58.581902', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('8fabd692-e4f5-435f-9185-d310f7fb4244', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The decision to use a plain `fetch` API instead of a library like Axios simplifies the bundle size but sacrifices built‑in features such as automatic JSON parsing, request cancellation, and interceptors for error handling.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/hooks/use-config.ts', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:55:58.654899', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('daa6fea3-326e-49f5-8db9-9410899577ae', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The `Config` page imports a large number of components and constants directly, resulting in a file size of over 44k characters. This monolithic structure makes the file hard to navigate and increases the risk of merge conflicts during future feature additions.', 'discovery', 'src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Config.tsx', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:55:58.727721', 1769291758, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('1711ad68-a7e6-448c-a9dd-78d44c85c4e4', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'Config.tsx builds a large configuration form using a single useState object to hold all field values. This leads to a single state update causing the entire form to re-render on every change, which can hurt performance for many fields.', 'discovery', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Config.tsx', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:56:16.542116', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('73691d2b-b628-40b0-bd6f-1dede91c7660', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'use-config.ts fetches configuration data via a raw fetch call but lacks error handling for network failures or non-200 responses. This can result in unhandled promise rejections and silent failures in the UI.', 'gotcha', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/hooks/use-config.ts', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T16:56:16.602550', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('d4cfec1f-5e81-4740-923d-7bef02bc3176', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'constants.ts mixes UI styling constants (e.g., colors, spacing) with feature configuration objects (e.g., CODEBASE_INTELLIGENCE config). This dual-purpose file can become a maintenance hotspot and makes it harder to locate UI constants versus feature flags.', 'discovery', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/lib/constants.ts', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:56:16.660741', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('d4de8f12-3fde-4c83-b59c-11dcc7acbf59', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'The UI components (e.g., ConfigComponents, Button) use inline styles and string literals for CSS rather than a CSS-in-JS solution or CSS modules. This quick approach simplifies styling but sacrifices scalability, theming, and potential CSS optimizations.', 'discovery', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/ui/*', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:56:16.719772', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('9ad601bf-f66e-42bc-9dbc-9f9eddf5b4bf', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'ConfigComponents.tsx introduces a generic ConfigField component that accepts a field type and renders the appropriate input element. This centralizes field rendering logic and reduces duplication across the form.', 'decision', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/ui/config-components.tsx', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:56:16.791737', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('2861c255-0924-4fd9-ba84-fb3609a82356', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'Dashboard.tsx imports and renders ConfigComponents without strict prop validation. If a required prop is omitted or mis-typed, the component may crash at runtime, indicating a need for PropTypes or TypeScript interfaces.', 'gotcha', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/pages/Dashboard.tsx', 'auto-extracted,importance:high,session:exploration', 8, NULL, '2026-01-24T16:56:16.858778', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('4224aa90-63be-4cab-89e7-78c606b4ace9', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'API endpoints are hardcoded in constants.ts without environment variable overrides, making it difficult to point the UI to different backends (e.g., staging vs production).', 'discovery', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/lib/constants.ts', 'auto-extracted,importance:medium,session:exploration', 5, NULL, '2026-01-24T16:56:16.922233', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('86d347cf-9f48-499e-a959-ea3ebebcf7ad', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 34, 'Button.tsx passes the onClick handler directly to the underlying <button> element but does not prevent default behavior for certain button types. In forms, this could inadvertently trigger form submission when the button is meant to perform an async action.', 'bug_fix', '/src/open_agent_kit/features/codebase_intelligence/daemon/ui/src/components/ui/button.tsx', 'auto-extracted,importance:low,session:exploration', 3, NULL, '2026-01-24T16:56:16.982333', 1769291776, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('09666213-5956-49a6-b5a7-ac48a1629e77', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Created a dedicated `config-components.tsx` file to encapsulate all UI components related to configuration sections. This modularizes the UI logic, makes the `Config.tsx` page cleaner, and allows reusability of components across the application.', 'decision', 'Config page UI', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:47.238490', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('d4c3e2ac-36af-477e-a163-cdd7994636be', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Decided to manage configuration state locally within the `Config.tsx` component using React state hooks instead of a global context or Redux store. This reduces boilerplate and keeps the component self‑contained, but it means that other parts of the app cannot react to config changes without additional prop drilling or event emitters.', 'discovery', 'Config state management', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T17:01:47.307396', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('f2e98c4a-7f46-4660-a2ee-8cefc0b42ca8', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'The `onChange` handlers for form inputs are typed as `(e: any) => void`. This bypasses TypeScript’s event typing and can lead to runtime errors if the event shape changes. A more robust approach would be to use `React.ChangeEvent<HTMLInputElement>` or a generic type for the specific input.', 'gotcha', 'Form input handling', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:47.433969', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('752991f0-3233-4246-a958-01e6401ce2b4', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Implemented a `restartDaemon` helper in the `use-config` hook that sends a restart request to the backend and waits for the daemon to come back online before updating the UI. This centralizes the restart logic and ensures the UI reflects the current daemon state.', 'decision', 'Daemon lifecycle management', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:47.557947', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('c7d7d6a6-8b0b-44f2-9161-dcb64957a55e', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Choosing to trigger a full daemon restart on any config change simplifies consistency guarantees but can be disruptive for long‑running processes. The trade‑off was accepted because the feature is primarily for development and debugging, where downtime is acceptable.', 'discovery', 'Config change handling', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T17:01:47.680106', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('0c963de9-1e2e-4e9d-a67b-ee29a20e960b', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Relative import paths such as `../../hooks/use-config` rely on the current file structure. If the folder hierarchy changes, these imports will break. Using TypeScript path aliases (configured in `tsconfig.json`) would make the imports more resilient.', 'gotcha', 'Module imports', 'auto-extracted,importance:low,session:refactoring', 3, NULL, '2026-01-24T17:01:47.807289', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('00f4bd9a-ec27-4ee1-9fea-4ca96882255a', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Exported the `Config` component as the default export and wired it into the application''s routing. This keeps the routing logic simple and follows the convention used by other feature pages.', 'decision', 'Routing integration', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T17:01:47.932468', 1769292107, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('ec2c31c7-7426-4ce3-a0cf-eab89833b9fe', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Created a dedicated `config-components.tsx` file to house reusable UI components for each configuration section, keeping the page component focused on orchestration and state handling.', 'decision', 'Config page UI', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:53.460988', 1769292113, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('54a3ba03-34a0-442a-a3ab-986cb91c5cbb', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Implemented a custom `use-config` hook to encapsulate fetching, updating, and restarting the daemon configuration, promoting separation of concerns and reusability across components.', 'decision', 'Config state management', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:53.535359', 1769292113, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('12974405-81c5-4de8-9a9e-a8b30a32a66b', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Chose to store form data in local component state (`useState`) rather than a global context to keep the configuration flow lightweight, accepting the trade‑off that changes are not globally visible until saved.', 'discovery', 'Form state handling', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T17:01:53.617491', 1769292113, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('6882ddd3-d88b-43d8-9867-92b7c7898497', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'Implemented a simple `handleChange` that updates the entire `formData` object per section instead of granular field updates, simplifying the logic at the cost of potentially re‑rendering the whole form on every keystroke.', 'discovery', 'Change handling', 'auto-extracted,importance:medium,session:refactoring', 5, NULL, '2026-01-24T17:01:53.690155', 1769292113, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('49f5e03c-7c95-4352-aac9-3ad6e94b9a8c', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'The `restartDaemon` API call must be awaited before updating the UI; otherwise, the UI may show stale data. Added proper async/await handling and error catching to avoid silent failures.', 'gotcha', 'Daemon restart integration', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:53.768957', 1769292113, 1);
INSERT INTO memory_observations (id, session_id, prompt_batch_id, observation, memory_type, context, tags, importance, file_path, created_at, created_at_epoch, embedded) VALUES ('32321bb9-1462-48a7-973d-116863b9bcab', 'b82ca70d-639b-427b-bb34-dec7756b80fb', 35, 'When initializing the form, the component must wait for the async fetch from `use-config` to complete; otherwise, accessing undefined properties causes runtime errors. Added a loading guard and default empty state.', 'gotcha', 'Initial data load', 'auto-extracted,importance:high,session:refactoring', 8, NULL, '2026-01-24T17:01:53.850852', 1769292113, 1);
