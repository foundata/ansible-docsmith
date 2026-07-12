"""Core functionality for ansible-docsmith."""

from .defaults_comments import DefaultsCommentGenerator
from .exceptions import (
    AnsibleDocSmithError,
    FileOperationError,
    ParseError,
    ProcessingError,
    TemplateError,
    ValidationError,
)
from .parser import ArgumentSpecParser
from .processor import RoleProcessor

__all__ = [
    "RoleProcessor",
    "ArgumentSpecParser",
    "DefaultsCommentGenerator",
    "AnsibleDocSmithError",
    "ValidationError",
    "ParseError",
    "ProcessingError",
    "TemplateError",
    "FileOperationError",
]
