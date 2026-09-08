"""Real MySQL/PostgreSQL coverage for the normalized metadata contract.

The unit suite verifies SQL shape with stubs.  These tests exercise the same
``ConnectionManager -> DatabaseIntrospector`` path against fixed-version
Testcontainers so driver rows and database catalog behavior stay covered.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.introspection import DatabaseIntrospector


PARENT_TABLE = "contract_parent"
CHILD_TABLE = "contract_child"
POSTGRES_SCHEMA = "dbjg_contract"
COMPOSITE_INDEX = "contract_child_parent_region_idx"


def _config(container: dict[str, Any], database_type: DatabaseType) -> DatabaseConfig:
    return DatabaseConfig(
        type=database_type,
        host=container["host"],
        port=container["port"],
        database=container["database"],
        username=container["username"],
        password=container["password"],
    )


def _assert_child_metadata_contract(metadata: dict[str, Any], expected_schema: str) -> None:
    """Assert only the normalized fields shared by MySQL and PostgreSQL."""
    assert metadata["name"] == CHILD_TABLE
    assert metadata["schema"] == expected_schema
    assert metadata["primary_keys"] == ["id"]

    columns = {column["name"]: column for column in metadata["columns"]}
    assert {"id", "parent_id", "region_code", "created_at"} <= set(columns)
    assert columns["id"]["primary_key"] is True
    assert columns["id"]["auto_increment"] is True
    assert columns["parent_id"]["nullable"] is False
    assert columns["region_code"]["nullable"] is False

    assert metadata["foreign_keys"] == [
        {
            "constraint_name": "contract_child_parent_fk",
            "column_name": "parent_id",
            "referenced_table": PARENT_TABLE,
            "referenced_column": "id",
        }
    ]

    composite_index = [
        index for index in metadata["indexes"] if index["key_name"] == COMPOSITE_INDEX
    ]
    assert [(index["column_name"], index["seq_in_index"]) for index in composite_index] == [
        ("parent_id", 1),
        ("region_code", 2),
    ]
    assert all(index["unique"] is False for index in composite_index)


async def _assert_real_codegen_contract(
    fixture: dict[str, Any], expected_schema: str
) -> dict[str, Any]:
    """Exercise analysis and rendering with metadata returned by a live database."""
    analyzer = CodegenAnalyzer(fixture["introspector"].connection_manager)
    analysis = await analyzer.analyze_table_for_codegen(
        fixture["connection_id"], CHILD_TABLE, schema=expected_schema
    )

    assert analysis["table_name"] == CHILD_TABLE
    assert analysis["table_info"]["schema"] == expected_schema
    columns = {column["name"]: column for column in analysis["table_info"]["columns"]}
    assert {"id", "parent_id", "region_code", "created_at"} <= set(columns)
    assert columns["id"]["primary_key"] is True
    assert columns["id"]["auto_increment"] is True
    assert columns["parent_id"]["nullable"] is False
    assert analysis["relationships"]["primary_keys"] == ["id"]
    assert analysis["relationships"]["foreign_keys"] == [
        {
            "constraint_name": "contract_child_parent_fk",
            "column_name": "parent_id",
            "referenced_table": PARENT_TABLE,
            "referenced_column": "id",
        }
    ]
    assert analysis["template_context"]["tableName"] == CHILD_TABLE
    assert {column["name"] for column in analysis["template_context"]["columns"]} >= {
        "id",
        "parent_id",
        "region_code",
        "created_at",
    }

    generated = await CodegenGenerator().generate_code(
        analysis, template_category="MybatisPlus-Mixed"
    )

    assert generated["generation_statistics"] == {
        "total_files": 7,
        "success_files": 7,
        "error_files": 0,
    }
    assert all("error" not in file for file in generated["generated_code"].values())
    entity = generated["generated_code"]["entity.mustache"]["code"]
    assert "public class ContractChild" in entity
    assert "private Long id;" in entity
    assert "private Long parentId;" in entity

    return analysis


@pytest.fixture
def mysql_contract_metadata(
    mysql_container: dict[str, Any],
) -> Generator[dict[str, Any], None, None]:
    """Create the minimum relational fixture in the disposable MySQL database."""
    manager = ConnectionManager()
    connection_id = manager.create_connection(_config(mysql_container, DatabaseType.MYSQL))
    try:
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS {CHILD_TABLE}")
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS {PARENT_TABLE}")
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {PARENT_TABLE} (
                id BIGINT NOT NULL AUTO_INCREMENT,
                external_code VARCHAR(32) NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY contract_parent_code_uq (external_code)
            ) ENGINE=InnoDB
            """,
        )
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {CHILD_TABLE} (
                id BIGINT NOT NULL AUTO_INCREMENT,
                parent_id BIGINT NOT NULL,
                region_code VARCHAR(16) NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT contract_child_parent_fk
                    FOREIGN KEY (parent_id) REFERENCES {PARENT_TABLE} (id),
                KEY {COMPOSITE_INDEX} (parent_id, region_code)
            ) ENGINE=InnoDB
            """,
        )
        yield {
            "introspector": DatabaseIntrospector(manager),
            "connection_id": connection_id,
            "schema": mysql_container["database"],
        }
    finally:
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS {CHILD_TABLE}")
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS {PARENT_TABLE}")
        manager.close_connection(connection_id)


@pytest.fixture
def postgres_contract_metadata(
    postgres_container: dict[str, Any],
) -> Generator[dict[str, Any], None, None]:
    """Create a non-public schema plus a public homonym for schema isolation."""
    manager = ConnectionManager()
    connection_id = manager.create_connection(_config(postgres_container, DatabaseType.POSTGRESQL))
    try:
        manager.execute_query(connection_id, f"DROP SCHEMA IF EXISTS {POSTGRES_SCHEMA} CASCADE")
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS public.{CHILD_TABLE}")
        manager.execute_query(connection_id, f"CREATE SCHEMA {POSTGRES_SCHEMA}")
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {POSTGRES_SCHEMA}.{PARENT_TABLE} (
                id BIGSERIAL PRIMARY KEY,
                external_code VARCHAR(32) NOT NULL UNIQUE
            )
            """,
        )
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {POSTGRES_SCHEMA}.{CHILD_TABLE} (
                id BIGSERIAL PRIMARY KEY,
                parent_id BIGINT NOT NULL,
                region_code VARCHAR(16) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                CONSTRAINT contract_child_parent_fk
                    FOREIGN KEY (parent_id)
                    REFERENCES {POSTGRES_SCHEMA}.{PARENT_TABLE} (id)
            )
            """,
        )
        manager.execute_query(
            connection_id,
            f"CREATE INDEX {COMPOSITE_INDEX} "
            f"ON {POSTGRES_SCHEMA}.{CHILD_TABLE} (parent_id, region_code)",
        )
        manager.execute_query(
            connection_id,
            f"CREATE TABLE public.{CHILD_TABLE} (id UUID PRIMARY KEY)",
        )
        yield {
            "introspector": DatabaseIntrospector(manager),
            "connection_id": connection_id,
            "schema": POSTGRES_SCHEMA,
        }
    finally:
        manager.execute_query(connection_id, f"DROP TABLE IF EXISTS public.{CHILD_TABLE}")
        manager.execute_query(connection_id, f"DROP SCHEMA IF EXISTS {POSTGRES_SCHEMA} CASCADE")
        manager.close_connection(connection_id)


def test_mysql_describe_table_matches_real_metadata_contract(
    mysql_contract_metadata: dict[str, Any],
) -> None:
    fixture = mysql_contract_metadata
    metadata = fixture["introspector"].describe_table(fixture["connection_id"], CHILD_TABLE)

    _assert_child_metadata_contract(metadata, fixture["schema"])


def test_postgresql_describe_table_scopes_real_metadata_to_schema(
    postgres_contract_metadata: dict[str, Any],
) -> None:
    fixture = postgres_contract_metadata
    metadata = fixture["introspector"].describe_table(
        fixture["connection_id"], CHILD_TABLE, fixture["schema"]
    )

    _assert_child_metadata_contract(metadata, fixture["schema"])
    assert {column["name"] for column in metadata["columns"]} != {"id"}
    assert (
        fixture["introspector"].get_table(fixture["connection_id"], CHILD_TABLE, fixture["schema"])[
            "schema"
        ]
        == fixture["schema"]
    )


@pytest.mark.asyncio
async def test_mysql_real_metadata_reaches_template_generation(
    mysql_contract_metadata: dict[str, Any],
) -> None:
    await _assert_real_codegen_contract(mysql_contract_metadata, mysql_contract_metadata["schema"])


@pytest.mark.asyncio
async def test_postgresql_real_metadata_reaches_schema_scoped_template_generation(
    postgres_contract_metadata: dict[str, Any],
) -> None:
    fixture = postgres_contract_metadata
    analysis = await _assert_real_codegen_contract(fixture, fixture["schema"])

    # ``public.contract_child`` only has a UUID id; these fields prove the
    # non-public relation was analyzed and passed to the renderer.
    assert {column["name"] for column in analysis["table_info"]["columns"]} != {"id"}
