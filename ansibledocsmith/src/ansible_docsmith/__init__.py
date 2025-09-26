"""DocSmith for Ansible: automating role documentation (using argument_specs.yml)"""

__version__ = "2.0.0"
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
from .core.exceptions import (
    AnsibleDocSmithError,
    FileOperationError,
    ParseError,
    ProcessingError,
    TemplateError,
    ValidationError,
)
from .core.generator import (
    BaseTocGenerator,
    DefaultsCommentGenerator,
    MarkdownTocGenerator,
    ReadmeUpdater,
    RSTDocumentationGenerator,
    RSTTocGenerator,
    create_toc_generator,
)
from .core.parser import ArgumentSpecParser
from .core.processor import RoleProcessor

__all__ = [
    "__version__",
    "__author__",
    "CLI_HEADER",
    "MARKER_README_MAIN_START",
    "MARKER_README_MAIN_END",
    "MARKER_README_TOC_START",
    "MARKER_README_TOC_END",
    "MARKER_COMMENT_MD_BEGIN",
    "MARKER_COMMENT_MD_END",
    "MARKER_COMMENT_RST_BEGIN",
    "MARKER_COMMENT_RST_END",
    "RoleProcessor",
    "ArgumentSpecParser",
    "DefaultsCommentGenerator",
    "ReadmeUpdater",
    "BaseTocGenerator",
    "MarkdownTocGenerator",
    "RSTDocumentationGenerator",
    "RSTTocGenerator",
    "create_toc_generator",
    "AnsibleDocSmithError",
    "ValidationError",
    "ParseError",
    "ProcessingError",
    "TemplateError",
    "FileOperationError",
]
