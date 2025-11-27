"""Interactive selection utilities using arrow keys."""

from collections.abc import Callable

import readchar

from open_agent_kit.utils.console import get_console


class SelectOption:
    """Represents a selectable option."""

    def __init__(
        self,
        value: str,
        label: str | None = None,
        description: str | None = None,
    ):
        """Initialize option.

        Args:
            value: Option value (returned when selected)
            label: Display label (defaults to value if not provided)
            description: Optional description text
        """
        self.value = value
        self.label = label or value
        self.description = description

    def __repr__(self) -> str:
        """String representation."""
        return f"SelectOption(value={self.value}, label={self.label})"


def select(
    options: list[SelectOption] | list[str],
    message: str = "Select an option:",
    default: str | None = None,
) -> str:
    """Interactive selection menu with arrow key navigation.

    Args:
        options: List of SelectOption objects or strings
        message: Prompt message
        default: Default value (auto-selected)

    Returns:
        Selected option value

    Example:
        >>> options = [
        ...     SelectOption("claude", "Claude", "Anthropic's Claude AI"),
        ...     SelectOption("copilot", "GitHub Copilot", "GitHub's AI assistant"),
        ... ]
        >>> result = select(options, "Choose an agent:")
    """
    console = get_console()

    # Convert strings to SelectOption objects
    normalized_options: list[SelectOption] = []
    if options and isinstance(options[0], str):
        normalized_options = [SelectOption(opt) for opt in options]  # type: ignore[arg-type]  # mypy can't narrow list[str] | list[SelectOption] after isinstance check
    else:
        normalized_options = options  # type: ignore[assignment]  # mypy can't narrow list[SelectOption] from union type

    if not normalized_options:
        raise ValueError("No options provided")

    # Find default index
    current_index = 0
    if default:
        for i, opt in enumerate(normalized_options):
            if opt.value == default:
                current_index = i
                break

    # Print message
    console.print(f"\n[cyan]?[/cyan] {message}")
    console.print("[dim](Use arrow keys to navigate, Enter to select)[/dim]\n")

    first_render = True
    while True:
        # Clear previous options (skip on first render)
        if not first_render:
            # Count lines to clear: each option + description lines
            lines_to_clear = 0
            for opt in normalized_options:
                lines_to_clear += 1  # Option line
                if opt.description:
                    lines_to_clear += 1  # Description line

            # Move cursor up and clear
            for _ in range(lines_to_clear):
                console.file.write("\033[F")  # Move up one line
            console.file.write("\033[J")  # Clear from cursor down
            console.file.flush()

        first_render = False

        # Print options
        for i, option in enumerate(normalized_options):
            if i == current_index:
                # Highlighted option
                prefix = "❯"
                style = "cyan bold"
                console.print(f"  {prefix} {option.label}", style=style)
                if option.description:
                    console.print(f"    [dim]{option.description}[/dim]")
            else:
                # Normal option
                prefix = " "
                console.print(f"  {prefix} {option.label}", style="dim")
                if option.description:
                    console.print(f"    [dim]{option.description}[/dim]")

        # Get key input
        key = readchar.readkey()

        if key == readchar.key.UP:
            current_index = (current_index - 1) % len(normalized_options)
        elif key == readchar.key.DOWN:
            current_index = (current_index + 1) % len(normalized_options)
        elif key in [readchar.key.ENTER, readchar.key.CR, readchar.key.LF]:
            # Clear the menu
            lines_to_clear = 0
            for opt in normalized_options:
                lines_to_clear += 1
                if opt.description:
                    lines_to_clear += 1

            for _ in range(lines_to_clear):
                console.file.write("\033[F")
            console.file.write("\033[J")
            console.file.flush()

            # Print final selection
            selected = normalized_options[current_index]
            console.print(f"[cyan]?[/cyan] {message} [green]{selected.label}[/green]")
            return selected.value
        elif key == readchar.key.CTRL_C:
            console.print("\n\n[red]Cancelled[/red]")
            raise KeyboardInterrupt()


