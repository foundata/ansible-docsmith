"""Shared Markdown parsing seam based on markdown-it-py.

All internal Markdown parsing goes through this module so that the
parser configuration lives in one place and tests can patch a single
symbol.
"""

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

# Strict CommonMark preset: no tables, strikethrough or linkification.
# This matches the behavior of the previously used (unmaintained)
# commonmark library. The instance is stateless after construction and
# safe to reuse.
#
# "text_join" (which merges escape/entity tokens into plain text) is
# disabled so that backslash escapes and entities stay visible as
# "text_special" nodes: their ".markup" attribute carries the original
# source (like "\\*"), allowing source-faithful re-emission.
_MD_PARSER = MarkdownIt("commonmark")
_MD_PARSER.disable("text_join")


def parse_markdown(text: str) -> SyntaxTreeNode:
    """Parse Markdown text into a syntax tree (SyntaxTreeNode root).

    Escaped characters and entities appear as "text_special" nodes
    (content: the resolved character, markup: the original source,
    info: "escape" or "entity") instead of being merged into "text".
    """
    return SyntaxTreeNode(_MD_PARSER.parse(text))
