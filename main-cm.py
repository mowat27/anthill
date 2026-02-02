import sys
from contextlib import contextmanager

from mission_source import MissionSource
from mission import Mission

from typing import Callable, NoReturn
from domain import State

# -- Core ----------------------------------------------------------------------


class App:
    @contextmanager
    def workflow(self):
        workflow = []

        def runner(mission):
            state = mission.initial_state
            for step in workflow:
                state = step(mission, state)
            return state

        yield (workflow, runner)


def def_workflow(app: App, steps: list[Callable] = []):
    with app.workflow() as (_steps, runner):
        _steps.extend(steps)
        return runner

# -- Agents --------------------------------------------------------------------


def init_state(mission: Mission, state: State) -> State:
    mission.report_progress("Initializing state")
    return {**state, **{"mission_id": mission.id,
                        "workflow_name": mission.workflow_name}}


def plus_1(mission: Mission, state: State) -> State:
    mission.report_progress("adding 1")
    return {**state, **{"result": state["result"] + 1}}


def times_2(mission: Mission, state: State) -> State:
    mission.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


def simulate_failure(mission: Mission, _state: State) -> State | NoReturn:
    mission.mission_source.report_error(mission.id, "simulating a failure")
    mission.fail("Workflow failed")


# -- Agents --------------------------------------------------------------------

app = App()

plus_1_times_2 = def_workflow(app, [init_state, plus_1, times_2])


def main(workflow_name: str, initial_value: int) -> None:
    mission_source = MissionSource("cli", workflow_name)
    mission = Mission(mission_source, initial_state={"result": initial_value})

    result = plus_1_times_2(mission)
    print(
        f"STATUS : {result["workflow_name"]} ({result["mission_id"]}) returned: {result["result"]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Missing argument: workflow_name", file=sys.stdout)
        exit(1)

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(workflow_name, initial_value)
