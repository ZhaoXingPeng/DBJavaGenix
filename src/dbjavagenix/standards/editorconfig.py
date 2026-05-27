"""EditorConfig generator — `.editorconfig` for Java + XML + YAML projects."""

from __future__ import annotations


def generate_editorconfig(
    indent_size: int = 4,
    line_endings: str = "lf",
    final_newline: bool = True,
    trim_trailing_ws: bool = True,
) -> str:
    """Generate a project-root `.editorconfig` content.

    Args:
        indent_size: spaces per indent for Java (XML/YAML use 2)
        line_endings: "lf" or "crlf"
        final_newline: insert final newline on save
        trim_trailing_ws: trim trailing whitespace on save

    Returns:
        EditorConfig content with sections for Java / XML / YAML / Markdown.
    """
    lines = [
        "# .editorconfig — editor settings normalization",
        "# https://editorconfig.org",
        "",
        "root = true",
        "",
        "[*]",
        "charset = utf-8",
        f"end_of_line = {line_endings}",
        f"insert_final_newline = {str(final_newline).lower()}",
        f"trim_trailing_whitespace = {str(trim_trailing_ws).lower()}",
        "indent_style = space",
        f"indent_size = {indent_size}",
        "",
        "[*.java]",
        f"indent_size = {indent_size}",
        "max_line_length = 120",
        "",
        "[*.{xml,yml,yaml,json}]",
        "indent_size = 2",
        "",
        "[*.{md,markdown}]",
        "trim_trailing_whitespace = false",
        "",
        "[Makefile]",
        "indent_style = tab",
        "",
    ]
    return "\n".join(lines)
