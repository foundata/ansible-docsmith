"""Generator for block comments in entry-point files like defaults/main.yml."""

import re
from io import StringIO
from pathlib import Path
from typing import Any

from markdown_it.tree import SyntaxTreeNode
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.tokens import ScalarToken

from ..constants import COMMENT_MAX_NESTED_DEPTH
from .exceptions import FileOperationError
from .markdown_ast import parse_markdown
from .markup import convert_ansible_markup
from .text import normalize_description

# Total line budget for generated comment lines, including the "# "
# prefix. Descriptions are wrapped to the same budget (max_width=78).
COMMENT_LINE_LENGTH = 80
MISSING_START = "# ANSIBLE DOCSMITH MISSING START"
MISSING_END = "# ANSIBLE DOCSMITH MISSING END"


class DefaultsCommentGenerator:
    """Add block comments above variables in entry-point files from argument specs."""

    def __init__(self, nested_options: bool = True, include_missing: bool = False):
        """Initialize the comment generator.

        Args:
            nested_options: Whether to document nested options ("dict
                attributes") of a variable inside its comment block.
            include_missing: Document absent options without a spec default.
        """
        self.nested_options = nested_options
        self.include_missing = include_missing
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.explicit_start = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def add_comments(self, defaults_path: Path, specs: dict[str, Any]) -> str | None:
        """Add block comments above variables in defaults file."""
        try:
            original = (
                defaults_path.read_text(encoding="utf-8")
                if defaults_path.exists()
                else None
            )
            return self.build_updated_content(original, specs)
        except (OSError, FileOperationError) as error:
            raise FileOperationError(
                f"Failed to update {defaults_path}: {error}"
            ) from error

    def build_updated_content(
        self, original: str | None, specs: dict[str, Any]
    ) -> str | None:
        """Prepare comments without writing; missing-option selection needs raw specs.

        Return None when there is no applicable output. An empty string means
        an existing section was removed from an otherwise empty file.
        """
        try:
            content, had_section = self._remove_missing_section(original or "")
            data = self.yaml.load(content)
            if data is not None and not isinstance(data, dict):
                raise FileOperationError("Defaults must contain a YAML mapping")
            if not data and not self.include_missing and not had_section:
                return None

            entry_point_spec = next(iter(specs.values()))
            options = entry_point_spec.get("options", {})
            updated = self._add_existing_comments(content, options) if data else content

            if self.include_missing:
                missing = {
                    name: spec
                    for name, spec in options.items()
                    if name not in (data or {}) and "default" not in spec
                }
                if missing:
                    if original is None:
                        updated = "---\n"
                    elif updated and not updated.endswith("\n"):
                        updated += "\n"
                    # A blank separator could extend a preceding |+ or >+ scalar.
                    updated += self._format_missing_section(missing)
            if original is None and not updated:
                return None
            if self.include_missing or had_section:
                self._remove_missing_section(updated)
                if self._yaml_value_signature(
                    original or ""
                ) != self._yaml_value_signature(updated):
                    raise FileOperationError(
                        "Comment generation would change defaults values"
                    )
            return updated

        except YAMLError as e:
            raise FileOperationError(f"Failed to parse defaults: {e}") from e

    def _yaml_value_signature(self, content: str) -> str:
        # Compare values and tags, including !vault, without comment metadata.
        yaml = YAML(typ="safe")
        node = yaml.compose(content)
        if node is None or node.tag == "tag:yaml.org,2002:null":
            return ""
        stream = StringIO()
        yaml.serialize(node, stream)
        return stream.getvalue()

    def _remove_missing_section(self, content: str) -> tuple[str, bool]:
        lines = content.splitlines(keepends=True)
        starts = [
            i for i, line in enumerate(lines) if line.rstrip("\r\n") == MISSING_START
        ]
        ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == MISSING_END]
        if not starts and not ends:
            return content, False
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise FileOperationError("Expected one ordered pair of MISSING markers")
        start, end = starts[0], ends[0]
        if any(
            line.strip() and not line.lstrip().startswith("#")
            for line in lines[start + 1 : end]
        ):
            raise FileOperationError(
                "MISSING section must contain only comments; "
                "move assignments outside the markers"
            )
        return "".join(lines[:start] + lines[end + 1 :]), True

    def _format_missing_section(self, options: dict[str, Any]) -> str:
        lines = [
            MISSING_START,
            "#",
            "# The following variables have no default values. They are documented",
            "# here as comments for easier discovery:",
            "#",
        ]
        for name, spec in options.items():
            if not isinstance(name, str) or not re.fullmatch(
                r"[a-zA-Z_][a-zA-Z0-9_]*", name
            ):
                raise FileOperationError(f"Invalid missing variable name: {name!r}")
            lines.extend(self._format_block_comment(spec))
            lines.extend([f"# {name}:", "#"])
        lines.append(MISSING_END)
        return "\n".join(lines) + "\n"

    def _add_existing_comments(self, content: str, options: dict[str, Any]) -> str:
        cleaned_content = self._remove_existing_variable_comments(content, options)
        scalar_ends = {
            token.end_mark.line
            for token in self.yaml.scan(cleaned_content)
            if isinstance(token, ScalarToken) and token.style in {"|", ">"}
        }
        result_lines: list[str] = []
        # Cleanup has already removed the final line terminator, not blank lines.
        for index, line in enumerate(cleaned_content.split("\n")):
            variable = self._get_variable_from_line(line)
            if variable and variable in options:
                var_spec = options[variable]
                if var_spec.get("description"):
                    if (
                        result_lines
                        and result_lines[-1].strip()
                        and index not in scalar_ends
                    ):
                        result_lines.append("")
                    result_lines.extend(self._format_block_comment(var_spec))
                line = self._remove_inline_comment(line)
            result_lines.append(line)
        return "\n".join(result_lines) + "\n"

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

        # Sensitive (no_log)
        if var_spec.get("no_log"):
            details.append(
                f"# {indent}- Sensitive: Yes (no_log, values are masked in logs)"
            )

        # Default value
        default = var_spec.get("default")
        if default is not None:
            details.extend(self._format_default_comment(default, indent))

        # Choices
        choices = var_spec.get("choices")
        if choices:
            formatted_choices = ", ".join(str(choice) for choice in choices)
            details.extend(
                self._wrap_detail_bullet("Choices", formatted_choices, indent)
            )

        # Aliases
        aliases = var_spec.get("aliases")
        if aliases:
            formatted_aliases = ", ".join(str(alias) for alias in aliases)
            details.extend(
                self._wrap_detail_bullet("Aliases", formatted_aliases, indent)
            )

        # List elements
        elements = var_spec.get("elements")
        if elements:
            details.extend(
                self._wrap_detail_bullet("List elements", str(elements), indent)
            )

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

    def _wrap_detail_bullet(self, label: str, text: str, indent: str) -> list[str]:
        """Wrap a '# {indent}- {label}: {text}' bullet at the line budget.

        Continuation lines align below the bullet content. A single token
        longer than the remaining budget (like a long URL) stays on its
        own line rather than being cut.
        """
        first_prefix = f"# {indent}- {label}: "
        cont_prefix = f"# {indent}  "

        if len(first_prefix) + len(text) <= COMMENT_LINE_LENGTH:
            return [f"{first_prefix}{text}"]

        wrapped: list[str] = []
        current = ""
        capacity = COMMENT_LINE_LENGTH - len(first_prefix)
        for word in text.split():
            candidate = f"{current} {word}" if current else word
            if len(candidate) <= capacity or not current:
                current = candidate
            else:
                wrapped.append(current)
                current = word
                capacity = COMMENT_LINE_LENGTH - len(cont_prefix)
        if current:
            wrapped.append(current)

        return [f"{first_prefix}{wrapped[0]}"] + [
            f"{cont_prefix}{line}" for line in wrapped[1:]
        ]

    def _format_default_comment(self, default: Any, indent: str = "") -> list[str]:
        """Format a default value as one or more comment lines."""
        formatted_default = self._format_default_value(default)
        if "\n" not in formatted_default:
            return self._wrap_detail_bullet("Default", formatted_default, indent)

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

    def _format_yaml_default_value(self, default: list[Any] | dict[str, Any]) -> str:
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
        """Parse description as Markdown and apply enhanced formatting rules.

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

        # Parse the markdown text and convert the AST back to formatted text
        result_parts = []
        for child in parse_markdown(text).children:
            formatted_block = self._format_ast_node(child, max_width, indent_level=0)
            if formatted_block:
                result_parts.append(formatted_block)

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
        current_line: list[str] = []
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

    def _format_list_node(
        self, node: SyntaxTreeNode, max_width: int = 0, indent_level: int = 0
    ) -> str:
        """Format a list node with proper type recognition and nesting support.

        Args:
            node: CommonMark list AST node
            max_width: Maximum line width for wrapping
            indent_level: Current indentation level

        Returns:
            Properly formatted list with correct numbering and indentation
        """
        if not node.children:
            return ""

        list_items = []
        # Use 2 spaces per indentation level to match standard Markdown convention
        current_indent = "  " * indent_level

        # Determine list type and starting number. The "start" attribute is
        # only present when the list does not start at 1.
        is_ordered = node.type == "ordered_list"
        start_num = int(node.attrs.get("start", 1)) if is_ordered else None
        # Preserve original bullet character from the AST
        bullet_char = node.markup or "-"

        item_num = start_num if start_num else 1

        for item in node.children:
            if item.type == "list_item":
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

        return "\n".join(list_items)

    def _format_list_item_content(
        self,
        item_node: SyntaxTreeNode,
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
        if not item_node.children:
            return f"{item_prefix}"

        content_parts = []

        for child in item_node.children:
            if child.type == "paragraph":
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
            elif child.type in ("bullet_list", "ordered_list"):
                # Nested list - increase indentation level
                formatted = self._format_ast_node(child, max_width, indent_level + 1)
                if formatted:
                    content_parts.append(formatted)
            else:
                # Other content (code blocks, etc.)
                formatted = self._format_ast_node(child, max_width, indent_level)
                if formatted:
                    content_parts.append(formatted)

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

    def _format_ast_node(
        self, node: SyntaxTreeNode, max_width: int = 0, indent_level: int = 0
    ) -> str:
        """Format a single AST node based on its type with optional text wrapping.

        Args:
            node: CommonMark AST node
            max_width: Maximum line width for text wrapping. If 0, no wrapping is done.
            indent_level: Current indentation level for nested content

        Returns:
            Formatted text for this node
        """
        if node.type == "paragraph":
            # For paragraphs, join inline content and convert softbreaks to spaces
            result = self._format_inline_content(node)
            cleaned_text = " ".join(result.split())

            # Apply text wrapping if max_width is specified
            if max_width > 0:
                wrapped_lines = self._wrap_text_line(cleaned_text, max_width)
                return "\n".join(wrapped_lines)
            else:
                return cleaned_text
        elif node.type in ("bullet_list", "ordered_list"):
            # For lists, respect the AST list type and nesting
            return self._format_list_node(node, max_width, indent_level)
        elif node.type == "blockquote":
            # Preserve block quotes: format the quoted blocks with a
            # reduced width, then prefix every line with "> " (empty
            # separator lines between quoted paragraphs become ">")
            inner_width = max_width - 2 if max_width > 0 else 0
            quoted_parts = []
            for child in node.children:
                formatted = self._format_ast_node(child, inner_width, indent_level)
                if formatted:
                    quoted_parts.append(formatted)
            lines: list[str] = []
            for index, part in enumerate(quoted_parts):
                if index:
                    lines.append(">")
                lines.extend(f"> {line}" if line else ">" for line in part.split("\n"))
            return "\n".join(lines)
        elif node.type in ("fence", "code_block"):
            # For code blocks (fenced or indented), preserve content exactly
            # including language info and existing indentation; always
            # re-emit as a fenced block
            language_info = node.info or ""
            code_content = node.content or ""

            # Split code into lines and preserve existing indentation
            code_lines = code_content.rstrip().split("\n")

            # Build the code block with proper formatting
            result_lines = [f"```{language_info}"]
            result_lines.extend(code_lines)
            result_lines.append("```")

            return "\n".join(result_lines)
        elif node.type == "heading":
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
            # For other block types (blockquotes, HTML blocks, ...), flatten
            # to the inline text of their children
            result = self._format_inline_content(node)
            cleaned_text = " ".join(result.split())

            # Apply text wrapping if max_width is specified
            if max_width > 0:
                wrapped_lines = self._wrap_text_line(cleaned_text, max_width)
                return "\n".join(wrapped_lines)
            else:
                return cleaned_text

    def _format_inline_content(self, node: SyntaxTreeNode) -> str:
        """Format inline Markdown nodes while preserving Markdown links."""
        text_parts = []

        for child in node.children:
            if child.type == "inline":
                # Container for the actual inline parts (paragraphs and
                # headings wrap their content in one of these)
                text_parts.append(self._format_inline_content(child))
            elif child.type == "text":
                text_parts.append(child.content)
            elif child.type == "text_special":
                # Backslash escapes keep their original source form so
                # that e.g. "\*literal asterisks\*" cannot be mistaken
                # for emphasis markers; entities render as their character
                text_parts.append(
                    child.markup if child.info == "escape" else child.content
                )
            elif child.type == "softbreak":
                text_parts.append(" ")
            elif child.type == "code_inline":
                text_parts.append(f"`{child.content}`")
            elif child.type == "hardbreak":
                text_parts.append("\n")
            elif child.type == "link":
                label = self._format_inline_content(child)
                destination = str(child.attrs.get("href", ""))
                title = str(child.attrs.get("title") or "")
                if label == destination and not title:
                    # Autolink (<url> or bare URL): keep it a plain URL
                    # instead of a noisy [url](url) construct
                    text_parts.append(destination)
                else:
                    escaped_title = title.replace('"', '\\"')
                    title_suffix = f' "{escaped_title}"' if title else ""
                    text_parts.append(f"[{label}]({destination}{title_suffix})")
            elif child.type == "em":
                text_parts.append(f"*{self._format_inline_content(child)}*")
            elif child.type == "strong":
                text_parts.append(f"**{self._format_inline_content(child)}**")
            else:
                # Unknown inline content (inline HTML, images, ...): emit its
                # raw content, or flatten its children if it has no content
                text_parts.append(child.content or self._format_inline_content(child))

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

    def _remove_existing_variable_comments(
        self, content: str, options: dict[str, Any]
    ) -> str:
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
