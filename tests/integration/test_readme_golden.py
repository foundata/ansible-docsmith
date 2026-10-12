# SPDX-FileCopyrightText: foundata GmbH <https://foundata.com>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Golden READMEs that the default Markdown template generates for the fixtures.

Every README a ``generate`` run writes for the Markdown fixtures listed below is
frozen in readme_golden.json, so a template or ToC change that alters the
output of these short names shows up as a data diff.

Regenerate the golden file after an INTENDED output change:

    uv run python tests/integration/test_readme_golden.py

and review the resulting diff carefully.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_docsmith.cli import app

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN_FILE = Path(__file__).parent / "readme_golden.json"

# Markdown fixtures that generate without errors. Their anchor IDs are all
# short enough for the inline anchor form.
GOLDEN_FIXTURES = (
    "example-collection",
    "example-role-ansible-markup",
    "example-role-formatter",
    "example-role-mismatch-spec-defaults",
    "example-role-mixed-entry-points",
    "example-role-multiple-entry-points",
    "example-role-nested-options",
    "example-role-simple",
    "example-role-simple-toc",
)


def _generate(fixture: str, work: Path) -> dict[str, str]:
    """Generate a copy of a fixture and return its READMEs by relative path."""
    target = work / fixture
    shutil.copytree(FIXTURES / fixture, target)
    result = CliRunner().invoke(
        app, ["generate", str(target), "--no-markdown-formatter"]
    )
    assert result.exit_code == 0, result.output
    return {
        f"{fixture}/{path.relative_to(target).as_posix()}": path.read_text(
            encoding="utf-8"
        )
        for path in sorted(target.rglob("README.md"))
    }


@pytest.fixture(scope="module")
def golden() -> dict[str, str]:
    assert GOLDEN_FILE.exists(), (
        f"Golden file missing: {GOLDEN_FILE}. Generate it with: "
        f"uv run python tests/integration/{Path(__file__).name}"
    )
    data: dict[str, str] = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("fixture", GOLDEN_FIXTURES)
def test_generated_readmes_match_golden(
    golden: dict[str, str], fixture: str, temp_dir: Path
) -> None:
    expected = {
        name: text for name, text in golden.items() if name.startswith(f"{fixture}/")
    }
    assert expected, f"No golden README for {fixture}"
    assert _generate(fixture, temp_dir) == expected


if __name__ == "__main__":
    # Regenerate the golden file from CURRENT behavior
    with tempfile.TemporaryDirectory() as directory:
        results: dict[str, str] = {}
        for name in GOLDEN_FIXTURES:
            results.update(_generate(name, Path(directory)))
    GOLDEN_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Regenerated {GOLDEN_FILE}")
