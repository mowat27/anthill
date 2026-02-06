"""Workflow execution engine.

This module provides the Runner class which orchestrates workflow execution,
manages run state, and provides communication utilities for handlers.
"""
import sys
import uuid

from typing import NoReturn

from anthill.core.domain import State, Channel
from anthill.core.app import App


class Runner:
    """Executes workflows by invoking handlers with state management.

    The Runner bridges the gap between channels (which define what to run)
    and apps (which define how to run it), managing execution lifecycle
    and providing utilities for progress reporting and error handling.
    """
    def __init__(self, app: App, channel: Channel) -> None:
        """Initialize a new Runner instance.

        Args:
            app: The App instance containing registered handlers.
            channel: The Channel instance defining the workflow to execute.
        """
        self.id: str = uuid.uuid4().hex[:8]
        self.channel = channel
        self.app = app

    def run(self) -> State:
        """Execute the workflow with initial state setup.

        Returns:
            The final state after workflow execution completes.
        """
        state = {**self.channel.initial_state, "run_id": self.id, "workflow_name": self.workflow_name}

        return self.workflow(self, state)

    @property
    def workflow_name(self):
        """Get the workflow name from the channel.

        Returns:
            The workflow name string.
        """
        return self.channel.workflow_name

    @property
    def workflow(self):
        """Get the workflow handler from the app.

        Returns:
            The workflow handler callable.
        """
        return self.app.get_handler(self.workflow_name)

    def report_progress(self, message: str) -> None:
        """Report progress through the channel.

        Args:
            message: Progress message to report.
        """
        self.channel.report_progress(self.id, message)

    def report_error(self, message: str) -> None:
        """Report an error through the channel.

        Args:
            message: Error message to report.
        """
        self.channel.report_error(self.id, message)

    def fail(self, message: str) -> NoReturn:
        """Fail the workflow with an error message and exit.

        Args:
            message: Error message to print to stderr before exiting.

        Raises:
            SystemExit: Always exits with code 1.
        """
        print(message, file=sys.stderr)
        exit(1)
