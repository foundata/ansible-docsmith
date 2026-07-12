"""Tests for Ansible markup conversion (core/markup.py)."""

import pytest

from ansible_docsmith.core.defaults_comments import DefaultsCommentGenerator
from ansible_docsmith.core.doc_generators import (
    MarkdownDocumentationGenerator,
    RSTDocumentationGenerator,
)
from ansible_docsmith.core.markup import convert_ansible_markup, lint_ansible_markup


class TestConvertAnsibleMarkupMarkdown:
    """Markdown conversion of the individual markup constructs."""

    def test_basic_formatting(self):
        assert convert_ansible_markup("Use I(care).", "markdown") == "Use *care*."
        assert convert_ansible_markup("B(Really) do.", "markdown") == "**Really** do."
        assert convert_ansible_markup("Run C(foo --bar).", "markdown") == (
            "Run `foo --bar`."
        )

    def test_values_and_env(self):
        assert convert_ansible_markup("Set V(enabled).", "markdown") == (
            "Set `enabled`."
        )
        assert convert_ansible_markup("Reads E(HOME).", "markdown") == "Reads `HOME`."

    def test_urls_and_links(self):
        assert convert_ansible_markup("See U(https://example.com).", "markdown") == (
            "See <https://example.com>."
        )
        assert (
            convert_ansible_markup(
                "See L(the docs,https://example.com/doc).", "markdown"
            )
            == "See [the docs](https://example.com/doc)."
        )

    def test_rst_ref_renders_as_plain_text(self):
        assert (
            convert_ansible_markup("See R(the docs,ansible_documentation).", "markdown")
            == "See the docs."
        )

    def test_horizontal_line(self):
        result = convert_ansible_markup("HORIZONTALLINE", "markdown")
        assert "---" in result

    def test_module_link_for_wellformed_fqcn(self):
        result = convert_ansible_markup("Use M(ansible.builtin.copy).", "markdown")
        assert result == (
            "Use [`ansible.builtin.copy`]"
            "(https://docs.ansible.com/ansible/latest/collections/"
            "ansible/builtin/copy_module.html)."
        )

    def test_malformed_module_stays_verbatim(self):
        # Invalid markup must never be dropped or replaced by error text
        result = convert_ansible_markup("Use M(bad) here.", "markdown")
        assert result == "Use M(bad) here."

    def test_plugin_link(self):
        result = convert_ansible_markup(
            "Uses P(ansible.builtin.file#lookup).", "markdown"
        )
        assert result == (
            "Uses [`ansible.builtin.file`]"
            "(https://docs.ansible.com/ansible/latest/collections/"
            "ansible/builtin/file_lookup.html)."
        )

    def test_option_links_to_known_role_variable(self):
        result = convert_ansible_markup(
            "See O(foo_domain) for details.",
            "markdown",
            role_options={"foo_domain", "foo_email"},
        )
        assert result == "See [`foo_domain`](#variable-foo_domain) for details."

    def test_option_with_value_links_too(self):
        result = convert_ansible_markup(
            "Set O(foo_domain=example.com).",
            "markdown",
            role_options={"foo_domain"},
        )
        assert result == "Set [`foo_domain=example.com`](#variable-foo_domain)."

    def test_unknown_option_renders_as_code(self):
        result = convert_ansible_markup(
            "See O(other_var).", "markdown", role_options={"foo_domain"}
        )
        assert result == "See `other_var`."

    def test_dotted_option_path_is_not_linked(self):
        # Nested anchors depend on template depth; only plain top-level
        # names are linked
        result = convert_ansible_markup(
            "See O(foo_domain.name).", "markdown", role_options={"foo_domain"}
        )
        assert result == "See `foo_domain.name`."

    def test_no_role_options_means_no_links(self):
        result = convert_ansible_markup("See O(foo_domain).", "markdown")
        assert result == "See `foo_domain`."


class TestConvertAnsibleMarkupRST:
    """RST conversion uses inline literals and no Sphinx roles."""

    def test_basic_formatting(self):
        assert convert_ansible_markup("Run C(foo).", "rst") == "Run ``foo``."
        assert convert_ansible_markup("Use I(care).", "rst") == "Use *care*."
        assert convert_ansible_markup("B(Really).", "rst") == "**Really**."

    def test_option_is_plain_literal_without_anchor_link(self):
        result = convert_ansible_markup(
            "See O(foo_domain).", "rst", role_options={"foo_domain"}
        )
        assert result == "See ``foo_domain``."

    def test_module_link(self):
        result = convert_ansible_markup("Use M(ansible.builtin.copy).", "rst")
        assert result == (
            "Use `ansible.builtin.copy "
            "<https://docs.ansible.com/ansible/latest/collections/"
            "ansible/builtin/copy_module.html>`__."
        )

    def test_link(self):
        result = convert_ansible_markup("L(docs,https://example.com)", "rst")
        assert result == "`docs <https://example.com>`__"


