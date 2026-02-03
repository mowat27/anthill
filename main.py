import sys
from operator import methodcaller
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

        def runner(mission, state=None) -> State:
            if state is None:
                state = mission.initial_state

            for step in workflow:
                state = step(mission, state)
            return state

        yield (workflow, runner)


app = App()


def def_workflow(app: App, steps: list[Callable] = []):
    with app.workflow() as (_steps, runner):
        _steps.extend(steps)
        return runner

# -- Agents --------------------------------------------------------------------


def init_state(mission: Mission, state: State) -> State | NoReturn:
    mission.report_progress("Initializing state")
    return {**state, **{"mission_id": mission.id,
                        "workflow_name": mission.workflow_name}}


def plus_1(mission: Mission, state: State) -> State | NoReturn:
    mission.report_progress("adding 1")
    return {**state, **{"result": state["result"] + 1}}


def times_2(mission: Mission, state: State) -> State | NoReturn:
    if state is None:
        state = mission.initial_state
    mission.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


def simulate_failure(mission: Mission, _state: State) -> State | NoReturn:
    mission.mission_source.report_error(mission.id, "simulating a failure")
    mission.fail("Workflow failed")


# -- Agents --------------------------------------------------------------------

plus_1_times_2 = def_workflow(app, [init_state, plus_1, times_2])
plus_1_times_2_times_2 = def_workflow(app, [plus_1_times_2, times_2])


def main(workflow: Callable, initial_value: int) -> None:
    mission_source = MissionSource("cli", workflow.__name__)
    mission = Mission(mission_source)

    initial_state = {
        "mission_id": mission.id,
        "workflow_name": mission.workflow_name,
        "result": initial_value
    }

    result = workflow(mission, initial_state)
    print(
        f"STATUS : {result["workflow_name"]} ({result["mission_id"]}) returned: {result["result"]}")


def resolve_workflow_name(workflow_name):
    this = sys.modules[__name__]
    return this.__dict__[workflow_name]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Missing argument: workflow_name", file=sys.stdout)
        exit(1)

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    workflow = resolve_workflow_name(workflow_name)

    main(workflow, initial_value)
