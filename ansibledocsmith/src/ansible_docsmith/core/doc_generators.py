"""Documentation generators for Markdown and reStructuredText READMEs."""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..constants import TABLE_DESCRIPTION_MAX_LENGTH
from ..templates import TemplateManager
from .exceptions import TemplateError
from .markup import convert_ansible_markup, md_code_span, rst_inline_literal
from .text import (
    MD_ATOMIC_TOKENS,
    RST_ATOMIC_TOKENS,
    HTMLStripper,
    normalize_description,
    truncate_preserving_tokens,
)


class BaseDocumentationGenerator(ABC):
    """Abstract base class for documentation generators."""

    def __init__(
        self,
        template_dir: Path | None = None,
        template_name: str = "default",
        template_file: Path | None = None,
    ):
        """Initialize the documentation generator.

        Args:
            template_dir: Custom template directory. If None, uses built-in templates.
            template_name: Name of the template to use (default: "default")
            template_file: Single template file. If provided, uses this file directly.
        """
        self.template_manager = TemplateManager(template_dir, template_file)
        self.template_name = template_name

        # Top-level option names of the role being rendered; used to turn
        # O(name) markup into intra-README anchor links. Set per render in
        # generate_role_documentation().
        self._role_options: set[str] = set()

        # Add format-specific filters to the Jinja environment
        self._setup_filters()

    def _setup_filters(self):
        """Setup format-specific filters."""
        filters = self._get_filters()
        for name, filter_func in filters.items():
            self.template_manager.add_filter(name, filter_func)

    @abstractmethod
    def _get_filters(self) -> dict[str, Callable[[Any], str]]:
        """Get format-specific filters."""
        pass

    def _get_template_subdir(self) -> str:
        """Get the template subdirectory (same for all formats)."""
        return "readme"

    @abstractmethod
    def _get_format_type(self) -> str:
        """Get the format type for this generator."""
        pass

    def generate_role_documentation(
        self, specs: dict[str, Any], role_name: str, role_path: Path
    ) -> str:
        """Generate complete role documentation."""

        try:
            # For multiple entry points, focus on the first one for primary
            # documentation
            # but make all entry points available to templates
            primary_entry_point = next(iter(specs.keys()))
            primary_spec = specs[primary_entry_point]

            # Known top-level options for O(name) anchor linking in filters
            self._role_options = set(primary_spec.get("options", {}).keys())

            context = {
                "role_name": role_name,
                "role_path": role_path,
                "specs": specs,
                "primary_entry_point": primary_entry_point,
                "primary_spec": primary_spec,
                "entry_points": list(specs.keys()),
                "options": primary_spec.get("options", {}),
                "has_options": bool(primary_spec.get("options", {})),
            }

            # Render template using template manager with format type
            return self.template_manager.render_template(
                self.template_name,
                self._get_template_subdir(),
                self._get_format_type(),
                **context,
            )

        except Exception as e:
            raise TemplateError(f"Failed to generate documentation: {e}")

    @abstractmethod
    def _ansible_escape_filter(self, value: Any) -> str:
        """Escape Ansible variable syntax for the target format."""
        pass

    @abstractmethod
    def _code_escape_filter(self, value: Any, table: bool = False) -> str:
        """Escape code for the target format.

        Args:
            value: The value to render as inline code
            table: Set to True when the output is placed in a table cell
                (enables cell-delimiter escaping where the format needs it).
        """
        pass

    @abstractmethod
    def _wrap_inline_code(self, text: str, table: bool = False) -> str:
        """Wrap text in format-specific inline code syntax."""
        pass

    def _format_default_filter(self, value: Any, table: bool = False) -> str:
        """Format default values for display.

        Args:
            value: The default value from the argument spec
            table: Set to True when the output is placed in a table cell
        """
        if value is None:
            return "N/A"
        elif isinstance(value, str):
            text = f'"{value}"'
        elif isinstance(value, bool):
            text = str(value).lower()
        else:
            text = str(value)
        return self._wrap_inline_code(text, table)

    def _format_description_filter(self, description: Any) -> str:
        """Format description for README display, handling both strings and lists."""
        text = normalize_description(description)
        return convert_ansible_markup(text, self._get_format_type(), self._role_options)

    @abstractmethod
    def _format_table_description_filter(
        self,
        description: Any,
        variable_name: str | None = None,
        max_length: int = TABLE_DESCRIPTION_MAX_LENGTH,
    ) -> str:
        """Format description for table display, handling multiline strings properly.

        Args:
            description: The description content to format
            variable_name: Optional variable name for creating anchor links
            max_length: Maximum length before truncation. Use 0 to disable.
        """
        pass


