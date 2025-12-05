"""Comprehensive tests for console utility functions."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest

from open_agent_kit.utils.console import (
    clear_line,
    confirm,
    custom_theme,
    get_console,
    print_banner,
    print_code_block,
    print_dict,
    print_divider,
    print_error,
    print_header,
    print_info,
    print_key_value,
    print_list,
    print_muted,
    print_numbered_list,
    print_panel,
    print_status,
    print_step,
    print_success,
    print_table,
    print_warning,
    prompt,
)

# ============================================================================
# Console Instance Management Tests
# ============================================================================


class TestConsoleInstance:
    """Tests for get_console() function."""

    def test_get_console_returns_console_instance(self) -> None:
        """Test get_console returns a Console instance."""
        console = get_console()
        from rich.console import Console

        assert isinstance(console, Console)

    def test_get_console_returns_same_instance(self) -> None:
        """Test get_console returns the same instance on multiple calls."""
        console1 = get_console()
        console2 = get_console()
        assert console1 is console2

    def test_console_has_custom_theme(self) -> None:
        """Test console uses custom theme."""
        console = get_console()
        # Console object has _theme_stack which contains the theme
        assert console._theme_stack is not None

    def test_custom_theme_has_required_styles(self) -> None:
        """Test custom theme contains all required style definitions."""
        required_styles = [
            "info",
            "success",
            "warning",
            "error",
            "muted",
            "primary",
            "secondary",
        ]
        for style in required_styles:
            assert style in custom_theme.styles


# ============================================================================
# Print Message Functions Tests
# ============================================================================


class TestPrintFunctions:
    """Tests for basic print functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_print_success(self, mock_console: MagicMock) -> None:
        """Test print_success formats message correctly."""
        print_success("Operation completed")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "✓ Operation completed" in str(call_args)
        assert "success" in str(call_args)

    def test_print_success_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_success passes through kwargs."""
        print_success("Done", soft_wrap=True)
        call_args = mock_console.print.call_args
        assert "soft_wrap" in call_args.kwargs

    def test_print_error(self, mock_console: MagicMock) -> None:
        """Test print_error formats message correctly."""
        print_error("Something went wrong")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "✗ Something went wrong" in str(call_args)
        assert "error" in str(call_args)

    def test_print_error_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_error passes through kwargs."""
        print_error("Failed", highlight=False)
        call_args = mock_console.print.call_args
        assert "highlight" in call_args.kwargs

    def test_print_warning(self, mock_console: MagicMock) -> None:
        """Test print_warning formats message correctly."""
        print_warning("Be careful")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "⚠ Be careful" in str(call_args)
        assert "warning" in str(call_args)

    def test_print_warning_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_warning passes through kwargs."""
        print_warning("Caution", soft_wrap=True)
        call_args = mock_console.print.call_args
        assert "soft_wrap" in call_args.kwargs

    def test_print_info(self, mock_console: MagicMock) -> None:
        """Test print_info formats message correctly."""
        print_info("This is information")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "ℹ This is information" in str(call_args)
        assert "info" in str(call_args)

    def test_print_info_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_info passes through kwargs."""
        print_info("Note", soft_wrap=True)
        call_args = mock_console.print.call_args
        assert "soft_wrap" in call_args.kwargs

    def test_print_muted(self, mock_console: MagicMock) -> None:
        """Test print_muted formats message correctly."""
        print_muted("Subtle message")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "Subtle message" in str(call_args)
        assert "muted" in str(call_args)

    def test_print_muted_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_muted passes through kwargs."""
        print_muted("Dim text", soft_wrap=True)
        call_args = mock_console.print.call_args
        assert "soft_wrap" in call_args.kwargs

    def test_print_banner(self, mock_console: MagicMock) -> None:
        """Test print_banner calls console.print with BANNER."""
        print_banner()
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "cyan" in str(call_args)
        # BANNER should be in the first positional argument
        assert len(call_args[0]) > 0
        banner_content = str(call_args[0][0])
        assert "oak" in banner_content.lower() or "agent" in banner_content.lower()

    @pytest.mark.parametrize(
        "message,prefix,style",
        [
            ("test", "✓", "success"),
            ("error", "✗", "error"),
            ("warn", "⚠", "warning"),
            ("info", "ℹ", "info"),
        ],
    )
    def test_print_functions_with_various_messages(
        self, mock_console: MagicMock, message: str, prefix: str, style: str
    ) -> None:
        """Test print functions with various message types."""
        print_func_map = {
            "success": print_success,
            "error": print_error,
            "warning": print_warning,
            "info": print_info,
        }
        print_func_map[style](message)
        call_args = mock_console.print.call_args
        assert prefix in str(call_args)
        assert style in str(call_args)


# ============================================================================
# Panel and Table Tests
# ============================================================================


class TestPanelAndTable:
    """Tests for panel and table printing functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_print_panel_with_content_only(self, mock_console: MagicMock) -> None:
        """Test print_panel with content only."""
        print_panel("Panel content")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        # Check that Panel was created and printed
        from rich.panel import Panel

        assert isinstance(call_args[0][0], Panel)

    def test_print_panel_with_title(self, mock_console: MagicMock) -> None:
        """Test print_panel with title."""
        print_panel("Content", title="My Title")
        call_args = mock_console.print.call_args
        from rich.panel import Panel

        panel = call_args[0][0]
        assert isinstance(panel, Panel)
        assert panel.title == "My Title"

    def test_print_panel_with_custom_style(self, mock_console: MagicMock) -> None:
        """Test print_panel with custom style."""
        print_panel("Content", style="red")
        call_args = mock_console.print.call_args
        from rich.panel import Panel

        panel = call_args[0][0]
        assert isinstance(panel, Panel)
        assert panel.border_style == "red"

    def test_print_panel_with_kwargs(self, mock_console: MagicMock) -> None:
        """Test print_panel passes additional kwargs to Panel."""
        print_panel("Content", padding=(1, 2))
        call_args = mock_console.print.call_args
        from rich.panel import Panel

        panel = call_args[0][0]
        assert isinstance(panel, Panel)
        assert panel.padding == (1, 2)

    def test_print_table_with_empty_data(self, mock_console: MagicMock) -> None:
        """Test print_table with empty data."""
        print_table([])
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "[muted]No data to display[/muted]" in str(call_args)

    def test_print_table_with_data(self, mock_console: MagicMock) -> None:
        """Test print_table with data."""
        data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        print_table(data)
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        from rich.table import Table

        table = call_args[0][0]
        assert isinstance(table, Table)

    def test_print_table_with_title(self, mock_console: MagicMock) -> None:
        """Test print_table with title."""
        data = [{"key": "value"}]
        print_table(data, title="My Table")
        call_args = mock_console.print.call_args
        from rich.table import Table

        table = call_args[0][0]
        assert isinstance(table, Table)
        assert table.title == "My Table"

    def test_print_table_with_specific_columns(self, mock_console: MagicMock) -> None:
        """Test print_table with specific columns."""
        data = [{"name": "Alice", "age": "30", "city": "NYC"}]
        print_table(data, columns=["name", "city"])
        call_args = mock_console.print.call_args
        from rich.table import Table

        table = call_args[0][0]
        assert isinstance(table, Table)
        # Verify columns were added
        assert len(table.columns) == 2

    def test_print_table_column_headers_formatted(self, mock_console: MagicMock) -> None:
        """Test print_table formats column headers."""
        data = [{"first_name": "Alice", "last_name": "Smith"}]
        print_table(data)
        call_args = mock_console.print.call_args
        from rich.table import Table

        table = call_args[0][0]
        assert isinstance(table, Table)
        # Headers should be title-cased and underscores replaced
        header_names = [col.header for col in table.columns]
        assert any("First Name" in h for h in header_names)

    def test_print_table_with_missing_values(self, mock_console: MagicMock) -> None:
        """Test print_table handles missing values."""
        data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob"},  # Missing age
        ]
        print_table(data, columns=["name", "age"])
        call_args = mock_console.print.call_args
        from rich.table import Table

        table = call_args[0][0]
        assert isinstance(table, Table)
        # Should have 2 rows despite missing value
        assert len(table.rows) == 2


