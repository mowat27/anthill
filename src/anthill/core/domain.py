from typing import Any, Protocol


type State = dict[str, Any]


class Channel(Protocol):
    type: str
    workflow_name: str
    initial_state: State
    def report_progress(self, run_id: str, message: str, **opts: Any) -> None: ...
    def report_error(self, run_id: str, message: str) -> None: ...
