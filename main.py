import sys
import uuid


def always(value):
    def thunk(*_args, **_vargs):
        return value
    return thunk


def fail_and_exit(message, *, exit_code=1):
    print(message, file=sys.stderr)
    exit(exit_code)


class MissionSource:
    def __init__(self, type, workflow_name, opts={}):
        self.type = type
        self.workflow_name = workflow_name
        self.mission_id = uuid.uuid4().hex[:8]
        self.opts = opts

    def report_progress(self, message, **opts):
        message = f"[{self.workflow_name}, {self.mission_id}] {message}"
        print(message, flush=True, **opts)

    def report_error(self, message):
        self.report_progress(message, file=sys.stderr)


class Mission:
    def __init__(self, mission_source):
        self.mission_source = mission_source
        self.id = uuid.uuid4().hex[:8]
        self.state = {}
        self.steps = []

    def fail(self, message):
        fail_and_exit(message)


class App:
    def __init__(self):
        self.runnables = {}
        self.setup_state = always({})

    def init_state(self, fn):
        def initializer(mission, initial_value=None):
            mission.mission_source.report_progress("Initializing state")
            return fn(mission, initial_value)

        self.setup_state = initializer
        return initializer

    def agent(self, fn):
        def agent_runner(mission, state):
            mission.state = fn(mission, state)
            return mission.state

        self.runnables[fn.__name__] = agent_runner
        return agent_runner

    def run(self, mission, initial_value=None):
        state = self.setup_state(mission, initial_value)
        for step_name in mission.steps:
            print(state)
            if step_name not in self.runnables:
                fail_and_exit(f"Unknown step: {step_name}")

            runnable = self.runnables[step_name]
            state = runnable(mission, state)

            if state is None:
                fail_and_exit("Agent returned invalid state: None")

        return state


app = App()


@app.init_state
def init_state(mission, initial_value=None):
    return {
        "result": int(initial_value) if initial_value else 0
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
def simulate_failure(mission, state):
    mission.mission_source.report_error("simulating a failure")
    mission.fail("Workflow failed")


def main(workflow_name, initial_value):
    mission_source = MissionSource("cli", workflow_name)
    mission = Mission(mission_source)

    if workflow_name == 'plus_1_times_2':
        mission.steps = ["plus_1", "times_2"]
    elif workflow_name == 'plus_1_times_2_times_2':
        mission.steps = ["plus_1", "times_2", "simulate_failure", "times_2"]
    else:
        fail_and_exit(f"Unknown workflow: {workflow_name}")

    print(app.run(mission, initial_value)["result"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        fail_and_exit("Missing argument: workflow_name")

    workflow_name = sys.argv[1]
    initial_value = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(workflow_name, initial_value)
