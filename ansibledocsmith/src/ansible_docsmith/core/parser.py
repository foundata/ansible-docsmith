"""Parser for Ansible argument_specs.yml files."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .exceptions import ParseError, ValidationError


class ArgumentSpecParser:
    """Parser for argument_specs.yml with validation."""

    def __init__(self):
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.explicit_start = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def parse_file(self, file_path: Path) -> dict[str, Any]:
        """Parse argument_specs.yml file with comprehensive error handling."""

        try:
            with open(file_path, encoding="utf-8") as file:
                data = self.yaml.load(file)

            if not data:
                raise ParseError(f"Empty or invalid YAML file: {file_path}")

            if "argument_specs" not in data:
                raise ParseError(f"Missing 'argument_specs' key in {file_path}")

            return self._normalize_specs(data["argument_specs"])

        except FileNotFoundError:
            raise ParseError(f"File not found: {file_path}")
        except YAMLError as e:
            raise ParseError(f"YAML parsing error in {file_path}: {e}")
        except Exception as e:
            raise ParseError(f"Unexpected error parsing {file_path}: {e}")

    def _normalize_specs(self, specs: dict[str, Any]) -> dict[str, Any]:
        """Normalize and validate argument specs structure."""

        normalized = {}

        for entry_point, spec in specs.items():
            if not isinstance(spec, dict):
                raise ValidationError(
                    f"Entry point '{entry_point}' must be a dictionary"
                )

            normalized[entry_point] = {
                "short_description": spec.get("short_description", ""),
                "description": self._normalize_description(spec.get("description", [])),
                "author": self._normalize_author(spec.get("author", [])),
                "version_added": spec.get("version_added", ""),
                "seealso": spec.get("seealso", []),
                "todo": spec.get("todo", []),
                "options": self._normalize_options(spec.get("options", {})),
            }

        return normalized

    def _normalize_description(self, description: Any) -> str:
        """Normalize description to string format."""
        if isinstance(description, list):
            return "\n".join(str(item) for item in description)
        return str(description) if description else ""

    def _normalize_author(self, author: Any) -> list[str]:
        """Normalize author to list format."""
        if isinstance(author, str):
            return [author]
        elif isinstance(author, list):
            return [str(item) for item in author]
        return []

    def _normalize_options(self, options: dict[str, Any]) -> dict[str, Any]:
        """Normalize options with full parameter specifications."""

        normalized = {}

        for param_name, param_spec in options.items():
            if not isinstance(param_spec, dict):
                raise ValidationError(f"Parameter '{param_name}' must be a dictionary")

            normalized[param_name] = {
                "type": param_spec.get("type", "str"),
                "required": param_spec.get("required", False),
                "default": param_spec.get("default"),
                "description": param_spec.get("description", ""),
                "choices": param_spec.get("choices", []),
                "elements": param_spec.get("elements"),
                "options": self._normalize_options(param_spec.get("options", {})),
                "version_added": param_spec.get("version_added"),
            }

        return normalized

    def validate_structure(self, role_path: Path) -> dict[str, Any]:
        """Validate role structure and return metadata."""

        # Check for required directories
        required_dirs = ["meta"]
        for dir_name in required_dirs:
            dir_path = role_path / dir_name
            if not dir_path.exists():
                raise ValidationError(f"Required directory missing: {dir_path}")

        # Find argument_specs file
        spec_file = None
        for ext in ["yml", "yaml"]:
            candidate = role_path / "meta" / f"argument_specs.{ext}"
            if candidate.exists():
                spec_file = candidate
                break

        if not spec_file:
            raise ValidationError("No argument_specs.yml found in meta/ directory")

        # Parse and validate specs
        specs = self.parse_file(spec_file)

        # Additional validation
        if not specs:
            raise ValidationError("No entry points defined in argument_specs.yml")

        # Check for main entry point
        if "main" not in specs:
            raise ValidationError("Missing 'main' entry point in argument_specs.yml")

        return {
            "specs": specs,
            "spec_file": spec_file,
            "role_name": role_path.name,
            "role_path": role_path,
        }
