"""Logging configuration for ansible-docsmith."""

import logging
import sys
from rich.logging import RichHandler
from rich.console import Console


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging with rich handler for better output."""

    # Create logger
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
        rich_tracebacks=True
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

    return logger
