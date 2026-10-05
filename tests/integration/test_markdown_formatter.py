"""Formatter workflows, including the locked development rumdl toolchain."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_docsmith.cli import app
from ansible_docsmith.core.defaults_comments import DefaultsCommentGenerator
from ansible_docsmith.core.processor import RoleProcessor

FIXTURES = Path(__file__).parents[1] / "fixtures"
ROOT = Path(__file__).parents[2]
RUNNER = CliRunner()


def _snapshot(root: Path) -> dict[Path, tuple[bytes, int]]:
    return {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def _configure(root: Path, command: list[str], mode: str = "stdin") -> None:
    (root / ".ansible-docsmith.toml").write_text(
        f"[markdown_formatter]\ncommand = {json.dumps(command)}\nmode = {json.dumps(mode)}\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("mode", ["stdin", "file"])
def test_rumdl_fixed_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Generate, standalone fmt, check and repeat generation agree byte-for-byte."""
    role = tmp_path / "role"
    shutil.copytree(FIXTURES / "example-role-formatter", role)
    shutil.copyfile(ROOT / ".rumdl.toml", role / ".rumdl.toml")
    executable = Path(sys.executable).with_name("rumdl")
    assert executable.is_file(), "Run with the project's development dependencies"
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.chdir(role)
    common = [
        str(executable),
        "fmt",
        "--config",
        str(role / ".rumdl.toml"),
        "--deny-config-warnings",
        "--no-cache",
    ]
    if mode == "file":
        _configure(role, [*common, "{path}"], mode)
    result = RUNNER.invoke(app, ["generate", "--no-markdown-formatter"])
    assert result.exit_code == 0, result.output
    readme = role / "README.md"
    check_command = [
        str(executable),
        "check",
        "--config",
        str(role / ".rumdl.toml"),
        "--deny-config-warnings",
        "--no-cache",
        "--output-format",
        "json",
        str(readme),
    ]
    raw = subprocess.run(check_command, capture_output=True, check=False, timeout=30)
    assert raw.returncode == 1
    rules = {issue["rule"] for issue in json.loads(raw.stdout)}
    assert {"MD060", "MD012", "MD013"} <= rules
    defaults = (role / "defaults/main.yml").read_bytes()
    result = RUNNER.invoke(app, ["generate"])
    assert result.exit_code == 0, result.output
    assert (role / "defaults/main.yml").read_bytes() == defaults
    lint = subprocess.run(check_command, capture_output=True, check=False, timeout=30)
    assert lint.returncode == 0, lint.stdout.decode()
    formatted = _snapshot(role)
    subprocess.run([*common, str(readme)], capture_output=True, check=True, timeout=30)
    assert _snapshot(role) == formatted
    for flags in (["--check"], ["--dry-run"], []):
        result = RUNNER.invoke(app, ["generate", *flags])
        assert result.exit_code == 0, result.output
        if flags:
            assert "No changes detected" in result.output
        assert _snapshot(role) == formatted
    assert RUNNER.invoke(app, ["validate"]).exit_code == 0

    readme.write_text(
        readme.read_text().replace("hand-written paragraph", "hand-written   paragraph")
    )
    dirty = _snapshot(role)
    result = RUNNER.invoke(app, ["generate", "--check"])
    assert result.exit_code == 1
    assert _snapshot(role) == dirty
    assert RUNNER.invoke(app, ["generate"]).exit_code == 0
    specs = role / "meta/argument_specs.yml"
    specs.write_text(
        specs.read_text().replace("Entries to include.", "New description.")
    )
    dirty = _snapshot(role)
    assert RUNNER.invoke(app, ["generate", "--check"]).exit_code == 1
    assert _snapshot(role) == dirty


@pytest.mark.parametrize("failure", ["second", "collection"])
@pytest.mark.parametrize("flags", [[], ["--check"], ["--dry-run"]])
def test_collection_formatter_failure_writes_nothing(
    tmp_path: Path, failure: str, flags: list[str]
) -> None:
    """A late failure leaves earlier role READMEs and defaults unchanged."""
    collection = tmp_path / "collection"
    shutil.copytree(FIXTURES / "example-collection", collection)
    script = tmp_path / "formatter.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        "readme, temporary = map(Path, sys.argv[1:])\n"
        "temporary.write_text(temporary.read_text() + '\\n')\n"
        f"if readme.parent.name == {failure!r}:\n"
        "    sys.stderr.write('[red]format failed[/red]')\n"
        "    sys.exit(7)\n"
    )
    _configure(collection, [sys.executable, str(script), "{readme}", "{path}"], "file")
    before = _snapshot(collection)
    result = RUNNER.invoke(app, ["generate", str(collection), *flags])
    assert result.exit_code == 1, result.output
    assert "exited 7" in " ".join(result.output.split())
    assert "[red]format failed[/red]" in result.output
    assert "Not written" in result.output
    assert _snapshot(collection) == before


