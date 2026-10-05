"""Run an optional Markdown formatter on disposable content."""

import stat
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from typing_extensions import override

from .config import MarkdownFormatterConfig
from .exceptions import FormatterError
from .markdown_ast import parse_markdown
from .readme_updater import MARKER_PATTERN
from .toc import MarkdownTocGenerator


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.comments: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    @override
    def handle_comment(self, data: str) -> None:
        if MARKER_PATTERN.search(data):
            self.comments.append(f"<!--{data}-->")

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is not None and (name == "id" or (tag == "a" and name == "name")):
                self.anchors.append((name, value))


def _structure(content: str) -> tuple[list[str], list[tuple[str, str]]]:
    comments: list[str] = []
    anchors: list[tuple[str, str]] = []
    for node in parse_markdown(content).walk():
        if node.type in {"html_inline", "html_block"}:
            parser = _StructureParser()
            parser.feed(node.content)
            parser.close()
            comments.extend(parser.comments)
            anchors.extend(parser.anchors)
    stack: list[tuple[str, str | None]] = []
    for comment in comments:
        match = MARKER_PATTERN.search(comment)
        if match is None:
            continue
        key = (match.group("type"), match.group("role"))
        if match.group("kind") == "START":
            stack.append(key)
        elif not stack or stack.pop() != key:
            raise FormatterError("Unpaired or reordered DocSmith markers")
    if stack:
        raise FormatterError("Unpaired DocSmith markers")
    return comments, anchors


def _validate_output(original: str, output: bytes) -> str:
    result = output.decode("utf-8").replace("\r\n", "\n")
    if not result.strip() or "\0" in result or "\ufeff" in result:
        raise FormatterError("Formatter output is empty or contains a BOM or NUL")
    if _structure(original) != _structure(result):
        raise FormatterError(
            "Formatter changed DocSmith marker comments or explicit anchors"
        )
    toc = MarkdownTocGenerator()
    if toc._extract_headings(original) != toc._extract_headings(result):
        raise FormatterError("Formatter changed heading text, levels or anchors")
    return result


def _diagnostics(data: bytes | None) -> str:
    return (data or b"")[:4096].decode("utf-8", errors="replace").strip()


def format_markdown(
    content: str, readme_path: Path, config: MarkdownFormatterConfig
) -> str:
    """Format the whole merged README without exposing a writable project file.

    The configured command is trusted code, not a sandboxed transformation.
    Its stdout is document data only in stdin mode.
    """
    readme_path = readme_path.absolute()
    context = (
        f"{readme_path} (config {config.config_path}, formatter {config.command[0]!r})"
    )
    diagnostics = ""
    try:
        with tempfile.TemporaryDirectory(prefix="ansible-docsmith-formatter-") as temp:
            temporary_path = Path(temp) / "README.md"
            if config.mode == "file":
                temporary_path.write_text(content, encoding="utf-8", newline="\n")
            arguments = [
                argument.format(
                    readme=str(readme_path),
                    path=str(temporary_path),
                    config_dir=str(config.config_path.parent),
                )
                for argument in config.command
            ]
            process = subprocess.run(
                arguments,
                input=content.encode("utf-8") if config.mode == "stdin" else None,
                stdin=subprocess.DEVNULL if config.mode == "file" else None,
                capture_output=True,
                cwd=readme_path.parent,
                timeout=config.timeout_seconds,
                shell=False,
                check=False,
            )
            diagnostics = _diagnostics(process.stderr)
            if config.mode == "file":
                diagnostics += "\n" + _diagnostics(process.stdout)
            if process.returncode != 0:
                raise FormatterError(f"Formatter exited {process.returncode}")
            if config.mode == "file":
                if not stat.S_ISREG(temporary_path.lstat().st_mode):
                    raise FormatterError("Formatter result must remain a regular file")
                output = temporary_path.read_bytes()
            else:
                output = process.stdout
            return _validate_output(content, output)
    except subprocess.TimeoutExpired as error:
        raise FormatterError(
            f"{context}: timed out after {config.timeout_seconds:g}s: "
            f"{_diagnostics(error.stderr)}"
        ) from error
    except (OSError, ValueError, FormatterError) as error:
        detail = f": {diagnostics.strip()}" if diagnostics.strip() else ""
        raise FormatterError(f"{context}: {error}{detail}") from error
