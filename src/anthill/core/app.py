from __future__ import annotations

from typing import Callable, NoReturn, TYPE_CHECKING

from anthill.core.domain import State

if TYPE_CHECKING:
    from anthill.core.runner import Runner


# -- Core ----------------------------------------------------------------------


class App:
    def __init__(self):
        self.handlers = {}

    def handler(self, fn):
        def wrapper(runner: Runner, state: State) -> State | NoReturn:
            return fn(runner, state)

        self.handlers[fn.__name__] = fn
        return wrapper

    def get_handler(self, name: str) -> Callable[[Runner, State], State | NoReturn]:
        try:
            return self.handlers[name]
        except KeyError:
            raise ValueError(f"Unknown handler: {name}")


def run_workflow(runner: Runner, state: State, steps: list[Callable]):
    for step in steps:
        state = step(runner, state)
    return state
