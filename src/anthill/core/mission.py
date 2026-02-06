import sys
import uuid

from anthill.sources.cli import CliMissionSource
from typing import NoReturn
from anthill.core.domain import State
from anthill.core.app import App


class Mission:
    def __init__(self, app: App, mission_source: CliMissionSource) -> None:
        self.id: str = uuid.uuid4().hex[:8]
        self.mission_source = mission_source
        self.app = app

    def run(self, initial_state: State = {}) -> State:
        state = {**{
            "mission_id": self.id,
            "workflow_name": self.workflow_name,
        }, **initial_state}

        return self.workflow(self, state)

    @property
    def workflow_name(self):
        return self.mission_source.workflow_name

    @property
    def workflow(self):
        return self.app.get_handler(self.workflow_name)

    def report_progress(self, message: str) -> None:
        self.mission_source.report_progress(self.id, message)

    def report_error(self, message: str) -> None:
        self.mission_source.report_error(self.id, message)

    def fail(self, message: str) -> NoReturn:
        print(message, file=sys.stderr)
        exit(1)
