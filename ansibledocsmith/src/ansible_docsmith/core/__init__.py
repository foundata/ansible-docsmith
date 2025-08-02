"""Core functionality for ansible-docsmith."""

from .processor import RoleProcessor
from .parser import ArgumentSpecParser
from .generator import DocumentationGenerator, DefaultsCommentGenerator
from .exceptions import (
    AnsibleDocSmithError,
    ValidationError,
    ParseError,
    ProcessingError,
    TemplateError,
    FileOperationError
)

__all__ = [
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