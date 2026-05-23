"""单元测试: ai.naming_rules + ai.llm_client + database.ai_tools (P4.1)

测试:
- 规则推断 (10 真实样本)
- 关联表识别 (业务列阈值)
- LLM 不可用时降级
- handle_ai_infer_business_names 返回结构
- GlobalLLMStats 累加
"""

import asyncio
import json
import os
from unittest.mock import patch

import pytest

from dbjavagenix.ai.llm_client import (
    GLOBAL_LLM_STATS,
    GlobalLLMStats,
    LLMMetrics,
    LLMResult,
    is_llm_available,
)
from dbjavagenix.ai.naming_rules import (
    _is_association_table,
    _singularize,
    _strip_known_prefix,
    _to_pascal_case,
    _tokenize,
    infer_business_name,
    infer_business_names_batch,
)
from dbjavagenix.database.ai_tools import handle_ai_infer_business_names


# ============================================================
# 规则推断核心
# ============================================================

class TestNamingInference:
    @pytest.mark.parametrize("table,expected_class,expected_kind", [
        ("sys_user", "User", "entity"),
        ("biz_order", "Order", "entity"),
        ("orders", "Order", "entity"),
        ("categories", "Category", "entity"),
        ("policies", "Policy", "entity"),
        ("t_dept", "Dept", "entity"),
        ("login_log", "LoginLog", "log"),
        ("login_history", "LoginLog", "log"),
        ("sys_dict_item", "DictItem", "dict"),
        ("sys_dict", "Dict", "dict"),
        ("sys_config", "Config", "config"),
        ("user_setting", "UserConfig", "config"),
        ("analysis", "Analysis", "entity"),  # 不应该单数化为 Analysi
    ])
    def test_basic_rules(self, table, expected_class, expected_kind):
        r = infer_business_name(table)
        assert r.class_name == expected_class, f"{table} -> {r.class_name}, want {expected_class}"
        assert r.table_kind == expected_kind

    def test_association_table_detected(self):
        # sys_user_role: 含 user_id 和 role_id 两个 fk,业务列 0
        r = infer_business_name(
            table="sys_user_role",
            columns=[
                {"name": "id", "primary_key": True},
                {"name": "user_id"},
                {"name": "role_id"},
            ],
            foreign_keys=[
                {"column": "user_id", "references_table": "sys_user"},
                {"column": "role_id", "references_table": "sys_role"},
            ],
        )
        assert r.class_name == "UserRoleAssignment"
        assert r.table_kind == "association"

    def test_not_association_when_business_columns(self):
        # 含两个 fk 但有 5 个业务列 → 仍是 entity 不是关联表
        r = infer_business_name(
            table="order_item",
            columns=[
                {"name": "id", "primary_key": True},
                {"name": "order_id"},
                {"name": "product_id"},
                {"name": "quantity"},
                {"name": "unit_price"},
                {"name": "discount"},
                {"name": "total"},
            ],
            foreign_keys=[
                {"column": "order_id", "references_table": "orders"},
                {"column": "product_id", "references_table": "products"},
            ],
        )
        # 因为业务列多 → 不是 association
        assert r.table_kind == "entity"
        assert r.class_name == "OrderItem"

    def test_audit_columns_excluded_from_business_count(self):
        # 含 created_at/updated_at 不算业务列
        r = infer_business_name(
            table="t_user_role",
            columns=[
                {"name": "id", "primary_key": True},
                {"name": "user_id"},
                {"name": "role_id"},
                {"name": "created_at"},
                {"name": "updated_at"},
                {"name": "version"},
            ],
            foreign_keys=[
                {"column": "user_id", "references_table": "users"},
                {"column": "role_id", "references_table": "roles"},
            ],
        )
        assert r.table_kind == "association"
        assert "Assignment" in r.class_name


class TestBatchInference:
    def test_batch_returns_same_order(self):
        tables = [
            {"name": "users", "columns": [], "foreign_keys": []},
            {"name": "orders", "columns": [], "foreign_keys": []},
        ]
        results = infer_business_names_batch(tables)
        assert len(results) == 2
        assert results[0].table == "users"
        assert results[1].table == "orders"


class TestHelpers:
    @pytest.mark.parametrize("input_,expected", [
        ("sys_user", "user"),
        ("biz_order", "order"),
        ("orders", "orders"),  # no prefix
        ("t_dept", "dept"),
    ])
    def test_strip_known_prefix(self, input_, expected):
        assert _strip_known_prefix(input_) == expected

    @pytest.mark.parametrize("input_,expected", [
        ("users", "user"),
        ("orders", "order"),
        ("categories", "category"),
        ("boxes", "box"),
        ("analysis", "analysis"),
        ("data", "data"),
        ("policies", "policy"),
    ])
    def test_singularize(self, input_, expected):
        assert _singularize(input_) == expected

    @pytest.mark.parametrize("input_,expected", [
        ("user_role", "UserRole"),
        ("order_item", "OrderItem"),
        ("user", "User"),
        ("a_b_c_d", "ABCD"),
    ])
    def test_to_pascal_case(self, input_, expected):
        assert _to_pascal_case(input_) == expected

    def test_tokenize(self):
        assert _tokenize("dict_item") == ["dict", "item"]
        assert _tokenize("login") == ["login"]
        assert _tokenize("a-b_c d") == ["a", "b", "c", "d"]


