"""Tests for CLI functionality."""

import pytest
from typer.testing import CliRunner

from ansible_docsmith.cli import app

runner = CliRunner()


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Ansible-DocSmith version:" in result.stdout


def test_help():
    """Test help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ansible-docsmith" in result.stdout.lower()
