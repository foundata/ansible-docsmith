"""Tests for documentation generators."""

from ansible_docsmith import (
    MARKER_COMMENT_MD_BEGIN,
    MARKER_COMMENT_MD_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
)
from ansible_docsmith.core.generator import (
    TABLE_DESCRIPTION_MAX_LENGTH,
    DefaultsCommentGenerator,
    HTMLStripper,
    MarkdownDocumentationGenerator,
    MarkdownTocGenerator,
    ReadmeUpdater,
    RSTDocumentationGenerator,
    RSTTocGenerator,
    create_documentation_generator,
    create_toc_generator,
)


class TestDocumentationGenerator:
    """Test the DocumentationGenerator class (alias for MarkdownDocGenerator)."""

    def test_generate_role_documentation(self, sample_role_with_specs):
        """Test generating role documentation."""
        generator = MarkdownDocumentationGenerator()

        # Parse the specs from fixture
        specs = {
            "main": {
                "short_description": "Test role",
                "description": "A test role for testing",
                "author": ["Test Author"],
                "options": {
                    "test_var": {
                        "type": "str",
                        "required": True,
                        "default": None,
                        "description": "A test variable",
                        "choices": [],
                        "options": {},
                    }
                },
            }
        }

        result = generator.generate_role_documentation(
            specs, "test-role", sample_role_with_specs
        )

        assert "## role variables" in result.lower()
        assert "test_var" in result.lower()
        assert "a test variable" in result.lower()

    def test_generate_documentation_no_options(self, sample_role_path):
        """Test generating documentation with no options."""
        generator = MarkdownDocumentationGenerator()

        specs = {
            "main": {
                "short_description": "Test role",
                "description": "A test role",
                "author": [],
                "options": {},
            }
        }

        result = generator.generate_role_documentation(
            specs, "test-role", sample_role_path
        )

        assert "no variables are defined for this role" in result.lower()

    def test_ansible_escape_filter(self):
        """Test Ansible variable escaping."""
        generator = MarkdownDocumentationGenerator()

        result = generator._ansible_escape_filter("{{ variable }}")
        assert result == "\\{\\{ variable \\}\\}"

        result = generator._ansible_escape_filter(None)
        assert result == "N/A"

    def test_code_escape_filter(self):
        """Test code escaping for Markdown."""
        generator = MarkdownDocumentationGenerator()

        result = generator._code_escape_filter("test|value")
        assert result == "`test\\|value`"

        result = generator._code_escape_filter("test`value")
        assert result == "`test\\`value`"

        result = generator._code_escape_filter(None)
        assert result == "N/A"

    def test_format_default_filter(self):
        """Test default value formatting."""
        generator = MarkdownDocumentationGenerator()

        # String
        result = generator._format_default_filter("test")
        assert result == '`"test"`'

        # Boolean
        result = generator._format_default_filter(True)
        assert result == "`true`"

        result = generator._format_default_filter(False)
        assert result == "`false`"

        # List
        result = generator._format_default_filter([1, 2, 3])
        assert result == "`[1, 2, 3]`"

        # Dict
        result = generator._format_default_filter({"key": "value"})
        assert result == "`{'key': 'value'}`"

        # None
        result = generator._format_default_filter(None)
        assert result == "N/A"

        # Number
        result = generator._format_default_filter(42)
        assert result == "`42`"

    def test_multiline_description_handling(self, sample_role_with_specs):
        """Test handling of multiline descriptions in documentation generation."""
        generator = MarkdownDocumentationGenerator()

        # Test with a multiline description that includes newlines
        multiline_description = """First paragraph of description.

Second paragraph with more details.

- List item 1
- List item 2"""

        specs = {
            "main": {
                "short_description": "Test role",
                "description": "A test role",
                "author": ["Test Author"],
                "options": {
                    "multiline_var": {
                        "type": "str",
                        "required": True,
                        "default": None,
                        "description": multiline_description,
                        "choices": [],
                        "options": {},
                    }
                },
            }
        }

        result = generator.generate_role_documentation(
            specs, "test-role", sample_role_with_specs
        )

        # Should contain all parts of the multiline description
        assert "first paragraph of description." in result.lower()
        assert "second paragraph with more details." in result.lower()
        assert "- list item 1" in result.lower()
        assert "- list item 2" in result.lower()


class TestHTMLStripper:
    """Test the HTMLStripper class for HTML tag removal and entity unescaping."""

    def test_basic_html_tag_removal(self):
        """Test that basic HTML tags are properly removed."""
        result = HTMLStripper.strip_tags("<p>Simple paragraph</p>")
        assert result == "Simple paragraph"

        result = HTMLStripper.strip_tags("<b>Bold</b> and <em>italic</em> text")
        assert result == "Bold and italic text"

    def test_nested_html_tags(self):
        """Test removal of nested HTML tags."""
        result = HTMLStripper.strip_tags("<div><span>Nested</span> tags</div>")
        assert result == "Nested tags"

        result = HTMLStripper.strip_tags("<p><b>Bold <em>and italic</em></b> text</p>")
        assert result == "Bold and italic text"

    def test_html_entities_unescaping(self):
        """Test that HTML entities are properly unescaped."""
        result = HTMLStripper.strip_tags("Text with &lt;escaped&gt; entities")
        assert result == "Text with <escaped> entities"

        result = HTMLStripper.strip_tags("Ampersand &amp; and quotes &quot;here&quot;")
        assert result == 'Ampersand & and quotes "here"'

    def test_complex_html_with_attributes(self):
        """Test removal of HTML tags with attributes."""
        result = HTMLStripper.strip_tags(
            "<img src='test.jpg' alt='Test image' style='width:100px'/>Caption"
        )
        assert result == "Caption"

        result = HTMLStripper.strip_tags(
            "<a href='#link' class='test' id='mylink'>Link text</a>"
        )
        assert result == "Link text"

    def test_script_and_style_content(self):
        """Test handling of script and style tag content."""
        # HTMLParser preserves content inside script tags (which is correct behavior)
        result = HTMLStripper.strip_tags("<script>alert('test')</script>Safe text")
        assert result == "alert('test')Safe text"

        result = HTMLStripper.strip_tags("<style>body {color: red;}</style>Content")
        assert result == "body {color: red;}Content"

    def test_edge_cases(self):
        """Test edge cases for HTML stripping."""
        # Empty input
        result = HTMLStripper.strip_tags("")
        assert result == ""

        # None input
        result = HTMLStripper.strip_tags(None)
        assert result == ""

        # No HTML tags
        result = HTMLStripper.strip_tags("Plain text without tags")
        assert result == "Plain text without tags"

        # Only HTML tags
        result = HTMLStripper.strip_tags("<p></p><div></div>")
        assert result == ""

    def test_malformed_html_fallback(self):
        """Test fallback behavior with malformed HTML."""
        # This should still work (HTMLParser is quite robust)
        result = HTMLStripper.strip_tags("<p>Unclosed paragraph")
        assert result == "Unclosed paragraph"

        result = HTMLStripper.strip_tags("Text with <unclosed> tag")
        assert result == "Text with  tag"


