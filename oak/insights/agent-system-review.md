# Agent System, Prompt & Task Review

*Generated: 2026-02-20 | Scope: Full CI agent system, all prompts, all task definitions*

## Executive Summary

The Codebase Intelligence agent system is well-architected with a clean template-task separation, strong safety boundaries, and a well-thought-out CI tool integration. However, there are concrete opportunities for improvement in prompt effectiveness, model selection economics, and task configuration. This review evaluates every prompt and agent task using context engineering principles and recommends Sonnet 4.6 as the default model for most agent tasks.

### Key Findings

1. **Model selection is the highest-leverage change** — switching from Opus to Sonnet 4.6 for analysis, documentation, and product-manager tasks would reduce cost by ~75% with no meaningful quality loss
2. **Activity processing prompts are well-structured** but have context engineering gaps (missing examples in observation extraction, no altitude calibration for importance)
3. **Agent system prompts are strong** — right altitude, good tool documentation, clear safety rules
4. **Task definitions have inconsistent timeout/turn budgets** relative to actual task complexity
5. **Several prompts would benefit from canonical examples** (the strongest single improvement technique)

---

## Part 1: Activity Processing Prompts (Observation Extraction)

These prompts run on every session to extract observations, classify activities, generate titles, and produce summaries. They are high-volume, cost-sensitive, and should prioritize speed and consistency.

### 1.1 `extraction.md` — General Observation Extraction

**Context Engineering Score: 7/10**

**Strengths:**
- Clean XML-like structure with section headers separating data from instructions
- Schema-driven observation types (injected via `{{observation_types}}`)
- Importance calibration with session context awareness (planning vs. implementation)
- Conservative bias ("prefer fewer high-quality observations")

**Weaknesses:**
- **Missing canonical examples** — The output format section shows the JSON schema but no complete example of a good extraction. This is the single highest-impact improvement. Per the context engineering framework: "a single well-chosen example communicates more than paragraphs of rules."
- **Importance altitude is slightly too low** — The three-tier system (high/medium/low) is described with examples, but the examples mix abstraction levels. "Hidden gotchas" and "security considerations" are very different things.
- **No negative examples** — Showing what NOT to extract would reduce noise (e.g., "Do not extract observations that merely restate what a function does")

**Recommendation:**
```markdown
## Examples

Good observation:
{
  "type": "gotcha",
  "observation": "SQLite WAL mode must be enabled before concurrent reads work — default journal mode causes SQLITE_BUSY under load",
  "context": "activity/store/core.py",
  "importance": "high"
}

Bad observation (too generic — skip this):
{
  "type": "discovery",
  "observation": "The project uses SQLite for storage",
  "context": "activity/store",
  "importance": "low"
}
```

**Model recommendation: Sonnet 4.6** — This is structured extraction with a fixed JSON schema. Sonnet 4.6 handles this reliably and is ~5x cheaper than Opus for equivalent quality.

### 1.2 `classify.md` — Activity Classification

**Context Engineering Score: 8/10**

**Strengths:**
- Extremely focused — single-word output format
- Clean data presentation with numeric summaries
- Schema-driven classification types

**Weaknesses:**
- No examples of boundary cases (when is something "exploration" vs "debugging"?)
- No fallback guidance ("if unclear, prefer...")

**Model recommendation: Haiku or Sonnet 4.6** — Single-word classification is a trivial task for any model. This is the strongest candidate for the cheapest model available.

### 1.3 `session-summary.md` — Session Summarization

**Context Engineering Score: 9/10**

**Strengths:**
- Excellent canonical examples (3 good, 3 bad) — this is the best-structured prompt in the system
- Developer name personalization
- Session origin type awareness
- Clear output constraints (plain text, no JSON)
- Right altitude: "Be specific - include file names, feature names, and technical details"

**Weaknesses:**
- Could benefit from a "length budget" hint (e.g., "2-4 sentences for simple sessions, up to a paragraph for complex ones")

**Model recommendation: Sonnet 4.6** — Summarization is a core Sonnet strength. The examples provide enough guidance for consistent output.

