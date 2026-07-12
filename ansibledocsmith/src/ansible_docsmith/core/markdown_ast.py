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
_MD_PARSER = MarkdownIt("commonmark")


def parse_markdown(text: str) -> SyntaxTreeNode:
    """Parse Markdown text into a syntax tree (SyntaxTreeNode root)."""
    return SyntaxTreeNode(_MD_PARSER.parse(text))
