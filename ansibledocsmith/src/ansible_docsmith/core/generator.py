"""Documentation generators for Markdown, reStructuredText and YAML comments."""

import html
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..constants import (
    MARKER_COMMENT_MD_BEGIN,
    MARKER_COMMENT_MD_END,
    MARKER_COMMENT_RST_BEGIN,
    MARKER_COMMENT_RST_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
    MARKER_README_TOC_END,
    MARKER_README_TOC_START,
)
from ..templates import TemplateManager
from .exceptions import FileOperationError, TemplateError


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
    def _code_escape_filter(self, value: Any) -> str:
        """Escape code for the target format."""
        pass

    def _format_default_filter(self, value: Any) -> str:
        """Format default values for display."""
        if value is None:
            return "N/A"
        elif isinstance(value, str):
            return f'`"{value}"`'
        elif isinstance(value, bool):
            return f"`{str(value).lower()}`"
        elif isinstance(value, list | dict):
            return f"`{value}`"
        else:
            return f"`{value}`"

    def _format_description_filter(self, description: Any) -> str:
        """Format description for README display, handling both strings and lists."""
        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation
            return "\n\n".join(
                str(item).strip() for item in description if str(item).strip()
            )
        return str(description).strip() if description else ""

    @abstractmethod
    def _format_table_description_filter(self, description: Any) -> str:
        """Format description for table display, handling multiline strings properly."""
        pass


class MarkdownDocumentationGenerator(BaseDocumentationGenerator):
    """Generate Markdown documentation from argument specs."""

    def _get_filters(self) -> dict[str, Callable[[Any], str]]:
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

    def _code_escape_filter(self, value: Any) -> str:
        """Escape code for Markdown code blocks."""
        if value is None:
            return "N/A"
        value_str = str(value)
        escaped = value_str.replace("`", "\\`").replace("|", "\\|")
        return f"`{escaped}`"

    def _format_table_description_filter(self, description: Any) -> str:
        """Format description for Markdown table display, handling multiline strings."""
        if description is None:
            return ""

        # Normalize description to string format
        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation
            text = "\n\n".join(
                str(item).strip() for item in description if str(item).strip()
            )
        else:
            # Convert to string and strip, handling any YAML object types
            try:
                text = str(description)
                text = text.strip() if hasattr(text, "strip") else text
            except Exception:
                return ""

        if not text:
            return ""

        # Process multiline descriptions for table display:
        # 1. Replace double line breaks (paragraph separators) with <br><br>
        # 2. Replace single line breaks with spaces

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
                # HTML encode the content for safe display in tables
                processed_paragraph = html.escape(processed_paragraph)
                processed_paragraphs.append(processed_paragraph)

        # Join paragraphs with <br><br> for proper table display
        return "<br><br>".join(processed_paragraphs)


class RSTDocumentationGenerator(BaseDocumentationGenerator):
    """Generate reStructuredText documentation from argument specs."""

    def _get_filters(self) -> dict[str, Callable[[Any], str]]:
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

    def _code_escape_filter(self, value: Any) -> str:
        """Escape code for reStructuredText code blocks."""
        if value is None:
            return "N/A"
        value_str = str(value)
        # RST uses double backticks for inline code
        escaped = value_str.replace("`", "\\`")
        return f"``{escaped}``"

    def _format_table_description_filter(self, description: Any) -> str:
        """Format description for reStructuredText table display."""
        if description is None:
            return ""

        # Normalize description to string format
        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation
            text = "\n\n".join(
                str(item).strip() for item in description if str(item).strip()
            )
        else:
            # Convert to string and strip, handling any YAML object types
            try:
                text = str(description)
                text = text.strip() if hasattr(text, "strip") else text
            except Exception:
                return ""

        if not text:
            return ""

        # Process multiline descriptions for RST table display:
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
        return " | ".join(processed_paragraphs)

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


