"""单元测试: mcp_apps.er_diagram + mcp_apps.meta_builder (P3.1)

测试:
- render_er_diagram 输出 Mermaid 语法 (正常 / 单表 / 含 FK)
- render_summary_text 文本摘要
- _safe_identifier 处理特殊字符
- meta_builder 命名空间前缀 + attach/merge 语义
"""

import pytest
from mcp.types import TextContent

from dbjavagenix.mcp_apps.er_diagram import (
    ERColumn,
    ERForeignKey,
    ERTable,
    _safe_identifier,
    _safe_type,
    render_er_diagram,
    render_summary_text,
)
from dbjavagenix.mcp_apps.meta_builder import (
    attach_meta,
    build_mcp_app_meta,
    merge_meta,
    with_meta_list,
)


# ============================================================
# er_diagram
# ============================================================

@pytest.fixture
def rbac_tables():
    return [
        ERTable(name="sys_user", columns=[
            ERColumn("id", "BIGINT", is_primary=True),
            ERColumn("username", "VARCHAR(64)"),
        ]),
        ERTable(name="sys_role", columns=[
            ERColumn("id", "BIGINT", is_primary=True),
            ERColumn("name", "VARCHAR(64)"),
        ]),
        ERTable(name="sys_user_role", columns=[
            ERColumn("id", "BIGINT", is_primary=True),
            ERColumn("user_id", "BIGINT", is_foreign=True),
            ERColumn("role_id", "BIGINT", is_foreign=True),
        ]),
    ]


@pytest.fixture
def rbac_fks():
    return [
        ERForeignKey("sys_user_role", "user_id", "sys_user", "id"),
        ERForeignKey("sys_user_role", "role_id", "sys_role", "id"),
    ]


class TestRenderErDiagram:
    def test_starts_with_erDiagram(self, rbac_tables, rbac_fks):
        src = render_er_diagram(rbac_tables, rbac_fks)
        assert src.startswith("erDiagram")

    def test_includes_all_tables_uppercase(self, rbac_tables, rbac_fks):
        src = render_er_diagram(rbac_tables, rbac_fks)
        assert "SYS_USER" in src
        assert "SYS_ROLE" in src
        assert "SYS_USER_ROLE" in src

    def test_marks_pk_columns(self, rbac_tables, rbac_fks):
        src = render_er_diagram(rbac_tables, rbac_fks)
        assert "id PK" in src

    def test_marks_fk_columns(self, rbac_tables, rbac_fks):
        src = render_er_diagram(rbac_tables, rbac_fks)
        assert "user_id FK" in src
        assert "role_id FK" in src

    def test_renders_relationships(self, rbac_tables, rbac_fks):
        src = render_er_diagram(rbac_tables, rbac_fks)
        # Many-to-one cardinality + from→to comment
        assert "SYS_USER_ROLE }o--|| SYS_USER" in src
        assert "user_id → id" in src

    def test_empty_tables_raises(self):
        with pytest.raises(ValueError, match="at least one table"):
            render_er_diagram([], [])

    def test_no_foreign_keys_ok(self, rbac_tables):
        src = render_er_diagram(rbac_tables, [])
        assert "erDiagram" in src
        # No relationship lines
        assert "}o--||" not in src

    def test_handles_special_chars_in_table_name(self):
        table = ERTable(
            name="weird-table.name",
            columns=[ERColumn("id", "BIGINT", is_primary=True)],
        )
        src = render_er_diagram([table], [])
        # Special chars replaced with underscores
        assert "WEIRD_TABLE_NAME" in src

    def test_type_with_spaces_is_sanitized(self):
        table = ERTable(
            name="t",
            columns=[ERColumn("col", "DECIMAL ( 10, 2 )")],
        )
        src = render_er_diagram([table], [])
        # No spaces inside type token (would break mermaid)
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("DECIMAL") and "col" in stripped:
                # 类型部分必须无空格
                type_part = stripped.split(" col")[0]
                assert " " not in type_part


class TestSafeIdentifier:
    @pytest.mark.parametrize("input_,expected", [
        ("user", "USER"),
        ("sys_user", "SYS_USER"),
        ("weird-name", "WEIRD_NAME"),
        ("MixedCase", "MIXEDCASE"),
        ("a.b", "A_B"),
    ])
    def test_sanitization(self, input_, expected):
        assert _safe_identifier(input_) == expected


class TestSafeType:
    def test_strips_internal_spaces(self):
        assert _safe_type("DECIMAL ( 10, 2 )") == "DECIMAL_(_10,_2_)"

    def test_trims_outer_whitespace(self):
        assert _safe_type("  BIGINT  ") == "BIGINT"


class TestRenderSummary:
    def test_includes_table_count(self, rbac_tables, rbac_fks):
        txt = render_summary_text(rbac_tables, rbac_fks)
        assert "3 tables" in txt
        assert "2 foreign keys" in txt

    def test_lists_each_table(self, rbac_tables):
        txt = render_summary_text(rbac_tables, [])
        for tbl in rbac_tables:
            assert tbl.name in txt

    def test_no_fk_section_when_empty(self, rbac_tables):
        txt = render_summary_text(rbac_tables, [])
        assert "Relationships" not in txt


# ============================================================
# meta_builder
# ============================================================

class TestBuildMcpAppMeta:
    def test_basic(self):
        meta = build_mcp_app_meta("mermaid", source="erDiagram\n  X")
        assert meta == {
            "mcp-apps/component": "mermaid",
            "mcp-apps/source": "erDiagram\n  X",
        }

    def test_namespace_prefix_only_when_missing(self):
        # Already namespaced key → kept as-is
        meta = build_mcp_app_meta(
            "dashboard", **{"mcp-apps/data": {"score": 80}}
        )
        assert meta == {
            "mcp-apps/component": "dashboard",
            "mcp-apps/data": {"score": 80},
        }

    def test_skips_none_values(self):
        meta = build_mcp_app_meta("code-diff", before=None, after="public class X{}")
        assert "mcp-apps/before" not in meta
        assert "mcp-apps/after" in meta


class TestAttachMeta:
    def test_attach_returns_new_object(self):
        content = TextContent(type="text", text="hello")
        meta = {"mcp-apps/component": "mermaid"}
        attached = attach_meta(content, meta)
        assert attached.meta == meta
        # Original unchanged
        assert content.meta is None

    def test_attach_replaces_existing_meta(self):
        content = TextContent(type="text", text="x", meta={"a": 1})
        attached = attach_meta(content, {"b": 2})
        assert attached.meta == {"b": 2}


class TestMergeMeta:
    def test_merge_none_existing(self):
        assert merge_meta(None, {"a": 1}) == {"a": 1}

    def test_merge_overrides(self):
        assert merge_meta({"a": 1}, {"a": 2, "b": 3}) == {"a": 2, "b": 3}


class TestWithMetaList:
    def test_attaches_to_first_content(self):
        contents = [
            TextContent(type="text", text="head"),
            TextContent(type="text", text="tail"),
        ]
        meta = {"mcp-apps/component": "mermaid"}
        out = with_meta_list(contents, meta)
        assert out[0].meta == meta
        assert out[1].meta is None

    def test_empty_list_safe(self):
        assert with_meta_list([], {"a": 1}) == []