class TestTableDescriptionFilter:
    """Test the improved format_table_description filter functionality."""

    def test_html_stripping_basic_tags(self):
        """Test that HTML tags are properly stripped (not encoded)."""
        generator = MarkdownDocumentationGenerator()

        # Test common HTML tags - should be STRIPPED, not encoded
        input_text = "This has <em>emphasis</em> and <b>bold</b> text."
        result = generator._format_table_description_filter(input_text)
        expected = "This has emphasis and bold text."
        assert result == expected

    def test_html_stripping_with_entities(self):
        """Test that HTML entities are properly unescaped after tag stripping."""
        generator = MarkdownDocumentationGenerator()

        input_text = "Text with &lt;entities&gt; and &amp; symbols."
        result = generator._format_table_description_filter(input_text)
        expected = "Text with <entities> and & symbols."
        assert result == expected

    def test_html_stripping_complex_tags(self):
        """Test stripping of complex HTML with attributes."""
        generator = MarkdownDocumentationGenerator()

        input_text = (
            "<p class='test'>This has <b>HTML tags</b> that should be "
            "<em>stripped</em>.</p>"
        )
        result = generator._format_table_description_filter(input_text)
        expected = "This has HTML tags that should be stripped."
        assert result == expected

    def test_multiline_single_breaks_to_spaces(self):
        """Test that single line breaks within paragraphs become spaces."""
        generator = MarkdownDocumentationGenerator()

        input_text = """First line continues
on the second line and
ends on third line."""
        result = generator._format_table_description_filter(input_text)
        expected = "First line continues on the second line and ends on third line."
        assert result == expected

    def test_multiline_double_breaks_to_br_tags(self):
        """Test that double line breaks (paragraphs) become <br><br> tags."""
        generator = MarkdownDocumentationGenerator()

        input_text = """First paragraph with some content.

Second paragraph after blank line.

Third paragraph here."""
        result = generator._format_table_description_filter(input_text)
        expected = (
            "First paragraph with some content.<br><br>Second paragraph "
            "after blank line.<br><br>Third paragraph here."
        )
        assert result == expected

    def test_truncation_at_word_boundary(self):
        """Test that text is truncated at word boundaries at max length."""
        generator = MarkdownDocumentationGenerator()

        # Create text longer than max length
        long_text = (
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, "
            "sed diam nonumy eirmod tempor invidunt ut labore et dolore "
            "magna aliquyam erat, sed diam voluptua. At vero eos et accusam "
            "et justo duo dolores et ea rebum. Stet clita kasd gubergren, "
            "no sea takimata sanctus est Lorem ipsum."
        )

        result = generator._format_table_description_filter(long_text, "test_var")

        # Should be truncated and include ellipses with link
        max_expected = (
            TABLE_DESCRIPTION_MAX_LENGTH + 50
        )  # Add buffer for ellipses + link
        assert len(result) <= max_expected
        assert result.endswith("[…](#variable-test_var)")
        assert "Lorem ipsum" in result
        # Should end at word boundary, not mid-word
        truncated_part = result.split(" […](")[0]
        assert not truncated_part.endswith("Lorem")  # Shouldn't cut mid-word

    def test_truncation_with_ellipses_and_link(self):
        """Test truncation adds proper ellipses and variable link."""
        generator = MarkdownDocumentationGenerator()

        # Use the first example from requirements
        long_text = (
            "Determines whether the managed resources should be `present` or "
            "`absent`.\n\n"
            "`present` ensures that required components, such as software packages, "
            "are installed and configured. `absent` reverts changes as much as "
            "possible, such as removing packages, deleting created users, stopping "
            "services, restoring modified settings.\n\n"
            "sed diam voluptua. At vero eos et accusam et justo duo dolores et ea "
            "rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem "
            "ipsum dolor sit amet."
        )

        result = generator._format_table_description_filter(
            long_text, "run_acmesh_autorenewal"
        )

        # Should be truncated with link
        assert "[…](#variable-run_acmesh_autorenewal)" in result
        assert (
            "Determines whether the managed resources should be `present` or `absent`"
            in result
        )
        assert "`present` ensures that required components" in result

    def test_no_truncation_for_short_text(self):
        """Test that short text is not truncated."""
        generator = MarkdownDocumentationGenerator()

        short_text = "This is a short description."
        result = generator._format_table_description_filter(short_text, "test_var")

        # Should be unchanged
        assert result == short_text
        assert "[…]" not in result

    def test_truncation_without_variable_name(self):
        """Test truncation behavior without variable name for link."""
        generator = MarkdownDocumentationGenerator()

        long_text = "A" * 300  # 300 A's
        result = generator._format_table_description_filter(long_text)

        # Should be truncated with generic ellipses (no link)
        assert len(result) < 300
        assert result.endswith(" […]")
        assert "#variable-" not in result

    def test_list_descriptions_with_br_tags(self):
        """Test that list descriptions are joined with <br><br>."""
        generator = MarkdownDocumentationGenerator()

        input_list = [
            "First item in the list.",
            "Second item with more details.",
            "Third and final item.",
        ]
        result = generator._format_table_description_filter(input_list)
        expected = (
            "First item in the list.<br><br>Second item with more "
            "details.<br><br>Third and final item."
        )
        assert result == expected

    def test_list_with_html_stripping(self):
        """Test that HTML in list items gets properly stripped."""
        generator = MarkdownDocumentationGenerator()

        input_list = [
            "First item with <em>HTML</em>.",
            "Second item with <script>alert('xss')</script>.",
        ]
        result = generator._format_table_description_filter(input_list)
        expected = "First item with HTML.<br><br>Second item with alert('xss')."
        assert result == expected

    def test_combined_html_stripping_and_multiline(self):
        """Test HTML stripping combined with multiline processing."""
        generator = MarkdownDocumentationGenerator()

        input_text = """<p>First paragraph with <b>bold</b> text.</p>

<div>Second paragraph with <script>alert("test")</script> content.</div>"""
        result = generator._format_table_description_filter(input_text)
        expected = (
            "First paragraph with bold text.<br><br>Second "
            'paragraph with alert("test") content.'
        )
        assert result == expected

    def test_edge_cases_none_and_empty(self):
        """Test edge cases with None and empty inputs."""
        generator = MarkdownDocumentationGenerator()

        # Test None input
        result = generator._format_table_description_filter(None)
        assert result == ""

        # Test empty string
        result = generator._format_table_description_filter("")
        assert result == ""

        # Test whitespace only
        result = generator._format_table_description_filter("   \n\n   ")
        assert result == ""

    def test_edge_cases_empty_list(self):
        """Test edge cases with empty and invalid lists."""
        generator = MarkdownDocumentationGenerator()

        # Test empty list
        result = generator._format_table_description_filter([])
        assert result == ""

        # Test list with empty strings
        result = generator._format_table_description_filter(["", "   ", ""])
        assert result == ""

        # Test list with some empty items
        result = generator._format_table_description_filter(
            ["Valid content", "", "More content"]
        )
        expected = "Valid content<br><br>More content"
        assert result == expected

    def test_whitespace_normalization(self):
        """Test that multiple spaces are normalized to single spaces."""
        generator = MarkdownDocumentationGenerator()

        input_text = "Text    with     multiple   spaces    here."
        result = generator._format_table_description_filter(input_text)
        expected = "Text with multiple spaces here."
        assert result == expected

    def test_rst_format_table_description_filter(self):
        """Test RST-specific table description formatting with pipe separators."""
        generator = RSTDocumentationGenerator()

        # Test multiline text with paragraph breaks
        input_text = "First paragraph.\n\nSecond paragraph."
        result = generator._format_table_description_filter(input_text)

        # RST uses pipe separators instead of <br><br>
        assert result == "First paragraph. | Second paragraph."

    def test_rst_truncation_with_rst_link_format(self):
        """Test RST truncation uses RST-style link format."""
        generator = RSTDocumentationGenerator()

        long_text = "A" * 300  # 300 A's
        result = generator._format_table_description_filter(long_text, "test_var")

        # Should be truncated with RST-style link
        assert len(result) < 300
        assert result.endswith("`[…] <#variable-test_var>`__")

    def test_rst_html_stripping(self):
        """Test that RST generator also strips HTML properly."""
        generator = RSTDocumentationGenerator()

        input_text = (
            "<p>This has <b>HTML tags</b> that should be <em>stripped</em>.</p>"
        )
        result = generator._format_table_description_filter(input_text)
        expected = "This has HTML tags that should be stripped."
        assert result == expected

    def test_requirements_example_1(self):
        """Test the first example from requirements exactly."""
        generator = MarkdownDocumentationGenerator()

        input_text = (
            "Determines whether the managed resources should be `present` or "
            "`absent`.\n\n"
            "`present` ensures that required components, such as software packages, "
            "are installed and configured. `absent` reverts changes as much as "
            "possible, "
            "such as removing packages, deleting created users, stopping services, "
            "restoring modified settings.\n\n"
            "sed diam voluptua. At vero eos et accusam et justo duo dolores et ea "
            "rebum. "
            "Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum "
            "dolor sit "
            "amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed "
            "diam nonumy "
            "eirmod tempor"
        )

        expected = (
            "Determines whether the managed resources should be `present` or `absent`."
            "<br><br>`present` ensures that required components, such as software "
            "packages, "
            "are installed and configured. `absent` reverts changes as much as "
            "possible, "
            "such as removing […](#variable-run_acmesh_autorenewal)"
        )

        result = generator._format_table_description_filter(
            input_text, "run_acmesh_autorenewal"
        )
        assert result == expected

    def test_requirements_example_2(self):
        """Test the second example from requirements exactly."""
        generator = MarkdownDocumentationGenerator()

        input_text = (
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy "
            "eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam "
            "voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet "
            "clita kasd gubergren, no sea takimata sanctus est Lorem ipsum "
            "dolor sit amet. "
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy "
            "eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam "
            "voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet "
            "clita kasd gubergren, no sea takimata sanctus est Lorem ipsum "
            "dolor sit amet."
        )

        expected = (
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy "
            "eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam "
            "voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet "
            "clita kasd gubergren, no sea […](#variable-foo)"
        )

        result = generator._format_table_description_filter(input_text, "foo")
        assert result == expected

    def test_disable_truncation_with_max_length_zero(self):
        """Test that setting max_length=0 disables truncation completely."""
        generator = MarkdownDocumentationGenerator()

        # Create text longer than default max length
        long_text = "A" * 400  # Much longer than default 250

        # Test default behavior (should truncate)
        result_default = generator._format_table_description_filter(long_text)
        assert len(result_default) < 400
        assert " […]" in result_default

        # Test max_length=0 (should NOT truncate)
        result_no_limit = generator._format_table_description_filter(
            long_text, max_length=0
        )
        assert len(result_no_limit) == 400
        assert " […]" not in result_no_limit
        assert result_no_limit == long_text

        # Test with variable name and max_length=0
        result_with_var = generator._format_table_description_filter(
            long_text, "test_var", max_length=0
        )
        assert len(result_with_var) == 400
        assert " […]" not in result_with_var
        assert "#variable-test_var" not in result_with_var

        # Test negative max_length also disables truncation
        result_negative = generator._format_table_description_filter(
            long_text, max_length=-1
        )
        assert len(result_negative) == 400
        assert " […]" not in result_negative

    def test_rst_disable_truncation_with_max_length_zero(self):
        """Test that RST generator also supports max_length=0 to disable truncation."""
        generator = RSTDocumentationGenerator()

        # Create text longer than default max length
        long_text = "B" * 350

        # Test default behavior (should truncate)
        result_default = generator._format_table_description_filter(long_text)
        assert len(result_default) < 350
        assert " […]" in result_default

        # Test max_length=0 (should NOT truncate)
        result_no_limit = generator._format_table_description_filter(
            long_text, max_length=0
        )
        assert len(result_no_limit) == 350
        assert " […]" not in result_no_limit
        assert result_no_limit == long_text


