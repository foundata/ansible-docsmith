"""Project configuration discovery and validation."""

import math
import string
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError

CONFIG_NAMES = ("ansible-docsmith.toml", ".ansible-docsmith.toml")


@dataclass(frozen=True)
class MarkdownFormatterConfig:
    """An explicitly configured external formatter."""

    command: tuple[str, ...]
    config_path: Path
    mode: str = "stdin"
    timeout_seconds: float = 30


@dataclass(frozen=True)
class GenerateConfig:
    """Defaults for the generate command."""

    readme: bool = True
    defaults: bool = True
    defaults_comments_nested: bool = True
    readme_toc_list_bulletpoints: str = "auto"
    template_readme: Path | None = None
    dry_run: bool = False
    check: bool = False
    markdown_formatter: bool = True


@dataclass(frozen=True)
class ValidateConfig:
    """Defaults for the validate command."""

    readme: bool = True
    argument_specs: bool = True
    strict: bool = False


@dataclass(frozen=True)
class ProjectConfig:
    """One authoritative configuration, without inherited settings."""

    path: Path | None = None
    format: str = "auto"
    verbose: bool = False
    generate: GenerateConfig = field(default_factory=GenerateConfig)
    validate: ValidateConfig = field(default_factory=ValidateConfig)
    markdown_formatter: MarkdownFormatterConfig | None = None


def _table(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a table")
    unknown = value.keys() - keys
    if unknown:
        raise ConfigurationError(f"Unknown {name} keys: {', '.join(sorted(unknown))}")
    return value


def _boolean(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{key} must be a boolean")
    return value


def _choice(
    data: dict[str, Any], key: str, default: str, choices: tuple[str, ...]
) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or value not in choices:
        raise ConfigurationError(f"{key} must be one of: {', '.join(choices)}")
    return value


def _formatter(data: Any, path: Path) -> MarkdownFormatterConfig:
    values = _table(data, "markdown_formatter", {"command", "mode", "timeout_seconds"})
    mode = _choice(values, "mode", "stdin", ("stdin", "file"))
    command = values.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(arg, str) and "\0" not in arg for arg in command)
        or not command[0].strip()
    ):
        raise ConfigurationError("command must be a nonempty argv array of strings")
    placeholders = set()
    try:
        for arg in command:
            for _, name, spec, conversion in string.Formatter().parse(arg):
                if name is None:
                    continue
                if name not in {"readme", "path", "config_dir"} or spec or conversion:
                    raise ValueError(f"unsupported placeholder: {{{name}}}")
                placeholders.add(name)
    except ValueError as error:
        raise ConfigurationError(f"Invalid formatter command: {error}") from error
    if mode == "stdin" and "path" in placeholders:
        raise ConfigurationError("{path} is only available in file mode")
    if mode == "file" and "path" not in placeholders:
        raise ConfigurationError("file mode requires {path} in command")
    timeout = values.get("timeout_seconds", 30)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ConfigurationError("timeout_seconds must be positive and finite")
    try:
        timeout = float(timeout)
    except OverflowError as error:
        raise ConfigurationError("timeout_seconds must be finite") from error
    if not math.isfinite(timeout):
        raise ConfigurationError("timeout_seconds must be positive and finite")
    return MarkdownFormatterConfig(tuple(command), path, mode, timeout)


def load_project_config(
    target: Path, config_path: Path | None = None, *, no_config: bool = False
) -> ProjectConfig:
    """Load exactly one explicit or target-local TOML file.

    Args:
        target: Role or collection directory; no ancestors are searched.
        config_path: Explicit file, relative to the caller's directory.
        no_config: Bypass discovery, mutually exclusive with config_path.

    Raises:
        ConfigurationError: Selection, TOML or schema is invalid.
    """
    if no_config:
        if config_path is not None:
            raise ConfigurationError("--config and --no-config are mutually exclusive")
        return ProjectConfig()
    if config_path is None:
        try:
            candidates = [
                target / name
                for name in CONFIG_NAMES
                if (target / name).exists() or (target / name).is_symlink()
            ]
        except OSError as error:
            raise ConfigurationError(
                f"Cannot discover configuration in {target}: {error}"
            ) from error
        if len(candidates) > 1:
            names = ", ".join(str(path) for path in candidates)
            raise ConfigurationError(f"Multiple configuration files: {names}")
        if not candidates:
            return ProjectConfig()
        config_path = candidates[0]
    config_path = config_path.absolute()
    try:
        with config_path.open("rb") as stream:
            data = tomllib.load(stream)
        data = _table(
            data,
            "project",
            {"format", "verbose", "generate", "validate", "markdown_formatter"},
        )
        generate = _table(
            data.get("generate", {}),
            "generate",
            {item.name for item in fields(GenerateConfig)},
        )
        validate = _table(
            data.get("validate", {}),
            "validate",
            {item.name for item in fields(ValidateConfig)},
        )
        template = generate.get("template_readme")
        if template is not None and (
            not isinstance(template, str) or not template or "\0" in template
        ):
            raise ConfigurationError("template_readme must be a nonempty path string")
        return ProjectConfig(
            path=config_path,
            format=_choice(data, "format", "auto", ("auto", "markdown", "rst")),
            verbose=_boolean(data, "verbose", False),
            generate=GenerateConfig(
                readme=_boolean(generate, "readme", True),
                defaults=_boolean(generate, "defaults", True),
                defaults_comments_nested=_boolean(
                    generate, "defaults_comments_nested", True
                ),
                readme_toc_list_bulletpoints=_choice(
                    generate, "readme_toc_list_bulletpoints", "auto", ("auto", "*", "-")
                ),
                template_readme=config_path.parent / template if template else None,
                dry_run=_boolean(generate, "dry_run", False),
                check=_boolean(generate, "check", False),
                markdown_formatter=_boolean(generate, "markdown_formatter", True),
            ),
            validate=ValidateConfig(
                readme=_boolean(validate, "readme", True),
                argument_specs=_boolean(validate, "argument_specs", True),
                strict=_boolean(validate, "strict", False),
            ),
            markdown_formatter=(
                _formatter(data["markdown_formatter"], config_path)
                if "markdown_formatter" in data
                else None
            ),
        )
    except (OSError, ValueError, ConfigurationError) as error:
        raise ConfigurationError(f"{config_path}: {error}") from error
