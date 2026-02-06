import sys
from typing import Any

from anthill.core.domain import State


class CliChannel:
    def __init__(self, workflow_name: str, initial_state: dict[str, str] | None = None) -> None:
        self.type = "cli"
        self.workflow_name = workflow_name
        self.initial_state: State = {**(initial_state or {})}

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        message = f"[{self.workflow_name}, {run_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, run_id: str, message: str) -> None:
        self.report_progress(run_id, message, file=sys.stderr)
