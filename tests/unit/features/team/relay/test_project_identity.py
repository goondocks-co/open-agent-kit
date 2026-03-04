"""Tests for project identity derivation.

Tests cover:
- get_project_identity() with mocked git subprocess returning a remote URL
- get_project_identity() fallback when git fails (no remote)
- _normalize_git_remote() strips .git and trailing slashes
- ProjectIdentity.full_id format is "slug:hash"
"""

import hashlib
import subprocess
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.constants.team import (
    TEAM_PROJECT_ID_SEPARATOR,
    TEAM_REMOTE_HASH_LENGTH,
)
from open_agent_kit.features.team.relay.identity import (
    ProjectIdentity,
    _normalize_git_remote,
    get_project_identity,
)

SAMPLE_REMOTE_URL = "https://github.com/example/my-project.git"
SAMPLE_REMOTE_NORMALIZED = "https://github.com/example/my-project"


# =============================================================================
# _normalize_git_remote Tests
# =============================================================================


class TestNormalizeGitRemote:
    """Test git remote URL normalization."""

    def test_strips_trailing_dot_git(self):
        """Test that .git suffix is removed."""
        result = _normalize_git_remote("https://github.com/org/repo.git")
        assert result == "https://github.com/org/repo"

    def test_strips_trailing_slash(self):
        """Test that trailing slashes are removed."""
        result = _normalize_git_remote("https://github.com/org/repo/")
        assert result == "https://github.com/org/repo"

    def test_strips_both_slash_and_dot_git(self):
        """Test that trailing slash before .git is handled."""
        result = _normalize_git_remote("https://github.com/org/repo.git/")
        # Trailing slash stripped first, then .git
        assert result == "https://github.com/org/repo"

    def test_no_modification_needed(self):
        """Test URL that needs no normalization."""
        result = _normalize_git_remote("https://github.com/org/repo")
        assert result == "https://github.com/org/repo"

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = _normalize_git_remote("  https://github.com/org/repo  ")
        assert result == "https://github.com/org/repo"

    def test_ssh_url(self):
        """Test SSH-style git remote URL normalization."""
        result = _normalize_git_remote("git@github.com:org/repo.git")
        assert result == "git@github.com:org/repo"


# =============================================================================
# get_project_identity Tests
# =============================================================================


class TestGetProjectIdentity:
    """Test project identity derivation."""

    def test_with_git_remote(self, tmp_path):
        """Test identity derivation with a valid git remote."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        expected_hash = hashlib.sha256(SAMPLE_REMOTE_NORMALIZED.encode()).hexdigest()[
            :TEAM_REMOTE_HASH_LENGTH
        ]

        mock_result = subprocess.CompletedProcess(
            args=["git", "remote", "get-url", "origin"],
            returncode=0,
            stdout=SAMPLE_REMOTE_URL + "\n",
            stderr="",
        )

        with patch("subprocess.run", return_value=mock_result):
            identity = get_project_identity(project_dir)

        assert identity.slug == "my-project"
        assert identity.remote_hash == expected_hash
        assert identity.full_id == f"my-project{TEAM_PROJECT_ID_SEPARATOR}{expected_hash}"

    def test_fallback_when_git_fails(self, tmp_path):
        """Test identity derivation falls back to path hash when git fails."""
        project_dir = tmp_path / "fallback-project"
        project_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=["git", "remote", "get-url", "origin"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        with patch("subprocess.run", return_value=mock_result):
            identity = get_project_identity(project_dir)

        expected_hash = hashlib.sha256(str(project_dir.resolve()).encode()).hexdigest()[
            :TEAM_REMOTE_HASH_LENGTH
        ]

        assert identity.slug == "fallback-project"
        assert identity.remote_hash == expected_hash
        assert identity.full_id == f"fallback-project{TEAM_PROJECT_ID_SEPARATOR}{expected_hash}"

    def test_fallback_when_subprocess_times_out(self, tmp_path):
        """Test identity derivation falls back when subprocess times out."""
        project_dir = tmp_path / "timeout-project"
        project_dir.mkdir()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5)):
            identity = get_project_identity(project_dir)

        expected_hash = hashlib.sha256(str(project_dir.resolve()).encode()).hexdigest()[
            :TEAM_REMOTE_HASH_LENGTH
        ]

        assert identity.slug == "timeout-project"
        assert identity.remote_hash == expected_hash

    def test_full_id_format(self, tmp_path):
        """Test that full_id uses the expected separator."""
        project_dir = tmp_path / "test-slug"
        project_dir.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=["git", "remote", "get-url", "origin"],
            returncode=0,
            stdout="https://github.com/org/test-slug.git\n",
            stderr="",
        )

        with patch("subprocess.run", return_value=mock_result):
            identity = get_project_identity(project_dir)

        assert TEAM_PROJECT_ID_SEPARATOR in identity.full_id
        parts = identity.full_id.split(TEAM_PROJECT_ID_SEPARATOR)
        assert len(parts) == 2
        assert parts[0] == "test-slug"
        assert len(parts[1]) == TEAM_REMOTE_HASH_LENGTH

    def test_project_identity_is_frozen(self):
        """Test that ProjectIdentity is immutable (frozen dataclass)."""
        import dataclasses

        identity = ProjectIdentity(slug="test", remote_hash="abcd1234", full_id="test:abcd1234")

        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.slug = "modified"  # type: ignore[misc]
