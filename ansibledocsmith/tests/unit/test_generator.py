"""Tests for documentation generators."""

from ansible_docsmith import (
    MARKER_COMMENT_MARKDOWN_BEGIN,
    MARKER_COMMENT_MARKDOWN_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
)
from ansible_docsmith.core.generator import (
    DefaultsCommentGenerator,
    DocumentationGenerator,
    ReadmeUpdater,
    TocGenerator,
)


class TestDocumentationGenerator:
    """Test the DocumentationGenerator class."""

    def test_generate_role_documentation(self, sample_role_with_specs):
        """Test generating role documentation."""
        generator = DocumentationGenerator()

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
        generator = DocumentationGenerator()

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
        generator = DocumentationGenerator()

        result = generator._ansible_escape_filter("{{ variable }}")
        assert result == "\\{\\{ variable \\}\\}"

        result = generator._ansible_escape_filter(None)
        assert result == "N/A"

    def test_code_escape_filter(self):
        """Test code escaping for Markdown."""
        generator = DocumentationGenerator()

        result = generator._code_escape_filter("test|value")
        assert result == "`test\\|value`"

        result = generator._code_escape_filter("test`value")
        assert result == "`test\\`value`"

        result = generator._code_escape_filter(None)
        assert result == "N/A"

    def test_format_default_filter(self):
        """Test default value formatting."""
        generator = DocumentationGenerator()

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
        generator = DocumentationGenerator()

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