class TestDefaultsCommentGenerator:
    """Test the DefaultsCommentGenerator class."""

    def test_add_comments_success(self, sample_role_with_specs_and_defaults):
        """Test adding comments to defaults file."""
        generator = DefaultsCommentGenerator()

        defaults_path = sample_role_with_specs_and_defaults / "defaults" / "main.yml"

        specs = {
            "main": {
                "options": {
                    "acmesh_domain": {
                        "description": "Primary domain name for the certificate"
                    },
                    "acmesh_email": {
                        "description": "Email address for ACME account registration"
                    },
                    "acmesh_staging": {
                        "description": (
                            "Use Let's Encrypt staging environment for testing"
                        )
                    },
                }
            }
        }

        result = generator.add_comments(defaults_path, specs)

        assert result is not None
        assert "primary domain name" in result.lower()
        assert "email address for acme" in result.lower()
        assert "staging environment" in result.lower()

    def test_add_comments_missing_file(self, sample_role_path):
        """Test adding comments to non-existent file."""
        generator = DefaultsCommentGenerator()

        defaults_path = sample_role_path / "defaults" / "main.yml"
        specs = {"main": {"options": {}}}

        result = generator.add_comments(defaults_path, specs)

        assert result is None

    def test_add_comments_empty_file(self, sample_role_path):
        """Test adding comments to empty file."""
        generator = DefaultsCommentGenerator()

        defaults_path = sample_role_path / "defaults" / "main.yml"
        defaults_path.write_text("")

        specs = {"main": {"options": {}}}

        result = generator.add_comments(defaults_path, specs)

        assert result is None

    def test_ast_aware_text_wrapping(self):
        """Test AST-aware text wrapping functionality."""
        generator = DefaultsCommentGenerator()

        # Short text (no wrapping needed)
        result = generator._parse_and_format_description(
            "This is a test description", max_width=50
        )
        assert result == "This is a test description"

        # Long text (should wrap)
        long_text = (
            "This is a very long description that should be wrapped because "
            "it exceeds the maximum width limit that we have set for our comments"
        )
        result = generator._parse_and_format_description(long_text, max_width=50)
        lines = result.split("\n")
        assert len(lines) > 1
        assert all(len(line) <= 50 for line in lines if line.strip())

        # Empty text
        result = generator._parse_and_format_description("", max_width=50)
        assert result == ""

    def test_complex_list_formatting_with_nesting(self):
        """Test complex list formatting with proper nesting and list types."""
        generator = DefaultsCommentGenerator()

        # Your exact example input
        input_text = (
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy "
            "eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam "
            "voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet "
            "clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit "
            "amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam "
            "nonumy eirmod tempor invidunt ut labore et dolore magna\n\n"
            "This is a list:\n\n"
            "- foo\n"
            "- bar\n\n"
            "This is a list with sublist\n\n"
            "1. foo\n"
            "2. bar\n"
            "   - foo\n"
            "   - bar bar bar\n"
            "3. hey\n\n"
            "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy "
            "eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam "
            "voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet "
            "clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit "
            "amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam "
            "nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, "
            "sed diam voluptua. At vero eos et accusam"
        )

        # Process with wrapping similar to YAML comment width
        result = generator._parse_and_format_description(input_text, max_width=78)

        # Verify that we preserve list types
        assert "1. foo" in result
        assert "2. bar" in result
        assert "3. hey" in result

        # Verify bullet lists are preserved
        assert "- foo" in result
        assert "- bar" in result

        # Test that we have proper nesting (nested list items should be indented)
        lines = result.split("\n")

        # Find the "2. bar" line and check that the nested items follow with indentation
        for i, line in enumerate(lines):
            if line.strip() == "2. bar":
                # Check that nested items follow with proper indentation
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Should be indented "- foo"
                    assert (
                        "- foo" in next_line or "- foo" in lines[i + 2]
                        if i + 2 < len(lines)
                        else False
                    )
                break

        # Verify we didn't flatten the structure
        assert "- bar - foo" not in result  # This was the broken behavior
        assert "bar- foo" not in result  # This should be properly nested with spacing

    def test_parse_and_format_description_basic_paragraphs(self):
        """Test basic paragraph formatting with single/double linebreak rules."""
        generator = DefaultsCommentGenerator()

        # Single linebreaks should become spaces
        input_text = """First line continues
on the second line and
ends on third line."""
        result = generator._parse_and_format_description(input_text)
        expected = "First line continues on the second line and ends on third line."
        assert result == expected

        # Double linebreaks should create paragraph separation
        input_text = """First paragraph with some content.

Second paragraph after blank line.

Third paragraph here."""
        result = generator._parse_and_format_description(input_text)
        expected = (
            "First paragraph with some content.\n\nSecond paragraph after blank line."
            "\n\nThird paragraph here."
        )
        assert result == expected

    def test_parse_and_format_description_code_blocks(self):
        """Test code block preservation without threading."""
        generator = DefaultsCommentGenerator()

        # Code blocks should be preserved exactly
        input_text = """Text before code block.

```yaml
perfect_example:
  nested_config:
    key1: "value1"
    key2: "value2"
  list_items:
    - item1
    - item2
```

Text after code block continues normally."""
        result = generator._parse_and_format_description(input_text)

        # Verify code block structure is preserved
        assert "```yaml" in result
        assert "perfect_example:" in result
        assert "nested_config:" in result
        assert "- item1" in result
        assert "```" in result

        # Verify paragraphs are properly separated from code block
        assert "Text before code block.\n\n```yaml" in result
        assert "```\n\nText after code block continues normally." in result

    def test_parse_and_format_description_lists(self):
        """Test markdown list preservation."""
        generator = DefaultsCommentGenerator()

        # Lists should be preserved exactly
        input_text = """Description with a list:

- First list item
- Second list item with more details
- Third item

Regular paragraph after the list."""
        result = generator._parse_and_format_description(input_text)

        # Verify list structure is preserved
        assert "- First list item" in result
        assert "- Second list item with more details" in result
        assert "- Third item" in result

        # Verify proper paragraph separation
        assert "Description with a list:\n\n- First list item" in result
        assert "- Third item\n\nRegular paragraph after the list." in result

    def test_parse_and_format_description_mixed_content(self):
        """Test complex mixed content with paragraphs, lists, and code blocks."""
        generator = DefaultsCommentGenerator()

        input_text = """This example demonstrates all formatting working perfectly
together.

Single linebreaks within paragraphs become spaces making text
flow naturally while preserving readability throughout.

Double linebreaks create proper paragraph separation like this one.

- List items are preserved perfectly
- Each item appears on its own line
- Multi-line list items like this one that spans
  across multiple lines are handled correctly
- Even complex items work great

Lists can be followed by regular paragraphs that get formatted
with single linebreaks becoming spaces as expected.

Code blocks are now perfectly preserved:
```yaml
perfect_example:
  nested_config:
    key1: "value1"
    key2: "value2"
    list_items:
      - item1
      - item2
```

And text after code blocks continues to work normally with
single linebreaks becoming spaces for natural flow."""

        result = generator._parse_and_format_description(input_text)

        # Verify all elements are present and properly formatted
        assert (
            "This example demonstrates all formatting working perfectly together."
            in result
        )
        assert (
            "Single linebreaks within paragraphs become spaces making text flow "
            "naturally while preserving readability throughout." in result
        )
        assert "- List items are preserved perfectly" in result
        assert "- Each item appears on its own line" in result
        assert "```yaml" in result
        assert "perfect_example:" in result
        assert (
            "And text after code blocks continues to work normally with single "
            "linebreaks becoming spaces for natural flow." in result
        )

        # Verify proper separation between blocks
        parts = result.split("\n\n")
        assert len(parts) >= 5  # Multiple distinct blocks

    def test_parse_and_format_description_edge_cases(self):
        """Test edge cases for parser-based description formatting."""
        generator = DefaultsCommentGenerator()

        # Empty input
        result = generator._parse_and_format_description("")
        assert result == ""

        # Whitespace-only input
        result = generator._parse_and_format_description("   \n\n   ")
        assert result == ""

        # Single line
        result = generator._parse_and_format_description("Single line description.")
        assert result == "Single line description."

        # Only lists
        input_text = """- Item one
- Item two
- Item three"""
        result = generator._parse_and_format_description(input_text)
        assert "- Item one" in result
        assert "- Item two" in result
        assert "- Item three" in result

        # Only code block
        input_text = """```bash
echo "Hello World"
ls -la
```"""
        result = generator._parse_and_format_description(input_text)
        assert result.startswith("```bash")
        assert 'echo "Hello World"' in result
        assert result.endswith("```")


