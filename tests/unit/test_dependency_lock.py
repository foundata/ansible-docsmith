"""The committed lockfile still resolves the declared dependencies."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_lockfile_matches_the_declared_dependencies() -> None:
    # Every documented command runs --frozen, which uses uv.lock without
    # questioning it. A changed constraint would otherwise be linted, typed and
    # tested against the packages of the old lock, silently.
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("no uv on PATH")

    completed = subprocess.run(
        (uv, "lock", "--check", "--offline"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, (
        "uv.lock does not match pyproject.toml; run `uv lock`\n" + completed.stderr
    )
