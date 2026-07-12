"""Documentation generators for Markdown, reStructuredText and YAML comments."""

import html
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..constants import (
    COMMENT_MAX_NESTED_DEPTH,
    MARKER_COMMENT_MD_BEGIN,
    MARKER_COMMENT_MD_END,
    MARKER_COMMENT_RST_BEGIN,
    MARKER_COMMENT_RST_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
    MARKER_README_TOC_END,
    MARKER_README_TOC_START,
    TABLE_DESCRIPTION_MAX_LENGTH,
)
from ..templates import TemplateManager
from .exceptions import FileOperationError, TemplateError
from .markup import convert_ansible_markup, md_code_span, rst_inline_literal

# Tokens that must never be split by table-cell truncation: Markdown
# links and inline code spans (left), RST hyperlinks and inline literals
# (right), each with trailing punctuation attached.
_MD_ATOMIC_TOKENS = re.compile(r"\[[^\]]*\]\([^)]*\)\S*|`+[^`]+`+\S*|\S+")
_RST_ATOMIC_TOKENS = re.compile(r"`[^`<>]*<[^>]*>`__\S*|``[^`]+``\S*|\S+")


def normalize_description(description: Any) -> str:
    """Normalize a description value (string or list) to a single string.

    Argument specs allow descriptions as a string or as a list of
    paragraphs; list items are joined as paragraphs separated by blank
    lines. Any other YAML object type is converted via str().
    """
    if description is None:
        return ""
    if isinstance(description, list):
        return "\n\n".join(
            str(item).strip() for item in description if str(item).strip()
        )
    try:
        return str(description).strip()
    except Exception:
        return ""


def _truncate_preserving_tokens(
    text: str, max_length: int, token_pattern: re.Pattern
) -> str:
    """Truncate at a word boundary without splitting atomic markup tokens.

    Accumulates whole tokens (words, links, code spans) until the length
    limit is reached, so truncation can never produce broken inline markup
    such as half a link.
    """
    result = ""
    for token in token_pattern.findall(text):
        candidate = f"{result} {token}" if result else token
        if len(candidate) > max_length:
            break
        result = candidate
    # A single oversized token: fall back to a hard character cut
    return result if result else text[:max_length].rstrip()


