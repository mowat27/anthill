import sys

from anthill.channels.cli import CliChannel
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
    return {**state, **{"result": state["result"] + 1}}


@app.handler
def times_2(runner: Runner, state: State) -> State | NoReturn:
    if state is None:
        state = runner.initial_state
    runner.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


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

# -- Main ----------------------------------------------------------------------


def main(workflow_name: str, initial_value: int) -> None:
    channel = CliChannel("cli", workflow_name)
    runner = Runner(app, channel)

    initial_state = {
        "result": initial_value
    }

    result = runner.run(initial_state)
    print(
        f"STATUS : {result["workflow_name"]} ({result["run_id"]}) returned: {result["result"]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Missing argument: workflow_name", file=sys.stdout)
        exit(1)

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    try:
        app.get_handler(workflow_name)
    except ValueError as ex:
        print(str(ex))
        exit(1)

    main(workflow_name, initial_value)