@pytest.mark.parametrize("rst_role", [False, True])
def test_collection_discovery_and_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rst_role: bool
) -> None:
    """Each eligible README runs once, using the root rather than nested config."""
    collection = tmp_path / "collection"
    shutil.copytree(FIXTURES / "example-collection", collection)
    if rst_role:
        second = collection / "roles/second"
        (second / "README.md").unlink()
        assert not RoleProcessor(format_type="rst").process_role(second).errors
    log = tmp_path / "invocations"
    script = tmp_path / "formatter.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"with Path({str(log)!r}).open('a') as stream: stream.write(sys.argv[1] + '\\n')\n"
        "sys.stdout.write(sys.stdin.read())\n"
    )
    _configure(collection, [sys.executable, str(script), "{readme}"])
    role = collection / "roles/first"
    (role / ".ansible-docsmith.toml").write_text("invalid TOML")
    monkeypatch.chdir(collection)
    result = RUNNER.invoke(app, ["generate"])
    assert result.exit_code == 0, result.output
    expected = [str(role / "README.md")]
    if not rst_role:
        expected.append(str(collection / "roles/second/README.md"))
    expected.append(str(collection / "README.md"))
    assert log.read_text().splitlines() == expected
    assert RUNNER.invoke(app, ["generate", str(role), "--check"]).exit_code == 2
    result = RUNNER.invoke(
        app, ["generate", str(role), "--config", ".ansible-docsmith.toml", "--check"]
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("collection_readme", ["missing", "unmanaged"])
def test_no_collection_formatter_without_managed_sections(
    tmp_path: Path, collection_readme: str
) -> None:
    """A collection README without eligible markers remains untouched."""
    collection = tmp_path / "collection"
    shutil.copytree(FIXTURES / "example-collection", collection)
    readme = collection / "README.md"
    readme.unlink()
    if collection_readme == "unmanaged":
        readme.write_text("# Handwritten\n")
    script = tmp_path / "formatter.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        "if Path(sys.argv[1]).parent.name == 'collection': sys.exit(7)\n"
        "sys.stdout.write(sys.stdin.read())\n"
    )
    _configure(collection, [sys.executable, str(script), "{readme}"])
    result = RUNNER.invoke(app, ["generate", str(collection)])
    assert result.exit_code == 0, result.output
    if collection_readme == "missing":
        assert not readme.exists()
    else:
        assert readme.read_text() == "# Handwritten\n"


def test_symlink_outputs_remain_links(tmp_path: Path) -> None:
    """Role/defaults/collection outputs can point outside the processed tree."""
    collection = tmp_path / "collection"
    shutil.copytree(FIXTURES / "example-collection", collection)
    links = [
        collection / "README.md",
        collection / "roles/first/README.md",
        collection / "roles/first/defaults/main.yml",
    ]
    targets = [tmp_path / f"target-{index}" for index in range(len(links))]
    for link, target in zip(links, targets, strict=True):
        link.rename(target)
        link.symlink_to(target)
    before = [target.read_bytes() for target in targets]
    result = RUNNER.invoke(app, ["generate", str(collection)])
    assert result.exit_code == 0, result.output
    assert all(link.is_symlink() for link in links)
    assert all(
        target.read_bytes() != old for target, old in zip(targets, before, strict=True)
    )
    assert RUNNER.invoke(app, ["generate", str(collection), "--check"]).exit_code == 0


def test_defaults_failure_prevents_readme_write(
    sample_role_with_specs_and_defaults: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deferred writing also protects against non-formatter preparation failures."""
    role = sample_role_with_specs_and_defaults
    before = _snapshot(role)

    def fail(*args: object, **kwargs: object) -> str:
        raise OSError("failed to prepare defaults")

    monkeypatch.setattr(DefaultsCommentGenerator, "add_comments", fail)
    result = RoleProcessor().process_role(role)
    assert result.errors
    assert _snapshot(role) == before


@pytest.mark.parametrize("destination", ["README.md", "defaults/main.yml"])
def test_missing_symlink_targets_keep_existing_semantics(
    sample_role_with_specs_and_defaults: Path, tmp_path: Path, destination: str
) -> None:
    """A missing README target is created; missing defaults still fail validation."""
    role = sample_role_with_specs_and_defaults
    link = role / destination
    if link.exists():
        link.unlink()
    target = tmp_path / "target"
    link.symlink_to(target)
    result = RUNNER.invoke(app, ["generate", str(role)])
    assert link.is_symlink()
    if destination == "README.md":
        assert result.exit_code == 0, result.output
        assert target.is_file()
    else:
        assert result.exit_code == 1
        assert not target.exists()
        assert not (role / "README.md").exists()
