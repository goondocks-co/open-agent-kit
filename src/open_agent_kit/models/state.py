"""Internal state models for open-agent-kit.

This module contains models for internal state that should not be
user-facing or editable. State is stored separately from config.yaml.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class CreatedFile(BaseModel):
    """A file created by oak.

    Tracks files we create from scratch so we can safely remove them.
    The hash allows us to detect if the user modified the file.
    """

    path: str = Field(description="Relative path from project root")
    hash: str = Field(description="SHA256 hash of file contents when created")
    created_at: str = Field(description="ISO timestamp when file was created")


class ModifiedFile(BaseModel):
    """A file modified by oak.

    Tracks files that existed before oak but we appended to.
    We don't auto-remove these - just inform the user.
    """

    path: str = Field(description="Relative path from project root")
    modification_type: str = Field(
        default="appended",
        description="Type of modification (appended, replaced)",
    )
    marker: str = Field(
        default="## Project Constitution",
        description="Marker text that identifies our additions",
    )


class ManagedAssets(BaseModel):
    """Assets managed by oak installation.

    Tracks what oak created vs modified so we can:
    - Safely remove files we created (if unchanged)
    - Inform users about files we modified
    - Clean up empty directories
    """

    directories: list[str] = Field(
        default_factory=list,
        description="Directories created by oak (relative paths)",
    )
    created_files: list[CreatedFile] = Field(
        default_factory=list,
        description="Files created by oak",
    )
    modified_files: list[ModifiedFile] = Field(
        default_factory=list,
        description="Files modified by oak (existed before)",
    )


class OakState(BaseModel):
    """Internal state for OAK installation.

    This tracks internal state like applied migrations that users
    should not need to see or edit. Stored in .oak/state.yaml.
    """

    migrations: list[str] = Field(
        default_factory=list,
        description="Completed migration IDs",
    )
    managed_assets: ManagedAssets = Field(
        default_factory=ManagedAssets,
        description="Assets created or modified by oak",
    )

    @classmethod
    def load(cls, state_path: Path) -> "OakState":
        """Load state from file.

        Args:
            state_path: Path to state.yaml file

        Returns:
            OakState instance (empty if file doesn't exist)
        """
        if not state_path.exists():
            return cls()

        with open(state_path) as f:
            data = yaml.safe_load(f)
            if not data:
                return cls()
            return cls(**data)

    def save(self, state_path: Path) -> None:
        """Save state to file.

        Args:
            state_path: Path to state.yaml file
        """
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
