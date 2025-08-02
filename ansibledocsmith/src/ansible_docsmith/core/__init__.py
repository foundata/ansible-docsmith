"""Core functionality for ansible-docsmith."""

from .exceptions import (
    AnsibleDocSmithError,
    FileOperationError,
    ParseError,
    ProcessingError,
    TemplateError,
    ValidationError,
)
from .generator import DefaultsCommentGenerator, DocumentationGenerator
from .parser import ArgumentSpecParser
from .processor import RoleProcessor

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
