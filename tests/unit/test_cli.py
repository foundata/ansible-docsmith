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


def test_project_settings_and_explicit_overrides(
    sample_role_with_specs_and_defaults: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitted CLI flags retain settings; explicit false and auto override them."""
    role = sample_role_with_specs_and_defaults
    monkeypatch.chdir(role)
    (role / ".ansible-docsmith.toml").write_text(
        'format = "rst"\n[generate]\ncheck = true\ndry_run = true\n'
        'defaults = false\nreadme_toc_list_bulletpoints = "-"\n'
    )
    defaults = role / "defaults/main.yml"
    before = defaults.read_bytes()
    assert runner.invoke(app, ["generate"]).exit_code == 1
    assert not (role / "README.rst").exists()
    result = runner.invoke(
        app,
        [
            "generate",
            "--no-check",
            "--no-dry-run",
            "--format",
            "auto",
            "--readme-toc-list-bulletpoints",
            "auto",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (role / "README.md").exists()
    assert not (role / "README.rst").exists()
    assert defaults.read_bytes() == before
    assert "Configuration:" in result.output


@pytest.mark.parametrize("command", ["generate", "validate"])
def test_config_errors_and_bypass(
    sample_role_with_specs_and_defaults: Path, command: str
) -> None:
    """Bad selected configuration fails before work, even with execution disabled."""
    role = sample_role_with_specs_and_defaults
    (role / ".ansible-docsmith.toml").write_text("unknown = true")
    args = [command, str(role)]
    if command == "generate":
        args.extend(["--dry-run", "--no-markdown-formatter"])
    assert runner.invoke(app, args).exit_code == 2
    assert runner.invoke(app, [*args, "--no-config"]).exit_code == 0
    assert runner.invoke(app, [*args, "--help"]).exit_code == 0
    assert (
        runner.invoke(app, [*args, "--no-config", "--config", "other"]).exit_code == 2
    )


@pytest.mark.parametrize("suppression", ["--no-markdown-formatter", "--no-readme"])
def test_formatter_suppression(
    sample_role_with_specs_and_defaults: Path, suppression: str
) -> None:
    """README and hook disabling prevent subprocess launch, including in check mode."""
    role = sample_role_with_specs_and_defaults
    (role / ".ansible-docsmith.toml").write_text(
        '[markdown_formatter]\ncommand = ["docsmith-no-such-command"]\n'
    )
    result = runner.invoke(app, ["generate", str(role), "--dry-run", suppression])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["generate", str(role), "--dry-run"])
    assert result.exit_code == 1
    assert "docsmith-no-such-command" in result.output
    assert not (role / "README.md").exists()


def test_validate_configuration_never_launches_formatter(
    sample_role_with_specs_and_defaults: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation uses its own settings and does not launch the declared command."""
    role = sample_role_with_specs_and_defaults
    monkeypatch.chdir(role)
    (role / ".ansible-docsmith.toml").write_text(
        "[validate]\nstrict = true\n[markdown_formatter]\n"
        'command = ["docsmith-no-such-command"]\n'
    )
    assert runner.invoke(app, ["validate"]).exit_code == 1
    assert runner.invoke(app, ["validate", "--no-strict"]).exit_code == 0
    assert runner.invoke(app, ["validate", "--no-argument-specs"]).exit_code == 0


def test_configured_template_can_be_overridden(
    sample_role_with_specs_and_defaults: Path, tmp_path: Path
) -> None:
    """File templates are config-relative; CLI can explicitly clear them."""
    role = sample_role_with_specs_and_defaults
    config = tmp_path / "settings.toml"
    config.write_text('[generate]\ntemplate_readme = "custom.j2"\n')
    (tmp_path / "custom.j2").write_text("Custom template content\n")
    result = runner.invoke(app, ["generate", str(role), "--config", str(config)])
    assert result.exit_code == 0, result.output
    readme = role / "README.md"
    assert "Custom template content" in readme.read_text()
    result = runner.invoke(
        app, ["generate", str(role), "--config", str(config), "--no-template-readme"]
    )
    assert result.exit_code == 0, result.output
    assert "Custom template content" not in readme.read_text()
