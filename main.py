import sys
import uuid


class MissionSource:
    def __init__(self, type, workflow_name, opts={}):
        self.type = type
        self.workflow_name = workflow_name
        self.mission_id = uuid.uuid4().hex[:8]
        self.opts = opts

    def report_progress(self, message, *, opts={}):
        message = f"[{self.workflow_name}, {self.mission_id}] {message}"
        print(message, {**opts, **{"flush": True}})

    def report_error(self, message):
        self.report_progress(message, file=sys.stderr)


class Mission:
    def __init__(self, mission_source):
        self.mission_source = mission_source
        self.id = uuid.uuid4().hex[:8]
        self.state = {}
        self.steps = []


def always(value):
    def thunk(*_args, **_vargs):
        return value
    return thunk


def fail(message, *, exit_code=1):
    print(message, file=sys.stderr)
    exit(exit_code)


class App:
    def __init__(self):
        self.runnables = {}
        self.setup_state = always({})

    def init_state(self, fn):
        def initializer(mission):
            mission.mission_source.report_progress("Initializing state")
            return fn(mission)

        self.setup_state = initializer
        return initializer

    def agent(self, fn):
        def agent_runner(mission, state):
            mission.state = fn(mission, state)
            return mission.state

        self.runnables[fn.__name__] = agent_runner
        return agent_runner

    def run(self, mission):
        state = self.setup_state(mission)
        for step_name in mission.steps:
            if step_name not in self.runnables:
                fail(f"Unknown step: {step_name}")

            runnable = self.runnables[step_name]
            state = runnable(mission, state)

            if state is None:
                fail("Agent returned invalid state: None")

        return state


app = App()


@app.init_state
def init_state(mission):
    return {
        "result": 0
    }


@app.agent
def plus_1(mission, state):
    mission.mission_source.report_progress("adding 1")
    return {**state, **{"result": state["result"] + 1}}


@app.agent
def times_2(mission, state):
    mission.mission_source.report_progress("multiplying by 2")
    return {**state, **{"result": state["result"] * 2}}


@app.agent
def failing_agent(mission, state):
    mission.mission_source.report_error("simulating a failure")
    mission.fail()


def main():
    mission_source = MissionSource("cli", "plus_one_times_2")
    mission = Mission(mission_source)
    mission.steps = ["plus_1", "times_2"]

    print(app.run(mission))


if __name__ == "__main__":
    if len(sys.argv) < 1:
        fail("Missing argument: workflow_name")

    main()
