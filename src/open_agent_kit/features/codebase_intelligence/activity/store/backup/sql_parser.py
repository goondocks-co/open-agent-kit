"""SQL parsing helpers for backup import/export.

Self-contained mini SQL-parsing layer for extracting and manipulating
INSERT statements in backup files.
"""

from __future__ import annotations

import re


def _extract_sql_statements(content: str) -> list[str]:
    """Extract complete SQL INSERT statements from backup content.

    Handles multi-line statements where values contain newlines.
    A statement ends with ');' not inside a quoted string.

    Args:
        content: Full backup file content.

    Returns:
        List of complete INSERT statements.
    """
    statements = []
    current_stmt = ""
    in_string = False
    in_comment = False
    i = 0

    while i < len(content):
        char = content[i]

        # Handle SQL comments (-- to end of line)
        if not in_string and not in_comment and char == "-":
            if i + 1 < len(content) and content[i + 1] == "-":
                in_comment = True
                i += 2
                continue

        # End of comment at newline
        if in_comment:
            if char == "\n":
                in_comment = False
            i += 1
            continue

        # Skip whitespace/newlines when not in a statement
        if not current_stmt and char in " \t\n\r":
            i += 1
            continue

        current_stmt += char

        if char == "'" and not in_string:
            in_string = True
        elif char == "'" and in_string:
            # Check for escaped quote ''
            if i + 1 < len(content) and content[i + 1] == "'":
                # Escaped quote - add it and skip next char
                current_stmt += content[i + 1]
                i += 1
            else:
                in_string = False
        elif char == ";" and not in_string:
            # Statement complete
            stmt = current_stmt.strip()
            if stmt.startswith("INSERT INTO"):
                statements.append(stmt)
            current_stmt = ""

        i += 1

    return statements


def _parse_insert_statement(stmt: str) -> dict | None:
    """Parse INSERT statement to extract column names and values.

    Args:
        stmt: SQL INSERT statement.

    Returns:
        Dictionary of column names to values, or None if parsing fails.
    """
    # Pattern: INSERT INTO table (col1, col2, ...) VALUES (val1, val2, ...);
    match = re.match(
        r"INSERT INTO \w+ \(([^)]+)\) VALUES \((.+)\);?$",
        stmt,
        re.DOTALL,
    )
    if not match:
        return None

    columns_str = match.group(1)
    values_str = match.group(2)

    columns = [c.strip() for c in columns_str.split(",")]

    # Parse values (handling quoted strings with commas)
    values = _parse_sql_values(values_str)
    if len(values) != len(columns):
        return None

    return dict(zip(columns, values, strict=False))


def _parse_sql_values(values_str: str) -> list:
    """Parse SQL VALUES clause, handling quoted strings with commas.

    Args:
        values_str: The values portion of an INSERT statement.

    Returns:
        List of parsed values.
    """
    values = []
    current = ""
    in_string = False
    i = 0

    while i < len(values_str):
        char = values_str[i]

        if char == "'" and not in_string:
            in_string = True
            current += char
        elif char == "'" and in_string:
            # Check for escaped quote
            if i + 1 < len(values_str) and values_str[i + 1] == "'":
                current += "''"
                i += 1
            else:
                in_string = False
                current += char
        elif char == "," and not in_string:
            values.append(_parse_sql_value(current.strip()))
            current = ""
        else:
            current += char
        i += 1

    # Don't forget the last value
    if current.strip():
        values.append(_parse_sql_value(current.strip()))

    return values


