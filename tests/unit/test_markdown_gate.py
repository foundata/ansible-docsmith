"""The Markdown gate runs what the foundata guide documents."""

import os
import shlex
from pathlib import Path

import pytest

from tests import check_markdown

GUIDE = "markdown-style-guide.md"


def _guide() -> Path | None:
    """The foundata Markdown guide, if this machine has a copy."""
    directory = os.environ.get("FOUNDATA_GUIDELINES")
    root = Path(directory) if directory else Path(__file__).resolve().parents[3]
    guide = (root if directory else root / "guidelines") / GUIDE
    return guide if guide.is_file() else None


def _invocation(text: str, verb: str) -> list[str]:
    """The arguments of the guide's ``rumdl <verb>`` example, path included."""
    start = text.index(f"rumdl {verb} \\\n")
    lines: list[str] = []
    for line in text[start:].splitlines():
        lines.append(line)
        if not line.rstrip().endswith("\\"):
            break
    joined = " ".join(line.rstrip().rstrip("\\").strip() for line in lines)
    return shlex.split(joined)


def test_the_markdown_gate_runs_what_the_guide_documents() -> None:
    # The gate carries a copy of the guide's invocation, which goes stale
    # without a word when the guide moves: an argument an older rumdl does not
    # know is refused by --deny-config-warnings rather than skipped.
    guide = _guide()
    if guide is None:
        pytest.skip(f"no {GUIDE} beside this repository or in FOUNDATA_GUIDELINES")
    documented = guide.read_text(encoding="utf-8")
    check = _invocation(documented, "check")
    fmt = _invocation(documented, "fmt")

    # One copy serves both verbs only for as long as the guide keeps them equal.
    assert check[2:] == fmt[2:], "the guide's check and fmt examples differ"
    assert check[-1] == ".", check[-1]
    assert list(check_markdown.RULES) == check[2:-1]
