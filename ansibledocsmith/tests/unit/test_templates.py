"""Tests for template management."""

import pytest

from ansible_docsmith.templates import TemplateManager


class TestTemplateManager:
    """Test the TemplateManager class."""

    def test_initialization(self):
        """Test template manager initialization."""
        tm = TemplateManager()
        assert tm.template_dir is not None
        assert tm.env is not None

    def test_list_templates(self):
        """Test listing available templates."""
        tm = TemplateManager()
        templates = tm.list_templates("readme")

        assert isinstance(templates, list)
        assert "default" in templates

    def test_get_template(self):
        """Test getting template content."""
        tm = TemplateManager()

        # Add dummy filters for testing template loading
        tm.add_filter("ansible_escape", lambda x: x)
        tm.add_filter("format_default", lambda x: x)
        tm.add_filter("format_table_description", lambda x, y=None: x)
        tm.add_filter("format_description", lambda x: x)
        tm.add_filter("code_escape", lambda x: x)

        content = tm.get_template("default", "readme")
        assert isinstance(content, str)
        assert "## Role variables" in content
        assert "{% for var_name, var_spec in options.items() %}" in content

    def test_render_template(self):
        """Test rendering template with context."""
        tm = TemplateManager()

        # Add dummy filters for testing
        tm.add_filter("ansible_escape", lambda x: x)
        tm.add_filter("format_default", lambda x: str(x) if x is not None else "N/A")
        tm.add_filter("format_table_description", lambda x, y=None: x)
        tm.add_filter("format_description", lambda x: x)
        tm.add_filter("code_escape", lambda x: f"`{x}`")

        context = {
            "role_name": "test-role",
            "primary_spec": {"author": ["Test Author"]},
            "main_spec": {"author": ["Test Author"]},  # Backward compatibility
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
            "has_options": True,
        }

        result = tm.render_template("default", "readme", **context)

        assert isinstance(result, str)
        assert "## role variables" in result.lower()
        assert "test_var" in result.lower()
        assert "a test variable" in result.lower()

    def test_render_template_no_options(self):
        """Test rendering template with no options."""
        tm = TemplateManager()

        # Add dummy filters for testing
        tm.add_filter("ansible_escape", lambda x: x)
        tm.add_filter("format_default", lambda x: str(x) if x is not None else "N/A")
        tm.add_filter("format_table_description", lambda x, y=None: x)
        tm.add_filter("format_description", lambda x: x)
        tm.add_filter("code_escape", lambda x: f"`{x}`")

        context = {
            "role_name": "empty-role",
            "primary_spec": {"author": []},
            "main_spec": {"author": []},  # Backward compatibility
            "options": {},
            "has_options": False,
        }

        result = tm.render_template("default", "readme", **context)

        assert "no variables are defined for this role" in result.lower()

    def test_custom_template_dir(self, temp_dir):
        """Test using custom template directory."""
        # Create custom template directory
        custom_templates = temp_dir / "custom"
        custom_templates.mkdir()
        (custom_templates / "readme").mkdir()

        # Create custom template
        custom_template = custom_templates / "readme" / "minimal.md.j2"
        custom_template.write_text("# {{ role_name }}\n\nMinimal template.")

        tm = TemplateManager(custom_templates)
        templates = tm.list_templates("readme")

        assert "minimal" in templates

        result = tm.render_template("minimal", "readme", role_name="test")
        assert "# test" in result.lower()
        assert "minimal template" in result.lower()

    def test_nonexistent_template(self):
        """Test handling of non-existent templates."""
        tm = TemplateManager()

        with pytest.raises(Exception):  # Jinja2 will raise TemplateNotFound
            tm.render_template("nonexistent", "readme", role_name="test")

    def test_empty_template_directory(self, temp_dir):
        """Test handling of empty template directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        tm = TemplateManager(empty_dir)
        templates = tm.list_templates("readme")

        assert templates == []

    def test_single_template_file(self, temp_dir):
        """Test using single template file."""
        # Create a test template file
        template_file = temp_dir / "custom.md.j2"
        template_file.write_text("# {{ role_name }}\n\nCustom template content")

        manager = TemplateManager(template_file=template_file)

        # Should be able to render using the default name
        result = manager.render_template("default", role_name="test-role")
        assert "# test-role" in result
        assert "Custom template content" in result

        # Clean up
        manager.cleanup()

    def test_single_template_file_invalid_syntax(self, temp_dir):
        """Test single template file with invalid Jinja2 syntax."""
        # Create a template file with invalid syntax
        template_file = temp_dir / "invalid.md.j2"
        template_file.write_text("# {{ role_name \n\nMissing closing brace")

        # Should raise ValueError for invalid syntax
        with pytest.raises(ValueError, match="Invalid template syntax"):
            TemplateManager(template_file=template_file)

    def test_single_template_file_cleanup(self, temp_dir):
        """Test that temporary directories are cleaned up."""
        template_file = temp_dir / "test.md.j2"
        template_file.write_text("Test template")

        manager = TemplateManager(template_file=template_file)
        temp_dir_path = manager._temp_dir

        # Temporary directory should exist
        assert temp_dir_path.exists()

        # After cleanup, should be gone
        manager.cleanup()
        assert not temp_dir_path.exists()

    def test_template_file_not_exists(self, temp_dir):
        """Test handling of non-existent template file."""
        non_existent = temp_dir / "missing.md.j2"

        # Should raise ValueError for missing file
        with pytest.raises(ValueError, match="Error reading template file"):
            TemplateManager(template_file=non_existent)
