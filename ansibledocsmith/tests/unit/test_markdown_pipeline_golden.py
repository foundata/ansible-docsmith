"""Golden-file characterization tests for the Markdown processing pipeline.

These tests freeze the observable behavior of the two components that
parse Markdown internally (description re-formatting for YAML comments
and TOC heading extraction). Their purpose is to make parser changes -
such as the commonmark to markdown-it-py migration - reviewable as a
plain data diff: any behavior change must show up as a change to
markdown_pipeline_golden.json.

Regenerate the golden file after an INTENDED behavior change:

    uv run python tests/unit/test_markdown_pipeline_golden.py

and review the resulting diff carefully.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from ansible_docsmith.core.defaults_comments import DefaultsCommentGenerator
from ansible_docsmith.core.toc import MarkdownTocGenerator

GOLDEN_FILE = Path(__file__).parent / "markdown_pipeline_golden.json"

# Inputs for DefaultsCommentGenerator._parse_and_format_description().
# Cover every Markdown construct the re-formatter handles (or is known
# to flatten/drop, which is deliberately frozen behavior as well).
DESCRIPTION_CORPUS = {
    "plain_paragraph": "Simple text.",
    "softbreak_join": "Line one\nline two",
    "multi_paragraph": "Para one.\n\nPara two.",
    "hard_break": "Line one  \nline two",
    "double_spaces": "keep  double  spaces?",
    "bullets_dash": "- a\n- b",
    "bullets_asterisk": "* a\n* b",
    "bullets_plus": "+ a\n+ b",
    "nested_list_3deep": "- a\n  - b\n    - c",
    "ordered_simple": "1. one\n2. two",
    "ordered_start_three": "3. three\n4. four",
    "ordered_paren_delimiter": "1) one\n2) two",
    "loose_list": "- a\n\n- b",
    "list_item_continuation": "- item\n  continued line",
    "list_item_two_paragraphs": "- item\n\n  second paragraph of item",
    "fenced_code_lang": "```yaml\nkey: value\n```",
    "fenced_code_nolang": "```\nplain\n```",
    "fenced_code_after_text": "Example:\n\n```sh\nrun --now\n```",
    "indented_code": "    indented code\n    second line",
    "inline_code": "Use `foo` here.",
    "inline_code_backticks": "Use ``a`b`` span.",
    "link_plain": "See [text](https://example.com) now.",
    "link_title": 'See [text](https://example.com "The Title") now.',
    "autolink": "See <https://example.com> now.",
    "bare_url": "See https://example.com now.",
    "emphasis_strong": "*em* and **strong**.",
    "blockquote": "> quoted text",
    "thematic_break": "before\n\n---\n\nafter",
    "image": "An ![alt text](img.png) image.",
    "escaped_star": "\\*not emphasis\\*",
    "html_entity": "AT&amp;T and 2 &lt; 3.",
    "html_block": "<div>\nblock content\n</div>",
    "html_inline": "text with <br> inline",
    "heading_in_description": "# Heading\n\nRegular text below.",
    "long_paragraph": (
        "This paragraph is deliberately longer than the usual wrapping "
        "width of seventy-eight characters so that the greedy word "
        "wrapping logic has to break it into several lines and the exact "
        "break positions become part of the frozen behavior."
    ),
    "long_list_items": (
        "- First list item that exceeds the wrapping width by using many "
        "unnecessary words in a single sentence for testing purposes\n"
        "- Second item with a [link](https://example.com/quite/long/url) "
        "and `inline code` that must survive wrapping"
    ),
    "mixed_document": (
        "Intro paragraph.\n\n"
        "- bullet one\n"
        "- bullet two with `code`\n\n"
        "```yaml\nkey: value\n```\n\n"
        "Closing paragraph."
    ),
}

# Inputs for MarkdownTocGenerator._extract_headings().
TOC_CORPUS = {
    "simple": "# One\n\nText.\n\n## Two",
    "inline_code_heading": "## Configure `nginx` Settings",
    "anchor_heading": '## Custom Title<a id="custom-anchor"></a>',
    "anchor_and_code_heading": '### The `code` part<a id="code-part"></a>',
    "setext_headings": "Heading\n=======\n\nSubheading\n----------",
    "hash_in_code_block": "```\n# not a heading\n```\n\n# Real Heading",
    "hash_in_indented_code": "    # also not a heading\n\n## Real",
    "no_headings": "Just some text.\n\nMore text.",
    "all_levels": "# a\n\n## b\n\n### c\n\n#### d\n\n##### e\n\n###### f",
    "empty": "",
}


def _compute_results() -> dict[str, Any]:
    """Compute the pipeline outputs for the whole corpus."""
    generator = DefaultsCommentGenerator()
    toc = MarkdownTocGenerator()

    return {
        "descriptions_nowrap": {
            name: generator._parse_and_format_description(text)
            for name, text in DESCRIPTION_CORPUS.items()
        },
        "descriptions_wrap78": {
            name: generator._parse_and_format_description(text, max_width=78)
            for name, text in DESCRIPTION_CORPUS.items()
        },
        "toc_headings": {
            name: toc._extract_headings(content) for name, content in TOC_CORPUS.items()
        },
    }


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    assert GOLDEN_FILE.exists(), (
        f"Golden file missing: {GOLDEN_FILE}. Generate it with: "
        f"uv run python {Path(__file__).name}"
    )
    data: dict[str, Any] = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    return data


class TestMarkdownPipelineGolden:
    """Compare current pipeline output against the frozen golden data."""

    @pytest.mark.parametrize("name", sorted(DESCRIPTION_CORPUS))
    def test_description_formatting_nowrap(
        self, golden: dict[str, Any], name: str
    ) -> None:
        generator = DefaultsCommentGenerator()
        result = generator._parse_and_format_description(DESCRIPTION_CORPUS[name])
        assert result == golden["descriptions_nowrap"][name]

    @pytest.mark.parametrize("name", sorted(DESCRIPTION_CORPUS))
    def test_description_formatting_wrap78(
        self, golden: dict[str, Any], name: str
    ) -> None:
        generator = DefaultsCommentGenerator()
        result = generator._parse_and_format_description(
            DESCRIPTION_CORPUS[name], max_width=78
        )
        assert result == golden["descriptions_wrap78"][name]

    @pytest.mark.parametrize("name", sorted(TOC_CORPUS))
    def test_toc_heading_extraction(self, golden: dict[str, Any], name: str) -> None:
        toc = MarkdownTocGenerator()
        result = toc._extract_headings(TOC_CORPUS[name])
        assert result == golden["toc_headings"][name]


if __name__ == "__main__":
    # Regenerate the golden file from CURRENT behavior
    GOLDEN_FILE.write_text(
        json.dumps(_compute_results(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Regenerated {GOLDEN_FILE}")
