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
    "## 关联 Issue",
    "## 背景（Situation）",
    "## 任务（Task）",
    "## 行动（Action）",
    "## 验证（Verification）",
    "## 实验与证据（Evidence）",
    "## 兼容性、风险与回滚",
)
ISSUE_BUG_SECTIONS = (
    "版本与环境",
    "问题与预期行为",
    "最小复现",
    "验收标准",
    "非目标、风险与安全",
)
ISSUE_FEATURE_SECTIONS = (
    "问题与用户价值",
    "建议方案与替代方案",
    "验收标准",
    "架构、兼容性与测试计划",
    "非目标与风险",
)
MARKDOWN_HEADING_PATTERN = re.compile(r"(?m)^#{2,3}\s+(?P<title>[^\r\n]+?)\s*$")
LITERAL_ESCAPE_PATTERN = re.compile(r"\\(?:r|t)(?![A-Za-z0-9_])|\\n\s*#{2,3}\s+")


def validate_title(title: str) -> list[str]:
    """Return policy violations for one title; an empty list means valid."""
    errors: list[str] = []
    normalized = title.rstrip("\r\n")
    if len(normalized) > 72:
        errors.append("title exceeds 72 characters")
    if "??" in normalized:
        errors.append("title contains consecutive '?' characters; check UTF-8 encoding")
    match = TITLE_PATTERN.fullmatch(normalized)
    if not match:
        errors.append("expected ':gitmoji: type(scope): imperative subject'")
        return errors
    expected_type = GITMOJI_TYPES.get(match.group("emoji"))
    if expected_type is None:
        errors.append(f"unsupported Gitmoji {match.group('emoji')}")
    elif match.group("type") != expected_type:
        errors.append(f"Gitmoji {match.group('emoji')} must use type {expected_type}")
    return errors


def _validate_encoding(text: str, label: str) -> list[str]:
    errors: list[str] = []
    if "??" in text:
        errors.append(f"{label} contains consecutive '?' characters; check UTF-8 encoding")
    if "\ufffd" in text:
        errors.append(f"{label} contains Unicode replacement characters; check UTF-8 encoding")
    controls = sorted({ord(char) for char in text if ord(char) < 32 and char not in "\r\n\t"})
    if controls:
        codes = ", ".join(f"U+{code:04X}" for code in controls)
        errors.append(f"{label} contains control characters: {codes}")
    if LITERAL_ESCAPE_PATTERN.search(text):
        errors.append(f"{label} contains literal escape sequences; use real Markdown line breaks")
    return errors


def _validate_sections(text: str, sections: tuple[str, ...], label: str) -> list[str]:
    matches = list(MARKDOWN_HEADING_PATTERN.finditer(text))
    positions: list[tuple[int, str, re.Match[str]]] = []
    errors: list[str] = []
    for section in sections:
        match = next(
            (item for item in matches if item.group("title") == section),
            None,
        )
        if match is None:
            errors.append(f"{label} is missing required section: {section}")
            continue
        positions.append((match.start(), section, match))

    if len(positions) == len(sections):
        ordered = [section for _, section, _ in sorted(positions)]
        if ordered != list(sections):
            errors.append(f"{label} sections are out of order")

        for index, (_, section, match) in enumerate(sorted(positions)):
            next_start = (
                sorted(positions)[index + 1][0] if index + 1 < len(positions) else len(text)
            )
            content = text[match.end() : next_start]
            content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
            if not content:
                errors.append(f"{label} section is empty: {section}")
    return errors


def validate_pr_body(body: str | None) -> list[str]:
    """Return structural and encoding-policy violations for a PR body."""
    normalized = body or ""
    errors = _validate_encoding(normalized, "PR body")
    if not ISSUE_REFERENCE_PATTERN.search(normalized):
        errors.append("PR body must contain 'Closes #<number>' or 'Refs #<number>'")
    errors.extend(
        _validate_sections(
            normalized,
            tuple(section.removeprefix("## ") for section in REQUIRED_PR_SECTIONS),
            "PR body",
        )
    )
    return errors


def validate_issue_body(body: str | None, title: str | None = None) -> list[str]:
    """Return structural and encoding-policy violations for one Issue body."""
    normalized = body or ""
    errors = _validate_encoding(normalized, "Issue body")
    is_bug = bool(re.search(r"\bfix\([a-z0-9][a-z0-9._/-]*\)", title or ""))
    sections = ISSUE_BUG_SECTIONS if is_bug else ISSUE_FEATURE_SECTIONS
    errors.extend(_validate_sections(normalized, sections, "Issue body"))
    return errors


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
        help="GitHub issues event payload used to validate the Issue title and body.",
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
        issue = event.get("issue", {})
        issue_title = issue.get("title", "")
        title_errors = validate_title(issue_title)
        if title_errors:
            failures += 1
            print("INVALID: issue title", file=sys.stderr)
            for error in title_errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print("OK: issue title")
        body_errors = validate_issue_body(issue.get("body"), issue_title)
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
