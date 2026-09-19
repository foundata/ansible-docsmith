"""DocSmith for Ansible: automating role documentation (using argument_specs.yml)"""

from importlib.metadata import version as _distribution_version

# One hand-edited version site: pyproject.toml. Everything else reads it back
# from the installed distribution metadata.
__version__ = _distribution_version("ansible-docsmith")
__author__ = "foundata GmbH"

from .constants import (
    CLI_HEADER,
    MARKER_COMMENT_MD_BEGIN,
    MARKER_COMMENT_MD_END,
    MARKER_COMMENT_RST_BEGIN,
    MARKER_COMMENT_RST_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
    MARKER_README_TOC_END,
    MARKER_README_TOC_START,
)
from .core.defaults_comments import DefaultsCommentGenerator
from .core.doc_generators import RSTDocumentationGenerator
from .core.exceptions import (
    AnsibleDocSmithError,
    FileOperationError,
    ParseError,
    ProcessingError,
    TemplateError,
    ValidationError,
)
from .core.parser import ArgumentSpecParser
from .core.processor import RoleProcessor
from .core.readme_updater import ReadmeUpdater
from .core.toc import (
    BaseTocGenerator,
    MarkdownTocGenerator,
    RSTTocGenerator,
    create_toc_generator,
)

__all__ = [
    "CLI_HEADER",
    "MARKER_COMMENT_MD_BEGIN",
    "MARKER_COMMENT_MD_END",
    "MARKER_COMMENT_RST_BEGIN",
    "MARKER_COMMENT_RST_END",
    "MARKER_README_MAIN_END",
    "MARKER_README_MAIN_START",
    "MARKER_README_TOC_END",
    "MARKER_README_TOC_START",
    "AnsibleDocSmithError",
    "ArgumentSpecParser",
    "BaseTocGenerator",
    "DefaultsCommentGenerator",
    "FileOperationError",
    "MarkdownTocGenerator",
    "ParseError",
    "ProcessingError",
    "RSTDocumentationGenerator",
    "RSTTocGenerator",
    "ReadmeUpdater",
    "RoleProcessor",
    "TemplateError",
    "ValidationError",
    "__author__",
    "__version__",
    "create_toc_generator",
]
