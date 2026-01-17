# RFC: OAK Skills Architecture Redesign - Implementation Record

**Status**: Implemented
**Date**: 2026-01-16
**Branch**: `feat/codebase-intelligence`

## Overview

This document records the implementation of the OAK Skills Architecture Redesign, which modernizes OAK's skills and commands to leverage modern agent capabilities while consolidating features around core value propositions.

## Design Decisions

- **RFC → Planning merge**: RFC skills merged into strategic-planning feature
- **Document naming**: Output document stays `constitution.md` (feature is `rules-management`)
- **Agent focus**: Claude Code first; Gemini workspace-level skills added later
- **Migration**: Clean break - no backward compatibility aliases

---

## Implementation Summary

### Phase 1: New Gerund Skills ✅

Created 5 new skills (consolidated from 9 original skills):

| Old Skills | New Skill | Feature | Status |
|-----------|-----------|---------|--------|
| constitution-authoring, constitution-governance | `managing-rules` | rules-management | ✅ Complete |
| planning-workflow, task-decomposition, rfc-authoring | `planning-work` | strategic-planning | ✅ Complete |
| research-synthesis | `researching-topics` | strategic-planning | ✅ Complete |
| rfc-review | `reviewing-plans` | strategic-planning | ✅ Complete |
| codebase-awareness | `searching-code` | codebase-intelligence | ✅ Complete |
| memory-capture | `capturing-memories` | codebase-intelligence | ✅ Complete |

**Files created:**
- `features/rules-management/skills/managing-rules/SKILL.md`
- `features/strategic-planning/skills/planning-work/SKILL.md`
- `features/strategic-planning/skills/researching-topics/SKILL.md`
- `features/strategic-planning/skills/reviewing-plans/SKILL.md`
- `features/codebase-intelligence/skills/searching-code/SKILL.md`
- `features/codebase-intelligence/skills/capturing-memories/SKILL.md`

### Phase 2: Feature Consolidation ✅

| Old Feature | New Feature | Status |
|-------------|-------------|--------|
| constitution | `rules-management` | ✅ Complete |
| plan + rfc | `strategic-planning` | ✅ Complete |
| codebase-intelligence | `codebase-intelligence` (unchanged) | ✅ Updated |

**Files created/modified:**
- `features/rules-management/manifest.yaml` - New manifest
- `features/strategic-planning/manifest.yaml` - New manifest (merged plan + rfc)
- `features/codebase-intelligence/manifest.yaml` - Updated dependencies and skills
- `src/open_agent_kit/constants.py` - Updated SUPPORTED_FEATURES, FEATURE_CONFIG

**Files deleted:**
- `features/constitution/` - Entire directory (content copied to rules-management)
- `features/plan/` - Entire directory (content copied to strategic-planning)
- `features/rfc/` - Entire directory (content merged into strategic-planning)

### Phase 3: CLI Updates ✅

| Old Command | New Command | Status |
|-------------|-------------|--------|
| `oak constitution *` | `oak rules *` | ✅ Complete |
| `oak rfc create` | `oak rfc create` (part of strategic-planning) | ✅ Unchanged |
| `oak plan *` | `oak plan *` | ✅ Unchanged |
| `oak ci *` | `oak ci *` | ✅ Unchanged |

**Files created/modified:**
- `src/open_agent_kit/commands/rules_cmd.py` - New CLI command module
- `src/open_agent_kit/cli.py` - Updated to use rules_app
- `features/rules-management/commands/oak.rules.md` - Simplified command reference
- `features/strategic-planning/commands/oak.plan.md` - Simplified command reference

### Phase 4: Cleanup ✅

- Deleted old skill directories from all features
- Updated template references from `features/constitution/` to `features/rules-management/`
- Removed old feature directories

---

## New Directory Structure

