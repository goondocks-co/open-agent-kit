"""File system utilities for open-agent-kit."""

import shutil
from pathlib import Path
from typing import Any

import yaml


def ensure_dir(path: Path) -> None:
    """Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists
    """
    path.mkdir(parents=True, exist_ok=True)


def read_file(path: Path) -> str:
    """Read text file contents.

    Args:
        path: Path to file to read

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str) -> None:
    """Write content to text file.

    Args:
        path: Path to file to write
        content: Content to write

    Creates parent directories if they don't exist.
    """
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def copy_file(src: Path, dst: Path, overwrite: bool = False) -> bool:
    """Copy a file from source to destination.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing file

    Returns:
        True if file was copied, False if destination exists and overwrite=False

    Raises:
        FileNotFoundError: If source file doesn't exist
    """
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if dst.exists() and not overwrite:
        return False

    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return True


def copy_dir(src: Path, dst: Path, overwrite: bool = False) -> None:
    """Copy directory recursively.

    Args:
        src: Source directory path
        dst: Destination directory path
        overwrite: Whether to overwrite existing files

    Raises:
        FileNotFoundError: If source directory doesn't exist
    """
    if not src.exists():
        raise FileNotFoundError(f"Source directory not found: {src}")

    ensure_dir(dst)

    for item in src.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(src)
            dst_path = dst / rel_path
            copy_file(item, dst_path, overwrite=overwrite)


def delete_file(path: Path) -> bool:
    """Delete a file if it exists.

    Args:
        path: Path to file to delete

    Returns:
        True if file was deleted, False if it didn't exist
    """
    if path.exists():
        path.unlink()
        return True
    return False


def delete_dir(path: Path) -> bool:
    """Delete a directory and all its contents.

    Args:
        path: Path to directory to delete

    Returns:
        True if directory was deleted, False if it didn't exist
    """
    if path.exists():
        shutil.rmtree(path)
        return True
    return False


def file_exists(path: Path) -> bool:
    """Check if file exists.

    Args:
        path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    return path.exists() and path.is_file()


def dir_exists(path: Path) -> bool:
    """Check if directory exists.

    Args:
        path: Path to check

    Returns:
        True if directory exists, False otherwise
    """
    return path.exists() and path.is_dir()


def list_files(
    directory: Path,
    pattern: str = "*",
    recursive: bool = False,
) -> list[Path]:
    """List files in directory matching pattern.

    Args:
        directory: Directory to search
        pattern: Glob pattern to match (e.g., "*.md", "**/*.py")
        recursive: Whether to search recursively

    Returns:
        List of matching file paths
    """
    if not dir_exists(directory):
        return []

    if recursive:
        return sorted([p for p in directory.rglob(pattern) if p.is_file()])
    else:
        return sorted([p for p in directory.glob(pattern) if p.is_file()])


def list_dirs(directory: Path, pattern: str = "*") -> list[Path]:
    """List subdirectories in directory matching pattern.

    Args:
        directory: Directory to search
        pattern: Glob pattern to match

    Returns:
        List of matching directory paths
    """
    if not dir_exists(directory):
        return []

    return sorted([p for p in directory.glob(pattern) if p.is_dir()])


def read_yaml(path: Path) -> dict[str, Any]:
    """Read YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if data is not None else {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to YAML file.

    Args:
        path: Path to YAML file
        data: Data to write
    """
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def get_file_size(path: Path) -> int:
    """Get file size in bytes.

    Args:
        path: Path to file

    Returns:
        File size in bytes

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.stat().st_size


def get_file_modified_time(path: Path) -> float:
    """Get file modification time as timestamp.

    Args:
        path: Path to file

    Returns:
        Modification time as Unix timestamp

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.stat().st_mtime


def is_empty_dir(path: Path) -> bool:
    """Check if directory is empty.

    Args:
        path: Path to directory

    Returns:
        True if directory is empty, False otherwise
    """
    if not dir_exists(path):
        return True

    return not any(path.iterdir())