def multi_select(
    options: list[SelectOption] | list[str],
    message: str = "Select options:",
    defaults: list[str] | None = None,
    min_selections: int = 0,
    max_selections: int | None = None,
    dependents_map: dict[str, list[str]] | None = None,
) -> list[str]:
    """Interactive multi-selection menu with arrow key navigation.

    Args:
        options: List of SelectOption objects or strings
        message: Prompt message
        defaults: List of default values (pre-selected)
        min_selections: Minimum number of selections required
        max_selections: Maximum number of selections allowed
        dependents_map: Map of option value to list of dependent option values.
            When an option is deselected, its dependents are also deselected.
            Example: {"constitution": ["rfc", "issues"]} means deselecting
            "constitution" will also deselect "rfc" and "issues".

    Returns:
        List of selected option values

    Example:
        >>> options = ["feature", "bugfix", "docs", "refactor"]
        >>> result = multi_select(options, "Select tags:")
    """
    console = get_console()

    # Convert strings to SelectOption objects
    normalized_options: list[SelectOption] = []
    if options and isinstance(options[0], str):
        normalized_options = [SelectOption(opt) for opt in options]  # type: ignore[arg-type]  # mypy can't narrow list[str] | list[SelectOption] after isinstance check
    else:
        normalized_options = options  # type: ignore[assignment]  # mypy can't narrow list[SelectOption] from union type

    if not normalized_options:
        raise ValueError("No options provided")

    # Track selections
    selected = set()
    if defaults:
        selected = {opt.value for opt in normalized_options if opt.value in defaults}

    current_index = 0

    # Print message
    console.print(f"\n[cyan]?[/cyan] {message}")
    console.print(
        "[dim](Use arrow keys to navigate, Space to select/deselect, Enter to confirm)[/dim]\n"
    )

    first_render = True
    prev_had_description = False  # Track if previous render had a description
    while True:
        # Clear previous options (skip on first render)
        if not first_render:
            # Count lines to clear: options + (description if shown) + count line + blank
            lines_to_clear = len(normalized_options)
            if prev_had_description:
                lines_to_clear += 1  # Add line for description
            lines_to_clear += 2  # Count line + blank line

            # Move cursor up and clear
            for _ in range(lines_to_clear):
                console.file.write("\033[F")  # Move up one line
            console.file.write("\033[J")  # Clear from cursor down
            console.file.flush()

        first_render = False

        # Check if current option has description (for next iteration's clearing)
        current_option = normalized_options[current_index]
        prev_had_description = bool(current_option.description)

        # Print options
        for i, option in enumerate(normalized_options):
            is_selected = option.value in selected
            is_current = i == current_index

            if is_selected:
                checkbox = "☑"
                style = "green"
            else:
                checkbox = "☐"
                style = "dim"

            if is_current:
                prefix = "❯"
                if is_selected:
                    style = "green bold"
                else:
                    style = "cyan bold"
            else:
                prefix = " "

            console.print(f"  {prefix} {checkbox} {option.label}", style=style)
            if option.description and is_current:
                console.print(f"      [dim]{option.description}[/dim]")

        # Print selection count
        count_text = f"Selected: {len(selected)}"
        if max_selections:
            count_text += f"/{max_selections}"
        console.print(f"\n[dim]{count_text}[/dim]")

        # Get key input
        key = readchar.readkey()

        if key == readchar.key.UP:
            current_index = (current_index - 1) % len(normalized_options)
        elif key == readchar.key.DOWN:
            current_index = (current_index + 1) % len(normalized_options)
        elif key == readchar.key.SPACE:
            option = normalized_options[current_index]
            if option.value in selected:
                # Deselecting - also deselect dependents
                selected.remove(option.value)
                if dependents_map and option.value in dependents_map:
                    for dependent in dependents_map[option.value]:
                        selected.discard(dependent)
            else:
                if max_selections is None or len(selected) < max_selections:
                    selected.add(option.value)
        elif key in [readchar.key.ENTER, readchar.key.CR, readchar.key.LF]:
            if len(selected) < min_selections:
                # Show error but continue
                continue

            # Clear the menu
            lines_to_clear = len(normalized_options) + 2  # options + count line + blank
            for _ in range(lines_to_clear):
                console.file.write("\033[F")
            console.file.write("\033[J")
            console.file.flush()

            # Print final selection
            selected_labels = [opt.label for opt in normalized_options if opt.value in selected]
            console.print(f"[cyan]?[/cyan] {message} [green]{', '.join(selected_labels)}[/green]")
            return list(selected)
        elif key == readchar.key.CTRL_C:
            console.print("\n\n[red]Cancelled[/red]")
            raise KeyboardInterrupt()


def confirm(message: str, default: bool = False) -> bool:
    """Interactive yes/no confirmation.

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if confirmed, False otherwise

    Example:
        >>> if confirm("Continue?", default=True):
        ...     print("Confirmed!")
    """
    console = get_console()

    suffix = " [Y/n]: " if default else " [y/N]: "
    prompt_text = f"[yellow]?[/yellow] {message}{suffix}"

    try:
        response = console.input(prompt_text)
        if not response:
            return default
        return response.lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        console.print()
        return False


