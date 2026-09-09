"""Regression tests for dependency requirement version isolation."""

from dbjavagenix.utils.dependency_requirements import DependencyRequirements


def _required_coordinate(requirements, group_id: str, artifact_id: str) -> tuple[str, str, str]:
    for dependency in requirements["required"]:
        if dependency.group_id == group_id and dependency.artifact_id == artifact_id:
            return dependency.group_id, dependency.artifact_id, dependency.version
    raise AssertionError(f"missing required dependency {group_id}:{artifact_id}")


def test_spring_boot_version_adaptation_does_not_leak_between_analyses():
    catalog = DependencyRequirements()

    boot2 = catalog.analyze_requirements("MybatisPlus", "mysql", spring_boot_version="2.7.18")
    modern_defaults = catalog.analyze_requirements("MybatisPlus", "mysql")

    assert _required_coordinate(boot2, "mysql", "mysql-connector-java") == (
        "mysql",
        "mysql-connector-java",
        "8.0.33",
    )
    assert _required_coordinate(modern_defaults, "com.mysql", "mysql-connector-j") == (
        "com.mysql",
        "mysql-connector-j",
        "8.4.0",
    )
    assert _required_coordinate(
        modern_defaults,
        "com.baomidou",
        "mybatis-plus-spring-boot3-starter",
    ) == ("com.baomidou", "mybatis-plus-spring-boot3-starter", "3.5.7")


def test_version_adaptation_is_order_independent():
    first = DependencyRequirements()
    first_modern = first.analyze_requirements("MybatisPlus", "mysql", spring_boot_version="3.5.5")
    first_boot2 = first.analyze_requirements("MybatisPlus", "mysql", spring_boot_version="2.7.18")

    second = DependencyRequirements()
    second_boot2 = second.analyze_requirements("MybatisPlus", "mysql", spring_boot_version="2.7.18")
    second_modern = second.analyze_requirements("MybatisPlus", "mysql", spring_boot_version="3.5.5")

    assert _required_coordinate(
        first_modern, "com.mysql", "mysql-connector-j"
    ) == _required_coordinate(second_modern, "com.mysql", "mysql-connector-j")
    assert _required_coordinate(
        first_boot2, "mysql", "mysql-connector-java"
    ) == _required_coordinate(second_boot2, "mysql", "mysql-connector-java")
