"""MCP server registration stages for init and upgrade pipelines.

MCP (Model Context Protocol) servers are a separate integration mechanism
from hooks. This module handles registering/updating MCP servers for
features that provide them (like codebase-intelligence).
"""

from open_agent_kit.pipeline.context import PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class ReconcileMcpServersStage(BaseStage):
    """Reconcile MCP server registrations for all agents.

    This stage ensures all configured agents have the required MCP server
    registrations for features that provide them. It's idempotent -
    existing registrations are updated, missing ones are created.

    Only agents with has_mcp=true in their manifest will have MCP
    servers registered.
    """

    name = "reconcile_mcp_servers"
    display_name = "Reconciling MCP servers"
    # Run after hooks are reconciled
    order = StageOrder.TRIGGER_AGENTS_CHANGED + 1
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents with MCP support.

        All features including codebase-intelligence are always enabled,
        so we just need to check if agents are selected.
        """
        return bool(context.selections.agents)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Reconcile MCP server registrations for all configured agents."""
        try:
            from open_agent_kit.features.codebase_intelligence.service import execute_hook

            result = execute_hook(
                "update_mcp_servers",
                context.project_root,
                agents=list(context.selections.agents),
            )

            if result.get("status") == "success":
                agents_result = result.get("agents", {})
                installed = [a for a, s in agents_result.items() if s == "installed"]
                skipped = [a for a, s in agents_result.items() if "skipped" in s or s == "skipped"]

                if installed:
                    return StageOutcome.success(
                        f"Registered MCP servers for: {', '.join(installed)}",
                        data={"installed": installed, "skipped": skipped},
                    )
                elif skipped:
                    return StageOutcome.success(
                        "MCP servers up to date (no agents with MCP support)",
                        data={"installed": [], "skipped": skipped},
                    )
                else:
                    return StageOutcome.success("MCP servers up to date")
            else:
                return StageOutcome.success(
                    "MCP server reconciliation skipped",
                    data={"message": result.get("message", "")},
                )
        except ImportError:
            # Codebase intelligence not available
            return StageOutcome.skipped("No MCP servers to reconcile")


def get_mcp_stages() -> list[BaseStage]:
    """Get all MCP-related stages."""
    return [
        ReconcileMcpServersStage(),
    ]