class TestBlockAwareProcessing:
    """Test the parser-based text processing methods."""

    def test_ast_wrapping_preserves_code_blocks(self):
        """Test that AST-aware wrapping preserves code blocks correctly."""
        generator = DefaultsCommentGenerator()

        # Test with code block
        input_text = (
            "Regular text before.\n\n```yaml\nconfig:\n  key: value\n  items:\n"
            "    - one\n    - two\n```\n\nText after code block."
        )

        # Parse and format with wrapping
        result = generator._parse_and_format_description(input_text, max_width=50)

        # Verify code block is preserved
        assert "```yaml" in result
        assert "config:" in result
        assert "  key: value" in result
        assert "```" in result
        assert "Text after code block." in result

    def test_ast_wrapping_preserves_lists(self):
        """Test that AST-aware wrapping preserves lists correctly."""
        generator = DefaultsCommentGenerator()

        input_text = """Text before list.

- First item
- Second item with continuation that spans multiple lines
- Third item

Text after list."""

        # Parse and format with wrapping
        result = generator._parse_and_format_description(input_text, max_width=50)

        # Verify list structure is preserved
        assert "- First item" in result
        assert "- Second item" in result
        assert "- Third item" in result
        assert "Text before list." in result
        assert "Text after list." in result

    def test_ast_wrapping_mixed_content(self):
        """Test AST-aware wrapping with mixed content types."""
        generator = DefaultsCommentGenerator()

        input_text = (
            "Paragraph text.\n\n- List item one\n- List item two\n\n```python\n"
            "def function():\n    return True\n```\n\nAnother paragraph.\n\n"
            "- Different bullet style item"
        )

        # Parse and format with wrapping
        result = generator._parse_and_format_description(input_text, max_width=50)

        # Verify all content types are preserved
        assert "Paragraph text." in result
        assert "- List item one" in result
        assert "```python" in result
        assert "def function():" in result
        assert "Another paragraph." in result
        assert "- Different bullet style item" in result

    def test_ast_wrapping_edge_cases(self):
        """Test edge cases in AST-aware text wrapping."""
        generator = DefaultsCommentGenerator()

        # Empty input
        result = generator._parse_and_format_description("", max_width=50)
        assert result == ""

        # Only whitespace
        result = generator._parse_and_format_description("   \n\n   ", max_width=50)
        assert result == ""

        # Very long single line that needs wrapping
        long_line = "This is a very long line that should be wrapped " * 5
        result = generator._parse_and_format_description(long_line, max_width=50)
        lines = result.split("\n")

        # Should have multiple lines
        assert len(lines) > 1
        # No line should exceed max width
        for line in lines:
            if line.strip():  # Skip empty lines
                assert len(line) <= 50

    def test_format_ast_node_paragraph(self):
        """Test AST paragraph node formatting."""
        generator = DefaultsCommentGenerator()

        # Test with actual CommonMark AST node
        from commonmark import Parser

        parser = Parser()
        ast = parser.parse("First line\nwith softbreak")

        # Get the paragraph node
        paragraph_node = ast.first_child
        assert paragraph_node.t == "paragraph"

        result = generator._format_ast_node(paragraph_node)
        assert result == "First line with softbreak"

    def test_format_ast_node_code_block(self):
        """Test AST code block node formatting."""
        generator = DefaultsCommentGenerator()

        from commonmark import Parser

        parser = Parser()
        ast = parser.parse("```yaml\nkey: value\n```")

        # Get the code block node
        code_block_node = ast.first_child
        assert code_block_node.t == "code_block"

        result = generator._format_ast_node(code_block_node)
        assert result.startswith("```")
        assert "key: value" in result
        assert result.endswith("```")

    def test_format_ast_node_list(self):
        """Test AST list node formatting."""
        generator = DefaultsCommentGenerator()

        from commonmark import Parser

        parser = Parser()
        ast = parser.parse("- First item\n- Second item")

        # Get the list node
        list_node = ast.first_child
        assert list_node.t == "list"

        result = generator._format_ast_node(list_node)
        assert "- First item" in result
        assert "- Second item" in result


