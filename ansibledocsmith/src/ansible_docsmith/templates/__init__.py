"""Template management for ansible-docsmith."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateManager:
    """Manage templates for documentation generation."""

    def __init__(self, template_dir: Path | None = None):
        """Initialize template manager.

        Args:
            template_dir: Custom template directory. If None, uses built-in templates.
        """
        self.template_dir = template_dir or self._get_builtin_template_dir()
        self.env = self._setup_jinja_env()

    def _get_builtin_template_dir(self) -> Path:
        """Get the built-in template directory."""
        return Path(__file__).parent

    def _setup_jinja_env(self) -> Environment:
        """Setup Jinja2 environment with proper loader."""
        return Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def add_filter(self, name: str, filter_func) -> None:
        """Add custom filter to the Jinja environment."""
        self.env.filters[name] = filter_func

    def get_template(self, template_name: str, template_type: str = "readme") -> str:
        """Get template content by name and type.

        Args:
            template_name: Name of the template (e.g., 'default')
            template_type: Type of template (e.g., 'readme')

        Returns:
            Template content as string
        """
        template_path = f"{template_type}/{template_name}.md.j2"
        # Read template file directly to get source content
        template_file = self.template_dir / template_path
        return template_file.read_text(encoding="utf-8")

    def render_template(
        self, template_name: str, template_type: str = "readme", **context
    ) -> str:
        """Render template with given context.

        Args:
            template_name: Name of the template (e.g., 'default')
            template_type: Type of template (e.g., 'readme')
            **context: Template context variables

        Returns:
            Rendered template content
        """
        template_path = f"{template_type}/{template_name}.md.j2"
        template = self.env.get_template(template_path)
        return template.render(**context)

    def list_templates(self, template_type: str = "readme") -> list[str]:
        """List available templates of given type.

        Args:
            template_type: Type of template to list

        Returns:
            List of available template names (without extension)
        """
        template_dir = self.template_dir / template_type
        if not template_dir.exists():
            return []

        templates = []
        for template_file in template_dir.glob("*.j2"):
            # Remove .md.j2 extension to get template name
            name = template_file.stem
            if name.endswith(".md"):
                name = name[:-3]  # Remove .md part
            templates.append(name)

        return sorted(templates)


__all__ = ["TemplateManager"]