class BaseTocGenerator(ABC):
    """Abstract base class for Table of Contents generators."""

    def __init__(self, bullet_style: str | None = None):
        """Initialize TOC generator.

        Args:
            bullet_style: Bullet style to use. If None, auto-detect.
        """
        self.bullet_style = bullet_style

    @abstractmethod
    def _get_format_type(self) -> str:
        """Return the format type this generator handles."""
        pass

    @abstractmethod
    def _extract_headings(self, content: str) -> list[dict[str, Any]]:
        """Extract headings from content.

        Returns:
            List of heading dictionaries with 'text', 'level', and 'anchor' keys
        """
        pass

    @abstractmethod
    def _detect_bullet_style(self, content: str) -> str:
        """Auto-detect bullet style from existing content."""
        pass

    @abstractmethod
    def _create_anchor_link(self, text: str) -> str:
        """Create anchor link from heading text."""
        pass

    @abstractmethod
    def _generate_toc_lines(
        self, headings: list[dict[str, Any]], bullet_style: str
    ) -> str:
        """Generate TOC lines from headings."""
        pass

    def generate_toc(self, content: str) -> str:
        """Generate Table of Contents from content.

        Args:
            content: Content to analyze

        Returns:
            Generated TOC as string
        """
        headings = self._extract_headings(content)
        if not headings:
            return ""

        # Auto-detect bullet style if not specified
        bullet_style = self.bullet_style or self._detect_bullet_style(content)

        return self._generate_toc_lines(headings, bullet_style)


class MarkdownTocGenerator(BaseTocGenerator):
    """Generate Table of Contents from markdown content."""

    def _get_format_type(self) -> str:
        """Return the format type this generator handles."""
        return "markdown"

    def _extract_headings(self, content: str) -> list[dict[str, Any]]:
        """Extract headings from markdown content.

        Returns:
            List of heading dictionaries with 'text', 'level', and 'anchor' keys
        """
        headings = []
        heading_pattern = r'^(#{1,6})\s+(.+?)(?:<a\s+id="([^"]+)"></a>)?$'

        for line in content.split("\n"):
            match = re.match(heading_pattern, line.strip(), re.MULTILINE)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                anchor = match.group(3) or self._create_anchor_link(text)

                headings.append({"text": text, "level": level, "anchor": anchor})

        return headings

    def _detect_bullet_style(self, content: str) -> str:
        """Auto-detect bullet style from existing content.

        Args:
            content: Markdown content to analyze

        Returns:
            Detected bullet style ("*" or "-"), defaults to "*"
        """
        # Look for existing list patterns
        dash_pattern = r"^\s*-\s+\["
        asterisk_pattern = r"^\s*\*\s+\["

        dash_count = len(re.findall(dash_pattern, content, re.MULTILINE))
        asterisk_count = len(re.findall(asterisk_pattern, content, re.MULTILINE))

        # Return the more common style, default to "*"
        return "-" if dash_count > asterisk_count else "*"

    def _create_anchor_link(self, text: str) -> str:
        """Create anchor link from heading text.

        Args:
            text: Heading text

        Returns:
            Anchor link suitable for markdown
        """
        # Convert to lowercase and replace spaces/special chars with hyphens
        anchor = re.sub(r"[^\w\s-]", "", text.lower())
        anchor = re.sub(r"[-\s]+", "-", anchor)
        return anchor.strip("-")

    def _generate_toc_lines(
        self, headings: list[dict[str, Any]], bullet_style: str
    ) -> str:
        """Generate TOC lines from headings.

        Args:
            headings: List of heading dictionaries
            bullet_style: Bullet style to use

        Returns:
            Generated TOC lines as string
        """
        if not headings:
            return ""

        lines = []
        min_level = min(h["level"] for h in headings)

        for heading in headings:
            # Calculate indentation based on heading level
            indent_level = heading["level"] - min_level
            indent = "  " * indent_level

            # Create TOC line
            line = f"{indent}{bullet_style} [{heading['text']}](#{heading['anchor']})"
            lines.append(line)

        return "\n".join(lines)


