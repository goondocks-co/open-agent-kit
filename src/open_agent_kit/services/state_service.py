"""State service for managing internal OAK state."""

import hashlib
from datetime import datetime
from pathlib import Path

from open_agent_kit.config.paths import STATE_FILE
from open_agent_kit.models.state import CreatedFile, ManagedAssets, ModifiedFile, OakState


class StateService:
    """Service for managing internal OAK state.

    State is stored separately from config.yaml to keep user-facing
    configuration clean. State includes things like applied migrations
    that users should not need to see or edit.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize state service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.state_path = self.project_root / STATE_FILE

    def load_state(self) -> OakState:
        """Load state from file.

        Returns:
            OakState instance
        """
        return OakState.load(self.state_path)

    def save_state(self, state: OakState) -> None:
        """Save state to file.

        Args:
            state: OakState instance to save
        """
        state.save(self.state_path)

    def get_applied_migrations(self) -> list[str]:
        """Get list of applied migration IDs.

        Returns:
            List of migration IDs that have been applied
        """
        state = self.load_state()
        return state.migrations

    def add_applied_migrations(self, migration_ids: list[str]) -> None:
        """Add migration IDs to the applied list.

        Args:
            migration_ids: List of migration IDs to add
        """
        state = self.load_state()
        # Use set to avoid duplicates, then sort for consistency
        all_migrations = list(set(state.migrations + migration_ids))
        all_migrations.sort()
        state.migrations = all_migrations
        self.save_state(state)

    def is_migration_applied(self, migration_id: str) -> bool:
        """Check if a specific migration has been applied.

        Args:
            migration_id: Migration ID to check

        Returns:
            True if migration has been applied
        """
        return migration_id in self.get_applied_migrations()

    # =========================================================================
    # Managed Assets Tracking
    # =========================================================================

    def get_managed_assets(self) -> ManagedAssets:
        """Get managed assets from state.

        Returns:
            ManagedAssets instance
        """
        state = self.load_state()
        return state.managed_assets

    def record_created_directory(self, directory_path: Path) -> None:
        """Record a directory created by oak.

        Args:
            directory_path: Path to directory (absolute or relative)
        """
        state = self.load_state()
        relative_path = self._to_relative_path(directory_path)

        if relative_path not in state.managed_assets.directories:
            state.managed_assets.directories.append(relative_path)
            state.managed_assets.directories.sort()
            self.save_state(state)

    def record_created_file(self, file_path: Path, content: str | None = None) -> None:
        """Record a file created by oak.

        Args:
            file_path: Path to file (absolute or relative)
            content: File content (reads from disk if not provided)
        """
        state = self.load_state()
        relative_path = self._to_relative_path(file_path)

        # Check if already recorded
        existing_paths = [f.path for f in state.managed_assets.created_files]
        if relative_path in existing_paths:
            return

        # Get content hash
        if content is None:
            abs_path = self._to_absolute_path(file_path)
            if abs_path.exists():
                content = abs_path.read_text(encoding="utf-8")
            else:
                return  # Can't record non-existent file

        file_hash = self._hash_content(content)

        created_file = CreatedFile(
            path=relative_path,
            hash=file_hash,
            created_at=datetime.now().isoformat(),
        )
        state.managed_assets.created_files.append(created_file)
        self.save_state(state)

    def record_modified_file(
        self,
        file_path: Path,
        modification_type: str = "appended",
        marker: str = "## Project Constitution",
    ) -> None:
        """Record a file modified by oak.

        Args:
            file_path: Path to file (absolute or relative)
            modification_type: Type of modification (appended, replaced)
            marker: Text marker identifying our additions
        """
        state = self.load_state()
        relative_path = self._to_relative_path(file_path)

        # Check if already recorded
        existing_paths = [f.path for f in state.managed_assets.modified_files]
        if relative_path in existing_paths:
            return

        modified_file = ModifiedFile(
            path=relative_path,
            modification_type=modification_type,
            marker=marker,
        )
        state.managed_assets.modified_files.append(modified_file)
        self.save_state(state)

    def is_file_unchanged(self, file_path: Path) -> bool:
        """Check if a created file is unchanged from when we created it.

        Args:
            file_path: Path to file

        Returns:
            True if file exists and hash matches original
        """
        relative_path = self._to_relative_path(file_path)
        abs_path = self._to_absolute_path(file_path)

        if not abs_path.exists():
            return False

        state = self.load_state()
        for created_file in state.managed_assets.created_files:
            if created_file.path == relative_path:
                current_hash = self._hash_content(abs_path.read_text(encoding="utf-8"))
                return current_hash == created_file.hash

        return False

    def clear_managed_assets(self) -> None:
        """Clear all managed assets tracking.

        Called after successful removal.
        """
        state = self.load_state()
        state.managed_assets = ManagedAssets()
        self.save_state(state)

    def _to_relative_path(self, path: Path) -> str:
        """Convert path to relative string from project root.

        Args:
            path: Absolute or relative path

        Returns:
            Relative path string
        """
        if path.is_absolute():
            try:
                return str(path.relative_to(self.project_root))
            except ValueError:
                return str(path)
        return str(path)

    def _to_absolute_path(self, path: Path) -> Path:
        """Convert path to absolute path.

        Args:
            path: Absolute or relative path

        Returns:
            Absolute path
        """
        if path.is_absolute():
            return path
        return self.project_root / path

    @staticmethod
    def _hash_content(content: str) -> str:
        """Generate SHA256 hash of content.

        Args:
            content: String content to hash

        Returns:
            Hex digest of hash
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_state_service(project_root: Path | None = None) -> StateService:
    """Get a StateService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        StateService instance
    """
    return StateService(project_root)