def prompt(
    message: str,
    default: str | None = None,
    validator: Callable[[str], bool] | None = None,
    error_message: str | None = None,
) -> str:
    """Interactive text input prompt with validation.

    Args:
        message: Prompt message
        default: Default value if user just presses Enter
        validator: Optional validation function
        error_message: Error message for invalid input

    Returns:
        User input string

    Example:
        >>> name = prompt("Enter your name:", validator=lambda x: len(x) > 0)
    """
    console = get_console()

    suffix = ": "
    if default is not None:
        # Use dim styling instead of brackets to avoid Rich markup conflicts
        suffix = f" [dim]\\[{default}][/dim]: "

    while True:
        try:
            prompt_text = f"[cyan]?[/cyan] {message}{suffix}"
            response = console.input(prompt_text)

            if not response and default is not None:
                return default

            if validator and not validator(response):
                from open_agent_kit.config.messages import ERROR_MESSAGES

                msg = error_message or ERROR_MESSAGES["invalid_input"]
                console.print(f"[red]✗[/red] {msg}")
                continue

            return response

        except (KeyboardInterrupt, EOFError):
            console.print()
            raise


def password_prompt(message: str = "Enter password:") -> str:
    """Interactive password input (hidden).

    Args:
        message: Prompt message

    Returns:
        Password string

    Example:
        >>> password = password_prompt()
    """
    console = get_console()

    try:
        from getpass import getpass

        prompt_text = f"[cyan]?[/cyan] {message} "
        # Print prompt without newline
        console.print(prompt_text, end="")
        return getpass("")
    except (KeyboardInterrupt, EOFError):
        console.print()
        raise


def select_with_search(
    options: list[SelectOption] | list[str],
    message: str = "Select an option:",
    default: str | None = None,
) -> str:
    """Interactive selection menu with search/filter capability.

    Args:
        options: List of SelectOption objects or strings
        message: Prompt message
        default: Default value (auto-selected)

    Returns:
        Selected option value

    Example:
        >>> options = ["option1", "option2", "option3"]
        >>> result = select_with_search(options, "Choose:")
    """
    import sys

    console = get_console()

    # Convert strings to SelectOption objects
    select_options: list[SelectOption]
    if options and isinstance(options[0], str):
        select_options = [SelectOption(str(opt)) for opt in options]
    else:
        select_options = [opt for opt in options if isinstance(opt, SelectOption)]

    if not select_options:
        raise ValueError("No options provided")

    search_query = ""
    filtered_options: list[SelectOption] = select_options[:]
    current_index = 0

    # Find default index
    if default:
        for i, opt in enumerate(filtered_options):
            if opt.value == default:
                current_index = i
                break

    # Print message
    console.print(f"\n[cyan]?[/cyan] {message}")
    console.print("[dim](Type to search, use arrow keys to navigate, Enter to select)[/dim]\n")

    while True:
        # Filter options based on search query
        if search_query:
            filtered_options = [
                opt
                for opt in select_options
                if search_query.lower() in opt.label.lower()
                or search_query.lower() in opt.value.lower()
            ]
            if not filtered_options:
                filtered_options = select_options[:]
            current_index = min(current_index, len(filtered_options) - 1)
        else:
            filtered_options = select_options[:]

        # Clear previous display
        if current_index > 0 or search_query:
            lines_to_clear = len(filtered_options) + 2
            sys.stdout.write(f"\033[{lines_to_clear}A")  # Move cursor up
            sys.stdout.write("\033[J")  # Clear from cursor down
            sys.stdout.flush()

        # Print search query
        if search_query:
            console.print(f"Search: [cyan]{search_query}[/cyan]")
        else:
            console.print("Search: [dim]type to filter...[/dim]")

        # Print options
        for i, option in enumerate(filtered_options[:10]):  # Limit display to 10
            if i == current_index:
                console.print(f"  ❯ {option.label}", style="cyan bold")
            else:
                console.print(f"    {option.label}", style="dim")

        if len(filtered_options) > 10:
            console.print(f"\n[dim]... and {len(filtered_options) - 10} more[/dim]")

        # Get key input
        key = readchar.readkey()

        if key == readchar.key.UP:
            current_index = max(0, current_index - 1)
        elif key == readchar.key.DOWN:
            current_index = min(len(filtered_options) - 1, current_index + 1)
        elif key in [readchar.key.ENTER, readchar.key.CR, readchar.key.LF]:
            if filtered_options:
                lines_to_clear = min(len(filtered_options), 10) + 2
                sys.stdout.write(f"\033[{lines_to_clear}A")
                sys.stdout.write("\033[J")
                sys.stdout.flush()
                selected = filtered_options[current_index]
                console.print(f"[cyan]?[/cyan] {message} [green]{selected.label}[/green]")
                return selected.value
        elif key == readchar.key.BACKSPACE:
            search_query = search_query[:-1]
            current_index = 0
        elif key == readchar.key.CTRL_C:
            console.print("\n\n[red]Cancelled[/red]")
            raise KeyboardInterrupt()
        elif len(key) == 1 and key.isprintable():
            search_query += key
            current_index = 0
