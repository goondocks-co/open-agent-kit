"""Tests for update script generation and spawning."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_installer import (
    apply_staged_update,
    generate_update_script,
)
from open_agent_kit.utils.install_method import InstallMethod


class TestGenerateUpdateScript:
    """Test shell script generation."""

    def test_script_starts_with_shebang(self) -> None:
        script = generate_update_script(
            project_root=Path("/home/user/project"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert script.startswith("#!/bin/sh")

    def test_script_contains_cd_to_project(self) -> None:
        script = generate_update_script(
            project_root=Path("/home/user/project"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert 'cd "/home/user/project"' in script

    def test_script_contains_pip_install_for_pip_user(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "--user" in script
        assert "/tmp/oak_ci-1.3.0.whl" in script

    def test_script_contains_uv_for_uv_tool(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/oak_ci-1.3.0.whl",
            install_method=InstallMethod.UV_TOOL,
            daemon_type="team",
        )
        assert "uv tool install" in script
        assert "--force" in script

    def test_script_uses_homebrew_pip(self) -> None:
        with patch("open_agent_kit.utils.install_method.sys") as mock_sys:
            mock_sys.executable = "/opt/homebrew/Cellar/oak-ci/1.5.6/libexec/bin/python3.13"
            script = generate_update_script(
                project_root=Path("/tmp/proj"),
                wheel_path="/tmp/oak_ci-1.3.0.whl",
                install_method=InstallMethod.HOMEBREW,
                daemon_type="team",
            )
        assert "libexec/bin/pip" in script

    def test_script_runs_oak_upgrade(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "oak upgrade --force" in script

    def test_team_daemon_restarts_with_team_start(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "oak team start" in script

    def test_swarm_daemon_restarts_with_swarm_start(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="swarm",
        )
        assert "oak swarm start" in script

    def test_script_writes_error_on_failure(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        assert "update-error.json" in script

    def test_script_attempts_restart_on_failure(self) -> None:
        script = generate_update_script(
            project_root=Path("/tmp/proj"),
            wheel_path="/tmp/w.whl",
            install_method=InstallMethod.PIP_USER,
            daemon_type="team",
        )
        # The error handler should still try to restart
        assert script.count("oak team start") >= 2  # normal + fallback

    def test_raises_for_editable(self) -> None:
        with pytest.raises(ValueError, match="editable"):
            generate_update_script(
                project_root=Path("/tmp/proj"),
                wheel_path="/tmp/w.whl",
                install_method=InstallMethod.EDITABLE,
                daemon_type="team",
            )


class TestApplyStagedUpdate:
    """Test the full apply flow: generate script, spawn, exit."""

    def test_spawns_detached_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        # Create staged update
        from open_agent_kit.utils.global_config import ensure_global_dir, write_staged_update

        ensure_global_dir()
        wheel = tmp_path / "staging" / "oak_ci-1.3.0.whl"
        wheel.write_bytes(b"fake")
        write_staged_update(
            {
                "schema_version": 1,
                "version": "1.3.0",
                "wheel_path": str(wheel),
                "channel": "stable",
                "downloaded_at": "2026-03-10T00:00:00Z",
                "sha256": "abc",
            }
        )

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_installer.detect_install_method",
                return_value=InstallMethod.PIP_USER,
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_installer.subprocess.Popen"
            ) as mock_popen,
        ):
            result = apply_staged_update(
                project_root=tmp_path,
                daemon_type="team",
            )

        assert result is True
        mock_popen.assert_called_once()
        # Verify it's using /bin/sh
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "/bin/sh"

    def test_returns_false_when_no_staged_update(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        result = apply_staged_update(project_root=tmp_path, daemon_type="team")
        assert result is False
