"""Runtime database capabilities exposed by DBJavaGenix."""

from ..core.models import DatabaseType


SUPPORTED_DATABASE_TYPES: tuple[DatabaseType, ...] = (
    DatabaseType.MYSQL,
    DatabaseType.POSTGRESQL,
    DatabaseType.SQLITE,
)

_DATABASE_DISPLAY_NAMES = {
    DatabaseType.MYSQL: "MySQL",
    DatabaseType.POSTGRESQL: "PostgreSQL",
    DatabaseType.SQLITE: "SQLite",
}


def supported_database_type_values() -> list[str]:
    """Return stable database type values for public tool schemas."""
    return [database_type.value for database_type in SUPPORTED_DATABASE_TYPES]


def supported_database_display_names() -> list[str]:
    """Return user-facing names for the currently implemented databases."""
    return [_DATABASE_DISPLAY_NAMES[database_type] for database_type in SUPPORTED_DATABASE_TYPES]
