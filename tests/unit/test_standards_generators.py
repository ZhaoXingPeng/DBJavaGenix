"""Unit tests for standards generators (checkstyle/spotbugs/editorconfig/lombok)."""
import pytest

from dbjavagenix.standards import (
    generate_checkstyle_xml,
    generate_editorconfig,
    generate_lombok_config,
    generate_spotbugs_exclude_xml,
    generate_suppressions_xml,
)


class TestCheckstyle:
    def test_default_output_valid_xml(self):
        out = generate_checkstyle_xml()
        assert out.startswith('<?xml version="1.0"?>')
        assert '<module name="Checker">' in out
        assert '<property name="max" value="120"/>' in out

    def test_custom_line_limit(self):
        out = generate_checkstyle_xml(line_limit=140)
        assert '<property name="max" value="140"/>' in out

    def test_indent_propagates(self):
        out = generate_checkstyle_xml(indent=2)
        assert '<property name="basicOffset" value="2"/>' in out

    def test_suppress_generated_off(self):
        out = generate_checkstyle_xml(suppress_generated=False)
        assert "SuppressionFilter" not in out

    def test_includes_naming_modules(self):
        out = generate_checkstyle_xml()
        # Standard Google style naming checks
        for mod in ["ConstantName", "MethodName", "TypeName"]:
            assert f'<module name="{mod}"/>' in out

    def test_suppressions_xml(self):
        out = generate_suppressions_xml()
        assert "<suppressions>" in out
        assert "generated" in out

    def test_suppressions_custom_paths(self):
        out = generate_suppressions_xml([r".*[\\/]vendor[\\/].*"])
        assert "vendor" in out
        # Default "generated" pattern should NOT appear when paths are given
        assert "generated" not in out


class TestSpotbugs:
    def test_default_output(self):
        out = generate_spotbugs_exclude_xml()
        assert out.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert "<FindBugsFilter>" in out
        # Defaults include the entity-mutable-exposure suppression
        assert "EI_EXPOSE_REP" in out

    def test_custom_groups(self):
        out = generate_spotbugs_exclude_xml(
            rule_id_groups=[["SE_BAD_FIELD"]]
        )
        assert "SE_BAD_FIELD" in out
        assert "EI_EXPOSE_REP" not in out

    def test_path_patterns_added(self):
        out = generate_spotbugs_exclude_xml(
            additional_path_patterns=[".*test.*"]
        )
        assert "test" in out
        assert '<Source name="~.*test.*"/>' in out

    def test_empty_groups_skipped(self):
        out = generate_spotbugs_exclude_xml(rule_id_groups=[[]])
        assert "<Match>" not in out  # empty group produces no match


class TestEditorConfig:
    def test_default_output(self):
        out = generate_editorconfig()
        assert "root = true" in out
        assert "indent_size = 4" in out
        assert "end_of_line = lf" in out

    def test_custom_indent(self):
        out = generate_editorconfig(indent_size=2)
        assert "indent_size = 2" in out

    def test_xml_yaml_section(self):
        out = generate_editorconfig()
        # XML/YAML/JSON get indent_size = 2 regardless of default
        assert "[*.{xml,yml,yaml,json}]\nindent_size = 2" in out

    def test_makefile_uses_tab(self):
        out = generate_editorconfig()
        assert "[Makefile]\nindent_style = tab" in out

    def test_crlf_option(self):
        out = generate_editorconfig(line_endings="crlf")
        assert "end_of_line = crlf" in out


class TestLombok:
    def test_default_output(self):
        out = generate_lombok_config()
        assert "config.stopBubbling = true" in out
        assert "lombok.anyConstructor.addConstructorProperties = true" in out

    def test_accessors_chain_off_by_default(self):
        out = generate_lombok_config()
        assert "lombok.accessors.chain" not in out

    def test_accessors_chain_on(self):
        out = generate_lombok_config(accessors_chain=True)
        assert "lombok.accessors.chain = true" in out

    def test_suppress_warnings_off_by_default(self):
        out = generate_lombok_config()
        assert "lombok.addSuppressWarnings = false" in out

    def test_log_field_name(self):
        out = generate_lombok_config(log_field_name="LOGGER")
        assert "lombok.log.fieldName = LOGGER" in out

    def test_log_field_omitted_by_default(self):
        out = generate_lombok_config()
        assert "lombok.log.fieldName" not in out
