"""Regression tests for the MCP server process output boundary."""

import pytest
import typer

from dbjavagenix import cli


def test_server_startup_diagnostics_use_stderr(monkeypatch, capsys):
    async def complete_server():
        return None

    monkeypatch.setattr(cli, "run_server", complete_server)

    cli.server()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Starting DBJavaGenix MCP Server" in captured.err
    assert "Starting MCP server in stdio mode" in captured.err


def test_server_failure_diagnostics_use_stderr(monkeypatch, capsys):
    async def failing_server():
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(cli, "run_server", failing_server)

    with pytest.raises(typer.Exit) as error:
        cli.server()

    captured = capsys.readouterr()
    assert error.value.exit_code == 1
    assert captured.out == ""
    assert "Server error: controlled failure" in captured.err


def test_server_interrupt_diagnostics_use_stderr(monkeypatch, capsys):
    async def interrupted_server():
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_server", interrupted_server)

    cli.server()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Shutting down server" in captured.err
