"""Generator for block comments in entry-point files like defaults/main.yml."""

import re
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..constants import COMMENT_MAX_NESTED_DEPTH
from .exceptions import FileOperationError
from .markup import convert_ansible_markup
from .text import normalize_description


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