class MarkdownDocumentationGenerator(BaseDocumentationGenerator):
    """Generate Markdown documentation from argument specs."""

    def _get_filters(self) -> dict[str, Callable]:
        """Get Markdown-specific filters."""
        return {
            "ansible_escape": self._ansible_escape_filter,
            "code_escape": self._code_escape_filter,
            "format_default": self._format_default_filter,
            "format_description": self._format_description_filter,
            "format_table_description": self._format_table_description_filter,
        }

    def _get_format_type(self) -> str:
        """Get the format type for Markdown generator."""
        return "markdown"

    def _ansible_escape_filter(self, value: Any) -> str:
        """Escape Ansible variable syntax for Markdown."""
        if value is None:
            return "N/A"
        value_str = str(value)
        return value_str.replace("{{", "\\{\\{").replace("}}", "\\}\\}")

    def _code_escape_filter(self, value: Any, table: bool = False) -> str:
        """Escape code for Markdown inline code spans."""
        if value is None:
            return "N/A"
        return self._wrap_inline_code(str(value), table)

    def _wrap_inline_code(self, text: str, table: bool = False) -> str:
        """Build a CommonMark-valid inline code span for arbitrary content."""
        return md_code_span(text, table)

    def _format_table_description_filter(
        self,
        description: Any,
        variable_name: str | None = None,
        max_length: int = TABLE_DESCRIPTION_MAX_LENGTH,
    ) -> str:
        """Format description for Markdown table display with HTML stripping.

        Args:
            description: The description content to format
            variable_name: Optional variable name for creating anchor links
            max_length: Maximum length before truncation. Use 0 to disable.
        """
        text = normalize_description(description)
        if not text:
            return ""

        # Step 0: Convert Ansible markup (C(...), O(...), ...) to Markdown
        text = convert_ansible_markup(text, "markdown", self._role_options)

        # Step 1: Strip all HTML tags using proper HTML parser
        text = HTMLStripper.strip_tags(text)

        # Step 2 & 3: Process multiline descriptions for table display
        # First, normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on double newlines to identify paragraphs
        paragraphs = text.split("\n\n")

        # Process each paragraph: replace single newlines with spaces
        processed_paragraphs = []
        for paragraph in paragraphs:
            if paragraph.strip():
                # Replace single newlines within paragraph with spaces
                processed_paragraph = paragraph.replace("\n", " ")
                # Clean up multiple spaces
                processed_paragraph = " ".join(processed_paragraph.split())
                processed_paragraphs.append(processed_paragraph)

        # Join paragraphs with <br><br> for proper table display
        result = "<br><br>".join(processed_paragraphs)

        # Step 4 & 5: Truncate at max length and add ellipses with link if needed
        # If max_length is 0 or less, disable truncation
        if max_length > 0 and len(result) > max_length:
            truncated = truncate_preserving_tokens(result, max_length, MD_ATOMIC_TOKENS)

            # Add ellipses with link
            if variable_name:
                link_target = f"variable-{variable_name}"
                result = f"{truncated} […](#{link_target})"
            else:
                result = f"{truncated} […]"

        # Escape unescaped pipes so description text cannot break the table row
        return re.sub(r"(?<!\\)\|", r"\\|", result)


