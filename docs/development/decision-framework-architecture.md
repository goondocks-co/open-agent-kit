# Decision Framework Architecture

## Overview

The decision framework uses **three complementary components** working together:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Framework                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DecisionContext Model (Python) ← SINGLE SOURCE OF TRUTH     │
│     └─ Type-safe schema with validation                         │
│                                                                 │
│  2. decision_points.yaml (YAML) ← AGENT REFERENCE               │
│     └─ Rich documentation for agent interactions                │
│                                                                 │
│  3. example-decisions*.json (JSON) ← USER REFERENCE             │
│     └─ Working examples for users                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. DecisionContext Model (Single Source of Truth)

**Location**: `src/open_agent_kit/models/constitution.py`

**Purpose**: Type-safe schema and validation for all constitution decisions.

**Responsibilities**:
- ✅ Define decision field types (Literal enums, int ranges, etc.)
- ✅ Validate decision values at creation time
- ✅ Provide sensible defaults
- ✅ Convert to template context for Jinja2 rendering
- ✅ Serve as the authoritative schema

**Example**:
```python
from open_agent_kit.models.constitution import DecisionContext

# Create with validation
decisions = DecisionContext(
    testing_strategy="balanced",
    coverage_target=70,
    architectural_pattern="clean_architecture",
    error_handling_pattern="result_pattern"
)

# Invalid values are rejected immediately
decisions = DecisionContext(testing_strategy="invalid")
# ValidationError: Input should be 'comprehensive', 'balanced' or 'pragmatic'
```

**Usage Pattern**:
1. Agent gathers user decisions interactively
2. Agent creates `DecisionContext(**user_decisions)`
3. Model validates all fields automatically
4. Validated context passed to `constitution_service.create()`

---

### 2. decision_points.yaml (Agent Reference)

**Location**: `templates/constitution/decision_points.yaml`

**Purpose**: Rich documentation and guidance for **AI agents** conducting interactive decision gathering.

**NOT for**: Runtime validation (that's the model's job)

**Responsibilities**:
- ✅ Document each decision point with descriptions
- ✅ Show characteristics and trade-offs for each option
- ✅ Provide follow-up questions for complex decisions
- ✅ Guide agents through the decision-gathering conversation
- ✅ Include "best-for" scenarios to help users choose

**Structure**:
```yaml
decision_categories:
  testing_strategy:
    description: "How comprehensive should testing be?"
    options:
      - id: "comprehensive"
        label: "Comprehensive Testing"
        characteristics:
          - "TDD required"
          - "High coverage target (80-100%)"
        best_for: "Mission-critical systems"
      # ... more options

    follow_up_questions:
      - condition: "if comprehensive"
        questions:
          - "What's your target coverage? (typically 80-100%)"
```

**Usage Pattern**:
1. Agent reads `decision_points.yaml` template
2. Agent uses it to structure the decision-gathering conversation
3. Agent presents options with characteristics
4. Agent asks follow-up questions based on user choices
5. Agent stores user decisions in a dict
6. Agent creates `DecisionContext(**decisions)` for validation

**Why Not Use for Validation?**
- YAML is for human/agent readability, not type safety
- Model provides compile-time type checking
- Model is tested (25 tests), YAML would need separate validation
- Model is importable, YAML requires parsing
- Model has IDE support, YAML doesn't

---

### 3. example-decisions*.json (User Reference)

**Location**: `templates/constitution/example-decisions*.json`

**Purpose**: Working examples for **users and agents** to understand decision structure.

**Four Example Files**:
1. **`example-decisions.json`** - Full example with all fields and comments
2. **`example-decisions-minimal.json`** - Minimal/pragmatic setup
3. **`example-decisions-comprehensive.json`** - Comprehensive/strict setup
4. **`example-decisions-oak-style.json`** - OAK's preferred style

**Responsibilities**:
- ✅ Show complete decision structure
- ✅ Demonstrate valid values
- ✅ Include `_comments` for documentation (ignored by model)
- ✅ Serve as templates for users to copy/modify
- ✅ Validated by tests (ensure they stay in sync with model)

