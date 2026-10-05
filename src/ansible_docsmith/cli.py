#!/usr/bin/env python3
"""
Ansible-DocSmith CLI - Generate Ansible role documentation from argument_specs.yml
"""

import difflib
import logging
from dataclasses import replace
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

import typer
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .constants import CLI_HEADER
from .core.collection import CollectionProcessor, detect_project_type
from .core.config import ProjectConfig, load_project_config
from .core.exceptions import ConfigurationError, ProcessingError, ValidationError
from .core.processor import ProcessingResults, RoleProcessor
from .utils.logging import setup_logging

app = typer.Typer(
    name="ansible-docsmith",
    help="Generate and maintain Ansible role documentation from argument_specs.yml",
    add_completion=True,
)
console = Console()
LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


class _FormatType(StrEnum):
    """README formats accepted by the command line."""

    AUTO = "auto"
    MARKDOWN = "markdown"
    RST = "rst"


class _TocBulletStyle(StrEnum):
    """Markdown bullet styles accepted by the command line."""

    AUTO = "auto"
    ASTERISK = "*"
    HYPHEN = "-"


def _display_header() -> None:
    """Display the branding header."""
    header = CLI_HEADER.format(version=__version__)
    console.print(header, style="bold", highlight=False)
    console.print()  # Blank line


def _project_config(path: Path, config: Path | None, no_config: bool) -> ProjectConfig:
    try:
        return load_project_config(path, config, no_config=no_config)
    except ConfigurationError as error:
        raise typer.BadParameter(str(error), param_hint="configuration") from error


def _display_config(project: ProjectConfig) -> None:
    if project.path is not None:
        console.print(f"Configuration: {project.path}", markup=False)


def _override(value: _T | None, configured: _T) -> _T:
    return configured if value is None else value


