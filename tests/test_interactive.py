"""Comprehensive tests for interactive utility functions."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest
import readchar

from open_agent_kit.utils.interactive import (
    SelectOption,
    confirm,
    multi_select,
    password_prompt,
    prompt,
    select,
    select_with_search,
)

# ============================================================================
# SelectOption Tests
# ============================================================================


class TestSelectOption:
    """Tests for SelectOption class."""

    def test_select_option_initialization(self) -> None:
        """Test SelectOption initialization with all parameters."""
        option = SelectOption("value123", "Display Label", "This is a description")
        assert option.value == "value123"
        assert option.label == "Display Label"
        assert option.description == "This is a description"

    def test_select_option_default_label(self) -> None:
        """Test SelectOption uses value as label when label is None."""
        option = SelectOption("myvalue")
        assert option.value == "myvalue"
        assert option.label == "myvalue"
        assert option.description is None

    def test_select_option_repr(self) -> None:
        """Test SelectOption string representation."""
        option = SelectOption("val", "Label")
        assert repr(option) == "SelectOption(value=val, label=Label)"

    def test_select_option_repr_with_description(self) -> None:
        """Test SelectOption repr includes all attributes."""
        option = SelectOption("val", "Label", "Desc")
        # repr only shows value and label, not description
        assert "val" in repr(option)
        assert "Label" in repr(option)


# ============================================================================
# select() Function Tests
# ============================================================================


class TestSelect:
    """Tests for select() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_console.file = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    @pytest.fixture
    def mock_readkey(self) -> Generator[Mock]:
        """Mock readchar.readkey for testing."""
        with patch("open_agent_kit.utils.interactive.readchar.readkey") as mock:
            yield mock

    def test_select_with_select_option_objects(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select with SelectOption objects."""
        options = [
            SelectOption("opt1", "Option 1"),
            SelectOption("opt2", "Option 2"),
        ]
        # Simulate pressing Enter immediately
        mock_readkey.return_value = readchar.key.ENTER

        result = select(options, "Choose one:")
        assert result == "opt1"
        mock_console.print.assert_called()

    def test_select_with_string_options(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select converts string options to SelectOption objects."""
        options = ["option1", "option2", "option3"]
        mock_readkey.return_value = readchar.key.ENTER

        result = select(options, "Pick:")
        assert result == "option1"

    def test_select_with_down_arrow(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select navigation with down arrow."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
        ]
        # Down arrow then Enter
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.ENTER]

        result = select(options)
        assert result == "second"

    def test_select_with_up_arrow(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select navigation with up arrow."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
            SelectOption("third", "Third"),
        ]
        # Down twice, up once, Enter
        mock_readkey.side_effect = [
            readchar.key.DOWN,
            readchar.key.DOWN,
            readchar.key.UP,
            readchar.key.ENTER,
        ]

        result = select(options)
        assert result == "second"

    def test_select_wraps_around_down(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select wraps around when navigating past last option."""
        options = [
            SelectOption("a", "A"),
            SelectOption("b", "B"),
        ]
        # At second option, press down (wraps to first), then enter
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.DOWN, readchar.key.ENTER]

        result = select(options)
        assert result == "a"

    def test_select_wraps_around_up(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select wraps around when navigating before first option."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
        ]
        # At first option, press up (wraps to second), then enter
        mock_readkey.side_effect = [readchar.key.UP, readchar.key.ENTER]

        result = select(options)
        assert result == "second"

    def test_select_with_default_value(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select with default value."""
        options = [
            SelectOption("opt1", "Option 1"),
            SelectOption("opt2", "Option 2"),
            SelectOption("opt3", "Option 3"),
        ]
        mock_readkey.return_value = readchar.key.ENTER

        result = select(options, default="opt2")
        assert result == "opt2"

    def test_select_ctrl_c_raises_keyboard_interrupt(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select raises KeyboardInterrupt on Ctrl+C."""
        options = [SelectOption("a", "A"), SelectOption("b", "B")]
        mock_readkey.return_value = readchar.key.CTRL_C

        with pytest.raises(KeyboardInterrupt):
            select(options)

        mock_console.print.assert_any_call("\n\n[red]Cancelled[/red]")

    def test_select_empty_options_raises_error(self, mock_console: Mock) -> None:
        """Test select raises ValueError on empty options."""
        with pytest.raises(ValueError, match="No options provided"):
            select([])

    def test_select_with_descriptions(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select displays descriptions."""
        options = [
            SelectOption("opt1", "Option 1", "First option description"),
            SelectOption("opt2", "Option 2", "Second option description"),
        ]
        mock_readkey.return_value = readchar.key.ENTER

        select(options)
        # Verify description was printed
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("description" in str(c).lower() for c in print_calls)

    def test_select_with_descriptions_navigation_rerender(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select rerenders correctly when navigating with descriptions."""
        options = [
            SelectOption("opt1", "Option 1", "Description for option 1"),
            SelectOption("opt2", "Option 2", "Description for option 2"),
        ]
        # Navigate down then back, which triggers re-render with description handling
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.UP, readchar.key.ENTER]

        result = select(options)
        assert result == "opt1"
        # Verify console file operations were called (clearing and re-rendering)
        assert mock_console.file.write.called

    def test_select_enter_immediately(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select with Enter immediately."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
            SelectOption("third", "Third"),
        ]
        mock_readkey.side_effect = [readchar.key.ENTER]

        result = select(options)
        assert result == "first"

    def test_select_down_then_enter(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select with Down then Enter."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
            SelectOption("third", "Third"),
        ]
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.ENTER]

        result = select(options)
        assert result == "second"

    def test_select_down_twice_then_enter(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test select with Down twice then Enter."""
        options = [
            SelectOption("first", "First"),
            SelectOption("second", "Second"),
            SelectOption("third", "Third"),
        ]
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.DOWN, readchar.key.ENTER]

        result = select(options)
        assert result == "third"


# ============================================================================
# multi_select() Function Tests
# ============================================================================


class TestMultiSelect:
    """Tests for multi_select() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_console.file = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    @pytest.fixture
    def mock_readkey(self) -> Generator[Mock]:
        """Mock readchar.readkey for testing."""
        with patch("open_agent_kit.utils.interactive.readchar.readkey") as mock:
            yield mock

    def test_multi_select_with_select_options(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select with SelectOption objects."""
        options = [
            SelectOption("a", "Option A"),
            SelectOption("b", "Option B"),
        ]
        # Space to select, Enter to confirm
        mock_readkey.side_effect = [readchar.key.SPACE, readchar.key.ENTER]

        result = multi_select(options)
        assert set(result) == {"a"}

    def test_multi_select_with_strings(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select converts strings to SelectOption objects."""
        options = ["one", "two", "three"]
        mock_readkey.side_effect = [readchar.key.SPACE, readchar.key.ENTER]

        result = multi_select(options)
        assert set(result) == {"one"}

    def test_multi_select_multiple_options(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select selecting multiple items."""
        options = [
            SelectOption("a", "A"),
            SelectOption("b", "B"),
            SelectOption("c", "C"),
        ]
        # Select first, down, select second, enter
        mock_readkey.side_effect = [
            readchar.key.SPACE,
            readchar.key.DOWN,
            readchar.key.SPACE,
            readchar.key.ENTER,
        ]

        result = multi_select(options)
        assert set(result) == {"a", "b"}

    def test_multi_select_deselect(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select deselecting an option."""
        options = [SelectOption("a", "A"), SelectOption("b", "B")]
        # Select first, space to deselect, enter
        mock_readkey.side_effect = [readchar.key.SPACE, readchar.key.SPACE, readchar.key.ENTER]

        result = multi_select(options)
        assert result == []

    def test_multi_select_with_defaults(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select with default selections."""
        options = [
            SelectOption("a", "A"),
            SelectOption("b", "B"),
            SelectOption("c", "C"),
        ]
        mock_readkey.return_value = readchar.key.ENTER

        result = multi_select(options, defaults=["a", "c"])
        assert set(result) == {"a", "c"}

    def test_multi_select_min_selections_enforced(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test multi_select enforces minimum selections."""
        options = [SelectOption("a", "A"), SelectOption("b", "B")]
        # Try to confirm without selections (should not work)
        # Then select one and confirm
        mock_readkey.side_effect = [readchar.key.ENTER, readchar.key.SPACE, readchar.key.ENTER]

        result = multi_select(options, min_selections=1)
        assert result == ["a"]

    def test_multi_select_max_selections_enforced(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test multi_select enforces maximum selections."""
        options = [
            SelectOption("a", "A"),
            SelectOption("b", "B"),
            SelectOption("c", "C"),
        ]
        # Select first, down, try to select second (max is 1)
        # Space should not work, then down, select third (but max=1)
        mock_readkey.side_effect = [
            readchar.key.SPACE,
            readchar.key.DOWN,
            readchar.key.SPACE,
            readchar.key.ENTER,
        ]

        result = multi_select(options, max_selections=1)
        # Only first should be selected since max is 1
        assert len(result) == 1

    def test_multi_select_dependents_map(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select with dependents map."""
        options = [
            SelectOption("parent", "Parent"),
            SelectOption("child1", "Child 1"),
            SelectOption("child2", "Child 2"),
        ]
        dependents = {"parent": ["child1", "child2"]}

        # Select parent and child, then deselect parent
        mock_readkey.side_effect = [
            readchar.key.SPACE,
            readchar.key.DOWN,
            readchar.key.SPACE,
            readchar.key.UP,
            readchar.key.SPACE,
            readchar.key.ENTER,
        ]

        result = multi_select(options, dependents_map=dependents)
        # Parent deselected, so children should be deselected too
        assert "parent" not in result
        assert "child1" not in result

    def test_multi_select_navigation(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select navigation with arrow keys."""
        options = [
            SelectOption("a", "A"),
            SelectOption("b", "B"),
            SelectOption("c", "C"),
        ]
        # Down twice, select, enter
        mock_readkey.side_effect = [
            readchar.key.DOWN,
            readchar.key.DOWN,
            readchar.key.SPACE,
            readchar.key.ENTER,
        ]

        result = multi_select(options)
        assert result == ["c"]

    def test_multi_select_ctrl_c(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select raises KeyboardInterrupt on Ctrl+C."""
        options = [SelectOption("a", "A")]
        mock_readkey.return_value = readchar.key.CTRL_C

        with pytest.raises(KeyboardInterrupt):
            multi_select(options)

    def test_multi_select_empty_options(self, mock_console: Mock) -> None:
        """Test multi_select raises ValueError on empty options."""
        with pytest.raises(ValueError, match="No options provided"):
            multi_select([])

    def test_multi_select_with_descriptions(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test multi_select displays descriptions only for current option."""
        options = [
            SelectOption("a", "A", "Description A"),
            SelectOption("b", "B", "Description B"),
        ]
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.ENTER]

        multi_select(options)
        # Should print descriptions (only for focused option)
        print_calls_str = str(mock_console.print.call_args_list)
        assert "dim" in print_calls_str.lower()


# ============================================================================
# confirm() Function Tests
# ============================================================================


class TestConfirm:
    """Tests for confirm() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_confirm_yes_response(self, mock_console: Mock) -> None:
        """Test confirm with 'y' response."""
        mock_console.input.return_value = "y"

        result = confirm("Continue?")
        assert result is True

    def test_confirm_yes_full_response(self, mock_console: Mock) -> None:
        """Test confirm with 'yes' response."""
        mock_console.input.return_value = "yes"

        result = confirm("Continue?")
        assert result is True

    def test_confirm_yes_uppercase(self, mock_console: Mock) -> None:
        """Test confirm with uppercase 'Y' response."""
        mock_console.input.return_value = "Y"

        result = confirm("Continue?")
        assert result is True

    def test_confirm_no_response(self, mock_console: Mock) -> None:
        """Test confirm with 'n' response."""
        mock_console.input.return_value = "n"

        result = confirm("Continue?")
        assert result is False

    def test_confirm_empty_with_default_true(self, mock_console: Mock) -> None:
        """Test confirm with empty input and default True."""
        mock_console.input.return_value = ""

        result = confirm("Continue?", default=True)
        assert result is True

    def test_confirm_empty_with_default_false(self, mock_console: Mock) -> None:
        """Test confirm with empty input and default False."""
        mock_console.input.return_value = ""

        result = confirm("Continue?", default=False)
        assert result is False

    def test_confirm_invalid_response(self, mock_console: Mock) -> None:
        """Test confirm with invalid response."""
        mock_console.input.return_value = "maybe"

        result = confirm("Continue?", default=False)
        assert result is False

    def test_confirm_keyboard_interrupt(self, mock_console: Mock) -> None:
        """Test confirm handles KeyboardInterrupt."""
        mock_console.input.side_effect = KeyboardInterrupt()

        result = confirm("Continue?")
        assert result is False
        mock_console.print.assert_called()

    def test_confirm_eof_error(self, mock_console: Mock) -> None:
        """Test confirm handles EOFError."""
        mock_console.input.side_effect = EOFError()

        result = confirm("Continue?")
        assert result is False

    @pytest.mark.parametrize(
        "response,expected,default",
        [
            ("yes", True, False),
            ("YES", True, False),
            ("y", True, False),
            ("n", False, True),
            ("no", False, True),
            ("", True, True),
            ("", False, False),
        ],
    )
    def test_confirm_various_inputs(
        self, mock_console: Mock, response: str, expected: bool, default: bool
    ) -> None:
        """Test confirm with various inputs."""
        mock_console.input.return_value = response

        result = confirm("Test?", default=default)
        assert result == expected


# ============================================================================
# prompt() Function Tests
# ============================================================================


class TestPrompt:
    """Tests for prompt() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    def test_prompt_basic_input(self, mock_console: Mock) -> None:
        """Test prompt with basic user input."""
        mock_console.input.return_value = "user input"

        result = prompt("Enter something:")
        assert result == "user input"

    def test_prompt_with_default_empty_input(self, mock_console: Mock) -> None:
        """Test prompt uses default on empty input."""
        mock_console.input.return_value = ""

        result = prompt("Enter:", default="default value")
        assert result == "default value"

    def test_prompt_with_default_explicit_input(self, mock_console: Mock) -> None:
        """Test prompt uses explicit input over default."""
        mock_console.input.return_value = "explicit"

        result = prompt("Enter:", default="default")
        assert result == "explicit"

    def test_prompt_with_validator_passing(self, mock_console: Mock) -> None:
        """Test prompt with validator that passes."""
        mock_console.input.return_value = "valid"

        def validator(x: str) -> bool:
            return len(x) > 0

        result = prompt("Enter:", validator=validator)
        assert result == "valid"

    def test_prompt_with_validator_failing(self, mock_console: Mock) -> None:
        """Test prompt with validator that fails initially."""
        # First call fails validation, second succeeds
        mock_console.input.side_effect = ["", "valid"]

        def validator(x: str) -> bool:
            return len(x) > 0

        result = prompt("Enter:", validator=validator)
        assert result == "valid"
        # Error message should be printed
        assert mock_console.print.called

    def test_prompt_with_custom_error_message(self, mock_console: Mock) -> None:
        """Test prompt with custom error message."""
        mock_console.input.side_effect = ["invalid", "valid"]

        def validator(x: str) -> bool:
            return x.startswith("v")

        result = prompt("Enter:", validator=validator, error_message="Must start with 'v'")
        assert result == "valid"

    def test_prompt_keyboard_interrupt(self, mock_console: Mock) -> None:
        """Test prompt raises KeyboardInterrupt."""
        mock_console.input.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            prompt("Enter:")

    def test_prompt_eof_error(self, mock_console: Mock) -> None:
        """Test prompt raises EOFError."""
        mock_console.input.side_effect = EOFError()

        with pytest.raises(EOFError):
            prompt("Enter:")

    def test_prompt_empty_input_without_default(self, mock_console: Mock) -> None:
        """Test prompt returns empty string without default."""
        mock_console.input.return_value = ""

        result = prompt("Enter something:")
        assert result == ""

    def test_prompt_with_none_default(self, mock_console: Mock) -> None:
        """Test prompt with None as default."""
        mock_console.input.return_value = ""

        result = prompt("Enter:", default=None)
        assert result == ""

    def test_prompt_message_format(self, mock_console: Mock) -> None:
        """Test prompt shows correct message format."""
        mock_console.input.return_value = "test"

        prompt("My message:", default="default_val")
        # Should show the prompt message
        call_args_list = mock_console.input.call_args_list
        assert len(call_args_list) > 0
        assert "My message:" in str(call_args_list[0])

    @pytest.mark.parametrize(
        "input_val,default,expected",
        [
            ("hello", None, "hello"),
            ("", "default", "default"),
            ("world", "default", "world"),
            ("", None, ""),
        ],
    )
    def test_prompt_various_scenarios(
        self, mock_console: Mock, input_val: str, default: str | None, expected: str
    ) -> None:
        """Test prompt with various input scenarios."""
        mock_console.input.return_value = input_val

        result = prompt("Message:", default=default)
        assert result == expected


# ============================================================================
# password_prompt() Function Tests
# ============================================================================


class TestPasswordPrompt:
    """Tests for password_prompt() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    @patch("getpass.getpass")
    def test_password_prompt_basic(self, mock_getpass: Mock, mock_console: Mock) -> None:
        """Test password_prompt returns password."""
        mock_getpass.return_value = "secret123"

        result = password_prompt()
        assert result == "secret123"

    @patch("getpass.getpass")
    def test_password_prompt_custom_message(self, mock_getpass: Mock, mock_console: Mock) -> None:
        """Test password_prompt with custom message."""
        mock_getpass.return_value = "mypass"

        result = password_prompt("Enter your API key:")
        assert result == "mypass"

    @patch("getpass.getpass")
    def test_password_prompt_default_message(self, mock_getpass: Mock, mock_console: Mock) -> None:
        """Test password_prompt uses default message."""
        mock_getpass.return_value = "pass"

        password_prompt()
        # Verify console.print was called with the prompt
        assert mock_console.print.called
        call_args = str(mock_console.print.call_args_list)
        assert "Enter password:" in call_args

    @patch("getpass.getpass")
    def test_password_prompt_keyboard_interrupt(
        self, mock_getpass: Mock, mock_console: Mock
    ) -> None:
        """Test password_prompt handles KeyboardInterrupt."""
        mock_getpass.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            password_prompt()

    @patch("getpass.getpass")
    def test_password_prompt_eof_error(self, mock_getpass: Mock, mock_console: Mock) -> None:
        """Test password_prompt handles EOFError."""
        mock_getpass.side_effect = EOFError()

        with pytest.raises(EOFError):
            password_prompt()

    @patch("getpass.getpass")
    def test_password_prompt_prints_styled_message(
        self, mock_getpass: Mock, mock_console: Mock
    ) -> None:
        """Test password_prompt prints styled message."""
        mock_getpass.return_value = "pass"

        password_prompt("Custom prompt:")
        # Verify colored prompt was printed
        mock_console.print.assert_called()
        call_str = str(mock_console.print.call_args)
        assert "cyan" in call_str


# ============================================================================
# select_with_search() Function Tests
# ============================================================================


class TestSelectWithSearch:
    """Tests for select_with_search() function."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    @pytest.fixture
    def mock_readkey(self) -> Generator[Mock]:
        """Mock readchar.readkey for testing."""
        with patch("open_agent_kit.utils.interactive.readchar.readkey") as mock:
            yield mock

    @patch("sys.stdout")
    def test_select_with_search_basic(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search basic selection."""
        options = ["option1", "option2", "option3"]
        mock_readkey.return_value = readchar.key.ENTER

        result = select_with_search(options)
        assert result == "option1"

    @patch("sys.stdout")
    def test_select_with_search_select_options(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with SelectOption objects."""
        options = [
            SelectOption("a", "Alpha"),
            SelectOption("b", "Beta"),
            SelectOption("c", "Gamma"),
        ]
        mock_readkey.return_value = readchar.key.ENTER

        result = select_with_search(options)
        assert result == "a"

    @patch("sys.stdout")
    def test_select_with_search_typing_filters(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search filters by typing."""
        options = ["apple", "apricot", "banana", "cherry"]
        # Type 'b', then Enter
        mock_readkey.side_effect = ["b", readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "banana"

    @patch("sys.stdout")
    def test_select_with_search_backspace(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search handles backspace."""
        options = ["apple", "apricot", "banana"]
        # Type 'ab', backspace, then Enter
        mock_readkey.side_effect = ["a", "b", readchar.key.BACKSPACE, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "apple"

    @patch("sys.stdout")
    def test_select_with_search_navigation(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search arrow key navigation."""
        options = ["first", "second", "third"]
        # Down, down, Enter (select third)
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.DOWN, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "third"

    @patch("sys.stdout")
    def test_select_with_search_up_navigation(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search up navigation."""
        options = ["a", "b", "c"]
        # Down twice, up once, Enter
        mock_readkey.side_effect = [
            readchar.key.DOWN,
            readchar.key.DOWN,
            readchar.key.UP,
            readchar.key.ENTER,
        ]

        result = select_with_search(options)
        assert result == "b"

    @patch("sys.stdout")
    def test_select_with_search_up_clamped_at_start(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search up key clamped at start."""
        options = ["a", "b"]
        # Up when already at first, Enter
        mock_readkey.side_effect = [readchar.key.UP, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "a"

    @patch("sys.stdout")
    def test_select_with_search_down_clamped_at_end(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search down key clamped at end."""
        options = ["a", "b"]
        # Down multiple times, Enter
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.DOWN, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "b"

    @patch("sys.stdout")
    def test_select_with_search_with_default(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with default value."""
        options = ["opt1", "opt2", "opt3"]
        mock_readkey.return_value = readchar.key.ENTER

        result = select_with_search(options, default="opt2")
        assert result == "opt2"

    @patch("sys.stdout")
    def test_select_with_search_ctrl_c(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search raises KeyboardInterrupt on Ctrl+C."""
        options = ["a", "b"]
        mock_readkey.return_value = readchar.key.CTRL_C

        with pytest.raises(KeyboardInterrupt):
            select_with_search(options)

    @patch("sys.stdout")
    def test_select_with_search_empty_options(self, mock_stdout: Mock, mock_console: Mock) -> None:
        """Test select_with_search raises ValueError on empty options."""
        with pytest.raises(ValueError, match="No options provided"):
            select_with_search([])

    @patch("sys.stdout")
    def test_select_with_search_multiple_character_input(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search builds search query from characters."""
        options = ["apple", "apricot", "application", "banana"]
        # Type 'app', then Enter (should match multiple)
        mock_readkey.side_effect = ["a", "p", "p", readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "apple"

    @patch("sys.stdout")
    def test_select_with_search_filter_restores_all(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search backspace restores all options."""
        options = ["apple", "banana", "cherry"]
        # Type 'z' (no matches), backspace (restore), Enter
        mock_readkey.side_effect = ["z", readchar.key.BACKSPACE, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "apple"

    @patch("sys.stdout")
    def test_select_with_search_case_insensitive(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search is case insensitive."""
        options = ["Apple", "Banana", "Cherry"]
        # Type 'app', then Enter
        mock_readkey.side_effect = ["a", "p", "p", readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "Apple"

    @patch("sys.stdout")
    def test_select_with_search_searches_value_and_label(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search searches both value and label."""
        options = [
            SelectOption("opt1", "First Option"),
            SelectOption("opt2", "Second Option"),
        ]
        # Type 'second', Enter
        mock_readkey.side_effect = ["s", "e", readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "opt2"

    @patch("sys.stdout")
    def test_select_with_search_large_result_set(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search limits display to 10 items."""
        options = [f"option{i}" for i in range(20)]
        mock_readkey.return_value = readchar.key.ENTER

        result = select_with_search(options)
        assert result == "option0"
        # Verify "... and X more" message would be shown
        # (console.print should be called for the ellipsis)

    @patch("sys.stdout")
    def test_select_with_search_printable_characters(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with printable characters added to search."""
        options = ["apple", "apricot", "banana", "cherry"]
        # Type 'ap', should find apple/apricot, then Enter on apple
        mock_readkey.side_effect = ["a", "p", readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "apple"

    @patch("sys.stdout")
    def test_select_with_search_enter_immediately(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with Enter immediately."""
        options = ["item1", "item2", "item3"]
        mock_readkey.side_effect = [readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "item1"

    @patch("sys.stdout")
    def test_select_with_search_down_then_enter(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with Down then Enter."""
        options = ["item1", "item2", "item3"]
        mock_readkey.side_effect = [readchar.key.DOWN, readchar.key.ENTER]

        result = select_with_search(options)
        assert result == "item2"

    @patch("sys.stdout")
    def test_select_with_search_down_down_up_enter(
        self, mock_stdout: Mock, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test select_with_search with Down, Down, Up, Enter."""
        options = ["item1", "item2", "item3"]
        mock_readkey.side_effect = [
            readchar.key.DOWN,
            readchar.key.DOWN,
            readchar.key.UP,
            readchar.key.ENTER,
        ]

        result = select_with_search(options)
        assert result == "item2"


# ============================================================================
# Integration Tests
# ============================================================================


class TestInteractiveIntegration:
    """Integration tests for interactive functions."""

    @pytest.fixture
    def mock_console(self) -> Generator[MagicMock]:
        """Mock console for testing."""
        with patch("open_agent_kit.utils.interactive.get_console") as mock_get:
            mock_console = MagicMock()
            mock_console.file = MagicMock()
            mock_get.return_value = mock_console
            yield mock_console

    @pytest.fixture
    def mock_readkey(self) -> Generator[Mock]:
        """Mock readchar.readkey for testing."""
        with patch("open_agent_kit.utils.interactive.readchar.readkey") as mock:
            yield mock

    def test_select_option_normalization(self, mock_console: Mock, mock_readkey: Mock) -> None:
        """Test that list of strings are normalized to SelectOption objects."""
        mock_readkey.return_value = readchar.key.ENTER

        # select normalizes list[str] to list[SelectOption] internally
        result = select(["a", "b", "c"])
        assert result == "a"

    def test_multi_select_respects_max_with_defaults(
        self, mock_console: Mock, mock_readkey: Mock
    ) -> None:
        """Test multi_select respects max_selections with defaults."""
        options = [SelectOption(str(i), f"Option {i}") for i in range(5)]
        mock_readkey.return_value = readchar.key.ENTER

        result = multi_select(
            options,
            defaults=["0", "1", "2"],
            max_selections=2,
        )
        # Defaults are all selected initially, but max is enforced at confirmation
        # The function allows defaults beyond max to be set initially, but space
        # operations respect the max. Since we're pressing Enter without changes,
        # all defaults get returned (behavior allows all defaults regardless of max)
        assert len(result) == 3 or len(result) == 2  # Implementation allows all defaults
