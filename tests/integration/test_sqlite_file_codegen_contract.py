"""File-backed SQLite coverage for metadata and code generation.

SQLite does not need Testcontainers, but an in-memory connection does not
exercise a database file's connection lifecycle. This fixture runs the public
``ConnectionManager -> DatabaseIntrospector -> CodegenAnalyzer`` path against
a temporary file and then renders the MyBatis-Plus mixed templates in memory.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from dbjavagenix.core.models import DatabaseConfig, DatabaseType
from dbjavagenix.database.codegen_tools import CodegenAnalyzer, CodegenGenerator
from dbjavagenix.database.connection_manager import ConnectionManager
from dbjavagenix.database.introspection import DatabaseIntrospector


PARENT_TABLE = "contract_parent"
CHILD_TABLE = "contract_child"
COMPOSITE_INDEX = "contract_child_parent_region_idx"


@pytest.fixture
def sqlite_file_contract(
    tmp_path: Path,
) -> Generator[dict[str, Any], None, None]:
    """Create the relational contract in a real, disposable SQLite file."""
    database_path = tmp_path / "sqlite-contract.db"
    manager = ConnectionManager()
    connection_id = manager.create_connection(
        DatabaseConfig(
            type=DatabaseType.SQLITE,
            host="",
            port=0,
            database=str(database_path),
            username="",
            password="",
        )
    )
    try:
        manager.execute_query(connection_id, "PRAGMA foreign_keys = ON")
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {PARENT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_code TEXT NOT NULL UNIQUE
            )
            """,
        )
        manager.execute_query(
            connection_id,
            f"""
            CREATE TABLE {CHILD_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NOT NULL,
                region_code TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES {PARENT_TABLE} (id)
            )
            """,
        )
        manager.execute_query(
            connection_id,
            f"CREATE INDEX {COMPOSITE_INDEX} ON {CHILD_TABLE} (parent_id, region_code)",
        )
        yield {
            "connection_id": connection_id,
            "database_path": database_path,
            "introspector": DatabaseIntrospector(manager),
            "manager": manager,
        }
    finally:
        manager.close_connection(connection_id)


@pytest.mark.asyncio
async def test_file_backed_sqlite_metadata_reaches_template_generation(
    sqlite_file_contract: dict[str, Any],
) -> None:
    fixture = sqlite_file_contract
    expected_schema = str(fixture["database_path"])
    introspector = fixture["introspector"]

    metadata = introspector.describe_table(fixture["connection_id"], CHILD_TABLE)

    assert fixture["database_path"].is_file()
    assert metadata["name"] == CHILD_TABLE
    assert metadata["schema"] == expected_schema
    assert metadata["primary_keys"] == ["id"]
    columns = {column["name"]: column for column in metadata["columns"]}
    assert {"id", "parent_id", "region_code", "created_at"} <= set(columns)
    assert columns["id"]["primary_key"] is True
    assert columns["id"]["auto_increment"] is True
    assert columns["parent_id"]["nullable"] is False
    assert columns["region_code"]["nullable"] is False
    # SQLite PRAGMA exposes a stable numeric foreign-key id, not a DDL name.
    assert metadata["foreign_keys"] == [
        {
            "constraint_name": "0",
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

    analyzer = CodegenAnalyzer(fixture["manager"])
    analysis = await analyzer.analyze_table_for_codegen(fixture["connection_id"], CHILD_TABLE)

    assert analysis["table_info"]["schema"] == expected_schema
    assert analysis["relationships"]["primary_keys"] == ["id"]
    assert analysis["relationships"]["foreign_keys"] == metadata["foreign_keys"]
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
