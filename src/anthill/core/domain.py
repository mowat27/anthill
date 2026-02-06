"""Core domain types and protocols for the Anthill framework.

This module defines the fundamental types used throughout the framework,
including State for workflow data and Channel for communication.
"""
from typing import Any, Protocol


type State = dict[str, Any]
"""State represents workflow data as a dictionary of key-value pairs."""


class Channel(Protocol):
    """Protocol for communication channels that drive workflow execution.

    Channels encapsulate the workflow configuration (type, name, initial state)
    and provide methods for reporting progress and errors during execution.

    Attributes:
        type: The channel type identifier (e.g., "cli", "api").
        workflow_name: The name of the workflow to execute.
        initial_state: The initial state dictionary for the workflow.
    """
    type: str
    workflow_name: str
    initial_state: State

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        """Report workflow progress.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Progress message to report.
            **opts: Additional options for progress reporting.
        """
        ...

    def report_error(self, run_id: str, message: str) -> None:
        """Report a workflow error.

        Args:
            run_id: Unique identifier for the workflow run.
            message: Error message to report.
        """
        ...