### 1.4 `session-title.md` / `session-title-from-summary.md` — Title Generation

**Context Engineering Score: 8/10**

**Strengths:**
- Good examples of both good and bad titles
- Clear word count constraint (6-12 words)
- Strong output format constraints (no JSON, no quotes, no markdown)
- Parent context awareness for continuation sessions

**Weaknesses:**
- The two prompts are nearly identical — could be unified with a conditional section

**Model recommendation: Haiku or Sonnet 4.6** — Title generation is a lightweight task.

### 1.5 `debugging.md` / `exploration.md` / `implementation.md` — Specialized Extraction

**Context Engineering Score: 6/10**

**Strengths:**
- Activity-type-specific focus guidance (e.g., "Prefer bug_fix and gotcha types for debugging")
- Shared importance calibration section

**Weaknesses:**
- **No canonical examples in any of the three** — All three share the extraction.md problem but worse, because they handle specialized cases where examples would disambiguate most
- The debugging prompt says "Extract the debugging journey" but the output format doesn't have a field for journey/narrative — there's a mismatch between the prose instructions and the JSON schema
- Exploration prompt could guide on the distinction between "discovery" and "gotcha" for exploration-only sessions

**Model recommendation: Sonnet 4.6** — Same structured extraction pattern as the general case.

### 1.6 `session-similarity.md` — Session Relatedness Scoring

**Context Engineering Score: 9/10**

**Strengths:**
- Well-calibrated scoring rubric with clear ranges
- Multi-factor weighting guidance
- Single-number output — minimal ambiguity

**Weaknesses:**
- No examples of session pair comparisons showing expected scores

**Model recommendation: Haiku or Sonnet 4.6** — Numeric scoring with a rubric is a lightweight task.

---

## Part 2: Agent System Prompts

### 2.1 Analysis Agent (`analysis/prompts/system.md`)

**Context Engineering Score: 8/10**

**Strengths:**
- Excellent tool documentation table with "What It Does" and "When To Use" columns
- Complete database schema reference including lifecycle columns
- Useful SQL query patterns as examples
- Clear report writing standards with a template
- Strong safety rules (read-only SQL, no fabricated data)

**Weaknesses:**
- **Long context risk** — At ~170 lines, this prompt consumes significant context. The SQL query examples could be moved to a `references/` file and loaded just-in-time (Isolate strategy)
- The "Key Column Reference" section duplicates information already in the schema table
- Missing: guidance on when to use `ci_query` vs `ci_memories` vs `ci_sessions` (decision tree)

**Altitude assessment: Right level** — Specific enough to be actionable (SQL patterns, column names) without being brittle.

### 2.2 Documentation Agent (`documentation/prompts/system.md`)

**Context Engineering Score: 9/10**

**Strengths:**
- The best-designed agent prompt in the system
- Clear CI-native workflow (Gather → Extract → Write → Verify)
- Excellent good/bad output examples with explicit "What makes this good/bad" annotations
- Link formatting rules are specific and practical
- Sparse data handling guidance is thoughtful
- Stale link maintenance section prevents a real operational issue

**Weaknesses:**
- **Very long** (~460 lines) — This prompt alone could consume 3-4K tokens. The "Example Outputs" section (~120 lines) and "Handling Sparse CI Data" section (~70 lines) could be isolated into reference documents loaded only when needed
- The ci_queries code blocks in "CI-Native Documentation Workflow" show tool call syntax that's slightly different from actual tool call format — could cause confusion

**Altitude assessment: Slightly too low in places** — The link formatting rules are extremely specific (em-dash rules, parenthesis warnings). Consider whether this level of detail is needed in every invocation or could be a reference doc.

### 2.3 Engineering Team Agent (`engineering/prompts/system.md`)

**Context Engineering Score: 8/10**

**Strengths:**
- Clean role delegation ("Your task defines who you are")
- Assignment handling section clearly separates WHAT from HOW
- "Research First" pattern is the right default
- Prompt crafting guidance for review work is excellent — the example fix prompt is a perfect canonical example
- Safety rules are comprehensive and use RFC 2119 language (NEVER, ALWAYS)

