import pytest

from anthill.core.app import App, run_workflow
from anthill.core.domain import State


class TestWorkflows:
    def test_single_handler(self, runner_factory):
        app = App()

        @app.handler
        def add_1(runner, state: State) -> State:
            runner.report_progress("adding 1")
            return {**state, "result": state["result"] + 1}

        runner, source = runner_factory(app, "add_1")
        result = runner.run({"result": 10})
        assert result["result"] == 11
        assert source.progress_messages == ["adding 1"]

    def test_multi_step_workflow(self, runner_factory):
        app = App()

        @app.handler
        def add_1(runner, state: State) -> State:
            runner.report_progress("adding 1")
            return {**state, "result": state["result"] + 1}

        @app.handler
        def double(runner, state: State) -> State:
            runner.report_progress("doubling")
            return {**state, "result": state["result"] * 2}

        @app.handler
        def add_1_then_double(runner, state: State) -> State:
            return run_workflow(runner, state, [add_1, double])

        runner, source = runner_factory(app, "add_1_then_double")
        result = runner.run({"result": 10})
        assert result["result"] == 22
        assert source.progress_messages == ["adding 1", "doubling"]

    def test_failure(self, runner_factory):
        app = App()

        @app.handler
        def blow_up(runner, _state: State):
            runner.report_error("something broke")
            runner.fail("Workflow failed")

        runner, source = runner_factory(app, "blow_up")
        with pytest.raises(SystemExit):
            runner.run({"result": 1})
        assert source.error_messages == ["something broke"]

    def test_unknown_workflow(self, runner_factory):
        app = App()
        runner, _source = runner_factory(app, "nonexistent")
        with pytest.raises(ValueError, match="Unknown handler: nonexistent"):
            runner.run({})
