"""Tests for the repository title policy used by CI."""

import runpy
from pathlib import Path


_POLICY = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "validate_commit_title.py"))
validate_title = _POLICY["validate_title"]
validate_pr_body = _POLICY["validate_pr_body"]
validate_issue_body = _POLICY["validate_issue_body"]


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


def test_rejects_replacement_character_pseudo_newline_and_placeholder_title():
    replacement_errors = validate_title(":books: docs(governance): 修复\ufffd")
    pseudo_newline_errors = validate_title(":books: docs(governance): 修复\\n占位")
    placeholder_errors = validate_title(":books: docs(governance): <请填写摘要>")

    assert any("replacement character" in error for error in replacement_errors)
    assert any("literal" in error for error in pseudo_newline_errors)
    assert any("placeholder" in error for error in placeholder_errors)


def test_rejects_generic_title_and_sentence_punctuation():
    assert validate_title("init")
    assert any(
        "sentence punctuation" in error
        for error in validate_title(":books: docs(readme): 更新说明。")
    )


def test_accepts_complete_pr_body():
    assert validate_pr_body(VALID_PR_BODY) == []


def test_rejects_incomplete_pr_body_and_encoding_corruption():
    errors = validate_pr_body("## 关联 Issue\n\nRefs #118\n\n????")

    assert any("UTF-8 encoding" in error for error in errors)
    assert any("missing required section" in error for error in errors)


def test_rejects_empty_pr_sections_and_unreplaced_placeholders():
    body = VALID_PR_BODY.replace("固化契约。", "").replace(
        "模板变为必填；回滚本提交。", "<填写风险>"
    )

    errors = validate_pr_body(body)

    assert any("section is empty" in error for error in errors)
    assert any("placeholder" in error for error in errors)


VALID_ISSUE_BODY = """## 问题与用户价值

贡献者需要可追溯的元数据规范。

## 建议方案与替代方案

扩展纯 Python 校验器；不依赖网络。

## 验收标准

- [ ] 覆盖正文结构和编码信号。

## 架构、兼容性与测试计划

运行单元测试，保持运行时 API 不变。

## 非目标与风险

不重写历史提交；回滚治理提交。
"""


def test_accepts_complete_issue_body():
    assert validate_issue_body(VALID_ISSUE_BODY) == []


def test_accepts_issue_form_headings():
    body = """### 环境信息

Python 3.12；SQLite fixture。

### 问题与预期行为

描述实际和预期行为。

### 复现步骤

运行脱敏的最小命令。

### 验收标准

- [ ] 回归测试通过。

### 非目标、风险与安全信息

不包含凭据；可回滚。
"""

    assert validate_issue_body(body) == []


def test_rejects_issue_body_with_missing_sections_and_pseudo_newline():
    errors = validate_issue_body("## 问题与用户价值\\n\n说明")

    assert any("complete bug or feature section set" in error for error in errors)
    assert any("literal" in error for error in errors)


def test_rejects_issue_body_with_empty_section_and_control_character():
    body = VALID_ISSUE_BODY.replace("扩展纯 Python 校验器；不依赖网络。", "") + "\x0b"

    errors = validate_issue_body(body)

    assert any("section is empty" in error for error in errors)
    assert any("control character" in error for error in errors)