class TestConvertAnsibleMarkupPassthrough:
    """Text without markup must come out byte-identical."""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "Plain text without any markup.",
            "Markdown stays: *emph*, **strong**, `code`, [link](https://x.y).",
            "Multi paragraph\n\ntext with  double  spaces preserved.",
            "- a list\n- with items\n\n```yaml\nkey: value\n```\n\ntail",
            "Line one\nline two (single newline preserved).",
        ],
    )
    def test_byte_identical_without_markup(self, text):
        assert convert_ansible_markup(text, "markdown") == text
        assert convert_ansible_markup(text, "rst") == text

    def test_paragraph_separators_preserved_around_markup(self):
        text = "First C(one).\n\n\nSecond C(two)."
        result = convert_ansible_markup(text, "markdown")
        assert result == "First `one`.\n\n\nSecond `two`."

    def test_code_fences_with_markup_like_text_stay_untouched(self):
        fence = "```yaml\nfoo: C(not converted)\n```"
        assert convert_ansible_markup(fence, "markdown") == fence

    def test_indented_code_block_stays_untouched(self):
        block = "    foo = C(bar)\n    baz = 1"
        assert convert_ansible_markup(block, "markdown") == block

    def test_mixed_prose_and_fence_chunks(self):
        text = "Use C(tool) like:\n\n```sh\ntool C(x)\n```"
        result = convert_ansible_markup(text, "markdown")
        assert result == "Use `tool` like:\n\n```sh\ntool C(x)\n```"

    def test_unsupported_target_raises(self):
        with pytest.raises(ValueError):
            convert_ansible_markup("C(x)", "asciidoc")


class TestMarkupInGeneratorFilters:
    """Integration of markup conversion into the README filters."""

    def test_format_description_filter_markdown(self):
        generator = MarkdownDocumentationGenerator()
        generator._role_options = {"foo_port"}

        result = generator._format_description_filter(["Set O(foo_port) to C(8080)."])
        assert result == "Set [`foo_port`](#variable-foo_port) to `8080`."

    def test_format_description_filter_rst(self):
        generator = RSTDocumentationGenerator()

        result = generator._format_description_filter("Run C(foo --bar).")
        assert result == "Run ``foo --bar``."

    def test_table_description_pipe_in_markup_is_escaped(self):
        generator = MarkdownDocumentationGenerator()

        result = generator._format_table_description_filter("Choose V(a|b).")
        assert result == "Choose `a\\|b`."

    def test_table_truncation_never_splits_links(self):
        """Truncation must drop a whole link rather than cut through it."""
        generator = MarkdownDocumentationGenerator()

        text = "Copy files with M(ansible.builtin.copy) whenever needed."
        # Force truncation inside the long generated link
        result = generator._format_table_description_filter(
            text, variable_name="myvar", max_length=40
        )
        assert result == "Copy files with […](#variable-myvar)"

    def test_table_truncation_never_splits_code_spans(self):
        generator = MarkdownDocumentationGenerator()

        result = generator._format_table_description_filter(
            "Values like C(some-quite-long-value) work.",
            variable_name="myvar",
            max_length=25,
        )
        assert result == "Values like […](#variable-myvar)"

    def test_defaults_comments_use_markdown_without_anchor_links(self):
        generator = DefaultsCommentGenerator()

        comment_lines = generator._format_block_comment(
            {
                "description": "Set O(foo_port) via C(cli).",
                "type": "str",
                "required": False,
            }
        )
        text = "\n".join(comment_lines)
        # Markup converted to Markdown conventions ...
        assert "`foo_port`" in text
        assert "`cli`" in text
        # ... but no README anchor links inside a YAML comment
        assert "](#variable-" not in text
        assert "O(" not in text


class TestLintAnsibleMarkup:
    """Linting of invalid Ansible markup constructs."""

    def test_invalid_module_fqcn(self):
        messages = lint_ansible_markup("Use M(copy) for this.")
        assert len(messages) == 1
        assert 'Module name "copy" is not a FQCN' in messages[0]

    def test_unclosed_construct(self):
        messages = lint_ansible_markup("Use C(unclosed here.")
        assert len(messages) == 1
        assert 'Cannot find closing ")"' in messages[0]

    def test_link_without_url(self):
        messages = lint_ansible_markup("See L(only text) for details.")
        assert len(messages) == 1
        assert "Cannot find comma" in messages[0]

    def test_valid_markup_produces_no_messages(self):
        assert lint_ansible_markup("Use C(code) and M(ansible.builtin.copy).") == []

    def test_plain_text_produces_no_messages(self):
        assert lint_ansible_markup("No markup at all, just text.") == []
        assert lint_ansible_markup("") == []

    def test_code_blocks_are_not_linted(self):
        text = "```yaml\nvalue: M(bad)\n```"
        assert lint_ansible_markup(text) == []

    def test_multiple_errors_are_all_reported(self):
        messages = lint_ansible_markup("M(one) and P(two).\n\nAlso M(three).")
        assert len(messages) == 3
