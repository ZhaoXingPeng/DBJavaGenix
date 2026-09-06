"""Tests for the repository title policy used by CI."""

import runpy
from pathlib import Path


_POLICY = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "validate_commit_title.py"))
validate_title = _POLICY["validate_title"]


def test_valid_gitmoji_conventional_title():
    assert validate_title(":sparkles: feat(generator): add nullable columns") == []


def test_valid_ci_and_build_titles_use_matching_gitmoji():
    assert validate_title(":construction_worker: ci: run unit tests") == []
    assert validate_title(":hammer: build: pin uv version") == []


def test_rejects_missing_gitmoji():
    assert validate_title("feat(generator): add nullable columns")


def test_rejects_mismatched_gitmoji_and_type():
    errors = validate_title(":bug: feat(generator): add nullable columns")
    assert any("must use type fix" in error for error in errors)


def test_rejects_long_title():
    title = ":books: docs: " + "x" * 60
    assert any("72 characters" in error for error in validate_title(title))
