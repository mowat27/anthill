from typing import Callable

from domain import State
from mission import Mission


# -- Core ----------------------------------------------------------------------


class App:
    def __init__(self):
        pass


def run_workflow(mission: Mission, state: State, steps: list[Callable]):
    for step in steps:
        state = step(mission, state)
    return state
