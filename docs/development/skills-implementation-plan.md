# Plan: Add Skills Agent Capability + Planning Feature Skills

## Overview

Add Claude Agent Skills support to Open-Agent-Kit, then create skills for the planning feature to leverage Claude's native skill system for enhanced planning workflows.

## Confirmed Design Decisions

1. **Auto-install**: Skills auto-install when associated feature is installed (with prompt)
2. **Multiple focused skills**: Separate skills for planning-workflow, research-synthesis, task-decomposition
3. **Complement commands**: Skills provide domain knowledge, commands remain as structured workflows

---

## Architecture

### Skills vs Features vs Commands

```
┌──────────────────────────────────────────────────────────────────┐
│                         OAK System                                │
├──────────────────────────────────────────────────────────────────┤
│  Features (plan, rfc, constitution)                              │
│    └── Commands (structured workflows: /oak.plan-create)         │
│    └── Skills (domain knowledge: planning-workflow)              │
├──────────────────────────────────────────────────────────────────┤
│  Skills provide context and expertise                            │
│  Commands provide structured step-by-step workflows              │
│  Together they enhance agent capability                          │
└──────────────────────────────────────────────────────────────────┘
```

### Directory Structure

**Package (source):**
```
open-agent-kit/
├── features/
│   └── plan/
│       ├── manifest.yaml
│       ├── commands/
│       ├── templates/
│       └── skills/                   # Skills bundled with feature
│           ├── planning-workflow/
│           │   └── SKILL.md
│           ├── research-synthesis/
│           │   └── SKILL.md
│           └── task-decomposition/
│               └── SKILL.md
```

**Project (after installation):**
```
project/
├── .claude/                          # (only if Claude is configured)
│   └── skills/                       # Skills for agents with has_skills capability
│       ├── planning-workflow/
│       │   └── SKILL.md
│       └── ...
├── .oak/
│   └── config.yaml                   # Skills config (tracks installed skills)
```

**Key architectural decisions:**
- Skills are bundled with features, not standalone
- Skills only install to agents with `has_skills: true` capability
- Skills are auto-discovered from `features/{feature}/skills/` directories
- Skills are installed/removed as part of the feature lifecycle

---

## Implementation Phases

### Phase 1: Core Infrastructure

#### 1.1 SkillManifest Model
**New file:** `src/open_agent_kit/models/skill.py`

- Parse SKILL.md with YAML frontmatter
- Validate name (lowercase, hyphens, max 64 chars)
- Validate description (max 1024 chars)
- Support `allowed_tools` field
- Serialize back to SKILL.md format

#### 1.2 Config Updates
**Modify:** `src/open_agent_kit/models/config.py`

Add `SkillsConfig`:
```python
class SkillsConfig(BaseModel):
    installed: list[str] = []
    auto_install: bool = True
```

#### 1.3 Feature Manifest Update
**Modify:** `src/open_agent_kit/models/feature.py`

Add `skills` field to FeatureManifest for declaring associated skills.

#### 1.4 Constants
**Modify:** `src/open_agent_kit/constants.py`

```python
SUPPORTED_SKILLS = ["planning-workflow", "research-synthesis", "task-decomposition"]
SKILL_MANIFEST_FILE = "SKILL.md"
```

**Modify:** `src/open_agent_kit/config/paths.py`

```python
SKILLS_DIR = "skills"
```

---

### Phase 2: Service Layer

#### 2.1 SkillService
**New file:** `src/open_agent_kit/services/skill_service.py`

Key methods:
- `list_available_skills()` - Discover from package
- `list_installed_skills()` - From config
- `get_skill_manifest(name)` - Load SKILL.md
- `install_skill(name)` - Copy to .oak/skills/ and .claude/skills/
- `remove_skill(name)` - Remove and update config
- `refresh_skills()` - Re-copy all installed
- `install_skills_for_feature(feature)` - Auto-install associated skills
- `create_skill_scaffold(name, description)` - Generate new skill

#### 2.2 Feature Service Integration
**Modify:** `src/open_agent_kit/services/feature_service.py`

In `install_feature()`, call `skill_service.install_skills_for_feature()` when `auto_install` is enabled.

