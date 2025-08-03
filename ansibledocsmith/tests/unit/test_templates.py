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
        tm.add_filter("format_table_description", lambda x: x)
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
        tm.add_filter("format_table_description", lambda x: x)
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
        assert "## Role variables" in result
        assert "test_var" in result
        assert "A test variable" in result

    def test_render_template_no_options(self):
        """Test rendering template with no options."""
        tm = TemplateManager()

        # Add dummy filters for testing
        tm.add_filter("ansible_escape", lambda x: x)
        tm.add_filter("format_default", lambda x: str(x) if x is not None else "N/A")
        tm.add_filter("format_table_description", lambda x: x)
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

        assert "No variables are defined for this role" in result

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
        assert "# test" in result
        assert "Minimal template" in result

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
