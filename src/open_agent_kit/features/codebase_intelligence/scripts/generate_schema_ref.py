#!/usr/bin/env python3
"""Generate skill reference files from the actual CI database schema.

This script reads the canonical schema DDL from schema.py and generates
the skill's references/schema.md and updates SKILL.md's core tables overview.

Usage:
    python generate_schema_ref.py              # Generate in place
    python generate_schema_ref.py --check      # Check if files are in sync (CI mode)

This is called by:
    make skill-build     # Generate skill reference files
    make skill-check     # Verify files are in sync (used in CI)
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path so we can import the schema
project_root = Path(__file__).resolve().parents[5]  # up to src/../
sys.path.insert(0, str(project_root / "src"))

from open_agent_kit.features.codebase_intelligence.activity.store.schema import (  # noqa: E402
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

CI_FEATURE_DIR = Path(__file__).resolve().parents[1]  # up to codebase_intelligence/
SKILL_DIR = CI_FEATURE_DIR / "skills" / "codebase-intelligence"
SCHEMA_REF_PATH = SKILL_DIR / "references" / "schema.md"
SKILL_MD_PATH = SKILL_DIR / "SKILL.md"

# Analysis agent system prompt (also contains generated core tables)
ANALYSIS_SYSTEM_PROMPT_PATH = (
    CI_FEATURE_DIR / "agents" / "definitions" / "analysis" / "prompts" / "system.md"
)


def extract_tables(schema_sql: str) -> dict[str, dict]:
    """Extract table definitions from schema SQL.

    Returns dict of table_name -> {type, sql, columns, comment_block}.
    """
    tables: dict[str, dict] = {}

    # Match CREATE TABLE blocks (regular and virtual)
    # Captures the full CREATE statement including closing );
    regular_pattern = re.compile(
        r"(-- [^\n]*\n)*"  # Optional comment lines before
        r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\);",
        re.DOTALL,
    )
    virtual_pattern = re.compile(
        r"(-- [^\n]*\n)*" r"CREATE VIRTUAL TABLE IF NOT EXISTS (\w+)\s+USING\s+(\w+)\((.*?)\);",
        re.DOTALL,
    )

    for match in regular_pattern.finditer(schema_sql):
        comments = match.group(1) or ""
        name = match.group(2)
        body = match.group(3)
        if name == "schema_version":
            continue
        tables[name] = {
            "type": "table",
            "body": body.strip(),
            "comments": comments.strip(),
            "full_match": match.group(0),
        }

    for match in virtual_pattern.finditer(schema_sql):
        comments = match.group(1) or ""
        name = match.group(2)
        engine = match.group(3)
        body = match.group(4)
        tables[name] = {
            "type": "virtual",
            "engine": engine,
            "body": body.strip(),
            "comments": comments.strip(),
            "full_match": match.group(0),
        }

    return tables


def extract_indexes(schema_sql: str) -> dict[str, list[str]]:
    """Extract indexes grouped by the table they reference."""
    indexes: dict[str, list[str]] = {}
    for match in re.finditer(
        r"CREATE INDEX IF NOT EXISTS (\w+)\s+ON\s+(\w+)\(([^)]+)\)", schema_sql
    ):
        idx_name = match.group(1)
        table_name = match.group(2)
        if table_name not in indexes:
            indexes[table_name] = []
        indexes[table_name].append(idx_name)
    return indexes


def parse_columns(body: str) -> list[dict]:
    """Parse column definitions from a CREATE TABLE body."""
    columns = []
    for line in body.split("\n"):
        line = line.strip().rstrip(",")
        if (
            not line
            or line.startswith("--")
            or line.startswith("FOREIGN KEY")
            or line.startswith("UNIQUE")
        ):
            continue
        # Extract column name, type, and inline comment
        col_match = re.match(r"(\w+)\s+(\w+(?:\s+\w+)*?)(?:\s+--\s*(.*))?$", line)
        if col_match:
            columns.append(
                {
                    "name": col_match.group(1),
                    "type_and_constraints": col_match.group(2),
                    "comment": col_match.group(3) or "",
                }
            )
    return columns


def get_table_description(name: str) -> str:
    """Return a human-readable description for each table."""
    descriptions = {
        "sessions": "Tracks coding sessions from launch to exit.",
        "prompt_batches": "Activities between user prompts — the unit of processing.",
        "activities": "Raw tool executions logged during sessions.",
        "memory_observations": "Source of truth for extracted memories. ChromaDB is a search index over this data.",
        "agent_runs": "CI agent executions via claude-code-sdk.",
        "agent_schedules": "Cron scheduling runtime state. Database is the sole source of truth.",
        "session_link_events": "Analytics for user-driven session linking.",
        "session_relationships": "Many-to-many semantic relationships between sessions.",
        "resolution_events": "Cross-machine resolution propagation. Each resolution action (resolve, supersede, reactivate) is recorded as a first-class, machine-owned entity that flows through the backup pipeline.",
        "activities_fts": "Full-text search index over activities (FTS5).",
        "memories_fts": "Full-text search index over memory observations (FTS5).",
    }
    return descriptions.get(name, "")


def generate_schema_md(tables: dict, indexes: dict) -> str:
    """Generate the references/schema.md content."""
    lines = [
        "# Oak CI Database Schema Reference",
        "",
        "Complete DDL for the Oak CI SQLite database at `.oak/ci/activities.db`.",
        "",
        f"Current schema version: **{SCHEMA_VERSION}**",
        "",
    ]

    # Regular tables first, then virtual tables
    regular = {k: v for k, v in tables.items() if v["type"] == "table"}
    virtual = {k: v for k, v in tables.items() if v["type"] == "virtual"}

    for name, info in regular.items():
        desc = get_table_description(name)
        lines.append(f"## {name}")
        lines.append("")
        if desc:
            lines.append(desc)
            lines.append("")
        lines.append("```sql")
        lines.append(f"CREATE TABLE IF NOT EXISTS {name} (")
        lines.append(f"    {info['body']}")
        lines.append(");")
        lines.append("```")
        lines.append("")
        if name in indexes:
            idx_list = ", ".join(f"`{i}`" for i in indexes[name])
            lines.append(f"**Key indexes:** {idx_list}")
            lines.append("")

    if virtual:
        lines.append("## Full-Text Search Tables (FTS5)")
        lines.append("")

        for name, info in virtual.items():
            desc = get_table_description(name)
            lines.append(f"### {name}")
            lines.append("")
            if desc:
                lines.append(desc)
                lines.append("")
            lines.append("```sql")
            lines.append(f"CREATE VIRTUAL TABLE IF NOT EXISTS {name} USING {info['engine']}(")
            lines.append(f"    {info['body']}")
            lines.append(");")
            lines.append("```")
            lines.append("")

        lines.extend(
            [
                "FTS5 tables are kept in sync via triggers. Query with `MATCH` syntax:",
                "",
                "```sql",
                "-- Simple term search",
                "WHERE activities_fts MATCH 'authentication'",
                "",
                "-- Phrase search",
                "WHERE memories_fts MATCH '\"database connection\"'",
                "",
                "-- Boolean operators",
                "WHERE activities_fts MATCH 'auth AND token'",
                "WHERE memories_fts MATCH 'auth OR authentication'",
                "",
                "-- Column-specific search",
                "WHERE activities_fts MATCH 'file_path:auth.py'",
                "```",
                "",
            ]
        )

    # Related files section
    lines.extend(
        [
            "## Related Files on Disk",
            "",
            "| Resource | Path |",
            "|----------|------|",
            "| SQLite database | `.oak/ci/activities.db` |",
            "| ChromaDB vector index | `.oak/ci/chroma/` |",
            "| Daemon logs | `.oak/ci/daemon.log` |",
            "| Hook logs | `.oak/ci/hooks.log` |",
            "| User backups (git-tracked) | `oak/history/*.sql` |",
            "| Agent configs (git-tracked) | `oak/agents/` |",
            "| Shared port file (git-tracked) | `oak/daemon.port` |",
            "",
        ]
    )

    return "\n".join(lines)


def generate_core_tables_section(tables: dict) -> str:
    """Generate the core tables overview for SKILL.md."""
    # Only regular tables, not FTS virtual tables
    regular = {k: v for k, v in tables.items() if v["type"] == "table"}

    # Build a concise overview table
    # Map table name to key columns (manually curated for readability)
    table_info = {
        "sessions": "`id`, `agent`, `status`, `summary`, `title`, `started_at`, `created_at_epoch`",
        "prompt_batches": "`session_id`, `user_prompt`, `classification`, `response_summary`",
        "activities": "`session_id`, `tool_name`, `file_path`, `success`, `error_message`",
        "memory_observations": "`observation`, `memory_type`, `status`, `context`, `tags`, `importance`, `session_origin_type`",
        "agent_runs": "`agent_name`, `task`, `status`, `result`, `cost_usd`, `turns_used`",
        "agent_schedules": "`task_name`, `cron_expression`, `enabled`, `last_run_at`, `next_run_at`",
        "session_link_events": "`session_id`, `event_type`, `old_parent_id`, `new_parent_id`",
        "session_relationships": "`session_a_id`, `session_b_id`, `relationship_type`, `similarity_score`",
        "resolution_events": "`observation_id`, `action`, `source_machine_id`, `applied`, `content_hash`",
    }

    # Build table descriptions
    table_purposes = {
        "sessions": "Coding sessions (launch to exit)",
        "prompt_batches": "User prompts within sessions",
        "activities": "Raw tool executions",
        "memory_observations": "Extracted memories/learnings",
        "agent_runs": "CI agent executions",
        "agent_schedules": "Cron scheduling state",
        "session_link_events": "Session linking analytics",
        "session_relationships": "Semantic session relationships",
        "resolution_events": "Cross-machine resolution propagation",
    }

    lines = []
    lines.append("| Table | Purpose | Key Columns |")
    lines.append("|-------|---------|-------------|")
    for name in regular:
        purpose = table_purposes.get(name, "")
        cols = table_info.get(name, "")
        lines.append(f"| `{name}` | {purpose} | {cols} |")

    return "\n".join(lines)


def _replace_between_markers(content: str, new_table: str, source_name: str) -> str:
    """Replace content between generation markers in a file's text.

    Args:
        content: Full file text.
        new_table: New table content to insert between markers.
        source_name: File name for error messages.

    Returns:
        Updated file text.

    Raises:
        ValueError: If markers are missing.
    """
    begin_marker = "<!-- BEGIN GENERATED CORE TABLES -->"
    end_marker = "<!-- END GENERATED CORE TABLES -->"

    if begin_marker in content and end_marker in content:
        pattern = re.compile(
            re.escape(begin_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        replacement = f"{begin_marker}\n{new_table}\n{end_marker}"
        return pattern.sub(replacement, content)
    else:
        raise ValueError(
            f"{source_name} is missing generation markers. "
            f"Add '{begin_marker}' and '{end_marker}' around the core tables section."
        )


def update_skill_md(tables: dict) -> str:
    """Update SKILL.md's core tables overview section."""
    skill_md = SKILL_MD_PATH.read_text()
    new_table = generate_core_tables_section(tables)
    return _replace_between_markers(skill_md, new_table, "SKILL.md")


