"""MCP tool: generate Java engineering-standards configuration files.

Wraps the four `dbjavagenix.standards` generators into a single MCP tool that
produces a bundle of config files at the project root.

Returns a structured payload listing each generated file's path and content
(does not write to disk — that's the client's responsibility / can be done
through another tool with explicit user confirmation).
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent, Tool

from ..standards import (
    generate_checkstyle_xml,
    generate_editorconfig,
    generate_lombok_config,
    generate_spotbugs_exclude_xml,
    generate_suppressions_xml,
)
from ..utils.json_serialization import dumps as _json_dumps


STANDARDS_GENERATE_TOOL = Tool(
    name="springboot_generate_quality_configs",
    description=(
        "Generate Java engineering-standards config bundle (Checkstyle XML, "
        "SpotBugs exclude XML, .editorconfig, lombok.config). Returns each "
        "file's suggested path and content as a JSON payload. Caller decides "
        "whether to write to disk."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "checkstyle_line_limit": {
                "type": "integer",
                "default": 120,
                "minimum": 80,
                "maximum": 200,
            },
            "checkstyle_indent": {
                "type": "integer",
                "default": 4,
                "minimum": 2,
                "maximum": 8,
            },
            "editorconfig_line_endings": {
                "type": "string",
                "enum": ["lf", "crlf"],
                "default": "lf",
            },
            "lombok_accessors_chain": {
                "type": "boolean",
                "default": False,
                "description": "If true, setters return `this` (builder-like)",
            },
            "include_files": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "checkstyle",
                        "checkstyle_suppressions",
                        "spotbugs",
                        "editorconfig",
                        "lombok",
                    ],
                },
                "description": "Which config files to include in the bundle. "
                "Omit or empty list -> all five.",
            },
        },
    },
)


_FILE_PATHS = {
    "checkstyle": "config/checkstyle/checkstyle.xml",
    "checkstyle_suppressions": "config/checkstyle/checkstyle-suppressions.xml",
    "spotbugs": "config/spotbugs/spotbugs-exclude.xml",
    "editorconfig": ".editorconfig",
    "lombok": "lombok.config",
}


async def handle_generate_quality_configs(
    arguments: dict[str, Any],
) -> list[TextContent]:
    line_limit = int(arguments.get("checkstyle_line_limit", 120))
    indent = int(arguments.get("checkstyle_indent", 4))
    line_endings = arguments.get("editorconfig_line_endings", "lf")
    accessors_chain = bool(arguments.get("lombok_accessors_chain", False))
    include = arguments.get("include_files")
    if not include:
        include = list(_FILE_PATHS.keys())

    files: list[dict[str, str]] = []
    if "checkstyle" in include:
        files.append(
            {
                "path": _FILE_PATHS["checkstyle"],
                "language": "xml",
                "content": generate_checkstyle_xml(line_limit=line_limit, indent=indent),
            }
        )
    if "checkstyle_suppressions" in include:
        files.append(
            {
                "path": _FILE_PATHS["checkstyle_suppressions"],
                "language": "xml",
                "content": generate_suppressions_xml(),
            }
        )
    if "spotbugs" in include:
        files.append(
            {
                "path": _FILE_PATHS["spotbugs"],
                "language": "xml",
                "content": generate_spotbugs_exclude_xml(),
            }
        )
    if "editorconfig" in include:
        files.append(
            {
                "path": _FILE_PATHS["editorconfig"],
                "language": "editorconfig",
                "content": generate_editorconfig(line_endings=line_endings),
            }
        )
    if "lombok" in include:
        files.append(
            {
                "path": _FILE_PATHS["lombok"],
                "language": "properties",
                "content": generate_lombok_config(accessors_chain=accessors_chain),
            }
        )

    payload = {
        "file_count": len(files),
        "files": files,
        "instructions": (
            "Write each file's content to the corresponding `path` at the "
            "project root. Then add maven-checkstyle-plugin and "
            "spotbugs-maven-plugin to your pom.xml."
        ),
    }
    return [
        TextContent(
            type="text",
            text=_json_dumps(payload, indent=2),
        )
    ]


STANDARDS_TOOLS = [STANDARDS_GENERATE_TOOL]

STANDARDS_HANDLERS = {
    "springboot_generate_quality_configs": handle_generate_quality_configs,
}
