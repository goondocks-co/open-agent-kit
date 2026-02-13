"""Removal stages for oak remove pipeline."""

import shutil
from pathlib import Path

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.models import StageResultRegistry
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class ValidateRemovalStage(BaseStage):
    """Validate that oak is initialized before removal."""

    name = "validate_removal"
    display_name = "Validating environment"
    order = StageOrder.VALIDATE_REMOVAL
    applicable_flows = {FlowType.REMOVE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (oak not initialized)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Validate oak is initialized."""
        oak_dir = context.oak_dir

        if not oak_dir.exists():
            return StageOutcome.failed(
                "open-agent-kit is not initialized in this project",
                error="Nothing to remove",
            )

        return StageOutcome.success("Environment validated")


class PlanRemovalStage(BaseStage):
    """Plan what needs to be removed using state tracking."""

    name = "plan_removal"
    display_name = "Planning removal"
    order = StageOrder.PLAN_REMOVAL
    applicable_flows = {FlowType.REMOVE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (no state to plan from)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Analyze what needs to be removed."""
        from open_agent_kit.services.skill_service import SkillService
        from open_agent_kit.services.state_service import StateService

        state_service = StateService(context.project_root)
        managed_assets = state_service.get_managed_assets()

        # Categorize files
        files_to_remove: list[tuple[str, str]] = []  # (path, description)
        files_modified_by_user: list[tuple[str, str]] = []  # (path, reason)
        files_to_inform_user: list[tuple[str, str]] = []  # (path, marker)
        directories_to_check: list[str] = []

        # Process created files - check if unchanged
        for created_file in managed_assets.created_files:
            file_path = context.project_root / created_file.path
            if file_path.exists():
                if state_service.is_file_unchanged(file_path):
                    files_to_remove.append((created_file.path, "Created by oak (unchanged)"))
                else:
                    files_modified_by_user.append(
                        (created_file.path, "File was modified after oak created it")
                    )

        # Process modified files - inform user to manually clean up
        for modified_file in managed_assets.modified_files:
            file_path = context.project_root / modified_file.path
            if file_path.exists():
                files_to_inform_user.append((modified_file.path, modified_file.marker))

        # Collect directories for potential cleanup
        for dir_path_str in managed_assets.directories:
            dir_path = context.project_root / dir_path_str
            if dir_path.exists():
                directories_to_check.append(dir_path_str)

        # Check for user content
        user_content_dir = context.project_root / "oak"
        has_user_content = user_content_dir.exists() and any(user_content_dir.iterdir())

        # Check for installed skills
        installed_skills: list[str] = []
        try:
            skill_service = SkillService(context.project_root)
            installed_skills = skill_service.list_installed_skills()
        except (OSError, ValueError):
            pass

        plan = {
            "files_to_remove": files_to_remove,
            "files_modified_by_user": files_modified_by_user,
            "files_to_inform_user": files_to_inform_user,
            "directories_to_check": directories_to_check,
            "installed_skills": installed_skills,
            "has_user_content": has_user_content,
        }

        return StageOutcome.success(
            f"Planned removal of {len(files_to_remove)} file(s)",
            data=plan,
        )


class TriggerPreRemoveHooksStage(BaseStage):
    """Trigger pre-remove hooks before removal."""

    name = "trigger_pre_remove_hooks"
    display_name = "Running pre-remove hooks"
    order = StageOrder.TRIGGER_PRE_REMOVE_HOOKS
    applicable_flows = {FlowType.REMOVE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (no feature service without .oak)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger pre-remove hooks."""
        feature_service = self._get_feature_service(context)

        try:
            feature_service.trigger_pre_remove_hooks()
            return StageOutcome.success("Pre-remove hooks completed")
        except Exception as e:
            # Hook failures are not fatal
            return StageOutcome.success(
                "Pre-remove hooks completed with warnings",
                data={"error": str(e)},
            )


class CleanupCiArtifactsStage(BaseStage):
    """Clean up CI artifacts (hooks, MCP) even if feature wasn't fully installed.

    This stage handles cleanup of codebase-intelligence artifacts that may have
    been created even when the feature failed to install (e.g., pip packages failed).
    It runs unconditionally during removal and delegates to the existing CI service
    cleanup methods when available.
    """

    name = "cleanup_ci_artifacts"
    display_name = "Cleaning up CI artifacts"
    order = StageOrder.CLEANUP_CI_ARTIFACTS
    applicable_flows = {FlowType.REMOVE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run during removal to clean up any leftover CI artifacts."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Clean up CI hooks and MCP server registrations using existing CI service."""
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(context.project_root)

        try:
            available_agents = agent_service.list_available_agents()
        except (OSError, ValueError):
            available_agents = ["claude", "cursor", "gemini", "vscode-copilot", "codex"]

        # Use CI service cleanup if packages are available
        try:
            from open_agent_kit.features.codebase_intelligence.service import (
                CodebaseIntelligenceService,
            )

            ci_service = CodebaseIntelligenceService(context.project_root)

            # Remove hooks using existing CI service method
            hook_results = ci_service._remove_agent_hooks(available_agents)
            cleaned_hooks = [a for a, s in hook_results.items() if s == "removed"]

            # Remove MCP servers using existing CI service method
            mcp_results = ci_service.remove_mcp_server(available_agents)
            cleaned_mcp = [a for a, s in mcp_results.items() if s == "removed"]

            if cleaned_hooks or cleaned_mcp:
                return StageOutcome.success(
                    f"Cleaned up CI artifacts (hooks: {len(cleaned_hooks)}, mcp: {len(cleaned_mcp)})",
                    data={"cleaned_hooks": cleaned_hooks, "cleaned_mcp": cleaned_mcp},
                )

        except ImportError:
            # CI packages not installed - skip (artifacts likely don't exist)
            pass

        return StageOutcome.success("No CI artifacts to clean up")


class RemoveSkillsStage(BaseStage):
    """Remove all installed skills."""

    name = "remove_skills"
    display_name = "Removing skills"
    order = StageOrder.REMOVE_SKILLS
    applicable_flows = {FlowType.REMOVE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_skills"

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (depends on plan_removal)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove all installed skills."""
        plan = context.get_result(StageResultRegistry.PLAN_REMOVAL, {})
        installed_skills = plan.get("installed_skills", [])

        if not installed_skills:
            return StageOutcome.skipped("No skills to remove")

        skill_service = self._get_skill_service(context)

        skills_removed = 0
        errors: list[str] = []

        for skill_name in installed_skills:
            try:
                result = skill_service.remove_skill(skill_name)
                if result.get("removed_from"):
                    skills_removed += 1
            except Exception as e:
                errors.append(f"{skill_name}: {e}")

        if errors:
            return StageOutcome.success(
                f"Removed {skills_removed} skill(s) with warnings",
                data={"skills_removed": skills_removed, "errors": errors},
            )

        return StageOutcome.success(
            f"Removed {skills_removed} skill(s)",
            data={"skills_removed": skills_removed},
        )


class RemoveCreatedFilesStage(BaseStage):
    """Remove files created by oak that are unchanged."""

    name = "remove_created_files"
    display_name = "Removing created files"
    order = StageOrder.REMOVE_CREATED_FILES
    applicable_flows = {FlowType.REMOVE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_features"  # Files created during feature installation

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (depends on plan_removal)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove created files."""
        plan = context.get_result(StageResultRegistry.PLAN_REMOVAL, {})
        files_to_remove = plan.get("files_to_remove", [])

        if not files_to_remove:
            return StageOutcome.skipped("No files to remove")

        removed_count = 0
        failed: list[str] = []

        for file_path_str, _ in files_to_remove:
            file_path = context.project_root / file_path_str
            try:
                if file_path.exists():
                    file_path.unlink()
                    removed_count += 1
            except PermissionError:
                failed.append(f"{file_path_str}: Permission denied")
            except Exception as e:
                failed.append(f"{file_path_str}: {e}")

        if failed:
            for error in failed:
                context.add_warning(self.name, error)

        return StageOutcome.success(
            f"Removed {removed_count} file(s)",
            data={"removed_count": removed_count, "failed": failed},
        )


class RemoveAgentSettingsStage(BaseStage):
    """Remove OAK-managed settings from agent config files."""

    name = "remove_agent_settings"
    display_name = "Removing agent settings"
    order = StageOrder.REMOVE_AGENT_SETTINGS_CLEANUP
    applicable_flows = {FlowType.REMOVE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_agent_settings"

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run for removal."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove OAK settings from all agent config files."""
        from open_agent_kit.services.agent_service import AgentService
        from open_agent_kit.services.agent_settings_service import AgentSettingsService

        agent_service = AgentService(context.project_root)
        settings_service = AgentSettingsService(context.project_root)

        # Get all available agents
        try:
            available_agents = agent_service.list_available_agents()
        except Exception as e:
            return StageOutcome.success(
                "No agents to clean up",
                data={"error": str(e)},
            )

        if not available_agents:
            return StageOutcome.skipped("No agents configured")

        # Remove settings for all agents
        results = settings_service.remove_settings_for_agents(available_agents)
        cleaned_count = sum(1 for v in results.values() if v)

        if cleaned_count > 0:
            return StageOutcome.success(
                f"Cleaned up settings for {cleaned_count} agent(s)",
                data={"results": results},
            )

        return StageOutcome.success(
            "No agent settings to clean up",
            data={"results": results},
        )


class CleanupDirectoriesStage(BaseStage):
    """Clean up empty directories created by oak."""

    name = "cleanup_directories"
    display_name = "Cleaning up directories"
    order = StageOrder.CLEANUP_DIRECTORIES
    applicable_flows = {FlowType.REMOVE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run to clean up agent directories."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Clean up empty directories including agent directories."""
        plan = context.get_result(StageResultRegistry.PLAN_REMOVAL, {})
        directories = plan.get("directories_to_check", [])

        # Collect all directories to check
        all_dirs: set[Path] = {context.project_root / d for d in directories}

        # Also check agent directories (commands, skills, and parent folders)
        all_dirs.update(self._get_agent_directories(context))

        if not all_dirs:
            return StageOutcome.skipped("No directories to check")

        # Sort by depth (deepest first) for proper cleanup
        dir_paths = sorted(all_dirs, key=lambda p: len(p.parts), reverse=True)

        removed = []
        for dir_path in dir_paths:
            if dir_path.exists() and dir_path.is_dir():
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        removed.append(str(dir_path.relative_to(context.project_root)))
                except OSError:
                    pass

        return StageOutcome.success(
            f"Cleaned up {len(removed)} empty directory(ies)",
            data={"removed": removed},
        )

    def _get_agent_directories(self, context: PipelineContext) -> set[Path]:
        """Get all agent directories that should be checked for cleanup.

        Returns directories for all known agents including:
        - Skills directories (e.g., .claude/skills/)
        - Commands directories (e.g., .claude/commands/)
        - Parent agent folders (e.g., .claude/)

        Args:
            context: Pipeline context

        Returns:
            Set of directory paths to check
        """
        from open_agent_kit.services.agent_service import AgentService

        dirs: set[Path] = set()

        try:
            agent_service = AgentService(context.project_root)
            available_agents = agent_service.list_available_agents()

            for agent_name in available_agents:
                try:
                    manifest = agent_service.get_agent_manifest(agent_name)

                    # Get agent's root folder (e.g., .claude, .codex)
                    agent_folder = context.project_root / manifest.installation.folder
                    dirs.add(agent_folder)

                    # Get commands directory
                    commands_dir = agent_service.get_agent_commands_dir(agent_name)
                    dirs.add(commands_dir)

                    # Get skills directory if agent supports skills
                    if manifest.capabilities.has_skills:
                        skills_dir = agent_folder / manifest.capabilities.skills_directory
                        dirs.add(skills_dir)

                except (OSError, ValueError):
                    # Skip agents that fail to load
                    pass

        except (OSError, ValueError):
            # If agent service fails, just return empty set
            pass

        return dirs


class RemoveOakDirStage(BaseStage):
    """Remove the .oak configuration directory."""

    name = "remove_oak_dir"
    display_name = "Removing oak configuration"
    order = StageOrder.REMOVE_OAK_DIR
    applicable_flows = {FlowType.REMOVE}
    is_critical = False  # Not critical in cleanup_only mode
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "create_oak_dir"

    def _should_run(self, context: PipelineContext) -> bool:
        """Skip if cleanup_only mode (no .oak to remove)."""
        return not context.options.get("cleanup_only", False)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove the .oak directory."""
        oak_dir = context.oak_dir

        try:
            if oak_dir.exists():
                shutil.rmtree(oak_dir)
                return StageOutcome.success(
                    f"Removed {OAK_DIR}/",
                    data={"removed": True},
                )
            return StageOutcome.success(
                f"{OAK_DIR}/ already removed",
                data={"removed": False},
            )
        except Exception as e:
            return StageOutcome.failed(
                f"Failed to remove {OAK_DIR}/",
                error=str(e),
            )


def get_removal_stages() -> list[BaseStage]:
    """Get all removal stages."""
    return [
        ValidateRemovalStage(),
        PlanRemovalStage(),
        TriggerPreRemoveHooksStage(),
        CleanupCiArtifactsStage(),
        RemoveSkillsStage(),
        RemoveCreatedFilesStage(),
        RemoveAgentSettingsStage(),
        CleanupDirectoriesStage(),
        RemoveOakDirStage(),
    ]