**Weaknesses:**
- The "SDLC Actions (Future)" section is dead weight — it describes functionality that doesn't exist yet and wastes context tokens
- Missing: explicit guidance on when to stop and ask vs. make a judgment call
- The "Follow Existing Conventions" section could include a concrete example of finding and mirroring an exemplar

**Altitude assessment: Right level** — Good balance of principle and specificity.

---

## Part 3: Agent Task Definitions

### 3.1 Analysis Tasks

| Task | Timeout | Max Turns | Assessment |
|------|---------|-----------|------------|
| `codebase-activity-report` | 180s | 50 | Appropriate — SQL queries are fast |
| `productivity-report` | 180s | 50 | Appropriate |
| `usage-report` | 180s | 50 | Appropriate |
| `prompt-analysis` | 180s | 50 | Appropriate |

**Prompt quality:** All four analysis tasks are well-structured with numbered sections and clear SQL-centric workflows. The `prompt-analysis` task is the strongest — it has a clear methodology for bucketing prompts and identifying anti-patterns.

**Issue: Repetitive preamble** — All four tasks repeat "Use ci_query for all data gathering. Refer to the database schema in your system prompt..." This could be factored into the system prompt's report-writing section.

**Model recommendation: Sonnet 4.6 for all four** — These tasks are data analysis with SQL + report writing. Sonnet 4.6 generates correct SQL and writes clear prose. The structured task format makes output quality predictable regardless of model.

### 3.2 Documentation Tasks

| Task | Timeout | Max Turns | Assessment |
|------|---------|-----------|------------|
| `root-docs` | 480s | 80 | **High** — 4 files with cross-referencing justifies this |
| `architecture-docs` | 600s | 100 | Appropriate for ADR generation |
| `feature-docs` | 600s | 100 | Appropriate for multi-feature discovery |
| `changelog` | 300s | 50 | Appropriate |

**Prompt quality:** The `root-docs` task is the standout — the line budgets per file, the explicit "what belongs here vs. there" guidance, and the periodic run mindset are all well-designed. The `feature-docs` task's auto-discovery workflow is ambitious and well-structured.

**Issue with `architecture-docs`:** The task instructs "KEEP existing ADRs unchanged (they're historical records)" and "CREATE new ADRs for decisions not yet documented" — but there's no deduplication guidance. The agent needs to compare CI memory decisions against existing ADRs to avoid creating duplicate ADRs.

**Model recommendation:**
- `changelog`, `root-docs`: **Sonnet 4.6** — structured writing with clear templates
- `architecture-docs`, `feature-docs`: **Sonnet 4.6** — code exploration + writing, Sonnet handles both well

### 3.3 Engineering Tasks

| Task | Timeout | Max Turns | Assessment |
|------|---------|-----------|------------|
| `engineer` | 1800s | 200 | **Very high budget** — appropriate for implementation work with git + tests |
| `product-manager` | 600s | 100 | Appropriate for review/triage |

**Prompt quality:** The engineer task is well-structured with clear Research → Analyze → Implement methodology and proper git safety rules. The product-manager task is clean but could benefit from more concrete examples of what a good triage output looks like.

**Critical issue with `engineer` task:** `permission_mode: bypassPermissions` combined with `Bash` access and 1800s timeout is the highest-risk configuration in the system. The safety rules in the prompt are the only guardrail. Consider whether `acceptEdits` would be sufficient for most use cases, with `bypassPermissions` reserved for explicitly autonomous runs.

**Model recommendation:**
- `engineer`: **Opus or Sonnet 4.6** depending on task complexity — implementation work benefits from Opus's deeper reasoning for complex refactors; Sonnet 4.6 is sufficient for straightforward fixes and reviews
- `product-manager`: **Sonnet 4.6** — analysis and structured reporting

### 3.4 User Task: `docs-site-sync`

This is a well-crafted custom task with a sophisticated 7-step workflow, Playwright integration, and Astro-specific build verification. The 1200s/200-turn budget is appropriate for its scope (build + visual checks + multi-file updates).

