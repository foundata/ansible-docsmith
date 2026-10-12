# SPDX-FileCopyrightText: foundata GmbH <https://foundata.com>
# SPDX-License-Identifier: GPL-3.0-or-later
"""READMEs of roles with maximum-length names pass foundata's Markdown rules."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_docsmith.cli import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "example-role-long-names"
# 64 characters, the maximum Galaxy accepts for a role name
ROLE_NAME = "another_long_product_name_with_a_galaxy_maximum_length_role_name"
RUNNER = CliRunner()


def _rumdl_issues(role: Path) -> list[dict[str, object]]:
    """Lint the role README with the fixture's copy of the house configuration."""
    executable = Path(sys.executable).with_name("rumdl")
    assert executable.is_file(), "Run with the project's development dependencies"
    result = subprocess.run(
        [
            str(executable),
            "check",
            "--config",
            str(role / ".rumdl.toml"),
            "--deny-config-warnings",
            "--no-cache",
            "--output-format",
            "json",
            str(role / "README.md"),
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    issues: list[dict[str, object]] = json.loads(result.stdout)
    assert (result.returncode != 0) == bool(issues), result.stderr.decode()
    return issues


@pytest.fixture
def role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the fixture, with the locked rumdl first on PATH."""
    role = tmp_path / "role"
    shutil.copytree(FIXTURE, role)
    bin_dir = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", bin_dir + os.pathsep + os.environ["PATH"])
    return role


def test_formatted_readme_passes_the_house_rules(role: Path) -> None:
    """The fixture's formatter setup is the one the role skeleton ships."""
    result = RUNNER.invoke(app, ["generate", str(role)])
    assert result.exit_code == 0, result.output
    assert _rumdl_issues(role) == []
    assert RUNNER.invoke(app, ["generate", str(role), "--check"]).exit_code == 0


def test_generated_lines_stay_within_the_limit(role: Path) -> None:
    """Formatters cannot shorten headings, so the template must."""
    result = RUNNER.invoke(app, ["generate", str(role), "--no-markdown-formatter"])
    assert result.exit_code == 0, result.output
    assert [issue for issue in _rumdl_issues(role) if issue["rule"] == "MD013"] == []
    readme = (role / "README.md").read_text(encoding="utf-8")
    anchors = set(re.findall(r'<a id="([^"]+)"></a>', readme))
    links = set(re.findall(r"\]\(#([^)]+)\)", readme))
    assert f"variable-{ROLE_NAME}_state" in links
    assert links <= anchors
