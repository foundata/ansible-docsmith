"""Logging configuration for ansible-docsmith."""

import logging

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(verbose: bool = False) -> None:
    """Configure the package logger with a Rich handler.

    Called once at the application entry point. Modules obtain their own
    loggers via ``logging.getLogger(__name__)``, which propagate to this
    configured ``ansible_docsmith`` package logger.
    """

    # Configure the package-root logger
    logger = logging.getLogger("ansible_docsmith")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create rich handler
    console = Console(stderr=True)
    handler = RichHandler(
        console=console,
        show_time=False,
        show_path=verbose,
        markup=True,
        rich_tracebacks=True,
    )

    # Set format
    if verbose:
        format_str = "%(name)s: %(message)s"
    else:
        format_str = "%(message)s"

    formatter = logging.Formatter(format_str)
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False
