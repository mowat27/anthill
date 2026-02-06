import pytest

from anthill.core.app import App, run_workflow
from anthill.core.domain import State


class TestWorkflows:
    def test_single_handler(self, mission_factory):
        app = App()

        @app.handler
        def add_1(mission, state: State) -> State:
            mission.report_progress("adding 1")
            return {**state, "result": state["result"] + 1}

        mission, source = mission_factory(app, "add_1")
        result = mission.run({"result": 10})
        assert result["result"] == 11
        assert source.progress_messages == ["adding 1"]

    def test_multi_step_workflow(self, mission_factory):
        app = App()

        @app.handler
        def add_1(mission, state: State) -> State:
            mission.report_progress("adding 1")
            return {**state, "result": state["result"] + 1}

        @app.handler
        def double(mission, state: State) -> State:
            mission.report_progress("doubling")
            return {**state, "result": state["result"] * 2}

        @app.handler
        def add_1_then_double(mission, state: State) -> State:
            return run_workflow(mission, state, [add_1, double])

        mission, source = mission_factory(app, "add_1_then_double")
        result = mission.run({"result": 10})
        assert result["result"] == 22
        assert source.progress_messages == ["adding 1", "doubling"]

    def test_failure(self, mission_factory):
        app = App()

        @app.handler
        def blow_up(mission, _state: State):
            mission.report_error("something broke")
            mission.fail("Workflow failed")

        mission, source = mission_factory(app, "blow_up")
        with pytest.raises(SystemExit):
            mission.run({"result": 1})
        assert source.error_messages == ["something broke"]

    def test_unknown_workflow(self, mission_factory):
        app = App()
        mission, _source = mission_factory(app, "nonexistent")
        with pytest.raises(ValueError, match="Unknown handler: nonexistent"):
            mission.run({})
