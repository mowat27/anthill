import pytest
from typing import Any

from anthill.core.app import App
from anthill.core.runner import Runner


class TestMissionSource:
    def __init__(self, type: str, workflow_name: str) -> None:
        self.type = type
        self.workflow_name = workflow_name
        self.progress_messages: list[str] = []
        self.error_messages: list[str] = []

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        self.progress_messages.append(message)

    def report_error(self, run_id: str, message: str) -> None:
        self.error_messages.append(message)


@pytest.fixture
def runner_factory():
    def _create(app: App, workflow_name: str):
        source = TestMissionSource("test", workflow_name)
        runner = Runner(app, source)
        return runner, source
    return _create