**Model recommendation: Sonnet 4.6** — documentation synchronization with build verification.

---

## Part 4: Sonnet 4.6 Model Recommendations

### Why Sonnet 4.6 for Most Tasks

Sonnet 4.6 is the latest Claude Sonnet model. It offers:
- **Faster output** than Opus
- **Significantly lower cost** (~5x cheaper than Opus per token)
- **Strong tool use** — reliable function calling and structured output
- **Strong writing quality** — adequate for reports, documentation, changelogs
- **Good SQL generation** — handles the analysis task SQL patterns well
- **Reliable JSON extraction** — handles the observation extraction schema consistently

### Model Selection Matrix

| Task Category | Recommended Model | Rationale |
|--------------|-------------------|-----------|
| **Activity classification** | Haiku (if available) or Sonnet 4.6 | Single-word output, trivial task |
| **Session title generation** | Sonnet 4.6 | Short creative text, examples constrain output |
| **Observation extraction** | Sonnet 4.6 | Structured JSON, schema-driven |
| **Session summarization** | Sonnet 4.6 | Summarization is a Sonnet strength |
| **Session similarity scoring** | Haiku or Sonnet 4.6 | Single-number output |
| **Analysis reports** (all 4) | Sonnet 4.6 | SQL + markdown tables, structured output |
| **Documentation tasks** (all 4) | Sonnet 4.6 | Code search + writing, clear templates |
| **Product manager** | Sonnet 4.6 | Structured analysis and reporting |
| **Engineer** (reviews, simple fixes) | Sonnet 4.6 | Code reading + structured findings |
| **Engineer** (complex implementation) | Opus | Multi-file refactors, architectural changes, novel code |

### Implementation Path

The agent system already supports per-task model configuration via the `execution.model` field in task YAML files. To implement these recommendations:

1. **For activity processing prompts** — These are controlled by the summarization config in `.oak/config.yaml`. The `summarization.model` setting governs which model processes observations. Set this to a Sonnet 4.6 model identifier.

2. **For agent tasks** — Add `model: claude-sonnet-4-6` to each task's `execution:` block:
   ```yaml
   execution:
     timeout_seconds: 180
     max_turns: 50
     permission_mode: acceptEdits
     model: claude-sonnet-4-6
   ```

3. **For the engineer task** — Consider a tiered approach: default to Sonnet 4.6, allow users to override to Opus for complex work via the assignment prompt or a task-level config override.

### Cost Impact Estimate

Assuming typical usage patterns (prices approximate):

| Category | Current (Opus) | With Sonnet 4.6 | Savings |
|----------|---------------|-----------------|---------|
| Analysis tasks (4x/week) | ~$2.00/week | ~$0.40/week | 80% |
| Documentation tasks (4x/week) | ~$4.00/week | ~$0.80/week | 80% |
| Observation extraction (continuous) | ~$1.50/week | ~$0.30/week | 80% |
| Engineering tasks (varies) | ~$5.00/week | ~$1.00–$3.00/week | 40-80% |
| **Total estimated** | **~$12.50/week** | **~$2.50–$4.50/week** | **64-80%** |

*Note: Engineering tasks may still use Opus for complex implementation work, hence the wider range.*

---

## Part 5: Cross-Cutting Recommendations

### 5.1 Add Canonical Examples to Extraction Prompts (High Priority)

The observation extraction prompts (`extraction.md`, `debugging.md`, `exploration.md`, `implementation.md`) are missing the single most effective prompt engineering technique: canonical examples. Adding 1-2 complete input/output examples to each prompt would:
- Reduce observation noise (fewer low-value extractions)
- Improve importance calibration consistency
- Reduce model-dependent output variation (important when switching to Sonnet 4.6)

### 5.2 Compress the Documentation Agent System Prompt (Medium Priority)

At ~460 lines, the documentation agent system prompt consumes substantial context tokens. Apply the **Isolate** strategy:
- Move "Example Outputs" (~120 lines) to a reference file loaded only when relevant
- Move "Handling Sparse CI Data" (~70 lines) to a reference file
- Move the detailed "Link formatting rules" section to a reference file
- Keep the core workflow, tool table, and safety rules in the system prompt

