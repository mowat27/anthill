"""Shared pytest fixtures and test utilities.

This module provides test doubles and factory fixtures for testing Anthill
workflows without I/O side effects.
"""

import pytest
from typing import Any

from anthill.core.app import App
from anthill.core.domain import State
from anthill.core.runner import Runner


class TestChannel:
    """In-memory test double for workflow channels.

    Captures progress and error messages without performing I/O, enabling
    verification of framework behavior in tests.
    """

    def __init__(self, workflow_name: str, initial_state: State | None = None) -> None:
        self.type = "test"
        self.workflow_name = workflow_name
        self.initial_state: State = initial_state or {}
        self.progress_messages: list[str] = []
        self.error_messages: list[str] = []

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        self.progress_messages.append(message)

    def report_error(self, run_id: str, message: str) -> None:
        self.error_messages.append(message)


@pytest.fixture
def runner_factory():
    """Factory fixture for creating test runners with capturing channels.

    Returns a factory function that creates a Runner with a TestChannel,
    allowing tests to exercise workflows and inspect captured messages.
    """

    def _create(app: App, workflow_name: str, initial_state: State | None = None):
        source = TestChannel(workflow_name, initial_state)
        runner = Runner(app, source)
        return runner, source
    return _create
