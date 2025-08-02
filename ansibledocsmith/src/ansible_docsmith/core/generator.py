"""Documentation generators for Markdown and YAML comments."""

import re
from pathlib import Path
from typing import Any
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .exceptions import TemplateError, FileOperationError
from ..templates import TemplateManager


class DocumentationGenerator:
    """Generate Markdown documentation from argument specs."""

    def __init__(self, template_dir: Path | None = None, template_name: str = "default"):
        """Initialize the documentation generator.

        Args:
            template_dir: Custom template directory. If None, uses built-in templates.
            template_name: Name of the template to use (default: "default")
        """
        self.template_manager = TemplateManager(template_dir)
        self.template_name = template_name

        # Add custom filters to the Jinja environment
        self.template_manager.add_filter('ansible_escape', self._ansible_escape_filter)
        self.template_manager.add_filter('code_escape', self._code_escape_filter)
        self.template_manager.add_filter('format_default', self._format_default_filter)
        self.template_manager.add_filter('format_description', self._format_description_filter)
        self.template_manager.add_filter('format_table_description', self._format_table_description_filter)

    def generate_role_documentation(
        self,
        specs: dict[str, Any],
        role_name: str,
        role_path: Path
    ) -> str:
        """Generate complete role documentation."""

        try:
            # Prepare context data
            main_spec = specs.get('main', {})
            context = {
                'role_name': role_name,
                'role_path': role_path,
                'specs': specs,
                'main_spec': main_spec,
                'entry_points': list(specs.keys()),
                'options': main_spec.get('options', {}),
                'has_options': bool(main_spec.get('options', {}))
            }

            # Render template using template manager
            return self.template_manager.render_template(
                self.template_name,
                "readme",
                **context
            )

        except Exception as e:
            raise TemplateError(f"Failed to generate documentation: {e}")


    def _ansible_escape_filter(self, value: Any) -> str:
        """Escape Ansible variable syntax for Markdown."""
        if value is None:
            return 'N/A'
        value_str = str(value)
        return value_str.replace('{{', '\\{\\{').replace('}}', '\\}\\}')

    def _code_escape_filter(self, value: Any) -> str:
        """Escape code for Markdown code blocks."""
        if value is None:
            return 'N/A'
        value_str = str(value)
        escaped = value_str.replace("`", "\\`").replace("|", "\\|")
        return f'`{escaped}`'

    def _format_default_filter(self, value: Any) -> str:
        """Format default values for display."""
        if value is None:
            return 'N/A'
        elif isinstance(value, str):
            return f'`"{value}"`'
        elif isinstance(value, bool):
            return f'`{str(value).lower()}`'
        elif isinstance(value, (list, dict)):
            return f'`{value}`'
        else:
            return f'`{value}`'

    def _format_description_filter(self, description: Any) -> str:
        """Format description for README display, handling both strings and lists."""
        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation in markdown
            return '\n\n'.join(str(item).strip() for item in description if str(item).strip())
        return str(description).strip() if description else ''

    def _format_table_description_filter(self, description: Any) -> str:
        """Format description for table display, joining multiple paragraphs with space."""
        if isinstance(description, list):
            # Join list items with space for table display (single line)
            return ' '.join(str(item).strip() for item in description if str(item).strip())
        return str(description).strip() if description else ''


