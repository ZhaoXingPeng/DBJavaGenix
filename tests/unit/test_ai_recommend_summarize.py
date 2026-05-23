"""单元测试: ai.template_recommender + ai.schema_summary (P4.2/P4.3)"""

import asyncio
import json

import pytest

from dbjavagenix.ai.schema_summary import (
    _detect_module_prefix,
    _group_by_prefix,
    _summarize_relationships,
    summarize_schema,
)
from dbjavagenix.ai.template_recommender import (
    PATTERNS,
    TemplateRecommendation,
    _score_pattern,
    _score_to_confidence,
    recommend_template,
)
from dbjavagenix.database.ai_tools import (
    handle_ai_recommend_template,
    handle_ai_summarize_schema,
)


# ============================================================
# Template recommender
# ============================================================

class TestRecommendTemplate:
    def test_rbac_detected(self):
        rec = recommend_template([
            "sys_user", "sys_role", "sys_permission",
            "sys_user_role", "sys_role_permission", "sys_menu",
        ])
        assert rec.pattern == "RBAC"
        assert rec.template == "MybatisPlus-Mixed"
        assert rec.confidence == "high"
        assert rec.score >= 1.5
        assert "sys_user" in rec.matched_tables
        assert "sys_role" in rec.matched_tables

    def test_ecommerce_detected(self):
        rec = recommend_template([
            "orders", "order_items", "products", "categories", "skus", "payments",
        ])
        assert rec.pattern == "E-Commerce"
        assert rec.confidence in ("high", "medium")

    def test_cms_detected(self):
        rec = recommend_template([
            "articles", "categories", "tags", "comments", "authors",
        ])
        assert rec.pattern == "CMS"
        assert rec.template == "MybatisPlus"

    def test_ticketing_detected(self):
        rec = recommend_template([
            "tickets", "assignments", "status_history", "priority",
        ])
        assert rec.pattern == "Ticketing"

    def test_unknown_pattern_falls_back_to_general(self):
        rec = recommend_template([
            "weird_table_1", "totally_random_2", "no_match_here",
        ])
        assert rec.pattern == "General"
        assert rec.template == "MybatisPlus-Mixed"
        assert rec.confidence == "low"

    def test_hint_modern_stack_forces_sb35(self):
        rec = recommend_template(
            ["sys_user", "sys_role"],
            hint_modern_stack=True,
        )
        assert rec.template == "sb35-java21"
        assert rec.pattern == "Modern-Spring-Boot-3"

    def test_options_field_present(self):
        rec = recommend_template(["users", "orders"])
        assert "useSwagger" in rec.options
        assert "useLombok" in rec.options


class TestScorePattern:
    def test_required_missing_returns_zero(self):
        pattern = PATTERNS[0]  # RBAC (require user + role)
        score, _reasons, _matched = _score_pattern(pattern, ["random_table"])
        assert score == 0.0

    def test_required_satisfied(self):
        pattern = PATTERNS[0]
        score, reasons, matched = _score_pattern(pattern, ["sys_user", "sys_role"])
        assert score >= 1.0
        assert any("必需表片段" in r for r in reasons)
        assert "sys_user" in matched

    def test_bonus_adds_score(self):
        pattern = PATTERNS[0]
        score_with_bonus, _, _ = _score_pattern(
            pattern, ["sys_user", "sys_role", "sys_permission", "sys_menu"]
        )
        score_no_bonus, _, _ = _score_pattern(pattern, ["sys_user", "sys_role"])
        assert score_with_bonus > score_no_bonus


class TestScoreToConfidence:
    @pytest.mark.parametrize("score,expected", [
        (1.5, "high"),
        (1.8, "high"),
        (1.2, "medium"),
        (1.0, "medium"),
        (0.5, "low"),
        (0.0, "low"),
    ])
    def test_threshold(self, score, expected):
        assert _score_to_confidence(score) == expected


# ============================================================
# Schema summary
# ============================================================

