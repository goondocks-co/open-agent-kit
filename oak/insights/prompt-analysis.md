# Prompt Quality Analysis Report

*Generated: 2026-02-07 | Analysis Period: Weeks 03-05 of 2026*

## Key Findings

1. **Longer prompts correlate with lower error rates** — Sessions with comprehensive prompts (avg 600+ chars) have 0.65% error rate vs 1.75% for brief prompts
2. **87% of prompts are classified** — Strong signal that the AI understands most instructions clearly
3. **File references dramatically improve context** — Prompts with `@file` or path references average 2,235 chars and lead to more focused work
4. **Short prompts dominate but underperform** — 23% of prompts are <50 chars, often leading to clarification loops

---

## 1. Prompt Overview

### Baseline Statistics

| Metric | Value |
|--------|-------|
| Total prompts analyzed | 862 |
| Total sessions | 160 |
| Average prompts per session | 5.39 |
| Average prompt length | 590 chars |
| Shortest prompt | 8 chars |
| Longest prompt | 10,000 chars |
| With classification | 750 (87%) |
| Without classification | 112 (13%) |

### Prompt Length Distribution

| Length Bucket | Count | % of Total | Avg Chars |
|---------------|-------|------------|-----------|
| Short (<50 chars) | 200 | 23% | 27 |
| Medium (50-200) | 302 | 35% | 119 |
| Long (200-500) | 214 | 25% | 315 |
| Very Long (500+) | 146 | 17% | 2,738 |

**Insight**: The majority of prompts (58%) fall in the short-to-medium range. The "very long" category averages nearly 3K characters, indicating detailed specifications with context.

### Classification Distribution

| Classification | Count | Avg Length |
|----------------|-------|------------|
| exploration | 202 | 446 chars |
| implementation | 160 | 486 chars |
| refactoring | 159 | 284 chars |
| system | 96 | 27 chars |
| debugging | 67 | 361 chars |
| plan | 56 | 1,962 chars |
| agent_work | 5 | 8,084 chars |

**Insight**: Planning prompts are significantly longer (avg 1,962 chars), reflecting the detailed nature of architectural decisions. Exploration and implementation prompts cluster around 450-500 chars—the "sweet spot" for actionable instructions.

---

## 2. Prompt Quality Patterns

### Length vs. Session Outcomes

| Prompt Detail Level | Sessions | Avg Prompts | Avg Activities | Error Rate |
|---------------------|----------|-------------|----------------|------------|
| Brief (<100 avg chars) | 25 | 4.5 | 106.6 | 1.75% |
| Moderate (100-300) | 53 | 7.5 | 147.8 | 1.50% |
| Detailed (300-600) | 37 | 5.2 | 102.2 | 1.33% |
| Comprehensive (600+) | 45 | 3.5 | 114.2 | **0.65%** |

**Key Finding**: Sessions with comprehensive prompts have **63% lower error rates** than those with brief prompts. This strongly suggests that upfront investment in detailed prompts pays off in reduced rework and errors.

### Classification by Length Bucket

**Short prompts (<50 chars):**
- 96 are `system` (internal/automated)
- 31 are `exploration`
- 20 are `refactoring`
- Only 13 are `implementation`

**Very long prompts (500+ chars):**
- 50 are `exploration` (deep research)
- 27 are `plan` (architectural decisions)
- 26 are `implementation` (detailed specs)

**Insight**: Short prompts are heavily skewed toward system messages and quick exploration. Substantive work (implementation, planning) benefits from longer, more detailed prompts.

### Context Signals in Prompts

| Context Type | Count | Avg Length |
|--------------|-------|------------|
| Has file reference (`@`, `.py`, `.ts`, etc.) | 159 | 2,235 chars |
| No file reference | 703 | 218 chars |

Prompts that reference specific files are **10x longer** on average—they provide the context needed for targeted work.

| Pattern Type | Count | Avg Length |
|--------------|-------|------------|
| Has `@file` mention | 55 | 2,460 chars |
| Has path reference (`src/`, `/oak/`) | 32 | 5,408 chars |
| Has code reference (function, class) | 21 | 1,271 chars |
| Problem description (error, bug, issue) | 90 | 417 chars |
| General (no specific markers) | 532 | 225 chars |

---

## 3. Common Anti-Patterns

### Very Short Prompts (< 20 chars)

These 16 prompts represent vague instructions that typically require follow-up:

| Prompt | Length | Classification |
|--------|--------|----------------|
| "continue" | 8 | exploration |
| "go ahead" | 8 | implementation |
| "try again" | 9 | (none) |
| "section 4" | 9 | debugging |
| "yes fix it" | 10 | refactoring |
| "claudeyolo" | 10 | (none) |
| "test prompt" | 11 | refactoring |
| "ok, check now" | 13 | exploration |

**Problem**: These prompts provide no context about *what* to continue, *what* to fix, or *which* section. They rely entirely on the AI remembering prior context.

### Rework Indicators

Sessions with multiple "try again" or "retry" patterns:

| Session ID | Prompts | Rework Indicators | Very Short (<30 chars) |
|------------|---------|-------------------|------------------------|
| c930cc44... | 7 | 4 | 0 |
| 0558da05... | 9 | 2 | 4 |
| a4b98e69... | 7 | 2 | 2 |
| 18a6287d... | 16 | 2 | 1 |

**Pattern**: Sessions with multiple rework indicators often also have several very short prompts. This suggests that vague initial instructions lead to retry loops.

### Prompts Without Classification

112 prompts (13%) received no classification. Common patterns:
- Follow-up confirmations: "yes", "ok", "sounds good"
- Context references: "and there we go!", "ok, makes sense"
- Partial thoughts: "ok, makes sense. i"

