"""Validate the shared Gitmoji + Conventional Commits title policy."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable

GITMOJI_TYPES = {
    ":sparkles:": "feat",
    ":bug:": "fix",
    ":test_tube:": "test",
    ":books:": "docs",
    ":recycle:": "refactor",
    ":zap:": "perf",
    ":construction_worker:": "ci",
    ":hammer:": "build",
    ":lock:": "security",
    ":wrench:": "chore",
    ":rocket:": "release",
}

TITLE_PATTERN = re.compile(
    r"^(?P<emoji>:[a-z0-9_+-]+:) "
    r"(?P<type>feat|fix|test|docs|refactor|perf|ci|build|security|chore|release)"
    r"\([a-z0-9][a-z0-9._/-]*\): (?P<subject>\S(?:.*\S)?)$"
)
ISSUE_REFERENCE_PATTERN = re.compile(r"\b(?:Closes|Refs)\s+#\d+\b", re.IGNORECASE)
REQUIRED_PR_SECTIONS = (
    "关联 Issue",
    "背景（Situation）",
    "任务（Task）",
    "行动（Action）",
    "验证（Verification）",
    "实验与证据（Evidence）",
    "兼容性、风险与回滚",
)
ISSUE_SECTION_SETS = (
    (
        "版本与环境",
        "问题与预期行为",
        "最小复现",
        "验收标准",
        "非目标、风险与安全",
    ),
    (
        "问题与用户价值",
        "建议方案与替代方案",
        "验收标准",
        "架构、兼容性与测试计划",
        "非目标与风险",
    ),
    (
        "问题与用户价值",
        "建议方案与非目标",
        "验收标准",
        "架构、兼容性与测试计划",
        "非目标与风险",
    ),
    (
        "环境信息",
        "问题与预期行为",
        "复现步骤",
        "验收标准",
        "非目标、风险与安全信息",
    ),
)
HEADING_PATTERN = re.compile(r"(?m)^#{2,6}\s+(?P<title>[^\r\n#]+?)\s*$")
PLACEHOLDER_PATTERN = re.compile(
    r"<\s*(?:[^>\r\n]{1,80})\s*>|\b(?:TODO|TBD|FIXME)\b|请填写|待填写|按模块列出",
    re.IGNORECASE,
)
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PSEUDO_NEWLINE_PATTERN = re.compile(r"\\[nr]")
GENERIC_TITLE_PATTERN = re.compile(
    r"^(?:config|init|\.gitignore|initial commit|请填写(?:标题|摘要)?)$",
    re.IGNORECASE,
)


def validate_title(title: str) -> list[str]:
    """Return policy violations for one title; an empty list means valid."""
    errors: list[str] = []
    normalized = title.rstrip("\r\n")
    if len(normalized) > 72:
        errors.append("title exceeds 72 characters")
    if "\ufffd" in normalized:
        errors.append("title contains the Unicode replacement character; check UTF-8 encoding")
    if "??" in normalized:
        errors.append("title contains consecutive '?' characters; check UTF-8 encoding")
    if PSEUDO_NEWLINE_PATTERN.search(normalized):
        errors.append("title contains a literal \\n or \\r escape; use real line structure")
    if CONTROL_CHARACTER_PATTERN.search(normalized):
        errors.append("title contains a control character")
    if GENERIC_TITLE_PATTERN.fullmatch(normalized.strip()) or PLACEHOLDER_PATTERN.search(
        normalized
    ):
        errors.append("title contains a generic or unreplaced placeholder subject")
    match = TITLE_PATTERN.fullmatch(normalized)
    if not match:
        errors.append("expected ':gitmoji: type(scope): imperative subject'")
        return errors
    expected_type = GITMOJI_TYPES.get(match.group("emoji"))
    if expected_type is None:
        errors.append(f"unsupported Gitmoji {match.group('emoji')}")
    elif match.group("type") != expected_type:
        errors.append(f"Gitmoji {match.group('emoji')} must use type {expected_type}")
    if normalized.endswith(("。", ".")):
        errors.append("title must not end with sentence punctuation")
    return errors


def validate_pr_body(body: str | None) -> list[str]:
    """Return structural and encoding-policy violations for a PR body."""
    normalized = body or ""
    errors: list[str] = []
    errors.extend(_validate_text_quality(normalized, "PR body"))
    content = _without_comments(normalized)
    if not ISSUE_REFERENCE_PATTERN.search(content):
        errors.append("PR body must contain 'Closes #<number>' or 'Refs #<number>'")
    _validate_sections(content, REQUIRED_PR_SECTIONS, "PR body", errors)
    return errors


def validate_issue_body(body: str | None) -> list[str]:
    """Return structural and encoding-policy violations for an Issue body."""
    normalized = body or ""
    errors = _validate_text_quality(normalized, "Issue body")
    content = _without_comments(normalized)
    headings = {match.group("title").strip() for match in HEADING_PATTERN.finditer(content)}
    matching_schema = next(
        (schema for schema in ISSUE_SECTION_SETS if set(schema) <= headings), None
    )
    if matching_schema is None:
        errors.append("Issue body does not contain a complete bug or feature section set")
        return errors
    _validate_sections(content, matching_schema, "Issue body", errors)
    return errors


def _without_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _validate_text_quality(text: str, label: str) -> list[str]:
    errors: list[str] = []
    if "\ufffd" in text:
        errors.append(f"{label} contains the Unicode replacement character; check UTF-8 encoding")
    if "??" in text:
        errors.append(f"{label} contains consecutive '?' characters; check UTF-8 encoding")
    if PSEUDO_NEWLINE_PATTERN.search(text):
        errors.append(f"{label} contains literal \\n or \\r escapes; use real line breaks")
    if CONTROL_CHARACTER_PATTERN.search(text):
        errors.append(f"{label} contains a control character")
    if PLACEHOLDER_PATTERN.search(_without_comments(text)):
        errors.append(f"{label} contains an unreplaced template placeholder")
    return errors


def _validate_sections(text: str, sections: Iterable[str], label: str, errors: list[str]) -> None:
    headings = list(HEADING_PATTERN.finditer(text))
    positions = {match.group("title").strip(): match for match in headings}
    previous_position = -1
    for section in sections:
        match = positions.get(section)
        if match is None:
            errors.append(f"{label} is missing required section: ## {section}")
            continue
        if match.start() < previous_position:
            errors.append(f"{label} sections are out of order: ## {section}")
        previous_position = match.start()
        next_heading = next((item for item in headings if item.start() > match.start()), None)
        section_body = text[match.end() : next_heading.start() if next_heading else None].strip()
        if not section_body or PLACEHOLDER_PATTERN.search(section_body):
            errors.append(f"{label} section is empty: ## {section}")


def _titles_from_range(rev_range: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%s", rev_range],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _iter_titles(args: argparse.Namespace) -> Iterable[str]:
    if args.title:
        yield from args.title
    if args.rev_range:
        yield from _titles_from_range(args.rev_range)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--title",
        action="append",
        help="Title to validate; may be repeated.",
    )
    parser.add_argument(
        "--range",
        dest="rev_range",
        help="Git revision range whose commit subjects should be validated.",
    )
    parser.add_argument(
        "--pr-event",
        help="GitHub pull_request event payload used to validate the PR body.",
    )
    parser.add_argument(
        "--issue-event",
        help="GitHub issues event payload used to validate the Issue body.",
    )
    args = parser.parse_args(argv)
    titles = list(_iter_titles(args))
    if not titles and not args.pr_event and not args.issue_event:
        parser.error("provide --title, --range, --pr-event, and/or --issue-event")

    failures = 0
    for title in titles:
        errors = validate_title(title)
        if errors:
            failures += 1
            print(f"INVALID: {title}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"OK: {title}")
    if args.pr_event:
        with open(args.pr_event, encoding="utf-8") as event_file:
            event = json.load(event_file)
        body_errors = validate_pr_body(event.get("pull_request", {}).get("body"))
        if body_errors:
            failures += 1
            print("INVALID: pull request body", file=sys.stderr)
            for error in body_errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print("OK: pull request body")
    if args.issue_event:
        with open(args.issue_event, encoding="utf-8") as event_file:
            event = json.load(event_file)
        body_errors = validate_issue_body(event.get("issue", {}).get("body"))
        if body_errors:
            failures += 1
            print("INVALID: issue body", file=sys.stderr)
            for error in body_errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print("OK: issue body")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
