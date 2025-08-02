"""Ansible DocSmith: role documentation automation (helper using argument_specs.yml)"""

__version__ = "0.1.0"
__author__ = "foundata GmbH"

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
