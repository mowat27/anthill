import sys
from typing import Any

class MissionSource:
    def __init__(self, type: str, workflow_name: str) -> None:
        self.type = type
        self.workflow_name = workflow_name

    def report_progress(self, mission_id: str, message: str, **opts: Any) -> None:
        message = f"[{self.workflow_name}, {mission_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, mission_id: str, message: str) -> None:
        self.report_progress(mission_id, message, file=sys.stderr)
