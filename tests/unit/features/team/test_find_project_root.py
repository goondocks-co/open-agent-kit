"""Tests for _find_project_root() in ci/hooks.py.

Verifies that the hook handler correctly resolves the project root even
when the working directory has been changed by the AI agent (e.g.,
``cd daemon/ui && npm run build``).
"""

from pathlib import Path

from open_agent_kit.commands.ci.hooks import _find_project_root
from open_agent_kit.config.paths import GIT_DIR, OAK_DIR


class TestFindProjectRoot:
    """Tests for _find_project_root."""

    def test_finds_oak_dir_at_cwd(self, tmp_path, monkeypatch):
        """When cwd IS the project root, returns it directly."""
        (tmp_path / OAK_DIR).mkdir()
        monkeypatch.chdir(tmp_path)

        assert _find_project_root() == tmp_path

    def test_finds_oak_dir_from_subdirectory(self, tmp_path, monkeypatch):
        """When cwd is a nested subdirectory, walks up to find .oak/."""
        (tmp_path / OAK_DIR).mkdir()
        sub = tmp_path / "src" / "features" / "daemon" / "ui"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)

        assert _find_project_root() == tmp_path

    def test_finds_oak_dir_from_deep_subdirectory(self, tmp_path, monkeypatch):
        """Deeply nested cwd still resolves to the .oak/ root."""
        (tmp_path / OAK_DIR).mkdir()
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)

        assert _find_project_root() == tmp_path

    def test_prefers_nearest_oak_dir(self, tmp_path, monkeypatch):
        """If a subdirectory also has .oak/, prefers the closest one going up."""
        # Outer project
        (tmp_path / OAK_DIR).mkdir()
        # Inner nested project
        inner = tmp_path / "nested" / "project"
        inner.mkdir(parents=True)
        (inner / OAK_DIR).mkdir()

        sub = inner / "src"
        sub.mkdir()
        monkeypatch.chdir(sub)

        # Should find the inner project's .oak, not the outer one
        assert _find_project_root() == inner

    def test_falls_back_to_git_when_no_oak(self, tmp_path, monkeypatch):
        """When there's no .oak/ but there is .git/, uses .git/ root."""
        (tmp_path / GIT_DIR).mkdir()
        sub = tmp_path / "src" / "lib"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)

        assert _find_project_root() == tmp_path

    def test_oak_preferred_over_git(self, tmp_path, monkeypatch):
        """When both .oak/ and .git/ exist, .oak/ takes priority."""
        (tmp_path / OAK_DIR).mkdir()
        (tmp_path / GIT_DIR).mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        monkeypatch.chdir(sub)

        assert _find_project_root() == tmp_path

    def test_falls_back_to_cwd_when_no_markers(self, tmp_path, monkeypatch):
        """When no .oak/ or .git/ exists, returns cwd as fallback."""
        sub = tmp_path / "isolated" / "dir"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)

        assert _find_project_root() == sub

    def test_ignores_oak_files_only_dirs(self, tmp_path, monkeypatch):
        """A file named .oak (not a directory) should not match."""
        (tmp_path / OAK_DIR).touch()  # file, not directory
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        monkeypatch.chdir(sub)

        # .oak is a file not a dir, so should fall back to .git
        assert _find_project_root() == tmp_path

    def test_returns_path_type(self, tmp_path, monkeypatch):
        """Return value is always a Path."""
        monkeypatch.chdir(tmp_path)
        result = _find_project_root()
        assert isinstance(result, Path)
