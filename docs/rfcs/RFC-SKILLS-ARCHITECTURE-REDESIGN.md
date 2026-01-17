# RFC: OAK Skills Architecture Redesign

**Status**: Approved
**Date**: 2026-01-16

## Overview

Redesign OAK's skills and commands to leverage modern agent capabilities (built-in plan mode, SDD, user-invokable skills) while consolidating features around core value propositions.

## Design Decisions

- **RFC → Planning merge**: RFC skills merge into strategic-planning feature
- **Document naming**: Output document stays `constitution.md` (feature is `rules-management`)
- **Agent focus**: Claude Code first; Gemini workspace-level skills added later
- **Migration**: Clean break - no backward compatibility aliases. Users run upgrade or reinstall.

---

## Key Changes

### 1. Skill Naming: Gerund Convention

| Current | New | Feature |
|---------|-----|---------|
| `constitution-authoring` | `managing-rules` | rules-management |
| `constitution-governance` | *(merged)* | rules-management |
| `planning-workflow` | `planning-work` | strategic-planning |
| `research-synthesis` | `researching-topics` | strategic-planning |
| `task-decomposition` | *(merged)* | strategic-planning |
| `rfc-authoring` | *(merged into planning-work)* | strategic-planning |
| `rfc-review` | `reviewing-plans` | strategic-planning |
| `codebase-awareness` | `searching-code` | codebase-intelligence |
| `memory-capture` | `capturing-memories` | codebase-intelligence |

**Result: 9 skills → 5 skills**

### 2. Feature Consolidation

| Current | New | Rationale |
|---------|-----|-----------|
| `constitution` | `rules-management` | Clearer purpose: managing AI agent rules files |
| `rfc` + `plan` | `strategic-planning` | RFC is a planning document type |
| `codebase-intelligence` | `codebase-intelligence` | Star feature, unchanged |

### 3. Directory Structure

```
features/
├── rules-management/              # Renamed from constitution
│   ├── manifest.yaml
│   ├── skills/
│   │   └── managing-rules/
│   │       ├── SKILL.md
│   │       └── references/
│   ├── commands/
│   │   └── oak.rules.md           # Simplified fallback
│   └── assets/                    # Shared scripts/templates
│
├── strategic-planning/            # Merged plan + rfc
│   ├── manifest.yaml
│   ├── skills/
│   │   ├── planning-work/
│   │   ├── researching-topics/
│   │   └── reviewing-plans/
│   ├── commands/
│   │   └── oak.plan.md
│   └── assets/
│
└── codebase-intelligence/         # Unchanged structure
    ├── skills/
    │   ├── searching-code/
    │   └── capturing-memories/
    └── ...
```

### 4. CLI Changes

| Current | New |
|---------|-----|
| `oak constitution *` | `oak rules *` |
| `oak rfc create` | `oak plan create --template rfc` |
| `oak plan *` | `oak plan *` |
| `oak ci *` | `oak ci *` |

### 5. Command Simplification

Commands become lightweight fallbacks for agents without skills. They reference shared assets.

**Before** (`oak.plan-create.md` - 120+ lines):
```markdown
## Step 1: Planning Source Decision
{% include 'early_triage.md' %}
... (full workflow)
```

**After** (`oak.plan.md` - concise):
```markdown
Follow the planning workflow in .claude/skills/planning-work/SKILL.md
For CLI: oak plan create|research|tasks|export|validate
```

### 6. What We Stop Replicating

| Built-in Agent Feature | OAK Can Remove |
|------------------------|----------------|
| Plan mode | Heavy workflow orchestration |
| SDD tool | Spec-driven development prompts |
| WebSearch/WebFetch | Custom research orchestration |
| Todo tracking | Task management workflows |

**New approach**: Skills guide *when* to use built-in features, not *how*.

---

## Implementation Plan

### Phase 1: New Gerund Skills
**Agent**: Use `code-documentation:docs-architect` for skill content design

