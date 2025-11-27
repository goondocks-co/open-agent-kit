"""Data models for activity processing.

These dataclasses are used throughout the processor modules.
"""

from dataclasses import dataclass


@dataclass
class ContextBudget:
    """Dynamic context budget based on model's context window.

    Allocates the model's context tokens across different parts of the prompt.
    """

    context_tokens: int = 4096  # Original context token limit
    max_user_prompt_chars: int = 3000
    max_activities: int = 30
    max_activity_summary_chars: int = 150
    max_oak_context_chars: int = 2000

    @classmethod
    def from_context_tokens(cls, context_tokens: int) -> "ContextBudget":
        """Calculate budget based on model's context token limit.

        Args:
            context_tokens: Model's max context tokens.

        Returns:
            ContextBudget scaled to the model.
        """
        # Reserve ~30% for model response, allocate rest to input
        available_tokens = int(context_tokens * 0.7)

        # Rough estimate: 1 token ≈ 3-4 chars for mixed content
        available_chars = available_tokens * 3

        # Allocation percentages:
        # - User prompt: 25%
        # - Activities: 50%
        # - Oak context: 15%
        # - Template overhead: 10%

        if context_tokens >= 32000:
            # Large context models (qwen2.5, llama3.1, gpt-4o)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(10000, int(available_chars * 0.25)),
                max_activities=50,
                max_activity_summary_chars=200,
                max_oak_context_chars=min(5000, int(available_chars * 0.15)),
            )
        elif context_tokens >= 8000:
            # Medium context models (llama3.2, mistral, gpt-3.5)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(5000, int(available_chars * 0.25)),
                max_activities=30,
                max_activity_summary_chars=150,
                max_oak_context_chars=min(2000, int(available_chars * 0.15)),
            )
        else:
            # Small context models (phi3:mini, 4K context)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(2000, int(available_chars * 0.25)),
                max_activities=15,
                max_activity_summary_chars=100,
                max_oak_context_chars=min(1000, int(available_chars * 0.15)),
            )


@dataclass
class ProcessingResult:
    """Result of processing a batch of activities."""

    session_id: str
    activities_processed: int
    observations_extracted: int
    success: bool
    error: str | None = None
    duration_ms: int = 0
    classification: str | None = None
    prompt_batch_id: int | None = None  # If processing a specific prompt batch
