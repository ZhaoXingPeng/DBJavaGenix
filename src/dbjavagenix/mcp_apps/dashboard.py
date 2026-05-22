"""
P3.2: 依赖健康仪表盘 MCP App。

把 springboot_analyze_dependencies 的输出转成结构化 dashboard 数据,
让支持 MCP Apps 的客户端渲染分区卡片 + 健康分 + 一键复制按钮。

数据结构 (mcp-apps/data):
{
  "score": 75,                              # 0-100
  "score_color": "yellow" | "green" | "red",
  "score_label": "良好",
  "sections": [
      {"title": "依赖统计", "items": [
          {"label": "Build Tool", "value": "Maven"},
          {"label": "Found Dependencies", "value": "8/10"},
          {"label": "Missing Required", "value": 1, "status": "warning"},
      ]},
      {"title": "迁移建议", "items": [
          {"name": "javax.annotation", "status": "deprecated", "target": "jakarta.annotation"},
      ]},
  ],
  "actions": [
      {"label": "复制 Maven XML", "type": "copy", "payload": "<dependencies>..."},
  ],
}
"""

from typing import Any, Dict, List


def _score_to_color(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"


def _score_to_label(score: int) -> str:
    if score >= 90:
        return "优秀"
    if score >= 70:
        return "良好"
    if score >= 50:
        return "一般"
    return "较差"


def build_dependency_dashboard_data(
    health_report: Dict[str, Any],
    migration_suggestions: List[Dict[str, Any]] = None,
    maven_xml_blocks: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从 DependencyManager 输出构建 dashboard data。

    Args:
        health_report: 形如 {build_tool, health_score, found_dependencies,
                            total_dependencies, missing_required, missing_optional}
        migration_suggestions: 形如 [{dependency, recommendation, ...}]
        maven_xml_blocks: 形如 [{description, xml}]

    Returns:
        dashboard data dict (放入 mcp-apps/data)
    """
    migration_suggestions = migration_suggestions or []
    maven_xml_blocks = maven_xml_blocks or []

    score = int(health_report.get("health_score", 0))
    color = _score_to_color(score)
    label = _score_to_label(score)

    # Section 1: 依赖统计
    found = health_report.get("found_dependencies", 0)
    total = health_report.get("total_dependencies", 0)
    missing_req = health_report.get("missing_required", 0)
    missing_opt = health_report.get("missing_optional", 0)

    deps_items: List[Dict[str, Any]] = [
        {"label": "Build Tool", "value": health_report.get("build_tool", "Unknown")},
        {"label": "Found Dependencies", "value": f"{found}/{total}"},
        {
            "label": "Missing Required",
            "value": missing_req,
            "status": "ok" if missing_req == 0 else "warning",
        },
        {
            "label": "Missing Optional",
            "value": missing_opt,
            "status": "ok" if missing_opt == 0 else "info",
        },
    ]

    sections: List[Dict[str, Any]] = [
        {"title": "依赖统计", "items": deps_items},
    ]

    # Section 2: 迁移建议
    if migration_suggestions:
        sections.append({
            "title": f"迁移建议 ({len(migration_suggestions)})",
            "items": [
                {
                    "name": s.get("dependency", "?"),
                    "status": "deprecated",
                    "target": s.get("recommendation", ""),
                }
                for s in migration_suggestions
            ],
        })

    # Actions: 一键复制完整 Maven XML
    actions: List[Dict[str, Any]] = []
    if maven_xml_blocks:
        combined_xml = _combine_maven_xml(maven_xml_blocks)
        actions.append({
            "label": f"复制 Maven Dependencies ({len(maven_xml_blocks)})",
            "type": "copy",
            "payload": combined_xml,
        })

    return {
        "score": score,
        "score_color": color,
        "score_label": label,
        "sections": sections,
        "actions": actions,
    }


def _combine_maven_xml(blocks: List[Dict[str, Any]]) -> str:
    """把多个 maven_xml block 合并成一个完整 <dependencies> 块"""
    lines = ["<dependencies>"]
    for block in blocks:
        desc = block.get("description", "").strip()
        xml = block.get("xml", "").strip()
        if not xml:
            continue
        if desc:
            lines.append(f"    <!-- {desc} -->")
        # 缩进 xml 4 spaces
        for x_line in xml.splitlines():
            lines.append(f"    {x_line}" if x_line.strip() else x_line)
        lines.append("")
    lines.append("</dependencies>")
    return "\n".join(lines)
