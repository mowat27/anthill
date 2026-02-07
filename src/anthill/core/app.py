"""Application framework for registering and managing workflow handlers.

This module provides:
- App: Central registry for workflow handlers with decorator-based registration
- run_workflow: Helper function for executing sequential handler chains

The App class is the main entry point for defining workflows. Use the @app.handler
decorator to register workflow functions, then pass the app to a Runner for execution.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, NoReturn, TYPE_CHECKING

from anthill.core.domain import State

if TYPE_CHECKING:
    from anthill.core.runner import Runner


# -- Core ----------------------------------------------------------------------


class App:
    """Central registry for workflow handlers.

    The App class manages handler registration and retrieval, allowing workflows
    to be defined as decorated functions and later executed by runners. Each app
    instance maintains its own handler registry and log directory configuration.

    Typical usage:
        app = App(log_dir="logs/")

        @app.handler
        def my_workflow(runner: Runner, state: State) -> State:
            return {**state, "result": "done"}

    Attributes:
        handlers: Dictionary mapping handler names to their functions.
        log_dir: Directory path where Runner instances will write log files.
        worktree_dir: Directory path where git worktrees will be created.
        state_dir: Directory path where Runner instances will write state files.
    """
    def __init__(self, log_dir: str = "agents/logs/", worktree_dir: str = "trees/", state_dir: str = ".anthill/state/") -> None:
        """Initialize a new App instance with an empty handler registry.

        Args:
            log_dir: Directory for log files. Defaults to "agents/logs/".
            worktree_dir: Directory for git worktrees. Defaults to "trees/".
            state_dir: Directory for state files. Defaults to ".anthill/state/".
        """
        self.handlers = {}
        self.log_dir = log_dir
        self.worktree_dir = worktree_dir
        self.state_dir = state_dir

    def handler(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Register a function as a workflow handler.

        This decorator registers a workflow handler function and wraps it for execution.
        The handler's name becomes its registry key for lookup by runners.

        Args:
            fn: A callable that accepts a Runner and State and returns a State
                or NoReturn (exits). The function's name is used as the handler key.

        Returns:
            The wrapped handler function that can be invoked by runners.
        """
        @functools.wraps(fn)
        def wrapper(runner: Runner, state: State) -> State | NoReturn:
            return fn(runner, state)

        name: str = fn.__name__  # type: ignore[attr-defined]
        self.handlers[name] = fn
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


def run_workflow(runner: Runner, state: State, steps: list[Callable[[Runner, State], State]]) -> State:
    """Execute a sequence of workflow steps with state threading.

    Each step receives the runner and current state, processes it, and returns
    an updated state that is passed to the next step. All steps are logged.

    Args:
        runner: The Runner instance executing the workflow.
        state: The initial state dictionary.
        steps: A list of callables that each accept (runner, state) and return
               the updated state.

    Returns:
        The final state after all steps have been executed.
    """
    runner.logger.info(f"run_workflow started with {len(steps)} steps: {[getattr(s, '__name__', repr(s)) for s in steps]}")
    for step in steps:
        step_name = getattr(step, "__name__", repr(step))
        runner.logger.info(f"Executing step: {step_name}")
        state = step(runner, state)
        runner._persist_state(state)
        runner.logger.debug(f"Step completed: {step_name}, state keys: {list(state.keys())}")
    runner.logger.info("run_workflow completed")
    return state
