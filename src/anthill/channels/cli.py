"""CLI channel implementation for Anthill workflows.

Provides progress reporting and error handling for command-line environments.
"""
import sys
from typing import Any

from anthill.core.domain import State


class CliChannel:
    """Channel adapter for command-line interface workflows.

    Handles progress reporting and error messaging through stdout/stderr
    for workflows executed in CLI environments.
    """

    def __init__(self, workflow_name: str, initial_state: dict[str, str] | None = None) -> None:
        """Initialize CLI channel with workflow configuration.

        Args:
            workflow_name: Name of the workflow for display purposes.
            initial_state: Optional dictionary of initial state key-value pairs.
        """
        self.type = "cli"
        self.workflow_name = workflow_name
        self.initial_state: State = {**(initial_state or {})}

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        """Report workflow progress to stdout.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Progress message to display.
            **opts: Additional keyword arguments passed to print().
        """
        message = f"[{self.workflow_name}, {run_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, run_id: str, message: str) -> None:
        """Report workflow error to stderr.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Error message to display.
        """
        self.report_progress(run_id, message, file=sys.stderr)
