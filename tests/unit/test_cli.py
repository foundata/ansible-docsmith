"""Tests for CLI functionality."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_docsmith.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Ansible-DocSmith version:" in result.stdout


def test_help() -> None:
    """Test help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ansible-docsmith" in result.stdout.lower()


@pytest.mark.parametrize(
    ("command", "option", "value"),
    [
        ("generate", "--format", "html"),
        ("validate", "--format", "html"),
        ("generate", "--readme-toc-list-bulletpoints", "+"),
    ],
)
def test_invalid_choice_is_a_usage_error(
    command: str,
    option: str,
    value: str,
    sample_role_fixture_path: Path,
) -> None:
    """Reject finite-choice options before running the command."""
    result = runner.invoke(app, [command, str(sample_role_fixture_path), option, value])

    assert result.exit_code == 2
    assert f"Invalid value for '{option}'" in result.output
    assert "Welcome to DocSmith" not in result.output


@pytest.mark.parametrize("command", ["generate", "validate"])
def test_format_choice_remains_case_insensitive(
    command: str, sample_role_fixture_path: Path
) -> None:
    """Keep accepting uppercase spellings of the documented formats."""
    args = [command, str(sample_role_fixture_path), "--format", "MARKDOWN"]
    if command == "generate":
        args.append("--dry-run")

    result = runner.invoke(app, args)

    assert result.exit_code == 0


@pytest.mark.parametrize("bullet_style", ["*", "-"])
def test_toc_bullet_choice_is_accepted(
    bullet_style: str, sample_role_fixture_path: Path
) -> None:
    """Pass either documented bullet style through the parser."""
    result = runner.invoke(
        app,
        [
            "generate",
            str(sample_role_fixture_path),
            "--readme-toc-list-bulletpoints",
            bullet_style,
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
