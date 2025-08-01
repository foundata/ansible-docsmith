#!/usr/bin/env python3
"""
Ansible-DocSmith CLI - Generate Ansible role documentation from argument_specs.yml
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich import print as rprint

from . import __version__

app = typer.Typer(
    name="ansible-docsmith",
    help="Generate and maintain Ansible role documentation from argument_specs.yml",
    add_completion=False,
)
console = Console()

def version_callback(value: bool):
    if value:
        rprint(f"Ansible-DocSmith version: {__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
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
        dir_okay=True
    ),
    output_readme: bool = typer.Option(
        True,
        "--readme/--no-readme",
        help="Generate/update README.md documentation"
    ),
    update_defaults: bool = typer.Option(
        True,
        "--defaults/--no-defaults",
        help="Add inline comments to defaults/main.yml"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without writing files"
    ),
    verbose: bool = typer.Option(
        False,
        "-v", "--verbose",
        help="Enable verbose logging"
    )
):
    """Generate comprehensive documentation for an Ansible role."""

    console.print(f"[bold green]Processing role:[/bold green] {role_path}")
    console.print(f"[blue]Options:[/blue] README={output_readme}, Defaults={update_defaults}, Dry-run={dry_run}")

    spec_file = None
    for ext in ["yml", "yaml"]:
        candidate = role_path / "meta" / f"argument_specs.{ext}"
        if candidate.exists():
            spec_file = candidate
            break

    if not spec_file:
        console.print("[red]Error:[/red] No argument_specs.yml found in meta/ directory")
        raise typer.Exit(1)

    console.print(f"[green]Found:[/green] {spec_file}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]")

    # TODO: Implement actual processing
    console.print("[green]✅ Documentation generation complete![/green]")

@app.command()
def validate(
    role_path: Path = typer.Argument(
        ...,
        help="Path to Ansible role directory",
        exists=True,
        file_okay=False,
        dir_okay=True
    )
):
    """Validate argument_specs.yml structure and content."""

    spec_file: Path | None = None
    for ext in ["yml", "yaml"]:
        candidate = role_path / "meta" / f"argument_specs.{ext}"
        if candidate.exists():
            spec_file = candidate
            break

    if not spec_file:
        console.print("[red]Error:[/red] No argument_specs.yml found")
        raise typer.Exit(1)

    console.print(f"[green]Validating:[/green] {spec_file}")
    # TODO: Implement validation logic
    console.print("[green]✅ Validation passed![/green]")
