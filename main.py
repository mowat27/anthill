import sys

from mission_source import MissionSource
from mission import Mission

from typing import Callable, NoReturn
from domain import State

from core import App, run_workflow

app = App()

# -- Agents --------------------------------------------------------------------


@app.handler
def init_state(mission: Mission, state: State) -> State | NoReturn:
    mission.report_progress("Initializing state")
    return {**state, **{"mission_id": mission.id,
                        "workflow_name": mission.workflow_name}}


@app.handler
def plus_1(mission: Mission, state: State) -> State | NoReturn:
    mission.report_progress("adding 1")
    return {**state, **{"result": state["result"] + 1}}


@app.handler
def times_2(mission: Mission, state: State) -> State | NoReturn:
    if state is None:
        state = mission.initial_state
    mission.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


@app.handler
def simulate_failure(mission: Mission, _state: State) -> State | NoReturn:
    mission.mission_source.report_error(mission.id, "simulating a failure")
    mission.fail("Workflow failed")


@app.handler
def plus_1_times_2(mission: Mission, state: State) -> State | NoReturn:
    return run_workflow(mission, state, [init_state, plus_1, times_2])


@app.handler
def plus_1_times_2_times_2(mission: Mission, state: State):
    return run_workflow(mission, state, [plus_1_times_2, times_2])

# -- Main ----------------------------------------------------------------------


def main(workflow: Callable, initial_value: int) -> None:
    mission_source = MissionSource("cli", workflow.__name__)
    mission = Mission(app, mission_source)

    initial_state = {
        "result": initial_value
    }

    result = mission.run(initial_state)
    print(
        f"STATUS : {result["workflow_name"]} ({result["mission_id"]}) returned: {result["result"]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Missing argument: workflow_name", file=sys.stdout)
        exit(1)

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    try:
        workflow = app.get_handler(workflow_name)
    except ValueError as ex:
        print(str(ex))
        exit(1)

    main(workflow, initial_value)