**Example Structure**:
```json
{
  "_comment": "Example decision context for balanced projects",
  "_usage": "Pass this file to: oak constitution create-file --context-file decisions.json",

  "testing_strategy": "balanced",
  "coverage_target": 70,
  "coverage_strict": true,

  "architectural_pattern": "clean_architecture",
  "error_handling_pattern": "result_pattern",

  "_architectural_pattern_options": ["vertical_slice", "clean_architecture", "layered", "modular_monolith", "pragmatic", "custom"]
}
```

**Usage Patterns**:

**By Users**:
```bash
# Copy and modify an example
cp templates/constitution/example-decisions-oak-style.json my-decisions.json
# Edit my-decisions.json with your choices
oak constitution create-file \
  --project-name "MyProject" \
  --author "Team" \
  --context-file my-decisions.json
```

**By Agents**:
```python
# Agent creates decision dict from user answers
decisions_dict = {
    "testing_strategy": user_answer_1,
    "coverage_target": user_answer_2,
    # ...
}

# Save to file for user
with open("decisions.json", "w") as f:
    json.dump(decisions_dict, f, indent=2)

# Create validated model
decisions = DecisionContext(**decisions_dict)
```

**Validation**:
All example files are validated by tests:
```python
def test_example_decisions_json():
    """Test that example-decisions.json validates."""
    with open("templates/constitution/example-decisions.json") as f:
        data = json.load(f)

    decisions = DecisionContext(**data)  # Must validate!
    assert decisions is not None
```

This ensures examples never drift out of sync with the model.

---

## Data Flow

### Constitution Creation Flow

```
┌───────────────────────────────────────────────────────────────┐
│ Step 1: Agent Conversation (uses decision_points.yaml)        │
├───────────────────────────────────────────────────────────────┤
│ Agent: "How comprehensive should testing be?"                 │
│ User:  "Balanced approach with 70% coverage"                  │
│ Agent: "Which architectural pattern?"                         │
│ User:  "Clean Architecture with Result Pattern"               │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│ Step 2: Agent Creates Decision Dict                           │
├───────────────────────────────────────────────────────────────┤
│ decisions_dict = {                                            │
│   "testing_strategy": "balanced",                             │
│   "coverage_target": 70,                                      │
│   "architectural_pattern": "clean_architecture",              │
│   "error_handling_pattern": "result_pattern"                  │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│ Step 3: Validate with DecisionContext Model                   │
├───────────────────────────────────────────────────────────────┤
│ from open_agent_kit.models.constitution import DecisionContext     │
│ decisions = DecisionContext(**decisions_dict)                 │
│ # Validation passes                                           |
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│ Step 4: Create Constitution                                   │
├───────────────────────────────────────────────────────────────┤
│ constitution = service.create(                                │
│   project_name="MyProject",                                   │
│   author="Team",                                              │
│   decision_context=decisions  # Type-safe!                    │
│ )                                                             │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│ Step 5: Render Template (uses base_constitution.md)           │
├───────────────────────────────────────────────────────────────┤
│ Jinja2 conditionals use decision values to generate sections  │
│ - Testing section matches testing_strategy                    │
│ - Architecture section matches architectural_pattern          │
│ - Error handling section matches error_handling_pattern       │
└───────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture?

### Separation of Concerns

**DecisionContext (Python Model)**
- Runtime validation
- Type safety
- IDE support
- Testable

**decision_points.yaml (YAML)**
- Human-readable
- Rich documentation
- Agent guidance
- No code dependency

**example-decisions*.json (JSON)**
- User examples
- Copy-paste templates
- Version-controlled
- Test-validated

### Benefits

1. **Single Source of Truth** (Model)
   - One place to define schema
   - Type-safe by design
   - Validated automatically

2. **Rich Agent Guidance** (YAML)
   - Detailed descriptions
   - Option characteristics
   - Follow-up questions
   - Best practices

3. **User-Friendly Examples** (JSON)
   - Working templates
   - Different styles
   - Easy to copy/modify
   - Always valid (tested)

### Trade-offs

**Why Not Just YAML?**
- ❌ No type safety
- ❌ No IDE support
- ❌ Runtime parsing required
- ❌ Hard to test

**Why Not Just JSON Schema?**
- ❌ No runtime validation in Python
- ❌ No default values
- ❌ No method support (to_template_context)
- ❌ Less rich than YAML for documentation

**Why Not Just the Model?**
- ❌ No rich agent guidance
- ❌ No follow-up questions
- ❌ No best-for scenarios
- ❌ Harder for agents to read

**Our Solution: Use All Three**
- ✅ Model for validation
- ✅ YAML for guidance
- ✅ JSON for examples
- ✅ Each serves its purpose

---

## Adding a New Decision

### Step 1: Add to Model (Required)

```python
# src/open_agent_kit/models/constitution.py

