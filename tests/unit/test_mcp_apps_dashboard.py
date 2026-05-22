"""单元测试: mcp_apps.dashboard (P3.2)

测试:
- _score_to_color / _score_to_label 边界值
- build_dependency_dashboard_data 分区结构
- 缺失迁移建议时不输出该 section
- 缺失 maven_xml 时无 actions
- _combine_maven_xml 缩进 + 注释
"""

import pytest

from dbjavagenix.mcp_apps.dashboard import (
    _combine_maven_xml,
    _score_to_color,
    _score_to_label,
    build_dependency_dashboard_data,
)


class TestScoreToColor:
    @pytest.mark.parametrize("score,color", [
        (100, "green"),
        (90, "green"),
        (80, "green"),
        (79, "yellow"),
        (70, "yellow"),
        (60, "yellow"),
        (59, "red"),
        (30, "red"),
        (0, "red"),
    ])
    def test_color(self, score, color):
        assert _score_to_color(score) == color


class TestScoreToLabel:
    @pytest.mark.parametrize("score,label", [
        (95, "优秀"),
        (90, "优秀"),
        (89, "良好"),
        (70, "良好"),
        (69, "一般"),
        (50, "一般"),
        (49, "较差"),
        (0, "较差"),
    ])
    def test_label(self, score, label):
        assert _score_to_label(score) == label


class TestBuildDashboard:
    def test_basic_structure(self):
        health = {
            "build_tool": "Maven",
            "health_score": 75,
            "found_dependencies": 8,
            "total_dependencies": 10,
            "missing_required": 1,
            "missing_optional": 1,
        }
        data = build_dependency_dashboard_data(health, [], [])
        assert data["score"] == 75
        assert data["score_color"] == "yellow"
        assert data["score_label"] == "良好"
        assert len(data["sections"]) == 1  # only 依赖统计
        assert data["sections"][0]["title"] == "依赖统计"
        assert data["actions"] == []

    def test_missing_required_warning_status(self):
        health = {"health_score": 90, "missing_required": 2, "missing_optional": 0}
        data = build_dependency_dashboard_data(health)
        deps_section = data["sections"][0]
        missing_req_item = next(
            i for i in deps_section["items"] if i["label"] == "Missing Required"
        )
        assert missing_req_item["status"] == "warning"
        assert missing_req_item["value"] == 2

    def test_all_zero_missing_is_ok(self):
        health = {"health_score": 100, "missing_required": 0, "missing_optional": 0}
        data = build_dependency_dashboard_data(health)
        items = data["sections"][0]["items"]
        for item in items:
            if item["label"] in ("Missing Required", "Missing Optional"):
                assert item["status"] == "ok"

    def test_migration_suggestions_section_added(self):
        health = {"health_score": 60}
        migrations = [
            {"dependency": "javax.annotation", "recommendation": "jakarta.annotation"},
            {"dependency": "springfox", "recommendation": "springdoc-openapi"},
        ]
        data = build_dependency_dashboard_data(health, migrations, [])
        # 应有 2 个 section: 依赖统计 + 迁移建议
        assert len(data["sections"]) == 2
        migration_section = data["sections"][1]
        assert "迁移建议" in migration_section["title"]
        assert "(2)" in migration_section["title"]
        items = migration_section["items"]
        assert len(items) == 2
        assert items[0]["name"] == "javax.annotation"
        assert items[0]["target"] == "jakarta.annotation"
        assert items[0]["status"] == "deprecated"

    def test_actions_added_when_maven_xml(self):
        health = {"health_score": 60}
        maven_xml = [
            {"description": "mysql driver", "xml": "<dependency>x</dependency>"},
        ]
        data = build_dependency_dashboard_data(health, [], maven_xml)
        assert len(data["actions"]) == 1
        action = data["actions"][0]
        assert action["type"] == "copy"
        assert "复制" in action["label"]
        assert "(1)" in action["label"]
        assert "<dependencies>" in action["payload"]
        assert "<dependency>x</dependency>" in action["payload"]

    def test_default_unknown_build_tool(self):
        data = build_dependency_dashboard_data({"health_score": 50})
        build_tool_item = next(
            i for i in data["sections"][0]["items"] if i["label"] == "Build Tool"
        )
        assert build_tool_item["value"] == "Unknown"


class TestCombineMavenXml:
    def test_single_block(self):
        out = _combine_maven_xml([
            {"description": "test", "xml": "<dependency>X</dependency>"}
        ])
        assert out.startswith("<dependencies>")
        assert out.endswith("</dependencies>")
        assert "<!-- test -->" in out
        # 缩进 4 个空格
        assert "    <dependency>X</dependency>" in out

    def test_multi_block(self):
        out = _combine_maven_xml([
            {"description": "a", "xml": "<a/>"},
            {"description": "b", "xml": "<b/>"},
        ])
        assert "<!-- a -->" in out
        assert "<!-- b -->" in out
        # both indented
        assert "    <a/>" in out
        assert "    <b/>" in out

    def test_empty_xml_skipped(self):
        out = _combine_maven_xml([
            {"description": "skip me", "xml": ""}
        ])
        # 仅顶层 wrapper,无内容
        assert "<!-- skip me -->" not in out

    def test_no_description_no_comment(self):
        out = _combine_maven_xml([
            {"description": "", "xml": "<x/>"}
        ])
        assert "<!--" not in out
        assert "    <x/>" in out