# ============================================================================
# List and Formatting Tests
# ============================================================================


class TestListsAndFormatting:
    """Tests for list and formatting functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_print_list_basic(self, mock_console: MagicMock) -> None:
        """Test print_list with basic items."""
        items = ["item1", "item2", "item3"]
        print_list(items)
        assert mock_console.print.call_count == 3
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("item1" in call for call in calls)

    def test_print_list_with_custom_bullet(self, mock_console: MagicMock) -> None:
        """Test print_list with custom bullet."""
        print_list(["item"], bullet="→")
        call_args = mock_console.print.call_args_list[0]
        assert "→" in str(call_args)

    def test_print_list_with_custom_style(self, mock_console: MagicMock) -> None:
        """Test print_list with custom style."""
        print_list(["item"], style="warning")
        call_args = mock_console.print.call_args_list[0]
        assert "warning" in str(call_args)

    def test_print_list_empty(self, mock_console: MagicMock) -> None:
        """Test print_list with empty list."""
        print_list([])
        mock_console.print.assert_not_called()

    def test_print_numbered_list_basic(self, mock_console: MagicMock) -> None:
        """Test print_numbered_list with items."""
        items = ["first", "second", "third"]
        print_numbered_list(items)
        assert mock_console.print.call_count == 3
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("1." in call for call in calls)
        assert any("2." in call for call in calls)
        assert any("3." in call for call in calls)

    def test_print_numbered_list_with_style(self, mock_console: MagicMock) -> None:
        """Test print_numbered_list with custom style."""
        print_numbered_list(["item"], style="error")
        call_args = mock_console.print.call_args_list[0]
        assert "error" in str(call_args)

    def test_print_numbered_list_empty(self, mock_console: MagicMock) -> None:
        """Test print_numbered_list with empty list."""
        print_numbered_list([])
        mock_console.print.assert_not_called()

    def test_print_divider_default(self, mock_console: MagicMock) -> None:
        """Test print_divider with default character."""
        mock_console.width = 50
        print_divider()
        call_args = mock_console.print.call_args
        assert "─" * 50 in str(call_args)

    def test_print_divider_custom_char(self, mock_console: MagicMock) -> None:
        """Test print_divider with custom character."""
        mock_console.width = 30
        print_divider(char="=")
        call_args = mock_console.print.call_args
        assert "=" * 30 in str(call_args)

    def test_print_divider_custom_style(self, mock_console: MagicMock) -> None:
        """Test print_divider with custom style."""
        mock_console.width = 20
        print_divider(style="error")
        call_args = mock_console.print.call_args
        assert "error" in str(call_args)

    def test_print_step(self, mock_console: MagicMock) -> None:
        """Test print_step formats step indicator."""
        print_step(1, 5, "Initialize")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert "[1/5]" in str(call_args)
        assert "Initialize" in str(call_args)

    def test_print_step_later_step(self, mock_console: MagicMock) -> None:
        """Test print_step with later step number."""
        print_step(3, 10, "Process")
        call_args = mock_console.print.call_args
        assert "[3/10]" in str(call_args)

    def test_print_header(self, mock_console: MagicMock) -> None:
        """Test print_header."""
        print_header("Configuration")
        assert mock_console.print.call_count == 2  # Header and underline
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Configuration" in call for call in calls)
        assert any("─" in call for call in calls)

    def test_print_header_with_custom_style(self, mock_console: MagicMock) -> None:
        """Test print_header with custom style."""
        print_header("Title", style="warning")
        call_args = mock_console.print.call_args_list[0]
        assert "warning" in str(call_args)

    def test_print_key_value(self, mock_console: MagicMock) -> None:
        """Test print_key_value."""
        print_key_value("name", "Alice")
        call_args = mock_console.print.call_args
        assert "name:" in str(call_args)
        assert "Alice" in str(call_args)

    def test_print_key_value_with_custom_style(self, mock_console: MagicMock) -> None:
        """Test print_key_value with custom key style."""
        print_key_value("status", "active", key_style="warning")
        call_args = mock_console.print.call_args
        assert "warning" in str(call_args)


# ============================================================================
# Dictionary and Code Block Tests
# ============================================================================


class TestDictAndCodeBlock:
    """Tests for dictionary and code block printing."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_print_dict_flat(self, mock_console: MagicMock) -> None:
        """Test print_dict with flat dictionary."""
        data = {"name": "Alice", "age": 30}
        print_dict(data)
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("name" in call for call in calls)
        assert any("age" in call for call in calls)

    def test_print_dict_nested(self, mock_console: MagicMock) -> None:
        """Test print_dict with nested dictionary."""
        data = {
            "user": {"name": "Alice", "age": 30},
            "status": "active",
        }
        print_dict(data)
        # Should handle nested dict recursively
        assert mock_console.print.call_count >= 3

    def test_print_dict_with_list_values(self, mock_console: MagicMock) -> None:
        """Test print_dict with list values."""
        data = {
            "tags": ["python", "testing"],
            "description": "Test",
        }
        print_dict(data)
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("python" in call for call in calls)
        assert any("testing" in call for call in calls)

    def test_print_dict_with_nested_list_of_dicts(self, mock_console: MagicMock) -> None:
        """Test print_dict with list containing dictionaries."""
        data = {
            "items": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}],
        }
        print_dict(data)
        # Should handle nested structures
        assert mock_console.print.call_count >= 4

    def test_print_dict_indentation_level_0(self, mock_console: MagicMock) -> None:
        """Test print_dict maintains correct indentation at level 0."""
        print_dict({"key": "value"}, indent=0)
        call_args = str(mock_console.print.call_args_list[0])
        # No indentation at level 0
        assert "[cyan]key:" in call_args or "key:" in call_args

    def test_print_dict_indentation_level_1(self, mock_console: MagicMock) -> None:
        """Test print_dict maintains correct indentation at nested level."""
        data = {"nested": {"key": "value"}}
        print_dict(data)
        # Nested dict is printed recursively
        assert mock_console.print.call_count >= 2

    def test_print_dict_empty(self, mock_console: MagicMock) -> None:
        """Test print_dict with empty dictionary."""
        print_dict({})
        mock_console.print.assert_not_called()

    def test_print_code_block_default_language(self, mock_console: MagicMock) -> None:
        """Test print_code_block with default language."""
        code = 'print("hello")'
        print_code_block(code)
        call_args = mock_console.print.call_args
        # Should create a Syntax object
        from rich.syntax import Syntax

        assert isinstance(call_args[0][0], Syntax)

    def test_print_code_block_custom_language(self, mock_console: MagicMock) -> None:
        """Test print_code_block with custom language."""
        code = "SELECT * FROM users"
        print_code_block(code, language="sql")
        call_args = mock_console.print.call_args
        from rich.syntax import Syntax

        syntax = call_args[0][0]
        assert isinstance(syntax, Syntax)
        assert "sql" in syntax.lexer.name.lower()

    def test_print_code_block_multiline(self, mock_console: MagicMock) -> None:
        """Test print_code_block with multiline code."""
        code = """
def hello():
    print("world")
"""
        print_code_block(code, language="python")
        call_args = mock_console.print.call_args
        from rich.syntax import Syntax

        assert isinstance(call_args[0][0], Syntax)


