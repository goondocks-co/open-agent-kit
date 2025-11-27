"""Skill installation and cleanup stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.models import StageResultRegistry
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class CleanupAgentSkillsStage(BaseStage):
    """Remove skills for agents that were deselected.

    When an agent is removed from the configuration, this stage cleans up
    the skills that were installed in that agent's skills directory.
    """

    name = StageResultRegistry.CLEANUP_AGENT_SKILLS
    display_name = "Removing skills for deselected agents"
    order = StageOrder.REMOVE_AGENT_COMMANDS - 1  # Run before command removal
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = StageResultRegistry.RECONCILE_SKILLS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were removed."""
        return bool(context.selections.agents_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Clean up skills for removed agents."""
        skill_service = self._get_skill_service(context)

        result = skill_service.cleanup_skills_for_removed_agents(
            list(context.selections.agents_removed)
        )

        agents_cleaned = result.get("agents_cleaned", [])
        skills_removed = result.get("skills_removed", [])
        errors = result.get("errors", [])

        if errors:
            return StageOutcome.success(
                f"Cleaned up skills for {len(agents_cleaned)} agent(s) with warnings",
                data={
                    "agents_cleaned": agents_cleaned,
                    "skills_removed": skills_removed,
                    "errors": errors,
                },
            )

        if skills_removed:
            return StageOutcome.success(
                f"Removed {len(skills_removed)} skill(s) for {len(agents_cleaned)} agent(s)",
                data={
                    "agents_cleaned": agents_cleaned,
                    "skills_removed": skills_removed,
                    "errors": errors,
                },
            )

        return StageOutcome.success(
            "No skills to clean up",
            data={
                "agents_cleaned": agents_cleaned,
                "skills_removed": skills_removed,
                "errors": errors,
            },
        )


class ReconcileSkillsStage(BaseStage):
    """Reconcile skills to ensure all configured agents have required skills.

    This stage ensures reality matches desired state:
    - All skills-capable agents have skills for all configured features
    - Missing skills are created, existing skills are preserved
    - Obsolete skills (no longer in any feature) are removed

    This is idempotent - running multiple times has no additional effect.
    """

    name = StageResultRegistry.RECONCILE_SKILLS
    display_name = "Reconciling skills"
    order = StageOrder.INSTALL_SKILLS
    # Runs for all flows - reconciles actual state to match config
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = StageResultRegistry.CLEANUP_AGENT_SKILLS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents configured (all features are always enabled)."""
        return bool(context.selections.agents)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Reconcile skills for all skills-capable agents."""
        skill_service = self._get_skill_service(context)

        # Check if any configured agent supports skills
        if not skill_service._has_skills_capable_agent():
            return StageOutcome.skipped("No skills-capable agents configured")

        # First, remove obsolete skills (skills no longer in any feature)
        obsolete_removed = skill_service.remove_obsolete_skills()
        skills_removed = obsolete_removed.get("skills_removed", [])

        # Refresh skills - ensures all skills-capable agents have all skills
        # This is idempotent - only creates missing skills
        result = skill_service.refresh_skills()
        skills_refreshed = result.get("skills_refreshed", [])
        installed_skills = skill_service.list_installed_skills()

        if skills_refreshed or skills_removed:
            return StageOutcome.success(
                f"Reconciled skills ({len(skills_refreshed)} added, "
                f"{len(skills_removed)} removed, {len(installed_skills)} total)",
                data={
                    "skills_added": skills_refreshed,
                    "skills_removed": skills_removed,
                    "total_skills": len(installed_skills),
                    "agents": result.get("agents", []),
                },
            )
        else:
            return StageOutcome.success(
                f"Skills up to date ({len(installed_skills)} installed)",
                data={
                    "skills_added": [],
                    "skills_removed": [],
                    "total_skills": len(installed_skills),
                    "agents": [],
                },
            )


def get_skill_stages() -> list[BaseStage]:
    """Get all skill stages."""
    return [
        CleanupAgentSkillsStage(),
        ReconcileSkillsStage(),
    ]
