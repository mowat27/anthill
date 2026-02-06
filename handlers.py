from anthill.core.runner import Runner

from typing import NoReturn
from anthill.core.domain import State

from anthill.core.app import App, run_workflow

app = App()

# -- Agents --------------------------------------------------------------------


@app.handler
def init_state(runner: Runner, state: State) -> State | NoReturn:
    runner.report_progress("Initializing state")
    return {**state, **{"run_id": runner.id,
                        "workflow_name": runner.workflow_name}}


@app.handler
def plus_1(runner: Runner, state: State) -> State | NoReturn:
    runner.report_progress("adding 1")
    return {**state, **{"result": int(state["result"]) + 1}}


@app.handler
def times_2(runner: Runner, state: State) -> State | NoReturn:
    runner.report_progress("multiplying by 2")
    return {**state, **{"result": int(state["result"]) * 2}}


@app.handler
def simulate_failure(runner: Runner, _state: State) -> State | NoReturn:
    runner.channel.report_error(runner.id, "simulating a failure")
    runner.fail("Workflow failed")


@app.handler
def plus_1_times_2(runner: Runner, state: State) -> State | NoReturn:
    return run_workflow(runner, state, [init_state, plus_1, times_2])


@app.handler
def plus_1_times_2_times_2(runner: Runner, state: State):
    return run_workflow(runner, state, [plus_1_times_2, times_2])