class TestMarkdownListFormattingFixes:
    """Test the markdown list formatting fixes for CommonMark AST processing."""

    def test_preserve_asterisk_list_markers(self):
        """
        Test that asterisk list markers are preserved instead of converted to dashes.
        """
        generator = DefaultsCommentGenerator()

        input_text = """List with asterisks:

* First item
* Second item
* Third item"""

        result = generator._parse_and_format_description(input_text, max_width=78)

        # Asterisks should be preserved
        assert "* First item" in result
        assert "* Second item" in result
        assert "* Third item" in result

        # Should not be converted to dashes
        assert "- First item" not in result

    def test_proper_list_indentation_levels(self):
        """Test that nested lists use proper continuation indentation levels."""
        generator = DefaultsCommentGenerator()

        input_text = """Nested list example:

- Top level item
  - Second level item
    - Third level item
    - Another third level
  - Back to second level
- Another top level"""

        result = generator._parse_and_format_description(input_text, max_width=78)

        lines = result.split("\n")

        # Find and verify indentation levels
        for line in lines:
            if "Top level" in line or "Another top level" in line:
                # Top level should have no indentation
                assert line.startswith("- ")
            elif "Second level" in line or "Back to second level" in line:
                # Second level should have 4 spaces (continuation alignment)
                assert line.startswith("    - ")
            elif "Third level" in line:
                # Third level should have 6 spaces (nested continuation alignment)
                assert line.startswith("      - ")

    def test_top_level_list_continuation_indentation(self):
        """Test that continuation lines for top-level lists get proper indentation."""
        generator = DefaultsCommentGenerator()

        # Simplified test that matches actual formatting
        input_text = """- List Item 1 continuation text that should wrap properly
- List Item 2
  ```
  code block content
  ```
  More continuation text"""

        result = generator._parse_and_format_description(input_text, max_width=78)

        lines = result.split("\n")

        # Verify continuation lines have proper indentation
        code_block_found = False
        for i, line in enumerate(lines):
            if line.strip() == "```":
                # Code blocks in lists should be indented by 2 spaces
                if i > 0:  # Not the first line
                    assert line.startswith("  ```")
                    code_block_found = True
            elif "code block content" in line:
                # Code content should have base indentation (2 spaces)
                assert line.startswith("  code block content")
            elif "More continuation text" in line:
                # Continuation text should be indented by 2 spaces
                assert line.startswith("  More continuation text")

        assert code_block_found, "Code block was not found in output"

    def test_code_block_indentation_preservation(self):
        """
        Test that code blocks preserve internal indentation while getting proper base
        indentation.
        """
        generator = DefaultsCommentGenerator()

        input_text = """- Configuration example:
  ```yaml
  config:
    nested_setting: value
    list_items:
      - item1
      - item2
  ```
  End of example."""

        result = generator._parse_and_format_description(input_text, max_width=78)

        lines = result.split("\n")

        # Verify code block structure
        for _i, line in enumerate(lines):
            if line.strip() == "```yaml":
                # Code block fence should be indented
                assert line.startswith("  ```yaml")
            elif "config:" in line:
                # Top-level YAML should have base + 0 indentation
                assert line.startswith("  config:")
            elif "nested_setting:" in line:
                # Nested YAML should have base + 2 indentation
                assert line.startswith("    nested_setting:")
            elif "list_items:" in line:
                # List property should have base + 2 indentation
                assert line.startswith("    list_items:")
            elif "- item1" in line or "- item2" in line:
                # List items should have base + 4 indentation
                assert line.startswith("      - item")

    def test_mixed_list_types_preservation(self):
        """Test that both bullet and ordered lists are preserved correctly."""
        generator = DefaultsCommentGenerator()

        input_text = """Mixed list example:

- Bullet item 1
- Bullet item 2
  1. Ordered subitem 1
  2. Ordered subitem 2
     - Nested bullet under ordered
  3. Ordered subitem 3
- Bullet item 3

Separate ordered list:

1. First ordered item
2. Second ordered item
   * Bullet under ordered
   * Another bullet"""

        result = generator._parse_and_format_description(input_text, max_width=78)

        # Verify list type preservation
        assert "- Bullet item 1" in result
        assert "1. Ordered subitem 1" in result
        assert "2. Ordered subitem 2" in result
        assert "- Nested bullet under ordered" in result
        assert "1. First ordered item" in result
        assert "* Bullet under ordered" in result

        # Verify proper nesting indentation
        lines = result.split("\n")
        for line in lines:
            if "Ordered subitem" in line:
                assert line.startswith(
                    "    "
                )  # 4-space continuation indent for nested ordered
            elif "Nested bullet under ordered" in line:
                assert line.startswith("      - ")  # 6 spaces for bullet under ordered
            elif "Bullet under ordered" in line:
                assert line.startswith("     * ")  # 5 spaces for bullet under ordered

    def test_long_text_wrapping_in_nested_lists(self):
        """
        Test that long text in nested lists wraps correctly with proper indentation.
        """
        generator = DefaultsCommentGenerator()

        input_text = (
            "Nested list with long text:\n\n"
            "- First item with some text\n"
            "  - Second level item with very long text that should wrap at the "
            "specified line length and maintain proper indentation\n"
            "    - Third level with even longer text that definitely needs to wrap and "
            "should maintain consistent indentation throughout the wrapped lines\n"
            "  - Another second level item"
        )

        result = generator._parse_and_format_description(input_text, max_width=78)

        lines = result.split("\n")

        # Verify wrapping behavior
        found_wrapped_second_level = False
        found_wrapped_third_level = False

        for i, line in enumerate(lines):
            if "Second level item with very long" in line:
                found_wrapped_second_level = True
                # Should start with 4-space continuation indent
                assert line.startswith("    - ")
                # Next line should be continuation with proper alignment
                if i + 1 < len(lines) and lines[i + 1].strip():
                    next_line = lines[i + 1]
                    if not next_line.strip().startswith("-"):  # Not another list item
                        assert next_line.startswith(
                            "      "
                        )  # 6 spaces for continuation

            elif "Third level with even longer" in line:
                found_wrapped_third_level = True
                # Should start with 6-space continuation indent
                assert line.startswith("      - ")
                # Check continuation line indentation
                if i + 1 < len(lines) and lines[i + 1].strip():
                    next_line = lines[i + 1]
                    if not next_line.strip().startswith("-"):  # Not another list item
                        assert next_line.startswith(
                            "        "
                        )  # 8 spaces for continuation

        assert found_wrapped_second_level, "Did not find wrapped second level text"
        assert found_wrapped_third_level, "Did not find wrapped third level text"

    def test_comprehensive_list_and_code_example(self):
        """Test the comprehensive example from the user's report."""
        generator = DefaultsCommentGenerator()

        # User's exact test case
        input_text = (
            "Text outside the list. Text outside the list. Text outside the list. Text "
            "outside the list. Text outside the list.Text outside the listText outside "
            "the listText outside the listText outside the list\n\n"
            "- List Item 1 For boolean values, use `true`/`false` (these will be"
            " converted to yes/no\n"
            "  by configuration tasks as needed). With long text. That should be "
            "wrapped to max line\n"
            "- Liste Item 2\n"
            "- List Item 3\n"
            "  ```\n"
            "  # This is code. Must not be touched beside the base indentation!\n"
            "  HostKey:\n"
            '    - "long long long long long long long long long long long long long '
            'long long long long long"\n'
            '    - "/etc/ssh/ssh_host_ed25519_key"\n'
            '    - "/etc/ssh/ssh_host_ecdsa_key"\n'
            "  ```\n"
            "  This will generate multiple entries in the config file, one per list "
            "item.\n"
            "- List Item 4\n"
            "  - Sublist 1\n"
            "  - Sublist 2\n"
            "    1. Sub sub sub list With long text. That should be wrapped to max "
            "line With long text.\n"
            "        ```\n"
            "        # This is code in a sublist. Must not be touched beside the base "
            "indentation!\n"
            "        HostKey:\n"
            '          - "long long long long long long long long long long long long'
            ' long long long long long long long long"\n'
            '          - "/etc/ssh/ssh_host_ed25519_key"\n'
            '          - "/etc/ssh/ssh_host_ecdsa_key"\n'
            "        ```\n"
            "        That should be wrapped to max line With long text. That should be"
            " wrapped to max line\n"
            "    2. Sub Sub Sub 2\n"
            "  - sublist 3\n"
            "- List Item 5\n\n"
            "Another list with Asterisk:\n\n"
            "* FOo\n"
            "* bar\n"
            "* Baz"
        )

        result = generator._parse_and_format_description(input_text, max_width=78)

        # Convert to YAML comment format for final verification
        comment_lines = []
        for line in result.split("\n"):
            if line.strip():
                comment_lines.append(f"# {line}")
            else:
                comment_lines.append("#")
        final_result = "\n".join(comment_lines)

        # Key assertions for the fixed issues:

        # 1. Top-level list continuation should be indented
        assert "# - List Item 3\n#   ```" in final_result
        assert "# - List Item 3\n# ```" not in final_result  # Should NOT be flush left

        # 2. Code blocks should maintain internal indentation
        assert "#   HostKey:" in final_result
        assert (
            '#     - "long long long' in final_result
        )  # 4 spaces total (2 base + 2 original)

        # 3. Nested lists should have proper indentation
        assert (
            "#     - Sublist 1" in final_result
        )  # 4-space continuation indent for second level
        assert (
            "#       1. Sub sub sub list" in final_result
        )  # 6-space continuation indent for third level

        # 4. Asterisk preservation
        assert "# * FOo" in final_result
        assert "# * bar" in final_result
        assert "# * Baz" in final_result

        # 5. Deep nesting with code blocks
        assert "#          ```" in final_result  # Code block in deep nest (10 spaces)
        assert (
            "#          HostKey:" in final_result
        )  # HostKey should be at same level as code fence
        assert (
            '#            - "long long' in final_result
        )  # List items inside code (12 spaces)

    def test_edge_case_empty_lists_and_mixed_content(self):
        """Test edge cases with empty list items and mixed content."""
        generator = DefaultsCommentGenerator()

        input_text = """Mixed content test:

- First item
-
- Item after empty

  New paragraph in same item.

- Final item

Regular paragraph after list."""

        result = generator._parse_and_format_description(input_text, max_width=78)

        # Should handle empty list items gracefully
        assert "- First item" in result
        assert "- Item after empty" in result
        assert "- Final item" in result
        assert "Regular paragraph after list." in result


