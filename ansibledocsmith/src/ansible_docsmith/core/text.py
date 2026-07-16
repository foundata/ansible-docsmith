"""Shared text utilities for documentation generation."""

import html
import logging
import re
from html.parser import HTMLParser
from typing import Any

from typing_extensions import override

LOGGER = logging.getLogger(__name__)

# Tokens that must never be split by table-cell truncation: Markdown
# links and inline code spans (left), RST hyperlinks and inline literals
# (right), each with trailing punctuation attached.
MD_ATOMIC_TOKENS = re.compile(r"\[[^\]]*\]\([^)]*\)\S*|`+[^`]+`+\S*|\S+")
RST_ATOMIC_TOKENS = re.compile(r"`[^`<>]*<[^>]*>`__\S*|``[^`]+``\S*|\S+")


def normalize_description(description: Any) -> str:
    """Normalize a description value (string or list) to a single string.

    Argument specs allow descriptions as a string or as a list of
    paragraphs; list items are joined as paragraphs separated by blank
    lines. Any other YAML object type is converted via str().
    """
    if description is None:
        return ""
    if isinstance(description, list):
        return "\n\n".join(
            str(item).strip() for item in description if str(item).strip()
        )
    try:
        return str(description).strip()
    except Exception:
        LOGGER.debug("Could not stringify description", exc_info=True)
        return ""


def truncate_preserving_tokens(
    text: str, max_length: int, token_pattern: re.Pattern[str]
) -> str:
    """Truncate at a word boundary without splitting atomic markup tokens.

    Accumulates whole tokens (words, links, code spans) until the length
    limit is reached, so truncation can never produce broken inline markup
    such as half a link.
    """
    result = ""
    for token in token_pattern.findall(text):
        candidate = f"{result} {token}" if result else token
        if len(candidate) > max_length:
            break
        result = candidate
    # A single oversized token: fall back to a hard character cut
    return result if result else text[:max_length].rstrip()


class HTMLStripper(HTMLParser):
    """HTML parser that strips all tags and returns clean text."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text: list[str] = []

    @override
    def handle_data(self, data: str) -> None:
        """Handle text data between HTML tags."""
        self.text.append(data)

    def get_text(self) -> str:
        """Return the cleaned text."""
        return "".join(self.text)

    @classmethod
    def strip_tags(cls, html_text: str | None) -> str:
        """Strip HTML tags from text and return clean text."""
        if not html_text:
            return ""

        stripper = cls()
        try:
            stripper.feed(html_text)
            # Unescape HTML entities as well
            return html.unescape(stripper.get_text())
        except Exception:
            # Fallback to regex if HTML is malformed
            LOGGER.debug("HTML parsing failed; using regex fallback", exc_info=True)
            return re.sub(r"<[^>]+>", "", html_text)