def version_callback(value: bool) -> None:
    if value:
        rprint(f"Ansible-DocSmith version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Ansible-DocSmith - Modern Ansible role documentation automation."""
    pass


@app.command()
def generate(
    path: Path = typer.Argument(
        Path("."),
        help="Role or collection directory (also the configuration discovery directory)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_readme: bool | None = typer.Option(
        None, "--readme/--no-readme", help="Generate/update README documentation"
    ),
    format_type: _FormatType | None = typer.Option(
        None,
        "--format",
        help="Output format: 'auto', 'markdown' or 'rst' (auto detects from files)",
        case_sensitive=False,
    ),
    update_defaults: bool | None = typer.Option(
        None,
        "--defaults/--no-defaults",
        help="Add inline comments to entry-point variable files like defaults/main.yml",
    ),
    defaults_comments_nested: bool | None = typer.Option(
        None,
        "--defaults-comments-nested/--no-defaults-comments-nested",
        help=("Document nested options (dict attributes) in entry-point file comments"),
    ),
    defaults_include_missing: bool | None = typer.Option(
        None,
        "--defaults-include-missing/--no-defaults-include-missing",
        help="Document variables without defaults in an owned comment section",
    ),
    dry_run: bool | None = typer.Option(
        None, "--dry-run/--no-dry-run", help="Preview changes without writing files"
    ),
    check: bool | None = typer.Option(
        None,
        "--check/--no-check",
        help="Check whether the documentation is up to date without writing "
        "files (implies --dry-run): exit code 1 if changes would be made. "
        "Useful for CI/CD pipelines and pre-commit hooks.",
    ),
    verbose: bool | None = typer.Option(
        None, "--verbose/--no-verbose", "-v", help="Enable verbose logging"
    ),
    readme_toc_list_bulletpoints: _TocBulletStyle | None = typer.Option(
        None,
        "--readme-toc-list-bulletpoints",
        help=("Bullet style for README TOC ('*', '-' or 'auto')."),
    ),
    template_readme: Path | None = typer.Option(
        None,
        "--template-readme",
        help="Path to custom README template file (.md.j2 or .rst.j2)",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    no_template_readme: bool = typer.Option(
        False, "--no-template-readme", help="Use the built-in README template"
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Use exactly this TOML file instead of discovery"
    ),
    no_config: bool = typer.Option(
        False, "--no-config", help="Ignore project configuration"
    ),
    markdown_formatter: bool | None = typer.Option(
        None,
        "--markdown-formatter/--no-markdown-formatter",
        help="Run the configured formatter, including during check and dry-run",
    ),
) -> None:
    """Generate role/collection documentation, trusting discovered formatter commands."""

    project = _project_config(path, config, no_config)
    if no_template_readme and template_readme is not None:
        raise typer.BadParameter(
            "--template-readme conflicts with --no-template-readme"
        )
    settings = replace(
        project.generate,
        readme=_override(output_readme, project.generate.readme),
        defaults=_override(update_defaults, project.generate.defaults),
        defaults_comments_nested=_override(
            defaults_comments_nested, project.generate.defaults_comments_nested
        ),
        defaults_include_missing=_override(
            defaults_include_missing, project.generate.defaults_include_missing
        ),
        dry_run=_override(dry_run, project.generate.dry_run),
        check=_override(check, project.generate.check),
        markdown_formatter=_override(
            markdown_formatter, project.generate.markdown_formatter
        ),
        readme_toc_list_bulletpoints=_override(
            readme_toc_list_bulletpoints, project.generate.readme_toc_list_bulletpoints
        ),
        template_readme=_override(template_readme, project.generate.template_readme),
    )
    if no_template_readme:
        settings = replace(settings, template_readme=None)
    settings = replace(settings, dry_run=settings.dry_run or settings.check)
    output_readme = settings.readme
    update_defaults = settings.defaults
    defaults_comments_nested = settings.defaults_comments_nested
    check = settings.check
    dry_run = settings.dry_run
    verbose = project.verbose if verbose is None else verbose
    format_type = _FormatType(project.format) if format_type is None else format_type
    bullet_style = settings.readme_toc_list_bulletpoints
    toc_bullet_style = None if bullet_style == "auto" else bullet_style
    if template_readme is None and settings.template_readme and output_readme:
        if (
            not settings.template_readme.is_file()
            or not settings.template_readme.name.endswith(".j2")
        ):
            raise typer.BadParameter(
                "Configured template_readme must be an existing .j2 file"
            )
    template_readme = settings.template_readme if output_readme else None
    formatter = project.markdown_formatter if settings.markdown_formatter else None

    setup_logging(verbose)
    _display_header()
    _display_config(project)
    LOGGER.debug("Effective generate settings: %s; format=%s", settings, format_type)

    # Validate template file extension if provided
    if template_readme and not template_readme.name.endswith(".j2"):
        console.print("[red]Error: Template file must have .j2 extension[/red]")
        raise typer.Exit(1)

    is_collection = detect_project_type(path) == "collection"
    kind = "collection" if is_collection else "role"
    console.print(f"[bold green]Processing {kind}:[/bold green] {path}")
    console.print(
        f"[blue]Options:[/blue] README={output_readme}, "
        f"Defaults={update_defaults}, Dry-run={dry_run}"
    )

    if template_readme:
        console.print(f"[blue]Using custom template:[/blue] {template_readme}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]")

    if is_collection:
        console.print(
            "[blue]Detected collection layout[/blue] (roles below roles/ directory)"
        )

    try:
        # Initialize processor

        try:
            if is_collection:
                collection_processor = CollectionProcessor(
                    collection_path=path,
                    dry_run=dry_run,
                    template_readme=template_readme,
                    toc_bullet_style=toc_bullet_style,
                    format_type=format_type,
                    defaults_comments_nested=defaults_comments_nested,
                    defaults_include_missing=settings.defaults_include_missing,
                    markdown_formatter=formatter,
                )
            else:
                processor = RoleProcessor(
                    dry_run=dry_run,
                    template_readme=template_readme,
                    toc_bullet_style=toc_bullet_style,
                    format_type=format_type,
                    role_path=path,
                    defaults_comments_nested=defaults_comments_nested,
                    defaults_include_missing=settings.defaults_include_missing,
                    markdown_formatter=formatter,
                )
        except ValueError as e:
            LOGGER.error("Template error: %s", e)
            raise typer.Exit(1) from e

        # Process the collection or role
        if is_collection:
            results = collection_processor.process_collection(
                generate_readme=output_readme,
                update_defaults=update_defaults,
            )
        else:
            results = processor.process_role(
                role_path=path,
                generate_readme=output_readme,
                update_defaults=update_defaults,
            )

        # Display results
        _display_results(results, dry_run, base_path=path)

        if results.errors:
            console.print("\n[red]❌ Processing completed with errors[/red]")
            console.print()  # Trailing newline
            raise typer.Exit(1)
        elif check:
            changed_files = [
                file_path
                for file_path, old_content, new_content in results.file_diffs
                if old_content != new_content
            ]
            if changed_files:
                console.print(
                    f"\n[red]❌ Documentation is not up to date "
                    f"({len(changed_files)} file(s) would change)[/red]"
                )
                console.print()  # Trailing newline
                raise typer.Exit(1)
            console.print("\n[green]✅ Documentation is up to date![/green]")
            console.print()  # Trailing newline
        else:
            console.print("\n[green]✅ Documentation generation complete![/green]")
            console.print()  # Trailing newline

    except typer.Exit:
        # Intentional exit with a specific code; do not treat as error
        raise
    except (ValidationError, ProcessingError) as e:
        LOGGER.error("Processing error: %s", e)
        console.print()  # Trailing newline
        raise typer.Exit(1) from e
    except Exception as e:
        LOGGER.error("Unexpected error: %s", e)
        if verbose:
            import traceback

            traceback.print_exc()
        console.print()  # Trailing newline
        raise typer.Exit(1) from e


@app.command()
def validate(
    path: Path = typer.Argument(
        Path("."),
        help="Role or collection directory (also the configuration discovery directory)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    format_type: _FormatType | None = typer.Option(
        None,
        "--format",
        help="Expected format: 'auto', 'markdown' or 'rst' (auto detects from files)",
        case_sensitive=False,
    ),
    verbose: bool | None = typer.Option(
        None, "--verbose/--no-verbose", "-v", help="Enable verbose logging"
    ),
    validate_readme: bool | None = typer.Option(
        None, "--readme/--no-readme", help="Validate README documentation"
    ),
    validate_argument_specs: bool | None = typer.Option(
        None,
        "--argument-specs/--no-argument-specs",
        help="Validate argument_specs file",
    ),
    strict: bool | None = typer.Option(
        None,
        "--strict/--no-strict",
        help="Treat warnings as errors (exit code 1). Useful for CI/CD "
        "pipelines and pre-commit hooks. Notices do not fail validation.",
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Use exactly this TOML file instead of discovery"
    ),
    no_config: bool = typer.Option(
        False, "--no-config", help="Ignore project configuration"
    ),
) -> None:
    """Validate argument_specs.yml structure and content."""

    project = _project_config(path, config, no_config)
    settings = replace(
        project.validate,
        readme=_override(validate_readme, project.validate.readme),
        argument_specs=_override(
            validate_argument_specs, project.validate.argument_specs
        ),
        strict=_override(strict, project.validate.strict),
    )
    validate_readme = settings.readme
    validate_argument_specs = settings.argument_specs
    strict = settings.strict
    verbose = project.verbose if verbose is None else verbose
    format_type = _FormatType(project.format) if format_type is None else format_type
    setup_logging(verbose)
    _display_header()
    _display_config(project)
    LOGGER.debug("Effective validate settings: %s; format=%s", settings, format_type)

    console.print(f"[green]Validating:[/green] {path}")

    try:
        if detect_project_type(path) == "collection":
            _validate_collection(
                path,
                format_type=format_type,
                validate_readme=validate_readme,
                validate_argument_specs=validate_argument_specs,
                strict=strict,
            )
            return

        # Initialize processor
        processor = RoleProcessor(format_type=format_type, role_path=path)

        # Validate the role
        role_data = processor.validate_role(
            path,
            validate_readme=validate_readme,
            validate_argument_specs=validate_argument_specs,
        )

        # Display validation results
        _display_validation_results(role_data)

        if strict and role_data.get("warnings"):
            console.print(
                "\n[red]❌ Validation failed (--strict): "
                "warnings are treated as errors[/red]"
            )
            console.print()  # Trailing newline
            raise typer.Exit(1)

        console.print("\n[green]✅ Validation passed![/green]")
        console.print()  # Trailing newline

    except typer.Exit:
        # Intentional exit with a specific code; do not treat as error
        raise
    except ValidationError as e:
        LOGGER.error("Validation failed: %s", e)
        console.print()  # Trailing newline
        raise typer.Exit(1) from e
    except Exception as e:
        LOGGER.error("Unexpected error: %s", e)
        if verbose:
            import traceback

            traceback.print_exc()
        console.print()  # Trailing newline
        raise typer.Exit(1) from e


def _validate_collection(
    collection_path: Path,
    format_type: str,
    validate_readme: bool,
    validate_argument_specs: bool,
    strict: bool,
) -> None:
    """Validate all roles of a collection plus the collection README."""
    processor = CollectionProcessor(
        collection_path=collection_path, format_type=format_type
    )
    console.print(
        f"[blue]Detected collection layout[/blue] "
        f"({len(processor.roles)} role(s) below roles/ directory)"
    )

    summary = processor.validate_collection(
        validate_readme=validate_readme,
        validate_argument_specs=validate_argument_specs,
    )

    has_warnings = bool(summary["warnings"])
    for role_name, role_data in summary["roles"].items():
        console.print(f"\n[bold]Role: {role_name}[/bold]")
        _display_validation_results(role_data)
        has_warnings = has_warnings or bool(role_data.get("warnings"))

    if summary["warnings"]:
        console.print("\n[yellow]Collection warnings:[/yellow]")
        for warning in summary["warnings"]:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    if summary["notices"]:
        console.print("\n[blue]Collection notices:[/blue]")
        for notice in summary["notices"]:
            console.print(f"  [blue]ℹ[/blue] {notice}")

    if summary["errors"]:
        console.print("\n[red]Errors:[/red]")
        for error in summary["errors"]:
            console.print(f"  • {error}", style="red")
        console.print("\n[red]❌ Validation failed[/red]")
        console.print()  # Trailing newline
        raise typer.Exit(1)

    if strict and has_warnings:
        console.print(
            "\n[red]❌ Validation failed (--strict): "
            "warnings are treated as errors[/red]"
        )
        console.print()  # Trailing newline
        raise typer.Exit(1)

    console.print("\n[green]✅ Validation passed![/green]")
    console.print()  # Trailing newline


def _display_results(
    results: ProcessingResults, dry_run: bool, base_path: Path | None = None
) -> None:
    """Display processing results in a rich table.

    Args:
        results: The processing results to display
        dry_run: Whether the run was a dry run (affects the table title)
        base_path: Base for displaying file paths relative to the
            submitted role/collection path (full path as fallback)
    """

    if not results.operations and not results.errors and not results.warnings:
        console.print("[yellow]No operations performed yet[/yellow]")
        return

    table = Table(title="Processing Results" + (" (DRY RUN)" if dry_run else ""))
    table.add_column("File", style="cyan")
    table.add_column("Action", style="magenta")
    table.add_column("Status", style="green")

    for file_path, action, status in results.operations:
        # Show the path relative to the submitted role/collection path,
        # so collection runs show which role a file belongs to
        try:
            display_path = (
                str(file_path.relative_to(base_path)) if base_path else str(file_path)
            )
        except ValueError:
            display_path = str(file_path)
        table.add_row(display_path, action, status)

    if table.rows:
        console.print(table)

    # Display detailed diffs for dry-run mode
    if dry_run and results.file_diffs:
        console.print(
            "\n[bold]Modifications that would be made without --dry-run "
            "([yellow]nothing was changed yet[/yellow]):[/bold]"
        )
        for file_path, old_content, new_content in results.file_diffs:
            _display_file_diff(file_path, old_content, new_content)

    # Display warnings
    if results.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in results.warnings:
            console.print(f"  • {warning}", style="yellow")

    # Display errors
    if results.errors:
        console.print("\n[red]Errors:[/red]")
        for error in results.errors:
            console.print(f"  • {escape(error)}", style="red")


def _display_file_diff(file_path: Path, old_content: str, new_content: str) -> None:
    """Display a unified diff for a file."""
    console.print(f"\n[bold cyan]--- {file_path}[/bold cyan]")

    # Generate unified diff
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path.name}",
        tofile=f"b/{file_path.name}",
        lineterm="",
    )

    diff_lines = list(diff)
    if not diff_lines:
        console.print("[dim]No changes detected[/dim]")
        return

    # Skip the first two lines (file headers) as we show our own
    for line in diff_lines[2:]:
        line = line.rstrip()
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[red]{line}[/red]")
        elif line.startswith("@@"):
            console.print(f"[bold blue]{line}[/bold blue]")
        else:
            console.print(line)