class DefaultsCommentGenerator:
    """Add block comments above variables in defaults/main.yml from argument specs."""

    def __init__(self):
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.explicit_start = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def add_comments(
        self,
        defaults_path: Path,
        specs: dict[str, Any]
    ) -> str | None:
        """Add block comments above variables in defaults file."""

        if not defaults_path.exists():
            return None

        try:
            # Read the original file as text
            with open(defaults_path, 'r', encoding='utf-8') as file:
                original_content = file.read()

            # Parse YAML to validate and get variable names
            data = self.yaml.load(original_content)
            if not data:
                return None

            # Get main spec options
            main_spec = specs.get('main', {})
            options = main_spec.get('options', {})

            # Clean the file first - remove all existing variable comments
            cleaned_content = self._remove_existing_variable_comments(original_content, options)

            # Process the cleaned file line by line to insert new comments
            lines = cleaned_content.splitlines()
            result_lines = []

            for line in lines:
                # Check if this line defines a variable
                variable_match = self._get_variable_from_line(line)

                if variable_match and variable_match in options:
                    var_spec = options[variable_match]
                    description = var_spec.get('description', '')

                    if description:
                        # Generate block comment
                        comment_lines = self._format_block_comment(description)

                        # Add blank line before comment (if previous line isn't blank)
                        if result_lines and result_lines[-1].strip():
                            result_lines.append('')

                        # Add comment lines
                        result_lines.extend(comment_lines)

                    # Clean any inline comments from the variable line
                    line = self._remove_inline_comment(line)

                # Add the original line
                result_lines.append(line)

            return '\n'.join(result_lines) + '\n'

        except YAMLError as e:
            raise FileOperationError(f"Failed to parse {defaults_path}: {e}")
        except Exception as e:
            raise FileOperationError(f"Failed to add comments: {e}")

    def _get_variable_from_line(self, line: str) -> str | None:
        """Extract variable name from a YAML line."""
        # Match lines like "var_name:" or "var_name: value"
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:', line.strip())
        return match.group(1) if match else None

    def _format_block_comment(self, description: Any) -> list[str]:
        """Format description as block comment with proper line wrapping."""
        # Normalize description to handle both string and list formats
        text = self._normalize_description(description)

        # Split into paragraphs
        paragraphs = text.split('\n\n') if '\n\n' in text else text.split('\n')

        comment_lines = []

        for i, paragraph in enumerate(paragraphs):
            if i > 0:  # Add blank comment line between paragraphs
                comment_lines.append('#')

            # Wrap paragraph to 80 chars (minus "# " prefix)
            wrapped_lines = self._wrap_text(paragraph.strip(), max_width=78)

            for wrapped_line in wrapped_lines:
                comment_lines.append(f'# {wrapped_line}' if wrapped_line else '#')

        return comment_lines

    def _normalize_description(self, description: Any) -> str:
        """Normalize description to string format, handling both strings and lists."""
        if isinstance(description, list):
            # Join list items with double newlines for paragraph separation
            return '\n\n'.join(str(item).strip() for item in description if str(item).strip())
        return str(description).strip() if description else ''

    def _wrap_text(self, text: str, max_width: int = 78) -> list[str]:
        """Wrap text to specified width, preserving word boundaries."""
        if not text:
            return ['']

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            # Check if adding this word would exceed the limit
            word_length = len(word)
            space_length = 1 if current_line else 0

            if current_length + space_length + word_length <= max_width:
                current_line.append(word)
                current_length += space_length + word_length
            else:
                # Start a new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length

        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))

        return lines if lines else ['']

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
        """Remove inline comments from a YAML line, preserving the variable definition."""
        # Match variable definitions and remove everything after the first # (but preserve quoted strings)
        if ':' in line:
            # Simple approach: find # that's not inside quotes
            in_quotes = False
            quote_char = None

            for i, char in enumerate(line):
                if char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif char == '#' and not in_quotes:
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
            if line.strip().startswith('#'):
                # Look ahead to see if there's a variable definition soon
                j = i + 1
                found_variable = False

                # Skip other comment lines and blank lines
                while j < len(lines) and (lines[j].strip().startswith('#') or not lines[j].strip()):
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

        return '\n'.join(result_lines)


class ReadmeUpdater:
    """Update README.md files with generated content."""

    def __init__(self,
                 start_marker: str = "<!-- BEGIN ANSIBLE DOCSMITH -->",
                 end_marker: str = "<!-- END ANSIBLE DOCSMITH -->"):
        self.start_marker = start_marker
        self.end_marker = end_marker

    def update_readme(self, readme_path: Path, new_content: str) -> bool:
        """Update content between markers in README.md."""

        try:
            if readme_path.exists():
                content = readme_path.read_text(encoding='utf-8')
                updated_content = self._replace_between_markers(content, new_content)
            else:
                # Create new README with template
                updated_content = self._create_new_readme(new_content, readme_path.parent.name)

            readme_path.write_text(updated_content, encoding='utf-8')
            return True

        except Exception as e:
            raise FileOperationError(f"Failed to update README: {e}")

    def _replace_between_markers(self, content: str, new_content: str) -> str:
        """Replace content between markers."""

        if self.start_marker not in content or self.end_marker not in content:
            # Add markers and content at the end
            return content + f"\n\n{self.start_marker}\n{new_content}\n{self.end_marker}\n"

        # Replace content between existing markers
        pattern = f"({re.escape(self.start_marker)}).*?({re.escape(self.end_marker)})"
        replacement = f"\\1\n{new_content}\n\\2"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)

    def _create_new_readme(self, role_content: str, role_name: str) -> str:
        """Create a new README with basic template."""
        return f"""# {role_name}

TODO: Add role description here.

{self.start_marker}
{role_content}
{self.end_marker}

## License

GPL-3.0-or-later

## Author Information

This role was created by [Your Name].
"""