class TestTableDescriptionFilter:
    """Test the format_table_description filter functionality."""

    def test_html_encoding_basic_tags(self):
        """Test that basic HTML tags are properly encoded."""
        generator = DocumentationGenerator()

        # Test common HTML tags
        input_text = "This has <em>emphasis</em> and <b>bold</b> text."
        result = generator._format_table_description_filter(input_text)
        expected = (
            "This has &lt;em&gt;emphasis&lt;/em&gt; and &lt;b&gt;bold&lt;/b&gt; text."
        )
        assert result == expected

    def test_html_encoding_xss_prevention(self):
        """Test that XSS attack vectors are properly neutralized."""
        generator = DocumentationGenerator()

        # Test script tag XSS
        input_text = 'Dangerous <script>alert("XSS")</script> content'
        result = generator._format_table_description_filter(input_text)
        expected = (
            "Dangerous &lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt; content"
        )
        assert result == expected

        # Test complex XSS with attributes
        input_text = (
            "Complex <b oncontentvisibilityautostatechange=alert(1) "
            "style=display:block>XSS</b> test"
        )
        result = generator._format_table_description_filter(input_text)
        expected = (
            "Complex &lt;b oncontentvisibilityautostatechange=alert(1) "
            "style=display:block&gt;XSS&lt;/b&gt; test"
        )
        assert result == expected

    def test_html_encoding_special_characters(self):
        """Test that special characters are properly encoded."""
        generator = DocumentationGenerator()

        # Test ampersand, quotes, and angle brackets
        input_text = 'Variables like ${VAR} & "quoted strings" < > symbols'
        result = generator._format_table_description_filter(input_text)
        expected = (
            "Variables like ${VAR} &amp; &quot;quoted strings&quot; &lt; &gt; symbols"
        )
        assert result == expected

    def test_multiline_single_breaks_to_spaces(self):
        """Test that single line breaks within paragraphs become spaces."""
        generator = DocumentationGenerator()

        input_text = """First line continues
on the second line and
ends on third line."""
        result = generator._format_table_description_filter(input_text)
        expected = "First line continues on the second line and ends on third line."
        assert result == expected

    def test_multiline_double_breaks_to_br_tags(self):
        """Test that double line breaks (paragraphs) become <br><br> tags."""
        generator = DocumentationGenerator()

        input_text = """First paragraph with some content.

Second paragraph after blank line.

Third paragraph here."""
        result = generator._format_table_description_filter(input_text)
        expected = (
            "First paragraph with some content.<br><br>Second paragraph "
            "after blank line.<br><br>Third paragraph here."
        )
        assert result == expected

    def test_list_descriptions_with_br_tags(self):
        """Test that list descriptions are joined with <br><br>."""
        generator = DocumentationGenerator()

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

    def test_list_with_html_encoding(self):
        """Test that HTML in list items gets properly encoded."""
        generator = DocumentationGenerator()

        input_list = [
            "First item with <em>HTML</em>.",
            "Second item with <script>alert('xss')</script>.",
        ]
        result = generator._format_table_description_filter(input_list)
        expected = (
            "First item with &lt;em&gt;HTML&lt;/em&gt;.<br><br>Second item with "
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;."
        )
        assert result == expected

    def test_combined_html_and_multiline(self):
        """Test HTML encoding combined with multiline processing."""
        generator = DocumentationGenerator()

        input_text = """First paragraph with <b>bold</b> text.

Second paragraph with <script>alert("test")</script> content."""
        result = generator._format_table_description_filter(input_text)
        expected = (
            "First paragraph with &lt;b&gt;bold&lt;/b&gt; text.<br><br>Second "
            "paragraph with &lt;script&gt;alert(&quot;test&quot;)&lt;/script&gt; "
            "content."
        )
        assert result == expected

    def test_edge_cases_none_and_empty(self):
        """Test edge cases with None and empty inputs."""
        generator = DocumentationGenerator()

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
        generator = DocumentationGenerator()

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
        generator = DocumentationGenerator()

        input_text = "Text    with     multiple   spaces    here."
        result = generator._format_table_description_filter(input_text)
        expected = "Text with multiple spaces here."
        assert result == expected

    def test_complex_real_world_example(self):
        """Test with a complex real-world example from the fixture."""
        generator = DocumentationGenerator()

        # Based on the actual fixture content
        input_text = (
            'Determines whether the managed resources should be "present" or '
            '"absent".\n\n'
            '"present" ensures that required components, such as software '
            "packages, are installed and configured.\n\n"
            '"absent" reverts changes as much as possible, such as removing '
            "packages, deleting created users, stopping services, restoring "
            "modified settings, …"
        )

        result = generator._format_table_description_filter(input_text)
        expected = (
            "Determines whether the managed resources should be &quot;present&quot; "
            "or &quot;absent&quot;.<br><br>&quot;present&quot; ensures that required "
            "components, such as software packages, are installed and "
            "configured.<br><br>&quot;absent&quot; reverts changes as much as "
            "possible, such as removing packages, deleting created users, "
            "stopping services, restoring modified settings, …"
        )
        assert result == expected


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

    def test_wrap_text(self):
        """Test text wrapping functionality."""
        generator = DefaultsCommentGenerator()

        # Short text (no wrapping needed)
        result = generator._wrap_text("This is a test description")
        assert result == ["This is a test description"]

        # Long text (should wrap)
        long_text = (
            "This is a very long description that should be wrapped because "
            "it exceeds the maximum width limit that we have set for our comments"
        )
        result = generator._wrap_text(long_text, max_width=50)
        assert len(result) > 1
        assert all(len(line) <= 50 for line in result)

        # Empty text
        result = generator._wrap_text("")
        assert result == [""]


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
        expected_start = f"{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MARKDOWN_END}"
        expected_end = f"{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MARKDOWN_END}"
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
        expected_start = f"{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MARKDOWN_END}"
        assert expected_start in content

    def test_update_readme_existing_file_with_markers(self, temp_dir):
        """Test updating existing README with markers."""
        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        existing_content = f"""# My Role

Existing content

{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MARKDOWN_END}
Old documentation
{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MARKDOWN_END}

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

{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_START}{MARKER_COMMENT_MARKDOWN_END}
Old main content
{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_MAIN_END}{MARKER_COMMENT_MARKDOWN_END}

## Table of Contents

{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_TOC_START}{MARKER_COMMENT_MARKDOWN_END}
Old TOC content
{MARKER_COMMENT_MARKDOWN_BEGIN}{MARKER_README_TOC_END}{MARKER_COMMENT_MARKDOWN_END}

## Section One

Some content here.
"""
        readme_path.write_text(existing_content)

        new_main_content = "New main content"
        result = updater.update_readme(readme_path, new_main_content)

        assert result is True

        content = readme_path.read_text()
        assert "New main content" in content
        assert "Old main content" not in content
        # TOC should be regenerated based on headings
        assert "* [My Role](#my-role)" in content
        assert "* [Section One](#section-one)" in content


class TestTocGenerator:
    """Test the TocGenerator class."""

    def test_generate_toc_basic(self):
        """Test basic TOC generation."""
        generator = TocGenerator(bullet_style="*")

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
        generator = TocGenerator(bullet_style="-")

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
        generator = TocGenerator()

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
        generator = TocGenerator()

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
        generator = TocGenerator()

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
        generator = TocGenerator()  # No bullet style specified

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
        generator = TocGenerator()

        content = """
Just some regular text
with no headings at all.
"""

        toc = generator.generate_toc(content)
        assert toc == ""

    def test_generate_toc_complex_headings(self):
        """Test TOC generation with complex heading text."""
        generator = TocGenerator(bullet_style="*")

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