1. Create new skill directories with gerund names
2. Design SKILL.md with `allowed-tools`, `hooks`, `user-invocable` metadata
3. Add progressive disclosure with reference files

**Files to create:**
- `features/rules-management/skills/managing-rules/SKILL.md`
- `features/strategic-planning/skills/planning-work/SKILL.md`
- `features/strategic-planning/skills/researching-topics/SKILL.md`
- `features/strategic-planning/skills/reviewing-plans/SKILL.md`
- `features/codebase-intelligence/skills/searching-code/SKILL.md`
- `features/codebase-intelligence/skills/capturing-memories/SKILL.md`

### Phase 2: Feature Consolidation
**Agent**: Use `code-refactoring:legacy-modernizer` for migration

1. Rename `constitution` directory → `rules-management`
2. Merge `rfc` directory into `plan` → rename to `strategic-planning`
3. Update manifests and remove old feature references
4. Delete old skill directories

**Files to modify:**
- `src/open_agent_kit/constants.py` - SUPPORTED_FEATURES, FEATURE_CONFIG
- `features/*/manifest.yaml` - all manifests
- `src/open_agent_kit/services/feature_service.py`
- `src/open_agent_kit/services/skill_service.py`

### Phase 3: CLI Updates
**Agent**: Use `backend-development:backend-architect` for CLI design

1. Replace `oak constitution` command group with `oak rules`
2. Remove `oak rfc` standalone commands (integrate into `oak plan`)
3. Simplify command prompts to reference skills

**Files to modify:**
- `src/open_agent_kit/commands/cli.py`
- `src/open_agent_kit/commands/*_cmd.py`
- `features/*/commands/*.md`

### Phase 4: Skill Enhancements
**Agent**: Use `llm-application-dev:prompt-engineer` for skill optimization

1. Add `hooks` definitions to skills (especially CI skills)
2. Add `context: fork` for isolated skills where appropriate
3. Create progressive disclosure reference files
4. Test skill invocation in Claude Code

**Files to create/modify:**
- `features/*/skills/*/references/*.md`
- `features/*/skills/*/assets/*`

### Phase 5: Migration & Cleanup
**Agent**: Use `debugging-toolkit:dx-optimizer` for migration experience

1. Update `oak upgrade` to handle feature renames
2. Remove old feature directories completely
3. Update documentation
4. Test fresh install and upgrade paths

---

## Critical Files

| File | Purpose |
|------|---------|
| `src/open_agent_kit/constants.py` | Feature config, supported features |
| `src/open_agent_kit/services/skill_service.py` | Skill lifecycle |
| `src/open_agent_kit/services/feature_service.py` | Feature management |
| `features/*/manifest.yaml` | Feature definitions |
| `features/*/skills/*/SKILL.md` | Skill definitions |

---

## Verification

1. Run `oak init` with new features, verify skills install
2. Test skill invocation via `/managing-rules` in Claude Code
3. Test CLI: `oak rules create`, `oak plan create --template rfc`
4. Verify hooks work in codebase-intelligence skills
5. Test fresh install path
6. Test upgrade path from previous version

---

## Execution Strategy

Use specialized agents in parallel where possible:

```
Phase 1 (Skills)          Phase 2 (Features)       Phase 3-5 (CLI/Polish)
├─ docs-architect         ├─ legacy-modernizer     ├─ backend-architect
│  (managing-rules)       │  (constitution→rules)  │  (CLI updates)
├─ docs-architect         ├─ legacy-modernizer     ├─ prompt-engineer
│  (planning-work)        │  (rfc+plan→strategic)  │  (skill optimization)
├─ docs-architect         │                        └─ dx-optimizer
│  (researching-topics)   │                           (migration)
├─ docs-architect         │
│  (reviewing-plans)      │
├─ docs-architect         │
│  (searching-code)       │
└─ docs-architect         │
   (capturing-memories)   │
```

Background agents can work on independent skills simultaneously, then synchronize for feature consolidation.
