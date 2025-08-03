"""Tests for documentation generators."""

from ansible_docsmith.core.generator import (
    DefaultsCommentGenerator,
    DocumentationGenerator,
    ReadmeUpdater,
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
        assert "<!-- BEGIN ANSIBLE DOCSMITH -->" in content
        assert "<!-- END ANSIBLE DOCSMITH -->" in content

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
        assert "<!-- BEGIN ANSIBLE DOCSMITH -->" in content

    def test_update_readme_existing_file_with_markers(self, temp_dir):
        """Test updating existing README with markers."""
        updater = ReadmeUpdater()
        readme_path = temp_dir / "README.md"

        existing_content = """# My Role

Existing content

<!-- BEGIN ANSIBLE DOCSMITH -->
Old documentation
<!-- END ANSIBLE DOCSMITH -->

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

        assert "# test-role" in result.lower()
        assert "test variables" in result.lower()
        assert "## license" in result.lower()
        assert "gpl-3.0-or-later" in result.lower()

    def test_custom_markers(self, temp_dir):
        """Test using custom markers."""
        updater = ReadmeUpdater(
            start_marker="<!-- START CUSTOM -->", end_marker="<!-- END CUSTOM -->"
        )

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