def _display_validation_results(role_data: dict[str, Any]) -> None:
    """Display validation results."""

    specs = role_data["specs"]
    spec_file = role_data["spec_file"]
    role_name = role_data["role_name"]

    console.print(f"[green]Found spec file:[/green] {spec_file}")
    console.print(f"[green]Role name:[/green] {role_name}")
    console.print(f"[green]Entry points:[/green] {', '.join(specs.keys())}")

    # Show variables for all entry points
    total_variables = sum(len(spec.get("options", {})) for spec in specs.values())
    console.print(f"[green]Variables defined:[/green] {total_variables}")

    if total_variables > 0:
        for entry_point, spec in specs.items():
            options = spec.get("options", {})
            if options:
                console.print(
                    f"\n[blue]Variables in '{entry_point}' entry point:[/blue]"
                )
                for var_name, var_spec in options.items():
                    required = "required" if var_spec.get("required") else "optional"
                    var_type = var_spec.get("type", "str")
                    console.print(f"  • {var_name} ({var_type}, {required})")

    # Show warnings
    if role_data.get("warnings"):
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in role_data["warnings"]:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    # Show notices
    if role_data.get("notices"):
        console.print("\n[blue]Notices:[/blue]")
        for notice in role_data["notices"]:
            console.print(f"  [blue]ℹ[/blue] {notice}")


if __name__ == "__main__":
    app()
