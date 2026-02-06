"""Example workflow handlers for the Anthill framework.

This module demonstrates basic handler patterns including state initialization,
simple transformations, failure simulation, and workflow composition.
"""

from anthill.core.runner import Runner

from typing import NoReturn
from anthill.core.domain import State

from anthill.core.app import App, run_workflow

app = App()

# -- Agents --------------------------------------------------------------------


@app.handler
def init_state(runner: Runner, state: State) -> State | NoReturn:
    """Initialize workflow state with run metadata.

    Args:
        runner: The runner executing this handler.
        state: Current workflow state.

    Returns:
        Updated state with run_id and workflow_name added.
    """
    runner.report_progress("Initializing state")
    return {**state, **{"run_id": runner.id,
                        "workflow_name": runner.workflow_name}}


@app.handler
def plus_1(runner: Runner, state: State) -> State | NoReturn:
    """Add 1 to the result value in state.

    Args:
        runner: The runner executing this handler.
        state: Current workflow state containing a 'result' key.

    Returns:
        Updated state with result incremented by 1.
    """
    runner.report_progress("adding 1")
    return {**state, **{"result": int(state["result"]) + 1}}


@app.handler
def times_2(runner: Runner, state: State) -> State | NoReturn:
    """Multiply the result value in state by 2.

    Args:
        runner: The runner executing this handler.
        state: Current workflow state containing a 'result' key.

    Returns:
        Updated state with result multiplied by 2.
    """
    runner.report_progress("multiplying by 2")
    return {**state, **{"result": int(state["result"]) * 2}}


@app.handler
def simulate_failure(runner: Runner, _state: State) -> State | NoReturn:
    """Simulate a workflow failure for testing error handling.

    Args:
        runner: The runner executing this handler.
        _state: Current workflow state (unused).

    Raises:
        SystemExit: Always raises via runner.fail() to terminate the workflow.
    """
    runner.channel.report_error(runner.id, "simulating a failure")
    runner.fail("Workflow failed")


@app.handler
def plus_1_times_2(runner: Runner, state: State) -> State | NoReturn:
    """Execute a composite workflow: initialize, add 1, then multiply by 2.

    Args:
        runner: The runner executing this handler.
        state: Current workflow state.

    Returns:
        State after executing the init_state, plus_1, and times_2 handlers.
    """
    return run_workflow(runner, state, [init_state, plus_1, times_2])


@app.handler
def plus_1_times_2_times_2(runner: Runner, state: State) -> State | NoReturn:
    """Execute a nested composite workflow: (result + 1) * 2 * 2.

    Args:
        runner: The runner executing this handler.
        state: Current workflow state.

    Returns:
        State after executing plus_1_times_2 followed by times_2.
    """
    return run_workflow(runner, state, [plus_1_times_2, times_2])
