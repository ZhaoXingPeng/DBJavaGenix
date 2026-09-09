"""Tests for the repository title policy used by CI."""

import runpy
from pathlib import Path


_POLICY = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "validate_commit_title.py"))
validate_title = _POLICY["validate_title"]
validate_pr_body = _POLICY["validate_pr_body"]
validate_issue_body = _POLICY["validate_issue_body"]
validate_main = _POLICY["main"]


VALID_PR_BODY = """## 关联 Issue

Closes #118

## 背景（Situation）

现有契约不完整。

## 任务（Task）

固化契约。

## 行动（Action）

更新模板和 CI。

## 验证（Verification）

运行单元测试。

## 实验与证据（Evidence）

无。

## 兼容性、风险与回滚

模板变为必填；回滚本提交。
"""

VALID_BUG_ISSUE_BODY = """## 版本与环境

Python 3.12，固定 SQLite fixture。

## 问题与预期行为

实际结果与预期结果不一致。

## 最小复现

运行最小测试命令即可复现。

## 验收标准

- [ ] 回归测试通过。

## 非目标、风险与安全

不涉及凭据或生产数据；恢复单一提交即可回滚。
"""

VALID_FEATURE_ISSUE_BODY = """## 问题与用户价值

统一合同，降低维护成本。

## 建议方案与替代方案

复用共享 helper；不采用重复实现。

## 验收标准

- [ ] 新旧入口行为一致。

## 架构、兼容性与测试计划

保持公共 API，运行单元测试和静态检查。

## 非目标与风险

不改变数据库 schema；回滚单一提交。
"""


def test_valid_gitmoji_conventional_title():
    assert validate_title(":sparkles: feat(generator): add nullable columns") == []


def test_valid_ci_and_build_titles_use_matching_gitmoji():
    assert validate_title(":construction_worker: ci(workflow): run unit tests") == []
    assert validate_title(":hammer: build(packaging): pin uv version") == []


def test_rejects_missing_gitmoji():
    assert validate_title("feat(generator): add nullable columns")


def test_rejects_missing_scope():
    errors = validate_title(":sparkles: feat: 增加列元数据")

    assert any("expected" in error for error in errors)


def test_rejects_native_unicode_emoji_prefix():
    errors = validate_title("✨ feat(generator): 增加列元数据")

    assert any("expected" in error for error in errors)


def test_rejects_mismatched_gitmoji_and_type():
    errors = validate_title(":bug: feat(generator): add nullable columns")
    assert any("must use type fix" in error for error in errors)


def test_rejects_long_title():
    title = ":books: docs: " + "x" * 60
    assert any("72 characters" in error for error in validate_title(title))


def test_rejects_likely_encoding_corruption():
    errors = validate_title(":recycle: refactor(model): 固化列元数据??????????")

    assert any("UTF-8 encoding" in error for error in errors)


def test_accepts_complete_pr_body():
    assert validate_pr_body(VALID_PR_BODY) == []


def test_rejects_incomplete_pr_body_and_encoding_corruption():
    errors = validate_pr_body("## 关联 Issue\n\nRefs #118\n\n????")

    assert any("UTF-8 encoding" in error for error in errors)
    assert any("missing required section" in error for error in errors)


def test_rejects_empty_and_out_of_order_pr_sections():
    empty = VALID_PR_BODY.replace("更新模板和 CI。", "")
    errors = validate_pr_body(empty)
    assert any("section is empty" in error for error in errors)

    out_of_order = (
        VALID_PR_BODY.replace("## 任务（Task）", "## TEMP")
        .replace("## 行动（Action）", "## 任务（Task）")
        .replace("## TEMP", "## 行动（Action）")
    )
    assert any("out of order" in error for error in validate_pr_body(out_of_order))


def test_rejects_replacement_control_and_literal_escape_characters():
    replacement_errors = validate_pr_body(VALID_PR_BODY.replace("固化契约。", "固化\ufffd契约。"))
    assert any("replacement characters" in error for error in replacement_errors)

    control_errors = validate_pr_body(VALID_PR_BODY.replace("固化契约。", "固化\x01契约。"))
    assert any("control characters" in error for error in control_errors)

    escape_errors = validate_pr_body(VALID_PR_BODY.replace("固化契约。", "固化\\r\\n契约。"))
    assert any("literal escape sequences" in error for error in escape_errors)


def test_accepts_windows_paths_in_body_text():
    body = VALID_PR_BODY.replace("固化契约。", r"记录 C:\tmp\report，固化契约。")
    assert validate_pr_body(body) == []


def test_validates_bug_and_feature_issue_bodies():
    assert validate_issue_body(VALID_BUG_ISSUE_BODY, ":bug: fix(database): 修复事务") == []
    assert (
        validate_issue_body(VALID_FEATURE_ISSUE_BODY, ":sparkles: feat(database): 增加能力") == []
    )


def test_rejects_issue_body_with_wrong_template_and_encoding():
    errors = validate_issue_body(
        VALID_BUG_ISSUE_BODY.replace("## 最小复现", "## 复现步骤").replace(
            "固定 SQLite", "固定?? SQLite"
        ),
        ":bug: fix(database): 修复事务",
    )
    assert any("consecutive '?'" in error for error in errors)
    assert any("missing required section" in error for error in errors)


def test_issue_event_cli_validates_title_and_body(tmp_path, capsys):
    event_path = tmp_path / "issues.json"
    event_path.write_text(
        '{"issue": {"title": ":sparkles: feat(database): 增加能力", '
        '"body": ' + repr(VALID_FEATURE_ISSUE_BODY).replace("'", '"') + "}}",
        encoding="utf-8",
    )
    assert validate_main(["--issue-event", str(event_path)]) == 0
    output = capsys.readouterr()
    assert "OK: issue title" in output.out
    assert "OK: issue body" in output.out
