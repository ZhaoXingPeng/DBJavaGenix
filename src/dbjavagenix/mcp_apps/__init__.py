"""
P3: MCP Apps - 把 MCP 工具的返回值附加 UI 渲染指令。

设计:
  - 每个 MCP App 是一个 pure function: 接受数据,返回 _meta dict
  - 客户端(支持 MCP Apps 规范的)读取 _meta 渲染 UI 组件
  - 不支持的客户端忽略 _meta,只看 text content (向后兼容)

包内模块:
  - er_diagram      : ER 图 (mermaid 组件)
  - dashboard       : 依赖健康仪表盘
  - code_diff       : 代码 diff 预览
  - package_tree    : 包结构树
  - meta_builder    : 共用辅助 (附加 meta 到 TextContent)
"""

from .meta_builder import attach_meta, build_mcp_app_meta

__all__ = ["attach_meta", "build_mcp_app_meta"]
