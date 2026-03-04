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
- background_phases.py: Background processing phases (error-isolated)
- scheduler.py: Timer-based background cycle scheduling
- power.py: Power state transition management
- async_api.py: Async wrappers for FastAPI routes
"""

from open_agent_kit.features.team.activity.processor.async_api import (
    process_prompt_batch_async,
    process_session_async,
    promote_agent_batch_async,
)
from open_agent_kit.features.team.activity.processor.core import (
    ActivityProcessor,
)
from open_agent_kit.features.team.activity.processor.models import (
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