# ============================================================================
# Status and Interactive Functions Tests
# ============================================================================


class TestStatusAndInteractive:
    """Tests for status and interactive functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_print_status_success(self, mock_console: MagicMock) -> None:
        """Test print_status with success status."""
        print_status("Operation complete", status="success")
        call_args = mock_console.print.call_args
        assert "✓ Operation complete" in str(call_args)
        assert "success" in str(call_args)

    def test_print_status_error(self, mock_console: MagicMock) -> None:
        """Test print_status with error status."""
        print_status("Failed", status="error")
        call_args = mock_console.print.call_args
        assert "✗ Failed" in str(call_args)
        assert "error" in str(call_args)

    def test_print_status_warning(self, mock_console: MagicMock) -> None:
        """Test print_status with warning status."""
        print_status("Caution", status="warning")
        call_args = mock_console.print.call_args
        assert "⚠ Caution" in str(call_args)

    def test_print_status_info(self, mock_console: MagicMock) -> None:
        """Test print_status with info status."""
        print_status("Note", status="info")
        call_args = mock_console.print.call_args
        assert "ℹ Note" in str(call_args)

    def test_print_status_pending(self, mock_console: MagicMock) -> None:
        """Test print_status with pending status."""
        print_status("Processing", status="pending")
        call_args = mock_console.print.call_args
        assert "○ Processing" in str(call_args)

    def test_print_status_current(self, mock_console: MagicMock) -> None:
        """Test print_status with current status."""
        print_status("Active", status="current")
        call_args = mock_console.print.call_args
        assert "● Active" in str(call_args)

    def test_print_status_unknown_status(self, mock_console: MagicMock) -> None:
        """Test print_status with unknown status uses default icon."""
        print_status("Unknown", status="unknown")
        call_args = mock_console.print.call_args
        assert "• Unknown" in str(call_args)

    @pytest.mark.parametrize(
        "status,icon",
        [
            ("success", "✓"),
            ("error", "✗"),
            ("warning", "⚠"),
            ("info", "ℹ"),
            ("pending", "○"),
            ("current", "●"),
        ],
    )
    def test_print_status_various_statuses(
        self, mock_console: MagicMock, status: str, icon: str
    ) -> None:
        """Test print_status with various status types."""
        print_status("Message", status=status)
        call_args = mock_console.print.call_args
        assert icon in str(call_args)

    def test_confirm_yes_response(self, mock_console: MagicMock) -> None:
        """Test confirm with 'y' response."""
        mock_console.input.return_value = "y"
        result = confirm("Continue?")
        assert result is True

    def test_confirm_yes_full_response(self, mock_console: MagicMock) -> None:
        """Test confirm with 'yes' response."""
        mock_console.input.return_value = "yes"
        result = confirm("Continue?")
        assert result is True

    def test_confirm_yes_uppercase(self, mock_console: MagicMock) -> None:
        """Test confirm with uppercase 'Y' response."""
        mock_console.input.return_value = "Y"
        result = confirm("Continue?")
        assert result is True

    def test_confirm_no_response(self, mock_console: MagicMock) -> None:
        """Test confirm with 'n' response."""
        mock_console.input.return_value = "n"
        result = confirm("Continue?")
        assert result is False

    def test_confirm_empty_with_default_true(self, mock_console: MagicMock) -> None:
        """Test confirm with empty input and default True."""
        mock_console.input.return_value = ""
        result = confirm("Continue?", default=True)
        assert result is True

    def test_confirm_empty_with_default_false(self, mock_console: MagicMock) -> None:
        """Test confirm with empty input and default False."""
        mock_console.input.return_value = ""
        result = confirm("Continue?", default=False)
        assert result is False

    def test_confirm_invalid_response(self, mock_console: MagicMock) -> None:
        """Test confirm with invalid response."""
        mock_console.input.return_value = "maybe"
        result = confirm("Continue?", default=False)
        assert result is False

    def test_confirm_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test confirm handles KeyboardInterrupt."""
        mock_console.input.side_effect = KeyboardInterrupt()
        result = confirm("Continue?")
        assert result is False
        mock_console.print.assert_called()

    def test_confirm_eof_error(self, mock_console: MagicMock) -> None:
        """Test confirm handles EOFError."""
        mock_console.input.side_effect = EOFError()
        result = confirm("Continue?")
        assert result is False

    def test_confirm_suffix_default_true(self, mock_console: MagicMock) -> None:
        """Test confirm shows correct suffix when default is True."""
        mock_console.input.return_value = "n"
        confirm("Continue?", default=True)
        call_args = mock_console.input.call_args
        assert "[Y/n]" in str(call_args)

    def test_confirm_suffix_default_false(self, mock_console: MagicMock) -> None:
        """Test confirm shows correct suffix when default is False."""
        mock_console.input.return_value = "y"
        confirm("Continue?", default=False)
        call_args = mock_console.input.call_args
        assert "[y/N]" in str(call_args)


