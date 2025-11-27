"""Tests for AgentService - agent instruction file management."""

from pathlib import Path

import pytest

from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService


class TestGetAgentInstructionFile:
    """Tests for get_agent_instruction_file method."""

    def test_returns_correct_path_for_claude(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Claude."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("claude")
        assert path == initialized_project / ".claude" / "CLAUDE.md"

    def test_returns_correct_path_for_copilot(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Copilot."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("copilot")
        assert path == initialized_project / ".github" / "copilot-instructions.md"

    def test_returns_correct_path_for_cursor(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Cursor."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("cursor")
        assert path == initialized_project / "AGENTS.md"

    def test_returns_correct_path_for_codex(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Codex."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("codex")
        assert path == initialized_project / "AGENTS.md"

    def test_returns_correct_path_for_gemini(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Gemini."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("gemini")
        assert path == initialized_project / "GEMINI.md"

    def test_returns_correct_path_for_windsurf(self, initialized_project: Path) -> None:
        """Test get_agent_instruction_file returns correct path for Windsurf."""
        service = AgentService(initialized_project)
        path = service.get_agent_instruction_file("windsurf")
        assert path == initialized_project / ".windsurf" / "rules" / "rules.md"

    def test_handles_unknown_agent_type(self, initialized_project: Path) -> None:
        """Test that unknown agent type raises ValueError."""
        service = AgentService(initialized_project)
        with pytest.raises(ValueError, match="Unknown agent type: unknown"):
            service.get_agent_instruction_file("unknown")

    def test_case_insensitive_agent_type(self, initialized_project: Path) -> None:
        """Test that agent type is case-insensitive."""
        service = AgentService(initialized_project)
        path_upper = service.get_agent_instruction_file("CLAUDE")
        assert path_upper == initialized_project / ".claude" / "CLAUDE.md"
        path_mixed = service.get_agent_instruction_file("ClAuDe")
        assert path_mixed == initialized_project / ".claude" / "CLAUDE.md"


class TestDetectExistingAgentInstructions:
    """Tests for detect_existing_agent_instructions method."""

    def test_detects_existing_copilot_instructions(self, initialized_project: Path) -> None:
        """Test detection of existing copilot instructions."""
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        test_content = "# Team Instructions\n\nOur conventions..."
        copilot_file.write_text(test_content, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert "copilot" in existing
        assert existing["copilot"]["exists"] is True
        assert existing["copilot"]["content"] == test_content
        assert len(existing["copilot"]["content"]) > 0
        assert existing["copilot"]["has_constitution_ref"] is False
        assert existing["copilot"]["path"] == copilot_file

    def test_returns_info_for_nonexistent_file(self, initialized_project: Path) -> None:
        """Test detection when instruction file doesn't exist."""
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert "claude" in existing
        assert existing["claude"]["exists"] is False
        assert existing["claude"]["content"] is None
        assert existing["claude"]["has_constitution_ref"] is False
        assert existing["claude"]["path"] == initialized_project / ".claude" / "CLAUDE.md"

    def test_detects_constitution_reference(self, initialized_project: Path) -> None:
        """Test detection when file has constitution reference."""
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        content_with_ref = "# Team Instructions\n\nOur conventions...\n\n## Project Constitution\n\nSee [oak/constitution.md](../oak/constitution.md)\n"
        copilot_file.write_text(content_with_ref, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert existing["copilot"]["exists"] is True
        assert existing["copilot"]["has_constitution_ref"] is True

    def test_handles_shared_files(self, initialized_project: Path) -> None:
        """Test that cursor and codex both detect the same AGENTS.md file."""
        agents_file = initialized_project / "AGENTS.md"
        agents_file.write_text("# AI Assistant Instructions\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["cursor", "codex"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert "cursor" in existing
        assert "codex" in existing
        assert existing["cursor"]["exists"] is True
        assert existing["codex"]["exists"] is True
        assert existing["cursor"]["path"] == agents_file
        assert existing["codex"]["path"] == agents_file

    def test_handles_multiple_agents(self, initialized_project: Path) -> None:
        """Test detection with multiple agents configured."""
        claude_dir = initialized_project / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_file = claude_dir / "CLAUDE.md"
        claude_file.write_text("# Claude Instructions\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        copilot_file.write_text("# Copilot Instructions\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude", "copilot"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert len(existing) == 2
        assert existing["claude"]["exists"] is True
        assert existing["copilot"]["exists"] is True

    def test_empty_result_when_no_agents_configured(self, initialized_project: Path) -> None:
        """Test that detection returns empty dict when no agents configured."""
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert existing == {}

    def test_handles_unreadable_file(self, initialized_project: Path) -> None:
        """Test handling of existing but unreadable file."""
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        copilot_file.write_text("# Instructions\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        existing = service.detect_existing_agent_instructions()
        assert "copilot" in existing


class TestHasConstitutionReference:
    """Tests for _has_constitution_reference method."""

    def test_returns_true_for_project_constitution_header(self, temp_project_dir: Path) -> None:
        """Test detection of '## Project Constitution' header."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text(
            "\n# Instructions\n\nSome content here.\n\n## Project Constitution\n\nReference to constitution.\n",
            encoding="utf-8",
        )
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True

    def test_returns_true_for_constitution_file_path(self, temp_project_dir: Path) -> None:
        """Test detection of 'oak/constitution.md' reference."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text(
            "\n# Instructions\n\nSee [constitution](oak/constitution.md) for details.\n",
            encoding="utf-8",
        )
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True

    def test_returns_true_for_dot_oak_constitution_path(self, temp_project_dir: Path) -> None:
        """Test detection of '.oak/constitution.md' reference."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text(
            "\nSee [.oak/constitution.md](.oak/constitution.md)\n", encoding="utf-8"
        )
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True

    def test_returns_false_for_no_reference(self, temp_project_dir: Path) -> None:
        """Test that file without reference returns False."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text(
            "\n# Instructions\n\nRegular content without constitution reference.\n",
            encoding="utf-8",
        )
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is False

    def test_returns_false_for_nonexistent_file(self, temp_project_dir: Path) -> None:
        """Test that non-existent file returns False."""
        nonexistent_file = temp_project_dir / "does-not-exist.md"
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(nonexistent_file) is False

    def test_case_insensitive_check(self, temp_project_dir: Path) -> None:
        """Test that detection is case-insensitive."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text(
            "\n## project constitution\n\\OAK/CONSTITUTION.MD reference.\n", encoding="utf-8"
        )
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True

    def test_detects_various_header_levels(self, temp_project_dir: Path) -> None:
        """Test detection of constitution header at different levels."""
        test_cases = [
            "# Project Constitution",
            "## Project Constitution",
            "### Project Constitution",
        ]
        service = AgentService(temp_project_dir)
        for header in test_cases:
            test_file = temp_project_dir / f"test_{header.count('#')}.md"
            test_file.write_text(f"{header}\n\nContent", encoding="utf-8")
            assert service._has_constitution_reference(test_file) is True

    def test_detects_see_constitution_reference(self, temp_project_dir: Path) -> None:
        """Test detection of 'See constitution:' text."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text("See constitution: ../oak/constitution.md", encoding="utf-8")
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True

    def test_detects_markdown_link_reference(self, temp_project_dir: Path) -> None:
        """Test detection of [constitution] or [Constitution] markdown link."""
        test_file = temp_project_dir / "test.md"
        test_file.write_text("Read the [constitution](../oak/constitution.md)", encoding="utf-8")
        service = AgentService(temp_project_dir)
        assert service._has_constitution_reference(test_file) is True


class TestUpdateAgentInstructionsFromConstitution:
    """Tests for update_agent_instructions_from_constitution method."""

    def test_updates_existing_file_without_reference(self, initialized_project: Path) -> None:
        """Test appending reference to existing file without constitution reference."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        original_content = "# Team Instructions\n\nOur conventions..."
        copilot_file.write_text(original_content, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(
            constitution_file, mode="additive"
        )
        assert "copilot" in results["updated"]
        assert "copilot" not in results["created"]
        assert "copilot" not in results["skipped"]
        assert len(results["backed_up"]) == 1
        updated_content = copilot_file.read_text(encoding="utf-8")
        assert original_content in updated_content
        assert "## Project Constitution" in updated_content
        assert "oak/constitution.md" in updated_content

    def test_creates_backup_before_updating(self, initialized_project: Path) -> None:
        """Test that backup file is created before updating."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        original_content = "# Original Content\n"
        copilot_file.write_text(original_content, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        backup_file = copilot_file.with_suffix(copilot_file.suffix + ".backup")
        assert backup_file.exists()
        assert backup_file.read_text(encoding="utf-8") == original_content
        assert str(backup_file) in results["backed_up"]

    def test_skips_file_that_already_has_reference(self, initialized_project: Path) -> None:
        """Test idempotency - skips file that already has reference."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        content_with_ref = "# Instructions\n\n## Project Constitution\nAlready has reference to oak/constitution.md\n"
        copilot_file.write_text(content_with_ref, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        assert "copilot" in results["skipped"]
        assert "copilot" not in results["updated"]
        assert "copilot" not in results["created"]
        assert len(results["backed_up"]) == 0
        assert copilot_file.read_text(encoding="utf-8") == content_with_ref

    def test_creates_new_file_if_doesnt_exist(self, initialized_project: Path) -> None:
        """Test creating new instruction file when none exists."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        assert "claude" in results["created"]
        assert "claude" not in results["updated"]
        assert "claude" not in results["skipped"]
        claude_file = initialized_project / ".claude" / "CLAUDE.md"
        assert claude_file.exists()
        content = claude_file.read_text(encoding="utf-8")
        assert "## Project Constitution" in content
        assert "oak/constitution.md" in content

    def test_handles_shared_files(self, initialized_project: Path) -> None:
        """Test updating shared files (cursor and codex use AGENTS.md)."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["cursor", "codex"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        assert "cursor" in results["created"]
        assert "codex" in results["created"]
        agents_file = initialized_project / "AGENTS.md"
        assert agents_file.exists()
        content = agents_file.read_text(encoding="utf-8")
        assert "## Project Constitution" in content

    def test_returns_error_if_constitution_not_found(self, initialized_project: Path) -> None:
        """Test error handling when constitution file doesn't exist."""
        nonexistent_constitution = initialized_project / "oak" / "nonexistent.md"
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(nonexistent_constitution)
        assert len(results["errors"]) > 0
        assert "not found" in results["errors"][0].lower()

    def test_skip_mode_preserves_existing_files(self, initialized_project: Path) -> None:
        """Test skip mode doesn't modify existing files."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        original_content = "# Team Instructions\n"
        copilot_file.write_text(original_content, encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["copilot"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(
            constitution_file, mode="skip"
        )
        assert "copilot" in results["skipped"]
        assert copilot_file.read_text(encoding="utf-8") == original_content

    def test_skip_mode_creates_new_files(self, initialized_project: Path) -> None:
        """Test skip mode still creates new files when they don't exist."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(
            constitution_file, mode="skip"
        )
        assert "claude" in results["created"]
        claude_file = initialized_project / ".claude" / "CLAUDE.md"
        assert claude_file.exists()


class TestAppendConstitutionReference:
    """Tests for _append_constitution_reference method."""

    def test_appends_reference_to_existing_file(self, temp_project_dir: Path) -> None:
        """Test appending constitution reference to existing file."""
        test_file = temp_project_dir / "instructions.md"
        original_content = "# Original Instructions\n\nSome content here."
        test_file.write_text(original_content, encoding="utf-8")
        constitution_file = temp_project_dir / "oak" / "constitution.md"
        constitution_file.parent.mkdir(parents=True, exist_ok=True)
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        backup_path = service._append_constitution_reference(test_file, constitution_file)
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == original_content
        updated_content = test_file.read_text(encoding="utf-8")
        assert original_content in updated_content
        assert "## Project Constitution" in updated_content
        assert "oak/constitution.md" in updated_content

    def test_creates_backup_with_backup_extension(self, temp_project_dir: Path) -> None:
        """Test backup file has .backup extension."""
        test_file = temp_project_dir / "instructions.md"
        test_file.write_text("Original content", encoding="utf-8")
        constitution_file = temp_project_dir / "constitution.md"
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        backup_path = service._append_constitution_reference(test_file, constitution_file)
        assert backup_path == test_file.with_suffix(".md.backup")
        assert backup_path.name == "instructions.md.backup"

    def test_preserves_original_content(self, temp_project_dir: Path) -> None:
        """Test that original content is preserved in updated file."""
        test_file = temp_project_dir / "instructions.md"
        original_content = "# Team Instructions\n\n## Coding Standards\n\nFollow PEP 8.\n\n## Review Process\n\nAll PRs need approval.\n"
        test_file.write_text(original_content, encoding="utf-8")
        constitution_file = temp_project_dir / "constitution.md"
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        service._append_constitution_reference(test_file, constitution_file)
        updated_content = test_file.read_text(encoding="utf-8")
        assert "# Team Instructions" in updated_content
        assert "## Coding Standards" in updated_content
        assert "Follow PEP 8." in updated_content
        assert "## Review Process" in updated_content

    def test_calculates_correct_relative_path(self, temp_project_dir: Path) -> None:
        """Test that relative path is calculated correctly."""
        instruction_dir = temp_project_dir / ".github"
        instruction_dir.mkdir(parents=True, exist_ok=True)
        test_file = instruction_dir / "copilot-instructions.md"
        test_file.write_text("# Instructions\n", encoding="utf-8")
        constitution_file = temp_project_dir / "oak" / "constitution.md"
        constitution_file.parent.mkdir(parents=True, exist_ok=True)
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        service._append_constitution_reference(test_file, constitution_file)
        updated_content = test_file.read_text(encoding="utf-8")
        assert "../oak/constitution.md" in updated_content


class TestCreateAgentInstructionFile:
    """Tests for _create_agent_instruction_file method."""

    def test_creates_new_file_with_constitution_reference(self, temp_project_dir: Path) -> None:
        """Test creating new instruction file with constitution reference."""
        file_path = temp_project_dir / ".claude" / "CLAUDE.md"
        constitution_file = temp_project_dir / "oak" / "constitution.md"
        constitution_file.parent.mkdir(parents=True, exist_ok=True)
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        service._create_agent_instruction_file(file_path, constitution_file, ["claude"])
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        assert "# Claude Code Instructions" in content
        assert "## Project Constitution" in content
        assert "../oak/constitution.md" in content

    def test_handles_single_agent(self, temp_project_dir: Path) -> None:
        """Test creating file for single agent."""
        file_path = temp_project_dir / ".claude" / "CLAUDE.md"
        constitution_file = temp_project_dir / "constitution.md"
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        service._create_agent_instruction_file(file_path, constitution_file, ["claude"])
        content = file_path.read_text(encoding="utf-8")
        assert "Claude Code" in content
        assert "This file contains instructions for Claude Code" in content

    def test_handles_multiple_agents(self, temp_project_dir: Path) -> None:
        """Test creating shared file for multiple agents."""
        file_path = temp_project_dir / "AGENTS.md"
        constitution_file = temp_project_dir / "constitution.md"
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        service = AgentService(temp_project_dir)
        service._create_agent_instruction_file(file_path, constitution_file, ["cursor", "codex"])
        content = file_path.read_text(encoding="utf-8")
        assert "# AI Assistant Instructions" in content
        assert "Cursor" in content or "Codex" in content
        assert "## Project Constitution" in content

    def test_creates_parent_directories(self, temp_project_dir: Path) -> None:
        """Test that parent directories are created if needed."""
        file_path = temp_project_dir / ".windsurf" / "rules" / "rules.md"
        constitution_file = temp_project_dir / "constitution.md"
        constitution_file.write_text("# Constitution\n", encoding="utf-8")
        assert not file_path.parent.exists()
        service = AgentService(temp_project_dir)
        service._create_agent_instruction_file(file_path, constitution_file, ["windsurf"])
        assert file_path.parent.exists()
        assert file_path.exists()


class TestIntegration:
    """Integration tests for agent instruction management."""

    def test_full_workflow_new_project(self, initialized_project: Path) -> None:
        """Test complete workflow for new project."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude", "copilot", "cursor"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        assert set(results["created"]) == {"claude", "copilot", "cursor"}
        assert len(results["updated"]) == 0
        assert len(results["skipped"]) == 0
        assert len(results["errors"]) == 0
        assert (initialized_project / ".claude" / "CLAUDE.md").exists()
        assert (initialized_project / ".github" / "copilot-instructions.md").exists()
        assert (initialized_project / "AGENTS.md").exists()

    def test_full_workflow_existing_project(self, initialized_project: Path) -> None:
        """Test workflow for project with existing instruction files."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        claude_dir = initialized_project / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_file = claude_dir / "CLAUDE.md"
        claude_file.write_text("# Existing Claude instructions\n", encoding="utf-8")
        copilot_dir = initialized_project / ".github"
        copilot_dir.mkdir(parents=True, exist_ok=True)
        copilot_file = copilot_dir / "copilot-instructions.md"
        copilot_file.write_text(
            "# Copilot\n\n## Project Constitution\nAlready has reference\n", encoding="utf-8"
        )
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude", "copilot", "cursor"])
        service = AgentService(initialized_project)
        results = service.update_agent_instructions_from_constitution(constitution_file)
        assert "claude" in results["updated"]
        assert "copilot" in results["skipped"]
        assert "cursor" in results["created"]

    def test_idempotency(self, initialized_project: Path) -> None:
        """Test running update multiple times is idempotent."""
        constitution_dir = initialized_project / "oak"
        constitution_dir.mkdir(parents=True, exist_ok=True)
        constitution_file = constitution_dir / "constitution.md"
        constitution_file.write_text("# Project Constitution\n", encoding="utf-8")
        config_service = ConfigService(initialized_project)
        config_service.create_default_config(agents=["claude"])
        service = AgentService(initialized_project)
        results1 = service.update_agent_instructions_from_constitution(constitution_file)
        assert "claude" in results1["created"]
        results2 = service.update_agent_instructions_from_constitution(constitution_file)
        assert "claude" in results2["skipped"]
        results3 = service.update_agent_instructions_from_constitution(constitution_file)
        assert "claude" in results3["skipped"]
        backup_file = initialized_project / ".claude" / "CLAUDE.md.backup"
        assert not backup_file.exists()