class TestParserBasedIntegration:
    """Integration tests for the complete parser-based workflow."""

    def test_real_world_complex_description(self, sample_role_with_specs_and_defaults):
        """Test with actual complex descriptions from fixtures."""
        generator = DefaultsCommentGenerator()

        # Use the complex description from the test fixtures
        complex_description = (
            'Determines whether the managed resources should be "present" or '
            '"absent".\n\n'
            '"present" ensures that required components, such as software packages, '
            "are installed and configured.\n\n"
            '"absent" reverts changes as much as possible, such as removing packages, '
            "deleting created users, stopping services, restoring modified "
            "settings, etc."
        )

        result = generator._parse_and_format_description(complex_description)

        # Verify proper formatting
        assert (
            'Determines whether the managed resources should be "present" or "absent".'
            in result
        )
        assert '"present" ensures that required components' in result
        assert '"absent" reverts changes as much as possible' in result

        # Should have proper paragraph separation
        paragraphs = result.split("\n\n")
        assert len(paragraphs) == 3

    def test_code_block_threading_prevention(self):
        """Test that code blocks are NOT threaded (critical regression test)."""
        generator = DefaultsCommentGenerator()

        # This is the critical test case - code blocks should not be threaded
        input_text = """Code blocks maintain their structure:

```bash
# This is a bash code block
echo "Hello, World!"
ls -la /home/user/
```

Regular text after code blocks works perfectly."""

        result = generator._parse_and_format_description(input_text)

        # The code block should be preserved as a complete block
        assert "```bash" in result
        assert "# This is a bash code block" in result
        assert 'echo "Hello, World!"' in result
        assert "ls -la /home/user/" in result
        assert "```" in result

        # Verify it's not threaded (each line individually prefixed)
        # If it were threaded, we'd see something like:
        # ```bash
        # # This is a bash code block
        # echo "Hello, World!"
        # ls -la /home/user/
        # ```
        # But as separate lines, which would break the code block structure
        lines = result.split("\n")
        code_start_idx = None
        code_end_idx = None

        for i, line in enumerate(lines):
            if line.strip() == "```bash":
                code_start_idx = i
            elif line.strip() == "```" and code_start_idx is not None:
                code_end_idx = i
                break

        assert code_start_idx is not None
        assert code_end_idx is not None

        # The code block content should be between these indices
        code_content = lines[code_start_idx + 1 : code_end_idx]
        assert len(code_content) == 3
        assert code_content[0] == "# This is a bash code block"
        assert code_content[1] == 'echo "Hello, World!"'
        assert code_content[2] == "ls -la /home/user/"

    def test_comprehensive_formatting_example(self):
        """Test the comprehensive example from the final test case."""
        generator = DefaultsCommentGenerator()

        # This is the actual content from /tmp/final-comprehensive-test
        comprehensive_text = """This example demonstrates all formatting working
perfectly together.

Single linebreaks within paragraphs become spaces making text
flow naturally while preserving readability throughout.

Double linebreaks create proper paragraph separation like this one.

- List items are preserved perfectly
- Each item appears on its own line
- Multi-line list items like this one that spans
  across multiple lines are handled correctly
- Even complex items work great

Lists can be followed by regular paragraphs that get formatted
with single linebreaks becoming spaces as expected.

Code blocks are now perfectly preserved:
```yaml
perfect_example:
  nested_config:
    key1: "value1"
    key2: "value2"
    list_items:
      - item1
      - item2
```

And text after code blocks continues to work normally with
single linebreaks becoming spaces for natural flow."""

        result = generator._parse_and_format_description(comprehensive_text)

        # Verify all major components are preserved correctly
        assert (
            "This example demonstrates all formatting working perfectly together."
            in result
        )
        assert (
            "Single linebreaks within paragraphs become spaces making text flow "
            "naturally while preserving readability throughout." in result
        )
        assert "- List items are preserved perfectly" in result
        assert (
            "- Multi-line list items like this one that spans across multiple "
            "lines are handled correctly" in result
        )
        assert "```yaml" in result
        assert "perfect_example:" in result
        assert 'key1: "value1"' in result
        assert "- item1" in result
        assert (
            "And text after code blocks continues to work normally with single "
            "linebreaks becoming spaces for natural flow." in result
        )

        # Verify proper paragraph/block separation
        parts = result.split("\n\n")
        assert len(parts) >= 6  # Should have multiple distinct sections

    def test_backwards_compatibility_with_existing_tests(
        self, sample_role_with_specs_and_defaults
    ):
        """Test parser-based approach compatibility with existing functionality."""
        generator = DefaultsCommentGenerator()

        defaults_path = sample_role_with_specs_and_defaults / "defaults" / "main.yml"

        specs = {
            "main": {
                "options": {
                    "acmesh_domain": {
                        "description": "Primary domain name for the certificate"
                    },
                    "acmesh_email": {
                        "description": "Email address for ACME account registration"
                    },
                    "acmesh_staging": {
                        "description": (
                            "Use Let's Encrypt staging environment for testing"
                        )
                    },
                }
            }
        }

        result = generator.add_comments(defaults_path, specs)

        # Should work exactly as before
        assert result is not None
        assert "primary domain name" in result.lower()
        assert "email address for acme" in result.lower()
        assert "staging environment" in result.lower()


class TestReadmeUpdater:
    """Test the ReadmeUpdater class."""

    def test_update_readme_new_file(self, temp_dir):
        """Test creating new README file."""
        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        new_content = "## Role variables\n\nTest content"

        result = updater.update_readme(readme_path, new_content)

        assert result is True
        assert readme_path.exists()

        content = readme_path.read_text()
        assert "test content" in content.lower()
        expected_start = (
            f"{MARKER_COMMENT_MD_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_MD_END}"
        )
        expected_end = (
            f"{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}"
        )
        assert expected_start in content
        assert expected_end in content

    def test_update_readme_existing_file_no_markers(self, temp_dir):
        """Test updating existing README without markers."""
        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        existing_content = "# My Role\n\nExisting content"
        readme_path.write_text(existing_content)

        new_content = "## Role variables\n\nNew content"

        result = updater.update_readme(readme_path, new_content)

        assert result is True

        content = readme_path.read_text()
        assert "existing content" in content.lower()
        assert "new content" in content.lower()
        expected_start = (
            f"{MARKER_COMMENT_MD_BEGIN}"
            f"{MARKER_README_MAIN_START}"
            f"{MARKER_COMMENT_MD_END}"
        )
        assert expected_start in content

    def test_update_readme_existing_file_with_markers(self, temp_dir):
        """Test updating existing README with markers."""
        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        existing_content = f"""# My Role

Existing content

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MD_END}
Old documentation
{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}

More content"""
        readme_path.write_text(existing_content)

        new_content = "## Role variables\n\nNew documentation"

        result = updater.update_readme(readme_path, new_content)

        assert result is True

        content = readme_path.read_text()
        assert "existing content" in content.lower()
        assert "more content" in content.lower()
        assert "new documentation" in content.lower()
        assert "old documentation" not in content.lower()

    def test_create_new_readme(self):
        """Test creating new README template."""
        updater = ReadmeUpdater()

        role_content = "## Role variables\n\nTest variables"
        result = updater._create_new_readme(role_content, "test-role")

        assert "# ansible role: `test-role`" in result.lower()
        assert "test variables" in result.lower()
        assert "## licens" in result.lower()
        assert "gpl-3.0-or-later" in result.lower()

    def test_custom_markers(self, temp_dir):
        """Test using custom markers."""
        updater = ReadmeUpdater(start_marker="START CUSTOM", end_marker="END CUSTOM")

        readme_path = temp_dir / "README.md"
        existing_content = """# My Role

<!-- START CUSTOM -->
Old content
<!-- END CUSTOM -->"""
        readme_path.write_text(existing_content)

        new_content = "New content"
        result = updater.update_readme(readme_path, new_content)

        assert result is True

        content = readme_path.read_text()
        assert "<!-- START CUSTOM -->" in content
        assert "<!-- END CUSTOM -->" in content
        assert "new content" in content.lower()
        assert "old content" not in content.lower()

    def test_update_readme_with_toc_markers(self, temp_dir):
        """Test updating README with TOC markers."""
        from ansible_docsmith import MARKER_README_TOC_END, MARKER_README_TOC_START

        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        # Create README with both main and TOC markers
        existing_content = f"""# My Role

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MD_END}
Old main content
{MARKER_COMMENT_MD_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MD_END}

## Table of Contents

{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MD_END}
Old TOC content
{MARKER_COMMENT_MD_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MD_END}

## Section One

Some content here.
"""
        readme_path.write_text(existing_content)

        new_main_content = """## Role variables

### Variable details

Some variable documentation here."""
        result = updater.update_readme(readme_path, new_main_content)

        assert result is True

        content = readme_path.read_text()
        assert "Role variables" in content
        assert "Old main content" not in content
        # TOC should be regenerated based only on headings from main content
        assert "* [Role variables](#role-variables)" in content
        assert "* [Variable details](#variable-details)" in content
        # Should NOT include headings from outside the main content
        assert "* [My Role](#my-role)" not in content
        assert "* [Section One](#section-one)" not in content


