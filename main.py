import sys
import uuid
from types import FunctionType
from typing import Any, Callable, NoReturn


type State = dict[str, Any]
type AgentRunner = Callable[[Mission, State], State]


def fail_and_exit(message: str, *, exit_code: int = 1) -> NoReturn:
    print(message, file=sys.stderr)
    exit(exit_code)


class UnknownWorkflowError(Exception):
    def __init__(self, workflow_name: str) -> None:
        super().__init__(f"Unknown workflow: {workflow_name}")


class MissionSource:
    def __init__(self, type: str, workflow_name: str) -> None:
        self.type = type
        self.workflow_name = workflow_name

    def report_progress(self, mission_id: str, message: str, **opts: Any) -> None:
        message = f"[{self.workflow_name}, {mission_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, mission_id: str, message: str) -> None:
        self.report_progress(mission_id, message, file=sys.stderr)


class Mission:
    def __init__(self, mission_source: MissionSource, *, initial_state: State = {}) -> None:
        self.id: str = uuid.uuid4().hex[:8]
        self.mission_source = mission_source
        self.initial_state = initial_state

    @property
    def workflow_name(self):
        return self.mission_source.workflow_name

    def report_progress(self, message: str) -> None:
        self.mission_source.report_progress(self.id, message)

    def report_error(self, message: str) -> None:
        self.mission_source.report_error(self.id, message)

    def fail(self, message: str) -> NoReturn:
        fail_and_exit(message)


class App:
    def __init__(self) -> None:
        self._hooks: dict[str, list[FunctionType]] = {"before": []}
        self.workflows: dict[str, FunctionType] = {}
        self.runnables: dict[str, AgentRunner] = {}

    def before(self, fn: FunctionType) -> FunctionType:
        def setup_step(state, mission: Mission) -> State:
            return fn(state, mission)
        self._hooks["before"].append(setup_step)
        return setup_step

    def agent(self, fn: FunctionType) -> None:
        def _agent_fn(mission: Mission, state: State) -> State:
            return fn(mission, state)

        self.runnables[fn.__name__] = _agent_fn

    def workflow(self, fn: FunctionType) -> None:
        def workflow_runner(mission: Mission) -> list[str]:
            return fn(mission)

        self.workflows[fn.__name__] = fn

    def _setup(self, mission: Mission) -> State:
        state: State = mission.initial_state
        for fn in self._hooks["before"]:
            state = fn(state, mission)
        return state

    def run(self, mission: Mission) -> State:
        workflow_name = mission.mission_source.workflow_name
        if workflow_name not in self.workflows:
            raise UnknownWorkflowError(workflow_name)

        workflow = self.workflows[workflow_name]

        state = self._setup(mission)
        for step_name in workflow(mission):
            if step_name not in self.runnables:
                fail_and_exit(f"Unknown step: {step_name}")

            runnable = self.runnables[step_name]
            state = runnable(mission, state)

            if state is None:
                fail_and_exit("Agent returned invalid state: None")

        return state


app = App()


@app.before
def init_state(state, mission: Mission) -> State:
    mission.report_progress(f"Initializing state")
    return {**state, **{"mission_id": mission.id,
                        "workflow_name": mission.workflow_name}}


@app.agent
def plus_1(mission: Mission, state: State) -> State:
    mission.report_progress("adding 1")
    return {**state, **{"result": state["result"] + 1}}


@app.agent
def times_2(mission: Mission, state: State) -> State:
    mission.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


@app.agent
def simulate_failure(mission: Mission, _state: State) -> State | NoReturn:
    mission.mission_source.report_error(mission.id, "simulating a failure")
    mission.fail("Workflow failed")


@app.workflow
def plus_1_times_2(_mission: Mission) -> list[str]:
    return ["plus_1", "times_2"]


@app.workflow
def plus_1_times_2_times_2(_mission: Mission) -> list[str]:
    return ["plus_1", "times_2", "simulate_failure", "times_2"]


def main(workflow_name: str, initial_value: int) -> None:
    mission_source = MissionSource("cli", workflow_name)
    mission = Mission(mission_source, initial_state={"result": initial_value})

    try:
        result = app.run(mission)
        print(
            f"STATUS : {result["workflow_name"]} ({result["mission_id"]}) returned: {result["result"]}")
    except UnknownWorkflowError as ex:
        mission.report_error(str(ex))
        exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        fail_and_exit("Missing argument: workflow_name")

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(workflow_name, initial_value)
