"""Step tracker for displaying progress during multi-step operations."""

from typing import Any

from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn

from open_agent_kit.utils.console import get_console, print_status


class StepTracker:
    """Track and display progress through multiple steps.

    Example:
        >>> tracker = StepTracker(3)
        >>> tracker.start_step("Initializing...")
        >>> # ... do work ...
        >>> tracker.complete_step("Initialized")
        >>> tracker.start_step("Processing...")
        >>> # ... do work ...
        >>> tracker.complete_step("Processed")
    """

    def __init__(self, total_steps: int):
        """Initialize step tracker.

        Args:
            total_steps: Total number of steps to track
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.console = get_console()
        self._current_message: str | None = None

    def start_step(self, message: str) -> None:
        """Start a new step.

        Args:
            message: Description of the step being started
        """
        self.current_step += 1
        self._current_message = message

        prefix = f"[{self.current_step}/{self.total_steps}]"
        self.console.print(f"[cyan bold]{prefix}[/cyan bold] {message}...", end="")

    def complete_step(self, message: str | None = None) -> None:
        """Mark current step as complete.

        Args:
            message: Optional completion message (uses start message if not provided)
        """
        if message is None:
            message = self._current_message or "Done"

        # Move to beginning of line and clear
        self.console.print("\r", end="")

        prefix = f"[{self.current_step}/{self.total_steps}]"
        self.console.print(f"[green]✓[/green] [cyan bold]{prefix}[/cyan bold] {message}")

    def fail_step(self, message: str | None = None, error: str | None = None) -> None:
        """Mark current step as failed.

        Args:
            message: Optional failure message
            error: Optional error details
        """
        if message is None:
            message = self._current_message or "Failed"

        # Move to beginning of line and clear
        self.console.print("\r", end="")

        prefix = f"[{self.current_step}/{self.total_steps}]"
        self.console.print(f"[red]✗[/red] [cyan bold]{prefix}[/cyan bold] {message}")

        if error:
            self.console.print(f"  [red]{error}[/red]")

    def skip_step(self, message: str | None = None) -> None:
        """Mark current step as skipped.

        Args:
            message: Optional skip message
        """
        if message is None:
            message = self._current_message or "Skipped"

        self.current_step += 1

        # Move to beginning of line and clear
        self.console.print("\r", end="")

        prefix = f"[{self.current_step}/{self.total_steps}]"
        self.console.print(f"[yellow]○[/yellow] [cyan bold]{prefix}[/cyan bold] {message}")

    def finish(self, message: str = "All steps completed!") -> None:
        """Mark all steps as finished.

        Args:
            message: Final completion message
        """
        self.console.print(f"\n[green bold]✓ {message}[/green bold]")


class ProgressTracker:
    """Track progress for long-running operations with spinner.

    Example:
        >>> with ProgressTracker("Processing files...") as tracker:
        ...     # ... do work ...
        ...     tracker.update("Processing file 1 of 10")
        ...     # ... continue work ...
    """

    def __init__(self, message: str):
        """Initialize progress tracker.

        Args:
            message: Initial progress message
        """
        self.message = message
        self.console = get_console()
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None

    def __enter__(self) -> "ProgressTracker":
        """Start progress display."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
        self._progress.__enter__()
        self._task_id = self._progress.add_task(self.message, total=None)
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop progress display."""
        if self._progress:
            self._progress.__exit__(*args)

    def update(self, message: str) -> None:
        """Update progress message.

        Args:
            message: New progress message
        """
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=message)

    def complete(self, message: str = "Complete") -> None:
        """Mark progress as complete.

        Args:
            message: Completion message
        """
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=f"[green]✓[/green] {message}")


class SimpleProgress:
    """Simple progress display without fancy formatting.

    Example:
        >>> progress = SimpleProgress("Processing")
        >>> for i in range(10):
        ...     progress.update(f"Step {i+1}/10")
        >>> progress.complete("Done!")
    """

    def __init__(self, prefix: str = ""):
        """Initialize simple progress.

        Args:
            prefix: Prefix to show before each update
        """
        self.prefix = prefix
        self.console = get_console()

    def update(self, message: str) -> None:
        """Update progress message.

        Args:
            message: Progress message
        """
        full_message = f"{self.prefix} {message}" if self.prefix else message
        self.console.print(f"[cyan]●[/cyan] {full_message}", end="\r")

    def complete(self, message: str = "Complete") -> None:
        """Mark progress as complete.

        Args:
            message: Completion message
        """
        # Clear the line and print completion
        self.console.print("\r", end="")
        full_message = f"{self.prefix} {message}" if self.prefix else message
        self.console.print(f"[green]✓[/green] {full_message}")

    def fail(self, message: str = "Failed") -> None:
        """Mark progress as failed.

        Args:
            message: Failure message
        """
        # Clear the line and print failure
        self.console.print("\r", end="")
        full_message = f"{self.prefix} {message}" if self.prefix else message
        self.console.print(f"[red]✗[/red] {full_message}")


class TaskList:
    """Display and track a list of tasks.

    Example:
        >>> tasks = TaskList()
        >>> tasks.add_task("Initialize project")
        >>> tasks.add_task("Create files")
        >>> tasks.add_task("Configure settings")
        >>> tasks.start_task(0)
        >>> tasks.complete_task(0)
        >>> tasks.start_task(1)
        >>> tasks.fail_task(1, "File already exists")
    """

    def __init__(self) -> None:
        """Initialize task list."""
        self.tasks: list[dict[str, str]] = []
        self.console = get_console()

    def add_task(self, description: str) -> int:
        """Add a task to the list.

        Args:
            description: Task description

        Returns:
            Task index
        """
        self.tasks.append({"description": description, "status": "pending"})
        return len(self.tasks) - 1

    def start_task(self, index: int) -> None:
        """Mark task as started.

        Args:
            index: Task index
        """
        if 0 <= index < len(self.tasks):
            self.tasks[index]["status"] = "running"
            self._display()

    def complete_task(self, index: int) -> None:
        """Mark task as complete.

        Args:
            index: Task index
        """
        if 0 <= index < len(self.tasks):
            self.tasks[index]["status"] = "complete"
            self._display()

    def fail_task(self, index: int, error: str | None = None) -> None:
        """Mark task as failed.

        Args:
            index: Task index
            error: Optional error message
        """
        if 0 <= index < len(self.tasks):
            self.tasks[index]["status"] = "failed"
            if error:
                self.tasks[index]["error"] = error
            self._display()

    def skip_task(self, index: int) -> None:
        """Mark task as skipped.

        Args:
            index: Task index
        """
        if 0 <= index < len(self.tasks):
            self.tasks[index]["status"] = "skipped"
            self._display()

    def _display(self) -> None:
        """Display current task list."""
        import sys

        # Clear previous display
        if self.tasks:
            sys.stdout.write(f"\033[{len(self.tasks)}A")  # Move cursor up
            sys.stdout.write("\033[J")  # Clear from cursor down
            sys.stdout.flush()

        # Print tasks
        for task in self.tasks:
            status = task["status"]
            description = task["description"]

            if status == "complete":
                print_status(description, "success")
            elif status == "failed":
                print_status(description, "error")
                if "error" in task:
                    self.console.print(f"  [dim]{task['error']}[/dim]")
            elif status == "running":
                print_status(description, "current")
            elif status == "skipped":
                print_status(description, "warning")
            else:  # pending
                print_status(description, "pending")
