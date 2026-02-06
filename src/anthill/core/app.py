"""Application framework for registering and managing workflow handlers.

This module provides the App class which serves as the central registry for
workflow handlers and the run_workflow function for executing handler chains.
"""
from __future__ import annotations

from typing import Callable, NoReturn, TYPE_CHECKING

from anthill.core.domain import State

if TYPE_CHECKING:
    from anthill.core.runner import Runner


# -- Core ----------------------------------------------------------------------


class App:
    """Central registry for workflow handlers.

    The App class manages handler registration and retrieval, allowing workflows
    to be defined as decorated functions and later executed by runners.
    """
    def __init__(self):
        """Initialize a new App instance with an empty handler registry."""
        self.handlers = {}

    def handler(self, fn):
        """Register a function as a workflow handler.

        Args:
            fn: A callable that accepts a Runner and State and returns a State
                or NoReturn (exits). The function's name is used as the handler key.

        Returns:
            The wrapped handler function that can be invoked by runners.
        """
        def wrapper(runner: Runner, state: State) -> State | NoReturn:
            return fn(runner, state)

        self.handlers[fn.__name__] = fn
        return wrapper

    def get_handler(self, name: str) -> Callable[[Runner, State], State | NoReturn]:
        """Retrieve a registered handler by name.

        Args:
            name: The handler function name to retrieve.

        Returns:
            The handler callable that accepts a Runner and State.

        Raises:
            ValueError: If no handler with the given name is registered.
        """
        try:
            return self.handlers[name]
        except KeyError:
            raise ValueError(f"Unknown handler: {name}")


def run_workflow(runner: Runner, state: State, steps: list[Callable]):
    """Execute a sequence of workflow steps with state threading.

    Args:
        runner: The Runner instance executing the workflow.
        state: The initial state dictionary.
        steps: A list of callables that each accept (runner, state) and return
               the updated state.

    Returns:
        The final state after all steps have been executed.
    """
    for step in steps:
        state = step(runner, state)
    return state
