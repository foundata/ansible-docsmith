"""Custom exceptions for ansible-docsmith."""


class AnsibleDocSmithError(Exception):
    """Base exception for all ansible-docsmith errors."""

    pass


class ValidationError(AnsibleDocSmithError):
    """Raised when role validation fails."""

    pass


class ParseError(AnsibleDocSmithError):
    """Raised when parsing argument_specs.yml fails."""

    pass


class ProcessingError(AnsibleDocSmithError):
    """Raised when role processing fails."""

    pass


class TemplateError(AnsibleDocSmithError):
    """Raised when template rendering fails."""

    pass


class FileOperationError(AnsibleDocSmithError):
    """Raised when file operations fail."""

    pass