class TestAssociationDetection:
    def test_is_association_true(self):
        assert _is_association_table(
            columns=[
                {"name": "id", "primary_key": True},
                {"name": "user_id"},
                {"name": "role_id"},
            ],
            foreign_keys=[
                {"column": "user_id"},
                {"column": "role_id"},
            ],
        ) is True

    def test_is_association_false_too_many_business(self):
        assert _is_association_table(
            columns=[
                {"name": "id", "primary_key": True},
                {"name": "user_id"},
                {"name": "role_id"},
                {"name": "extra1"},
                {"name": "extra2"},
            ],
            foreign_keys=[
                {"column": "user_id"},
                {"column": "role_id"},
            ],
        ) is False

    def test_is_association_false_one_fk(self):
        assert _is_association_table(
            columns=[{"name": "id", "primary_key": True}, {"name": "user_id"}],
            foreign_keys=[{"column": "user_id"}],
        ) is False


# ============================================================
# LLM client
# ============================================================

class TestLLMAvailability:
    def test_no_key_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_llm_available() is False

    def test_with_key_but_no_sdk_returns_false(self):
        # 当前测试环境未装 anthropic SDK,key 存在也不可用
        # 真实部署时装了 anthropic 包,该 case 会返回 True
        try:
            import anthropic  # noqa: F401
            sdk_installed = True
        except ImportError:
            sdk_installed = False
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake"}):
            assert is_llm_available() is sdk_installed


class TestGlobalLLMStats:
    def setup_method(self):
        self.stats = GlobalLLMStats()

    def test_record_increments(self):
        m = LLMMetrics(
            input_tokens=100, output_tokens=50,
            cache_read_input_tokens=200, cache_creation_input_tokens=30,
            model="claude-sonnet-4-6",
        )
        self.stats.record(m)
        assert self.stats.total_calls == 1
        assert self.stats.total_input_tokens == 100
        assert self.stats.total_output_tokens == 50
        assert self.stats.total_cache_read == 200
        assert self.stats.total_cache_creation == 30
        assert self.stats.total_errors == 0

    def test_record_error(self):
        m = LLMMetrics(error="json_decode_failed")
        self.stats.record(m)
        assert self.stats.total_errors == 1

    def test_cache_hit_rate(self):
        # cache_read=200, cache_creation=30, input=100 → 200 / 330
        self.stats.record(LLMMetrics(
            input_tokens=100, cache_read_input_tokens=200, cache_creation_input_tokens=30,
        ))
        assert abs(self.stats.cache_hit_rate - 200/330) < 1e-6

    def test_cache_hit_rate_zero_when_empty(self):
        assert self.stats.cache_hit_rate == 0.0

    def test_snapshot_has_expected_keys(self):
        self.stats.record(LLMMetrics(input_tokens=50))
        snap = self.stats.snapshot()
        for key in ("ai.calls_total", "ai.cache_hit_rate", "ai.tokens_saved_via_cache"):
            assert key in snap


# ============================================================
# MCP handler
# ============================================================

class TestHandleAiInferBusinessNames:
    def test_empty_tables_error(self):
        result = asyncio.run(handle_ai_infer_business_names({"tables": []}))
        payload = json.loads(result[0].text)
        assert "error" in payload

    def test_default_uses_rule(self):
        tables = [{"name": "sys_user", "columns": [], "foreign_keys": []}]
        result = asyncio.run(handle_ai_infer_business_names({"tables": tables}))
        payload = json.loads(result[0].text)
        assert payload["source"] == "rule"
        assert payload["inferences"][0]["class_name"] == "User"

    def test_prefer_llm_without_key_falls_back(self):
        with patch.dict(os.environ, {}, clear=True):
            tables = [{"name": "orders", "columns": [], "foreign_keys": []}]
            result = asyncio.run(handle_ai_infer_business_names({
                "tables": tables, "prefer_llm": True,
            }))
            payload = json.loads(result[0].text)
            assert payload["source"] == "rule_llm_unavailable"
            assert payload["llm_available"] is False
            assert payload["inferences"][0]["class_name"] == "Order"

    def test_inference_record_fields(self):
        tables = [{"name": "sys_user", "columns": [], "foreign_keys": []}]
        result = asyncio.run(handle_ai_infer_business_names({"tables": tables}))
        payload = json.loads(result[0].text)
        item = payload["inferences"][0]
        assert "class_name" in item
        assert "table_kind" in item
        assert "reason" in item
        assert "source" in item
        assert "confidence" in item