---

### Phase 3: CLI Commands

#### 3.1 Skill Command Group
**New file:** `src/open_agent_kit/commands/skill_cmd.py`

```
oak skill              # Interactive (defaults to list)
oak skill list         # Show available/installed
oak skill install <n>  # Install skill
oak skill remove <n>   # Remove skill
oak skill refresh      # Refresh all
oak skill create <n>   # Scaffold new skill
```

#### 3.2 CLI Registration
**Modify:** `src/open_agent_kit/cli.py`

```python
from open_agent_kit.commands.skill_cmd import skill_app
app.add_typer(skill_app, name="skill")
```

---

### Phase 4: Planning Skills Content

#### 4.1 Planning Workflow Skill
**New file:** `skills/planning-workflow/SKILL.md`

```yaml
---
name: planning-workflow
description: Guide strategic implementation planning with structured phases,
  risk assessment, and constitution alignment. Use when creating implementation
  plans, evaluating technical approaches, or structuring development work.
---
```

Sections: Context Gathering, Scope Definition, Risk Assessment, Task Decomposition, Success Criteria

#### 4.2 Research Synthesis Skill
**New file:** `skills/research-synthesis/SKILL.md`

```yaml
---
name: research-synthesis
description: Synthesize research findings into actionable insights for
  implementation planning. Use when consolidating research from multiple
  sources, comparing technical approaches, or extracting patterns.
---
```

Sections: Source Categories, Synthesis Process, Quality Indicators, Documentation Template

#### 4.3 Task Decomposition Skill
**New file:** `skills/task-decomposition/SKILL.md`

```yaml
---
name: task-decomposition
description: Break down implementation plans into well-structured, estimatable
  tasks with clear dependencies. Use when converting plans to tasks, structuring
  sprint work, or organizing development effort.
---
```

Sections: Task Hierarchy, Quality Checklist, Decomposition Patterns, Estimation Guidelines

---

### Phase 5: Feature Integration

#### 5.1 Update Plan Manifest
**Modify:** `features/plan/manifest.yaml`

```yaml
skills:
  - planning-workflow
  - research-synthesis
  - task-decomposition
```

#### 5.2 Update Claude Manifest
**Modify:** `agents/claude/manifest.yaml`

```yaml
capabilities:
  has_skills: true
  skills_directory: "skills"
```

---

## Critical Files

### New Files (8):
| File | Purpose |
|------|---------|
| `src/open_agent_kit/models/skill.py` | SkillManifest model with YAML parsing |
| `src/open_agent_kit/services/skill_service.py` | Skill management service |
| `src/open_agent_kit/commands/skill_cmd.py` | CLI commands |
| `skills/planning-workflow/SKILL.md` | Planning methodology skill |
| `skills/research-synthesis/SKILL.md` | Research synthesis skill |
| `skills/task-decomposition/SKILL.md` | Task decomposition skill |

### Modified Files (6):
| File | Changes |
|------|---------|
| `src/open_agent_kit/cli.py` | Add skill_app typer |
| `src/open_agent_kit/constants.py` | Add SUPPORTED_SKILLS |
| `src/open_agent_kit/config/paths.py` | Add SKILLS_DIR |
| `src/open_agent_kit/models/config.py` | Add SkillsConfig |
| `src/open_agent_kit/models/feature.py` | Add skills field |
| `src/open_agent_kit/services/feature_service.py` | Auto-install integration |
| `features/plan/manifest.yaml` | Add skills list |
| `agents/claude/manifest.yaml` | Add has_skills capability |

---

## Implementation Order

1. `src/open_agent_kit/models/skill.py` - SkillManifest model
2. `src/open_agent_kit/config/paths.py` - Add SKILLS_DIR constant
3. `src/open_agent_kit/constants.py` - Add SUPPORTED_SKILLS
4. `src/open_agent_kit/models/config.py` - Add SkillsConfig
5. `src/open_agent_kit/models/feature.py` - Add skills field
6. `agents/claude/manifest.yaml` - Add has_skills capability
7. `src/open_agent_kit/services/skill_service.py` - Core service
8. `src/open_agent_kit/services/feature_service.py` - Auto-install hook
9. `src/open_agent_kit/commands/skill_cmd.py` - CLI commands
10. `src/open_agent_kit/cli.py` - Register skill_app
11. `skills/planning-workflow/SKILL.md` - Planning skill
12. `skills/research-synthesis/SKILL.md` - Research skill
13. `skills/task-decomposition/SKILL.md` - Task skill
14. `features/plan/manifest.yaml` - Associate skills

