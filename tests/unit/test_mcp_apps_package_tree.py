"""单元测试: mcp_apps.package_tree (P3.4)

测试:
- build_package_tree_data 多文件 + 多层包
- common prefix 检测
- status: new / modified
- 空输入
- _serialize_tree 字母序
"""

from dbjavagenix.mcp_apps.package_tree import (
    _common_prefix,
    _determine_status,
    build_package_tree_data,
)


class TestBuildPackageTreeData:
    def test_empty(self):
        data = build_package_tree_data([])
        assert data == {"root": "", "children": []}

    def test_single_file(self):
        data = build_package_tree_data([
            "com/example/entity/User.java",
        ])
        assert data["root"] == "com.example.entity"
        # 仅有一层 children: 文件本身
        assert len(data["children"]) == 1
        assert data["children"][0] == {
            "name": "User.java",
            "type": "file",
            "status": "new",
        }

    def test_common_prefix_detected(self):
        data = build_package_tree_data([
            "com/example/entity/User.java",
            "com/example/dao/UserDao.java",
            "com/example/service/UserService.java",
        ])
        assert data["root"] == "com.example"
        # 三个一级 children: entity / dao / service (packages)
        names = [c["name"] for c in data["children"]]
        assert names == sorted(names)
        assert "entity" in names
        assert "dao" in names
        assert "service" in names

    def test_nested_packages(self):
        data = build_package_tree_data([
            "com/example/entity/sub/Inner.java",
            "com/example/entity/Outer.java",
        ])
        assert data["root"] == "com.example.entity"
        # children: Outer.java (file) + sub (package)
        children = data["children"]
        types = {c["name"]: c["type"] for c in children}
        assert types["Outer.java"] == "file"
        assert types["sub"] == "package"

    def test_alpha_sort(self):
        data = build_package_tree_data([
            "z.java",
            "a.java",
            "m.java",
        ])
        names = [c["name"] for c in data["children"]]
        assert names == ["a.java", "m.java", "z.java"]

    def test_status_modified_when_file_exists(self, tmp_path):
        # 准备已存在文件
        existing_rel = "com/example/entity/User.java"
        existing = tmp_path / existing_rel
        existing.parent.mkdir(parents=True)
        existing.write_text("old", encoding="utf-8")

        data = build_package_tree_data(
            [existing_rel, "com/example/dao/UserDao.java"],
            project_root=str(tmp_path),
        )
        # 找到 User.java 节点 (在 entity 包下)
        entity_pkg = next(c for c in data["children"] if c["name"] == "entity")
        user_file = next(c for c in entity_pkg["children"] if c["name"] == "User.java")
        assert user_file["status"] == "modified"

        # UserDao.java 不存在 → new
        dao_pkg = next(c for c in data["children"] if c["name"] == "dao")
        userdao_file = next(c for c in dao_pkg["children"] if c["name"] == "UserDao.java")
        assert userdao_file["status"] == "new"


class TestCommonPrefix:
    def test_single_path(self):
        assert _common_prefix([["a", "b", "X.java"]]) == ["a", "b"]

    def test_no_common(self):
        assert _common_prefix([["a", "X.java"], ["b", "Y.java"]]) == []

    def test_partial(self):
        assert _common_prefix([
            ["a", "b", "c", "X.java"],
            ["a", "b", "d", "Y.java"],
        ]) == ["a", "b"]

    def test_empty_list(self):
        assert _common_prefix([]) == []


class TestDetermineStatus:
    def test_none_root_returns_new(self):
        assert _determine_status(None, "any/path.java") == "new"

    def test_file_exists_returns_modified(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("y")
        assert _determine_status(tmp_path, "x.txt") == "modified"

    def test_file_missing_returns_new(self, tmp_path):
        assert _determine_status(tmp_path, "missing.txt") == "new"
