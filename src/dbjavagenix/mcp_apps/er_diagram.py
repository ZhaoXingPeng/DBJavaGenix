"""
P3.1: ER 图 MCP App - 把表关系转成 Mermaid erDiagram 源码。

生成的 mermaid 源码示例:

    erDiagram
        SYS_USER {
            BIGINT id PK
            VARCHAR(64) username
        }
        SYS_ROLE {
            BIGINT id PK
            VARCHAR(64) name
        }
        SYS_USER_ROLE {
            BIGINT id PK
            BIGINT user_id FK
            BIGINT role_id FK
        }
        SYS_USER_ROLE }o--|| SYS_USER : "user_id → id"
        SYS_USER_ROLE }o--|| SYS_ROLE : "role_id → id"

设计:
  - 输入纯 Python 数据 (List[TableSchema], List[ForeignKey]),无 IO
  - 自动 sanitize 表名 (大小写、特殊字符) 以适配 Mermaid 语法
  - 处理空数据 / 单表无 FK 的退化情况
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ERColumn:
    name: str
    type: str
    is_primary: bool = False
    is_foreign: bool = False


@dataclass(frozen=True)
class ERTable:
    name: str
    columns: List[ERColumn] = field(default_factory=list)


@dataclass(frozen=True)
class ERForeignKey:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "}o--||"  # default: many-to-one


# Mermaid 标识符: 字母 / 数字 / 下划线
_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]")


def _safe_identifier(name: str) -> str:
    """把表名/列名转为 Mermaid 兼容标识符 (大写, 替换非法字符)"""
    return _IDENTIFIER_RE.sub("_", name).upper()


def _safe_type(type_str: str) -> str:
    """Mermaid 类型字段必须连续 (不能含空格)。VARCHAR(64) → VARCHAR_64_"""
    # Mermaid 实际支持括号,但保留小心起见简化
    return re.sub(r"\s+", "_", type_str.strip())


def render_er_diagram(
    tables: List[ERTable], foreign_keys: Optional[List[ERForeignKey]] = None
) -> str:
    """生成 Mermaid erDiagram 源码字符串。

    Args:
        tables: 表结构列表
        foreign_keys: 跨表关系 (可为空,此时只渲染表块)

    Returns:
        Mermaid 源码字符串 (以 'erDiagram' 开头)

    Raises:
        ValueError: 当 tables 为空
    """
    if not tables:
        raise ValueError("render_er_diagram: at least one table required")

    fks = foreign_keys or []

    lines: List[str] = ["erDiagram"]
    for tbl in tables:
        lines.append(f"    {_safe_identifier(tbl.name)} {{")
        for col in tbl.columns:
            marker = ""
            if col.is_primary:
                marker = " PK"
            elif col.is_foreign:
                marker = " FK"
            lines.append(
                f"        {_safe_type(col.type)} {col.name}{marker}"
            )
        lines.append("    }")

    for fk in fks:
        lines.append(
            f"    {_safe_identifier(fk.from_table)} "
            f"{fk.cardinality} "
            f"{_safe_identifier(fk.to_table)} : "
            f'"{fk.from_column} → {fk.to_column}"'
        )

    return "\n".join(lines)


def render_summary_text(
    tables: List[ERTable], foreign_keys: Optional[List[ERForeignKey]] = None
) -> str:
    """生成纯文本摘要 (作为不支持 mcp-apps 客户端的 fallback)"""
    fks = foreign_keys or []
    lines: List[str] = [
        f"ER diagram: {len(tables)} tables, {len(fks)} foreign keys",
        "",
    ]
    for tbl in tables:
        pk = next((c.name for c in tbl.columns if c.is_primary), "(no PK)")
        lines.append(f"  • {tbl.name}  PK={pk}  ({len(tbl.columns)} columns)")
    if fks:
        lines.append("")
        lines.append("Relationships:")
        for fk in fks:
            lines.append(
                f"  • {fk.from_table}.{fk.from_column} → {fk.to_table}.{fk.to_column}"
            )
    return "\n".join(lines)