class RSTTocGenerator(BaseTocGenerator):
    """
    Generate Table of Contents from reStructuredText content.

    ATTENTION:
    Unlike the ToC generation in Markdown, use something like

      .. contents:: Table of Contents

    whenever possible. This is a very rough list based fallback mechanism if
    your reStructuredText (reST) renderer is very limited.
    """

    def _get_format_type(self) -> str:
        """Return the format type this generator handles."""
        return "rst"

    def _extract_headings(self, content: str) -> list[dict[str, Any]]:
        """Extract headings from RST content.

        Returns:
            List of heading dictionaries with 'text', 'level', and 'anchor' keys
        """
        headings = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check next line for RST underline
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()

                # RST heading patterns with underlines
                if next_line and len(set(next_line)) == 1:
                    underline_char = next_line[0]
                    if underline_char in "=-`':\"~^_*+#<>" and len(next_line) >= len(
                        line
                    ):
                        # Map underline characters to heading levels (RST convention)
                        level_map = {
                            "=": 1,
                            "-": 2,
                            "`": 3,
                            "'": 4,
                            ":": 5,
                            '"': 6,
                            "~": 3,
                            "^": 4,
                            "_": 5,
                            "*": 6,
                            "+": 7,
                            "#": 8,
                            "<": 9,
                            ">": 10,
                        }
                        level = level_map.get(underline_char, 1)
                        anchor = self._create_anchor_link(line)

                        # Strip inline "``" as "```foo`` <#anchor>`" does not work
                        # with many renderers out there
                        line = re.sub(r"``", "", line)

                        headings.append(
                            {"text": line, "level": level, "anchor": anchor}
                        )

        return headings

    def _detect_bullet_style(self, content: str) -> str:
        """Auto-detect bullet style from existing RST content."""
        # Look for existing list patterns in RST
        dash_pattern = r"^\s*-\s+\`"
        asterisk_pattern = r"^\s*\*\s+\`"

        dash_count = len(re.findall(dash_pattern, content, re.MULTILINE))
        asterisk_count = len(re.findall(asterisk_pattern, content, re.MULTILINE))

        # Return the more common style, default to "*"
        return "-" if dash_count > asterisk_count else "*"

    def _create_anchor_link(self, text: str) -> str:
        """Create anchor link from heading text for RST.

        Args:
            text: Heading text

        Returns:
            Anchor link suitable for RST
        """
        # Convert to lowercase and replace spaces/special chars with hyphens
        anchor = re.sub(r"[^\w\s-]", "", text.lower())
        anchor = re.sub(r"[-\s]+", "-", anchor)
        return anchor.strip("-")

    def _generate_toc_lines(
        self, headings: list[dict[str, Any]], bullet_style: str
    ) -> str:
        """Generate TOC lines from headings for RST.

        Args:
            headings: List of heading dictionaries
            bullet_style: Bullet style to use

        Returns:
            Generated TOC lines as RST string
        """
        if not headings:
            return ""

        lines = []
        min_level = min(h["level"] for h in headings)
        prev_level = None

        lines.append("")
        for i, heading in enumerate(headings):
            # Calculate indentation based on heading level
            indent_level = heading["level"] - min_level
            indent = "  " * indent_level

            # Add blank line before level changes (except for the first item)
            if i > 0 and prev_level is not None and heading["level"] != prev_level:
                lines.append("")

            # Create TOC line with RST-style internal link
            line = (
                f"{indent}{bullet_style} `{heading['text']} <#{heading['anchor']}>`__"
            )
            lines.append(line)
            prev_level = heading["level"]
        lines.append("")

        return "\n".join(lines)


def create_toc_generator(
    format_type: str = "markdown", bullet_style: str | None = None
) -> BaseTocGenerator:
    """Create a TOC generator for the specified format.

    Args:
        format_type: Output format ("markdown" or "rst")
        bullet_style: Bullet style to use. If None, auto-detect.

    Returns:
        Appropriate TOC generator instance

    Raises:
        ValueError: If format_type is not supported
    """
    if format_type.lower() == "markdown":
        return MarkdownTocGenerator(bullet_style)
    elif format_type.lower() == "rst":
        return RSTTocGenerator(bullet_style)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")


