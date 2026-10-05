"""Project discovery and schema validation."""

from pathlib import Path

import pytest

from ansible_docsmith.core.config import (
    CONFIG_NAMES,
    ProjectConfig,
    load_project_config,
)
from ansible_docsmith.core.exceptions import ConfigurationError


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_discovery_is_limited_to_target(tmp_path: Path, name: str) -> None:
    target = tmp_path / "role"
    target.mkdir()
    (tmp_path / name).write_text('format = "rst"\n')
    assert load_project_config(target) == ProjectConfig()
    (target / name).write_text("[generate]\nreadme = false\n")
    config = load_project_config(target)
    assert config.path == target / name
    assert config.format == "auto"
    assert not config.generate.readme
    assert config.markdown_formatter is None


def test_one_authoritative_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in CONFIG_NAMES:
        (tmp_path / name).write_text("[generate]\nreadme = false\n")
    with pytest.raises(ConfigurationError, match="Multiple configuration"):
        load_project_config(tmp_path)
    assert not load_project_config(tmp_path, tmp_path / CONFIG_NAMES[0]).generate.readme
    (tmp_path / "alternative.toml").write_text("[validate]\nstrict = true\n")
    monkeypatch.chdir(tmp_path)
    config = load_project_config(tmp_path, Path("alternative.toml"))
    assert config.generate.readme
    assert config.validate.strict
    assert config.path == tmp_path / "alternative.toml"
    assert load_project_config(tmp_path, no_config=True) == ProjectConfig()
    with pytest.raises(ConfigurationError, match="mutually exclusive"):
        load_project_config(tmp_path, Path("alternative.toml"), no_config=True)


def test_all_project_settings(tmp_path: Path) -> None:
    path = tmp_path / CONFIG_NAMES[0]
    path.write_text("""format = "rst"
verbose = true
[generate]
readme = false
defaults = false
defaults_comments_nested = false
readme_toc_list_bulletpoints = "-"
template_readme = "templates/custom.j2"
check = true
dry_run = true
markdown_formatter = false
[validate]
readme = false
argument_specs = false
strict = true
[markdown_formatter]
command = ["tool", "{config_dir}/policy", "{readme}", "{{literal}}"]
""")
    config = load_project_config(tmp_path)
    assert config.format == "rst" and config.verbose
    assert not config.generate.readme and not config.generate.defaults
    assert not config.generate.defaults_comments_nested
    assert config.generate.readme_toc_list_bulletpoints == "-"
    assert config.generate.template_readme == tmp_path / "templates/custom.j2"
    assert config.generate.check and config.generate.dry_run
    assert not config.generate.markdown_formatter
    assert not config.validate.readme and not config.validate.argument_specs
    assert config.validate.strict
    assert config.markdown_formatter is not None
    assert config.markdown_formatter.mode == "stdin"
    assert config.markdown_formatter.timeout_seconds == 30


@pytest.mark.parametrize(
    "text",
    [
        "not valid TOML",
        "unknown = true",
        'format = "html"',
        "verbose = 1",
        "generate = false",
        "[generate]\nunknown = true",
        "[generate]\nreadme = 0",
        '[generate]\nreadme_toc_list_bulletpoints = "+"',
        "[generate]\ntemplate_readme = false",
        "[validate]\nstrict = 1",
        "[markdown_formatter]",
        '[markdown_formatter]\ncommand = "tool"',
        "[markdown_formatter]\ncommand = []",
        '[markdown_formatter]\ncommand = [""]',
        '[markdown_formatter]\ncommand = ["tool", 1]',
        '[markdown_formatter]\ncommand = ["tool"]\nunknown = true',
        '[markdown_formatter]\ncommand = ["tool"]\nmode = "pipe"',
        '[markdown_formatter]\ncommand = ["tool"]\nmode = "file"',
        '[markdown_formatter]\ncommand = ["tool", "{path}"]',
        '[markdown_formatter]\ncommand = ["tool", "{unknown}"]',
        '[markdown_formatter]\ncommand = ["tool", "{readme.name}"]',
        '[markdown_formatter]\ncommand = ["tool", "{readme!r}"]',
        '[markdown_formatter]\ncommand = ["tool", "{readme:>30}"]',
        '[markdown_formatter]\ncommand = ["tool", "{"]',
        *[
            f'[markdown_formatter]\ncommand = ["tool"]\ntimeout_seconds = {value}'
            for value in ("true", "0", "-1", "inf", "nan", '"30"')
        ],
    ],
)
def test_invalid_schema(tmp_path: Path, text: str) -> None:
    path = tmp_path / CONFIG_NAMES[0]
    path.write_text(text)
    with pytest.raises(ConfigurationError, match=str(path)):
        load_project_config(tmp_path)


def test_missing_explicit_config_does_not_fall_back(tmp_path: Path) -> None:
    (tmp_path / CONFIG_NAMES[0]).write_text("")
    with pytest.raises(ConfigurationError, match=r"missing\.toml"):
        load_project_config(tmp_path, tmp_path / "missing.toml")


def test_file_transport(tmp_path: Path) -> None:
    (tmp_path / CONFIG_NAMES[0]).write_text(
        '[markdown_formatter]\ncommand = ["tool", "{path}"]\n'
        'mode = "file"\ntimeout_seconds = 0.5\n'
    )
    config = load_project_config(tmp_path).markdown_formatter
    assert config is not None and config.mode == "file"
    assert config.timeout_seconds == 0.5


def test_discovery_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery failures use the configuration error contract."""

    def denied(self: Path) -> bool:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "exists", denied)
    with pytest.raises(ConfigurationError, match="Cannot discover configuration"):
        load_project_config(tmp_path)