def _parse_sql_value(val_str: str) -> str | int | float | bool | None:
    """Parse a single SQL value string to Python type.

    Args:
        val_str: SQL value string.

    Returns:
        Parsed Python value (str, int, float, None, or bool).
    """
    if val_str == "NULL":
        return None
    if val_str.startswith("'") and val_str.endswith("'"):
        # Unescape single quotes
        return val_str[1:-1].replace("''", "'")
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def _parse_sql_values_as_strings(values_str: str) -> list[str]:
    """Parse SQL VALUES section into list of raw SQL value strings.

    Handles quoted strings with embedded commas and parentheses.
    Returns original SQL representation (e.g., 'text', NULL, 123).

    Args:
        values_str: The content inside VALUES (...) without outer parens.

    Returns:
        List of SQL value strings.
    """
    values: list[str] = []
    current = ""
    in_string = False
    depth = 0

    for char in values_str:
        if char == "'" and not in_string:
            in_string = True
            current += char
        elif char == "'" and in_string:
            # Check for escaped quote ('')
            if current.endswith("'"):
                current += char
            else:
                in_string = False
                current += char
        elif char == "(" and not in_string:
            depth += 1
            current += char
        elif char == ")" and not in_string:
            depth -= 1
            current += char
        elif char == "," and not in_string and depth == 0:
            values.append(current.strip())
            current = ""
        else:
            current += char

    # Don't forget the last value
    if current.strip():
        values.append(current.strip())

    return values


def _remove_column_from_insert(stmt: str, column_name: str) -> str:
    """Remove a column and its value from an INSERT statement.

    Used to strip auto-increment id columns so SQLite generates new IDs,
    avoiding PRIMARY KEY conflicts when importing from different machines.

    Args:
        stmt: INSERT INTO table (cols) VALUES (vals); statement.
        column_name: Name of the column to remove.

    Returns:
        Modified statement without the column.
    """
    # Parse column list
    cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(", stmt, re.IGNORECASE)
    if not cols_match:
        return stmt

    cols_str = cols_match.group(1)
    columns = [c.strip() for c in cols_str.split(",")]

    # Find target column index
    try:
        col_idx = columns.index(column_name)
    except ValueError:
        return stmt  # Column not in statement

    # Find VALUES section
    values_start = stmt.upper().find("VALUES")
    if values_start == -1:
        return stmt

    # Find the opening paren after VALUES
    paren_start = stmt.find("(", values_start)
    if paren_start == -1:
        return stmt

    # Parse values as raw SQL strings (handling quoted strings with commas)
    values_section = stmt[paren_start + 1 :]
    values = _parse_sql_values_as_strings(values_section.rstrip(");"))

    if col_idx >= len(values):
        return stmt

    # Remove the column and value
    new_columns = columns[:col_idx] + columns[col_idx + 1 :]
    new_values = values[:col_idx] + values[col_idx + 1 :]

    # Get table name
    table_match = re.match(r"INSERT INTO (\w+)", stmt)
    if not table_match:
        return stmt
    table_name = table_match.group(1)

    # Rebuild the statement
    return f"INSERT INTO {table_name} ({', '.join(new_columns)}) VALUES ({', '.join(new_values)});"


def _replace_column_value(stmt: str, column_name: str, new_value: str) -> str:
    """Replace a column's value in an INSERT statement.

    Parses the INSERT statement to find the column index in the column list,
    then replaces the corresponding value in the VALUES section.

    Args:
        stmt: INSERT INTO table (cols) VALUES (vals); statement.
        column_name: Name of the column to modify.
        new_value: New value to set.

    Returns:
        Modified statement with the column's value replaced.
    """
    # Parse column list
    cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(", stmt, re.IGNORECASE)
    if not cols_match:
        return stmt

    cols_str = cols_match.group(1)
    columns = [c.strip() for c in cols_str.split(",")]

    # Find target column index
    try:
        col_idx = columns.index(column_name)
    except ValueError:
        return stmt  # Column not in statement

    # Find VALUES section
    values_start = stmt.upper().find("VALUES")
    if values_start == -1:
        return stmt

    # Find the opening paren after VALUES
    paren_start = stmt.find("(", values_start)
    if paren_start == -1:
        return stmt

    # Parse values as raw SQL strings (handling quoted strings with commas)
    values_section = stmt[paren_start + 1 :]
    values = _parse_sql_values_as_strings(values_section.rstrip(");"))

    if col_idx >= len(values):
        return stmt

    # Replace the value
    values[col_idx] = new_value

    # Rebuild the statement
    prefix = stmt[: paren_start + 1]
    return f"{prefix}{', '.join(values)});"
