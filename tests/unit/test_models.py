"""
Test core models for DBJavaGenix
"""

import pytest
from dbjavagenix.config.config_manager import ConfigManager
from dbjavagenix.core.models import (
    ColumnInfo,
    TableInfo,
    DatabaseConfig,
    DatabaseType,
    GenerationConfig,
)


def test_column_info_creation():
    """Test ColumnInfo creation"""
    column = ColumnInfo(name="user_id", data_type="BIGINT", java_type="Long", primary_key=True)

    assert column.name == "user_id"
    assert column.java_type == "Long"
    assert column.primary_key is True


def test_table_info_entity_name():
    """Test TableInfo entity name conversion"""
    table = TableInfo(name="user_profiles", schema="test")
    assert table.entity_name == "UserProfiles"


def test_database_config_connection_url():
    """Test DatabaseConfig connection URL generation"""
    config = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="localhost",
        port=3306,
        database="test",
        username="root",
        password="password",
    )

    expected_url = "mysql+pymysql://root:password@localhost:3306/test?charset=utf8mb4"
    assert config.connection_url == expected_url


def test_database_config_connection_url_round_trips_special_mysql_components():
    config = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="db.internal",
        port=3306,
        database="app/core",
        username="reader+svc",
        password="p@ss/#?word",
        charset="utf8mb4",
    )

    parsed = ConfigManager._parse_database_url(config.connection_url)

    assert parsed["database"] == config.database
    assert parsed["username"] == config.username
    assert parsed["password"] == config.password
    assert parsed["charset"] == config.charset


def test_database_config_connection_url_round_trips_sqlite_path():
    config = DatabaseConfig(
        type=DatabaseType.SQLITE,
        host="",
        port=0,
        database="fixtures/demo#1.db",
        username="",
        password="",
    )

    parsed = ConfigManager._parse_database_url(config.connection_url)

    assert parsed["database"] == config.database
