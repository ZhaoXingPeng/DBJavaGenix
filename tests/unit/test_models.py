"""
Test core models for DBJavaGenix
"""
import pytest
from dbjavagenix.core.models import (
    ColumnInfo, 
    TableInfo, 
    DatabaseConfig, 
    DatabaseType,
    GenerationConfig
)


def test_column_info_creation():
    """Test ColumnInfo creation"""
    column = ColumnInfo(
        name="user_id",
        data_type="BIGINT",
        java_type="Long",
        primary_key=True
    )
    
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
        password="password"
    )
    
    expected_url = "mysql+pymysql://root:password@localhost:3306/test?charset=utf8mb4"
    assert config.connection_url == expected_url