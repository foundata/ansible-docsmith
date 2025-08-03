"""DocSmith for Ansible: automating role documentation (using argument_specs.yml)"""

__version__ = "0.1.0"
__author__ = "foundata GmbH"

from .constants import README_END_MARKER, README_START_MARKER
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
    "README_START_MARKER",
    "README_END_MARKER",
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
