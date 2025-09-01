#!/usr/bin/env python3
"""
Ansible-DocSmith CLI - Generate Ansible role documentation from argument_specs.yml
"""

import difflib
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from . import __version__
from .constants import CLI_HEADER
from .core.exceptions import ProcessingError, ValidationError
from .core.processor import RoleProcessor
from .utils.logging import setup_logging

app = typer.Typer(
    name="ansible-docsmith",
    help="Generate and maintain Ansible role documentation from argument_specs.yml",
    add_completion=True,
)
console = Console()


def _display_header():
    """Display the branding header."""
    header = CLI_HEADER.format(version=__version__)
    console.print(header, style="bold", highlight=False)
    console.print()  # Blank line


def version_callback(value: bool):
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
):
    """Ansible-DocSmith - Modern Ansible role documentation automation."""
    pass


@app.command()
def generate(
    role_path: Path = typer.Argument(
        ...,
        help="Path to Ansible role directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_readme: bool = typer.Option(
        True, "--readme/--no-readme", help="Generate/update README documentation"
    ),
    format_type: str = typer.Option(
        "markdown",
        "--format",
        help="Output format: 'markdown' or 'rst'",
        case_sensitive=False,
    ),
    update_defaults: bool = typer.Option(
        True,
        "--defaults/--no-defaults",
        help="Add inline comments to entry-point variable files like defaults/main.yml",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without writing files"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Enable verbose logging"
    ),
    readme_toc_list_bulletpoints: str | None = typer.Option(
        None,
        "--readme-toc-list-bulletpoints",
        help=(
            "Bullet style for README TOC ('*' or '-'). Auto-detected if not specified."
        ),
    ),
    template_readme: Path | None = typer.Option(
        None,
        "--template-readme",
        help="Path to custom README template file (.md.j2)",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
):
    """Generate comprehensive documentation for an Ansible role."""

    logger = setup_logging(verbose)
    _display_header()

    # Validate format type
    if format_type.lower() not in ["markdown", "rst"]:
        console.print("[red]Error: Format must be 'markdown' or 'rst'[/red]")
        raise typer.Exit(1)

    # Validate template file extension if provided
    if template_readme and not template_readme.name.endswith(".j2"):
        console.print("[red]Error: Template file must have .j2 extension[/red]")
        raise typer.Exit(1)

    # Validate TOC bullet style if provided
    if readme_toc_list_bulletpoints and readme_toc_list_bulletpoints not in ["*", "-"]:
        console.print("[red]Error: TOC bullet style must be '*' or '-'[/red]")
        raise typer.Exit(1)

    console.print(f"[bold green]Processing role:[/bold green] {role_path}")
    console.print(
        f"[blue]Options:[/blue] README={output_readme}, "
        f"Defaults={update_defaults}, Dry-run={dry_run}"
    )

    if template_readme:
        console.print(f"[blue]Using custom template:[/blue] {template_readme}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]")

    try:
        # Initialize processor
        try:
            processor = RoleProcessor(
                dry_run=dry_run,
                template_readme=template_readme,
                toc_bullet_style=readme_toc_list_bulletpoints,
                format_type=format_type,
            )
        except ValueError as e:
            logger.error(f"Template error: {e}")
            raise typer.Exit(1)

        # Process the role
        results = processor.process_role(
            role_path=role_path,
            generate_readme=output_readme,
            update_defaults=update_defaults,
        )

        # Display results
        _display_results(results, dry_run)

        if results.errors:
            console.print("\n[red]❌ Processing completed with errors[/red]")
            console.print()  # Trailing newline
            raise typer.Exit(1)
        else:
            console.print("\n[green]✅ Documentation generation complete![/green]")
            console.print()  # Trailing newline

    except (ValidationError, ProcessingError) as e:
        logger.error(f"Processing error: {e}")
        console.print()  # Trailing newline
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        console.print()  # Trailing newline
        raise typer.Exit(1)


@app.command()
def validate(
    role_path: Path = typer.Argument(
        ...,
        help="Path to Ansible role directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Enable verbose logging"
    ),
):
    """Validate argument_specs.yml structure and content."""

    logger = setup_logging(verbose)
    _display_header()

    console.print(f"[green]Validating:[/green] {role_path}")

    try:
        # Initialize processor
        processor = RoleProcessor()

        # Validate the role
        role_data = processor.validate_role(role_path)

        # Display validation results
        _display_validation_results(role_data)

        console.print("\n[green]✅ Validation passed![/green]")
        console.print()  # Trailing newline

    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        console.print()  # Trailing newline
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        console.print()  # Trailing newline
        raise typer.Exit(1)


def _display_results(results, dry_run: bool):
    """Display processing results in a rich table."""

    if not results.operations and not results.errors and not results.warnings:
        console.print("[yellow]No operations performed yet[/yellow]")
        return

    table = Table(title="Processing Results" + (" (DRY RUN)" if dry_run else ""))
    table.add_column("File", style="cyan")
    table.add_column("Action", style="magenta")
    table.add_column("Status", style="green")

    for file_path, action, status in results.operations:
        # Show relative path for readability
        display_path = str(file_path.name) if file_path.name else str(file_path)
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
            console.print(f"  • {error}", style="red")


def _display_file_diff(file_path: Path, old_content: str, new_content: str):
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


def _display_validation_results(role_data):
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
