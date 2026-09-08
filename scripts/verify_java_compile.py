"""Compile a representative Java 21 project rendered from current templates."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import pystache

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "src" / "dbjavagenix" / "templates" / "java" / "sb35-java21"
FIXTURE_PACKAGE = "com.dbjavagenix.compilefixture"

TEMPLATES = (
    ("entity.mustache", "entityPackage", "Invoice.java"),
    ("dao.mustache", "daoPackage", "InvoiceDao.java"),
    ("dto.mustache", "dtoPackage", "InvoiceDTO.java"),
    ("service.mustache", "servicePackage", "InvoiceService.java"),
    ("serviceImpl.mustache", "serviceImplPackage", "InvoiceServiceImpl.java"),
    ("controller.mustache", "controllerPackage", "InvoiceController.java"),
)

CONTEXT = {
    "entityPackage": f"{FIXTURE_PACKAGE}.entity",
    "dtoPackage": f"{FIXTURE_PACKAGE}.dto",
    "daoPackage": f"{FIXTURE_PACKAGE}.dao",
    "servicePackage": f"{FIXTURE_PACKAGE}.service",
    "serviceImplPackage": f"{FIXTURE_PACKAGE}.service.impl",
    "controllerPackage": f"{FIXTURE_PACKAGE}.controller",
    "className": "Invoice",
    "tableName": "invoice",
    "entityNameLowerCase": "invoice",
    "comment": "Invoice",
    "author": "DBJavaGenix CI",
    "date": "2026-09-08",
    "primaryKeyName": "id",
    "primaryKeyType": "Long",
    "capitalizedPrimaryKeyName": "Id",
    "serialVersionUID": "1",
    "hasJakarta": True,
    "hasSpringDoc": True,
    "useLombok": True,
    "useSwagger": True,
    "generateDto": True,
    "imports": ["java.math.BigDecimal", "java.time.OffsetDateTime"],
    "columns": [
        {
            "name": "id",
            "javaName": "id",
            "capitalizedJavaName": "Id",
            "javaType": "Long",
            "comment": "Primary key",
            "isPrimaryKey": True,
            "nullable": False,
            "isString": False,
            "maxLength": None,
            "last": False,
        },
        {
            "name": "amount",
            "javaName": "amount",
            "capitalizedJavaName": "Amount",
            "javaType": "BigDecimal",
            "comment": "Amount",
            "isPrimaryKey": False,
            "nullable": False,
            "isString": False,
            "maxLength": None,
            "last": False,
        },
        {
            "name": "created_at",
            "javaName": "createdAt",
            "capitalizedJavaName": "CreatedAt",
            "javaType": "OffsetDateTime",
            "comment": "Creation time",
            "isPrimaryKey": False,
            "nullable": True,
            "isString": False,
            "maxLength": None,
            "last": True,
        },
    ],
}

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.5</version>
    <relativePath/>
  </parent>
  <groupId>com.dbjavagenix</groupId>
  <artifactId>generated-compile-fixture</artifactId>
  <version>1.0.0</version>
  <properties>
    <java.version>21</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springdoc</groupId>
      <artifactId>springdoc-openapi-starter-webmvc-api</artifactId>
      <version>2.8.9</version>
    </dependency>
    <dependency>
      <groupId>org.projectlombok</groupId>
      <artifactId>lombok</artifactId>
      <optional>true</optional>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <configuration>
          <annotationProcessorPaths>
            <path>
              <groupId>org.projectlombok</groupId>
              <artifactId>lombok</artifactId>
            </path>
          </annotationProcessorPaths>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""


def render_fixture(project_dir: Path) -> list[Path]:
    """Render the representative sb35-java21 source set into ``project_dir``."""
    source_root = project_dir / "src" / "main" / "java"
    renderer = pystache.Renderer()
    rendered_files: list[Path] = []

    for template_name, package_key, output_name in TEMPLATES:
        template_path = TEMPLATE_ROOT / template_name
        code = renderer.render(template_path.read_text(encoding="utf-8"), CONTEXT)
        output_path = source_root / Path(CONTEXT[package_key].replace(".", "/")) / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        rendered_files.append(output_path)

    (project_dir / "pom.xml").write_text(POM, encoding="utf-8")
    return rendered_files


def build_maven_command(maven: str) -> list[str]:
    """Build the explicit, batch-mode compile command for a rendered fixture."""
    return [maven, "-B", "-ntp", "-DskipTests", "clean", "compile"]


def cleanup_fixture(project_dir: Path, *, keep_fixture: bool, compile_succeeded: bool) -> None:
    """Remove a successful fixture unless diagnostics were explicitly requested."""
    if keep_fixture or not compile_succeeded:
        print(f"Fixture retained at {project_dir}")
        return
    shutil.rmtree(project_dir, ignore_errors=True)


def verify_java_compile(*, keep_fixture: bool = False) -> int:
    """Render and compile the fixture, retaining it only when requested or on failure."""
    maven = shutil.which("mvn")
    if maven is None:
        print("Maven executable 'mvn' was not found on PATH")
        return 1

    project_dir = Path(tempfile.mkdtemp(prefix="dbjavagenix-java-compile-"))
    compile_succeeded = False
    try:
        rendered_files = render_fixture(project_dir)
        command = build_maven_command(maven)
        print(f"Rendered {len(rendered_files)} sb35-java21 files to {project_dir}", flush=True)
        print("$ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=project_dir, text=True, check=False)
        if result.returncode != 0:
            print("Java compile failed")
            return result.returncode
        compile_succeeded = True
        print("Generated Java compile smoke passed")
        return 0
    finally:
        cleanup_fixture(
            project_dir,
            keep_fixture=keep_fixture,
            compile_succeeded=compile_succeeded,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-fixture",
        action="store_true",
        help="Keep the generated temporary Maven project after a successful compile.",
    )
    args = parser.parse_args()
    return verify_java_compile(keep_fixture=args.keep_fixture)


if __name__ == "__main__":
    raise SystemExit(main())