This would reduce the system prompt from ~460 lines to ~250 lines, freeing ~2K tokens for actual document content.

### 5.3 Remove Dead Weight from Engineering System Prompt (Low Priority)

Remove the "SDLC Actions (Future)" section — it describes unimplemented functionality and wastes context tokens every invocation.

### 5.4 Add Deduplication Guidance to `architecture-docs` (Medium Priority)

The task instructs "CREATE new ADRs for decisions not yet documented" but provides no guidance on detecting whether a CI memory decision is already covered by an existing ADR. Add a deduplication step:
```
## 2.5 Deduplicate Before Writing
- For each decision memory, Grep existing ADRs for keywords from the decision
- If a matching ADR exists, skip (or note "already documented in ADR-{N}")
- Only CREATE an ADR for genuinely undocumented decisions
```

### 5.5 Standardize Task Preamble (Low Priority)

The four analysis tasks all repeat "Use ci_query for all data gathering. Refer to the database schema in your system prompt..." This boilerplate could be factored into the analysis agent system prompt as a default instruction, reducing each task by ~3 lines.

### 5.6 Consider Risk Tiers for `bypassPermissions` (Medium Priority)

The engineering agent template uses `bypassPermissions` with 1800s timeout and Bash access. While the safety rules in the prompt are strong, consider:
- Defaulting the template to `acceptEdits`
- Having only the `engineer` task override to `bypassPermissions` (which it already does)
- Adding a governance rule that audits all Bash calls during agent runs

---

## Part 6: Prompt-by-Prompt Scorecard

| Prompt/System | CE Score | Key Strength | Key Weakness | Model Rec |
|--------------|----------|-------------|-------------|-----------|
| `extraction.md` | 7/10 | Schema-driven types | Missing examples | Sonnet 4.6 |
| `classify.md` | 8/10 | Focused single-word output | No boundary examples | Haiku/Sonnet 4.6 |
| `session-summary.md` | 9/10 | 3 good + 3 bad examples | Could use length hint | Sonnet 4.6 |
| `session-title.md` | 8/10 | Clear constraints | Nearly identical twin | Sonnet 4.6 |
| `session-title-from-summary.md` | 8/10 | Clear constraints | Redundant with above | Sonnet 4.6 |
| `debugging.md` | 6/10 | Debugging focus | No examples, schema mismatch | Sonnet 4.6 |
| `exploration.md` | 6/10 | Exploration focus | No examples | Sonnet 4.6 |
| `implementation.md` | 6/10 | Implementation focus | No examples | Sonnet 4.6 |
| `session-similarity.md` | 9/10 | Well-calibrated rubric | No pair examples | Haiku/Sonnet 4.6 |
| Analysis system prompt | 8/10 | SQL patterns, schema | Long, some duplication | — |
| Documentation system prompt | 9/10 | Best-designed prompt | Too long (460 lines) | — |
| Engineering system prompt | 8/10 | Role delegation, safety | Dead "SDLC Actions" section | — |
| Analysis tasks (4) | 8/10 | Clear SQL workflows | Repetitive preamble | Sonnet 4.6 |
| Documentation tasks (4) | 8/10 | Line budgets, CI enrichment | ADR dedup gap | Sonnet 4.6 |
| Engineer task | 7/10 | Full SDLC methodology | High-risk permission mode | Opus/Sonnet 4.6 |
| Product Manager task | 7/10 | Clear triage methodology | Missing output examples | Sonnet 4.6 |

---

## Action Items (Prioritized)

1. **Set Sonnet 4.6 as default model** for all agent tasks except complex engineering work
2. **Add canonical examples** to `extraction.md`, `debugging.md`, `exploration.md`, `implementation.md`
3. **Compress documentation agent system prompt** by isolating examples and sparse-data guidance
4. **Add deduplication step** to `architecture-docs` task
5. **Remove "SDLC Actions (Future)"** from engineering system prompt
6. **Standardize analysis task preamble** into system prompt
7. **Review `bypassPermissions`** usage and add governance audit rules