def update_analysis_system_prompt(tables: dict) -> str | None:
    """Update the analysis agent's system.md core tables overview section.

    Returns:
        Updated file text, or None if the file doesn't exist.
    """
    if not ANALYSIS_SYSTEM_PROMPT_PATH.exists():
        return None
    content = ANALYSIS_SYSTEM_PROMPT_PATH.read_text()
    new_table = generate_core_tables_section(tables)
    return _replace_between_markers(content, new_table, "analysis/prompts/system.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate skill schema reference files")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files are in sync (exit 1 if stale)",
    )
    args = parser.parse_args()

    tables = extract_tables(SCHEMA_SQL)
    indexes = extract_indexes(SCHEMA_SQL)

    # Generate schema.md
    new_schema_md = generate_schema_md(tables, indexes)

    # Generate updated SKILL.md
    new_skill_md = update_skill_md(tables)

    # Generate updated analysis agent system prompt (if it exists)
    new_analysis_prompt = update_analysis_system_prompt(tables)

    if args.check:
        # Check mode: compare with existing files
        errors = []

        current_schema = SCHEMA_REF_PATH.read_text() if SCHEMA_REF_PATH.exists() else ""
        if current_schema != new_schema_md:
            errors.append(
                "references/schema.md is out of sync with schema.py. "
                "Run 'make skill-build' to regenerate."
            )

        current_skill = SKILL_MD_PATH.read_text()
        if current_skill != new_skill_md:
            errors.append(
                "SKILL.md core tables section is out of sync with schema.py. "
                "Run 'make skill-build' to regenerate."
            )

        if new_analysis_prompt is not None:
            current_analysis = ANALYSIS_SYSTEM_PROMPT_PATH.read_text()
            if current_analysis != new_analysis_prompt:
                errors.append(
                    "analysis/prompts/system.md core tables section is out of sync "
                    "with schema.py. Run 'make skill-build' to regenerate."
                )

        if errors:
            for e in errors:
                print(f"Error: {e}", file=sys.stderr)
            return 1
        else:
            print("Skill reference files are in sync with schema.py.")
            return 0
    else:
        # Generate mode: write files
        SCHEMA_REF_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_REF_PATH.write_text(new_schema_md)
        print(f"Generated {SCHEMA_REF_PATH.relative_to(project_root)}")

        SKILL_MD_PATH.write_text(new_skill_md)
        print(f"Updated {SKILL_MD_PATH.relative_to(project_root)}")

        if new_analysis_prompt is not None:
            ANALYSIS_SYSTEM_PROMPT_PATH.write_text(new_analysis_prompt)
            print(f"Updated {ANALYSIS_SYSTEM_PROMPT_PATH.relative_to(project_root)}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
