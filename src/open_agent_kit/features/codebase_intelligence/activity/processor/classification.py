"""Session classification logic.

Two-stage classification:
1. LLM-based classification using activity patterns
2. Heuristic fallback when LLM unavailable
"""

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.prompts import (
        PromptTemplate,
        PromptTemplateConfig,
    )

logger = logging.getLogger(__name__)


def classify_session(
    activities: list[dict[str, Any]],
    tool_names: list[str],
    files_read: list[str],
    files_modified: list[str],
    files_created: list[str],
    has_errors: bool,
    duration_minutes: float,
    prompt_config: "PromptTemplateConfig",
    call_llm: Any,
) -> str:
    """Classify session type using LLM.

    Args:
        activities: Activity dictionaries.
        tool_names: List of tool names used.
        files_read: Files that were read.
        files_modified: Files that were modified.
        files_created: Files that were created.
        has_errors: Whether errors occurred.
        duration_minutes: Session duration.
        prompt_config: Prompt template configuration.
        call_llm: Function to call LLM.

    Returns:
        Classification from schema (e.g., exploration, debugging, implementation, refactoring).
    """
    from open_agent_kit.features.codebase_intelligence.activity.prompts import get_schema

    classify_template = prompt_config.get_template("classify")
    if not classify_template:
        # Fallback to heuristic if no classify template
        return classify_heuristic(tool_names, has_errors, files_modified, files_created)

    # Get schema for classification types
    schema = get_schema()
    valid_classifications = schema.get_classification_type_names()

    # Build tool summary
    tool_counts = Counter(tool_names)
    tool_summary = ", ".join(f"{tool}:{count}" for tool, count in tool_counts.most_common(5))

    # Format activities briefly
    activity_lines = []
    for i, act in enumerate(activities[:20], 1):  # Limit to first 20
        tool = act.get("tool_name", "Unknown")
        file_path = act.get("file_path", "")
        line = f"{i}. {tool}"
        if file_path:
            line += f" - {file_path}"
        activity_lines.append(line)
    activities_text = "\n".join(activity_lines)

    # Build classification prompt with schema-driven types
    prompt = classify_template.prompt
    prompt = prompt.replace("{{session_duration}}", f"{duration_minutes:.1f}")
    prompt = prompt.replace("{{tool_summary}}", tool_summary)
    prompt = prompt.replace("{{files_read_count}}", str(len(files_read)))
    prompt = prompt.replace("{{files_modified_count}}", str(len(files_modified)))
    prompt = prompt.replace("{{files_created_count}}", str(len(files_created)))
    prompt = prompt.replace("{{has_errors}}", "yes" if has_errors else "no")
    prompt = prompt.replace("{{activities}}", activities_text)
    # Inject schema-driven classification types
    prompt = prompt.replace(
        "{{classification_types}}", schema.format_classification_types_for_prompt()
    )

    # Call LLM
    result = call_llm(prompt)

    if result.get("success"):
        # Parse classification from response using schema-defined types
        raw = result.get("raw_response", "").strip().lower()
        for cls in valid_classifications:
            if cls in raw:
                return cls

    # Fallback to heuristic
    return classify_heuristic(tool_names, has_errors, files_modified, files_created)


def classify_heuristic(
    tool_names: list[str],
    has_errors: bool,
    files_modified: list[str],
    files_created: list[str],
) -> str:
    """Fallback heuristic classification.

    Args:
        tool_names: Tools used in session.
        has_errors: Whether errors occurred.
        files_modified: Modified files.
        files_created: Created files.

    Returns:
        Classification string.
    """
    if has_errors:
        return "debugging"

    edit_count = sum(1 for t in tool_names if t in ("Write", "Edit"))
    if files_created:
        return "implementation"
    if edit_count > len(tool_names) * 0.3:
        return "refactoring" if not files_created else "implementation"

    explore_count = sum(1 for t in tool_names if t in ("Read", "Grep", "Glob"))
    if explore_count > len(tool_names) * 0.5:
        return "exploration"

    return "exploration"


def select_template_by_classification(
    classification: str,
    prompt_config: "PromptTemplateConfig",
) -> "PromptTemplate":
    """Select extraction template based on LLM classification.

    Args:
        classification: Session classification.
        prompt_config: Prompt template configuration.

    Returns:
        Appropriate PromptTemplate.
    """
    # Map classifications to template names
    template_map = {
        "exploration": "exploration",
        "debugging": "debugging",
        "implementation": "implementation",
        "refactoring": "implementation",  # Use implementation for refactoring
    }

    template_name = template_map.get(classification, "extraction")
    template = prompt_config.get_template(template_name)

    if template:
        return template

    # Fallback to extraction
    return prompt_config.get_template("extraction") or prompt_config.templates[0]
