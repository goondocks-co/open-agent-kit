"""Prompt batch operations for activity store.

Functions for creating, retrieving, and managing prompt batches and plans.

Submodules:
- crud: Create, read, update, and lifecycle management
- queries: Read-only queries for listing, filtering, and aggregating
- recovery: Recovery of stuck, orphaned, and stale batches
- plan_embedding: ChromaDB embedding tracking for plans
- plan_graph: Cross-session plan source linking
"""

from open_agent_kit.features.codebase_intelligence.activity.store.batches.crud import (
    create_prompt_batch,
    end_prompt_batch,
    get_active_prompt_batch,
    get_latest_prompt_batch,
    get_prompt_batch,
    get_session_plan_batch,
    mark_prompt_batch_processed,
    reactivate_prompt_batch,
    update_prompt_batch_response,
    update_prompt_batch_source_type,
)
from open_agent_kit.features.codebase_intelligence.activity.store.batches.plan_embedding import (
    count_embedded_plans,
    count_unembedded_plans,
    get_embedded_plan_chromadb_ids,
    get_unembedded_plans,
    mark_all_plans_unembedded,
    mark_plan_embedded,
    mark_plan_unembedded,
)
from open_agent_kit.features.codebase_intelligence.activity.store.batches.plan_graph import (
    auto_link_batch_to_plan,
    find_source_plan_batch,
    get_plan_implementations,
    link_batch_to_source_plan,
)
from open_agent_kit.features.codebase_intelligence.activity.store.batches.queries import (
    get_batch_ids_for_reprocessing,
    get_bulk_plan_counts,
    get_plans,
    get_prompt_batch_activities,
    get_prompt_batch_stats,
    get_session_prompt_batches,
    get_unprocessed_prompt_batches,
)
from open_agent_kit.features.codebase_intelligence.activity.store.batches.recovery import (
    queue_batches_for_reprocessing,
    recover_orphaned_activities,
    recover_stuck_batches,
)

__all__ = [
    # crud
    "create_prompt_batch",
    "end_prompt_batch",
    "get_active_prompt_batch",
    "get_latest_prompt_batch",
    "get_prompt_batch",
    "get_session_plan_batch",
    "mark_prompt_batch_processed",
    "reactivate_prompt_batch",
    "update_prompt_batch_response",
    "update_prompt_batch_source_type",
    # queries
    "get_batch_ids_for_reprocessing",
    "get_bulk_plan_counts",
    "get_plans",
    "get_prompt_batch_activities",
    "get_prompt_batch_stats",
    "get_session_prompt_batches",
    "get_unprocessed_prompt_batches",
    # recovery
    "queue_batches_for_reprocessing",
    "recover_orphaned_activities",
    "recover_stuck_batches",
    # plan_embedding
    "count_embedded_plans",
    "count_unembedded_plans",
    "get_embedded_plan_chromadb_ids",
    "get_unembedded_plans",
    "mark_all_plans_unembedded",
    "mark_plan_embedded",
    "mark_plan_unembedded",
    # plan_graph
    "auto_link_batch_to_plan",
    "find_source_plan_batch",
    "get_plan_implementations",
    "link_batch_to_source_plan",
]
