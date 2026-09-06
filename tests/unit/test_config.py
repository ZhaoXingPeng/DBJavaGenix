"""
Test configuration for DBJavaGenix
"""

import pytest
from dbjavagenix.config.config_manager import ConfigManager
from dbjavagenix.core.exceptions import ConfigurationError
from dbjavagenix.core.models import DatabaseType, AIProvider, CodeStyle


def test_config_manager_initialization():
    """Test ConfigManager initialization"""
    config_manager = ConfigManager()
    assert config_manager is not None


def test_create_default_config():
    """Test creating default configuration"""
    config_manager = ConfigManager()
    config = config_manager.create_default_config()

    assert config.database.type == DatabaseType.MYSQL
    assert config.ai.provider == AIProvider.OPENAI
    assert config.generation.code_style == CodeStyle.SPRING_BOOT


@pytest.mark.parametrize(
    ("database_url", "database_type", "host", "port", "database", "username", "password"),
    [
        (
            "mysql://reader:p%40ss@db.internal/app?charset=utf8mb4",
            DatabaseType.MYSQL,
            "db.internal",
            3306,
            "app",
            "reader",
            "p@ss",
        ),
        (
            "postgresql://reader:p%40ss@db.internal/app",
            DatabaseType.POSTGRESQL,
            "db.internal",
            5432,
            "app",
            "reader",
            "p@ss",
        ),
        ("sqlite:///:memory:", DatabaseType.SQLITE, "", 0, ":memory:", "", ""),
    ],
)
def test_database_url_override_is_parsed(
    monkeypatch,
    database_url,
    database_type,
    host,
    port,
    database,
    username,
    password,
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    parsed = ConfigManager()._apply_env_overrides({"database": {}})["database"]

    assert parsed["type"] == database_type.value
    assert parsed["host"] == host
    assert parsed["port"] == port
    assert parsed["database"] == database
    assert parsed["username"] == username
    assert parsed["password"] == password


def test_database_url_override_rejects_unknown_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "oracle://reader:secret@db.internal/app")

    with pytest.raises(ConfigurationError, match="scheme"):
        ConfigManager()._apply_env_overrides({"database": {}})
