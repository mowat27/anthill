"""CLI channel implementation for Antkeeper workflows.

This module provides the CliChannel class, which implements the Channel
protocol for command-line interface environments. It handles progress
reporting to stdout and error reporting to stderr.
"""
import logging
import sys
from typing import Any

from antkeeper.core.domain import State

logger = logging.getLogger("antkeeper.channels.cli")


class CliChannel:
    """Channel adapter for command-line interface workflows.

    Implements the Channel protocol for CLI environments. Progress messages
    are written to stdout with flush=True for immediate display. Error messages
    are written to stderr.

    Attributes:
        type: Always "cli" to identify this channel type.
        workflow_name: The name of the workflow being executed.
        initial_state: The initial state dictionary for the workflow.
    """

    def __init__(self, workflow_name: str, initial_state: dict[str, str] | None = None) -> None:
        """Initialize CLI channel with workflow configuration.

        Args:
            workflow_name: Name of the workflow for display purposes and logging.
            initial_state: Optional dictionary of initial state key-value pairs.
                Defaults to an empty dict if not provided.
        """
        self.type = "cli"
        self.workflow_name = workflow_name
        self.initial_state: State = {**(initial_state or {})}
        logger.debug(f"CliChannel initialized: workflow_name={workflow_name}")

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        """Report workflow progress to stdout.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Progress message to display.
            **opts: Additional keyword arguments passed to print().
        """
        logger.debug(f"Progress [{run_id}]: {message}")
        message = f"[{self.workflow_name}, {run_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, run_id: str, message: str) -> None:
        """Report workflow error to stderr.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Error message to display.
        """
        logger.debug(f"Error [{run_id}]: {message}")
        self.report_progress(run_id, message, file=sys.stderr)
