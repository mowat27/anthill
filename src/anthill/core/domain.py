"""Core domain types and protocols for the Anthill framework.

This module defines the fundamental types used throughout the framework:
- State: Type alias for workflow data (dict[str, Any])
- Channel: Protocol for I/O boundaries and workflow configuration

These types form the foundation for handler signatures and runner operations.
"""
from typing import Any, Protocol


class WorkflowFailedError(Exception):
    """Raised by Runner.fail() to signal a workflow failure.

    This exception is raised when a workflow encounters a fatal error that
    should terminate execution. It is caught by channels to handle workflow
    failures appropriately (e.g., CLI exits with status 1, API logs error).
    """


type State = dict[str, Any]
"""State represents workflow data as a dictionary of key-value pairs.

Handlers receive State as input and return a new State as output. State
should be treated as immutable - always return a new copy with updates
rather than modifying in place.
"""


class Channel(Protocol):
    """Protocol for communication channels that drive workflow execution.

    Channels serve as I/O boundaries for workflows, defining what workflow to
    run (workflow_name), what data to start with (initial_state), and how to
    communicate progress (report_progress, report_error). Implementations adapt
    workflows to different environments like CLI, web servers, or message queues.

    Attributes:
        type: The channel type identifier (e.g., "cli", "api", "web").
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
