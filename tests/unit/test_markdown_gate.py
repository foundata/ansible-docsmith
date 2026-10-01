"""The Markdown gate runs with the foundata guide's .rumdl.toml."""

import os
from pathlib import Path

import pytest

from tests import check_markdown

GUIDE = "markdown.md"
ROOT = Path(__file__).resolve().parents[2]


def _guide() -> Path | None:
    """The foundata Markdown guide, if this machine has a copy."""
    directory = os.environ.get("FOUNDATA_GUIDELINES")
    root = Path(directory) if directory else ROOT.parent
    guide = (root if directory else root / "guidelines") / GUIDE
    return guide if guide.is_file() else None


def _documented_config(text: str) -> str:
    """The ``.rumdl.toml`` the guide's linting section shows."""
    section = text.index("## Linting and automatic formatting")
    start = text.index("```toml\n", section) + len("```toml\n")
    return text[start : text.index("```\n", start)]


def test_the_markdown_config_is_the_guides() -> None:
    # .rumdl.toml is a copy of the guide's file, which goes stale without a word
    # when the guide moves. Compare byte for byte where the guide is checked out.
    guide = _guide()
    if guide is None:
        pytest.skip(f"no {GUIDE} beside this repository or in FOUNDATA_GUIDELINES")
    documented = _documented_config(guide.read_text(encoding="utf-8"))
    committed = (ROOT / check_markdown.CONFIG).read_text(encoding="utf-8")
    assert committed == documented
