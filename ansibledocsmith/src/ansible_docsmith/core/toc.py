"""Table of Contents generators for Markdown and reStructuredText."""

import re
from abc import ABC, abstractmethod
from typing import Any

from .markdown_ast import parse_markdown


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
        """Extract headings from markdown content using the Markdown AST.

        Uses AST parsing to avoid false positives from code blocks or other
        contexts where '#' characters might appear but aren't actually headings.

        Returns:
            List of heading dictionaries with 'text', 'level', and 'anchor' keys
        """
        if not content.strip():
            return []

        try:
            headings = []
            root = parse_markdown(content)

            for node in root.walk():
                if node.type != "heading":
                    continue

                # The tag is "h1".."h6" for both ATX and setext headings
                level = int(node.tag[1])
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

            return headings

        except Exception:
            # Fallback to regex-based extraction if AST parsing fails
            return self._extract_headings_fallback(content)

    def _extract_text_from_node(self, node) -> str:
        """Extract text from a Markdown AST node preserving inline formatting.

        Inline code keeps its backticks to maintain the original heading
        text appearance. Inline HTML (like the ``<a id="..."></a>`` anchors
        DocSmith generates) is emitted verbatim so that the caller can
        detect existing anchors.

        Args:
            node: Markdown AST node (SyntaxTreeNode)

        Returns:
            Text content with inline formatting preserved
        """
        text_parts = []

        for current_node in node.walk():
            if current_node.type == "code_inline":
                # For inline code, add backticks to preserve formatting
                text_parts.append(f"`{current_node.content}`")
            elif current_node.type in ("text", "html_inline"):
                text_parts.append(current_node.content)

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
