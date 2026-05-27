"""Google Checkstyle configuration generator with project-specific tweaks.

Produces a `checkstyle.xml` based on Google Java Style with:
- Line limit configurable (default 120, slightly wider than Google's 100 to
  accommodate Mustache template expansions that can be wide)
- Indent configurable (default 4)
- Optional generated-code suppression filter
"""

from __future__ import annotations

DEFAULT_LINE_LIMIT = 120
DEFAULT_INDENT = 4


def generate_checkstyle_xml(
    line_limit: int = DEFAULT_LINE_LIMIT,
    indent: int = DEFAULT_INDENT,
    suppress_generated: bool = True,
) -> str:
    """Generate a checkstyle.xml configuration content.

    Args:
        line_limit: maximum line length in characters
        indent: number of spaces per indent level
        suppress_generated: whether to add a suppression filter for
            paths containing /generated/ (typical for auto-generated DAOs)

    Returns:
        XML content (with trailing newline). Save to e.g.
        `config/checkstyle/checkstyle.xml` for `maven-checkstyle-plugin`.
    """
    lines = [
        '<?xml version="1.0"?>',
        '<!DOCTYPE module PUBLIC',
        '    "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"',
        '    "https://checkstyle.org/dtds/configuration_1_3.dtd">',
        '<module name="Checker">',
        '    <property name="charset" value="UTF-8"/>',
        '    <property name="severity" value="warning"/>',
        '    <property name="fileExtensions" value="java, properties, xml"/>',
        '',
        '    <module name="LineLength">',
        f'        <property name="max" value="{line_limit}"/>',
        '    </module>',
        '',
        '    <module name="TreeWalker">',
        '        <!-- Naming -->',
        '        <module name="ConstantName"/>',
        '        <module name="LocalVariableName"/>',
        '        <module name="MemberName"/>',
        '        <module name="MethodName"/>',
        '        <module name="ParameterName"/>',
        '        <module name="StaticVariableName"/>',
        '        <module name="TypeName"/>',
        '',
        '        <!-- Imports -->',
        '        <module name="AvoidStarImport"/>',
        '        <module name="IllegalImport"/>',
        '        <module name="RedundantImport"/>',
        '        <module name="UnusedImports"/>',
        '',
        '        <!-- Whitespace & blocks -->',
        '        <module name="Indentation">',
        f'            <property name="basicOffset" value="{indent}"/>',
        '        </module>',
        '        <module name="EmptyBlock"/>',
        '        <module name="NeedBraces"/>',
        '',
        '        <!-- Common best practices -->',
        '        <module name="MissingOverride"/>',
        '        <module name="EqualsHashCode"/>',
        '        <module name="StringLiteralEquality"/>',
        '    </module>',
        '',
    ]
    if suppress_generated:
        lines.extend(
            [
                '    <module name="SuppressionFilter">',
                '        <property name="file" value="${config_loc}/checkstyle-suppressions.xml"/>',
                '        <property name="optional" value="true"/>',
                '    </module>',
                '',
            ]
        )
    lines.append('</module>')
    return "\n".join(lines) + "\n"


def generate_suppressions_xml(
    paths_to_suppress: list[str] | None = None,
) -> str:
    """Generate checkstyle-suppressions.xml to exclude paths.

    Args:
        paths_to_suppress: list of regex patterns for paths to exclude.
            Default suppresses generated/ directories.
    """
    paths = paths_to_suppress or [r".*[\\/]generated[\\/].*"]
    lines = [
        '<?xml version="1.0"?>',
        '<!DOCTYPE suppressions PUBLIC',
        '    "-//Checkstyle//DTD SuppressionFilter Configuration 1.2//EN"',
        '    "https://checkstyle.org/dtds/suppressions_1_2.dtd">',
        '<suppressions>',
    ]
    for path in paths:
        lines.append(f'    <suppress checks=".*" files="{path}"/>')
    lines.append('</suppressions>')
    return "\n".join(lines) + "\n"
