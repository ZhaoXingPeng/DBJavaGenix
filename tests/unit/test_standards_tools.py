"""Unit tests for standards_tools (MCP tool wrapping standards generators)."""

import asyncio
import json

import pytest

from dbjavagenix.database.standards_tools import (
    STANDARDS_TOOLS,
    handle_generate_quality_configs,
)


def _run(coro):
    return asyncio.run(coro)


class TestToolDefinition:
    def test_tool_registered(self):
        assert len(STANDARDS_TOOLS) == 1
        assert STANDARDS_TOOLS[0].name == "springboot_generate_quality_configs"

    def test_input_schema_has_defaults(self):
        schema = STANDARDS_TOOLS[0].inputSchema
        assert schema["properties"]["checkstyle_line_limit"]["default"] == 120
        assert schema["properties"]["checkstyle_indent"]["default"] == 4


class TestHandler:
    def test_default_returns_all_five_files(self):
        result = _run(handle_generate_quality_configs({}))
        payload = json.loads(result[0].text)
        assert payload["file_count"] == 5
        paths = [f["path"] for f in payload["files"]]
        assert "config/checkstyle/checkstyle.xml" in paths
        assert "config/checkstyle/checkstyle-suppressions.xml" in paths
        assert "config/spotbugs/spotbugs-exclude.xml" in paths
        assert ".editorconfig" in paths
        assert "lombok.config" in paths

    def test_include_files_subset(self):
        result = _run(
            handle_generate_quality_configs({"include_files": ["editorconfig", "lombok"]})
        )
        payload = json.loads(result[0].text)
        assert payload["file_count"] == 2
        paths = [f["path"] for f in payload["files"]]
        assert ".editorconfig" in paths
        assert "lombok.config" in paths

    def test_custom_checkstyle_line_limit(self):
        result = _run(
            handle_generate_quality_configs(
                {"checkstyle_line_limit": 100, "include_files": ["checkstyle"]}
            )
        )
        payload = json.loads(result[0].text)
        checkstyle = payload["files"][0]
        assert '<property name="max" value="100"/>' in checkstyle["content"]

    def test_crlf_line_endings(self):
        result = _run(
            handle_generate_quality_configs(
                {
                    "editorconfig_line_endings": "crlf",
                    "include_files": ["editorconfig"],
                }
            )
        )
        payload = json.loads(result[0].text)
        editorconfig = payload["files"][0]
        assert "end_of_line = crlf" in editorconfig["content"]

    def test_accessors_chain_propagates(self):
        result = _run(
            handle_generate_quality_configs(
                {"lombok_accessors_chain": True, "include_files": ["lombok"]}
            )
        )
        payload = json.loads(result[0].text)
        lombok = payload["files"][0]
        assert "lombok.accessors.chain = true" in lombok["content"]

    def test_empty_include_files_means_all(self):
        result = _run(handle_generate_quality_configs({"include_files": []}))
        payload = json.loads(result[0].text)
        assert payload["file_count"] == 5

    def test_payload_has_instructions(self):
        result = _run(handle_generate_quality_configs({}))
        payload = json.loads(result[0].text)
        assert "instructions" in payload
        assert "Write each file" in payload["instructions"]

    def test_file_has_path_language_content(self):
        result = _run(handle_generate_quality_configs({}))
        payload = json.loads(result[0].text)
        for f in payload["files"]:
            assert "path" in f
            assert "language" in f
            assert "content" in f
            assert len(f["content"]) > 0