class TestSummarizeSchema:
    def test_basic_summary(self):
        s = summarize_schema(
            table_names=["sys_user", "sys_role", "biz_order"],
        )
        assert s.total_tables == 3
        assert "数据库包含 3 张表" in s.narrative

    def test_modules_grouped(self):
        s = summarize_schema(
            table_names=["sys_user", "sys_role", "biz_order", "biz_item"],
        )
        module_prefixes = {m["prefix"] for m in s.modules}
        assert "sys" in module_prefixes
        assert "biz" in module_prefixes

    def test_rbac_detected_in_narrative(self):
        s = summarize_schema(
            table_names=["sys_user", "sys_role", "sys_permission", "sys_user_role"],
        )
        assert s.detected_pattern == "RBAC"
        assert "RBAC" in s.narrative

    def test_core_entities_from_column_counts(self):
        s = summarize_schema(
            table_names=["users", "orders", "logs"],
            table_column_counts={"users": 5, "orders": 15, "logs": 3},
        )
        # orders 列最多 → 应在核心实体前
        assert "orders" in s.core_entities

    def test_relationships_extracted(self):
        s = summarize_schema(
            table_names=["a", "b"],
            foreign_keys=[{"from_table": "a", "to_table": "b"}],
        )
        assert len(s.relationships) == 1
        assert s.relationships[0]["from_table"] == "a"
        assert s.relationships[0]["to_table"] == "b"

    def test_dedup_relationships(self):
        s = summarize_schema(
            table_names=["a", "b"],
            foreign_keys=[
                {"from_table": "a", "to_table": "b"},
                {"from_table": "a", "to_table": "b"},  # dup
            ],
        )
        assert len(s.relationships) == 1


class TestDetectModulePrefix:
    @pytest.mark.parametrize("table,expected", [
        ("sys_user", "sys"),
        ("biz_order", "biz"),
        ("bd_dict", "bd"),
        ("admin_log", "admin"),
        ("user", "(other)"),
        ("unknown_table_xyz", "unknown"),
    ])
    def test_prefix_detection(self, table, expected):
        assert _detect_module_prefix(table) == expected


class TestGroupByPrefix:
    def test_known_prefix_kept_even_with_one_table(self):
        # 已知前缀 (sys/biz/admin) 即使只有 1 表也保留,
        # 因为前缀本身已是有效信息
        groups = _group_by_prefix(["sys_user", "biz_order", "biz_item"])
        prefixes = {g["prefix"] for g in groups}
        assert "sys" in prefixes
        assert "biz" in prefixes

    def test_other_unique_kept_when_count_ge_2(self):
        # "(other)" 类组只有 ≥ 2 张才聚合
        groups = _group_by_prefix(["table_x"])
        # 单 "(other)" 表被过滤
        prefixes = {g["prefix"] for g in groups}
        assert "(other)" not in prefixes


class TestSummarizeRelationships:
    def test_uses_to_table_when_present(self):
        rels = _summarize_relationships([
            {"from_table": "a", "to_table": "b"},
        ])
        assert rels[0]["to_table"] == "b"

    def test_uses_references_table_fallback(self):
        # FK format from db_table_foreign_keys
        rels = _summarize_relationships([
            {"table": "a", "references_table": "b"},
        ])
        assert rels[0]["from_table"] == "a"
        assert rels[0]["to_table"] == "b"

    def test_skips_invalid(self):
        rels = _summarize_relationships([
            {},
            {"from_table": ""},
            {"from_table": "a", "to_table": ""},
        ])
        assert rels == []


# ============================================================
# MCP handlers
# ============================================================

class TestRecommendTemplateHandler:
    def test_empty_error(self):
        result = asyncio.run(handle_ai_recommend_template({"table_names": []}))
        payload = json.loads(result[0].text)
        assert "error" in payload

    def test_returns_recommendation(self):
        result = asyncio.run(handle_ai_recommend_template({
            "table_names": ["sys_user", "sys_role"],
        }))
        payload = json.loads(result[0].text)
        assert payload["recommended_template"]
        assert "options" in payload
        assert "confidence" in payload


class TestSummarizeSchemaHandler:
    def test_empty_error(self):
        result = asyncio.run(handle_ai_summarize_schema({"table_names": []}))
        payload = json.loads(result[0].text)
        assert "error" in payload

    def test_returns_narrative(self):
        result = asyncio.run(handle_ai_summarize_schema({
            "table_names": ["sys_user", "sys_role"],
        }))
        payload = json.loads(result[0].text)
        assert "narrative" in payload
        assert payload["total_tables"] == 2
