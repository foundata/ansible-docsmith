"""Missing-variable documentation through the CLI and collection pipeline."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ansible_docsmith.cli import app
from ansible_docsmith.core.defaults_comments import MISSING_END, MISSING_START

RUNNER = CliRunner()
SPEC = """argument_specs:
  main:
    options:
      app_host:
        description: Server hostname.
        type: str
        required: true
      app_tls:
        description: Optional TLS settings.
        type: dict
        options:
          certificate:
            description: Certificate file.
            type: path
  install:
    options:
      install_user:
        description: Installation user.
        type: str
"""


def _role(path: Path) -> Path:
    (path / "meta").mkdir(parents=True)
    (path / "meta/argument_specs.yml").write_text(SPEC, encoding="utf-8")
    return path


def _snapshot(root: Path) -> dict[Path, tuple[bytes, int] | None]:
    return {
        path.relative_to(root): (
            (path.read_bytes(), path.stat().st_mtime_ns) if path.is_file() else None
        )
        for path in root.rglob("*")
    }


@pytest.mark.parametrize("initial", [None, "", "# Keep this introduction.\n", "{}\n"])
@pytest.mark.parametrize("extension", ["yml", "yaml"])
def test_generate_preview_check_and_repeat(
    tmp_path: Path, initial: str | None, extension: str
) -> None:
    role = _role(tmp_path / "role")
    main = role / f"defaults/main.{extension if initial is not None else 'yml'}"
    if initial is not None:
        main.parent.mkdir()
        main.write_text(initial, encoding="utf-8")
    before = _snapshot(role)
    args = ["generate", str(role), "--defaults-include-missing"]

    for flag, code in (("--check", 1), ("--dry-run", 0)):
        preview = RUNNER.invoke(app, [*args, flag])
        assert preview.exit_code == code, preview.output
        assert "app_host:" in preview.output
        assert _snapshot(role) == before

    generated = RUNNER.invoke(app, args)
    assert generated.exit_code == 0, generated.output
    content = main.read_text(encoding="utf-8")
    assert MISSING_START + "\n#\n" in content
    assert "#\n" + MISSING_END + "\n" in content
    assert "# app_host:" in content and "# app_tls:" in content
    assert "#   - certificate:" in content
    assert "# certificate:" not in content
    assert "install_user" not in content
    assert YAML().load(content) == YAML().load(initial or "")
    install = role / "defaults/install.yml"
    assert "# install_user:" in install.read_text(encoding="utf-8")
    assert "app_host" not in install.read_text(encoding="utf-8")
    assert len(list(main.parent.iterdir())) == 2
    after = _snapshot(role)

    for flags in (["--check"], ["--dry-run"], []):
        result = RUNNER.invoke(app, [*args, *flags])
        assert result.exit_code == 0, result.output
        assert _snapshot(role) == after

    assert RUNNER.invoke(app, ["validate", str(role), "--strict"]).exit_code == 0


def test_project_settings_overrides_and_disabling(tmp_path: Path) -> None:
    role = _role(tmp_path / "role")
    config = role / ".ansible-docsmith.toml"
    config.write_text(
        "[generate]\nreadme = false\ndefaults_include_missing = true\n"
        "defaults_comments_nested = false\n",
        encoding="utf-8",
    )
    args = ["generate", str(role)]

    for flags in (["--no-defaults"], ["--no-defaults-include-missing"]):
        assert RUNNER.invoke(app, [*args, *flags]).exit_code == 0
        assert not (role / "defaults").exists()

    result = RUNNER.invoke(app, args)
    assert result.exit_code == 0, result.output
    main = role / "defaults/main.yml"
    assert "Dict attributes" not in main.read_text(encoding="utf-8")
    assert not (role / "README.md").exists()
    with main.open("a", encoding="utf-8") as stream:
        stream.write("\n# Keep this example.\n# install_user:\n")
    before = _snapshot(role)
    assert RUNNER.invoke(app, [*args, "--no-defaults"]).exit_code == 0
    assert _snapshot(role) == before
    assert (
        RUNNER.invoke(
            app, [*args, "--no-defaults-include-missing", "--check"]
        ).exit_code
        == 1
    )
    assert _snapshot(role) == before

    assert RUNNER.invoke(app, [*args, "--no-defaults-include-missing"]).exit_code == 0
    assert (
        main.read_text(encoding="utf-8")
        == "---\n\n# Keep this example.\n# install_user:\n"
    )
    assert (role / "defaults/install.yml").read_text(encoding="utf-8") == "---\n"

    config.write_text(
        "[generate]\nreadme = false\ndefaults_include_missing = false\n",
        encoding="utf-8",
    )
    assert RUNNER.invoke(app, [*args, "--defaults-include-missing"]).exit_code == 0
    assert MISSING_START in main.read_text(encoding="utf-8")
    assert "Dict attributes" in main.read_text(encoding="utf-8")


def test_default_off_and_no_eligible_options_create_nothing(tmp_path: Path) -> None:
    role = _role(tmp_path / "role")
    assert RUNNER.invoke(app, ["generate", str(role), "--no-readme"]).exit_code == 0
    assert not (role / "defaults").exists()
    (role / "meta/argument_specs.yml").write_text(
        "argument_specs:\n  main:\n    options: {}\n", encoding="utf-8"
    )
    result = RUNNER.invoke(
        app, ["generate", str(role), "--no-readme", "--defaults-include-missing"]
    )
    assert result.exit_code == 0, result.output
    assert not (role / "defaults").exists()


def test_explicit_spec_default_null_is_not_a_missing_placeholder(
    tmp_path: Path,
) -> None:
    role = _role(tmp_path / "role")
    (role / "meta/argument_specs.yml").write_text(
        "argument_specs:\n  main:\n    options:\n      nullable:\n        default: null\n",
        encoding="utf-8",
    )
    before = _snapshot(role)
    result = RUNNER.invoke(app, ["generate", str(role), "--defaults-include-missing"])
    assert result.exit_code == 1, result.output
    assert "missing from defaults/main.yml" in result.output
    assert _snapshot(role) == before


def test_collection_uses_root_settings_for_every_role(tmp_path: Path) -> None:
    first = _role(tmp_path / "roles/first")
    second = _role(tmp_path / "roles/second")
    (tmp_path / "ansible-docsmith.toml").write_text(
        "[generate]\nreadme = false\ndefaults_include_missing = true\n",
        encoding="utf-8",
    )
    (second / "ansible-docsmith.toml").write_text(
        "[generate]\ndefaults_include_missing = false\n", encoding="utf-8"
    )
    args = ["generate", str(tmp_path)]
    result = RUNNER.invoke(app, args)
    assert result.exit_code == 0, result.output
    for role in (first, second):
        for entry in ("main", "install"):
            assert MISSING_START in (role / f"defaults/{entry}.yml").read_text(
                encoding="utf-8"
            )
    before = _snapshot(tmp_path)
    assert RUNNER.invoke(app, [*args, "--check"]).exit_code == 0
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "bad_content",
    [MISSING_START + "\n", MISSING_START + "\napp_host:\n" + MISSING_END + "\n"],
)
@pytest.mark.parametrize("flags", [[], ["--check"], ["--dry-run"]])
def test_late_failure_leaves_all_files_and_directories_untouched(
    tmp_path: Path, bad_content: str, flags: list[str]
) -> None:
    _role(tmp_path / "roles/first")
    second = _role(tmp_path / "roles/second")
    (second / "defaults").mkdir()
    (second / "defaults/main.yml").write_text(bad_content, encoding="utf-8")
    before = _snapshot(tmp_path)

    result = RUNNER.invoke(
        app, ["generate", str(tmp_path), "--defaults-include-missing", *flags]
    )

    assert result.exit_code == 1, result.output
    assert "MISSING" in result.output
    assert _snapshot(tmp_path) == before


def test_defaults_symlink_is_preserved(tmp_path: Path) -> None:
    role = _role(tmp_path / "role")
    target = tmp_path / "defaults.yaml"
    target.write_text("# Keep this introduction.\n", encoding="utf-8")
    (role / "defaults").mkdir()
    link = role / "defaults/main.yaml"
    link.symlink_to(target)

    result = RUNNER.invoke(
        app, ["generate", str(role), "--no-readme", "--defaults-include-missing"]
    )

    assert result.exit_code == 0, result.output
    assert link.is_symlink()
    assert MISSING_START in target.read_text(encoding="utf-8")
    assert not (role / "defaults/main.yml").exists()
