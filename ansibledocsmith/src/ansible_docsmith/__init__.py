"""DocSmith for Ansible: automating role documentation (using argument_specs.yml)"""

__version__ = "1.0.0"
__author__ = "foundata GmbH"

from .constants import (
    CLI_HEADER,
    MARKER_COMMENT_MARKDOWN_BEGIN,
    MARKER_COMMENT_MARKDOWN_END,
    MARKER_README_MAIN_END,
    MARKER_README_MAIN_START,
)
from .core.exceptions import (
    AnsibleDocSmithError,
    FileOperationError,
    ParseError,
    ProcessingError,
    TemplateError,
    ValidationError,
)
from .core.generator import DefaultsCommentGenerator, DocumentationGenerator
from .core.parser import ArgumentSpecParser
from .core.processor import RoleProcessor

__all__ = [
    "__version__",
    "__author__",
    "CLI_HEADER",
    "MARKER_README_MAIN_START",
    "MARKER_README_MAIN_END",
    "MARKER_COMMENT_MARKDOWN_BEGIN",
    "MARKER_COMMENT_MARKDOWN_END",
    "RoleProcessor",
    "ArgumentSpecParser",
    "DocumentationGenerator",
    "DefaultsCommentGenerator",
    "AnsibleDocSmithError",
    "ValidationError",
    "ParseError",
    "ProcessingError",
    "TemplateError",
    "FileOperationError",
]
