import sys
import uuid

from mission_source import MissionSource
from typing import NoReturn
from domain import State


class Mission:
    def __init__(self, mission_source: MissionSource) -> None:
        self.id: str = uuid.uuid4().hex[:8]
        self.mission_source = mission_source

    @property
    def workflow_name(self):
        return self.mission_source.workflow_name

    def report_progress(self, message: str) -> None:
        self.mission_source.report_progress(self.id, message)

    def report_error(self, message: str) -> None:
        self.mission_source.report_error(self.id, message)

    def fail(self, message: str) -> NoReturn:
        print(message, file=sys.stderr)
        exit(1)
