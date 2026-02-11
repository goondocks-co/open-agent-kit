#!/usr/bin/env python3
"""Build generated assets for all Oak skills.

Discovers and runs all skill asset generators across features.
Generators are Python scripts named `generate_*.py` inside skill directories
or feature `scripts/` directories.

Usage:
    python scripts/build_skill_assets.py           # Generate all skill assets
    python scripts/build_skill_assets.py --check   # Verify all assets are in sync (CI mode)

This is called by:
    make skill-build     # Generate all skill assets
    make skill-check     # Verify all skill assets are in sync (for CI)

Pattern:
    To add a generator for a new skill, create a `generate_*.py` script in the
    skill directory or in the feature's `scripts/` directory. The script must
    accept a `--check` flag for CI verification.

    Examples:
        src/open_agent_kit/features/my_feature/skills/my-skill/generate_foo.py
        src/open_agent_kit/features/my_feature/scripts/generate_bar.py
"""

import subprocess
import sys
from pathlib import Path

FEATURES_DIR = Path(__file__).parent.parent / "src" / "open_agent_kit" / "features"


def discover_generators() -> list[Path]:
    """Find all generate_*.py scripts inside skill or feature scripts directories."""
    generators = sorted(
        list(FEATURES_DIR.glob("*/skills/*/generate_*.py"))
        + list(FEATURES_DIR.glob("*/scripts/generate_*.py"))
    )
    return generators


def main() -> int:
    check_mode = "--check" in sys.argv

    generators = discover_generators()

    if not generators:
        print("No skill asset generators found.")
        return 0

    print(f"Found {len(generators)} skill asset generator(s):")
    for gen in generators:
        # Show path relative to project root
        rel = gen.relative_to(FEATURES_DIR.parent.parent.parent)
        print(f"  - {rel}")
    print()

    errors = []
    for gen in generators:
        rel = gen.relative_to(FEATURES_DIR.parent.parent.parent)
        action = "Checking" if check_mode else "Building"
        print(f"{action}: {rel}")

        cmd = [sys.executable, str(gen)]
        if check_mode:
            cmd.append("--check")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                print(f"  {line}")

        if result.returncode != 0:
            errors.append(rel)
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n"):
                    print(f"  ERROR: {line}")
        print()

    if errors:
        print(f"FAILED: {len(errors)} generator(s) reported errors:")
        for e in errors:
            print(f"  - {e}")
        if check_mode:
            print("\nRun 'make skill-build' to regenerate skill assets.")
        return 1
    else:
        action = "verified" if check_mode else "built"
        print(f"All {len(generators)} skill asset generator(s) {action} successfully.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
