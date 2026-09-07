"""Deterministic Java identifier normalisation shared by code-generation paths."""

from __future__ import annotations

import re


# Java keywords, literals and contextual keywords that are unsafe as generated names.
JAVA_KEYWORDS = frozenset(
    {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "null",
        "_",
        # Contextual keywords used by modern Java language features.
        "module",
        "open",
        "opens",
        "provides",
        "requires",
        "to",
        "transitive",
        "uses",
        "with",
        "yield",
        "record",
        "sealed",
        "permits",
        "non-sealed",
        "var",
        "when",
    }
)

_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _words(value: str) -> list[str]:
    """Split a database name into alphanumeric words while retaining Unicode letters."""
    if not isinstance(value, str):
        return []

    # Treat every non-alphanumeric character as a separator. This keeps the original
    # database identifier untouched while ensuring generated Java names are portable.
    normalized = "".join(char if (char == "_" or char.isalnum()) else "_" for char in value)
    words: list[str] = []
    for part in normalized.split("_"):
        words.extend(piece for piece in _CAMEL_BOUNDARY_RE.split(part) if piece)
    return words


def _fallback_name(value: str) -> str:
    return "" if value == "" else "Generated"


def to_pascal_case(value: str) -> str:
    """Convert a database identifier to a valid Java-style PascalCase name."""
    words = _words(value)
    if not words:
        return _fallback_name(value)

    result = "".join(word[:1].upper() + word[1:].lower() for word in words)
    if result and result[0].isdigit():
        result = f"Generated{result}"
    return result or _fallback_name(value)


def to_camel_case(value: str) -> str:
    """Convert a database identifier to a valid Java-style camelCase name."""
    pascal = to_pascal_case(value)
    if not pascal:
        return ""

    result = pascal[:1].lower() + pascal[1:]
    if result in JAVA_KEYWORDS:
        result = f"{result}_"
    return result


def is_valid_java_identifier(value: str) -> bool:
    """Return whether *value* is a Java identifier safe for generated source."""
    return bool(value) and value != "_" and value.isidentifier() and value not in JAVA_KEYWORDS