---

## Testing Strategy

### Unit Tests
- `tests/unit/test_skill_model.py` - Manifest parsing, validation
- `tests/unit/test_skill_service.py` - Install, remove, list operations

### Integration Tests
- `tests/integration/test_skill_cli.py` - CLI commands E2E
- `tests/integration/test_feature_skill_install.py` - Auto-install flow

---

## Implementation Progress

### Completed ✓

1. **Core Infrastructure (Phase 1)**
   - [x] `src/open_agent_kit/models/skill.py` - SkillManifest model with YAML parsing
   - [x] `src/open_agent_kit/config/paths.py` - SKILLS_DIR constant
   - [x] `src/open_agent_kit/models/config.py` - SkillsConfig with auto_install
   - [x] `src/open_agent_kit/models/agent_manifest.py` - Added `has_skills` and `skills_directory` to AgentCapabilities

2. **Service Layer (Phase 2)**
   - [x] `src/open_agent_kit/services/skill_service.py` - Full service with:
     - Capability-based agent detection (checks `has_skills: true`)
     - Feature-based skill discovery (`features/{feature}/skills/`)
     - Install/remove/refresh/upgrade operations
   - [x] `src/open_agent_kit/services/feature_service.py` - Auto-install/remove integration

3. **CLI Commands (Phase 3)**
   - [x] `src/open_agent_kit/commands/skill_cmd.py` - Full CLI:
     - `oak skill list` - Show available/installed
     - `oak skill install <name>` - Install skill
     - `oak skill remove <name>` - Remove skill
     - `oak skill refresh` - Refresh all installed
   - [x] `src/open_agent_kit/cli.py` - Registered skill_app

4. **Planning Skills (Phase 4)**
   - [x] `features/plan/skills/planning-workflow/SKILL.md`
   - [x] `features/plan/skills/research-synthesis/SKILL.md`
   - [x] `features/plan/skills/task-decomposition/SKILL.md`

5. **Feature Integration (Phase 5)**
   - [x] `agents/claude/manifest.yaml` - has_skills capability

6. **Upgrade Integration**
   - [x] `src/open_agent_kit/services/upgrade_service.py` - Skills install/upgrade on `oak upgrade`
   - [x] `src/open_agent_kit/commands/upgrade_cmd.py` - Skills display in upgrade plan/results

### Architecture Decisions Made

1. **Skills are bundled with features** - Located at `features/{feature}/skills/{skill}/SKILL.md`
2. **Capability-based installation** - Skills only install to agents with `has_skills: true` in manifest
3. **Automatic lifecycle** - Skills install/remove with feature install/remove
4. **Upgrade support** - Skills install during `oak upgrade` for existing projects

### Pending

- [x] Unit tests for skill model and service
  - `tests/test_skill_model.py` - 45 tests for SkillManifest validation, parsing, serialization
  - `tests/test_skill_service.py` - 29 tests for SkillService operations
- [ ] Integration tests for CLI and feature lifecycle

### Recent Updates

**Skills Enhanced with OAK-Specific Content** (latest)

The planning skills have been updated to be **OAK-aware** rather than generic planning skills:

- **planning-workflow**: Now includes OAK command workflow diagram, file structure (`oak/plan/<name>/`), constitution integration, and expected `plan.md` format
- **research-synthesis**: Now includes `research/*.md` format, research-manifest.yml tracking, constitution cross-referencing, and OAK research workflow
- **task-decomposition**: Now includes `tasks.md` format, OAK phased structure, export considerations (GitHub/ADO), and constitution-driven testing tasks

Each skill now provides:
- OAK file structure and paths
- Command workflow diagrams showing where the skill fits
- Expected document formats matching OAK conventions
- Constitution integration guidance
- Quick reference section for paths and relationships