class DefaultsCommentGenerator:
    """Add block comments above variables in entry-point files from argument specs."""

    def __init__(self):
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.explicit_start = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def add_comments(self, defaults_path: Path, specs: dict[str, Any]) -> str | None:
        """Add block comments above variables in defaults file."""

        if not defaults_path.exists():
            return None

        try:
            # Read the original file as text
            with open(defaults_path, encoding="utf-8") as file:
                original_content = file.read()

            # Parse YAML to validate and get variable names
            data = self.yaml.load(original_content)
            if not data:
                return None

            # Get the first (and typically only) entry point's options
            entry_point_name = next(iter(specs.keys()))
            entry_point_spec = specs[entry_point_name]
            options = entry_point_spec.get("options", {})

            # Clean the file first - remove all existing variable comments
            cleaned_content = self._remove_existing_variable_comments(
                original_content, options
            )

            # Process the cleaned file line by line to insert new comments
            lines = cleaned_content.splitlines()
            result_lines = []

            for line in lines:
                # Check if this line defines a variable
                variable_match = self._get_variable_from_line(line)

                if variable_match and variable_match in options:
                    var_spec = options[variable_match]
                    description = var_spec.get("description", "")

                    if description:
                        # Generate block comment with full variable details
                        comment_lines = self._format_block_comment(var_spec)

                        # Add blank line before comment (if previous line isn't blank)
                        if result_lines and result_lines[-1].strip():
                            result_lines.append("")

                        # Add comment lines
                        result_lines.extend(comment_lines)

                    # Clean any inline comments from the variable line
                    line = self._remove_inline_comment(line)

                # Add the original line
                result_lines.append(line)

            return "\n".join(result_lines) + "\n"

        except YAMLError as e:
            raise FileOperationError(f"Failed to parse {defaults_path}: {e}")
        except Exception as e:
            raise FileOperationError(f"Failed to add comments: {e}")

    def _get_variable_from_line(self, line: str) -> str | None:
        """Extract variable name from a YAML line."""
        # Match lines like "var_name:" or "var_name: value"
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:", line.strip())
        return match.group(1) if match else None

    def _format_block_comment(self, var_spec: dict[str, Any]) -> list[str]:
        """Format variable spec as detailed block comment with proper line wrapping."""
        description = var_spec.get("description", "")
        # Normalize description to handle both string and list formats
        text = self._normalize_description(description)

        # Split into paragraphs
        paragraphs = text.split("\n\n") if "\n\n" in text else text.split("\n")

        comment_lines = []

        # Add description paragraphs
        for i, paragraph in enumerate(paragraphs):
            if i > 0:  # Add blank comment line between paragraphs
                comment_lines.append("#")

            # Wrap paragraph to 80 chars (minus "# " prefix)
            wrapped_lines = self._wrap_text(paragraph.strip(), max_width=78)

            for wrapped_line in wrapped_lines:
                comment_lines.append(f"# {wrapped_line}" if wrapped_line else "#")

        # Add separator line before variable details
        if comment_lines and text.strip():
            comment_lines.append("#")

        # Add variable details
        details = self._format_variable_details(var_spec)
        comment_lines.extend(details)

        return comment_lines

    def _format_variable_details(self, var_spec: dict[str, Any]) -> list[str]:
        """Format variable details (type, required, default, choices) as comments."""
        details = []

        # Type
        var_type = var_spec.get("type", "str")
        details.append(f"# - Type: {var_type}")

        # Required
        required = var_spec.get("required", False)
        details.append(f"# - Required: {'Yes' if required else 'No'}")

        # Default value
        default = var_spec.get("default")
        if default is not None:
            formatted_default = self._format_default_value(default)
            details.append(f"# - Default: {formatted_default}")

        # Choices
        choices = var_spec.get("choices")
        if choices:
            formatted_choices = ", ".join(str(choice) for choice in choices)
            details.append(f"# - Choices: {formatted_choices}")

        # List elements
        elements = var_spec.get("elements")
        if elements:
            details.append(f"# - List elements: {elements}")

        return details

    def _format_default_value(self, default: Any) -> str:
        """Format default value for display in comments."""
        if default is None:
            return "N/A"
        elif isinstance(default, str):
            return default
        elif isinstance(default, bool):
            return str(default).lower()
        elif isinstance(default, list | dict):
            if not default:  # Empty list or dict
                return "{}" if isinstance(default, dict) else "[]"
            else:
                return str(default)
        else:
            return str(default)

    def _normalize_description(self, description: Any) -> str:
        """Normalize description to string format with improved formatting rules.

        Rules:
        - Single linebreaks in regular text become spaces
        - Two or more linebreaks become double newlines (\n\n)
        - Markdown lists are preserved
        - Markdown code blocks are preserved
        """
        if description is None:
            return ""

        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation
            text = "\n\n".join(
                str(item).strip() for item in description if str(item).strip()
            )
        else:
            # Convert to string and strip, handling any YAML object types
            try:
                text = str(description)
                text = text.strip() if hasattr(text, "strip") else text
            except Exception:
                return ""

        if not text:
            return ""

        return self._parse_and_format_description(text)

    def _parse_and_format_description(self, text: str) -> str:
        """Parse description using commonmark and apply enhanced formatting rules.

        Uses a proper markdown parser to handle complex structures like lists
        and code blocks correctly.

        Rules:
        - Single linebreaks (softbreaks) in regular text become spaces
        - Paragraphs are separated with double newlines (\n\n)
        - Markdown lists are preserved exactly as-is
        - Markdown code blocks are preserved exactly as-is

        Args:
            text: Input text to format

        Returns:
            Formatted text following the enhanced rules
        """
        if not text.strip():
            return ""

        from commonmark import Parser

        # Parse the markdown text into an AST
        parser = Parser()
        ast = parser.parse(text)

        # Convert the AST back to formatted text
        result_parts = []
        if ast.first_child:
            child = ast.first_child
            while child:
                formatted_block = self._format_ast_node(child)
                if formatted_block:
                    result_parts.append(formatted_block)
                child = child.nxt

        # Join blocks with double newlines (paragraph separation)
        return "\n\n".join(result_parts).strip()

    def _format_ast_node(self, node) -> str:
        """Format a single AST node based on its type.

        Args:
            node: CommonMark AST node

        Returns:
            Formatted text for this node
        """
        if node.t == "paragraph":
            # For paragraphs, join inline content and convert softbreaks to spaces
            return self._format_paragraph_node(node)
        elif node.t == "list":
            # For lists, preserve structure exactly
            return self._format_list_node(node)
        elif node.t == "code_block":
            # For code blocks, preserve content exactly
            return f"```\n{node.literal or ''}```"
        elif node.t == "heading":
            # For headings, format as plain text (shouldn't occur in descriptions)
            return self._format_paragraph_node(node)
        else:
            # For other block types, format as paragraph
            return self._format_paragraph_node(node)

    def _format_paragraph_node(self, node) -> str:
        """Format a paragraph node, converting softbreaks to spaces.

        Args:
            node: Paragraph AST node

        Returns:
            Formatted paragraph text
        """
        text_parts = []
        if node.first_child:
            child = node.first_child
            while child:
                if child.t == "text":
                    text_parts.append(child.literal or "")
                elif child.t == "softbreak":
                    # Single linebreaks become spaces
                    text_parts.append(" ")
                elif child.t == "code":
                    # Inline code - preserve as-is
                    text_parts.append(f"`{child.literal or ''}`")
                elif child.t == "linebreak":
                    # Hard line breaks (two spaces + newline) - preserve
                    text_parts.append("\n")
                else:
                    # Handle other inline elements as text
                    text_parts.append(child.literal or "")
                child = child.nxt

        # Join and clean up multiple spaces
        result = "".join(text_parts)
        return " ".join(result.split())

    def _format_list_node(self, node) -> str:
        """Format a list node, preserving structure exactly.

        Args:
            node: List AST node

        Returns:
            Formatted list text
        """
        list_items = []
        if node.first_child:
            item = node.first_child
            while item:
                if item.t == "item":
                    item_text = self._format_list_item_node(item)
                    if item_text:
                        list_items.append(item_text)
                item = item.nxt

        return "\n".join(list_items)

    def _format_list_item_node(self, node) -> str:
        """Format a list item node.

        Args:
            node: List item AST node

        Returns:
            Formatted list item text
        """
        # List items start with "- "
        item_parts = []
        if node.first_child:
            child = node.first_child
            while child:
                if child.t == "paragraph":
                    # Format the paragraph content but preserve structure for lists
                    para_text = self._format_paragraph_node(child)
                    item_parts.append(para_text)
                else:
                    # Handle other content in list items
                    formatted = self._format_ast_node(child)
                    if formatted:
                        item_parts.append(formatted)
                child = child.nxt

        # Join list item content and prefix with "- "
        item_content = " ".join(item_parts)
        return f"- {item_content}"

    def _split_into_blocks(self, text: str) -> list[dict]:
        """Split text into blocks preserving markdown structure.

        Returns a list of block dictionaries with 'type' and 'content' keys:
        - type: 'text', 'code_block', or 'list'
        - content: the block content as string

        Args:
            text: Formatted text from CommonMark parser

        Returns:
            List of block dictionaries
        """
        if not text.strip():
            return []

        blocks = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for code block start
            if line.strip() == '```':
                # Collect entire code block
                code_lines = [line]
                i += 1

                # Find matching closing ```
                while i < len(lines):
                    code_lines.append(lines[i])
                    if lines[i].strip() == '```':
                        break
                    i += 1

                blocks.append({
                    'type': 'code_block',
                    'content': '\n'.join(code_lines)
                })

            # Check for list items
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                # Collect consecutive list items
                list_lines = []

                while i < len(lines) and (
                    lines[i].strip().startswith('- ') or
                    lines[i].strip().startswith('* ') or
                    lines[i].startswith('  ') or  # List continuation
                    lines[i].strip() == ''  # Empty lines in lists
                ):
                    list_lines.append(lines[i])
                    i += 1

                # Don't increment i here since we already moved past the list
                i -= 1  # Back up one since we'll increment at end of loop

                if list_lines:
                    blocks.append({
                        'type': 'list',
                        'content': '\n'.join(list_lines)
                    })

            # Regular text or empty lines
            else:
                # Collect consecutive non-special lines
                text_lines = []

                while i < len(lines) and (
                    not lines[i].strip() == '```' and
                    not lines[i].strip().startswith('- ') and
                    not lines[i].strip().startswith('* ')
                ):
                    text_lines.append(lines[i])
                    i += 1

                i -= 1  # Back up one since we'll increment at end of loop

                if text_lines:
                    blocks.append({
                        'type': 'text',
                        'content': '\n'.join(text_lines).rstrip()
                    })

            i += 1

        return blocks

    def _wrap_text(self, text: str, max_width: int = 78) -> list[str]:
        """Wrap text to specified width while preserving markdown structure.

        This method is block-aware and preserves code blocks, lists, and other
        structures exactly as formatted by the CommonMark parser.
        """
        if not text:
            return [""]

        # Split into blocks first to handle different content types
        blocks = self._split_into_blocks(text)
        if not blocks:
            return [""]

        wrapped_lines = []

        for block in blocks:
            block_type = block['type']
            content = block['content']

            if block_type == 'code_block':
                # Code blocks are preserved exactly as-is
                wrapped_lines.extend(content.split('\n'))

            elif block_type == 'list':
                # Lists are preserved exactly as-is
                wrapped_lines.extend(content.split('\n'))

            elif block_type == 'text':
                # Regular text gets word-wrapped
                text_lines = content.split('\n')
                for line in text_lines:
                    line = line.strip()

                    if not line:
                        wrapped_lines.append("")
                    elif len(line) <= max_width:
                        wrapped_lines.append(line)
                    else:
                        wrapped_lines.extend(self._wrap_single_line(line, max_width))

        return wrapped_lines if wrapped_lines else [""]

    def _wrap_single_line(self, line: str, max_width: int = 78) -> list[str]:
        """Wrap a single line of text to specified width."""
        words = line.split()
        if not words:
            return [""]

        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            space_length = 1 if current_line else 0

            if current_length + space_length + word_length <= max_width:
                current_line.append(word)
                current_length += space_length + word_length
            else:
                # Start a new line
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length

        # Add the last line
        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def _has_block_comment_above(self, result_lines: list[str]) -> bool:
        """Check if there's already a variable-specific block comment above."""
        # We should only skip if the immediately preceding lines contain
        # a block comment that was just added for this variable
        # For now, we'll be more permissive and always add comments
        # since detecting "our" comments vs existing general comments is complex
        # Parameter result_lines is reserved for future implementation
        _ = result_lines  # Suppress unused parameter warning
        return False

    def _remove_inline_comment(self, line: str) -> str:
        """Remove inline comments from a YAML line, preserving variable definition."""
        # Match variable definitions and remove everything after first #
        # (but preserve quoted strings)
        if ":" in line:
            # Simple approach: find # that's not inside quotes
            in_quotes = False
            quote_char = None

            for i, char in enumerate(line):
                if char in ['"', "'"] and (i == 0 or line[i - 1] != "\\"):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif char == "#" and not in_quotes:
                    # Found unquoted comment, remove it and trailing whitespace
                    return line[:i].rstrip()

        return line

    def _remove_existing_variable_comments(self, content: str, options: dict) -> str:
        """Remove existing block comments that appear to be for variables."""
        lines = content.splitlines()
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is a comment line
            if line.strip().startswith("#"):
                # Look ahead to see if there's a variable definition soon
                j = i + 1
                found_variable = False

                # Skip other comment lines and blank lines
                while j < len(lines) and (
                    lines[j].strip().startswith("#") or not lines[j].strip()
                ):
                    j += 1

                # Check if the next non-comment line is a variable we're managing
                if j < len(lines):
                    var_match = self._get_variable_from_line(lines[j])
                    if var_match and var_match in options:
                        found_variable = True

                # If this comment precedes a variable we manage, skip it
                if found_variable:
                    # Skip all comment lines until we hit the variable
                    while i < j:
                        if not lines[i].strip():  # Keep blank lines
                            result_lines.append(lines[i])
                        i += 1
                    continue

            result_lines.append(line)
            i += 1

        return "\n".join(result_lines)