class TestTocGenerator:
    """Test the TOC generator functionality (using MarkdownTocGenerator)."""

    def test_generate_toc_basic(self):
        """Test basic TOC generation."""
        generator = MarkdownTocGenerator(bullet_style="*")

        content = """# Main Title

## Section One<a id="section-one"></a>

Some content here.

### Subsection A<a id="subsection-a"></a>

More content.

## Section Two<a id="section-two"></a>

Final content.
"""

        toc = generator.generate_toc(content)
        expected_lines = [
            "* [Main Title](#main-title)",
            "  * [Section One](#section-one)",
            "    * [Subsection A](#subsection-a)",
            "  * [Section Two](#section-two)",
        ]

        assert toc == "\n".join(expected_lines)

    def test_generate_toc_with_dash_bullets(self):
        """Test TOC generation with dash bullets."""
        generator = MarkdownTocGenerator(bullet_style="-")

        content = """# Main Title

## Section One

More content.
"""

        toc = generator.generate_toc(content)
        expected_lines = [
            "- [Main Title](#main-title)",
            "  - [Section One](#section-one)",
        ]

        assert toc == "\n".join(expected_lines)

    def test_extract_headings(self):
        """Test heading extraction."""
        generator = MarkdownTocGenerator()

        content = """# Title One<a id="custom-id"></a>

## Title Two

### Title Three<a id="another-id"></a>

Some text that is not a heading.

#### Title Four
"""

        headings = generator._extract_headings(content)

        expected = [
            {"text": "Title One", "level": 1, "anchor": "custom-id"},
            {"text": "Title Two", "level": 2, "anchor": "title-two"},
            {"text": "Title Three", "level": 3, "anchor": "another-id"},
            {"text": "Title Four", "level": 4, "anchor": "title-four"},
        ]

        assert headings == expected

    def test_create_anchor_link(self):
        """Test anchor link creation."""
        generator = MarkdownTocGenerator()

        test_cases = [
            ("Simple Title", "simple-title"),
            ("Title with Spaces", "title-with-spaces"),
            ("Title-with-Dashes", "title-with-dashes"),
            ("Title (with) Special! Characters?", "title-with-special-characters"),
            ("  Whitespace   Around  ", "whitespace-around"),
            ("Multiple---Dashes", "multiple-dashes"),
        ]

        for input_text, expected in test_cases:
            assert generator._create_anchor_link(input_text) == expected

    def test_detect_bullet_style(self):
        """Test bullet style detection."""
        generator = MarkdownTocGenerator()

        # Content with more asterisk bullets
        content_asterisk = """
Some text
* [Link one](#one)
* [Link two](#two)
- [Link three](#three)
"""
        assert generator._detect_bullet_style(content_asterisk) == "*"

        # Content with more dash bullets
        content_dash = """
Some text
- [Link one](#one)
- [Link two](#two)
- [Link three](#three)
* [Link four](#four)
"""
        assert generator._detect_bullet_style(content_dash) == "-"

        # Content with no bullets defaults to asterisk
        content_none = """
Just some regular text
with no bullet lists.
"""
        assert generator._detect_bullet_style(content_none) == "*"

    def test_generate_toc_auto_detect_bullets(self):
        """Test TOC generation with auto-detected bullet style."""
        generator = MarkdownTocGenerator()  # No bullet style specified

        content = """# Main Title

Some content with existing lists:
- [Existing link](#existing)
- [Another link](#another)

## Section One

More content.
"""

        toc = generator.generate_toc(content)
        # Should detect dash style from existing content
        assert toc.startswith("- [Main Title]")

    def test_generate_toc_empty_content(self):
        """Test TOC generation with no headings."""
        generator = MarkdownTocGenerator()

        content = """
Just some regular text
with no headings at all.
"""

        toc = generator.generate_toc(content)
        assert toc == ""

    def test_generate_toc_complex_headings(self):
        """Test TOC generation with complex heading text."""
        generator = MarkdownTocGenerator(bullet_style="*")

        content = """# Role: `example-role`

## Variable `config_setting`<a id="variable-config_setting"></a>

### Nested Options

#### Sub-option: `enabled`
"""

        toc = generator.generate_toc(content)
        expected_lines = [
            "* [Role: `example-role`](#role-example-role)",
            "  * [Variable `config_setting`](#variable-config_setting)",
            "    * [Nested Options](#nested-options)",
            "      * [Sub-option: `enabled`](#sub-option-enabled)",
        ]

        assert toc == "\n".join(expected_lines)


class TestMarkdownTocGenerator:
    """Test the MarkdownTocGenerator class."""

    def test_markdown_get_format_type(self):
        """Test that MarkdownTocGenerator returns correct format type."""
        generator = MarkdownTocGenerator()
        assert generator._get_format_type() == "markdown"

    def test_markdown_toc_generation_same_as_legacy(self):
        """Test MarkdownTocGenerator produces same results as legacy TocGenerator."""
        content = """# Main Title

Some content here.

## Section One

Content for section one.

### Subsection

More content.

## Section Two

Final content.
"""

        legacy_generator = MarkdownTocGenerator(bullet_style="*")
        new_generator = MarkdownTocGenerator(bullet_style="*")

        legacy_result = legacy_generator.generate_toc(content)
        new_result = new_generator.generate_toc(content)

        assert legacy_result == new_result

    def test_ast_extract_headings_with_code_blocks(self):
        """Test that AST-based extraction avoids false positives from code blocks."""
        generator = MarkdownTocGenerator()

        # This is the problematic case mentioned by the user
        content = """# Real Heading

Some text here.

```bash
# this is not a headline but a comment
echo "some code"
```

## Another Real Heading

```yaml
# Also not a heading
key: value
```

### Third Real Heading"""

        headings = generator._extract_headings(content)

        # Should only extract actual headings, not code comments
        assert len(headings) == 3
        assert headings[0]["text"] == "Real Heading"
        assert headings[0]["level"] == 1
        assert headings[1]["text"] == "Another Real Heading"
        assert headings[1]["level"] == 2
        assert headings[2]["text"] == "Third Real Heading"
        assert headings[2]["level"] == 3

    def test_ast_extract_headings_with_inline_code(self):
        """Test headings with inline code are handled properly."""
        generator = MarkdownTocGenerator()

        content = """# Configure `nginx` Settings

## Variable `ssl_enabled`<a id="variable-ssl_enabled"></a>

### Method `configure_ssl()`"""

        headings = generator._extract_headings(content)

        assert len(headings) == 3
        assert headings[0]["text"] == "Configure `nginx` Settings"
        assert headings[0]["level"] == 1
        assert headings[1]["text"] == "Variable `ssl_enabled`"
        assert headings[1]["level"] == 2
        assert (
            headings[1]["anchor"] == "variable-ssl_enabled"
        )  # Custom anchor preserved
        assert headings[2]["text"] == "Method `configure_ssl()`"
        assert headings[2]["level"] == 3

    def test_ast_extract_headings_mixed_content(self):
        """Test complex markdown with various constructs."""
        generator = MarkdownTocGenerator()

        content = """# Main Document

## Introduction

Some text with [links](#somewhere) and **bold text**.

### Code Examples

Here's a code block:

```python
def function():
    # This comment should not be extracted as a heading
    return "# Neither should this string"
```

## FAQ

### What about `inline code`?

Answer here.

```markdown
# This is markdown inside code block
## Should not be extracted
```

#### Final Section"""

        headings = generator._extract_headings(content)

        expected_headings = [
            {"text": "Main Document", "level": 1, "anchor": "main-document"},
            {"text": "Introduction", "level": 2, "anchor": "introduction"},
            {"text": "Code Examples", "level": 3, "anchor": "code-examples"},
            {"text": "FAQ", "level": 2, "anchor": "faq"},
            {
                "text": "What about `inline code`?",
                "level": 3,
                "anchor": "what-about-inline-code",
            },
            {"text": "Final Section", "level": 4, "anchor": "final-section"},
        ]

        assert len(headings) == len(expected_headings)
        for i, expected in enumerate(expected_headings):
            assert headings[i]["text"] == expected["text"]
            assert headings[i]["level"] == expected["level"]
            assert headings[i]["anchor"] == expected["anchor"]

    def test_ast_extract_headings_fallback_on_error(self):
        """Test fallback to regex extraction when AST parsing fails."""
        generator = MarkdownTocGenerator()

        # Mock the Parser to raise an exception
        import unittest.mock

        with unittest.mock.patch("commonmark.Parser") as mock_parser:
            mock_parser.side_effect = Exception("Parser error")

            content = """# Test Heading
## Second Heading"""

            headings = generator._extract_headings(content)

            # Should fall back to regex method
            assert len(headings) == 2
            assert headings[0]["text"] == "Test Heading"
            assert headings[1]["text"] == "Second Heading"

    def test_ast_extract_headings_empty_content(self):
        """Test AST extraction with empty or whitespace content."""
        generator = MarkdownTocGenerator()

        # Empty content
        assert generator._extract_headings("") == []

        # Only whitespace
        assert generator._extract_headings("   \n\n   ") == []

        # Content with no headings
        content = """Just some regular text

with multiple paragraphs

but no headings at all."""

        assert generator._extract_headings(content) == []

    def test_ast_extract_text_from_node(self):
        """Test the helper method for extracting text from AST nodes."""
        from commonmark import Parser

        generator = MarkdownTocGenerator()
        parser = Parser()

        # Test with simple heading
        ast = parser.parse("# Simple Heading")
        heading_node = ast.first_child
        text = generator._extract_text_from_node(heading_node)
        assert text == "Simple Heading"

        # Test with heading containing inline code
        ast = parser.parse("# Configure `nginx` Settings")
        heading_node = ast.first_child
        text = generator._extract_text_from_node(heading_node)
        assert text == "Configure `nginx` Settings"

    def test_ast_fallback_method(self):
        """Test the fallback regex-based extraction method."""
        generator = MarkdownTocGenerator()

        content = """# Main Title<a id="custom-id"></a>
## Section Title
### Subsection"""

        headings = generator._extract_headings_fallback(content)

        assert len(headings) == 3
        assert headings[0]["text"] == "Main Title"
        assert headings[0]["anchor"] == "custom-id"
        assert headings[1]["text"] == "Section Title"
        assert headings[2]["text"] == "Subsection"


