"""Convert Ansible documentation markup to Markdown or reStructuredText.

Ansible argument specs commonly use `Ansible markup`_ such as ``C(...)``,
``O(...)`` or ``M(...)`` in descriptions. This module converts these
constructs into the target documentation format as a preprocessing step,
before the text enters the regular rendering/wrapping pipeline.

Plain text (including any Markdown the description already contains) is
passed through verbatim; only Ansible markup constructs are rewritten.
Text without any markup is returned unchanged (byte-identical).

.. _Ansible markup:
   https://docs.ansible.com/projects/ansible/latest/dev_guide/ansible_markup.html
"""

import re
from collections.abc import Callable, Collection

from antsibull_docs_parser import dom
from antsibull_docs_parser.parser import Context, Whitespace, parse

# Fast gate: only text matching this can contain Ansible markup. Chunks
# without a match are passed through without invoking the parser at all,
# which also guarantees byte-identical output for markup-free text.
_MARKUP_HINT = re.compile(r"\b(?:[IBCULRMOVEP]|RV)\(|HORIZONTALLINE")

# Split on blank lines, keeping the exact separators so that paragraph
# structure survives unchanged (the parser itself collapses blank lines).
_PARAGRAPH_SPLIT = re.compile(r"(\n[ \t]*\n+)")

_DOCS_BASE_URL = "https://docs.ansible.com/ansible/latest/collections"