def cleanup_empty_directories(start_dir: Path, stop_at: Path) -> None:
    """Remove empty directories recursively up to a stop directory.

    Walks up the directory tree from start_dir, removing empty directories
    until it reaches stop_at or finds a non-empty directory.

    Args:
        start_dir: Directory to start cleanup from
        stop_at: Directory to stop at (will not be removed)

    Example:
        >>> cleanup_empty_directories(Path('.codex/prompts'), Path('.'))
        # Removes .codex/prompts/ if empty, then .codex/ if empty
        # Stops at project root ('.')
    """
    current = start_dir

    # Walk up the tree, removing empty directories
    while current != stop_at and current != current.parent:
        try:
            # Check if directory exists and is empty
            if current.exists() and current.is_dir():
                # List all contents (including hidden files)
                contents = list(current.iterdir())
                if not contents:
                    # Directory is empty, safe to remove
                    current.rmdir()
                else:
                    # Directory has contents, stop cleanup
                    break
            else:
                # Directory doesn't exist or isn't a directory, stop
                break
        except (OSError, PermissionError):
            # Can't remove or access, stop cleanup
            break

        # Move up to parent
        current = current.parent


def get_relative_path(path: Path, base: Path) -> Path:
    """Get relative path from base.

    Args:
        path: Path to convert to relative
        base: Base path

    Returns:
        Relative path from base
    """
    try:
        return path.relative_to(base)
    except ValueError:
        # If path is not relative to base, return the path as-is
        return path


def find_files_by_name(
    directory: Path,
    filename: str,
    recursive: bool = True,
) -> list[Path]:
    """Find files by exact filename.

    Args:
        directory: Directory to search
        filename: Exact filename to match
        recursive: Whether to search recursively

    Returns:
        List of matching file paths
    """
    if not dir_exists(directory):
        return []

    if recursive:
        return sorted([p for p in directory.rglob(filename) if p.is_file()])
    else:
        return sorted([p for p in directory.glob(filename) if p.is_file()])


def find_files_by_extension(
    directory: Path,
    extension: str,
    recursive: bool = True,
) -> list[Path]:
    """Find files by extension.

    Args:
        directory: Directory to search
        extension: File extension (with or without leading dot)
        recursive: Whether to search recursively

    Returns:
        List of matching file paths
    """
    if not extension.startswith("."):
        extension = f".{extension}"

    pattern = f"**/*{extension}" if recursive else f"*{extension}"
    return list_files(directory, pattern, recursive)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem
    """
    import re

    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)

    # Replace spaces with hyphens
    filename = filename.replace(" ", "-")

    # Remove multiple consecutive hyphens
    filename = re.sub(r"-+", "-", filename)

    # Remove leading/trailing hyphens and dots
    filename = filename.strip("-.")

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        name = name[: max_length - len(ext) - 1]
        filename = f"{name}.{ext}" if ext else name

    return filename


def get_project_root(start_path: Path | None = None) -> Path | None:
    """Find project root by looking for .oak directory.

    Args:
        start_path: Path to start searching from (defaults to current directory)

    Returns:
        Project root path if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Search up the directory tree
    for parent in [current] + list(current.parents):
        oak_dir = parent / ".oak"
        if oak_dir.exists() and oak_dir.is_dir():
            return parent

    return None


def is_git_repo(path: Path | None = None) -> bool:
    """Check if path is within a git repository.

    Args:
        path: Path to check (defaults to current directory)

    Returns:
        True if within a git repository, False otherwise
    """
    if path is None:
        path = Path.cwd()

    current = path.resolve()

    # Search up the directory tree for .git directory
    for parent in [current] + list(current.parents):
        git_dir = parent / ".git"
        if git_dir.exists():
            return True

    return False


def get_git_root(path: Path | None = None) -> Path | None:
    """Find git repository root.

    Args:
        path: Path to start searching from (defaults to current directory)

    Returns:
        Git repository root path if found, None otherwise
    """
    if path is None:
        path = Path.cwd()

    current = path.resolve()

    # Search up the directory tree for .git directory
    for parent in [current] + list(current.parents):
        git_dir = parent / ".git"
        if git_dir.exists():
            return parent

    return None
