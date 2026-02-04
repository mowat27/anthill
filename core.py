from typing import Callable, NoReturn

from domain import State
from mission import Mission


# -- Core ----------------------------------------------------------------------


class App:
    def __init__(self):
        self.handlers = {}

    def handler(self, fn):
        def runner(mission: Mission, state: State) -> State | NoReturn:
            return fn(mission, state)

        self.handlers[fn.__name__] = fn
        return runner

    def get_handler(self, name: str) -> Callable[[Mission, State], State | NoReturn]:
        try:
            return self.handlers[name]
        except KeyError as ex:
            raise ValueError(f"Unknown handler: {name}")


def run_workflow(mission: Mission, state: State, steps: list[Callable]):
    for step in steps:
        state = step(mission, state)
    return state