def md_code_span(text: str, table: bool = False) -> str:
    """Build a CommonMark-valid inline code span for arbitrary content.

    Backslash escapes do not work inside code spans; content containing
    backticks needs a delimiter run longer than the longest backtick run
    in the content, padded with spaces if the content starts or ends with
    a backtick. Pipes are only escaped inside GFM table cells, where
    ``\\|`` is honored even within code spans.
    """
    if table:
        text = text.replace("|", "\\|")
    backtick_runs = re.findall(r"`+", text)
    longest_run = max((len(run) for run in backtick_runs), default=0)
    delimiter = "`" * (longest_run + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def rst_inline_literal(text: str) -> str:
    """Wrap text in an RST inline literal (double backticks).

    Single backticks inside inline literals are valid RST and need no
    escaping (backslash escapes are not processed inside literals).
    Content containing a double backtick cannot be represented in an
    RST inline literal at all; a space is inserted as mitigation.
    """
    return f"``{text.replace('``', '` `')}``"


def _plugin_url(fqcn: str, plugin_type: str) -> str | None:
    """Build a docs.ansible.com URL for a well-formed plugin FQCN."""
    segments = fqcn.split(".")
    if len(segments) < 3 or not all(segments):
        return None
    namespace, collection = segments[0], segments[1]
    name = ".".join(segments[2:])
    return f"{_DOCS_BASE_URL}/{namespace}/{collection}/{name}_{plugin_type}.html"


def _option_display(part: dom.OptionNamePart) -> str:
    """Human-readable form of an O() part: 'name' or 'name=value'."""
    return f"{part.name}={part.value}" if part.value is not None else part.name


def _render_md_part(part: dom.AnyPart, role_options: Collection[str]) -> str:
    """Render one DOM part as Markdown, passing plain text through verbatim."""
    if part.type == dom.PartType.TEXT:
        return part.text
    if part.type == dom.PartType.ERROR:
        # Unparseable markup stays exactly as the author wrote it
        return part.source or ""
    if part.type == dom.PartType.BOLD:
        return f"**{part.text}**"
    if part.type == dom.PartType.ITALIC:
        return f"*{part.text}*"
    if part.type == dom.PartType.CODE:
        return md_code_span(part.text)
    if part.type == dom.PartType.OPTION_NAME:
        display = md_code_span(_option_display(part))
        # Link only plain top-level options of this role; DocSmith's README
        # sections provide a matching "variable-<name>" anchor for those.
        if (
            part.plugin is None
            and part.link == [part.name]
            and (part.name in role_options)
        ):
            return f"[{display}](#variable-{part.name})"
        return display
    if part.type == dom.PartType.OPTION_VALUE:
        return md_code_span(part.value)
    if part.type == dom.PartType.ENV_VARIABLE:
        return md_code_span(part.name)
    if part.type == dom.PartType.MODULE:
        url = _plugin_url(part.fqcn, "module")
        code = md_code_span(part.fqcn)
        return f"[{code}]({url})" if url else code
    if part.type == dom.PartType.PLUGIN:
        url = _plugin_url(part.plugin.fqcn, part.plugin.type)
        code = md_code_span(part.plugin.fqcn)
        return f"[{code}]({url})" if url else code
    if part.type == dom.PartType.URL:
        return f"<{part.url}>"
    if part.type == dom.PartType.LINK:
        return f"[{part.text}]({part.url})"
    if part.type == dom.PartType.RST_REF:
        # Sphinx references have no meaning in a standalone README
        return part.text
    if part.type == dom.PartType.HORIZONTAL_LINE:
        return "\n\n---\n\n"
    return part.source or ""


def _render_rst_part(part: dom.AnyPart, role_options: Collection[str]) -> str:
    """Render one DOM part as reStructuredText (plain, no Sphinx roles)."""
    _ = role_options  # anchors are not linked in RST output
    if part.type == dom.PartType.TEXT:
        return part.text
    if part.type == dom.PartType.ERROR:
        return part.source or ""
    if part.type == dom.PartType.BOLD:
        return f"**{part.text}**"
    if part.type == dom.PartType.ITALIC:
        return f"*{part.text}*"
    if part.type == dom.PartType.CODE:
        return rst_inline_literal(part.text)
    if part.type == dom.PartType.OPTION_NAME:
        return rst_inline_literal(_option_display(part))
    if part.type == dom.PartType.OPTION_VALUE:
        return rst_inline_literal(part.value)
    if part.type == dom.PartType.ENV_VARIABLE:
        return rst_inline_literal(part.name)
    if part.type == dom.PartType.MODULE:
        url = _plugin_url(part.fqcn, "module")
        if url:
            return f"`{part.fqcn} <{url}>`__"
        return rst_inline_literal(part.fqcn)
    if part.type == dom.PartType.PLUGIN:
        url = _plugin_url(part.plugin.fqcn, part.plugin.type)
        if url:
            return f"`{part.plugin.fqcn} <{url}>`__"
        return rst_inline_literal(part.plugin.fqcn)
    if part.type == dom.PartType.URL:
        return part.url
    if part.type == dom.PartType.LINK:
        return f"`{part.text} <{part.url}>`__"
    if part.type == dom.PartType.RST_REF:
        return part.text
    if part.type == dom.PartType.HORIZONTAL_LINE:
        return "\n\n----\n\n"
    return part.source or ""


_RENDERERS: dict[str, Callable[[dom.AnyPart, Collection[str]], str]] = {
    "markdown": _render_md_part,
    "rst": _render_rst_part,
}


def _looks_like_code_block(chunk: str) -> bool:
    """Detect chunks that are Markdown code blocks and must stay untouched.

    The Ansible markup parser normalizes whitespace, which would corrupt
    code examples. Fenced blocks and fully indented (4+ spaces) blocks are
    therefore passed through verbatim, even if they contain markup-like
    text.
    """
    stripped = chunk.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return True
    lines = [line for line in chunk.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("    ") for line in lines)


def _convert_chunk(chunk: str, target: str, role_options: Collection[str]) -> str:
    """Convert one blank-line-free chunk of text."""
    paragraphs = parse(
        chunk,
        Context(),
        errors="message",
        add_source=True,
        whitespace=Whitespace.KEEP_SINGLE_NEWLINES,
    )
    render = _RENDERERS[target]
    return "\n\n".join(
        "".join(render(part, role_options) for part in paragraph)
        for paragraph in paragraphs
    )


def lint_ansible_markup(text: str) -> list[str]:
    """Return parse error messages for Ansible markup in the given text.

    Text without markup-like constructs (or inside code blocks, which the
    converter skips as well) produces no messages. The returned messages
    include the offending construct and position, e.g.:
    'While parsing "M(bad)" at index 1: Module name "bad" is not a FQCN'.
    """
    if not text or not _MARKUP_HINT.search(text):
        return []

    errors = []
    for index, chunk in enumerate(_PARAGRAPH_SPLIT.split(text)):
        if index % 2 or not _MARKUP_HINT.search(chunk):
            continue
        if _looks_like_code_block(chunk):
            continue
        for paragraph in parse(
            chunk,
            Context(),
            errors="message",
            whitespace=Whitespace.KEEP_SINGLE_NEWLINES,
        ):
            for part in paragraph:
                if part.type == dom.PartType.ERROR:
                    errors.append(part.message)
    return errors


def convert_ansible_markup(
    text: str,
    target: str,
    role_options: Collection[str] | None = None,
) -> str:
    """Convert Ansible markup in text to the target documentation format.

    Args:
        text: Input text, may freely mix Ansible markup with Markdown.
        target: Output format, "markdown" or "rst".
        role_options: Top-level option names of the current role. When
            given (Markdown only), ``O(name)`` references to these options
            become links to DocSmith's ``#variable-<name>`` README anchors.

    Returns:
        Text with Ansible markup rewritten. Text without markup is
        returned unchanged (byte-identical), including code blocks.
    """
    if not text or not _MARKUP_HINT.search(text):
        return text
    if target not in _RENDERERS:
        raise ValueError(f"Unsupported markup target: {target}")

    options = role_options or ()
    chunks = _PARAGRAPH_SPLIT.split(text)
    # Even-indexed entries are content, odd-indexed ones the separators
    # captured by the split; separators pass through unchanged.
    return "".join(
        chunk
        if index % 2 or not _MARKUP_HINT.search(chunk) or _looks_like_code_block(chunk)
        else _convert_chunk(chunk, target, options)
        for index, chunk in enumerate(chunks)
    )
