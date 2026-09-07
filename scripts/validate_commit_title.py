"""Validate the shared Gitmoji + Conventional Commits title policy."""

from __future__ import annotations

import argparse
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
    args = parser.parse_args(argv)
    titles = list(_iter_titles(args))
    if not titles:
        parser.error("provide --title and/or --range")

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
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
