"""
P3.4: 包结构树 MCP App。

把生成的 java 文件列表渲染成包结构树状视图,客户端渲染折叠式树。

数据结构 (mcp-apps/data):
{
  "root": "com.example.demo",
  "children": [
    {"name": "controller", "type": "package", "children": [
        {"name": "SysUserController.java", "type": "file", "status": "new"},
    ]},
    {"name": "entity", "type": "package", "children": [...]},
    ...
  ]
}

设计:
  - status: "new" / "modified" / "unchanged" (由文件是否在目标位置已存在决定)
  - 自动从 file_path 推断 root package (公共前缀)
  - 按字母序排序 children
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


def build_package_tree_data(
    file_paths: List[str],
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """从相对 file_path 列表构建包结构树。

    Args:
        file_paths: 相对路径列表, 如 ['com/example/entity/User.java', ...]
        project_root: 可选,用于判断 status (new/modified)

    Returns:
        tree data dict
    """
    if not file_paths:
        return {"root": "", "children": []}

    # 拆分为路径段列表
    split_paths = [p.split("/") for p in file_paths if p]

    # 寻找公共前缀作为 root (仅对 java 包路径)
    java_paths = [p for p in split_paths if p[-1].endswith(".java")]
    root_segments = _common_prefix(java_paths) if java_paths else []
    root_package = ".".join(root_segments)

    # 构建树
    tree: Dict[str, Any] = {"children": {}}
    root = Path(project_root) if project_root else None
    for parts, original in zip(split_paths, file_paths):
        # 移除 root 前缀
        relative = parts[len(root_segments):] if parts[:len(root_segments)] == root_segments else parts
        _insert_into_tree(
            tree,
            relative,
            file_status=_determine_status(root, original),
        )

    return {
        "root": root_package,
        "children": _serialize_tree(tree),
    }


def _common_prefix(paths: List[List[str]]) -> List[str]:
    """计算多个路径段列表的公共前缀(不含文件名)"""
    if not paths:
        return []
    # 只对目录段求前缀,不含文件名
    dir_segments = [p[:-1] for p in paths]
    if not dir_segments or any(not d for d in dir_segments):
        return []

    prefix = list(dir_segments[0])
    for segs in dir_segments[1:]:
        new_prefix: List[str] = []
        for a, b in zip(prefix, segs):
            if a == b:
                new_prefix.append(a)
            else:
                break
        prefix = new_prefix
        if not prefix:
            break
    return prefix


def _insert_into_tree(
    node: Dict[str, Any], parts: List[str], file_status: str
) -> None:
    """把 parts 路径插入树节点"""
    if not parts:
        return
    head, *rest = parts
    children = node.setdefault("children", {})
    if not rest:
        # 文件
        children[head] = {"_file": True, "_status": file_status}
    else:
        # 目录
        child = children.setdefault(head, {})
        _insert_into_tree(child, rest, file_status)


def _serialize_tree(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把 nested dict 转成 [{name, type, status, children}, ...] 列表"""
    children = node.get("children", {})
    out: List[Dict[str, Any]] = []
    for name in sorted(children.keys()):
        child = children[name]
        if child.get("_file"):
            out.append({
                "name": name,
                "type": "file",
                "status": child.get("_status", "new"),
            })
        else:
            out.append({
                "name": name,
                "type": "package",
                "children": _serialize_tree(child),
            })
    return out


def _determine_status(project_root: Optional[Path], relative_path: str) -> str:
    """判断目标位置文件状态"""
    if not project_root:
        return "new"
    target = project_root / relative_path
    if target.exists() and target.is_file():
        return "modified"
    return "new"
