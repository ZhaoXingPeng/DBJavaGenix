"""单元测试: mcp_apps.code_diff (P3.3)

测试:
- build_code_diff_data 正常多文件
- 跳过 error 项
- before 字段在无 project_root 时为 None
- 在 project_root 给定但目标文件不存在时 before 为 None
- 在 project_root 给定且文件存在时 before 是文件内容
"""

import pytest

from dbjavagenix.mcp_apps.code_diff import (
    _try_read_existing,
    build_code_diff_data,
)


@pytest.fixture
def render_files_ok():
    return [
        {
            "template_file": "entity.mustache",
            "file_path": "com/example/entity/User.java",
            "code": "package com.example.entity;\n\npublic class User {}",
            "lines": 3,
        },
        {
            "template_file": "dao.mustache",
            "file_path": "com/example/dao/UserDao.java",
            "code": "package com.example.dao;\n\npublic interface UserDao {}",
            "lines": 3,
        },
    ]


class TestBuildCodeDiffData:
    def test_basic(self, render_files_ok):
        data = build_code_diff_data(render_files_ok)
        assert data["language"] == "java"
        assert len(data["files"]) == 2
        f1 = data["files"][0]
        assert f1["file_path"] == "com/example/entity/User.java"
        assert "public class User" in f1["after"]
        assert f1["template_file"] == "entity.mustache"
        assert f1["before"] is None  # no project_root

    def test_skips_error_entries(self):
        files = [
            {"template_file": "entity.mustache", "file_path": "x.java", "code": "x"},
            {"template_file": "missing.mustache", "error": "template not found"},
        ]
        data = build_code_diff_data(files)
        # 错误项被过滤
        assert len(data["files"]) == 1
        assert data["files"][0]["template_file"] == "entity.mustache"

    def test_no_project_root_before_is_none(self, render_files_ok):
        data = build_code_diff_data(render_files_ok, project_root=None)
        for f in data["files"]:
            assert f["before"] is None

    def test_project_root_file_not_found(self, render_files_ok, tmp_path):
        data = build_code_diff_data(render_files_ok, project_root=str(tmp_path))
        for f in data["files"]:
            assert f["before"] is None

    def test_project_root_file_exists(self, tmp_path):
        # 准备已存在文件
        target_rel = "com/example/entity/User.java"
        target = tmp_path / target_rel
        target.parent.mkdir(parents=True)
        target.write_text("public class User { /* old */ }", encoding="utf-8")

        files = [
            {
                "template_file": "entity.mustache",
                "file_path": target_rel,
                "code": "public class User { /* new */ }",
                "lines": 1,
            }
        ]
        data = build_code_diff_data(files, project_root=str(tmp_path))
        assert len(data["files"]) == 1
        f = data["files"][0]
        assert f["before"] == "public class User { /* old */ }"
        assert f["after"] == "public class User { /* new */ }"

    def test_language_override(self, render_files_ok):
        data = build_code_diff_data(render_files_ok, language="kotlin")
        assert data["language"] == "kotlin"


class TestTryReadExisting:
    def test_returns_none_for_missing_path(self, tmp_path):
        assert _try_read_existing(tmp_path, "no/such/file.java") is None

    def test_returns_none_for_empty_relative(self, tmp_path):
        assert _try_read_existing(tmp_path, "") is None

    def test_reads_existing(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello", encoding="utf-8")
        assert _try_read_existing(tmp_path, "hello.txt") == "hello"

    def test_returns_none_for_binary(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\xff\xfe\xfd\xfc")
        # 非 utf-8 时返回 None
        assert _try_read_existing(tmp_path, "binary.bin") is None

    def test_returns_none_for_parent_path_escape(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("must not read", encoding="utf-8")
        assert _try_read_existing(tmp_path, "../outside.txt") is None

    def test_returns_none_for_absolute_path_escape(self, tmp_path):
        outside = tmp_path.parent / "outside-absolute.txt"
        outside.write_text("must not read", encoding="utf-8")
        assert _try_read_existing(tmp_path, str(outside)) is None
