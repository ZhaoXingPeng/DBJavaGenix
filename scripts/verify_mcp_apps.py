"""脚本: 验证 4 个 MCP App 组件的 _meta 字段在 server 响应中正确出现。

不需要真实数据库 — 直接调用各 handler 用 mock context,检查返回的 TextContent.meta。

用法:
    PYTHONPATH=src python scripts/verify_mcp_apps.py

退出码:
    0 = 4 个组件全部验证通过
    1 = 任一组件 meta 缺失或结构错误
"""

import asyncio
import json
import sys
from pathlib import Path

# 让 src/ 可被 import
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def assert_meta_has(meta, key, label):
    if not meta:
        raise AssertionError(f"{label}: meta is empty/None")
    if key not in meta:
        raise AssertionError(f"{label}: missing meta key {key!r} (keys: {list(meta.keys())})")


async def verify_er_diagram():
    """P3.1: ER 图 mermaid 组件"""
    from dbjavagenix.mcp_apps.er_diagram import (
        ERColumn, ERForeignKey, ERTable, render_er_diagram, render_summary_text,
    )
    from dbjavagenix.mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
    from mcp.types import TextContent

    tables = [
        ERTable("sys_user", [ERColumn("id", "BIGINT", is_primary=True)]),
        ERTable("sys_role", [ERColumn("id", "BIGINT", is_primary=True)]),
    ]
    fks = [ERForeignKey("sys_user", "role_id", "sys_role", "id")]
    source = render_er_diagram(tables, fks)
    meta = build_mcp_app_meta("mermaid", source=source, version="1.0")
    content = attach_meta(TextContent(type="text", text=render_summary_text(tables, fks)), meta)

    assert_meta_has(content.meta, "mcp-apps/component", "ER diagram")
    assert content.meta["mcp-apps/component"] == "mermaid"
    assert_meta_has(content.meta, "mcp-apps/source", "ER diagram")
    print(f"  [OK] er_diagram: component=mermaid, source={len(source)} chars")


async def verify_dashboard():
    """P3.2: dashboard 组件"""
    from dbjavagenix.mcp_apps.dashboard import build_dependency_dashboard_data
    from dbjavagenix.mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
    from mcp.types import TextContent

    health = {
        "build_tool": "Maven",
        "health_score": 75,
        "found_dependencies": 8,
        "total_dependencies": 10,
        "missing_required": 1,
        "missing_optional": 1,
    }
    data = build_dependency_dashboard_data(health, [], [])
    meta = build_mcp_app_meta("dashboard", version="1.0", data=data)
    content = attach_meta(TextContent(type="text", text="dependency analysis"), meta)

    assert content.meta["mcp-apps/component"] == "dashboard"
    assert_meta_has(content.meta, "mcp-apps/data", "dashboard")
    payload = content.meta["mcp-apps/data"]
    for required in ("score", "score_color", "score_label", "sections"):
        assert required in payload, f"dashboard payload missing {required}"
    print(f"  [OK] dashboard: score={payload['score']} sections={len(payload['sections'])}")


async def verify_code_diff():
    """P3.3: code-diff 组件"""
    from dbjavagenix.mcp_apps.code_diff import build_code_diff_data
    from dbjavagenix.mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
    from mcp.types import TextContent

    files = [
        {
            "template_file": "entity.mustache",
            "file_path": "com/example/entity/User.java",
            "code": "public class User {}",
            "lines": 1,
        }
    ]
    data = build_code_diff_data(files)
    meta = build_mcp_app_meta("code-diff", language="java", files=data["files"], version="1.0")
    content = attach_meta(TextContent(type="text", text="rendered"), meta)

    assert content.meta["mcp-apps/component"] == "code-diff"
    assert content.meta["mcp-apps/language"] == "java"
    assert_meta_has(content.meta, "mcp-apps/files", "code-diff")
    assert len(content.meta["mcp-apps/files"]) == 1
    print(f"  [OK] code-diff: language=java, files={len(content.meta['mcp-apps/files'])}")


async def verify_package_tree():
    """P3.4: tree 组件"""
    from dbjavagenix.mcp_apps.meta_builder import attach_meta, build_mcp_app_meta
    from dbjavagenix.mcp_apps.package_tree import build_package_tree_data
    from mcp.types import TextContent

    file_paths = [
        "com/example/entity/User.java",
        "com/example/entity/Role.java",
        "com/example/dao/UserDao.java",
        "com/example/service/impl/UserServiceImpl.java",
    ]
    data = build_package_tree_data(file_paths)
    meta = build_mcp_app_meta("tree", version="1.0", data=data)
    content = attach_meta(TextContent(type="text", text="generated"), meta)

    assert content.meta["mcp-apps/component"] == "tree"
    payload = content.meta["mcp-apps/data"]
    assert payload["root"] == "com.example"
    assert len(payload["children"]) >= 3
    print(f"  [OK] tree: root={payload['root']}, top-level children={len(payload['children'])}")


async def verify_all():
    checks = [
        ("ER Diagram (P3.1)", verify_er_diagram),
        ("Dependency Dashboard (P3.2)", verify_dashboard),
        ("Code Diff (P3.3)", verify_code_diff),
        ("Package Tree (P3.4)", verify_package_tree),
    ]
    failed = 0
    for label, fn in checks:
        print(f"\n[*] {label}")
        try:
            await fn()
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"=== {len(checks) - failed}/{len(checks)} components verified ===")
    return failed


def main():
    failed = asyncio.run(verify_all())
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
