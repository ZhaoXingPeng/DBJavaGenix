"""Render every checked-in Java template with a representative context."""

from __future__ import annotations

from pathlib import Path

import pystache

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "src" / "dbjavagenix" / "templates" / "java"

CONTEXT = {
    "entityPackage": "verify.entity",
    "dtoPackage": "verify.dto",
    "voPackage": "verify.vo",
    "daoPackage": "verify.dao",
    "servicePackage": "verify.service",
    "serviceImplPackage": "verify.service.impl",
    "controllerPackage": "verify.controller",
    "mapperPackage": "verify.mapper",
    "className": "SysUser",
    "tableName": "sys_user",
    "entityNameLowerCase": "sysUser",
    "comment": "system user",
    "author": "ci",
    "date": "2026-09-06",
    "primaryKeyName": "id",
    "primaryKeyType": "Long",
    "capitalizedPrimaryKeyName": "Id",
    "serialVersionUID": "1",
    "hasJakarta": True,
    "hasJavax": False,
    "hasSpringDoc": True,
    "useSwagger": True,
    "useLombok": True,
    "useJPA": True,
    "generateDto": True,
    "generateVo": True,
    "generateMapper": True,
    "generateMappers": True,
    "imports": [],
    "columns": [
        {
            "name": "id",
            "javaName": "id",
            "capitalizedJavaName": "Id",
            "javaType": "Long",
            "comment": "primary key",
            "isPrimaryKey": True,
            "primaryKey": True,
            "nullable": False,
            "isString": False,
            "maxLength": None,
            "last": False,
        },
        {
            "name": "username",
            "javaName": "username",
            "capitalizedJavaName": "Username",
            "javaType": "String",
            "comment": "login name",
            "isPrimaryKey": False,
            "primaryKey": False,
            "nullable": False,
            "isString": True,
            "maxLength": 64,
            "last": True,
        },
    ],
}


def verify_templates() -> list[str]:
    """Return a list of template rendering errors."""
    renderer = pystache.Renderer()
    failures: list[str] = []
    categories = sorted(path for path in TEMPLATE_ROOT.iterdir() if path.is_dir())
    for category in categories:
        templates = sorted(category.glob("*.mustache"))
        if not templates:
            failures.append(f"{category.name}: no Mustache templates found")
            continue
        for template in templates:
            rendered = renderer.render(template.read_text(encoding="utf-8"), CONTEXT)
            if not rendered.strip():
                failures.append(f"{category.name}/{template.name}: rendered empty output")
            if "{{" in rendered or "}}" in rendered:
                failures.append(f"{category.name}/{template.name}: unresolved Mustache tag")
            print(f"OK {category.name}/{template.name} ({len(rendered)} chars)")
    return failures


def main() -> int:
    failures = verify_templates()
    if failures:
        print("Template contract failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All Java templates rendered successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