```
features/
├── core/
│   └── manifest.yaml
│
├── rules-management/              # Renamed from constitution
│   ├── manifest.yaml
│   ├── skills/
│   │   └── managing-rules/
│   │       └── SKILL.md
│   ├── commands/
│   │   ├── oak.rules.md
│   │   └── oak.constitution-*.md  # Legacy commands (kept for reference)
│   └── templates/
│       ├── base_constitution.md
│       ├── agent_instructions.md
│       ├── decision_points.yaml
│       └── includes/
│
├── strategic-planning/            # Merged plan + rfc
│   ├── manifest.yaml
│   ├── skills/
│   │   ├── planning-work/
│   │   │   └── SKILL.md
│   │   ├── researching-topics/
│   │   │   └── SKILL.md
│   │   └── reviewing-plans/
│   │       └── SKILL.md
│   ├── commands/
│   │   ├── oak.plan.md
│   │   ├── oak.plan-*.md
│   │   └── oak.rfc-*.md
│   └── templates/
│       ├── early_triage.md
│       ├── plan_structure.md
│       ├── architecture.md        # RFC template
│       ├── engineering.md         # RFC template
│       └── ...
│
└── codebase-intelligence/
    ├── manifest.yaml
    ├── skills/
    │   ├── searching-code/
    │   │   └── SKILL.md
    │   └── capturing-memories/
    │       └── SKILL.md
    ├── commands/
    │   └── oak.ci.md
    ├── hooks/
    ├── mcp/
    └── prompts/
```

---

## Constants Changes

### SUPPORTED_FEATURES

```python
# Before
SUPPORTED_FEATURES = ["constitution", "rfc", "plan", "codebase-intelligence"]

# After
SUPPORTED_FEATURES = ["rules-management", "strategic-planning", "codebase-intelligence"]
```

### DEFAULT_FEATURES

```python
# Before
DEFAULT_FEATURES = ["constitution", "rfc", "plan"]

# After
DEFAULT_FEATURES = ["rules-management", "strategic-planning"]
```

### FEATURE_CONFIG

```python
FEATURE_CONFIG = {
    "rules-management": {
        "name": "Rules Management",
        "description": "Create, validate, and maintain AI agent rules files (constitution.md)",
        "default_enabled": True,
        "dependencies": [],
        "commands": ["rules-create", "rules-validate", "rules-amend"],
    },
    "strategic-planning": {
        "name": "Strategic Planning",
        "description": "Unified SDD workflow supporting implementation planning, RFCs, research phases, structured task generation, and export to issue trackers",
        "default_enabled": True,
        "dependencies": ["rules-management"],
        "commands": [
            "plan-create", "plan-research", "plan-tasks",
            "plan-implement", "plan-export", "plan-validate",
            "rfc-create", "rfc-list", "rfc-validate",
        ],
    },
    "codebase-intelligence": {
        "name": "Codebase Intelligence",
        "description": "Semantic search and persistent memory for AI assistants...",
        "default_enabled": False,
        "dependencies": ["rules-management"],
        "commands": ["ci"],
        "pip_extras": ["codebase-intelligence"],
    },
}
```

---

## Skill Naming Convention

All skills now follow a **gerund naming convention** (verb + -ing):

| Skill Name | Description |
|------------|-------------|
| `managing-rules` | Create and maintain rules files |
| `planning-work` | Create plans, RFCs, and task breakdowns |
| `researching-topics` | Research unknowns before implementation |
| `reviewing-plans` | Review and validate plans |
| `searching-code` | Semantic code search and context retrieval |
| `capturing-memories` | Store observations for future sessions |

---

## Migration Notes

### For Users

1. Run `oak upgrade` after updating to refresh skills and commands
2. Use `oak rules` instead of `oak constitution`
3. The output file is still `constitution.md` - only the feature name changed

### For Developers

1. Feature service now looks for `rules-management` instead of `constitution`
2. ConstitutionService remains unchanged (manages the constitution.md file)
3. Skills are discovered from the new feature directories

---

## Testing Checklist

- [ ] `oak init` creates new feature directories correctly
- [ ] `oak rules create` works (replacement for `oak constitution create`)
- [ ] `oak rules validate` works
- [ ] `oak plan create` works
- [ ] Skills are installed to `.claude/skills/` with new names
- [ ] `oak upgrade` refreshes skills correctly
- [ ] CI hooks work with codebase-intelligence

---

## Known Issues / Future Work

1. **Legacy command compatibility**: The old `oak constitution` command is removed. Users must use `oak rules`.
2. **Service layer**: ConstitutionService still uses "constitution" naming since the output file is `constitution.md`.
3. **Tests**: Tests that reference old feature names need updating.

---

## References

- Original RFC: `docs/rfcs/RFC-SKILLS-ARCHITECTURE-REDESIGN.md`
- Constitution doc: `docs/development/features.md`
- Skills system: `src/open_agent_kit/services/skill_service.py`
