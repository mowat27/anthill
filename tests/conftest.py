"""Shared pytest fixtures and test utilities.

This module provides test doubles and factory fixtures for testing Anthill
workflows without I/O side effects.
"""

import tempfile

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
def app():
    """Provide a fresh App with logs directed to a temp directory."""
    return App(log_dir=tempfile.mkdtemp())


@pytest.fixture
def runner_factory(app):
    """Factory fixture for creating test runners with capturing channels.

    Returns a factory function that creates a Runner with a TestChannel,
    allowing tests to exercise workflows and inspect captured messages.
    """

    def _create(test_app: App | None = None, workflow_name: str = "test", initial_state: State | None = None):
        source = TestChannel(workflow_name, initial_state)
        runner = Runner(test_app or app, source)
        return runner, source
    return _create