class HTMLStripper(HTMLParser):
    """HTML parser that strips all tags and returns clean text."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, data):
        """Handle text data between HTML tags."""
        self.text.append(data)

    def get_text(self):
        """Return the cleaned text."""
        return "".join(self.text)

    @classmethod
    def strip_tags(cls, html_text: str) -> str:
        """Strip HTML tags from text and return clean text."""
        if not html_text:
            return ""

        stripper = cls()
        try:
            stripper.feed(html_text)
            # Unescape HTML entities as well
            return html.unescape(stripper.get_text())
        except Exception:
            # Fallback to regex if HTML is malformed
            return re.sub(r"<[^>]+>", "", html_text)


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
            truncated = _truncate_preserving_tokens(
                result, max_length, _MD_ATOMIC_TOKENS
            )

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
            truncated = _truncate_preserving_tokens(
                result, max_length, _RST_ATOMIC_TOKENS
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
        """Extract headings from markdown content using CommonMark AST.

        Uses AST parsing to avoid false positives from code blocks or other
        contexts where '#' characters might appear but aren't actually headings.

        Returns:
            List of heading dictionaries with 'text', 'level', and 'anchor' keys
        """
        if not content.strip():
            return []

        try:
            from commonmark import Parser

            headings = []
            parser = Parser()
            ast = parser.parse(content)

            # Walk through all nodes in the AST
            walker = ast.walker()
            event = walker.nxt()

            while event is not None:
                node, entering = event["node"], event["entering"]

                # Process heading nodes when entering them
                if entering and node.t == "heading":
                    level = node.level
                    # Extract   text content from all child nodes
                    text = self._extract_text_from_node(node)

                    # Check for existing anchor in the heading text
                    anchor_match = re.search(r'<a\s+id="([^"]+)"></a>', text)
                    if anchor_match:
                        anchor = anchor_match.group(1)
                        # Remove the anchor tag from the text
                        text = re.sub(r'<a\s+id="[^"]+"></a>', "", text).strip()
                    else:
                        anchor = self._create_anchor_link(text)

                    headings.append({"text": text, "level": level, "anchor": anchor})

                event = walker.nxt()

            return headings

        except Exception:
            # Fallback to regex-based extraction if AST parsing fails
            return self._extract_headings_fallback(content)

    def _extract_text_from_node(self, node) -> str:
        """Extract text from a CommonMark AST node preserving inline formatting.

        This method preserves inline code formatting by adding backticks around
        code nodes to maintain the original heading text appearance.

        Args:
            node: CommonMark AST node

        Returns:
            Text content with inline formatting preserved
        """
        text_parts = []
        walker = node.walker()
        event = walker.nxt()

        while event is not None:
            current_node, entering = event["node"], event["entering"]

            if entering and current_node.t == "code":
                # For inline code, add backticks to preserve formatting
                text_parts.append(f"`{current_node.literal}`")
            elif entering and current_node.literal:
                text_parts.append(current_node.literal)

            event = walker.nxt()

        return "".join(text_parts).strip()

    def _extract_headings_fallback(self, content: str) -> list[dict[str, Any]]:
        """Fallback regex-based heading extraction for error cases.

        Args:
            content: Markdown content to parse

        Returns:
            List of heading dictionaries
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

    def __init__(self, nested_options: bool = True):
        """Initialize the comment generator.

        Args:
            nested_options: Whether to document nested options ("dict
                attributes") of a variable inside its comment block.
        """
        self.nested_options = nested_options
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
        """Extract a top-level variable name from a YAML line.

        Only matches keys starting at column 0. Indented keys belong to
        nested structures and must not be treated as role variables, even
        if they share a name with one.
        """
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:", line)
        return match.group(1) if match else None

    def _format_block_comment(self, var_spec: dict[str, Any]) -> list[str]:
        """Format variable spec as detailed block comment with proper line wrapping."""
        description = var_spec.get("description", "")

        # Normalize description - handle both string and list formats
        normalized_description = self._normalize_description(description)

        # Parse and format description with AST-aware wrapping (minus "# " = 78)
        formatted_text = self._parse_and_format_description(
            normalized_description, max_width=78
        )

        comment_lines = []

        # Add description paragraphs
        if formatted_text:
            lines = formatted_text.split("\n")
            for line in lines:
                comment_lines.append(f"# {line}" if line else "#")

        # Add separator line before variable details
        if comment_lines and formatted_text.strip():
            comment_lines.append("#")

        # Add variable details
        details = self._format_variable_details(var_spec)
        comment_lines.extend(details)

        return comment_lines

    def _format_variable_details(
        self, var_spec: dict[str, Any], indent: str = "", depth: int = 0
    ) -> list[str]:
        """Format variable details (type, required, default, choices) as comments.

        Args:
            var_spec: The (normalized) option specification
            indent: Indentation inside the comment, after the "# " prefix
            depth: Current nesting depth (0 = top-level variable)
        """
        details = []

        # Type
        var_type = var_spec.get("type", "str")
        details.append(f"# {indent}- Type: {var_type}")

        # Required
        required = var_spec.get("required", False)
        details.append(f"# {indent}- Required: {'Yes' if required else 'No'}")

        # Default value
        default = var_spec.get("default")
        if default is not None:
            details.extend(self._format_default_comment(default, indent))

        # Choices
        choices = var_spec.get("choices")
        if choices:
            formatted_choices = ", ".join(str(choice) for choice in choices)
            details.append(f"# {indent}- Choices: {formatted_choices}")

        # List elements
        elements = var_spec.get("elements")
        if elements:
            details.append(f"# {indent}- List elements: {elements}")

        # Nested options ("dict attributes"), see issue #21
        suboptions = var_spec.get("options")
        if suboptions and self.nested_options:
            if depth < COMMENT_MAX_NESTED_DEPTH:
                details.append(f"# {indent}- Dict attributes:")
                details.extend(self._format_suboptions(suboptions, depth + 1))
            else:
                details.append(
                    f"# {indent}- Dict attributes: (omitted at this nesting "
                    f"depth, see meta/argument_specs.yml)"
                )

        return details

    def _format_suboptions(self, options: dict[str, Any], depth: int = 1) -> list[str]:
        """Render nested option specs as indented comment bullets.

        Produces a compact block per attribute: the description on the
        bullet line (wrapped with hanging indent) followed by the same
        detail bullets used for top-level variables.
        """
        bullet_indent = "  " * (2 * depth - 1)
        detail_indent = f"{bullet_indent}  "
        lines: list[str] = []

        for name, spec in options.items():
            header = f"{bullet_indent}- {name}:"

            description = self._normalize_description(spec.get("description", ""))
            if description:
                width = max(78 - len(detail_indent), 30)
                wrapped = self._parse_and_format_description(
                    description, max_width=width
                )
                desc_lines = wrapped.split("\n")
                first_line = desc_lines[0]
                if first_line and len(f"{header} {first_line}") <= 78:
                    lines.append(f"# {header} {first_line}")
                    remaining = desc_lines[1:]
                else:
                    lines.append(f"# {header}")
                    remaining = desc_lines
                lines.extend(
                    f"# {detail_indent}{line}" if line else "#" for line in remaining
                )
            else:
                lines.append(f"# {header}")

            lines.extend(self._format_variable_details(spec, detail_indent, depth))

        return lines

    def _format_default_comment(self, default: Any, indent: str = "") -> list[str]:
        """Format a default value as one or more comment lines."""
        formatted_default = self._format_default_value(default)
        if "\n" not in formatted_default:
            return [f"# {indent}- Default: {formatted_default}"]

        return [
            f"# {indent}- Default:",
            *(
                f"# {indent}  {line}" if line else "#"
                for line in formatted_default.splitlines()
            ),
        ]

    def _format_default_value(self, default: Any) -> str:
        """Format default value for display in comments."""
        if default is None:
            return "N/A"
        elif isinstance(default, str):
            if default == "":
                return '""'
            return default
        elif isinstance(default, bool):
            return str(default).lower()
        elif isinstance(default, list | dict):
            if not default:  # Empty list or dict
                return "{}" if isinstance(default, dict) else "[]"
            return self._format_yaml_default_value(default)
        else:
            return str(default)

    def _format_yaml_default_value(self, default: list | dict) -> str:
        """Format compound defaults as block-style YAML."""
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.explicit_start = False
        yaml.indent(mapping=2, sequence=2, offset=0)
        yaml.width = 120

        output = StringIO()
        yaml.dump(default, output)
        return output.getvalue().strip()

    def _normalize_description(self, description: Any) -> str:
        """Normalize description to string format with improved formatting rules.

        Rules:
        - Single linebreaks in regular text become spaces
        - Two or more linebreaks become double newlines (\n\n)
        - Markdown lists are preserved
        - Markdown code blocks are preserved
        """
        text = normalize_description(description)
        if not text:
            return ""

        # Convert Ansible markup (C(...), O(...), ...) to Markdown first;
        # YAML comments follow Markdown conventions. Anchor links would
        # point nowhere in a defaults file, so no role options are passed.
        text = convert_ansible_markup(text, "markdown")

        return self._parse_and_format_description(text)

    def _parse_and_format_description(self, text: str, max_width: int = 0) -> str:
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
            max_width: Maximum line width for text wrapping. If 0, no wrapping is done.

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
                formatted_block = self._format_ast_node(
                    child, max_width, indent_level=0
                )
                if formatted_block:
                    result_parts.append(formatted_block)
                child = child.nxt

        # Join blocks with double newlines (paragraph separation)
        return "\n\n".join(result_parts).strip()

    def _wrap_text_line(self, text: str, max_width: int) -> list[str]:
        """Helper method to wrap a single line of text to specified width.

        Args:
            text: Text to wrap
            max_width: Maximum line width

        Returns:
            List of wrapped lines
        """
        if max_width <= 0 or len(text) <= max_width:
            return [text] if text else [""]

        words = self._split_markdown_words(text)
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

    def _split_markdown_words(self, text: str) -> list[str]:
        """Split text for wrapping without breaking Markdown links or code spans."""
        return re.findall(
            r"`[^`]+`(?:/`[^`]+`)+[.,;:!?)]*|"
            r"\[[^\]]+\]\([^)]+\)[.,;:!?)]*|"
            r"`[^`]+`[.,;:!?)]*|"
            r"\S+",
            text,
        )

    def _format_list_node(self, node, max_width: int = 0, indent_level: int = 0) -> str:
        """Format a list node with proper type recognition and nesting support.

        Args:
            node: CommonMark list AST node
            max_width: Maximum line width for wrapping
            indent_level: Current indentation level

        Returns:
            Properly formatted list with correct numbering and indentation
        """
        if not node.first_child:
            return ""

        list_items = []
        # Use 2 spaces per indentation level to match standard Markdown convention
        current_indent = "  " * indent_level

        # Determine list type and starting number from list_data
        list_data = getattr(node, "list_data", {})
        is_ordered = list_data.get("type") == "ordered"
        start_num = list_data.get("start", 1) if is_ordered else None
        # Preserve original bullet character from AST
        bullet_char = list_data.get("bullet_char", "-")

        item_num = start_num if start_num else 1
        item = node.first_child

        while item:
            if item.t == "item":
                # Format the list item with proper prefix using original bullet char
                if is_ordered:
                    item_prefix = f"{item_num}. "
                    item_num += 1
                else:
                    item_prefix = f"{bullet_char} "

                # Format the content of this list item
                item_content = self._format_list_item_content(
                    item, max_width, indent_level, item_prefix
                )

                if item_content:
                    # Apply current indentation to all lines
                    item_lines = item_content.split("\n")
                    for i, line in enumerate(item_lines):
                        if i == 0:
                            # First line gets current indent + formatted line
                            list_items.append(f"{current_indent}{line}")
                        elif line.strip():
                            # Check if already properly indented from nesting
                            if current_indent and line.startswith(current_indent):
                                # Already has proper base indentation
                                list_items.append(line)
                            else:
                                # Determine if we're inside a code block
                                in_code_block = False
                                for prev_idx in range(i):
                                    prev_line = item_lines[prev_idx].strip()
                                    if prev_line.startswith("```"):
                                        in_code_block = not in_code_block

                                stripped = line.strip()
                                if stripped.startswith("```") or in_code_block:
                                    # Code blocks get content alignment
                                    continuation_indent = current_indent + (
                                        " " * len(item_prefix)
                                    )
                                    list_items.append(f"{continuation_indent}{line}")
                                else:
                                    # Regular continuation line alignment
                                    continuation_indent = current_indent + (
                                        " " * len(item_prefix)
                                    )
                                    list_items.append(f"{continuation_indent}{line}")
                        else:
                            # Empty lines
                            list_items.append("")

            item = item.nxt

        return "\n".join(list_items)

    def _format_list_item_content(
        self,
        item_node,
        max_width: int = 0,
        indent_level: int = 0,
        item_prefix: str = "",
    ) -> str:
        """Format the content of a single list item.

        Args:
            item_node: List item AST node
            max_width: Maximum line width for wrapping
            indent_level: Current indentation level
            item_prefix: The list marker prefix ("- " or "1. " etc.)

        Returns:
            Formatted content for this list item
        """
        if not item_node.first_child:
            return f"{item_prefix}"

        content_parts = []
        child = item_node.first_child

        while child:
            if child.t == "paragraph":
                # Format paragraph content
                # Adjust max_width to account for the indentation that will be added
                # Base indentation (2 spaces per level) + list prefix alignment
                base_indent = 2 * indent_level
                # For continuation lines, we need space for prefix alignment
                continuation_indent = base_indent + len(item_prefix)
                # Ensure we don't exceed the target width when indented
                adjusted_width = max_width - continuation_indent if max_width > 0 else 0
                if adjusted_width <= 0 and max_width > 0:
                    adjusted_width = max_width // 2  # Fallback for very deep nesting
                formatted = self._format_ast_node(child, adjusted_width, indent_level)
                if formatted:
                    content_parts.append(formatted)
            elif child.t == "list":
                # Nested list - increase indentation level
                formatted = self._format_ast_node(child, max_width, indent_level + 1)
                if formatted:
                    content_parts.append(formatted)
            else:
                # Other content (code blocks, etc.)
                formatted = self._format_ast_node(child, max_width, indent_level)
                if formatted:
                    content_parts.append(formatted)

            child = child.nxt

        if not content_parts:
            return f"{item_prefix}"

        # Join content with proper line breaks
        if len(content_parts) == 1 and "\n" not in content_parts[0]:
            # Simple single-line content
            return f"{item_prefix}{content_parts[0]}"
        else:
            # Multi-part or multi-line content
            result_lines = []

            # Add the first part with the item prefix
            if content_parts:
                if content_parts[0]:
                    result_lines.append(f"{item_prefix}{content_parts[0]}")
                else:
                    result_lines.append(item_prefix)
            else:
                result_lines.append(item_prefix)

            # Add remaining parts (like nested lists)
            for part in content_parts[1:]:
                if part:
                    # Don't add blank line for nested lists - they should be connected
                    part_lines = part.split("\n")
                    result_lines.extend(part_lines)

            return "\n".join(result_lines)

    def _format_ast_node(self, node, max_width: int = 0, indent_level: int = 0) -> str:
        """Format a single AST node based on its type with optional text wrapping.

        Args:
            node: CommonMark AST node
            max_width: Maximum line width for text wrapping. If 0, no wrapping is done.
            indent_level: Current indentation level for nested content

        Returns:
            Formatted text for this node
        """
        if node.t == "paragraph":
            # For paragraphs, join inline content and convert softbreaks to spaces
            result = self._format_inline_content(node)
            cleaned_text = " ".join(result.split())

            # Apply text wrapping if max_width is specified
            if max_width > 0:
                wrapped_lines = self._wrap_text_line(cleaned_text, max_width)
                return "\n".join(wrapped_lines)
            else:
                return cleaned_text
        elif node.t == "list":
            # For lists, respect the AST list type and nesting
            return self._format_list_node(node, max_width, indent_level)
        elif node.t == "code_block":
            # For code blocks, preserve content exactly including language info
            # and preserve existing indentation in the code content
            language_info = node.info or ""
            code_content = node.literal or ""

            # Split code into lines and preserve existing indentation
            code_lines = code_content.rstrip().split("\n")

            # Build the code block with proper formatting
            result_lines = [f"```{language_info}"]
            result_lines.extend(code_lines)
            result_lines.append("```")

            return "\n".join(result_lines)
        elif node.t == "heading":
            # For headings, format as plain text (shouldn't occur in descriptions)
            result = self._format_inline_content(node)
            cleaned_text = " ".join(result.split())

            # Apply text wrapping if max_width is specified
            if max_width > 0:
                wrapped_lines = self._wrap_text_line(cleaned_text, max_width)
                return "\n".join(wrapped_lines)
            else:
                return cleaned_text
        else:
            # For other block types, format as paragraph
            result = self._format_inline_content(node)
            cleaned_text = " ".join(result.split())

            # Apply text wrapping if max_width is specified
            if max_width > 0:
                wrapped_lines = self._wrap_text_line(cleaned_text, max_width)
                return "\n".join(wrapped_lines)
            else:
                return cleaned_text

    def _format_inline_content(self, node) -> str:
        """Format inline CommonMark nodes while preserving Markdown links."""
        text_parts = []
        child = node.first_child

        while child:
            if child.t == "text":
                text_parts.append(child.literal or "")
            elif child.t == "softbreak":
                text_parts.append(" ")
            elif child.t == "code":
                text_parts.append(f"`{child.literal or ''}`")
            elif child.t == "linebreak":
                text_parts.append("\n")
            elif child.t == "link":
                label = self._format_inline_content(child)
                destination = child.destination or ""
                title = child.title or ""
                if label == destination and not title:
                    # Autolink (<url> or bare URL): keep it a plain URL
                    # instead of a noisy [url](url) construct
                    text_parts.append(destination)
                else:
                    escaped_title = title.replace('"', '\\"')
                    title_suffix = f' "{escaped_title}"' if title else ""
                    text_parts.append(f"[{label}]({destination}{title_suffix})")
            elif child.t == "emph":
                text_parts.append(f"*{self._format_inline_content(child)}*")
            elif child.t == "strong":
                text_parts.append(f"**{self._format_inline_content(child)}**")
            else:
                text_parts.append(child.literal or self._format_inline_content(child))

            child = child.nxt

        return "".join(text_parts)

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
            readme_path.write_text(updated_content, encoding="utf-8", newline="\n")
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
        return re.sub(
            pattern,
            lambda match: f"{match.group(1)}\n{new_content}\n{match.group(2)}",
            content,
            flags=re.DOTALL,
        )

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

..REUSE-IgnoreStart
Copyright (c) [FIXME YYYY Your Name]

[FIXME Adapt license:
This project is licensed under the GNU General Public License v3.0 or later
(SPDX-License-Identifier: ``GPL-3.0-or-later``)].
..REUSE-IgnoreEnd


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

<!--REUSE-IgnoreStart-->
Copyright (c) [FIXME YYYY Your Name]

[FIXME Adapt license:
This project is licensed under the GNU General Public License v3.0 or later
(SPDX-License-Identifier: `GPL-3.0-or-later`)].
<!--REUSE-IgnoreEnd-->


## Author information

This project was created and is maintained by [FIXME Your Name].

"""