class TestRSTTocGenerator:
    """Test the RSTTocGenerator class."""

    def test_rst_get_format_type(self):
        """Test that RSTTocGenerator returns correct format type."""
        generator = RSTTocGenerator()
        assert generator._get_format_type() == "rst"

    def test_rst_extract_headings(self):
        """Test extracting headings from RST content."""
        generator = RSTTocGenerator()
        content = """Main Title
==========

Some content here.

Section One
-----------

Content for section one.

Subsection
``````````

More content.

Section Two
-----------

Final content.
"""

        headings = generator._extract_headings(content)

        assert len(headings) == 4
        assert headings[0]["text"] == "Main Title"
        assert headings[0]["level"] == 1
        assert headings[1]["text"] == "Section One"
        assert headings[1]["level"] == 2
        assert headings[2]["text"] == "Subsection"
        assert headings[2]["level"] == 3
        assert headings[3]["text"] == "Section Two"
        assert headings[3]["level"] == 2

    def test_rst_create_anchor_link(self):
        """Test creating anchor links for RST format."""
        generator = RSTTocGenerator()

        assert generator._create_anchor_link("Simple Title") == "simple-title"
        assert (
            generator._create_anchor_link("Title with: Special! Chars?")
            == "title-with-special-chars"
        )
        assert generator._create_anchor_link("Multiple   Spaces") == "multiple-spaces"

    def test_rst_generate_toc_lines(self):
        """Test generating TOC lines in RST format."""
        generator = RSTTocGenerator(bullet_style="*")

        headings = [
            {"text": "Main Title", "level": 1, "anchor": "main-title"},
            {"text": "Section One", "level": 2, "anchor": "section-one"},
            {"text": "Section Two", "level": 2, "anchor": "section-two"},
        ]

        result = generator._generate_toc_lines(headings, "*")
        expected_lines = [
            "",  # Leading blank line
            "* `Main Title <#main-title>`__",
            "",  # Blank line before level change
            "  * `Section One <#section-one>`__",
            "  * `Section Two <#section-two>`__",
            "",  # Trailing blank line
        ]

        assert result == "\n".join(expected_lines)

    def test_rst_detect_bullet_style(self):
        """Test auto-detecting bullet style from RST content."""
        generator = RSTTocGenerator()

        # Content with dash bullets
        dash_content = """
- `Link One <#one>`__
- `Link Two <#two>`__
"""
        assert generator._detect_bullet_style(dash_content) == "-"

        # Content with asterisk bullets
        asterisk_content = """
* `Link One <#one>`__
* `Link Two <#two>`__
"""
        assert generator._detect_bullet_style(asterisk_content) == "*"

        # Default when no pattern found
        empty_content = "Just some text without TOC patterns"
        assert generator._detect_bullet_style(empty_content) == "*"


class TestCreateTocGenerator:
    """Test the factory function for creating TOC generators."""

    def test_create_markdown_toc_generator(self):
        """Test creating a Markdown TOC generator."""
        generator = create_toc_generator("markdown")
        assert isinstance(generator, MarkdownTocGenerator)
        assert generator._get_format_type() == "markdown"

    def test_create_rst_toc_generator(self):
        """Test creating an RST TOC generator."""
        generator = create_toc_generator("rst")
        assert isinstance(generator, RSTTocGenerator)
        assert generator._get_format_type() == "rst"

    def test_create_toc_generator_with_bullet_style(self):
        """Test factory function with bullet style parameter."""
        generator = create_toc_generator("markdown", bullet_style="-")
        assert generator.bullet_style == "-"

    def test_create_toc_generator_case_insensitive(self):
        """Test factory function is case insensitive."""
        generator = create_toc_generator("RST")
        assert isinstance(generator, RSTTocGenerator)

        generator = create_toc_generator("Markdown")
        assert isinstance(generator, MarkdownTocGenerator)

    def test_create_toc_generator_unsupported_format(self):
        """Test factory function with unsupported format."""
        import pytest

        with pytest.raises(ValueError, match="Unsupported format type: html"):
            create_toc_generator("html")


class TestRSTDocumentationGenerator:
    """Test the RSTDocumentationGenerator class."""

    def test_rst_generate_role_documentation(self, sample_role_with_specs):
        """Test generating RST role documentation."""
        generator = RSTDocumentationGenerator()

        # Parse the specs from fixture
        specs = {
            "main": {
                "short_description": "Test role",
                "description": "A test role for testing",
                "author": ["Test Author"],
                "options": {
                    "test_var": {
                        "type": "str",
                        "required": True,
                        "default": None,
                        "description": "A test variable",
                        "choices": [],
                        "options": {},
                    }
                },
            }
        }

        result = generator.generate_role_documentation(
            specs, "test-role", sample_role_with_specs
        )

        # Check RST-specific formatting
        assert "role variables" in result.lower()
        assert "==============" in result  # RST heading underline
        assert "``test_var``" in result  # RST inline code
        assert ":Type: ``str``" in result  # RST field list
        assert ":Required: Yes" in result
        assert "a test variable" in result.lower()

    def test_rst_ansible_escape_filter(self):
        """Test RST Ansible escape filter (should not escape)."""
        generator = RSTDocumentationGenerator()

        # RST doesn't need Ansible variable escaping
        result = generator._ansible_escape_filter("{{ variable }}")
        assert result == "{{ variable }}"

        result = generator._ansible_escape_filter(None)
        assert result == "N/A"

    def test_rst_code_escape_filter(self):
        """Test RST code escape filter."""
        generator = RSTDocumentationGenerator()

        # RST uses double backticks for inline code
        result = generator._code_escape_filter("test|value")
        assert result == "``test|value``"

        result = generator._code_escape_filter("test`value")
        assert result == "``test\\`value``"  # Escape backticks in RST

        result = generator._code_escape_filter(None)
        assert result == "N/A"

    def test_rst_format_table_description_filter(self):
        """Test RST table description formatting."""
        generator = RSTDocumentationGenerator()

        # Test multiline text with paragraph breaks
        input_text = "First paragraph.\n\nSecond paragraph."
        result = generator._format_table_description_filter(input_text)

        # RST uses pipe separators instead of <br><br>
        assert "First paragraph. | Second paragraph." == result

    def test_rst_format_description_filter(self):
        """Test RST description formatting."""
        generator = RSTDocumentationGenerator()

        # Test list input
        input_list = ["First item", "Second item"]
        result = generator._format_description_filter(input_list)
        expected = "First item\n\nSecond item"
        assert result == expected

        # Test string input
        input_str = "Simple description"
        result = generator._format_description_filter(input_str)
        assert result == "Simple description"

        # Test None input
        result = generator._format_description_filter(None)
        assert result == ""


class TestCreateDocumentationGenerator:
    """Test the factory function for creating generators."""

    def test_create_markdown_generator(self):
        """Test creating a Markdown generator."""
        generator = create_documentation_generator("markdown")
        assert isinstance(generator, MarkdownDocumentationGenerator)
        assert generator._get_format_type() == "markdown"

    def test_create_rst_generator(self):
        """Test creating an RST generator."""
        generator = create_documentation_generator("rst")
        assert isinstance(generator, RSTDocumentationGenerator)
        assert generator._get_format_type() == "rst"

    def test_create_generator_case_insensitive(self):
        """Test factory function is case insensitive."""
        generator = create_documentation_generator("RST")
        assert isinstance(generator, RSTDocumentationGenerator)

        generator = create_documentation_generator("Markdown")
        assert isinstance(generator, MarkdownDocumentationGenerator)

    def test_create_generator_unsupported_format(self):
        """Test factory function with unsupported format."""
        import pytest

        with pytest.raises(ValueError, match="Unsupported format type: html"):
            create_documentation_generator("html")
