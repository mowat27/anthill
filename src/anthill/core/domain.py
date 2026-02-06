from typing import Any, Protocol


class Channel(Protocol):
    type: str
    workflow_name: str
    def report_progress(self, run_id: str, message: str, **opts: Any) -> None: ...
    def report_error(self, run_id: str, message: str) -> None: ...


type State = dict[str, Any]
