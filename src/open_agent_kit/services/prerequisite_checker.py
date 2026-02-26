"""Prerequisite checker for validating feature requirements."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PrerequisiteChecker:
    """Checks if external prerequisites for a feature are satisfied.

    Validates that required services and commands are available on the system
    before a feature is installed.
    """

    def check(self, prerequisites: list) -> dict[str, Any]:
        """Check if prerequisites for a feature are satisfied.

        Args:
            prerequisites: List of Prerequisite instances from manifest

        Returns:
            Dictionary with check results:
            {
                'satisfied': True/False,
                'missing': [{'name': 'ollama', 'instructions': '...'}],
                'warnings': ['Ollama not found, will use FastEmbed fallback']
            }
        """
        import shutil
        import subprocess

        from open_agent_kit.utils import print_info, print_success, print_warning

        result: dict[str, Any] = {
            "satisfied": True,
            "missing": [],
            "warnings": [],
        }

        for prereq in prerequisites:
            name = prereq.name
            prereq_type = prereq.type
            check_cmd = prereq.check_command
            required = prereq.required
            install_url = prereq.install_url
            install_instructions = prereq.install_instructions

            print_info(f"Checking prerequisite: {name}...")

            is_available = False

            if prereq_type == "service" and check_cmd:
                cmd_name = check_cmd.split()[0]
                if shutil.which(cmd_name):
                    try:
                        proc = subprocess.run(
                            check_cmd.split(),
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )
                        is_available = proc.returncode == 0
                    except (subprocess.TimeoutExpired, OSError):
                        is_available = False

            elif prereq_type == "command" and check_cmd:
                cmd_name = check_cmd.split()[0]
                is_available = shutil.which(cmd_name) is not None

            if is_available:
                print_success(f"  {name} is available")
            else:
                if required:
                    result["satisfied"] = False
                    result["missing"].append(
                        {
                            "name": name,
                            "install_url": install_url,
                            "instructions": install_instructions,
                        }
                    )
                    print_warning(f"  {name} is not available (required)")
                else:
                    result["warnings"].append(
                        f"{name} not found - feature will use fallback if available"
                    )
                    print_warning(f"  {name} not found (optional, will use fallback)")

        return result