class DecisionContext(BaseModel):
    # ... existing fields

    # New field
    security_scanning: bool = Field(
        default=False,
        description="Whether security scanning is required in CI/CD"
    )
```

### Step 2: Update YAML (Recommended)

```yaml
# templates/constitution/decision_points.yaml

security_scanning:
  description: "Should security vulnerabilities be scanned in CI/CD?"
  type: "boolean"
  default: false
  options:
    - id: true
      label: "Required"
      characteristics:
        - "Dependency scanning enabled"
        - "SAST/DAST checks"
      best_for: "Production systems"
    - id: false
      label: "Optional"
      best_for: "Early-stage projects"
```

### Step 3: Update Examples (Recommended)

```json
// templates/constitution/example-decisions.json

{
  "security_scanning": false,
  "_security_scanning_description": "Enable security scanning in CI/CD?"
}
```

### Step 4: Update Template (Required)

```jinja2
{# templates/constitution/base_constitution.md #}

{% if security_scanning -%}
### Security Scanning

All code must pass security scans before merge:
- Dependency vulnerability scanning
- SAST (Static Application Security Testing)
- DAST (Dynamic Application Security Testing)
{% endif %}
```

### Step 5: Add Tests (Required)

```python
# tests/test_decision_context.py

def test_security_scanning_field():
    """Test security_scanning field."""
    decisions = DecisionContext(security_scanning=True)
    assert decisions.security_scanning is True
```

**Total**: 5 steps (same as before), but with validation!

---

## Maintenance Guarantees

### Model Changes ✅
- **Type errors**: Caught at import time
- **Invalid values**: Caught at creation time
- **Missing fields**: IDE autocomplete shows them

### YAML Changes ⚠️
- **Not validated**: Free-form documentation
- **Purpose**: Agent guidance, not validation
- **Risk**: Low (agents adapt, not critical)

### JSON Examples ✅
- **Validated by tests**: All 4 examples tested
- **Tests fail if**: Example doesn't match model
- **Prevents drift**: Automatic sync checking

---

## Summary

| Component | Purpose | Validated | Type-Safe | Use Case |
|-----------|---------|-----------|-----------|----------|
| **DecisionContext** | Schema & validation | ✅ 25 tests | ✅ Pydantic | Runtime validation |
| **decision_points.yaml** | Agent guidance | ❌ Free-form | ❌ YAML | Interactive conversations |
| **example-decisions*.json** | User templates | ✅ 4 tests | ✅ Model validates | Copy-paste examples |

**Key Insight**: The model is the source of truth, YAML guides agents, JSON helps users.

---

## Future Enhancements (Optional)

### Phase 2: YAML Validation
- Validate `decision_points.yaml` against model schema
- Ensure YAML options match model Literal types
- Add CI check for YAML/model alignment

### Phase 3: Schema Generation
- Auto-generate JSON Schema from DecisionContext
- Export OpenAPI spec for external tools
- Generate TypeScript types for web UIs

### Phase 4: CLI Enhancements
- `oak decision validate decisions.json`
- `oak decision schema` (print JSON Schema)
- `oak decision example --style oak` (generate example)

---

## Questions & Answers

**Q: Why not remove the YAML file?**
A: It provides rich guidance for agents that the model can't (descriptions, best-for, characteristics, follow-up questions).

**Q: Why not remove the JSON examples?**
A: They're validated templates for users. Much easier to copy/modify than creating from scratch.

**Q: Can I use just the model?**
A: Yes! Agents can create `DecisionContext()` directly without YAML. But YAML makes conversations better.

**Q: Do I need to keep YAML and model in sync?**
A: Not strictly, but recommended. The model validates, YAML documents. They serve different purposes.

**Q: What if YAML has an option not in the model?**
A: Model validation will reject it. This is intentional - model is the source of truth.

**Q: Can I add fields to JSON examples?**
A: Yes! Fields starting with `_` are ignored by the model (useful for comments).

---

**Recommendation**: This architecture provides the best of all worlds - validation, guidance, and usability.
