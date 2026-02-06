import sys
import uuid

from typing import NoReturn

from anthill.channels.cli import CliChannel
from anthill.core.domain import State
from anthill.core.app import App


class Runner:
    def __init__(self, app: App, channel: CliChannel) -> None:
        self.id: str = uuid.uuid4().hex[:8]
        self.channel = channel
        self.app = app

    def run(self, initial_state: State = {}) -> State:
        state = {**{
            "run_id": self.id,
            "workflow_name": self.workflow_name,
        }, **initial_state}

        return self.workflow(self, state)

    @property
    def workflow_name(self):
        return self.channel.workflow_name

    @property
    def workflow(self):
        return self.app.get_handler(self.workflow_name)

    def report_progress(self, message: str) -> None:
        self.channel.report_progress(self.id, message)

    def report_error(self, message: str) -> None:
        self.channel.report_error(self.id, message)

    def fail(self, message: str) -> NoReturn:
        print(message, file=sys.stderr)
        exit(1)
