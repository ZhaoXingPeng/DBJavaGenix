"""
P3.3: 代码预览 + Diff MCP App。

把 codegen_render_* 输出的代码附加 code-diff 元数据,客户端渲染:
- 语法高亮 (java)
- 与目标位置已有文件的 diff (before/after)
- 文件路径

数据结构 (mcp-apps/data 或独立字段):
{
  "mcp-apps/component": "code-diff",
  "mcp-apps/language": "java",
  "mcp-apps/files": [
      {
          "file_path": "com/example/entity/SysUser.java",
          "before": null | "<existing content>",
          "after": "<generated code>",
      },
      ...
  ],
}

为何放 files 数组而非单文件:
- codegen_render_service 会生成 service.mustache + serviceImpl.mustache 两个文件
- code-diff 组件支持 tabs / 折叠多文件
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


def build_code_diff_data(
    files: List[Dict[str, Any]],
    language: str = "java",
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """从 render_* 工具的 files 列表构建 code-diff data。

    Args:
        files: 每项至少含 {code, file_path, template_file}, 错误项含 {error}
        language: 语法高亮语言, 默认 java
        project_root: 可选,用于解析 before 文件 (从磁盘读)。
                      为 None 时不做磁盘查找,before 全部为 null。

    Returns:
        {"language": "java", "files": [{file_path, before, after, template_file}]}
    """
    diff_files: List[Dict[str, Any]] = []
    root = Path(project_root) if project_root else None

    for entry in files:
        # 跳过错误项
        if "error" in entry or "code" not in entry:
            continue

        file_path = entry.get("file_path", "")
        after = entry.get("code", "")
        before = _try_read_existing(root, file_path) if root else None

        diff_files.append({
            "file_path": file_path,
            "template_file": entry.get("template_file"),
            "before": before,
            "after": after,
            "lines": entry.get("lines"),
        })

    return {
        "language": language,
        "files": diff_files,
    }


def _try_read_existing(root: Path, relative_path: str) -> Optional[str]:
    """尝试读取目标位置已有文件,返回字符串或 None"""
    if not relative_path:
        return None
    try:
        target = root / relative_path
        if not target.exists() or not target.is_file():
            return None
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
