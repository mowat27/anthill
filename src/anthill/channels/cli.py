import sys
from typing import Any

class CliChannel:
    def __init__(self, type: str, workflow_name: str) -> None:
        self.type = type
        self.workflow_name = workflow_name

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        message = f"[{self.workflow_name}, {run_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, run_id: str, message: str) -> None:
        self.report_progress(run_id, message, file=sys.stderr)
