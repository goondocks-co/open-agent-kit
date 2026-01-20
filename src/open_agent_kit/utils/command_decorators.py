"""Command decorators for DRY pattern enforcement.

This module provides decorators that reduce code duplication across command files.
Decorators handle common patterns like project validation, ensuring consistent
error handling and reducing maintenance burden.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

import typer

from open_agent_kit.config.messages import ERROR_MESSAGES
from open_agent_kit.utils.console import print_error
from open_agent_kit.utils.file_utils import get_project_root


def require_oak_project[F: Callable[..., Any]](func: F) -> F:
    """Decorator to ensure OAK is initialized before running command.

    This decorator checks for the presence of .oak directory and injects
    the project_root as a keyword argument to the wrapped function.

    The decorated function should accept project_root with a default value
    of None, which the decorator will override with the actual project root:
        def my_command(project_root: Path | None = None, ...other params) -> None:
            ...

    Raises:
        typer.Exit: With code 1 if .oak directory is not found

    Example:
        @rules_app.command("my-command")
        @require_oak_project
        def my_command(project_root: Path | None = None) -> None:
            # project_root is automatically injected (never None when decorator used)
            assert project_root is not None
            config_file = project_root / ".oak" / "config.yaml"
            ...
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        project_root = get_project_root()
        if not project_root:
            print_error(ERROR_MESSAGES["no_oak_dir"])
            raise typer.Exit(code=1)
        # Inject project_root as keyword argument
        kwargs["project_root"] = project_root
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
