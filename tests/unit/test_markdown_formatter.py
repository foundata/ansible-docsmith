"""The formatter command contract, using isolated Python subprocesses."""

import json
import sys
from pathlib import Path

import pytest

from ansible_docsmith.core.config import MarkdownFormatterConfig
from ansible_docsmith.core.exceptions import FormatterError
from ansible_docsmith.core.markdown_formatter import format_markdown

DOCUMENT = """# Heading<a id="heading"></a>

Hand-written  prose.

<!-- ANSIBLE DOCSMITH MAIN START -->
## Variable<a id="variable"></a>
Generated  prose.
<!-- ANSIBLE DOCSMITH MAIN END -->
"""


def formatter(
    tmp_path: Path, code: str, mode: str = "stdin"
) -> MarkdownFormatterConfig:
    script = tmp_path / "formatter.py"
    script.write_text(code, encoding="utf-8")
    args = ("{path}",) if mode == "file" else ()
    return MarkdownFormatterConfig(
        (sys.executable, str(script), *args), tmp_path / "config.toml", mode
    )


@pytest.mark.parametrize("mode", ["stdin", "file"])
def test_whole_file_and_cleanup(tmp_path: Path, mode: str) -> None:
    log = tmp_path / "temporary-path.txt"
    source = (
        "import sys\nfrom pathlib import Path\nprint('diagnostic', file=sys.stderr)\n"
    )
    if mode == "stdin":
        source += "sys.stdout.write(sys.stdin.read().replace('  ', ' '))\n"
    else:
        source += (
            "path = Path(sys.argv[1])\n"
            f"Path({str(log)!r}).write_text(str(path))\n"
            "path.write_text(path.read_text().replace('  ', ' '))\n"
        )
    config = formatter(tmp_path, source, mode)
    readme = tmp_path / "README.md"
    result = format_markdown(DOCUMENT, readme, config)
    assert result == DOCUMENT.replace("  ", " ")
    assert not readme.exists()
    if mode == "file":
        assert not Path(log.read_text()).parent.exists()


def test_context_and_literal_argv(tmp_path: Path) -> None:
    role = tmp_path / "role with spaces"
    role.mkdir()
    log = tmp_path / "arguments.json"
    script = tmp_path / "formatter.py"
    script.write_text(
        "import json, os, sys\nfrom pathlib import Path\n"
        f"Path({str(log)!r}).write_text(json.dumps([os.getcwd(), sys.argv[1:]]))\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
    )
    config = MarkdownFormatterConfig(
        (sys.executable, str(script), "{readme}", "{config_dir}", "a; $HOME", "{{x}}"),
        tmp_path / "config.toml",
    )
    readme = role / "README.md"
    assert format_markdown(DOCUMENT, readme, config) == DOCUMENT
    cwd, args = json.loads(log.read_text())
    assert cwd == str(role)
    assert args == [str(readme), str(tmp_path), "a; $HOME", "{x}"]


@pytest.mark.parametrize(
    "output", [b"", b" \n\t", b"\xff", b"\xef\xbb\xbftext", b"a\0b"]
)
@pytest.mark.parametrize("mode", ["stdin", "file"])
def test_invalid_output(tmp_path: Path, output: bytes, mode: str) -> None:
    """Invalid documents fail regardless of their transport."""
    code = "import sys\nfrom pathlib import Path\n"
    code += (
        f"sys.stdout.buffer.write({output!r})\n"
        if mode == "stdin"
        else f"Path(sys.argv[1]).write_bytes({output!r})\n"
    )
    config = formatter(tmp_path, code, mode)
    with pytest.raises(FormatterError, match=r"README\.md.*config\.toml"):
        format_markdown(DOCUMENT, tmp_path / "README.md", config)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("MAIN START", "MAIN END"),
        ("<!-- ANSIBLE DOCSMITH MAIN END -->", ""),
        ("DOCSMITH MAIN", "DOCSMITH TOC"),
        ("## Variable", "### Variable"),
        ("## Variable", "## Renamed"),
        ('id="variable"', 'id="different"'),
        ('<a id="variable"></a>', ""),
    ],
)
def test_structure_changes_rejected(tmp_path: Path, old: str, new: str) -> None:
    code = f"import sys\nsys.stdout.write(sys.stdin.read().replace({old!r}, {new!r}))\n"
    with pytest.raises(FormatterError):
        format_markdown(DOCUMENT, tmp_path / "README.md", formatter(tmp_path, code))


def test_marker_examples_in_fences_are_not_managed(tmp_path: Path) -> None:
    document = DOCUMENT + "\n```html\n<!-- ANSIBLE DOCSMITH TOC START -->\n```\n"
    config = formatter(
        tmp_path,
        "import sys\nsys.stdout.write(sys.stdin.read().replace('TOC START', 'example'))",
    )
    assert "example" in format_markdown(document, tmp_path / "README.md", config)


def test_unicode_and_crlf(tmp_path: Path) -> None:
    document = DOCUMENT + "\nCaf\u00e9.\n"
    config = formatter(
        tmp_path,
        "import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read().replace(b'\\n', b'\\r\\n'))",
    )
    assert format_markdown(document, tmp_path / "README.md", config) == document


@pytest.mark.parametrize("failure", ["missing", "exit", "timeout", "delete", "symlink"])
def test_failures(tmp_path: Path, failure: str) -> None:
    mode = "file" if failure in {"delete", "symlink"} else "stdin"
    code = {
        "missing": "",
        "exit": "import sys\nsys.stderr.write('[red]problem[/red]')\nsys.exit(7)",
        "timeout": "import time\ntime.sleep(30)",
        "delete": "import sys\nfrom pathlib import Path\nPath(sys.argv[1]).unlink()",
        "symlink": "import sys\nfrom pathlib import Path\np=Path(sys.argv[1])\np.unlink()\np.symlink_to('missing')",
    }[failure]
    config = formatter(tmp_path, code, mode)
    if failure == "missing":
        config = MarkdownFormatterConfig(
            (str(tmp_path / "absent"),), config.config_path
        )
    if failure == "timeout":
        config = MarkdownFormatterConfig(
            config.command, config.config_path, timeout_seconds=0.05
        )
    with pytest.raises(FormatterError) as caught:
        format_markdown(DOCUMENT, tmp_path / "README.md", config)
    if failure == "exit":
        assert "exited 7" in str(caught.value)
        assert "[red]problem[/red]" in str(caught.value)
    if failure == "timeout":
        assert "timed out" in str(caught.value)