class ReadmeUpdater:
    """Update README files with generated content."""

    def __init__(
        self,
        format_type: str = "markdown",
        start_marker: str = MARKER_README_MAIN_START,
        end_marker: str = MARKER_README_MAIN_END,
        toc_bullet_style: str | None = None,
    ):
        self.format_type = format_type.lower()

        # Set format-specific comment markers
        if self.format_type == "rst":
            comment_begin = MARKER_COMMENT_RST_BEGIN
            comment_end = MARKER_COMMENT_RST_END
        else:
            comment_begin = MARKER_COMMENT_MD_BEGIN
            comment_end = MARKER_COMMENT_MD_END

        self.start_marker = f"{comment_begin}{start_marker}{comment_end}"
        self.end_marker = f"{comment_begin}{end_marker}{comment_end}"

        # TOC markers
        self.toc_start_marker = f"{comment_begin}{MARKER_README_TOC_START}{comment_end}"
        self.toc_end_marker = f"{comment_begin}{MARKER_README_TOC_END}{comment_end}"

        # TOC generator for the specified format
        self.toc_generator = create_toc_generator(
            format_type=self.format_type, bullet_style=toc_bullet_style
        )

    def update_readme(self, readme_path: Path, new_content: str) -> bool:
        """Update content between markers in README file."""

        try:
            updated_content = self._get_updated_content(readme_path, new_content)
            readme_path.write_text(updated_content, encoding="utf-8")
            return True

        except Exception as e:
            raise FileOperationError(f"Failed to update README: {e}")

    def _get_updated_content(self, readme_path: Path, new_content: str) -> str:
        """Get the updated content without writing to file."""
        if readme_path.exists():
            content = readme_path.read_text(encoding="utf-8")
            # Update main content
            content = self._replace_between_markers(
                content, new_content, self.start_marker, self.end_marker
            )
            # Update TOC if markers are present
            content = self._update_toc_section(content)
            return content
        else:
            # Create new README with template
            return self._create_new_readme(new_content, readme_path.parent.name)

    def _replace_between_markers(
        self, content: str, new_content: str, start_marker: str, end_marker: str
    ) -> str:
        """Replace content between markers."""

        if start_marker not in content or end_marker not in content:
            # Add markers and content at the end
            return content + f"\n\n{start_marker}\n{new_content}\n{end_marker}\n"

        # Replace content between existing markers
        pattern = f"({re.escape(start_marker)}).*?({re.escape(end_marker)})"
        replacement = f"\\1\n{new_content}\n\\2"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)

    def _update_toc_section(self, content: str) -> str:
        """Update TOC section if markers are present, using only main content."""

        # Skip TOC generation for non-Markdown formats
        if not self.toc_generator:
            return content

        # Check if TOC markers exist
        if self.toc_start_marker not in content or self.toc_end_marker not in content:
            return content

        # Extract content between MAIN markers to generate TOC from
        main_content = self._extract_main_content(content)

        # Detect bullet style from content outside the managed sections
        external_content = self._extract_external_content(content)
        if external_content and not self.toc_generator.bullet_style:
            detected_style = self.toc_generator._detect_bullet_style(external_content)
            self.toc_generator.bullet_style = detected_style

        # Generate TOC only from the main content (generated by the tool)
        toc_content = self.toc_generator.generate_toc(main_content)

        # Update TOC section
        return self._replace_between_markers(
            content, toc_content, self.toc_start_marker, self.toc_end_marker
        )

    def _extract_main_content(self, content: str) -> str:
        """Extract content between MAIN markers for TOC generation."""
        if self.start_marker not in content or self.end_marker not in content:
            return ""

        # Extract content between main markers using regex
        pattern = f"{re.escape(self.start_marker)}(.*?){re.escape(self.end_marker)}"
        match = re.search(pattern, content, flags=re.DOTALL)

        if match:
            return match.group(1).strip()

        return ""

    def _extract_external_content(self, content: str) -> str:
        """Extract content outside MAIN and TOC markers for bullet style detection."""
        # Remove content between MAIN markers
        if self.start_marker in content and self.end_marker in content:
            pattern = f"{re.escape(self.start_marker)}.*?{re.escape(self.end_marker)}"
            content = re.sub(pattern, "", content, flags=re.DOTALL)

        # Remove content between TOC markers
        if self.toc_start_marker in content and self.toc_end_marker in content:
            pattern = (
                f"{re.escape(self.toc_start_marker)}.*?{re.escape(self.toc_end_marker)}"
            )
            content = re.sub(pattern, "", content, flags=re.DOTALL)

        return content.strip()

    def _create_new_readme(self, role_content: str, role_name: str) -> str:
        """Create a new README with basic template."""
        if self.format_type == "rst":
            return f"""Ansible role: {role_name}
{"=" * (15 + len(role_name))}

FIXME Add role description here.

{self.start_marker}
{role_content}
{self.end_marker}


Dependencies
============

See ``dependencies`` in ``meta/main.yml``.


Compatibility
=============

See ``min_ansible_version`` in ``meta/main.yml``.


Licensing, copyright
====================

Copyright (c) [FIXME YYYY Your Name]

[FIXME Adapt license:
This project is licensed under the GNU General Public License v3.0 or later
(SPDX-License-Identifier: ``GPL-3.0-or-later``)].


Author information
==================

This project was created and is maintained by [FIXME Your Name].

"""
        else:
            return f"""# Ansible role: `{role_name}`

FIXME Add role description here.

{self.start_marker}
{role_content}
{self.end_marker}


## Dependencies<a id="dependencies"></a>

See `dependencies` in [`meta/main.yml`](./meta/main.yml).


## Compatibility<a id="compatibility"></a>

See `min_ansible_version` in [`meta/main.yml`](./meta/main.yml).


## Licensing, copyright<a id="licensing-copyright"></a>

Copyright (c) [FIXME YYYY Your Name]

[FIXME Adapt license:
This project is licensed under the GNU General Public License v3.0 or later
(SPDX-License-Identifier: `GPL-3.0-or-later`)].


## Author information

This project was created and is maintained by [FIXME Your Name].

"""
