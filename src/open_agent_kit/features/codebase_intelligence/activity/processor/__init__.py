"""Activity processor package.

Decomposes the large processor.py into focused modules:
- core.py: Main ActivityProcessor class and orchestration
- models.py: Data models (ContextBudget, ProcessingResult)
- handlers.py: Batch handlers by source type
- classification.py: Session classification logic
- llm.py: LLM calls and context building
- observation.py: Observation storage logic
- titles.py: Session title generation
- summaries.py: Session summary generation
- indexing.py: Plan/memory indexing and rebuilds
"""

from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
    ActivityProcessor,
    process_prompt_batch_async,
    process_session_async,
    promote_agent_batch_async,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.models import (
    ContextBudget,
    ProcessingResult,
)

__all__ = [
    # Main class
    "ActivityProcessor",
    # Data models
    "ContextBudget",
    "ProcessingResult",
    # Async wrappers
    "process_session_async",
    "process_prompt_batch_async",
    "promote_agent_batch_async",
]
