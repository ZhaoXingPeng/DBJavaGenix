"""Java engineering-standards config generators.

Generates per-project Checkstyle / SpotBugs / EditorConfig / Lombok
configurations following Google Java Style with project-specific tweaks.

The MCP tool wrapper lives in `dbjavagenix.database.standards_tools`.
"""

from .checkstyle import generate_checkstyle_xml, generate_suppressions_xml
from .editorconfig import generate_editorconfig
from .lombok import generate_lombok_config
from .spotbugs import generate_spotbugs_exclude_xml

__all__ = [
    "generate_checkstyle_xml",
    "generate_suppressions_xml",
    "generate_spotbugs_exclude_xml",
    "generate_editorconfig",
    "generate_lombok_config",
]
