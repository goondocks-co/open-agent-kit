"""Activity tracking and processing for Codebase Intelligence.

This module implements the activity-first observation pattern:
1. Capture tool executions liberally during sessions (organized by prompt batches)
2. Store in SQLite with FTS5 for fast search
3. Process asynchronously with LLM to extract observations

Architecture inspired by claude-mem: https://docs.claude-mem.ai/architecture/overview

Key concepts:
- Session: A Claude Code session from launch to exit
- PromptBatch: Activities from a single user prompt - the unit of processing
- Activity: A single tool execution event
"""

from open_agent_kit.features.codebase_intelligence.activity.processor import (
    ActivityProcessor,
    ProcessingResult,
    process_prompt_batch_async,
    process_session_async,
)
from open_agent_kit.features.codebase_intelligence.activity.prompts import (
    PromptTemplate,
    PromptTemplateConfig,
    render_prompt,
)
from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity,
    ActivityStore,
    PromptBatch,
    Session,
)

__all__ = [
    # Store
    "Activity",
    "ActivityStore",
    "PromptBatch",
    "Session",
    # Processor
    "ActivityProcessor",
    "ProcessingResult",
    "process_prompt_batch_async",
    "process_session_async",
    # Prompts
    "PromptTemplate",
    "PromptTemplateConfig",
    "render_prompt",
]
