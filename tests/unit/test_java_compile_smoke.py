"""Unit coverage for the generated Java compile fixture."""

import runpy
import xml.etree.ElementTree as element_tree
from pathlib import Path


_SCRIPT = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "verify_java_compile.py"))
CONTEXT = _SCRIPT["CONTEXT"]
POM = _SCRIPT["POM"]
TEMPLATES = _SCRIPT["TEMPLATES"]
build_maven_command = _SCRIPT["build_maven_command"]
cleanup_fixture = _SCRIPT["cleanup_fixture"]
render_fixture = _SCRIPT["render_fixture"]
render_real_sqlite_fixture = _SCRIPT["render_real_sqlite_fixture"]


def test_rendered_fixture_contains_every_java_layer(tmp_path):
    files = render_fixture(tmp_path)

    assert len(files) == len(TEMPLATES) == 6
    assert {path.name for path in files} == {
        "Invoice.java",
        "InvoiceDao.java",
        "InvoiceDTO.java",
        "InvoiceService.java",
        "InvoiceServiceImpl.java",
        "InvoiceController.java",
    }
    for (_, package_key, _), path in zip(TEMPLATES, files, strict=True):
        rendered = path.read_text(encoding="utf-8")
        assert "{{" not in rendered
        assert "}}" not in rendered
        assert f"package {CONTEXT[package_key]};" in rendered


def test_real_sqlite_fixture_uses_generated_package_paths_and_closes_database(tmp_path):
    files = render_real_sqlite_fixture(tmp_path)

    assert len(files) == len(TEMPLATES) == 6
    assert {path.relative_to(tmp_path / "src" / "main" / "java").as_posix() for path in files} == {
        "com/dbjavagenix/compilefixture/entity/Invoice.java",
        "com/dbjavagenix/compilefixture/dao/InvoiceDao.java",
        "com/dbjavagenix/compilefixture/dto/InvoiceDTO.java",
        "com/dbjavagenix/compilefixture/service/InvoiceService.java",
        "com/dbjavagenix/compilefixture/service/impl/InvoiceServiceImpl.java",
        "com/dbjavagenix/compilefixture/controller/InvoiceController.java",
    }
    dto = next(path for path in files if path.name == "InvoiceDTO.java").read_text(encoding="utf-8")
    service = next(path for path in files if path.name == "InvoiceService.java").read_text(
        encoding="utf-8"
    )
    controller = next(path for path in files if path.name == "InvoiceController.java").read_text(
        encoding="utf-8"
    )
    assert "package com.dbjavagenix.compilefixture.dto;" in dto
    assert "import com.dbjavagenix.compilefixture.dto.InvoiceDTO;" in service
    assert "import com.dbjavagenix.compilefixture.dto.InvoiceDTO;" in controller

    database_path = tmp_path / "invoice.db"
    database_path.unlink()
    assert not database_path.exists()


def test_fixture_pom_locks_java_and_spring_boot_versions():
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    root = element_tree.fromstring(POM)

    assert root.findtext("m:parent/m:version", namespaces=namespace) == "3.5.5"
    assert root.findtext("m:properties/m:java.version", namespaces=namespace) == "21"


def test_maven_command_is_non_interactive_compile_only():
    command = build_maven_command("mvn")

    assert command == ["mvn", "-B", "-ntp", "-DskipTests", "clean", "compile"]


def test_cleanup_removes_only_successful_default_fixture(tmp_path):
    successful_fixture = tmp_path / "successful"
    failed_fixture = tmp_path / "failed"
    requested_fixture = tmp_path / "requested"
    for fixture in (successful_fixture, failed_fixture, requested_fixture):
        fixture.mkdir()

    cleanup_fixture(successful_fixture, keep_fixture=False, compile_succeeded=True)
    cleanup_fixture(failed_fixture, keep_fixture=False, compile_succeeded=False)
    cleanup_fixture(requested_fixture, keep_fixture=True, compile_succeeded=True)

    assert not successful_fixture.exists()
    assert failed_fixture.exists()
    assert requested_fixture.exists()
