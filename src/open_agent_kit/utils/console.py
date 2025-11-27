"""Rich Console utilities for beautiful CLI output."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from open_agent_kit.config.messages import BANNER

# Custom theme for consistent styling
custom_theme = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "muted": "dim",
        "primary": "cyan bold",
        "secondary": "blue",
    }
)

# Global console instance
_console: Console | None = None


def get_console() -> Console:
    """Get or create the global console instance."""
    global _console
    if _console is None:
        _console = Console(theme=custom_theme)
    return _console


def print_banner() -> None:
    """Print the open-agent-kit banner."""
    console = get_console()
    console.print(BANNER, style="cyan")


def print_success(message: str, **kwargs: Any) -> None:
    """Print a success message."""
    console = get_console()
    console.print(f"✓ {message}", style="success", **kwargs)


def print_error(message: str, **kwargs: Any) -> None:
    """Print an error message."""
    console = get_console()
    console.print(f"✗ {message}", style="error", **kwargs)


def print_warning(message: str, **kwargs: Any) -> None:
    """Print a warning message."""
    console = get_console()
    console.print(f"⚠ {message}", style="warning", **kwargs)


def print_info(message: str, **kwargs: Any) -> None:
    """Print an info message."""
    console = get_console()
    console.print(f"ℹ {message}", style="info", **kwargs)


def print_muted(message: str, **kwargs: Any) -> None:
    """Print a muted message."""
    console = get_console()
    console.print(message, style="muted", **kwargs)


def print_panel(
    content: str,
    title: str | None = None,
    style: str = "cyan",
    **kwargs: Any,
) -> None:
    """Print content in a styled panel."""
    console = get_console()
    panel = Panel(content, title=title, border_style=style, **kwargs)
    console.print(panel)


def print_table(
    data: list[dict[str, Any]],
    title: str | None = None,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> None:
    """Print data in a formatted table.

    Args:
        data: List of dictionaries with data to display
        title: Optional table title
        columns: Optional list of column names (uses keys from first dict if not provided)
        **kwargs: Additional arguments passed to Table constructor
    """
    console = get_console()

    if not data:
        console.print("[muted]No data to display[/muted]")
        return

    # Get column names
    if columns is None:
        columns = list(data[0].keys())

    # Create table
    table = Table(title=title, **kwargs)

    # Add columns
    for col in columns:
        # Capitalize column names
        header = col.replace("_", " ").title()
        table.add_column(header, style="cyan")

    # Add rows
    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_divider(char: str = "─", style: str = "muted") -> None:
    """Print a horizontal divider."""
    console = get_console()
    width = console.width
    console.print(char * width, style=style)


def print_step(step_number: int, total_steps: int, message: str) -> None:
    """Print a step indicator."""
    console = get_console()
    step_text = Text()
    step_text.append(f"[{step_number}/{total_steps}] ", style="cyan bold")
    step_text.append(message)
    console.print(step_text)


def print_header(text: str, style: str = "primary") -> None:
    """Print a header."""
    console = get_console()
    console.print(f"\n{text}", style=style)
    console.print("─" * len(text), style="muted")


def confirm(message: str, default: bool = False) -> bool:
    """Prompt for confirmation.

    Args:
        message: The confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    console = get_console()
    suffix = " [Y/n]: " if default else " [y/N]: "

    try:
        response = console.input(f"[yellow]?[/yellow] {message}{suffix}")
        if not response:
            return default
        return response.lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        console.print()
        return False


def prompt(
    message: str,
    default: str | None = None,
    required: bool = False,
) -> str:
    """Prompt for user input.

    Args:
        message: The prompt message
        default: Default value if user just presses Enter
        required: Whether input is required

    Returns:
        User input string
    """
    console = get_console()

    suffix = ": "
    if default:
        suffix = f" [{default}]: "

    while True:
        try:
            response = console.input(f"[cyan]?[/cyan] {message}{suffix}")

            if not response and default:
                return default

            if not response and required:
                from open_agent_kit.config.messages import ERROR_MESSAGES

                print_error(ERROR_MESSAGES["field_required"])
                continue

            return response

        except (KeyboardInterrupt, EOFError):
            console.print()
            if required:
                raise
            return default or ""


def print_list(items: list[str], style: str = "info", bullet: str = "•") -> None:
    """Print a bulleted list."""
    console = get_console()
    for item in items:
        console.print(f"  {bullet} {item}", style=style)


def print_numbered_list(items: list[str], style: str = "info") -> None:
    """Print a numbered list."""
    console = get_console()
    for i, item in enumerate(items, 1):
        console.print(f"  {i}. {item}", style=style)


def clear_line() -> None:
    """Clear the current line."""
    import sys

    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


def print_status(message: str, status: str = "info") -> None:
    """Print a status message with icon.

    Args:
        message: The message to print
        status: Status type (success, error, warning, info)
    """
    console = get_console()
    icons = {
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ",
        "pending": "○",
        "current": "●",
    }
    icon = icons.get(status, "•")
    console.print(f"{icon} {message}", style=status)


def print_key_value(key: str, value: str, key_style: str = "cyan") -> None:
    """Print a key-value pair."""
    console = get_console()
    console.print(f"[{key_style}]{key}:[/{key_style}] {value}")


def print_dict(data: dict[str, Any], indent: int = 0) -> None:
    """Print a dictionary with indentation."""
    console = get_console()
    indent_str = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            console.print(f"{indent_str}[cyan]{key}:[/cyan]")
            print_dict(value, indent + 1)
        elif isinstance(value, list):
            console.print(f"{indent_str}[cyan]{key}:[/cyan]")
            for item in value:
                if isinstance(item, dict):
                    print_dict(item, indent + 1)
                else:
                    console.print(f"{indent_str}  • {item}")
        else:
            console.print(f"{indent_str}[cyan]{key}:[/cyan] {value}")


def print_code_block(code: str, language: str = "python") -> None:
    """Print a syntax-highlighted code block."""
    console = get_console()
    from rich.syntax import Syntax

    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(syntax)