class RSTDocumentationGenerator(BaseDocumentationGenerator):
    """Generate reStructuredText documentation from argument specs."""

    def _get_filters(self) -> dict[str, Callable]:
        """Get reStructuredText-specific filters."""
        return {
            "ansible_escape": self._ansible_escape_filter,
            "code_escape": self._code_escape_filter,
            "format_default": self._format_default_filter,
            "format_description": self._format_description_filter,
            "format_table_description": self._format_table_description_filter,
            "csv_escape": self._csv_escape_filter,
        }

    def _get_format_type(self) -> str:
        """Get the format type for RST generator."""
        return "rst"

    def _ansible_escape_filter(self, value: Any) -> str:
        """Escape Ansible variable syntax for reStructuredText."""
        if value is None:
            return "N/A"
        value_str = str(value)
        # RST doesn't need special escaping for Ansible variables
        return value_str

    def _code_escape_filter(self, value: Any, table: bool = False) -> str:
        """Escape code for reStructuredText inline literals."""
        if value is None:
            return "N/A"
        return self._wrap_inline_code(str(value), table)

    def _wrap_inline_code(self, text: str, table: bool = False) -> str:
        """Wrap text in an RST inline literal (double backticks)."""
        _ = table  # RST tables use csv_escape; no delimiter escaping needed
        return rst_inline_literal(text)

    def _format_table_description_filter(
        self,
        description: Any,
        variable_name: str | None = None,
        max_length: int = TABLE_DESCRIPTION_MAX_LENGTH,
    ) -> str:
        """Format description for reStructuredText table display with HTML stripping.

        Args:
            description: The description content to format
            variable_name: Optional variable name for creating anchor links
            max_length: Maximum length before truncation. Use 0 to disable.
        """
        text = normalize_description(description)
        if not text:
            return ""

        # Step 0: Convert Ansible markup (C(...), O(...), ...) to RST
        text = convert_ansible_markup(text, "rst", self._role_options)

        # Step 1: Strip all HTML tags using proper HTML parser
        text = HTMLStripper.strip_tags(text)

        # Step 2 & 3: Process multiline descriptions for RST table display
        # Replace line breaks with spaces for single-line table cells
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # For RST tables, we need to handle multiline content differently
        # Replace paragraph breaks with | (pipe) for RST table continuation
        paragraphs = text.split("\n\n")
        processed_paragraphs = []

        for paragraph in paragraphs:
            if paragraph.strip():
                # Replace single newlines within paragraph with spaces
                processed_paragraph = paragraph.replace("\n", " ")
                # Clean up multiple spaces
                processed_paragraph = " ".join(processed_paragraph.split())
                processed_paragraphs.append(processed_paragraph)

        # Join paragraphs with | for RST table line continuation
        result = " | ".join(processed_paragraphs)

        # Step 4 & 5: Truncate at max length and add ellipses with link if needed
        # If max_length is 0 or less, disable truncation
        if max_length > 0 and len(result) > max_length:
            truncated = truncate_preserving_tokens(
                result, max_length, RST_ATOMIC_TOKENS
            )

            # Add ellipses with link (RST format)
            if variable_name:
                link_target = f"variable-{variable_name}"
                result = f"{truncated} `[…] <#{link_target}>`__"
            else:
                result = f"{truncated} […]"

        return result

    def _csv_escape_filter(self, value: Any) -> str:
        """Escape double quotes in strings for CSV format.

        In CSV format, double quotes within field values must be escaped
        by doubling them (e.g., 'He said ""Hello""' for: He said "Hello").

        Args:
            value: The value to escape for CSV

        Returns:
            CSV-escaped string
        """
        if value is None:
            return ""
        value_str = str(value)
        # Escape double quotes by doubling them
        return value_str.replace('"', '""')


# Factory function to create appropriate generator
def create_documentation_generator(
    format_type: str = "markdown",
    template_dir: Path | None = None,
    template_name: str = "default",
    template_file: Path | None = None,
) -> BaseDocumentationGenerator:
    """Create a documentation generator for the specified format.

    Args:
        format_type: Output format ("markdown" or "rst")
        template_dir: Custom template directory
        template_name: Name of the template to use
        template_file: Single template file

    Returns:
        Appropriate documentation generator instance

    Raises:
        ValueError: If format_type is not supported
    """
    if format_type.lower() == "markdown":
        return MarkdownDocumentationGenerator(
            template_dir, template_name, template_file
        )
    elif format_type.lower() == "rst":
        return RSTDocumentationGenerator(template_dir, template_name, template_file)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")