These work fine as conversational continuations but are less effective as standalone instructions.

---

## 4. Exemplary Prompts

### High-Activity, Low-Error Prompts

These prompts led to productive sessions with zero errors:

| Preview (200 chars) | Length | Classification | Activities |
|---------------------|--------|----------------|------------|
| "ok, help me understand the ux here. for the first one, the plan is in the prompt. i do want the plan in the db, but i don't think this was the intention..." | 1,186 | implementation | 284 |
| "really take a look at the install process for oak. so much has been added, we have a lot of dependencies, especially when installing codebase intelligence..." | 1,445 | exploration | 281 |
| "great, we've found many issues and i like the suggestions. lets jump into plan mode and map all of this out in detail" | 117 | plan | 281 |

### What Makes These Effective

1. **Clear Intent**: "help me understand", "take a look at", "map all of this out"
2. **Specific Context**: References to UX, installation process, specific features
3. **Actionable Direction**: "jump into plan mode", not just "plan this"
4. **Acknowledgment of Progress**: "we've found many issues" provides context from prior work

### Effective Implementation Prompts (200-600 chars)

Recent well-structured implementation prompts:

```
"If the daemon port was referenced in the Claude.md file, then it was
likely referenced in all of the agent instruction files. Go ahead and
update all of them, including the Constitution if it's referenced there."
```
*Why it works*: Specific file mentioned, clear action (update), scope defined (all agent files)

```
"Okay, now let's jump back into the Astro site and the Coding Agents
Agents Overview page. Let's pull out skills into its own page in the
coding agent section, as there's plenty of information there to justify
its own page."
```
*Why it works*: Navigation context (Astro site), specific page, clear refactoring goal with rationale

### Effective Debugging Prompts

```
"looks good. in the daemon.log, i keeps seeing this warning, what's going on?
16:39:04 [DEBUG] open_agent_kit.features.codebase_intelligence.activity.processor.llm:79 -
[LLM] Response status: 400..."
```
*Why it works*: Includes actual log output, specific timestamp, asks for explanation

---

## 5. Context Engineering Recommendations

### Optimal Prompt Length

Based on your data:

| Use Case | Recommended Length | Why |
|----------|-------------------|-----|
| Quick confirmation | 20-50 chars | Just enough to affirm direction |
| Exploration | 200-500 chars | Enough context to guide research |
| Implementation | 300-600 chars | Specific enough to avoid ambiguity |
| Planning/Architecture | 500-2000 chars | Complex decisions need full context |
| Bug reports | 400-800 chars | Include error output, expected vs actual |

**Sweet Spot**: 200-600 characters for most productive work.

### Tips for Writing Better Prompts

Based on patterns that correlated with successful sessions:

1. **Reference files explicitly** with `@filename` or full paths
   - Prompts with file references are 10x more detailed and lead to focused work

2. **State intent before action**
   - ✅ "I want to understand X. Can you explore Y?"
   - ❌ "explore Y"

3. **Provide success criteria**
   - ✅ "Update the config. Verify by running the tests."
   - ❌ "Update the config."

4. **Include error output for debugging**
   - Debugging prompts averaging 361 chars typically include actual error messages
   - The most effective ones paste log snippets directly

5. **Use "jump into plan mode" for complex tasks**
   - Planning prompts average 1,962 chars for good reason
   - Complex work benefits from explicit planning phases

### Common Mistakes to Avoid

| Anti-Pattern | Example | Better Alternative |
|--------------|---------|-------------------|
| Vague continuation | "continue" | "continue implementing the session tracking feature" |
| Context-free confirmation | "yes" | "yes, implement the caching approach you suggested" |
| Retry without context | "try again" | "try again, but this time check if the file exists first" |
| Implicit file reference | "fix the bug" | "fix the bug in src/daemon/routes.py line 42" |

### Improvement Trend Over Time

| Week | Total Prompts | Avg Length | Classification Rate | Short Prompts | Detailed Prompts |
|------|---------------|------------|---------------------|---------------|------------------|
| 2026-03 | 150 | 1,872 | 83% | 10% | 57% |
| 2026-04 | 288 | 451 | 93% | 10% | 50% |
| 2026-05 | 424 | 231 | 85% | 37% | 30% |

**Trend Analysis**:
- Week 03 had the highest average length (1,872 chars) with the most detailed prompts
- Week 05 shows increased volume (424 prompts) but shorter average length (231 chars)
- This may indicate faster iteration cycles OR increased reliance on context carryover

**Recommendation**: Monitor if shorter prompts in Week 05 correlate with increased rework. If so, consider investing more upfront in prompt detail.

---

## Summary: Your Prompt Quality Score

| Metric | Your Data | Benchmark | Status |
|--------|-----------|-----------|--------|
| Classification rate | 87% | >80% | ✅ Good |
| Avg prompt length | 590 chars | 300-600 | ✅ Good |
| Short prompts (<50) | 23% | <15% | ⚠️ Room to improve |
| File references | 18% | >25% | ⚠️ Room to improve |
| Error rate (comprehensive) | 0.65% | <1% | ✅ Excellent |

### Action Items

1. **Reduce ultra-short prompts** — Convert "continue" to "continue with [specific next step]"
2. **Increase file references** — Use `@filename` syntax more frequently to anchor context
3. **Front-load detail** — Invest the extra 30 seconds upfront to write 200+ char prompts
4. **Include rationale** — "because X" helps the AI understand the "why" behind requests

---

*This report is based on 862 prompts across 160 sessions. Data extracted from Oak CI `prompt_batches` and `activities` tables.*