# ============================================================================
# Prompt Function Tests
# ============================================================================


class TestPromptFunction:
    """Tests for prompt() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_prompt_basic_input(self, mock_console: MagicMock) -> None:
        """Test prompt with basic user input."""
        mock_console.input.return_value = "user input"
        result = prompt("Enter something:")
        assert result == "user input"

    def test_prompt_with_default_empty_input(self, mock_console: MagicMock) -> None:
        """Test prompt uses default on empty input."""
        mock_console.input.return_value = ""
        result = prompt("Enter:", default="default value")
        assert result == "default value"

    def test_prompt_with_default_explicit_input(self, mock_console: MagicMock) -> None:
        """Test prompt uses explicit input over default."""
        mock_console.input.return_value = "explicit"
        result = prompt("Enter:", default="default")
        assert result == "explicit"

    def test_prompt_empty_input_without_default(self, mock_console: MagicMock) -> None:
        """Test prompt returns empty string without default."""
        mock_console.input.return_value = ""
        result = prompt("Enter something:")
        assert result == ""

    def test_prompt_with_none_default(self, mock_console: MagicMock) -> None:
        """Test prompt with None as default."""
        mock_console.input.return_value = ""
        result = prompt("Enter:", default=None)
        assert result == ""

    def test_prompt_required_field_empty_input(self, mock_console: MagicMock) -> None:
        """Test prompt with required=True rejects empty input."""
        mock_console.input.side_effect = ["", "valid input"]
        result = prompt("Enter:", required=True)
        assert result == "valid input"
        # Should print error message
        assert mock_console.print.called

    def test_prompt_required_field_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test prompt with required=True raises KeyboardInterrupt on Ctrl+C."""
        mock_console.input.side_effect = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            prompt("Enter:", required=True)

    def test_prompt_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test prompt handles KeyboardInterrupt."""
        mock_console.input.side_effect = KeyboardInterrupt()
        result = prompt("Enter:")
        assert result == ""
        mock_console.print.assert_called()

    def test_prompt_eof_error(self, mock_console: MagicMock) -> None:
        """Test prompt handles EOFError."""
        mock_console.input.side_effect = EOFError()
        result = prompt("Enter:")
        assert result == ""

    def test_prompt_required_eof_error(self, mock_console: MagicMock) -> None:
        """Test prompt with required=True raises EOFError."""
        mock_console.input.side_effect = EOFError()
        with pytest.raises(EOFError):
            prompt("Enter:", required=True)

    def test_prompt_message_format_no_default(self, mock_console: MagicMock) -> None:
        """Test prompt shows correct message format without default."""
        mock_console.input.return_value = "test"
        prompt("My message:")
        call_args = mock_console.input.call_args
        assert "My message:" in str(call_args)
        assert ": " in str(call_args)

    def test_prompt_message_format_with_default(self, mock_console: MagicMock) -> None:
        """Test prompt shows default in message format."""
        mock_console.input.return_value = ""
        prompt("My message:", default="default_val")
        call_args = mock_console.input.call_args
        assert "[default_val]:" in str(call_args)

    @pytest.mark.parametrize(
        "input_val,default,required,expected",
        [
            ("hello", None, False, "hello"),
            ("", "default", False, "default"),
            ("world", "default", False, "world"),
            ("", None, False, ""),
        ],
    )
    def test_prompt_various_scenarios(
        self,
        mock_console: MagicMock,
        input_val: str,
        default: str | None,
        required: bool,
        expected: str,
    ) -> None:
        """Test prompt with various input scenarios."""
        mock_console.input.return_value = input_val
        result = prompt("Message:", default=default, required=required)
        assert result == expected


# ============================================================================
# Clear Line Function Tests
# ============================================================================


class TestClearLine:
    """Tests for clear_line() function."""

    @patch("sys.stdout.write")
    @patch("sys.stdout.flush")
    def test_clear_line_writes_escape_sequence(self, mock_flush: Mock, mock_write: Mock) -> None:
        """Test clear_line writes correct escape sequence."""
        clear_line()
        mock_write.assert_called_with("\r\033[K")
        mock_flush.assert_called_once()

    @patch("sys.stdout")
    def test_clear_line_flushes_output(self, mock_stdout: MagicMock) -> None:
        """Test clear_line flushes stdout."""
        clear_line()
        mock_stdout.flush.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================


class TestConsoleIntegration:
    """Integration tests for console functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.console.get_console") as mock_get:
            mock_console = MagicMock()
            mock_console.width = 80
            mock_get.return_value = mock_console
            yield mock_console

    def test_multiple_print_calls_sequence(self, mock_console: MagicMock) -> None:
        """Test sequence of multiple print calls."""
        print_header("Test Header")
        print_success("Step 1 done")
        print_warning("Watch out")
        print_error("Something failed")

        assert mock_console.print.call_count == 5  # header, underline, success, warning, error

    def test_table_then_list_output(self, mock_console: MagicMock) -> None:
        """Test combining table and list output."""
        data = [{"name": "Alice"}, {"name": "Bob"}]
        print_table(data)
        print_list(["item1", "item2"])

        assert mock_console.print.call_count == 3  # table + 2 list items

    def test_nested_dict_with_mixed_types(self, mock_console: MagicMock) -> None:
        """Test print_dict with complex nested structure."""
        data = {
            "config": {
                "name": "test",
                "values": [1, 2, 3],
                "nested": {"deep": "value"},
            },
            "status": "active",
        }
        print_dict(data)
        # Should handle all nested structures
        assert mock_console.print.call_count >= 6

    def test_all_print_functions_work_together(self, mock_console: MagicMock) -> None:
        """Test all print functions can be called in sequence."""
        print_banner()
        print_header("Operations")
        print_info("Starting")
        print_panel("Content")
        print_table([{"id": 1}])
        print_divider()
        print_success("Done")

        # All should call print at least once
        assert mock_console.print.call_count > 5
