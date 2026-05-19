"""
Test fixtures and sample data for DBJavaGenix tests
"""
import pytest
from dbjavagenix.core.models import (
    DatabaseConfig, 
    AIConfig, 
    GenerationConfig,
    TableInfo,
    ColumnInfo,
    DatabaseType,
    AIProvider,
    CodeStyle
)


@pytest.fixture
def sample_database_config():
    """Sample database configuration"""
    return DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="localhost",
        port=3306,
        database="test_db",
        username="test_user",
        password="test_password"
    )


@pytest.fixture
def sample_ai_config():
    """Sample AI configuration"""
    return AIConfig(
        provider=AIProvider.OPENAI,
        api_key="test-api-key",
        model="gpt-3.5-turbo"
    )


@pytest.fixture
def sample_generation_config():
    """Sample generation configuration"""
    return GenerationConfig(
        output_dir="./test_output",
        package_name="com.test.example"
    )


@pytest.fixture
def sample_user_table():
    """Sample user table structure"""
    columns = [
        ColumnInfo(
            name="id",
            data_type="BIGINT",
            java_type="Long",
            primary_key=True,
            nullable=False,
            comment="Primary key"
        ),
        ColumnInfo(
            name="username",
            data_type="VARCHAR",
            java_type="String",
            max_length=50,
            nullable=False,
            comment="Username"
        ),
        ColumnInfo(
            name="email",
            data_type="VARCHAR",
            java_type="String",
            max_length=100,
            nullable=False,
            comment="Email address"
        ),
        ColumnInfo(
            name="created_at",
            data_type="DATETIME",
            java_type="LocalDateTime",
            nullable=False,
            comment="Creation timestamp"
        )
    ]
    
    return TableInfo(
        name="users",
        schema="test_db",
        columns=columns,
        primary_keys=["id"],
        comment="User information table"
    )