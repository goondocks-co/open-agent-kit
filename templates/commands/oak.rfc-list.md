---
description: List and analyze RFC documents in the project.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** incorporate any provided filters or goals supplied by the user.

## Purpose

Generate an informative overview of the RFC landscape. Highlight trends, stale work, and actionable insights rather than simply echoing CLI output. Support both exploratory (greenfield) and maintenance (brownfield) scenarios.

## Workflow Overview

1. Clarify what the user wants to learn (status overview, stale drafts, ownership questions, etc.).
2. Run the appropriate CLI commands to gather RFC metadata (`oak rfc list --json`, `--verbose`, filters).
3. Analyze the data: segment results, spot patterns, and surface risks/opportunities.
4. Present findings in a structured format with recommendations.

## Step 1: Clarify Intent & Filters

1. Parse `$ARGUMENTS` for hints (status filters, author names, date ranges, tags, keywords).
2. If unclear, ask the user what they need (e.g., “Do you want drafts pending review? All adopted architecture RFCs? Recently implemented?”).
3. Confirm any constraints (limit count, need JSON output, highlight specific authors).

## Step 2: Gather RFC Data

1. Run the list command with relevant options:
   ```bash
   oak rfc list --json [--status STATUS]
   ```
   - For quick human-readable output, you can also run `oak rfc list --verbose`.
2. Parse the JSON to extract:
   - RFC number, title, author, date, status, tags
   - Aggregate statistics (`by_status`, `by_author`, `stale_drafts`, etc.)
3. If needed, run additional queries:
   - `oak rfc show {number}` for deep dives
   - `python` snippets using `RFCService.search_rfcs` for keyword/tag matches

## Step 3: Analyze & Interpret

1. Segment results based on user goals. Examples:
   - Drafts older than 60 days (stale work)
   - RFCs awaiting approval by specific teams
   - Recently implemented RFCs for release notes
   - Gaps in coverage (e.g., no “process” RFCs yet)
2. Look for trends in the statistics:
   - Status breakdown (draft vs review vs adopted)
   - Top contributors or areas with minimal ownership
   - Tags with high velocity or abandoned work
3. Identify actionable insights:
   - “3 drafts pending review for >60 days → recommend scheduling design review.”
   - “No RFCs tagged with ‘observability’ → potential documentation gap.”
   - “Architecture RFCs cluster around service X → cross-team alignment needed.”
   - "RFC-120 has been approved and should be marked adopted → offer to run `oak rfc adopt 120` after confirming with the user."
   - "RFC-098 is obsolete → offer to run `oak rfc abandon 98` if the user agrees."

## Step 4: Present Results to the User

1. Provide a structured summary:
   - Total count and status distribution
   - Key highlights (stale items, recently updated RFCs, missing coverage)
   - Table or bullet list of relevant RFCs (number, title, author, status, date)
2. If the user requested it, supply the raw JSON or filtered subsets (e.g., only drafts).
3. Offer recommended next steps (review sessions, follow-up with owners, archive stale drafts, create new RFCs for uncovered areas). When appropriate, ask if the user would like you to run lifecycle commands such as `oak rfc adopt <number>` or `oak rfc abandon <number>`.
4. Invite further questions or deeper dives (e.g., “Would you like a summary of RFC-123 in draft?”).

## Response Expectations

- Keep the user informed about filters applied and data sources used.
- Emphasize insights and actions over raw listings.
- Reference RFC numbers and titles directly so the user can follow up quickly.
- Maintain a collaborative tone—offer to investigate additional slices if the user needs more detail.
- Always ask for confirmation before executing any lifecycle commands (`oak rfc adopt`, `oak rfc abandon`).
