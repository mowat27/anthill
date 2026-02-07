"""Core workflow execution tests.

Tests the framework's ability to execute single handlers, multi-step workflows,
error handling, and handler resolution.
"""

import pytest

from antkeeper.core.app import run_workflow
from antkeeper.core.domain import State, WorkflowFailedError


class TestWorkflows:
    """Test suite for workflow execution and handler composition."""
    def test_single_handler(self, app, runner_factory):
        """Test execution of a workflow with a single handler."""

        @app.handler
        def add_1(runner, state: State) -> State:
            runner.report_progress("adding 1")
            return {**state, "result": state["result"] + 1}

        runner, source = runner_factory(app, "add_1", {"result": 10})
        result = runner.run()
        assert result["result"] == 11
        assert source.progress_messages == ["adding 1"]

    def test_multi_step_workflow(self, app, runner_factory):
        """Test execution of a workflow composed of multiple sequential handlers."""

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

        runner, source = runner_factory(app, "add_1_then_double", {"result": 10})
        result = runner.run()
        assert result["result"] == 22
        assert source.progress_messages == ["adding 1", "doubling"]

    def test_failure(self, app, runner_factory):
        """Test that workflow failure is propagated correctly via WorkflowFailedError."""

        @app.handler
        def blow_up(runner, _state: State):
            runner.report_error("something broke")
            runner.fail("Workflow failed")

        runner, source = runner_factory(app, "blow_up", {"result": 1})
        with pytest.raises(WorkflowFailedError):
            runner.run()
        assert source.error_messages == ["something broke"]

    def test_unknown_workflow(self, app, runner_factory):
        """Test that attempting to run an unregistered handler raises ValueError."""
        runner, _source = runner_factory(app, "nonexistent")
        with pytest.raises(ValueError, match="Unknown handler: nonexistent"):
            runner.run()
